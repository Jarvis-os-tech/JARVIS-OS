"""Unit tests for Phase 2/3 Linux/PipeWire/Hyprland/cliphist/type_text primitives."""
from __future__ import annotations

import json
import os
import signal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from skills import DesktopSkills, ground_truth, system_control


@pytest.mark.asyncio
async def test_audio_list_devices_filters_monitors_and_reads_streams(monkeypatch):
    monkeypatch.setattr(system_control.shutil, "which", lambda cmd: f"/usr/bin/{cmd}" if cmd in ("pactl", "wpctl") else None)
    sinks_json = json.dumps([
        {
            "index": 41,
            "name": "alsa_output.pci-0000_00_1f.3.analog-stereo",
            "description": "Built-in Audio Analog Stereo",
            "state": "RUNNING",
            "mute": False,
            "volume": {"front-left": {"value_percent": "60%"}, "front-right": {"value_percent": "60%"}},
            "active_port": "analog-output-speaker",
            "ports": [{"name": "analog-output-speaker", "description": "Speakers", "availability": "available"}],
            "properties": {"object.id": "55", "node.nick": "ALC295 Analog"},
        },
        {
            "index": 48,
            "name": "bluez_output.AA_BB_CC.1",
            "description": "WH-1000XM5 Headphones",
            "state": "IDLE",
            "mute": False,
            "volume": {"front-left": {"value_percent": "80%"}},
            "active_port": "headphone-output",
            "ports": [{"name": "headphone-output", "description": "Headphone", "availability": "available"}],
            "properties": {"object.id": "82", "node.nick": "XM5"},
        },
    ])
    sources_json = json.dumps([
        {
            "index": 12,
            "name": "alsa_output.pci.analog-stereo.monitor",
            "description": "Monitor of Built-in Audio",
            "state": "IDLE",
            "mute": False,
            "volume": {},
            "properties": {"object.id": "56", "device.class": "monitor"},
        },
        {
            "index": 15,
            "name": "alsa_input.usb-Blue_Yeti.mono",
            "description": "Yeti Stereo Microphone",
            "state": "RUNNING",
            "mute": False,
            "volume": {"mono": {"value_percent": "75%"}},
            "properties": {"object.id": "63", "node.nick": "Yeti"},
        },
    ])
    sink_inputs_json = json.dumps([{"index": 101, "sink": 41, "properties": {"application.name": "Firefox", "media.name": "Video"}}])
    source_outputs_json = json.dumps([])

    async def fake_control_exec(*args, **_kwargs):
        cmd = args[1:]
        if cmd == ("get-default-sink",):
            return {"status": "success", "stdout": "alsa_output.pci-0000_00_1f.3.analog-stereo"}
        if cmd == ("get-default-source",):
            return {"status": "success", "stdout": "alsa_input.usb-Blue_Yeti.mono"}
        if cmd == ("-f", "json", "list", "sinks"):
            return {"status": "success", "stdout": sinks_json}
        if cmd == ("-f", "json", "list", "sources"):
            return {"status": "success", "stdout": sources_json}
        if cmd == ("-f", "json", "list", "sink-inputs"):
            return {"status": "success", "stdout": sink_inputs_json}
        if cmd == ("-f", "json", "list", "source-outputs"):
            return {"status": "success", "stdout": source_outputs_json}
        raise AssertionError(f"unexpected args: {args}")

    monkeypatch.setattr(system_control, "_control_exec", fake_control_exec)
    res = await system_control.audio_list_devices("all")
    assert res["status"] == "success" and res["verified"] is True
    assert len(res["outputs"]) == 2
    assert res["outputs"][0]["is_default"] is True
    assert len(res["inputs"]) == 1  # monitor source excluded
    assert res["inputs"][0]["description"] == "Yeti Stereo Microphone"
    assert res["active_streams"]["output_streams"][0]["app_name"] == "Firefox"


@pytest.mark.asyncio
async def test_audio_set_device_switches_default_moves_streams_and_verifies(monkeypatch):
    monkeypatch.setattr(system_control.shutil, "which", lambda cmd: f"/usr/bin/{cmd}" if cmd in ("pactl", "wpctl") else None)
    state = {"default_sink": "alsa_output.pci.analog"}
    calls = []

    sinks = [
        {"id": 41, "wp_id": 55, "kind": "output", "name": "alsa_output.pci.analog", "description": "Built-in Speakers", "nick": "", "ports": [], "is_default": True},
        {"id": 48, "wp_id": 82, "kind": "output", "name": "bluez_output.XM5", "description": "Sony Headphones", "nick": "XM5", "ports": [], "is_default": False},
    ]
    monkeypatch.setattr(
        system_control,
        "audio_list_devices",
        AsyncMock(return_value={"status": "success", "verified": True, "outputs": sinks}),
    )

    async def fake_control_exec(*args, **_kwargs):
        calls.append(args)
        if args == ("/usr/bin/wpctl", "set-default", "82"):
            state["default_sink"] = "bluez_output.XM5"
            return {"status": "success", "stdout": ""}
        if args[:2] == ("/usr/bin/pactl", "set-default-sink"):
            return {"status": "success", "stdout": ""}
        if args == ("/usr/bin/pactl", "-f", "json", "list", "sink-inputs"):
            return {"status": "success", "stdout": json.dumps([
                {"index": 101, "sink": 41, "properties": {"application.name": "Firefox"}},
                {"index": 102, "sink": 41, "properties": {"media.role": "filter"}},
            ])}
        if args == ("/usr/bin/pactl", "move-sink-input", "101", "bluez_output.XM5"):
            return {"status": "success", "stdout": ""}
        if args == ("/usr/bin/pactl", "get-default-sink"):
            return {"status": "success", "stdout": state["default_sink"]}
        raise AssertionError(f"unexpected command: {args}")

    monkeypatch.setattr(system_control, "_control_exec", fake_control_exec)
    skills = DesktopSkills()
    try:
        res = await skills.execute("audio_set_device", {"device": "headphones", "kind": "output", "move_streams": True})
    finally:
        await skills.close_agent_jobs()

    assert res["status"] == "success" and res["verified"] is True
    assert res["device"] == "bluez_output.XM5"
    assert res["moved_streams"] == 1
    assert ("/usr/bin/wpctl", "set-default", "82") in calls
    assert ("/usr/bin/pactl", "move-sink-input", "101", "bluez_output.XM5") in calls
    assert not any("102" in c for c in calls)


@pytest.mark.asyncio
async def test_audio_set_device_reports_readback_mismatch(monkeypatch):
    monkeypatch.setattr(system_control.shutil, "which", lambda cmd: f"/usr/bin/{cmd}" if cmd in ("pactl", "wpctl") else None)
    sinks = [{"id": 48, "wp_id": 82, "kind": "output", "name": "bluez_output.XM5", "description": "Headphones", "nick": "", "ports": [], "is_default": False}]
    monkeypatch.setattr(system_control, "audio_list_devices", AsyncMock(return_value={"status": "success", "outputs": sinks}))
    monkeypatch.setattr(system_control.asyncio, "sleep", AsyncMock())

    async def fake_control_exec(*args, **_kwargs):
        if args[:2] in (("/usr/bin/wpctl", "set-default"), ("/usr/bin/pactl", "set-default-sink")):
            return {"status": "success", "stdout": ""}
        if args == ("/usr/bin/pactl", "-f", "json", "list", "sink-inputs"):
            return {"status": "success", "stdout": "[]"}
        if args == ("/usr/bin/pactl", "get-default-sink"):
            return {"status": "success", "stdout": "alsa_output.pci.analog"}
        return {"status": "success", "stdout": ""}

    monkeypatch.setattr(system_control, "_control_exec", fake_control_exec)
    res = await system_control.audio_set_device("headphones")
    assert res["status"] == "error"
    assert "remained" in res["message"]


@pytest.mark.asyncio
async def test_manage_window_directional_monitor_swap_split_resize(monkeypatch):
    monkeypatch.setattr(system_control.shutil, "which", lambda cmd: "/usr/bin/hyprctl" if cmd == "hyprctl" else None)
    dispatched_lua = []
    state = {
        "active": {"address": "0x123", "pid": 42, "monitor": 0, "at": [0, 0], "size": [900, 1000], "workspace": {"id": 1}},
        "clients": [
            {"address": "0x123", "pid": 42, "monitor": 0, "at": [0, 0], "size": [900, 1000], "workspace": {"id": 1}},
            {"address": "0x456", "pid": 99, "monitor": 0, "at": [900, 0], "size": [900, 1000], "workspace": {"id": 1}},
        ],
        "monitors": [
            {"id": 0, "name": "eDP-1", "x": 0, "y": 0, "width": 1920, "height": 1080, "scale": 1.0, "focused": True, "disabled": False},
            {"id": 1, "name": "DP-1", "x": 1920, "y": 0, "width": 2560, "height": 1440, "scale": 1.0, "focused": False, "disabled": False},
        ],
    }

    async def fake_observe(_hyprctl, query):
        data = state[{"activewindow": "active", "clients": "clients", "monitors": "monitors"}[query]]
        return {"status": "success", "data": json.loads(json.dumps(data)), "source": f"hyprctl {query}", "observed_at": "now"}

    async def fake_dispatch(_hyprctl, lua, _legacy, **_kwargs):
        dispatched_lua.append(lua)
        w = state["clients"][0]
        if 'monitor = "DP-1"' in lua:
            w["monitor"] = 1
        elif "window.move" in lua or "window.swap" in lua:
            w["at"] = [900, 0]
        elif "window.resize" in lua:
            w["size"] = [980, 1000]
        elif "togglesplit" in lua:
            w["size"] = [1800, 500]
        return {"status": "executed"}

    monkeypatch.setattr(system_control, "_desktop_observe", fake_observe)
    monkeypatch.setattr(system_control, "_desktop_dispatch", fake_dispatch)

    r_mon = await system_control.manage_window("move_monitor", monitor="next")
    assert r_mon["status"] == "success" and r_mon["verified"] is True
    assert 'monitor = "DP-1"' in dispatched_lua[-1]

    state["clients"][0]["monitor"] = 0
    state["clients"][0]["at"] = [0, 0]
    r_dir = await system_control.manage_window("move_direction", direction="right")
    assert r_dir["status"] == "success" and r_dir["verified"] is True
    assert 'direction = "r"' in dispatched_lua[-1]

    state["clients"][0]["at"] = [0, 0]
    r_swap = await system_control.manage_window("swap", direction="right")
    assert r_swap["status"] == "success" and r_swap["verified"] is True
    assert "hl.dsp.window.swap" in dispatched_lua[-1]

    r_split = await system_control.manage_window("split")
    assert r_split["status"] == "success" and r_split["verified"] is True
    assert 'hl.dsp.layout("togglesplit")' in dispatched_lua[-1]

    state["clients"][0]["size"] = [900, 1000]
    r_resize = await system_control.manage_window("resize", direction="right")
    assert r_resize["status"] == "success" and r_resize["verified"] is True
    assert "x = 80, y = 0" in dispatched_lua[-1]


@pytest.mark.asyncio
async def test_control_display_list_scale_extend_mirror_and_rejects_bad_monitor(monkeypatch):
    monkeypatch.setattr(system_control.shutil, "which", lambda cmd: "/usr/bin/hyprctl" if cmd == "hyprctl" else None)
    monitors_state = [
        {"id": 0, "name": "eDP-1", "description": "Internal", "width": 1920, "height": 1080, "refreshRate": 60.0, "x": 0, "y": 0, "scale": 1.0, "transform": 0, "focused": True, "disabled": False, "mirrorOf": ""},
        {"id": 1, "name": "DP-1", "description": "External", "width": 2560, "height": 1440, "refreshRate": 144.0, "x": 1920, "y": 0, "scale": 1.0, "transform": 0, "focused": False, "disabled": False, "mirrorOf": ""},
    ]
    keyword_cmds = []

    async def fake_observe(_hyprctl, query):
        return {"status": "success", "data": json.loads(json.dumps(monitors_state)), "source": f"hyprctl {query}", "observed_at": "now"}

    async def fake_exec(*args, **_kwargs):
        keyword_cmds.append(args)
        spec = args[3]
        if spec.startswith("DP-1,2560x1440"):
            monitors_state[1]["scale"] = 1.5
        elif "mirror,eDP-1" in spec:
            monitors_state[1]["mirrorOf"] = "eDP-1"
        elif spec.startswith("DP-1,preferred,1920x0"):
            monitors_state[1]["mirrorOf"] = ""
            monitors_state[1]["disabled"] = False
        return {"status": "success", "stdout": ""}

    monkeypatch.setattr(system_control, "_desktop_observe", fake_observe)
    monkeypatch.setattr(system_control, "_control_exec", fake_exec)

    listed = await system_control.control_display("list")
    assert listed["count"] == 2

    scaled = await system_control.control_display("scale", monitor="DP-1", scale="1.5")
    assert scaled["status"] == "success" and scaled["verified"] is True

    mirrored = await system_control.control_display("mirror", monitor="DP-1", source_monitor="eDP-1")
    assert mirrored["status"] == "success" and mirrored["verified"] is True

    extended = await system_control.control_display("extend", monitor="DP-1", source_monitor="eDP-1", position="right")
    assert extended["status"] == "success" and extended["verified"] is True

    bad = await system_control.control_display("scale", monitor="DP-1;rm -rf /", scale="1.5")
    assert bad["status"] == "error"


@pytest.mark.asyncio
async def test_cliphist_history_and_paste_item_via_desktop_skills(monkeypatch):
    monkeypatch.setattr(system_control.shutil, "which", lambda cmd: f"/usr/bin/{cmd}" if cmd in ("cliphist", "wl-copy", "wl-paste", "wtype") else None)
    clipboard_buf = {"data": b""}
    active_win = {"address": "0x222", "pid": 77, "class": "foot"}

    async def fake_exec_bytes(*args, input_bytes=None, **_kwargs):
        cmd_name = Path(args[0]).name
        if cmd_name == "cliphist" and args[1] == "list":
            return 0, b"12\thello world\n9\tsecond item\n", b""
        if cmd_name == "cliphist" and args[1] == "decode":
            assert args[2] == "12"
            return 0, b"hello world", b""
        if cmd_name == "wl-copy":
            clipboard_buf["data"] = input_bytes or b""
            return 0, b"", b""
        if cmd_name == "wl-paste":
            return 0, clipboard_buf["data"], b""
        raise AssertionError(f"unexpected bytes cmd: {args}")

    monkeypatch.setattr(system_control, "_subprocess_exec_bytes", fake_exec_bytes)
    monkeypatch.setattr(system_control, "_query_active_window", AsyncMock(return_value=active_win))
    run_mock = AsyncMock(return_value=(0, "", ""))
    monkeypatch.setattr(system_control, "_run_command", run_mock)

    skills = DesktopSkills()
    try:
        hist = await skills.execute("read_clipboard", {"action": "history", "limit": 5})
        assert hist["count"] == 2
        assert hist["items"][0]["id"] == "12"

        pasted = await skills.execute("read_clipboard", {"action": "paste_item", "item_id": "12", "paste": True})
        assert pasted["status"] == "pasted" and pasted["verified"] is True
        run_mock.assert_awaited_once_with("/usr/bin/wtype", "-M", "ctrl", "-M", "shift", "-k", "v", "-m", "shift", "-m", "ctrl")
    finally:
        await skills.close_agent_jobs()


@pytest.mark.asyncio
async def test_screen_record_start_status_stop(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "runtime"))
    out_file = tmp_path / "capture.mp4"
    monkeypatch.setattr(system_control.shutil, "which", lambda cmd: f"/usr/bin/{cmd}" if cmd in ("gpu-screen-recorder", "hyprctl") else None)
    monkeypatch.setattr(system_control, "_desktop_observe", AsyncMock(return_value={
        "status": "success",
        "data": [{"name": "DP-1", "focused": True, "disabled": False}],
    }))
    monkeypatch.setattr(system_control.asyncio, "sleep", AsyncMock())

    alive = {"running": True}
    fake_proc = SimpleNamespace(pid=424242, returncode=None, stderr=None)
    monkeypatch.setattr(system_control.asyncio, "create_subprocess_exec", AsyncMock(return_value=fake_proc))
    monkeypatch.setattr(system_control, "_pid_matches_recorder", lambda pid, backend: alive["running"] and pid == 424242)

    def fake_kill(pid, sig):
        assert pid == 424242
        if sig == signal.SIGINT:
            out_file.write_bytes(b"\x00\x00\x00\x20ftypmp42")
            alive["running"] = False
            return None
        if sig == 0 and not alive["running"]:
            raise ProcessLookupError()

    monkeypatch.setattr(system_control.os, "kill", fake_kill)

    started = await system_control.screen_record("start", region="full", with_audio=True, output_path=str(out_file))
    assert started["status"] == "recording" and started["verified"] is True

    dup = await system_control.screen_record("start")
    assert dup["status"] == "error"

    stat = await system_control.screen_record("status")
    assert stat["recording"] is True and stat["pid"] == 424242

    stopped = await system_control.screen_record("stop")
    assert stopped["status"] == "stopped" and stopped["verified"] is True and stopped["size_bytes"] > 0

    idle = await system_control.screen_record("status")
    assert idle["recording"] is False and idle["status"] == "idle"


@pytest.mark.asyncio
async def test_type_text_electron_paste_and_tmux_effect_observed(monkeypatch):
    monkeypatch.setattr(
        system_control.shutil,
        "which",
        lambda cmd: f"/usr/bin/{cmd}" if cmd in ("wtype", "wl-copy", "wl-paste", "tmux", "hyprctl") else None,
    )
    electron_win = {"address": "0x999", "pid": 88, "class": "antigravity", "title": "Editor", "xwayland": False}
    monkeypatch.setattr(system_control, "_query_active_window", AsyncMock(return_value=electron_win))
    monkeypatch.setattr(system_control, "_query_open_windows", AsyncMock(return_value=[electron_win]))
    monkeypatch.setattr(system_control, "_find_tmux_pane_for_window", AsyncMock(return_value=None))
    monkeypatch.setattr(system_control, "_ocr_window_snapshot", AsyncMock(return_value=None))
    monkeypatch.setattr(system_control.asyncio, "sleep", AsyncMock())

    clip = {"bytes": b"prior-clip"}
    copied_values = []

    async def fake_exec_bytes(*args, input_bytes=None, **_kwargs):
        name = Path(args[0]).name
        if name == "wl-paste":
            return 0, clip["bytes"], b""
        if name == "wl-copy":
            clip["bytes"] = input_bytes or b""
            copied_values.append(clip["bytes"])
            return 0, b"", b""
        return 0, b"", b""

    monkeypatch.setattr(system_control, "_subprocess_exec_bytes", fake_exec_bytes)
    mock_run = AsyncMock(return_value=(0, "", ""))
    monkeypatch.setattr(system_control, "_run_command", mock_run)

    with patch("asyncio.create_subprocess_exec") as mock_sub:
        proc_mock = AsyncMock()
        proc_mock.communicate = AsyncMock(side_effect=lambda payload=None: (setattr(proc_mock, "returncode", 0), clip.__setitem__("bytes", payload or b""), copied_values.append(payload), (b"", b""))[-1])
        proc_mock.returncode = 0
        mock_sub.return_value = proc_mock

        res = await system_control.type_text("hello electron", target_window="antigravity", press_enter=True)

    assert res["method"] == "clipboard_paste"
    mock_run.assert_any_await("/usr/bin/wtype", "-M", "ctrl", "-k", "v", "-m", "ctrl")
    mock_run.assert_any_await("/usr/bin/wtype", "-k", "Return")
    # Restores prior clipboard after paste
    assert copied_values[-1] == b"prior-clip"

    # Now verify direct single-line ASCII call without target_window/ACTION_TARGET still queries active window + tmux readback
    term_win = {"address": "0xabc", "pid": 90, "class": "foot", "title": "zsh"}
    monkeypatch.setattr(system_control, "_query_active_window", AsyncMock(return_value=term_win))
    monkeypatch.setattr(system_control, "_find_tmux_pane_for_window", AsyncMock(return_value="%3"))
    monkeypatch.setattr(system_control, "_capture_tmux_pane", AsyncMock(side_effect=["$ ", "$ echo direct"]))

    direct_res = await system_control.type_text("echo direct")
    assert direct_res["status"] == "effect_observed"
    assert direct_res["verified"] is True

    # Reset side_effect for DesktopSkills.execute check
    monkeypatch.setattr(system_control, "_capture_tmux_pane", AsyncMock(side_effect=["$ ", "$ echo hi"]))

    skills = DesktopSkills()
    try:
        verified_res = await skills.execute("type_text", {"text": "echo hi"})
    finally:
        await skills.close_agent_jobs()

    assert verified_res["status"] == "effect_observed"
    assert verified_res["verified"] is True
    assert verified_res["evidence"]["source"] == "tmux_capture_pane"


@pytest.mark.asyncio
async def test_choices_widget_manifest_and_select_adapter(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "ui.jarvis_widgets.backend.shell_call",
        lambda method, payload=None: (calls.append((method, payload)), {"ok": True, "id": "choice-1"})[1],
    )
    skills = DesktopSkills()
    try:
        shown = await skills.execute("show_widget", {
            "kind": "choices",
            "title": "Pick monitor",
            "data_json": json.dumps({"items": [{"label": "eDP-1"}, {"label": "DP-1"}]}),
        })
        assert shown["ok"] is True
        sel = await skills.execute("manage_widget", {
            "action": "select",
            "widget_id": "choice-1",
            "index": 2,
            "dismiss": True,
        })
        assert sel["ok"] is True
        assert calls[-1] == ("manage", {"id": "choice-1", "action": "select", "index": 2, "dismiss": True})
    finally:
        await skills.close_agent_jobs()
