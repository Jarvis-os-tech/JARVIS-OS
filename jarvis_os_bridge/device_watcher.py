"""Zero-Polling udev Hardware Device Watcher for JARVIS OS.

Monitors removable USB media and display hotplug events directly via netlink
file descriptors registered on the asyncio event loop (Zero Polling Invariant).
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
from typing import Any, Callable, Dict, List, Optional

import pyudev

from .constants import (
    EVENT_DEVICE_DISPLAY_CHANGED,
    EVENT_DEVICE_USB_ADDED,
    EVENT_DEVICE_USB_REMOVED,
)

log = logging.getLogger("jarvis.bridge.device_watcher")

EventCallback = Callable[[str, Dict[str, Any]], None]


class DeviceWatcher:
    """Async udev device event monitor for removable drives and displays."""

    def __init__(self, on_event: Optional[EventCallback] = None):
        self.on_event = on_event
        self._context = pyudev.Context()
        self._monitor: Optional[pyudev.Monitor] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._fd: Optional[int] = None

    def start(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        """Register netlink socket on the asyncio event loop."""
        self._loop = loop or asyncio.get_running_loop()
        self._monitor = pyudev.Monitor.from_netlink(self._context)
        self._monitor.filter_by(subsystem="block")
        self._monitor.filter_by(subsystem="drm")
        self._monitor.start()
        self._fd = self._monitor.fileno()

        self._loop.add_reader(self._fd, self._on_device_event)
        log.info("DeviceWatcher attached to asyncio loop on netlink fd %d", self._fd)

    def close(self) -> None:
        """Detach netlink socket reader from event loop."""
        if self._loop and self._fd is not None:
            try:
                self._loop.remove_reader(self._fd)
            except Exception:
                pass
            self._fd = None
            self._monitor = None
            log.info("DeviceWatcher detached")

    def _emit(self, event_name: str, payload: Dict[str, Any]) -> None:
        if self.on_event and callable(self.on_event):
            try:
                self.on_event(event_name, payload)
            except Exception as err:
                log.error("Error in DeviceWatcher callback for %s: %s", event_name, err)

    def _on_device_event(self) -> None:
        """Non-blocking event handler called when netlink socket has data."""
        if not self._monitor:
            return
        try:
            device = self._monitor.poll(timeout=0)
            if not device:
                return

            action = device.action
            subsystem = device.subsystem

            if subsystem == "block":
                devtype = device.get("DEVTYPE")
                id_bus = device.get("ID_BUS")

                # Filter for USB drives or removable partitions
                if id_bus == "usb" or devtype in ("disk", "partition"):
                    node = device.device_node or ""
                    label = device.get("ID_FS_LABEL") or "Removable Drive"
                    fs_type = device.get("ID_FS_TYPE") or "unknown"
                    model = device.get("ID_MODEL") or "USB Device"

                    if action == "add":
                        self._emit(EVENT_DEVICE_USB_ADDED, {
                            "action": "add",
                            "node": node,
                            "label": label,
                            "fs_type": fs_type,
                            "model": model,
                            "is_usb": id_bus == "usb",
                        })
                    elif action == "remove":
                        self._emit(EVENT_DEVICE_USB_REMOVED, {
                            "action": "remove",
                            "node": node,
                            "label": label,
                            "is_usb": id_bus == "usb",
                        })

            elif subsystem == "drm":
                # Display hotplug event
                status = device.get("HOTPLUG") or device.action
                self._emit(EVENT_DEVICE_DISPLAY_CHANGED, {
                    "action": action,
                    "device": device.device_node or "drm",
                    "status": status,
                })
        except Exception as err:
            log.warning("Error processing udev device event: %s", err)

    def list_usb_devices(self) -> List[Dict[str, Any]]:
        """Return list of currently connected USB/removable block devices."""
        usb_devices = []
        for dev in self._context.list_devices(subsystem="block"):
            if dev.get("ID_BUS") == "usb" and dev.get("DEVTYPE") in ("disk", "partition"):
                node = dev.device_node or ""
                label = dev.get("ID_FS_LABEL") or ""
                fs_type = dev.get("ID_FS_TYPE") or ""
                model = dev.get("ID_MODEL") or "USB Storage"

                # Check if mounted via findmnt
                mount_point = None
                try:
                    res = subprocess.run(
                        ["findmnt", "-n", "-o", "TARGET", node],
                        capture_output=True,
                        text=True,
                        timeout=2.0,
                    )
                    if res.returncode == 0 and res.stdout.strip():
                        mount_point = res.stdout.strip().splitlines()[0]
                except Exception:
                    pass

                usb_devices.append({
                    "node": node,
                    "label": label or model,
                    "model": model,
                    "fs_type": fs_type,
                    "mounted": mount_point is not None,
                    "mount_point": mount_point,
                })
        return usb_devices
