"""Minimal stdlib interface to the linux-jarvisos kernel driver (/dev/jarvis + sysfs)."""
from __future__ import annotations

import ctypes
import fcntl
import os
from pathlib import Path
import struct
from typing import Any, Optional

DEV_PATH = Path("/dev/jarvis")
SYSFS_PATH = Path("/sys/class/misc/jarvis")

JARVIS_STATE_OFFLINE = 0
JARVIS_STATE_IDLE = 1
JARVIS_STATE_PROCESSING = 2
JARVIS_STATE_ERROR = 3

JARVIS_PROVIDER_NONE = 0
JARVIS_PROVIDER_OLLAMA = 1
JARVIS_PROVIDER_CLAUDE = 2
JARVIS_PROVIDER_OPENAI = 3
JARVIS_PROVIDER_OPENAI_COMPAT = 4

# Linux x86_64 _IOC(dir, type, nr, size) encoding matching include/uapi/linux/jarvis.h
_IOC_NONE, _IOC_WRITE, _IOC_READ = 0, 1, 2


def _ioc(direction: int, nr: int, size: int) -> int:
    return (direction << 30) | (size << 16) | (ord("J") << 8) | nr


class JarvisStatus(ctypes.Structure):
    _fields_ = [
        ("state", ctypes.c_uint32),
        ("provider", ctypes.c_uint32),
        ("pending_queries", ctypes.c_uint32),
        ("model_loaded", ctypes.c_uint32),
        ("model_name", ctypes.c_ubyte * 64),
        ("provider_name", ctypes.c_ubyte * 64),
    ]


class JarvisSysmon(ctypes.Structure):
    _fields_ = [
        ("cpu_load_1min", ctypes.c_uint32),
        ("cpu_count", ctypes.c_uint32),
        ("mem_total_mb", ctypes.c_uint64),
        ("mem_free_mb", ctypes.c_uint64),
        ("mem_avail_mb", ctypes.c_uint64),
        ("thermal_count", ctypes.c_uint32),
        ("thermal_celsius", ctypes.c_int32 * 16),
        ("thermal_crit_c", ctypes.c_int32),
        ("swap_total_mb", ctypes.c_uint64),
        ("swap_free_mb", ctypes.c_uint64),
    ]


class JarvisPolicyCheck(ctypes.Structure):
    _fields_ = [
        ("server", ctypes.c_ubyte * 128),
        ("tool", ctypes.c_ubyte * 128),
        ("path", ctypes.c_ubyte * 256),
        ("tier", ctypes.c_uint32),
        ("allowed", ctypes.c_uint32),
    ]


IOC_STATUS = _ioc(_IOC_READ, 1, ctypes.sizeof(JarvisStatus))
IOC_SET_STATE = _ioc(_IOC_WRITE, 2, 4)
IOC_SET_MODEL = _ioc(_IOC_WRITE, 3, 64)
IOC_SET_PROVIDER = _ioc(_IOC_WRITE, 8, 4)
IOC_SYSMON = _ioc(_IOC_READ, 10, ctypes.sizeof(JarvisSysmon))
IOC_POLICY_CHECK = _ioc(_IOC_READ | _IOC_WRITE, 22, ctypes.sizeof(JarvisPolicyCheck))


def _read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _cstr(buf: ctypes.Array[ctypes.c_ubyte]) -> str:
    return bytes(buf).split(b"\x00", 1)[0].decode("utf-8", errors="replace")


def _fill_bytes(buf: ctypes.Array[ctypes.c_ubyte], text: str) -> None:
    encoded = text.encode("utf-8")[: len(buf) - 1]
    ctypes.memset(buf, 0, len(buf))
    for i, b in enumerate(encoded):
        buf[i] = b


def sysfs_snapshot(sysfs_root: Path = SYSFS_PATH) -> Optional[dict[str, Any]]:
    """Read live kernel state and sysmon telemetry from /sys/class/misc/jarvis."""
    if not sysfs_root.exists():
        return None
    sysmon = sysfs_root / "sysmon"
    thermals_raw = _read_text(sysmon / "thermal") or ""
    thermals = [int(x) for x in thermals_raw.split() if x.lstrip("-").isdigit()]

    def _int(name: str) -> Optional[int]:
        val = _read_text(sysmon / name)
        return int(val) if val is not None and val.lstrip("-").isdigit() else None

    return {
        "state": _read_text(sysfs_root / "state"),
        "model": _read_text(sysfs_root / "model"),
        "pending": int(_read_text(sysfs_root / "pending") or 0),
        "cpu_count": _int("cpu_count"),
        "cpu_load_1min": _int("cpu_load"),
        "mem_avail_mb": _int("mem_avail"),
        "mem_total_mb": _int("mem_total"),
        "thermal_celsius": thermals,
        "thermal_crit_c": _int("thermal_crit"),
    }


def device_access_status(dev_path: Path = DEV_PATH, sysfs_root: Path = SYSFS_PATH) -> dict[str, Any]:
    """Report kernel driver presence and whether the current user can open /dev/jarvis."""
    loaded = sysfs_root.exists() or dev_path.exists()
    if not dev_path.exists():
        return {"loaded": loaded, "device_exists": False, "accessible": False, "error": "missing"}
    try:
        fd = os.open(str(dev_path), os.O_RDWR)
        os.close(fd)
        return {"loaded": True, "device_exists": True, "accessible": True, "error": None}
    except PermissionError:
        return {"loaded": True, "device_exists": True, "accessible": False, "error": "permission_denied"}
    except OSError as exc:
        return {"loaded": loaded, "device_exists": True, "accessible": False, "error": exc.strerror or str(exc)}


def _open_rw(dev_path: Path) -> Optional[int]:
    try:
        return os.open(str(dev_path), os.O_RDWR)
    except OSError:
        return None


def ioctl_status(dev_path: Path = DEV_PATH) -> Optional[dict[str, Any]]:
    fd = _open_rw(dev_path)
    if fd is None:
        return None
    try:
        st = JarvisStatus()
        fcntl.ioctl(fd, IOC_STATUS, st, True)
        return {
            "state": st.state,
            "provider": st.provider,
            "pending_queries": st.pending_queries,
            "model_loaded": bool(st.model_loaded),
            "model_name": _cstr(st.model_name),
            "provider_name": _cstr(st.provider_name),
        }
    except OSError:
        return None
    finally:
        os.close(fd)


def ioctl_sysmon(dev_path: Path = DEV_PATH) -> Optional[dict[str, Any]]:
    fd = _open_rw(dev_path)
    if fd is None:
        return None
    try:
        sm = JarvisSysmon()
        fcntl.ioctl(fd, IOC_SYSMON, sm, True)
        return {
            "cpu_load_1min": sm.cpu_load_1min,
            "cpu_count": sm.cpu_count,
            "mem_total_mb": sm.mem_total_mb,
            "mem_free_mb": sm.mem_free_mb,
            "mem_avail_mb": sm.mem_avail_mb,
            "thermal_celsius": [sm.thermal_celsius[i] for i in range(min(sm.thermal_count, 16))],
            "thermal_crit_c": sm.thermal_crit_c,
            "swap_total_mb": sm.swap_total_mb,
            "swap_free_mb": sm.swap_free_mb,
        }
    except OSError:
        return None
    finally:
        os.close(fd)


def set_daemon_state(
    state: int,
    *,
    provider: Optional[int] = None,
    model: Optional[str] = None,
    dev_path: Path = DEV_PATH,
) -> bool:
    """Publish daemon state/provider/model to /dev/jarvis when accessible."""
    fd = _open_rw(dev_path)
    if fd is None:
        return False
    try:
        fcntl.ioctl(fd, IOC_SET_STATE, struct.pack("I", state))
        if provider is not None:
            fcntl.ioctl(fd, IOC_SET_PROVIDER, struct.pack("I", provider))
        if model is not None:
            buf = (ctypes.c_char * 64)()
            encoded = model.encode("utf-8")[:63]
            buf[: len(encoded)] = encoded
            fcntl.ioctl(fd, IOC_SET_MODEL, buf)
        return True
    except OSError:
        return False
    finally:
        os.close(fd)


def policy_check(server: str, tool: str, path: str = "", dev_path: Path = DEV_PATH) -> Optional[tuple[int, bool]]:
    """Query the kernel jarvis_policy engine; returns (tier, allowed) or None."""
    fd = _open_rw(dev_path)
    if fd is None:
        return None
    try:
        req = JarvisPolicyCheck()
        _fill_bytes(req.server, server)
        _fill_bytes(req.tool, tool)
        if path:
            _fill_bytes(req.path, path)
        fcntl.ioctl(fd, IOC_POLICY_CHECK, req, True)
        return req.tier, bool(req.allowed)
    except OSError:
        return None
    finally:
        os.close(fd)


if __name__ == "__main__":
    assert ctypes.sizeof(JarvisStatus) == 144
    assert ctypes.sizeof(JarvisSysmon) == 120
    assert ctypes.sizeof(JarvisPolicyCheck) == 520
    assert IOC_STATUS == 0x80904A01
    assert IOC_SET_STATE == 0x40044A02
    assert IOC_SET_MODEL == 0x40404A03
    assert IOC_SET_PROVIDER == 0x40044A08
    assert IOC_SYSMON == 0x80784A0A
    assert IOC_POLICY_CHECK == 0xC2084A16
    print("sysfs:", sysfs_snapshot())
    print("access:", device_access_status())
