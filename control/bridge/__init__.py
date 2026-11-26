"""JARVIS OS Deep Integration Bridge.

Zero-polling DBus, udev, journald, and inotify reactive operating system interface.
"""
from __future__ import annotations

__version__ = "0.1.0"

from .bluetooth_control import BluetoothController
from .constants import *
from .dbus_listener import DBusEventListener
from .device_watcher import DeviceWatcher
from .fs_watcher import FsWatcher
from .journal_streamer import JournalStreamer
from .network_control import NetworkController
from .service import BridgeService, run_daemon

__all__ = [
    "BridgeService",
    "run_daemon",
    "NetworkController",
    "BluetoothController",
    "DBusEventListener",
    "DeviceWatcher",
    "JournalStreamer",
    "FsWatcher",
]
