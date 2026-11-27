"""JARVIS OS Deep Integration Bridge Daemon Service.

Orchestrates DBusEventListener, DeviceWatcher, JournalStreamer, and FsWatcher.
Dispatches critical spoken alerts to jarvis-voice-speak.sock and broadcasts
structured UI events to jarvis/control.sock.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import socket
import time
from typing import Any, Dict, Optional

from .constants import (
    CONTROL_SOCKET_PATH,
    EVENT_DEVICE_DISPLAY_CHANGED,
    EVENT_DEVICE_USB_ADDED,
    EVENT_DEVICE_USB_REMOVED,
    EVENT_FS_CONFIG_CHANGED,
    EVENT_FS_DOWNLOAD_COMPLETED,
    EVENT_FS_THEME_CHANGED,
    EVENT_JOURNAL_DISK_ERROR,
    EVENT_JOURNAL_OOM_KILL,
    EVENT_JOURNAL_SEGFAULT,
    EVENT_JOURNAL_SERVICE_FAILED,
    EVENT_NETWORK_STATE_CHANGED,
    EVENT_POWER_BATTERY_CHANGED,
    EVENT_POWER_LOW_BATTERY,
    EVENT_SESSION_LOCKED,
    EVENT_SESSION_SLEEP_PREPARE,
    EVENT_SESSION_UNLOCKED,
    SPEAK_SOCKET_PATH,
)
from .dbus_listener import DBusEventListener
from .device_watcher import DeviceWatcher
from .fs_watcher import FsWatcher
from .journal_streamer import JournalStreamer
from kernel import jarvis_dev

log = logging.getLogger("jarvis.bridge.service")


def speak_alert(text: str, priority: str = "normal", dedup_key: Optional[str] = None) -> None:
    """Non-blocking dispatch to JARVIS voice speak socket."""
    if not text or not SPEAK_SOCKET_PATH.exists():
        return
    payload = json.dumps({
        "command": "speak",
        "text": text.strip(),
        "priority": priority,
        "source": "os_bridge",
        "dedup_key": dedup_key or f"bridge_{abs(hash(text)) % 100000}",
        "speak": True,
        "silent": False,
    }) + "\n"

    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            s.connect(str(SPEAK_SOCKET_PATH))
            s.sendall(payload.encode("utf-8"))
            try:
                _ = s.recv(1024)
            except socket.timeout:
                pass
    except Exception as err:
        log.debug("Speech socket delivery failed: %s", err)


class BridgeService:
    """Core daemon managing all deep OS integration event sources."""

    def __init__(self):
        self.dbus_listener = DBusEventListener(on_event=self._on_bridge_event)
        self.device_watcher = DeviceWatcher(on_event=self._on_bridge_event)
        self.journal_streamer = JournalStreamer(on_event=self._on_bridge_event)
        self.fs_watcher = FsWatcher(on_event=self._on_bridge_event)
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def start(self) -> None:
        """Start all bridge subsystems."""
        self._running = True
        self._loop = asyncio.get_running_loop()
        log.info("Starting JARVIS OS Deep Integration Bridge...")

        # 1. DBus signals
        await self.dbus_listener.start()

        # 2. Hardware udev netlink watcher
        self.device_watcher.start(loop=self._loop)

        # 3. systemd journal anomaly streamer
        await self.journal_streamer.start()

        # 4. inotify filesystem watcher
        self.fs_watcher.start(loop=self._loop)

        # 5. linux-jarvisos kernel driver status registration (best-effort)
        access = jarvis_dev.device_access_status()
        if access["accessible"]:
            jarvis_dev.set_daemon_state(jarvis_dev.JARVIS_STATE_IDLE)
            log.info("Registered daemon IDLE state with /dev/jarvis kernel driver")
        elif access["device_exists"]:
            log.warning("/dev/jarvis present but not accessible (%s); run: sudo usermod -aG jarvis $USER", access["error"])

        log.info("All JARVIS OS Bridge subsystems operational")

    async def stop(self) -> None:
        """Stop all bridge subsystems cleanly."""
        self._running = False
        log.info("Stopping JARVIS OS Bridge...")

        jarvis_dev.set_daemon_state(jarvis_dev.JARVIS_STATE_OFFLINE)
        self.fs_watcher.close()
        self.device_watcher.close()
        await self.journal_streamer.close()
        await self.dbus_listener.close()

        log.info("JARVIS OS Bridge stopped cleanly")

    def _on_bridge_event(self, event_name: str, payload: Dict[str, Any]) -> None:
        """Handle incoming hardware/OS events and trigger voice alerts and IPC broadcasts."""
        log.info("Bridge event: %s -> %s", event_name, payload)

        # 1. Hardware Removable Media
        if event_name == EVENT_DEVICE_USB_ADDED:
            label = payload.get("label") or payload.get("model") or "USB Storage"
            speak_alert(f"Removable drive connected: {label}.", priority="normal", dedup_key=f"usb_add_{label}")

        elif event_name == EVENT_DEVICE_USB_REMOVED:
            label = payload.get("label") or "drive"
            speak_alert(f"Removable {label} was disconnected.", priority="normal", dedup_key=f"usb_rm_{label}")

        # 2. Display Hotplug
        elif event_name == EVENT_DEVICE_DISPLAY_CHANGED:
            status = payload.get("status", "changed")
            log.info("Display hotplug event: %s", status)

        # 3. Battery Alerts
        elif event_name == EVENT_POWER_LOW_BATTERY:
            pct = payload.get("percentage", 15)
            speak_alert(f"Warning. System battery is down to {int(pct)} percent.", priority="critical", dedup_key="low_battery")

        # 4. Journal Anomalies (OOM, Crash, Disk)
        elif event_name == EVENT_JOURNAL_OOM_KILL:
            proc = payload.get("process", "A process")
            speak_alert(f"{proc} was terminated by the Linux kernel out of memory killer.", priority="critical", dedup_key=f"oom_{proc}")

        elif event_name == EVENT_JOURNAL_SEGFAULT:
            proc = payload.get("process", "A process")
            speak_alert(f"Application error: {proc} crashed with a segmentation fault.", priority="critical", dedup_key=f"segfault_{proc}")

        elif event_name == EVENT_JOURNAL_DISK_ERROR:
            comp = payload.get("component", "storage")
            speak_alert(f"Storage alert: Disk input-output error detected on {comp}.", priority="critical", dedup_key=f"disk_{comp}")

        # 5. Filesystem Activity
        elif event_name == EVENT_FS_DOWNLOAD_COMPLETED:
            fn = payload.get("filename", "")
            if fn:
                speak_alert(f"Download complete: {fn}.", priority="normal", dedup_key=f"dl_{fn}")

        elif event_name == EVENT_FS_CONFIG_CHANGED:
            log.info("Configuration modified: %s (%s)", payload.get("component"), payload.get("file"))

        elif event_name == EVENT_FS_THEME_CHANGED:
            log.info("Theme file updated: %s", payload.get("file"))

        # Broadcast to control IPC
        self._broadcast_to_ipc(event_name, payload)

    def _broadcast_to_ipc(self, event_name: str, payload: Dict[str, Any]) -> None:
        """Broadcast event to JARVIS control socket if accessible."""
        if not CONTROL_SOCKET_PATH.exists():
            return
        msg = json.dumps({"command": "broadcast", "event": event_name, **payload}) + "\n"
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(0.2)
                s.connect(str(CONTROL_SOCKET_PATH))
                s.sendall(msg.encode("utf-8"))
        except Exception:
            pass


async def run_daemon() -> None:
    """Run bridge service until SIGINT/SIGTERM."""
    service = BridgeService()
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    await service.start()
    try:
        await stop_event.wait()
    finally:
        await service.stop()
