from io import BytesIO
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from widget_engine import protocol, test_emit


@pytest.mark.parametrize("event", [
    {"action": "spawn_widget", "id": "task-1", "payload": {"data": {"text": "Ω\nReady"}}},
    {"action": "update_widget", "id": "task-1", "payload": {"data": {"value": 0.5}}},
    {"action": "pin_widget", "id": "task-1"},
    {"action": "pin_widget", "id": "task-1", "payload": {"pinned": False}},
    {"action": "dismiss_widget", "id": "task-1"},
    {"action": "restore_widget", "id": "task-1", "payload": {}},
    {"action": "set_voice_state", "payload": {"state": "listening"}},
])
def test_event_round_trip(event):
    frame = protocol.encode_event(event)
    assert frame.count(b"\n") == 1
    assert protocol.decode_event(frame) == event


@pytest.mark.parametrize("frame", [
    b'{"action":"launch","id":"a"}\n',
    b'{"action":"spawn_widget","id":"a/b"}\n',
    b'{"action":"restore_widget","id":"a"}',
    b'{"action":"restore_widget","id":"a"}\n{}\n',
    b'{"action":"dismiss_widget","id":"a","id":"b"}\n',
    b'{"action":"dismiss_widget","id":"a","payload":{"extra":true}}\n',
    b'{"action":"pin_widget","id":"a","payload":{"pinned":1}}\n',
    b'{"action":"set_voice_state","id":"a","payload":{"state":"idle"}}\n',
    b'{"action":"set_voice_state","payload":{"state":"missing"}}\n',
    b'{"action":"update_widget","id":"a","payload":{"data":{"constructor":{}}}}\n',
    b'{"action":"update_widget","id":"a","payload":{"data":1e900}}\n',
    b'{"action":"update_widget","id":"a","payload":{"data":"\\ud800"}}\n',
    b'{"action":"update_widget","id":"a","payload":{"data":"\xff"}}\n',
])
def test_malformed_events_are_rejected(frame):
    with pytest.raises(protocol.ProtocolError):
        protocol.decode_event(frame)


def test_frame_and_payload_bounds():
    event = {"action": "spawn_widget", "id": "a", "payload": {"data": ""}}
    size = protocol.MAX_EVENT_BYTES - len(protocol.encode_event(event))
    event["payload"]["data"] = "x" * size
    frame = protocol.encode_event(event)
    assert len(frame) == protocol.MAX_EVENT_BYTES
    assert protocol.decode_event(frame) == event
    event["payload"]["data"] += "x"
    with pytest.raises(protocol.ProtocolError, match="exceeds"):
        protocol.encode_event(event)
    with pytest.raises(protocol.ProtocolError, match="exceeds"):
        protocol.decode_event(b" " + frame)

    value = None
    for _ in range(protocol.MAX_PAYLOAD_DEPTH + 1):
        value = [value]
    event["payload"]["data"] = value
    with pytest.raises(protocol.ProtocolError, match="nested"):
        protocol.encode_event(event)


def test_socket_path(monkeypatch, tmp_path):
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    assert protocol.socket_path() == Path(f"/run/user/{os.getuid()}/jarvis-hud-preview.sock")
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    assert protocol.socket_path() == tmp_path / "jarvis-hud-preview.sock"


def test_emitter_dry_run_supports_both_input_forms(capsys):
    event = b'{"action":"set_voice_state","payload":{"state":"listening"}}\n'
    assert test_emit.main(["--dry-run", event.decode().rstrip()]) == 0
    assert capsys.readouterr().out.encode() == event
    assert test_emit.main(["--dry-run", "set_voice_state", "--payload", '{"state":"listening"}']) == 0
    assert capsys.readouterr().out.encode() == event


@pytest.mark.parametrize("reply,exit_code", [
    (b'{"ok":true}\n', 0),
    (b'{"ok":false,"error":"unknown widget"}\n', 1),
    (b'{"ok":true}', 1),
])
def test_emitter_sends_one_event_and_checks_acknowledgment(monkeypatch, tmp_path, capsys, reply, exit_code):
    path = tmp_path / "preview.sock"
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.makefile.return_value = BytesIO(reply)
    monkeypatch.setattr(test_emit.socket, "socket", lambda *args: connection)

    assert test_emit.main(["--socket", str(path), "pin_widget", "my-card"]) == exit_code
    connection.connect.assert_called_once_with(str(path))
    connection.sendall.assert_called_once_with(protocol.encode_event({"action": "pin_widget", "id": "my-card"}))
    if b"unknown widget" in reply:
        assert "unknown widget" in capsys.readouterr().err
