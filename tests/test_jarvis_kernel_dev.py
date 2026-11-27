"""Checks for the linux-jarvisos kernel driver interface (kernel/jarvis_dev.py)."""
import ctypes
from pathlib import Path
from unittest.mock import patch

from kernel import jarvis_dev


def test_uapi_struct_sizes_and_ioctls():
    assert ctypes.sizeof(jarvis_dev.JarvisStatus) == 144
    assert ctypes.sizeof(jarvis_dev.JarvisSysmon) == 120
    assert ctypes.sizeof(jarvis_dev.JarvisPolicyCheck) == 520
    assert jarvis_dev.IOC_STATUS == 0x80904A01
    assert jarvis_dev.IOC_SET_STATE == 0x40044A02
    assert jarvis_dev.IOC_SET_MODEL == 0x40404A03
    assert jarvis_dev.IOC_SET_PROVIDER == 0x40044A08
    assert jarvis_dev.IOC_SYSMON == 0x80784A0A
    assert jarvis_dev.IOC_POLICY_CHECK == 0xC2084A16


def test_sysfs_snapshot_parses_sysfs_tree(tmp_path):
    sysmon = tmp_path / "sysmon"
    sysmon.mkdir()
    (tmp_path / "state").write_text("idle\n")
    (tmp_path / "model").write_text("gemini-live\n")
    (tmp_path / "pending").write_text("2\n")
    (sysmon / "cpu_count").write_text("12\n")
    (sysmon / "cpu_load").write_text("325\n")
    (sysmon / "mem_avail").write_text("4096\n")
    (sysmon / "mem_total").write_text("7611\n")
    (sysmon / "thermal").write_text("55 61\n")
    (sysmon / "thermal_crit").write_text("100\n")

    snap = jarvis_dev.sysfs_snapshot(tmp_path)
    assert snap == {
        "state": "idle",
        "model": "gemini-live",
        "pending": 2,
        "cpu_count": 12,
        "cpu_load_1min": 325,
        "mem_avail_mb": 4096,
        "mem_total_mb": 7611,
        "thermal_celsius": [55, 61],
        "thermal_crit_c": 100,
    }


def test_missing_or_unprivileged_device_fails_gracefully(tmp_path):
    missing = tmp_path / "no_jarvis"
    assert jarvis_dev.sysfs_snapshot(missing) is None
    assert jarvis_dev.ioctl_status(missing) is None
    assert jarvis_dev.ioctl_sysmon(missing) is None
    assert jarvis_dev.set_daemon_state(jarvis_dev.JARVIS_STATE_IDLE, dev_path=missing) is False
    assert jarvis_dev.policy_check("FileSystemMCP", "read_file", dev_path=missing) is None

    fake_dev = tmp_path / "jarvis"
    fake_dev.touch()
    with patch("os.open", side_effect=PermissionError("denied")):
        access = jarvis_dev.device_access_status(fake_dev, tmp_path)
        assert access["device_exists"] is True
        assert access["accessible"] is False
        assert access["error"] == "permission_denied"
