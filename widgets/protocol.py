"""Bounded NDJSON messages for the local widget preview socket."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re

MAX_EVENT_BYTES = 16 * 1024
MAX_PAYLOAD_DEPTH = 12
WIDGET_ACTIONS = frozenset({
    "spawn_widget", "update_widget", "pin_widget", "dismiss_widget", "restore_widget",
})
VOICE_ACTION = "set_voice_state"
VOICE_STATES = frozenset({"idle", "standby", "listening", "thinking", "working", "speaking"})
WIDGET_ID = re.compile(r"[A-Za-z0-9_-]{1,80}")
UNSAFE_KEYS = frozenset({"__proto__", "constructor", "prototype"})


class ProtocolError(ValueError):
    """An incoming or outgoing message violates the preview protocol."""


def socket_path() -> Path:
    runtime = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return Path(runtime) / "jarvis-hud-preview.sock"


def _check_data(value, depth=0) -> None:
    if depth > MAX_PAYLOAD_DEPTH:
        raise ProtocolError("payload is nested too deeply")
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or key in UNSAFE_KEYS:
                raise ProtocolError("invalid payload key")
            key.encode("utf-8")
            _check_data(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _check_data(item, depth + 1)
    elif isinstance(value, str):
        value.encode("utf-8")
    elif value is None or isinstance(value, bool):
        return
    elif isinstance(value, int) and abs(value) <= (1 << 53) - 1:
        return
    elif isinstance(value, float) and math.isfinite(value):
        return
    else:
        raise ProtocolError("payload values must be plain JSON with finite numbers")


def validate_event(event: object) -> dict:
    """Validate an event's shape and return it without mutating its payload."""
    if not isinstance(event, dict) or event.keys() - {"action", "id", "payload"}:
        raise ProtocolError("event must be an object with action, optional id and optional payload")
    action = event.get("action")
    if not isinstance(action, str) or (action not in WIDGET_ACTIONS and action != VOICE_ACTION):
        raise ProtocolError("unknown widget action")
    payload = event.get("payload", {})
    if not isinstance(payload, dict):
        raise ProtocolError("payload must be an object")
    if action == VOICE_ACTION:
        state = payload.get("state")
        if "id" in event or payload.keys() != {"state"} or not isinstance(state, str) or state not in VOICE_STATES:
            raise ProtocolError("voice event requires a valid payload.state and no widget id")
    else:
        widget_id = event.get("id")
        if not isinstance(widget_id, str) or WIDGET_ID.fullmatch(widget_id) is None:
            raise ProtocolError("widget id must be 1–80 letters, numbers, hyphens or underscores")
        if action == "pin_widget":
            if payload.keys() - {"pinned"} or not isinstance(payload.get("pinned", True), bool):
                raise ProtocolError("pin payload may only contain a boolean pinned value")
        if action in {"dismiss_widget", "restore_widget"} and payload:
            raise ProtocolError(f"{action} does not take payload fields")
    try:
        _check_data(payload)
    except UnicodeEncodeError as exc:
        raise ProtocolError("event must contain valid Unicode") from exc
    return event


def encode_event(event: object) -> bytes:
    """Validate and encode one UTF-8 event, including its newline."""
    validate_event(event)
    line = json.dumps(event, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8") + b"\n"
    if len(line) > MAX_EVENT_BYTES:
        raise ProtocolError(f"event exceeds {MAX_EVENT_BYTES} bytes")
    return line


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError("duplicate JSON key")
        result[key] = value
    return result


def decode_frame(line: bytes) -> object:
    """Decode exactly one newline-terminated JSON value from a bounded frame."""
    if len(line) > MAX_EVENT_BYTES:
        raise ProtocolError(f"event exceeds {MAX_EVENT_BYTES} bytes")
    if not line.endswith(b"\n") or b"\n" in line[:-1]:
        raise ProtocolError("expected one newline-terminated JSON event")
    try:
        return json.loads(line.decode("utf-8"), object_pairs_hook=_unique_object)
    except ProtocolError:
        raise
    except (ValueError, RecursionError) as exc:
        raise ProtocolError("event must be valid UTF-8 JSON") from exc


def decode_event(line: bytes) -> dict:
    """Decode and validate one event from a complete frame."""
    return validate_event(decode_frame(line))
