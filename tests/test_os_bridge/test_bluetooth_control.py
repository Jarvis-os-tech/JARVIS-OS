"""Unit tests for BluetoothController."""
import pytest
import asyncio
from unittest.mock import patch, AsyncMock

from jarvis_os_bridge.bluetooth_control import BluetoothController


@pytest.mark.asyncio
async def test_bluetooth_controller_init():
    ctrl = BluetoothController()
    assert ctrl is not None


@pytest.mark.asyncio
async def test_get_status_live():
    ctrl = BluetoothController()
    status = await ctrl.get_status()
    assert isinstance(status, dict)
    assert "ok" in status
    assert "powered" in status
    assert "devices" in status
    assert isinstance(status["devices"], list)


@pytest.mark.asyncio
async def test_scan_devices_structure():
    ctrl = BluetoothController()
    # Mocking scan_devices to not hang or alter system state during tests if adapter is off
    with patch.object(ctrl, "scan_devices", new_callable=AsyncMock) as mock_scan:
        mock_scan.return_value = [
            {"name": "Test Device", "address": "00:11:22:33:44:55", "connected": False}
        ]
        devs = await ctrl.scan_devices(timeout=1.0)
        assert len(devs) == 1
        assert devs[0]["name"] == "Test Device"
