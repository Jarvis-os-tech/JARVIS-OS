"""Constants, paths, and event taxonomy for JARVIS OS Deep Bridge."""
from __future__ import annotations

import os
from pathlib import Path

# Socket paths
RUNTIME_DIR = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
SPEAK_SOCKET_PATH = RUNTIME_DIR / "jarvis-voice-speak.sock"
CONTROL_SOCKET_PATH = RUNTIME_DIR / "jarvis" / "control.sock"
LEGACY_SOCKET_PATH = RUNTIME_DIR / "jarvis.sock"

# Event taxonomy
EVENT_NETWORK_STATE_CHANGED = "network.state_changed"
EVENT_NETWORK_CONNECTIVITY_CHANGED = "network.connectivity_changed"
EVENT_WIFI_ACCESS_POINT_CHANGED = "network.wifi_ap_changed"

EVENT_BLUETOOTH_ADAPTER_CHANGED = "bluetooth.adapter_changed"
EVENT_BLUETOOTH_DEVICE_ADDED = "bluetooth.device_added"
EVENT_BLUETOOTH_DEVICE_REMOVED = "bluetooth.device_removed"
EVENT_BLUETOOTH_DEVICE_CHANGED = "bluetooth.device_changed"

EVENT_POWER_BATTERY_CHANGED = "power.battery_changed"
EVENT_POWER_LID_CHANGED = "power.lid_changed"
EVENT_POWER_LOW_BATTERY = "power.low_battery"

EVENT_SESSION_LOCKED = "session.locked"
EVENT_SESSION_UNLOCKED = "session.unlocked"
EVENT_SESSION_SLEEP_PREPARE = "session.sleep_prepare"

EVENT_DEVICE_USB_ADDED = "device.usb_added"
EVENT_DEVICE_USB_REMOVED = "device.usb_removed"
EVENT_DEVICE_DISPLAY_CHANGED = "device.display_changed"

EVENT_JOURNAL_OOM_KILL = "journal.oom_kill"
EVENT_JOURNAL_SEGFAULT = "journal.segfault"
EVENT_JOURNAL_DISK_ERROR = "journal.disk_error"
EVENT_JOURNAL_SERVICE_FAILED = "journal.service_failed"

EVENT_FS_DOWNLOAD_COMPLETED = "fs.download_completed"
EVENT_FS_CONFIG_CHANGED = "fs.config_changed"
EVENT_FS_THEME_CHANGED = "fs.theme_changed"
