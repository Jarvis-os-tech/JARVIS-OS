"""Reactive DBus Signal Listener for JARVIS OS.

Subscribes to system and session DBus signals for NetworkManager, BlueZ,
UPower, and logind without periodic polling loops (Zero-Polling Invariant).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

from dbus_fast import BusType, MessageType
from dbus_fast.aio import MessageBus
from dbus_fast.message import Message

from .constants import (
    EVENT_BLUETOOTH_ADAPTER_CHANGED,
    EVENT_BLUETOOTH_DEVICE_ADDED,
    EVENT_BLUETOOTH_DEVICE_CHANGED,
    EVENT_BLUETOOTH_DEVICE_REMOVED,
    EVENT_NETWORK_CONNECTIVITY_CHANGED,
    EVENT_NETWORK_STATE_CHANGED,
    EVENT_POWER_BATTERY_CHANGED,
    EVENT_POWER_LID_CHANGED,
    EVENT_POWER_LOW_BATTERY,
    EVENT_SESSION_LOCKED,
    EVENT_SESSION_SLEEP_PREPARE,
    EVENT_SESSION_UNLOCKED,
)

log = logging.getLogger("jarvis.bridge.dbus")

EventCallback = Callable[[str, Dict[str, Any]], None]


class DBusEventListener:
    """Listens for hardware and OS lifecycle events over DBus and emits structured events."""

    def __init__(self, on_event: Optional[EventCallback] = None):
        self.on_event = on_event
        self._system_bus: Optional[MessageBus] = None
        self._session_bus: Optional[MessageBus] = None
        self._running = False
        self._last_battery_alert = 0.0

    async def start(self) -> None:
        """Connect to system and session buses and register signal match rules."""
        self._running = True
        try:
            self._system_bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
            self._system_bus.add_message_handler(self._handle_system_message)
            await self._register_system_matches()
            log.info("DBus system bus event listener connected")
        except Exception as err:
            log.warning("Could not connect to system bus: %s", err)

        try:
            self._session_bus = await MessageBus(bus_type=BusType.SESSION).connect()
            self._session_bus.add_message_handler(self._handle_session_message)
            await self._register_session_matches()
            log.info("DBus session bus event listener connected")
        except Exception as err:
            log.warning("Could not connect to session bus: %s", err)

    async def close(self) -> None:
        """Disconnect message buses."""
        self._running = False
        if self._system_bus:
            self._system_bus.disconnect()
            self._system_bus = None
        if self._session_bus:
            self._session_bus.disconnect()
            self._session_bus = None

    async def _add_match(self, bus: MessageBus, rule: str) -> None:
        try:
            await bus.call(
                Message(
                    destination="org.freedesktop.DBus",
                    path="/org/freedesktop/DBus",
                    interface="org.freedesktop.DBus",
                    member="AddMatch",
                    signature="s",
                    body=[rule],
                )
            )
        except Exception as err:
            log.debug("AddMatch failed for rule '%s': %s", rule, err)

    async def _register_system_matches(self) -> None:
        if not self._system_bus:
            return
        rules = [
            # NetworkManager
            "type='signal',sender='org.freedesktop.NetworkManager',interface='org.freedesktop.NetworkManager'",
            # BlueZ ObjectManager & Properties
            "type='signal',sender='org.bluez',interface='org.freedesktop.DBus.ObjectManager'",
            "type='signal',sender='org.bluez',interface='org.freedesktop.DBus.Properties'",
            # UPower
            "type='signal',sender='org.freedesktop.UPower',interface='org.freedesktop.DBus.Properties'",
            # logind
            "type='signal',sender='org.freedesktop.login1',interface='org.freedesktop.login1.Manager'",
        ]
        for rule in rules:
            await self._add_match(self._system_bus, rule)

    async def _register_session_matches(self) -> None:
        if not self._session_bus:
            return
        rules = [
            "type='signal',interface='org.freedesktop.Notifications',member='NotificationClosed'",
            "type='signal',interface='org.freedesktop.ScreenSaver'",
        ]
        for rule in rules:
            await self._add_match(self._session_bus, rule)

    def _emit(self, event_name: str, payload: Dict[str, Any]) -> None:
        if self.on_event and callable(self.on_event):
            try:
                self.on_event(event_name, payload)
            except Exception as err:
                log.error("Error in DBus event callback for %s: %s", event_name, err)

    def _handle_system_message(self, msg: Message) -> None:
        if msg.message_type != MessageType.SIGNAL:
            return

        iface = msg.interface
        member = msg.member
        body = msg.body or []

        # 1. NetworkManager State & Connectivity
        if iface == "org.freedesktop.NetworkManager":
            if member == "StateChanged" and body:
                raw_state = body[0]
                self._emit(EVENT_NETWORK_STATE_CHANGED, {
                    "raw_state": raw_state,
                    "connected": raw_state in (50, 60, 70),
                })
            elif member == "ConnectivityChanged" and body:
                raw_conn = body[0]
                self._emit(EVENT_NETWORK_CONNECTIVITY_CHANGED, {
                    "raw_connectivity": raw_conn,
                    "has_internet": raw_conn == 4,
                })

        # 2. BlueZ Events
        elif msg.sender and "bluez" in (msg.sender or ""):
            if iface == "org.freedesktop.DBus.ObjectManager":
                if member == "InterfacesAdded" and len(body) >= 2:
                    path = str(body[0])
                    ifaces = body[1]
                    if "org.bluez.Device1" in ifaces:
                        props = ifaces["org.bluez.Device1"]
                        name = props.get("Name", props.get("Alias", "Unknown"))
                        addr = props.get("Address", "")
                        self._emit(EVENT_BLUETOOTH_DEVICE_ADDED, {
                            "path": path,
                            "name": str(name.value if hasattr(name, "value") else name),
                            "address": str(addr.value if hasattr(addr, "value") else addr),
                        })
                elif member == "InterfacesRemoved" and len(body) >= 2:
                    path = str(body[0])
                    ifaces = body[1]
                    if any("Device" in i for i in ifaces):
                        self._emit(EVENT_BLUETOOTH_DEVICE_REMOVED, {"path": path})

            elif iface == "org.freedesktop.DBus.Properties" and member == "PropertiesChanged":
                if len(body) >= 2:
                    target_iface = body[0]
                    changed_props = body[1]
                    if target_iface == "org.bluez.Device1":
                        payload: Dict[str, Any] = {"path": msg.path}
                        for k, v in changed_props.items():
                            val = v.value if hasattr(v, "value") else v
                            payload[k.lower()] = val
                        self._emit(EVENT_BLUETOOTH_DEVICE_CHANGED, payload)
                    elif target_iface == "org.bluez.Adapter1":
                        payload = {"path": msg.path}
                        for k, v in changed_props.items():
                            val = v.value if hasattr(v, "value") else v
                            payload[k.lower()] = val
                        self._emit(EVENT_BLUETOOTH_ADAPTER_CHANGED, payload)

        # 3. UPower Battery and Lid
        elif msg.path and "UPower" in msg.path:
            if iface == "org.freedesktop.DBus.Properties" and member == "PropertiesChanged" and len(body) >= 2:
                changed = body[1]
                if "Percentage" in changed or "State" in changed:
                    pct = changed.get("Percentage")
                    pct_val = pct.value if hasattr(pct, "value") else pct
                    state = changed.get("State")
                    state_val = state.value if hasattr(state, "value") else state
                    payload = {"percentage": pct_val, "state": state_val}
                    self._emit(EVENT_POWER_BATTERY_CHANGED, payload)

                    # Low battery trigger
                    if pct_val is not None and pct_val <= 15 and state_val == 2:  # 2 = discharging
                        loop = asyncio.get_event_loop()
                        now = loop.time()
                        if now - self._last_battery_alert > 300:  # 5 min cooldown
                            self._last_battery_alert = now
                            self._emit(EVENT_POWER_LOW_BATTERY, {"percentage": pct_val})

                if "LidIsClosed" in changed:
                    lid = changed.get("LidIsClosed")
                    self._emit(EVENT_POWER_LID_CHANGED, {"closed": bool(lid.value if hasattr(lid, "value") else lid)})

        # 4. logind Sleep / Session
        elif iface == "org.freedesktop.login1.Manager":
            if member == "PrepareForSleep" and body:
                going_to_sleep = bool(body[0])
                self._emit(EVENT_SESSION_SLEEP_PREPARE, {"sleep": going_to_sleep})

    def _handle_session_message(self, msg: Message) -> None:
        if msg.message_type != MessageType.SIGNAL:
            return
        if msg.interface == "org.freedesktop.ScreenSaver":
            if msg.member == "ActiveChanged" and msg.body:
                active = bool(msg.body[0])
                event = EVENT_SESSION_LOCKED if active else EVENT_SESSION_UNLOCKED
                self._emit(event, {"locked": active})
