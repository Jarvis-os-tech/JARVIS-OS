"""NetworkManager DBus Client & Control Engine for JARVIS OS.

Provides zero-polling status introspection, WiFi scanning, AP connection,
VPN activation, and saved profile management with verified state transitions.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from dbus_fast import BusType, Variant
from dbus_fast.aio import MessageBus

log = logging.getLogger("jarvis.bridge.network")

NM_BUS_NAME = "org.freedesktop.NetworkManager"
NM_OBJ_PATH = "/org/freedesktop/NetworkManager"
NM_IFACE = "org.freedesktop.NetworkManager"
NM_DEVICE_IFACE = "org.freedesktop.NetworkManager.Device"
NM_WIRELESS_IFACE = "org.freedesktop.NetworkManager.Device.Wireless"
NM_AP_IFACE = "org.freedesktop.NetworkManager.AccessPoint"
NM_SETTINGS_IFACE = "org.freedesktop.NetworkManager.Settings"
NM_CONNECTION_IFACE = "org.freedesktop.NetworkManager.Settings.Connection"
DBUS_PROPS_IFACE = "org.freedesktop.DBus.Properties"

# NM State mappings
NM_STATE_MAP = {
    0: "unknown",
    10: "asleep",
    20: "disconnected",
    30: "disconnecting",
    40: "connecting",
    50: "connected_local",
    60: "connected_site",
    70: "connected_global",
}

NM_CONNECTIVITY_MAP = {
    0: "unknown",
    1: "none",
    2: "portal",
    3: "limited",
    4: "full",
}

# NM Device types
NM_DEVICE_TYPE_WIFI = 2
NM_DEVICE_TYPE_ETHERNET = 1


def _run_cli(cmd: List[str], timeout: float = 10.0) -> Tuple[int, str, str]:
    """Execute command safely without shell expansion."""
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except Exception as exc:
        return 1, "", str(exc)


class NetworkController:
    """Reactive NetworkManager controller using native DBus with verified state checks."""

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

    async def get_status(self) -> Dict[str, Any]:
        """Return comprehensive verified network status."""
        try:
            bus = await self._ensure_bus()
            intro = await bus.introspect(NM_BUS_NAME, NM_OBJ_PATH)
            nm_obj = bus.get_proxy_object(NM_BUS_NAME, NM_OBJ_PATH, intro)
            props = nm_obj.get_interface(DBUS_PROPS_IFACE)

            raw_state = (await props.call_get(NM_IFACE, "State")).value
            raw_conn = (await props.call_get(NM_IFACE, "Connectivity")).value
            primary_path = (await props.call_get(NM_IFACE, "PrimaryConnection")).value

            state_str = NM_STATE_MAP.get(raw_state, "unknown")
            conn_str = NM_CONNECTIVITY_MAP.get(raw_conn, "unknown")
            is_connected = raw_state in (50, 60, 70)

            wifi_info: Optional[Dict[str, Any]] = None
            devices = await nm_obj.get_interface(NM_IFACE).call_get_all_devices()

            for dev_path in devices:
                dev_intro = await bus.introspect(NM_BUS_NAME, dev_path)
                dev_obj = bus.get_proxy_object(NM_BUS_NAME, dev_path, dev_intro)
                dev_props = dev_obj.get_interface(DBUS_PROPS_IFACE)
                dev_type = (await dev_props.call_get(NM_DEVICE_IFACE, "DeviceType")).value

                if dev_type == NM_DEVICE_TYPE_WIFI:
                    iface_name = (await dev_props.call_get(NM_DEVICE_IFACE, "Interface")).value
                    active_ap = (await dev_props.call_get(NM_WIRELESS_IFACE, "ActiveAccessPoint")).value
                    wifi_connected = active_ap != "/" and active_ap != ""
                    ssid = "Disconnected"
                    strength = 0
                    frequency = 0

                    if wifi_connected:
                        try:
                            ap_intro = await bus.introspect(NM_BUS_NAME, active_ap)
                            ap_obj = bus.get_proxy_object(NM_BUS_NAME, active_ap, ap_intro)
                            ap_props = ap_obj.get_interface(DBUS_PROPS_IFACE)
                            ssid_raw = (await ap_props.call_get(NM_AP_IFACE, "Ssid")).value
                            ssid = bytes(ssid_raw).decode("utf-8", errors="replace")
                            strength = int((await ap_props.call_get(NM_AP_IFACE, "Strength")).value)
                            frequency = int((await ap_props.call_get(NM_AP_IFACE, "Frequency")).value)
                        except Exception as e:
                            log.debug("Failed reading active AP: %s", e)

                    wifi_info = {
                        "interface": iface_name,
                        "connected": wifi_connected,
                        "ssid": ssid,
                        "signal_percent": strength,
                        "frequency_mhz": frequency,
                    }
                    break

            # Fetch IP addresses from hostnamectl or ip addr
            ip_addrs = self._get_local_ips()

            return {
                "ok": True,
                "connected": is_connected,
                "state": state_str,
                "connectivity": conn_str,
                "ip_addresses": ip_addrs,
                "wifi": wifi_info,
            }
        except Exception as err:
            log.warning("DBus get_status failed (%s), falling back to CLI", err)
            return self._cli_status()

    def _get_local_ips(self) -> List[str]:
        code, out, _ = _run_cli(["ip", "-br", "-4", "addr", "show", "scope", "global"])
        if code != 0:
            return []
        ips = []
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[1] == "UP":
                ips.append(parts[2].split("/")[0])
        return ips

    def _cli_status(self) -> Dict[str, Any]:
        """Fallback status via nmcli."""
        code, out, _ = _run_cli(["nmcli", "-t", "-f", "STATE,CONNECTIVITY,WIFI", "general", "status"])
        if code != 0:
            return {"ok": False, "connected": False, "state": "unknown", "error": "nmcli unavailable"}
        fields = out.split(":") if out else []
        state = fields[0] if len(fields) > 0 else "unknown"
        conn = fields[1] if len(fields) > 1 else "unknown"

        # Check wifi
        w_code, w_out, _ = _run_cli(["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,FREQ,DEVICE", "dev", "wifi"])
        wifi_info = None
        if w_code == 0:
            for line in w_out.splitlines():
                if line.startswith("*"):
                    parts = line.split(":")
                    if len(parts) >= 5:
                        wifi_info = {
                            "interface": parts[4],
                            "connected": True,
                            "ssid": parts[1],
                            "signal_percent": int(parts[2]) if parts[2].isdigit() else 0,
                            "frequency_mhz": int(parts[3].replace(" MHz", "")) if parts[3].replace(" MHz", "").isdigit() else 0,
                        }
                    break

        return {
            "ok": True,
            "connected": state.lower() == "connected",
            "state": state.lower(),
            "connectivity": conn.lower(),
            "ip_addresses": self._get_local_ips(),
            "wifi": wifi_info,
        }

    async def scan_wifi(self, rescan: bool = True) -> List[Dict[str, Any]]:
        """Scan for available WiFi networks and return sorted unique access points."""
        try:
            bus = await self._ensure_bus()
            intro = await bus.introspect(NM_BUS_NAME, NM_OBJ_PATH)
            nm_obj = bus.get_proxy_object(NM_BUS_NAME, NM_OBJ_PATH, intro)
            devices = await nm_obj.get_interface(NM_IFACE).call_get_all_devices()

            wifi_dev_obj = None
            for dev_path in devices:
                dev_intro = await bus.introspect(NM_BUS_NAME, dev_path)
                dev_obj = bus.get_proxy_object(NM_BUS_NAME, dev_path, dev_intro)
                dev_props = dev_obj.get_interface(DBUS_PROPS_IFACE)
                dev_type = (await dev_props.call_get(NM_DEVICE_IFACE, "DeviceType")).value
                if dev_type == NM_DEVICE_TYPE_WIFI:
                    wifi_dev_obj = dev_obj
                    break

            if wifi_dev_obj is None:
                raise RuntimeError("No wireless interface detected")

            wifi_iface = wifi_dev_obj.get_interface(NM_WIRELESS_IFACE)

            if rescan:
                try:
                    await wifi_iface.call_request_scan({})
                    await asyncio.sleep(1.0)
                except Exception as e:
                    log.debug("RequestScan skipped or rate-limited: %s", e)

            aps = await wifi_iface.call_get_access_points()
            results_by_ssid: Dict[str, Dict[str, Any]] = {}

            for ap_path in aps:
                try:
                    ap_intro = await bus.introspect(NM_BUS_NAME, ap_path)
                    ap_obj = bus.get_proxy_object(NM_BUS_NAME, ap_path, ap_intro)
                    ap_props = ap_obj.get_interface(DBUS_PROPS_IFACE)
                    ssid_raw = (await ap_props.call_get(NM_AP_IFACE, "Ssid")).value
                    ssid = bytes(ssid_raw).decode("utf-8", errors="replace").strip()
                    if not ssid:
                        continue
                    strength = int((await ap_props.call_get(NM_AP_IFACE, "Strength")).value)
                    frequency = int((await ap_props.call_get(NM_AP_IFACE, "Frequency")).value)
                    flags = int((await ap_props.call_get(NM_AP_IFACE, "Flags")).value)
                    wpa_flags = int((await ap_props.call_get(NM_AP_IFACE, "WpaFlags")).value)
                    rsn_flags = int((await ap_props.call_get(NM_AP_IFACE, "RsnFlags")).value)

                    security = "Open"
                    if rsn_flags > 0:
                        security = "WPA3/WPA2"
                    elif wpa_flags > 0:
                        security = "WPA"
                    elif flags > 0:
                        security = "WEP"

                    # Keep strongest entry per SSID
                    if ssid not in results_by_ssid or strength > results_by_ssid[ssid]["signal_percent"]:
                        results_by_ssid[ssid] = {
                            "ssid": ssid,
                            "signal_percent": strength,
                            "frequency_mhz": frequency,
                            "band": "5GHz" if frequency > 4000 else "2.4GHz",
                            "security": security,
                        }
                except Exception:
                    continue

            sorted_aps = sorted(results_by_ssid.values(), key=lambda x: x["signal_percent"], reverse=True)
            return sorted_aps
        except Exception as err:
            log.warning("DBus scan_wifi failed (%s), falling back to nmcli", err)
            return self._cli_scan()

    def _cli_scan(self) -> List[Dict[str, Any]]:
        """Fallback WiFi scan via nmcli."""
        code, out, _ = _run_cli(["nmcli", "-t", "-f", "SSID,SIGNAL,FREQ,SECURITY", "dev", "wifi", "list", "--rescan", "yes"])
        if code != 0:
            return []
        results: Dict[str, Dict[str, Any]] = {}
        for line in out.splitlines():
            parts = line.split(":")
            if len(parts) >= 4 and parts[0]:
                ssid = parts[0]
                strength = int(parts[1]) if parts[1].isdigit() else 0
                freq_val = parts[2].replace(" MHz", "").strip()
                freq = int(freq_val) if freq_val.isdigit() else 0
                sec = parts[3] or "Open"
                if ssid not in results or strength > results[ssid]["signal_percent"]:
                    results[ssid] = {
                        "ssid": ssid,
                        "signal_percent": strength,
                        "frequency_mhz": freq,
                        "band": "5GHz" if freq > 4000 else "2.4GHz",
                        "security": sec,
                    }
        return sorted(results.values(), key=lambda x: x["signal_percent"], reverse=True)

    async def connect_wifi(self, ssid: str, password: Optional[str] = None) -> Dict[str, Any]:
        """Connect to specified WiFi network with verification."""
        if not ssid or not ssid.strip():
            return {"ok": False, "error": "SSID cannot be empty"}
        target_ssid = ssid.strip()

        # Connect via nmcli for reliable credential handoff and WPA-PSK provisioning
        cmd = ["nmcli", "dev", "wifi", "connect", target_ssid]
        if password:
            cmd.extend(["password", password])

        code, out, err = _run_cli(cmd, timeout=20.0)
        # Verify post-connect status
        await asyncio.sleep(1.0)
        status = await self.get_status()
        wifi_info = status.get("wifi") or {}
        connected_ssid = wifi_info.get("ssid", "")

        if connected_ssid.lower() == target_ssid.lower() and status.get("connected"):
            return {
                "ok": True,
                "message": f"Successfully connected to '{target_ssid}' ({wifi_info.get('signal_percent', 0)}% signal).",
                "ssid": target_ssid,
                "signal_percent": wifi_info.get("signal_percent", 0),
            }

        if code != 0:
            return {"ok": False, "error": err or out or f"Failed connecting to '{target_ssid}'"}
        return {"ok": False, "error": f"Connected to network, but active SSID shows '{connected_ssid}'"}

    async def disconnect_wifi(self) -> Dict[str, Any]:
        """Disconnect active WiFi interface."""
        status = await self.get_status()
        wifi = status.get("wifi")
        if not wifi or not wifi.get("connected"):
            return {"ok": True, "message": "WiFi is already disconnected."}

        iface = wifi.get("interface", "wlo1")
        code, out, err = _run_cli(["nmcli", "dev", "disconnect", iface], timeout=8.0)
        await asyncio.sleep(0.5)

        # Verify
        new_status = await self.get_status()
        new_wifi = new_status.get("wifi") or {}
        if not new_wifi.get("connected"):
            return {"ok": True, "message": f"Disconnected WiFi on interface {iface}."}
        return {"ok": False, "error": err or "WiFi failed to disconnect"}

    async def forget_wifi(self, ssid: str) -> Dict[str, Any]:
        """Remove saved WiFi connection profile."""
        if not ssid or not ssid.strip():
            return {"ok": False, "error": "SSID cannot be empty"}
        code, out, err = _run_cli(["nmcli", "connection", "delete", "id", ssid.strip()], timeout=5.0)
        if code == 0:
            return {"ok": True, "message": f"Removed saved connection for '{ssid.strip()}'."}
        return {"ok": False, "error": err or f"No saved connection found for '{ssid.strip()}'"}

    async def list_saved_wifi(self) -> List[Dict[str, Any]]:
        """List all saved WiFi connection profiles."""
        code, out, _ = _run_cli(["nmcli", "-t", "-f", "NAME,UUID,TYPE,TIMESTAMP", "connection", "show"])
        if code != 0:
            return []
        saved = []
        for line in out.splitlines():
            parts = line.split(":")
            if len(parts) >= 3 and parts[2] in ("802-11-wireless", "wifi"):
                saved.append({
                    "name": parts[0],
                    "uuid": parts[1],
                    "type": "wifi",
                    "timestamp": parts[3] if len(parts) > 3 else "",
                })
        return saved

    async def list_vpns(self) -> List[Dict[str, Any]]:
        """List configured VPN and WireGuard connections."""
        code, out, _ = _run_cli(["nmcli", "-t", "-f", "NAME,UUID,TYPE,DEVICE", "connection", "show"])
        if code != 0:
            return []
        vpns = []
        for line in out.splitlines():
            parts = line.split(":")
            if len(parts) >= 3 and parts[2] in ("vpn", "wireguard"):
                is_active = len(parts) >= 4 and bool(parts[3])
                vpns.append({
                    "name": parts[0],
                    "uuid": parts[1],
                    "type": parts[2],
                    "active": is_active,
                })
        return vpns

    async def connect_vpn(self, name: str) -> Dict[str, Any]:
        """Activate named VPN profile."""
        if not name or not name.strip():
            return {"ok": False, "error": "VPN name cannot be empty"}
        target = name.strip()
        code, out, err = _run_cli(["nmcli", "connection", "up", target], timeout=15.0)
        if code == 0:
            return {"ok": True, "message": f"VPN '{target}' activated successfully."}
        return {"ok": False, "error": err or out or f"Failed activating VPN '{target}'"}

    async def disconnect_vpn(self, name: str) -> Dict[str, Any]:
        """Deactivate named VPN profile."""
        if not name or not name.strip():
            return {"ok": False, "error": "VPN name cannot be empty"}
        target = name.strip()
        code, out, err = _run_cli(["nmcli", "connection", "down", target], timeout=10.0)
        if code == 0:
            return {"ok": True, "message": f"VPN '{target}' deactivated."}
        return {"ok": False, "error": err or out or f"Failed deactivating VPN '{target}'"}
