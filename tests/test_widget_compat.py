import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from widgets import backend
from widgets.view_schema import validate_view


def test_workspace_uses_legacy_view_only_on_omarchy_fallback():
    widget = backend.make_widget("workspace", "Project", {
        "revision": 2, "brief": "A brief",
        "files": [{"path": "/tmp/notes.md", "detail": "Notes"}],
        "tasks": [{"id": "review", "label": "Review", "done": True}],
    }, widget_id="project", presentation="canvas", expires_seconds=0)
    with patch.object(backend, "theme_hud_entry", return_value=None) as theme, \
            patch.object(backend, "running_standalone_entry", return_value=None), \
            patch.object(backend, "session_dir"), \
            patch.object(backend.shutil, "which", side_effect=lambda name: name), \
            patch.object(backend.subprocess, "run", return_value=subprocess.CompletedProcess(
                [], 0, '{"ok":true}', ""
            )) as run:
        backend.shell_call("present", widget)
        command = run.call_args.args[0]
        assert command[:-1] == ["omarchy-shell", "jarvis-canvas", "present"]
        fallback = json.loads(command[-1])
        view = validate_view(fallback["data"])
        assert fallback == dict(widget, kind="view", data=view)
        assert view["state"] == {"review": True}
        brief, files, tasks = [node["children"] for node in view["layout"]["children"]]
        assert brief[1]["children"][0]["text"] == "A brief"
        assert files[1]["children"] == [
            {"type": "button", "label": "/tmp/notes.md", "prompt": "Open the workspace file: /tmp/notes.md"},
            {"type": "text", "text": "Notes", "tone": "muted"},
        ]
        assert tasks[1]["children"][0]["bind"] == "review"

        theme.return_value = Path("/mock/ui/JarvisTheme.qml")
        backend.shell_call("present", widget)
        command = run.call_args.args[0]
        assert command[-3:-1] == ["jarvis-hud-preview", "present"]
        assert json.loads(command[-1]) == widget
