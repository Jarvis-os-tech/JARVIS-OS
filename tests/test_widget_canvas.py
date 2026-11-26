import asyncio
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from widgets import backend
from scripts.install_widget_plugin import install
from skills.domains.widgets import WidgetsDomain
from skills.errors import SkillError
from widgets.view_schema import validate_view, EXAMPLE


@pytest.fixture(autouse=True)
def private_widget_state(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))


class WidgetDataTests(unittest.TestCase):
    def test_widget_management_routes_bulk_removal_to_canvas(self):
        for action, method in (("clear", "clear"), ("clear_all", "clearAll"), ("status", "status")):
            with self.subTest(action=action), patch("asyncio.to_thread", WidgetAdapterTests.inline_worker), patch.object(backend, "shell_call", return_value={"ok": True}) as call:
                result = asyncio.run(WidgetsDomain()._adapter_manage_widget(action))
                call.assert_called_once_with(method)
                self.assertTrue(result["ok"])

    def test_custom_layout_is_generated_from_composable_components(self):
        item = backend.make_widget("view", "Estimator", EXAMPLE)
        self.assertTrue(item["floating"])
        self.assertEqual(item["data"]["layout"]["children"][1]["type"], "slider")

    def test_view_rejects_cycles_unbound_controls_and_executable_properties(self):
        for data in [
            {"layout": {"type": "text", "text": "A", "onClicked": "run()"}},
            {"computed": {"a": {"ref": "b"}, "b": {"ref": "a"}}, "layout": {"type": "text", "text": "A"}},
            {"state": {}, "layout": {"type": "input", "label": "Missing", "bind": "missing"}},
            {"state": {"n": 10}, "layout": {"type": "slider", "label": "Bad", "bind": "n", "min": 0, "max": 5}},
        ]:
            with self.subTest(data=data), self.assertRaises(ValueError): validate_view(data)

    def test_diagrams_accept_data_bound_geometry(self):
        data = {"state": {"position": 100}, "layout": {"type": "canvas", "shapes": [
            {"type": "circle", "x": {"ref": "position"}, "y": 500, "r": 40, "fill": "#76DDD2"}
        ]}}
        self.assertEqual(validate_view(data)["layout"]["type"], "canvas")

    def test_widget_specs_load_in_the_actual_registry_without_starting_services(self):
        from skills.skills import DesktopSkills
        registry = DesktopSkills.__new__(DesktopSkills)
        registry.manifest_dirs = [Path(__file__).resolve().parents[1] / "skill_manifests"]
        specs = registry._load_manifests()
        self.assertTrue({"show_widget", "manage_canvas", "manage_widget"} <= set(specs))

    def test_generated_code_and_remote_media_are_not_widgets(self):
        for kind, data in [("qml", {"code": "Qt.quit()"}), ("text", {"text": "ok", "command": "exit"}),
                           ("pip", {"path": "https://example.org/video.mp4"})]:
            with self.subTest(kind=kind), self.assertRaises((ValueError, OSError)):
                backend.make_widget(kind, "Test", data)

    def test_table_shape_and_chart_measurements_are_checked(self):
        for kind, data in [("table", {"columns": ["A"], "rows": [[1, 2]]}),
                           ("chart", {"labels": ["A"], "values": [float("nan")]}),
                           ("progress", {"value": 12, "maximum": 10})]:
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                backend.validate(kind, data)

    def test_updates_use_given_identity_and_unknown_progress_is_not_a_percentage(self):
        item = backend.make_widget("progress", "Research", {"text": "Reading sources"}, widget_id="research-1")
        self.assertEqual(item["id"], "research-1")
        self.assertNotIn("value", item["data"])

    def test_qr_is_generated_locally_without_payload_in_argv(self):
        if not backend.shutil.which("qrencode"):
            self.skipTest("qrencode unavailable")
        with tempfile.TemporaryDirectory(prefix="jarvis-widgets-test-") as directory:
            with patch.dict(os.environ, {"XDG_RUNTIME_DIR": directory}):
                actual = subprocess.run
                with patch.object(backend.subprocess, "run", wraps=actual) as run:
                    item = backend.make_widget("qr", "Example", {"content": "https://example.org"})
                self.assertNotIn("https://example.org", run.call_args.args[0])
                path = Path(item["data"]["source"].removeprefix("file://"))
                self.assertTrue(path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_image_and_pip_widgets_support_actions(self):
        with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
            item = backend.make_widget("image", "Snapshot", {
                "path": tmp.name,
                "caption": "Captured window",
                "actions": [{"label": "Dismiss", "action": "dismiss"}]
            })
            self.assertEqual(item["kind"], "image")
            self.assertIn("actions", item["data"])
            self.assertEqual(item["data"]["actions"][0]["label"], "Dismiss")

    def test_theme_hud_routes_widget_updates_to_quickshell(self):
        entry = Path("/mock/jarvis/ui/JarvisTheme.qml")
        with patch.object(backend, "theme_hud_entry", return_value=entry), \
                patch.object(backend.shutil, "which", return_value="/usr/bin/qs"), \
                patch.object(backend.subprocess, "run", return_value=subprocess.CompletedProcess(
                    [], 0, '{"ok":true}', ""
                )) as run:
            widget = backend.make_widget("text", "Demo", {"text": "Live"}, widget_id="demo")
            self.assertTrue(backend.shell_call("present", widget)["ok"])
            command = run.call_args.args[0]
            self.assertEqual(command[:-1], ["/usr/bin/qs", "--path", str(entry), "ipc", "call",
                                            "jarvis-hud-preview", "present"])
            self.assertEqual(json.loads(command[-1]), widget)

    def test_clear_routes_to_visible_native_shell(self):
        entry = Path("/mock/jarvis/ui/JarvisTheme.qml")
        with patch.object(backend, "theme_hud_entry", return_value=entry), \
                patch.object(backend.shutil, "which", return_value="/usr/bin/qs"), \
                patch.object(backend.subprocess, "run", return_value=subprocess.CompletedProcess(
                    [], 0, '{"ok":true,"retained":0}', ""
                )) as run:
            for method in ("clear", "clearAll"):
                self.assertEqual(backend.shell_call(method)["retained"], 0)
                self.assertEqual(run.call_args.args[0], ["/usr/bin/qs", "--path", str(entry),
                    "ipc", "call", "jarvis-hud-preview", method])

    def test_unknown_ipc_targets_cannot_look_successful(self):
        with patch.object(backend.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "Target not found.", "")):
            with self.assertRaises(RuntimeError): backend.shell_call("open")


class ExistingShellInstallTests(unittest.TestCase):
    def test_install_preserves_existing_island_and_is_idempotent(self):
        with tempfile.TemporaryDirectory(prefix="jarvis-plugin-config-") as directory:
            config_home = Path(directory)
            shell_config = config_home / "omarchy/shell.json"
            shell_config.parent.mkdir()
            original = {"version": 1, "plugins": [{"id": "omarchy-dynamic-island", "scale": 1.25}],
                        "bar": {"position": "top"}, "custom": "keep"}
            shell_config.write_text(json.dumps(original))
            result = install(config_home)
            updated = json.loads(shell_config.read_text())
            self.assertEqual(updated["plugins"][0], original["plugins"][0])
            self.assertEqual(updated["custom"], "keep")
            self.assertEqual(updated["plugins"][-1], {"id": "jarvis.widgets"})
            self.assertTrue((Path(result["backup"]) / "shell.json").exists())
            self.assertTrue((Path(result["plugin"]) / "Widgets.qml").exists())
            install(config_home)
            entries = json.loads(shell_config.read_text())["plugins"]
            self.assertEqual(sum(item["id"] == "jarvis.widgets" for item in entries), 1)


class WidgetAdapterTests(unittest.TestCase):
    @staticmethod
    async def inline_worker(function, *args, **kwargs):
        # Shell calls are mocked; no executor or external process is needed.
        return function(*args, **kwargs)

    def test_app_stage_dispatch_uses_a_specific_target(self):
        domain = WidgetsDomain()
        with patch("asyncio.to_thread", self.inline_worker), patch.object(
                backend, "shell_call", return_value={"ok": True, "status": "requested"}) as call:
            result = asyncio.run(domain._adapter_manage_app_stage("park", address="0x123"))
            self.assertEqual(result["status"], "requested")
            call.assert_called_once_with("desktop", {"action": "park", "address": "0x123"})
            with self.assertRaises(SkillError):
                asyncio.run(domain._adapter_manage_app_stage("park"))

    def test_native_cards_use_their_shell_routes(self):
        with patch("asyncio.to_thread", self.inline_worker), patch.object(
                backend, "shell_call", return_value={"ok": True, "mounted": True}) as call:
            result = asyncio.run(WidgetsDomain()._adapter_manage_canvas("audio"))
            self.assertTrue(result["mounted"])
            call.assert_called_once_with("showAudio")
            call.reset_mock()
            result = asyncio.run(WidgetsDomain()._adapter_manage_canvas("devices"))
            self.assertTrue(result["mounted"])
            call.assert_called_once_with("showDevices")

    def test_ipc_timeouts_are_reported_as_tool_failures(self):
        domain = WidgetsDomain()
        with patch("asyncio.to_thread", self.inline_worker), patch.object(backend, "shell_call", side_effect=subprocess.TimeoutExpired("omarchy-shell", 4)):
            with self.assertRaises(SkillError):
                asyncio.run(domain._adapter_manage_canvas("open"))

    def test_input_bar_preserves_attachments_when_canvas_is_available(self):
        from skills.skills import DesktopSkills
        registry = DesktopSkills.__new__(DesktopSkills)
        registry.test_bar = MagicMock()
        registry.test_bar.start.return_value = "http://127.0.0.1:12345/#test-token"
        registry._launch = AsyncMock()
        probe = MagicMock()
        probe.wait = AsyncMock(return_value=0)
        with patch.object(backend, "shell_call") as call, \
                patch("skills.skills.os.path.isfile", return_value=True), \
                patch("skills.skills.asyncio.create_subprocess_exec", AsyncMock(return_value=probe)):
            result = asyncio.run(registry._adapter_open_input_bar())
        call.assert_not_called()
        registry._launch.assert_awaited_once()
        self.assertTrue(registry._launch.call_args.args[1].endswith("overlay_client.py"))
        self.assertEqual(registry._launch.call_args.args[2], registry.test_bar.start.return_value)
        self.assertEqual(result["accepts"], ["text", "image", "audio", "pdf", "file"])

    def test_closing_input_also_closes_attachment_server_and_legacy_window(self):
        from skills.skills import DesktopSkills
        registry = DesktopSkills.__new__(DesktopSkills)
        registry.test_bar = MagicMock()
        registry.test_bar.close.return_value = True
        registry._adapter_list_windows = AsyncMock(return_value={"windows": [
            {"title": "JARVIS Input Bar", "class": "JarvisInputBar", "address": "0x123"}
        ]})
        registry._command = MagicMock(return_value="hyprctl")
        registry._run = AsyncMock()
        with patch("asyncio.to_thread", self.inline_worker), \
                patch.object(backend, "shell_call", return_value={"ok": True, "mode": "hidden"}):
            result = asyncio.run(registry._adapter_close_input_bar())
        registry.test_bar.close.assert_called_once()
        registry._run.assert_awaited_once()
        self.assertEqual(result["windows_closed"], 1)


if __name__ == "__main__": unittest.main()


def test_voice_service_discovers_the_native_session_without_display_env(monkeypatch):
    entry = '/usr/lib/jarvis-de/ui/JarvisDesktop.qml'
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        stdout = json.dumps([{'config_path': entry}]) if 'list' in command else '{"ok":true}'
        return subprocess.CompletedProcess(command, 0, stdout, '')

    monkeypatch.setattr(backend, 'theme_hud_entry', lambda: None)
    monkeypatch.setattr(backend.subprocess, 'run', run)
    assert backend.shell_call('status')['ok']
    assert commands[1][1:] == ['--path', entry, '--any-display', 'ipc', 'call', 'jarvis-hud-preview', 'status']


def test_choices_disambiguation_card_compiles_and_validates():
    from widgets.view_schema import describe
    example = describe()["native_cards"]["choices"]
    widget = backend.make_widget("choices", "Choose file", example, widget_id="disambig-1")
    assert widget["kind"] == "view"
    assert widget["id"] == "disambig-1"
    state = widget["data"]["state"]
    assert state["target_kind"] == "file"
    assert state["choice_count"] == 2
    assert state["selected_index"] == 0
    assert state["selected_id"] == ""
    assert state["selected_value"] == ""
    choices = [n for n in widget["data"]["layout"]["children"] if n["type"] == "choice"]
    assert [c["index"] for c in choices] == [1, 2]
    assert choices[0]["value"] == "/home/user/Documents/notes-final.md"
    validate_view(widget["data"])

    for bad_data in [
        {"items": []},
        {"items": [{"label": f"Item {i}"} for i in range(10)]},
        {"items": [{"label": "   "}]},
        {"items": [{"id": "dup", "label": "A"}, {"id": "dup", "label": "B"}]},
    ]:
        with pytest.raises(ValueError):
            backend.make_widget("choices", "Bad choices", bad_data)

    for bad_view in [
        {"layout": {"type": "choice", "index": 0, "label": "Zero", "prompt": "Pick"}},
        {"layout": {"type": "choice", "index": 10, "label": "Ten", "prompt": "Pick"}},
        {"layout": {"type": "column", "children": [
            {"type": "choice", "index": 1, "label": "One", "prompt": "Pick 1"},
            {"type": "choice", "index": 1, "label": "Dup", "prompt": "Pick 1b"},
        ]}},
    ]:
        with pytest.raises(ValueError):
            validate_view(bad_view)


def test_choices_manage_select_cli_dispatches_index_and_dismiss(monkeypatch):
    calls = []

    def fake_shell_call(method, payload=None):
        calls.append((method, payload))
        return {"ok": True, "id": "pick-1", "action": "select", "selected": {"index": 2}}

    monkeypatch.setattr(backend, "shell_call", fake_shell_call)
    assert backend.main(["manage", "pick-1", "select", "--index", "2", "--dismiss"]) == 0
    assert calls == [("manage", {"id": "pick-1", "action": "select", "index": 2, "dismiss": True})]
    assert backend.main(["manage", "pick-1", "select", "--index", "0"]) == 1


def test_zero_polling_and_motion_compliance_across_shell_surfaces():
    import re
    root = Path(__file__).resolve().parents[1]
    hud_preview = (root / "shell/HudPreview.qml").read_text()
    assert "stateFileView.reload()" not in hud_preview or "onFileChanged: reload()" in hud_preview
    assert "interval: 100" not in hud_preview
    assert "watchChanges: path !== \"\"" in hud_preview
    assert "Style.reduceMotion" in hud_preview
    assert "root.drafts = nextDrafts" in hud_preview

    scifi_panel = (root / "shell/SciFiPanel.qml").read_text()
    assert "textFormat: Text.PlainText" in scifi_panel

    shell_qml = (root / "shell/Shell.qml").read_text()
    assert "sh -c" not in shell_qml
    assert "interval: 200" not in shell_qml
    assert "watchChanges: path !== \"\"" in shell_qml
    assert "running: rootWin.visible && rootWin.activeVoice" in shell_qml

    wave_qml = (root / "shell/AcousticWaveform.qml").read_text()
    assert "running: true" not in wave_qml
    assert 'wave.voiceState === "listening" || wave.voiceState === "speaking"' in wave_qml
    assert "Style.duration(" in wave_qml

    reactor_qml = (root / "shell/ArcReactorCore.qml").read_text()
    assert "running: core.visible && core.animating" in reactor_qml
    assert "Style.duration(" in reactor_qml

    core_canvas_qml = (root / "shell/CoreCanvas.qml").read_text()
    assert "Style.duration(" in core_canvas_qml

    hologram_qml = (root / "shell/HologramCard.qml").read_text()
    assert "Style.duration(" in hologram_qml

    for name in ("AgentsStatusPanel.qml", "MemoryPanel.qml"):
        content = (root / "shell" / name).read_text()
        assert "running: true" not in content

    shell_cfg = json.loads((root / "config/omarchy/shell.json").read_text())
    assert "omarchy-ai.orbit" in shell_cfg["disabledPlugins"]
    assert any(p.get("id") == "jarvis.widgets" for p in shell_cfg["plugins"])
    island = next(p for p in shell_cfg["plugins"] if p.get("id") == "omarchy-dynamic-island")
    assert island["mic"] is False
    assert isinstance(island["reducedMotion"], bool)
    for rel in ("CoreCanvas.qml", "ArcReactorCore.qml", "HologramCard.qml", "AcousticWaveform.qml"):
        src = (root / "shell" / rel).read_text()
        assert not re.search(r"\bduration\s*:\s*\d+", src), f"Bare numeric duration found in {rel}"
