"""Unit tests for system_control_extension validation and execution dispatch."""
import pytest
from jarvis_control.system_control_extension import validate, EXTENSION_ACTIONS, execute


def test_validate_actions():
    assert validate("invalid_action") is not None
    assert validate("network_status") is None
    assert validate("bt_status") is None
    assert validate("wifi_scan") is None


def test_validate_required_targets():
    assert validate("wifi_connect") == "target is required for wifi_connect"
    assert validate("wifi_connect", target="MySSID") is None
    assert validate("bt_connect") == "target is required for bt_connect"
    assert validate("process_kill") == "target is required for process_kill"


def test_extension_actions_list():
    assert "network_status" in EXTENSION_ACTIONS
    assert "wifi_scan" in EXTENSION_ACTIONS
    assert "bt_status" in EXTENSION_ACTIONS
    assert "screenshot_full" in EXTENSION_ACTIONS
    assert "process_list" in EXTENSION_ACTIONS
