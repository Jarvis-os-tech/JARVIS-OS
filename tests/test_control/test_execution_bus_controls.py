"""Tests for UnifiedSkills catalog deduplication, Control system_control, cliphist, and type_text."""
from __future__ import annotations

import json
import subprocess
from unittest.mock import Mock, patch

import pytest

from jarvis_control.config import Config
from jarvis_control.skills import ControlSkills, UnifiedSkills
from jarvis_control.system_control import ACTIONS, SCHEMA, execute, validate
from jarvis_control.tools import Executor, Result
from skills.skills import DesktopSkills


@pytest.mark.asyncio
async def test_unified_skills_prefers_desktop_and_keeps_legacy_executable(monkeypatch):
    control = ControlSkills(Config(dry_run=True))
    desktop = DesktopSkills()
    unified = UnifiedSkills(control_skills=control, desktop_skills=desktop)
    try:
        live_names = [t["name"] for t in unified.live_declarations]
        assert len(live_names) <= 50
        assert len(live_names) == len(set(live_names))
        assert "type_text" in unified._desktop_names
        assert "lock_screen" in unified._control_names
        assert "shutdown_system" in unified._control_names
        assert "restart_system" in unified._control_names
        assert "system_power" in unified._control_names
        assert "show_widget" in unified._desktop_names

        # NeedsConfirmation / ExecutionAirlock gate must hold even when confirm=True is passed
        for power_tool in ("lock_screen", "shutdown_system", "restart_system"):
            res_hold = await unified.execute(power_tool, {"confirm": True})
            assert "needs spoken confirmation" in res_hold
            pending = control.executor.pending_approval()
            assert pending is not None
            cancel_msg = await unified.execute("cancel_system_action", {})
            assert "Cancelled" in cancel_msg
            assert control.executor.pending_approval() is None

        # execute_domain_tool / direct DesktopSkills bypass attempt with confirm=True is also blocked
        from skills.system_power import POWER_MANAGER
        from skills.errors import SkillError
        POWER_MANAGER.clear_pending()
        with patch.object(desktop, "_run", side_effect=AssertionError("must never lock")):
            for dom in ("core", "desktop"):
                with pytest.raises(SkillError):
                    await unified.execute("execute_domain_tool", {
                        "domain": dom,
                        "tool_name": "lock_screen",
                        "arguments_json": '{"confirm": true}',
                    })
            with pytest.raises(SkillError):
                await desktop.execute("lock_screen", {"confirm": True})
            held_direct = await desktop._adapter_lock_screen(confirm=True)
            assert held_direct["status"] == "needs_confirmation"
            POWER_MANAGER.clear_pending()

        # Legacy ControlSkills alias launch_app remains executable even though excluded from live_declarations
        assert "launch_app" not in set(live_names)
        assert "launch_app" in {t["name"] for t in unified.declarations}
        res = await unified.execute("launch_app", {"app": "nonexistent.desktop"})
        assert isinstance(res, str)

        # Confirmation bridges both ControlSkills.executor.pending and POWER_MANAGER
        from skills.system_power import POWER_MANAGER
        with patch("ui.jarvis_widgets.backend.shell_call", return_value={"ok": True}):
            POWER_MANAGER.request_action("lock", confirm=False)
            try:
                with patch.object(desktop, "execute", return_value={"status": "executing", "action": "lock"}) as mock_exec:
                    conf = await unified.execute("confirm_system_action", {"heard_phrase": "yes"})
                    assert json.loads(conf)["status"] == "executing"
                    mock_exec.assert_called_once_with("confirm_system_action", {"heard_phrase": "yes"})
            finally:
                POWER_MANAGER.clear_pending()
    finally:
        await unified.close_agent_jobs()


def test_control_system_control_directional_window_actions():
    assert {"window_minimize", "window_move_monitor", "window_move_direction", "window_swap", "window_split", "window_resize"} <= set(ACTIONS)
    assert "direction" in SCHEMA["input_schema"]["properties"]
    assert validate("window_move_direction", direction="bogus") is not None
    assert validate("window_resize") is not None
    assert validate("window_resize", value=40, direction="invalid") is not None

    state = {
        "active": {"address": "0x100", "pid": 55, "monitor": 0, "at": [0, 0], "size": [800, 900], "workspace": {"id": 1, "name": "1"}},
        "clients": [{"address": "0x100", "pid": 55, "monitor": 0, "at": [0, 0], "size": [800, 900], "workspace": {"id": 1, "name": "1"}}],
        "monitors": [
            {"id": 0, "name": "eDP-1", "x": 0, "y": 0, "disabled": False},
            {"id": 1, "name": "DP-1", "x": 1920, "y": 0, "disabled": False},
        ],
    }
    dispatches = []
    executor = Mock()

    def query(kind):
        return Result(True, json.dumps(state[{"activewindow": "active", "clients": "clients", "monitors": "monitors"}[kind]]))

    def dispatch(lua):
        dispatches.append(lua)
        c = state["clients"][0]
        if "special:scratchpad" in lua:
            c["workspace"] = {"id": -99, "name": "special:scratchpad"}
        elif 'monitor = "DP-1"' in lua:
            c["monitor"] = 1
        elif "window.move" in lua or "window.swap" in lua:
            c["at"] = [960, 0]
        elif "window.resize" in lua:
            c["size"] = [860, 900]
        return Result(True, "ok")

    executor._tool_hypr_query.side_effect = query
    executor._tool_hypr_dispatch.side_effect = dispatch

    assert execute(executor, "window_minimize").ok
    assert execute(executor, "window_move_monitor", target="DP-1").ok
    assert execute(executor, "window_move_direction", direction="right").ok
    assert execute(executor, "window_swap", direction="left").ok
    assert execute(executor, "window_split").ok
    assert execute(executor, "window_resize", direction="right", value=60).ok


def test_executor_clipboard_cliphist_history_and_paste_item(monkeypatch):
    executor = Executor(Config())
    monkeypatch.setattr("jarvis_control.tools.shutil.which", lambda cmd: f"/usr/bin/{cmd}" if cmd in ("cliphist", "wl-copy", "wl-paste") else None)
    clipboard_bytes = {"buf": b""}

    def fake_run(argv, capture_output=False, text=False, input=None, stdout=None, stderr=None, timeout=None, env=None):
        prog = argv[0]
        if prog == "cliphist" and argv[1] == "list":
            return subprocess.CompletedProcess(argv, 0, "42\talpha line\n43\tbeta line\n", "")
        if prog == "cliphist" and argv[1] == "decode":
            assert argv[2] == "42"
            return subprocess.CompletedProcess(argv, 0, b"alpha line", b"")
        if prog == "wl-copy":
            clipboard_bytes["buf"] = input or b""
            return subprocess.CompletedProcess(argv, 0, b"", b"")
        if prog == "wl-paste":
            return subprocess.CompletedProcess(argv, 0, clipboard_bytes["buf"], b"")
        raise AssertionError(f"unexpected subprocess: {argv}")

    monkeypatch.setattr("jarvis_control.tools.subprocess.run", fake_run)
    win = {"address": "0x200", "pid": 77, "class": "antigravity", "focusHistoryID": 0}
    monkeypatch.setattr(executor, "_window_geometry", lambda _target="activewindow": (win, None))
    shortcut_mock = Mock(return_value=Result(True, "ok"))
    monkeypatch.setattr(executor, "_tool_send_shortcut", shortcut_mock)

    hist = executor.call("clipboard", {"action": "history", "limit": 5})
    assert hist.ok
    assert json.loads(hist.output)["items"][0]["id"] == "42"

    pasted = executor.call("clipboard", {"action": "paste_item", "item_id": "42", "paste": True})
    assert pasted.ok
    assert json.loads(pasted.output)["verified"] is True
    shortcut_mock.assert_called_once_with("CTRL", "v", "address:0x200")


def test_executor_type_text_wayland_electron_and_tmux_verification(monkeypatch):
    executor = Executor(Config())
    win_electron = {"address": "0x300", "pid": 88, "class": "antigravity", "xwayland": False, "focusHistoryID": 0}
    monkeypatch.setattr(executor, "_window_geometry", lambda _target="activewindow": (win_electron, None))
    pasted = []
    monkeypatch.setattr("jarvis_control.tools.page_text.paste_text", lambda text, paste_fn, _focused: (paste_fn(), pasted.append(text)))
    monkeypatch.setattr(executor, "_tool_send_shortcut", lambda mods, key, window: Result(True, f"{mods}+{key}@{window}"))

    res = executor.call("type_text", {"text": "hello antigravity", "press_enter": True})
    assert res.ok and pasted == ["hello antigravity"]

    # Terminal with tmux pane proves effect_observed
    win_term = {"address": "0x301", "pid": 1, "class": "foot", "xwayland": False, "focusHistoryID": 0}
    monkeypatch.setattr(executor, "_window_geometry", lambda _target="activewindow": (win_term, None))
    monkeypatch.setattr("jarvis_control.tools.shutil.which", lambda cmd: "/usr/bin/tmux" if cmd == "tmux" else None)
    monkeypatch.setattr(executor, "_shell", lambda argv, input_text="": Result(True, "ok"))

    captures = iter(["$ ", "$ pwd"])

    def fake_run(argv, capture_output=False, text=False, timeout=None, env=None):
        if argv[1] == "list-panes":
            return subprocess.CompletedProcess(argv, 0, "1\t%1\t1\n", "")
        if argv[1] == "capture-pane":
            return subprocess.CompletedProcess(argv, 0, next(captures), "")
        raise AssertionError(argv)

    monkeypatch.setattr("jarvis_control.tools.subprocess.run", fake_run)
    monkeypatch.setattr("jarvis_control.tools.time.sleep", lambda _s: None)
    term_res = executor.call("type_text", {"text": "pwd"})
    assert term_res.ok
    data = json.loads(term_res.output)
    assert data["status"] == "effect_observed" and data["verified"] is True
