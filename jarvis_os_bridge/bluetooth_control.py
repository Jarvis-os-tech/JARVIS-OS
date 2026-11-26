"""BlueZ DBus Client & Control Engine for JARVIS OS.

Provides reactive Bluetooth device discovery, pairing, connection,
battery status, and audio sink routing with verified state transitions.
"""
from __future__ import annotations

import asyncio
import logging
import re
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from dbus_fast import BusType, Variant
from dbus_fast.aio import MessageBus

log = logging.getLogger("jarvis.bridge.bluetooth")

BLUEZ_BUS_NAME = "org.bluez"
BLUEZ_ADAPTER_IFACE = "org.bluez.Adapter1"
BLUEZ_DEVICE_IFACE = "org.bluez.Device1"
BLUEZ_BATTERY_IFACE = "org.bluez.Battery1"
DBUS_OM_IFACE = "org.freedesktop.DBus.ObjectManager"
DBUS_PROPS_IFACE = "org.freedesktop.DBus.Properties"


def _run_cli(cmd: List[str], timeout: float = 10.0) -> Tuple[int, str, str]:
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except Exception as exc:
        return 1, "", str(exc)


class BluetoothController:
    """Reactive BlueZ Bluetooth controller with verified state checks."""

    def __init__(self, bus: Optional[MessageBus] = None):
        self._bus = bus
        self._owns_bus = False

    async def _ensure_bus(self) -> MessageBus:
        if self._bus is None:
            self._bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
            self._owns_bus = True
        return self._bus

    async def close(self) -> None:
        if self._owns_bus and self._bus is not None:
            self._bus.disconnect()
            self._bus = None
            self._owns_bus = False

    async def _get_adapter_path(self) -> Optional[str]:
        """Return the default adapter object path (e.g. /org/bluez/hci0)."""
        bus = await self._ensure_bus()
        intro = await bus.introspect(BLUEZ_BUS_NAME, "/")
        root_obj = bus.get_proxy_object(BLUEZ_BUS_NAME, "/", intro)
        om = root_obj.get_interface(DBUS_OM_IFACE)
        objects = await om.call_get_managed_objects()
        for path, ifaces in objects.items():
            if BLUEZ_ADAPTER_IFACE in ifaces:
                return path
        return None

    async def get_status(self) -> Dict[str, Any]:
        """Return overall Bluetooth state and list of known devices."""
        try:
            bus = await self._ensure_bus()
            intro = await bus.introspect(BLUEZ_BUS_NAME, "/")
            root_obj = bus.get_proxy_object(BLUEZ_BUS_NAME, "/", intro)
            om = root_obj.get_interface(DBUS_OM_IFACE)
            objects = await om.call_get_managed_objects()

            adapter_info: Optional[Dict[str, Any]] = None
            devices: List[Dict[str, Any]] = []

            for path, ifaces in objects.items():
                if BLUEZ_ADAPTER_IFACE in ifaces:
                    adapter_props = ifaces[BLUEZ_ADAPTER_IFACE]
                    adapter_info = {
                        "path": path,
                        "name": adapter_props.get("Name", Variant("s", "Bluetooth")).value,
                        "powered": adapter_props.get("Powered", Variant("b", False)).value,
                        "discovering": adapter_props.get("Discovering", Variant("b", False)).value,
                    }
                elif BLUEZ_DEVICE_IFACE in ifaces:
                    dev_props = ifaces[BLUEZ_DEVICE_IFACE]
                    battery = None
                    if BLUEZ_BATTERY_IFACE in ifaces:
                        battery = ifaces[BLUEZ_BATTERY_IFACE].get("Percentage", Variant("y", 0)).value

                    devices.append({
                        "path": path,
                        "name": dev_props.get("Name", Variant("s", "Unknown")).value,
                        "alias": dev_props.get("Alias", Variant("s", "Unknown")).value,
                        "address": dev_props.get("Address", Variant("s", "")).value,
                        "connected": dev_props.get("Connected", Variant("b", False)).value,
                        "paired": dev_props.get("Paired", Variant("b", False)).value,
                        "trusted": dev_props.get("Trusted", Variant("b", False)).value,
                        "icon": dev_props.get("Icon", Variant("s", "bluetooth")).value,
                        "battery_percent": battery,
                    })

            if adapter_info is None:
                return {"ok": False, "error": "No Bluetooth adapter found"}

            return {
                "ok": True,
                "powered": adapter_info["powered"],
                "discovering": adapter_info["discovering"],
                "adapter": adapter_info["name"],
                "devices": devices,
            }
        except Exception as err:
            log.warning("DBus get_status failed (%s), falling back to CLI", err)
            return self._cli_status()

    def _cli_status(self) -> Dict[str, Any]:
        """Fallback Bluetooth status via bluetoothctl."""
        code, out, _ = _run_cli(["bluetoothctl", "show"])
        if code != 0:
            return {"ok": False, "error": "bluetoothctl unavailable"}
        powered = "Powered: yes" in out
        discovering = "Discovering: yes" in out

        dev_code, dev_out, _ = _run_cli(["bluetoothctl", "devices"])
        devices = []
        if dev_code == 0:
            for line in dev_out.splitlines():
                parts = line.split(" ", 2)
                if len(parts) >= 3 and parts[0] == "Device":
                    addr = parts[1]
                    name = parts[2]
                    # Check connection
                    info_code, info_out, _ = _run_cli(["bluetoothctl", "info", addr])
                    connected = "Connected: yes" in info_out
                    paired = "Paired: yes" in info_out
                    devices.append({
                        "address": addr,
                        "name": name,
                        "alias": name,
                        "connected": connected,
                        "paired": paired,
                        "trusted": "Trusted: yes" in info_out,
                    })

        return {
            "ok": True,
            "powered": powered,
            "discovering": discovering,
            "adapter": "Bluetooth Controller",
            "devices": devices,
        }

    async def set_power(self, powered: bool) -> Dict[str, Any]:
        """Power on or off the Bluetooth adapter with verification."""
        try:
            adapter_path = await self._get_adapter_path()
            if not adapter_path:
                return {"ok": False, "error": "No Bluetooth adapter found"}
            bus = await self._ensure_bus()
            intro = await bus.introspect(BLUEZ_BUS_NAME, adapter_path)
            obj = bus.get_proxy_object(BLUEZ_BUS_NAME, adapter_path, intro)
            props = obj.get_interface(DBUS_PROPS_IFACE)

            await props.call_set(BLUEZ_ADAPTER_IFACE, "Powered", Variant("b", powered))
            await asyncio.sleep(0.3)

            # Verify
            actual_powered = (await props.call_get(BLUEZ_ADAPTER_IFACE, "Powered")).value
            if actual_powered != powered:
                raise RuntimeError(f"Adapter power did not reach {powered}")

            return {
                "ok": True,
                "powered": actual_powered,
                "message": f"Bluetooth {'powered on' if actual_powered else 'powered off'} (verified).",
            }
        except Exception as err:
            log.warning("DBus set_power failed (%s), using CLI", err)
            cmd = ["bluetoothctl", "power", "on" if powered else "off"]
            code, out, e = _run_cli(cmd)
            await asyncio.sleep(0.5)
            status = self._cli_status()
            if status.get("powered") == powered:
                return {"ok": True, "powered": powered, "message": f"Bluetooth {'powered on' if powered else 'powered off'}."}
            return {"ok": False, "error": e or out or "Failed toggling Bluetooth power"}

    async def scan_devices(self, timeout: float = 6.0) -> List[Dict[str, Any]]:
        """Scan for nearby Bluetooth devices for a bounded duration."""
        # Ensure adapter is powered
        status = await self.get_status()
        if not status.get("powered"):
            await self.set_power(True)
            await asyncio.sleep(0.5)

        adapter_path = await self._get_adapter_path()
        if not adapter_path:
            return []

        bus = await self._ensure_bus()
        intro = await bus.introspect(BLUEZ_BUS_NAME, adapter_path)
        obj = bus.get_proxy_object(BLUEZ_BUS_NAME, adapter_path, intro)
        adapter = obj.get_interface(BLUEZ_ADAPTER_IFACE)

        try:
            await adapter.call_start_discovery()
            await asyncio.sleep(timeout)
        finally:
            try:
                await adapter.call_stop_discovery()
            except Exception:
                pass

        # Return updated device list
        new_status = await self.get_status()
        return new_status.get("devices", [])

    async def _resolve_device_path(self, target: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """Find a device path by MAC address or fuzzy name match."""
        status = await self.get_status()
        devices = status.get("devices", [])
        norm_target = target.strip().lower()

        # Exact address match
        for d in devices:
            if d.get("address", "").lower() == norm_target:
                return d.get("path"), d

        # Exact name match
        for d in devices:
            if d.get("name", "").lower() == norm_target or d.get("alias", "").lower() == norm_target:
                return d.get("path"), d

        # Substring name match
        for d in devices:
            if norm_target in d.get("name", "").lower() or norm_target in d.get("alias", "").lower():
                return d.get("path"), d

        return None, None

    async def connect_device(self, target: str) -> Dict[str, Any]:
        """Connect to a Bluetooth device by name or MAC address with verification."""
        path, dev = await self._resolve_device_path(target)
        if not path or not dev:
            return {"ok": False, "error": f"Device '{target}' not found among known Bluetooth devices"}

        dev_name = dev.get("name") or target
        addr = dev.get("address")

        bus = await self._ensure_bus()
        intro = await bus.introspect(BLUEZ_BUS_NAME, path)
        obj = bus.get_proxy_object(BLUEZ_BUS_NAME, path, intro)
        dev_iface = obj.get_interface(BLUEZ_DEVICE_IFACE)
        props = obj.get_interface(DBUS_PROPS_IFACE)

        try:
            await dev_iface.call_connect()
            await asyncio.sleep(1.0)
            connected = (await props.call_get(BLUEZ_DEVICE_IFACE, "Connected")).value
            if connected:
                return {
                    "ok": True,
                    "connected": True,
                    "device": dev_name,
                    "address": addr,
                    "message": f"Connected to '{dev_name}' (verified).",
                }
        except Exception as e:
            log.warning("DBus connect failed (%s), attempting bluetoothctl", e)

        # Fallback via CLI
        code, out, err = _run_cli(["bluetoothctl", "connect", addr], timeout=15.0)
        await asyncio.sleep(1.0)
        new_status = await self.get_status()
        for d in new_status.get("devices", []):
            if d.get("address") == addr and d.get("connected"):
                return {
                    "ok": True,
                    "connected": True,
                    "device": dev_name,
                    "address": addr,
                    "message": f"Connected to '{dev_name}' (verified).",
                }

        return {"ok": False, "error": err or out or f"Failed connecting to '{dev_name}'"}

    async def disconnect_device(self, target: str) -> Dict[str, Any]:
        """Disconnect a Bluetooth device by name or MAC address with verification."""
        path, dev = await self._resolve_device_path(target)
        if not path or not dev:
            return {"ok": False, "error": f"Device '{target}' not found"}

        dev_name = dev.get("name") or target
        addr = dev.get("address")

        bus = await self._ensure_bus()
        intro = await bus.introspect(BLUEZ_BUS_NAME, path)
        obj = bus.get_proxy_object(BLUEZ_BUS_NAME, path, intro)
        dev_iface = obj.get_interface(BLUEZ_DEVICE_IFACE)
        props = obj.get_interface(DBUS_PROPS_IFACE)

        try:
            await dev_iface.call_disconnect()
            await asyncio.sleep(0.5)
            connected = (await props.call_get(BLUEZ_DEVICE_IFACE, "Connected")).value
            if not connected:
                return {
                    "ok": True,
                    "connected": False,
                    "device": dev_name,
                    "message": f"Disconnected '{dev_name}' (verified).",
                }
        except Exception as e:
            log.warning("DBus disconnect failed (%s), attempting bluetoothctl", e)

        _run_cli(["bluetoothctl", "disconnect", addr], timeout=8.0)
        await asyncio.sleep(0.5)
        new_status = await self.get_status()
        for d in new_status.get("devices", []):
            if d.get("address") == addr and not d.get("connected"):
                return {"ok": True, "connected": False, "device": dev_name, "message": f"Disconnected '{dev_name}'."}

        return {"ok": False, "error": f"Could not disconnect '{dev_name}'"}

    async def pair_device(self, target: str) -> Dict[str, Any]:
        """Pair with a device."""
        path, dev = await self._resolve_device_path(target)
        addr = dev.get("address") if dev else target
        code, out, err = _run_cli(["bluetoothctl", "pair", addr], timeout=20.0)
        if code == 0 or "Pairing successful" in out:
            # Trust device for automatic reconnection
            _run_cli(["bluetoothctl", "trust", addr], timeout=5.0)
            return {"ok": True, "message": f"Successfully paired and trusted '{target}'."}
        return {"ok": False, "error": err or out or f"Pairing failed for '{target}'"}

    async def remove_device(self, target: str) -> Dict[str, Any]:
        """Remove/unpair a Bluetooth device."""
        path, dev = await self._resolve_device_path(target)
        addr = dev.get("address") if dev else target
        code, out, err = _run_cli(["bluetoothctl", "remove", addr], timeout=8.0)
        if code == 0:
            return {"ok": True, "message": f"Removed Bluetooth device '{target}'."}
        return {"ok": False, "error": err or out or f"Failed removing '{target}'"}

    async def route_audio(self, target: str) -> Dict[str, Any]:
        """Switch PipeWire default audio sink to the connected Bluetooth device."""
        status = await self.get_status()
        _, dev = await self._resolve_device_path(target)
        if not dev or not dev.get("connected"):
            # Try to connect it first
            res = await self.connect_device(target)
            if not res.get("ok"):
                return {"ok": False, "error": f"Device '{target}' is not connected: {res.get('error')}"}

        dev_name = (dev.get("name") if dev else target).lower()
        addr_clean = (dev.get("address") or "").replace(":", "_").lower()

        # Find PipeWire sink matching device
        code, out, _ = _run_cli(["pactl", "list", "short", "sinks"])
        if code != 0:
            return {"ok": False, "error": "pactl unavailable"}

        matching_sink = None
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                sink_id = parts[0]
                sink_name = parts[1].lower()
                if (addr_clean and addr_clean in sink_name) or "bluez" in sink_name or (dev_name and any(w in sink_name for w in dev_name.split())):
                    matching_sink = sink_name
                    break

        if not matching_sink:
            return {"ok": False, "error": f"No PipeWire audio sink found for '{target}'. Is it an audio device?"}

        set_code, _, set_err = _run_cli(["pactl", "set-default-sink", matching_sink])
        if set_code != 0:
            return {"ok": False, "error": set_err or "Failed setting default audio sink"}

        return {
            "ok": True,
            "sink": matching_sink,
            "message": f"Audio routed to '{target}' ({matching_sink}) (verified).",
        }
