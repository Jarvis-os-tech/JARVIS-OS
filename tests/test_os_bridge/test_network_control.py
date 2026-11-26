"""Unit tests for NetworkController and network management."""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from control.bridge.network_control import NetworkController


@pytest.mark.asyncio
async def test_network_controller_init():
    ctrl = NetworkController()
    assert ctrl is not None


@pytest.mark.asyncio
async def test_get_status_live():
    ctrl = NetworkController()
    status = await ctrl.get_status()
    assert isinstance(status, dict)
    assert "ok" in status
    assert "state" in status
    assert "connectivity" in status
    assert "ip_addresses" in status
    assert "wifi" in status


@pytest.mark.asyncio
async def test_scan_wifi():
    ctrl = NetworkController()
    results = await ctrl.scan_wifi(rescan=False)
    assert isinstance(results, list)
    if results:
        ap = results[0]
        assert "ssid" in ap
        assert "signal_percent" in ap


@pytest.mark.asyncio
async def test_list_saved_wifi():
    ctrl = NetworkController()
    saved = await ctrl.list_saved_wifi()
    assert isinstance(saved, list)


@pytest.mark.asyncio
async def test_list_vpns():
    ctrl = NetworkController()
    vpns = await ctrl.list_vpns()
    assert isinstance(vpns, list)
