"""Typed widget controller for the existing Omarchy shell; never launches a GUI."""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
try:
    from widgets.view_schema import validate_view
    from widgets.native_cards import view as native_view, objects, line_chart
    from widgets.workspace import compile_workspace, legacy_view
except ModuleNotFoundError:
    from native_cards import view as native_view, objects, line_chart
    from view_schema import validate_view  # Installed shell's short-lived input helper.
    from workspace import compile_workspace, legacy_view

KINDS = {"workspace", "metric", "list", "actions", "form", "choices", "view", "text", "qr", "image", "pip", "table", "chart", "progress", "3d"}
FIELDS = {
    "workspace": {"brief", "files", "ideas", "plan", "tasks", "revision", "reopen"},
    "metric": {"value", "unit", "detail"}, "list": {"items"},
    "actions": {"buttons"}, "form": {"fields", "submit"},
    "choices": {"prompt", "target_kind", "items", "cancel_label"},
    "text": {"text", "actions"}, "qr": {"content"}, "image": {"path", "caption", "actions"},
    "pip": {"path", "caption", "actions"}, "table": {"columns", "rows"},
    "chart": {"labels", "values", "unit", "mode", "points"},
    "progress": {"text", "value", "maximum", "actions"},
    "view": {"state", "computed", "layout", "width"},
    "3d": {"script", "caption", "actions"},
}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
VIDEO_SUFFIXES = {".mp4", ".webm", ".mkv"}


def compact(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def runtime_dir():
    root = Path(os.environ.get("XDG_RUNTIME_DIR") or os.environ.get("XDG_STATE_HOME")
                or Path.home() / ".local/state") / "jarvis/widgets"
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = root.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("Widget runtime must be private and owned by this user")
    return root


def text(value, maximum=8000):
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError(f"Expected text of at most {maximum} characters")
    return value


def finite_number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Expected a finite number")
    return value


def validate(kind, data):
    if kind not in KINDS or not isinstance(data, dict):
        raise ValueError("Unsupported widget kind or data")
    if set(data) - FIELDS[kind]:
        raise ValueError("Unexpected widget fields")
    if len(compact(data).encode()) > 48000:
        raise ValueError("Widget data exceeds 48 KiB")
    if kind == "workspace":
        return compile_workspace(data)
    if kind in {"metric", "list", "actions", "form", "choices"}:
        return native_view(kind, data)
    if kind == "view":
        return validate_view(data)
    if kind == "text":
        out = {"text": text(data.get("text", ""))}
        if "actions" in data and isinstance(data["actions"], list):
            out["actions"] = [
                {
                    "label": text(item.get("label", ""), 40),
                    "action": text(item.get("action", ""), 40),
                    "prompt": text(item.get("prompt", item.get("action", "")), 100),
                    "primary": bool(item.get("primary", False))
                }
                for item in data["actions"] if isinstance(item, dict)
            ]
        return out
    if kind == "qr":
        return {"content": text(data.get("content"), 2000)}
    if kind in ("image", "pip"):
        path = Path(text(data.get("path"), 4096)).expanduser().resolve(strict=True)
        allowed = IMAGE_SUFFIXES | (VIDEO_SUFFIXES if kind == "pip" else set())
        if not path.is_file() or path.suffix.lower() not in allowed:
            raise ValueError("Choose a local supported image or video file")
        if path.stat().st_size > 128 * 1024 * 1024:
            raise ValueError("Media exceeds the 128 MiB widget limit")
        out = {
            "source": path.as_uri(),
            "video": path.suffix.lower() in VIDEO_SUFFIXES,
            "caption": text(data.get("caption", ""), 1000)
        }
        if "actions" in data and isinstance(data["actions"], list):
            out["actions"] = [
                {
                    "label": text(item.get("label", ""), 40),
                    "action": text(item.get("action", ""), 40),
                    "prompt": text(item.get("prompt", item.get("action", "")), 100),
                    "primary": bool(item.get("primary", False))
                }
                for item in data["actions"] if isinstance(item, dict)
            ]
        return out
    if kind == "table":
        columns, rows = data.get("columns"), data.get("rows")
        if not isinstance(columns, list) or not 1 <= len(columns) <= 8:
            raise ValueError("Tables need 1–8 columns")
        columns = [text(item, 100) for item in columns]
        if not isinstance(rows, list) or len(rows) > 100:
            raise ValueError("Tables support at most 100 rows per card")
        validated = []
        for row in rows:
            if not isinstance(row, list) or len(row) != len(columns):
                raise ValueError("Every row must match the columns")
            validated.append([text(str(item), 500) if type(item) in (str, int, float, bool) else
                              (_ for _ in ()).throw(ValueError("Invalid table cell")) for item in row])
        return {"columns": columns, "rows": validated}
    if kind == "chart":
        if "points" in data:
            if "labels" in data or "values" in data:
                raise ValueError("Choose points or labels/values")
            points = objects(data["points"], 20, {"label", "value"})
            data = {**data, "labels": [p.get("label") for p in points], "values": [p.get("value") for p in points]}
        mode = data.get("mode", "bar")
        if mode not in {"bar", "line"}:
            raise ValueError("Chart mode must be bar or line")
        labels, values = data.get("labels"), data.get("values")
        if not isinstance(labels, list) or not isinstance(values, list) or not 1 <= len(labels) <= 20 or len(labels) != len(values):
            raise ValueError("Charts need 1–20 matching labels and values")
        values = [finite_number(value) for value in values]
        if mode == "bar" and any(value < 0 for value in values):
            raise ValueError("This bar-chart component supports non-negative values")
        result = {"labels": [text(label, 80) for label in labels], "values": values,
                  "unit": text(data.get("unit", ""), 40)}
        if mode == "line":
            return line_chart(result)
        return result
    if kind == "3d":
        script_content = text(data.get("script", ""), 48000)
        if not script_content.strip():
            raise ValueError("3D widget requires a Three.js script")
        try:
            from widgets.three_compiler import compile_3d
        except ModuleNotFoundError:
            from three_compiler import compile_3d
        compiled = compile_3d(script_content, title="3D Model")
        if not compiled.get("valid", False):
            raise ValueError(f"3D script error: {compiled.get('error', 'Compilation failed')}")

        actions = [
            {"label": "Inspect 3D", "action": f"inspect_3d:{compiled['model_path']}", "primary": True},
            {"label": "Export GLB", "action": f"export_glb:{compiled['model_path']}", "primary": False}
        ]
        if "actions" in data and isinstance(data["actions"], list):
            actions.extend(data["actions"])

        return {
            "source": compiled["source"],
            "model_path": compiled["model_path"],
            "script_path": compiled["script_path"],
            "caption": text(data.get("caption", ""), 1000),
            "dimensions": compiled["dimensions"],
            "triangles": compiled["triangles"],
            "vertices": compiled["vertices"],
            "actions": actions
        }
    result = {"text": text(data.get("text", ""), 1000)}
    if "actions" in data and isinstance(data["actions"], list):
        result["actions"] = [
            {
                "label": text(item.get("label", ""), 40),
                "action": text(item.get("action", ""), 40),
                "prompt": text(item.get("prompt", item.get("action", "")), 100),
                "primary": bool(item.get("primary", False))
            }
            for item in data["actions"] if isinstance(item, dict)
        ]
    if "value" in data:
        maximum = finite_number(data.get("maximum", 100))
        value = finite_number(data["value"])
        if maximum <= 0 or not 0 <= value <= maximum:
            raise ValueError("Progress must be within a positive maximum")
        result.update(value=value, maximum=maximum)
    elif "maximum" in data:
        raise ValueError("A maximum requires measured progress")
    return result


def make_widget(kind, title, data, *, widget_id="", presentation="floating", expires_seconds=120, revision=0, reopen=False):
    if type(revision) is not int or not 0 <= revision <= 2**53 - 1 or type(reopen) is not bool:
        raise ValueError("Invalid revision or reopen flag")
    if presentation not in ("canvas", "floating"):
        raise ValueError("Presentation must be canvas or floating")
    if not isinstance(expires_seconds, int) or not 0 <= expires_seconds <= 86400:
        raise ValueError("Expiry must be 0–86400 seconds; zero retains the card")
    widget_id = widget_id or "widget-" + uuid.uuid4().hex[:16]
    if widget_id.startswith('jtask_'):
        raise ValueError('Task card IDs are reserved for task events')
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", widget_id):
        raise ValueError("Invalid widget ID")
    clean = validate(kind, data)
    if kind in {"metric", "list", "actions", "form", "choices"} or (kind == "chart" and data.get("mode") == "line"):
        kind = "view"
    if kind == "qr":
        binary = shutil.which("qrencode")
        if not binary:
            raise ValueError("QR rendering requires qrencode")
        # Input goes through stdin; neither shell expansion nor secret argv.
        descriptor, filename = tempfile.mkstemp(prefix="qr-", suffix=".png", dir=runtime_dir())
        os.close(descriptor)
        try:
            subprocess.run([binary, "-t", "PNG", "-l", "M", "-s", "8", "-o", filename],
                           input=clean["content"], text=True, check=True,
                           capture_output=True, timeout=3)
        except Exception:
            Path(filename).unlink(missing_ok=True)
            raise
        clean = {"source": Path(filename).as_uri()}
    return {"id": widget_id, "kind": kind, "title": text(title, 160), "data": clean,
            "floating": presentation == "floating", "expires_seconds": expires_seconds, "revision": revision, "reopen": reopen}


def session_dir():
    root = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state") / "jarvis/widget-session"
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = root.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise ValueError("Widget session directory must be owned by this user and not a symlink")
    if info.st_mode & 0o077:
        root.chmod(0o700)
    return root


def theme_hud_entry():
    standalone = os.environ.get("JARVIS_DE_HUD_ENTRY")
    if standalone:
        entry = Path(standalone)
        return entry if entry.is_file() else None
    state = Path.home() / ".local/state/omarchy/current/theme.name"
    try:
        if state.read_text().strip().lower() != "jarvis":
            return None
        launcher = (Path.home() / ".local/bin/jarvis-shell").resolve(strict=True)
        entries = (launcher.with_name("Theme.qml"), launcher.with_name("JarvisTheme.qml"),
                   launcher.parents[1] / "JarvisTheme.qml")
        if launcher.parent.name == "shell":
            entries = (launcher.parents[1] / "shell.qml", *entries)
        return next((entry for entry in entries if entry.is_file()), None)
    except OSError:
        return None


def running_standalone_entry():
    root = Path(__file__).resolve().parents[1]
    entries = {
        root / "shell/Desktop.qml",
        root / "ui/JarvisDesktop.qml",
        Path("/usr/lib/jarvis-de/shell/Desktop.qml"),
        Path("/usr/lib/jarvis-de/ui/JarvisDesktop.qml"),
    }
    try:
        result = subprocess.run(
            [shutil.which("qs") or "qs", "list", "--all", "--any-display", "--json"],
            capture_output=True, text=True, check=True, timeout=2,
        )
        running = json.loads(result.stdout)
        if not isinstance(running, list):
            return None
        matches = [record.get("config_path") for record in running if isinstance(record, dict)]
        selected = [Path(path) for path in matches if isinstance(path, str) and Path(path) in entries]
        return selected[0] if len(selected) == 1 else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def shell_call(method, payload=None):
    entry = theme_hud_entry()
    discovered = entry is None
    if discovered:
        entry = running_standalone_entry()
    if entry is not None:
        session_dir()
        command = [shutil.which("qs") or "qs", "--path", str(entry)]
        if discovered:
            command.append("--any-display")
        command.extend(["ipc", "call", "jarvis-hud-preview", method])
    else:
        command = [shutil.which("omarchy-shell") or "omarchy-shell", "jarvis-canvas", method]
        if method == "present" and isinstance(payload, dict) and payload.get("kind") == "workspace":
            payload = dict(payload, kind="view", data=legacy_view(payload["data"]))
    if payload is not None:
        command.append(compact(payload) if isinstance(payload, dict) else str(payload))
    process = subprocess.run(command, capture_output=True, text=True, timeout=4)
    if process.returncode:
        raise RuntimeError(process.stderr.strip() or "The selected JARVIS widget shell is unavailable")
    try:
        result = json.loads(process.stdout.strip())
    except ValueError:
        raise RuntimeError("The widget shell did not acknowledge the request") from None
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise RuntimeError(str(result.get("error", "Widget request rejected")) if isinstance(result, dict) else "Invalid widget receipt")
    return result


async def voice_request(line, *, timeout):
    runtime = os.environ.get("XDG_RUNTIME_DIR") or os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local/state")
    async with asyncio.timeout(timeout):
        reader, writer = await asyncio.open_unix_connection(str(Path(runtime) / "jarvis/control.sock"), limit=262144)
        try:
            writer.write((line + "\n").encode())
            await writer.drain()
            return json.loads(await reader.readline())
        finally:
            writer.close()
            await writer.wait_closed()


async def send_text(message):
    message = " ".join(text(message, 16000).split())
    if not message:
        raise ValueError("Enter a request first")
    result = await voice_request("send " + message, timeout=2)
    if not isinstance(result, dict) or result.get("status") != "sent":
        raise RuntimeError("Voice session did not accept the request")
    return {"ok": True, "status": "sent"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("open", "close", "input", "clear", "clearAll", "status"):
        sub.add_parser(name)
    show = sub.add_parser("show")
    show.add_argument("kind", choices=sorted(KINDS))
    show.add_argument("--title", default="JARVIS")
    data_input = show.add_mutually_exclusive_group(required=True)
    data_input.add_argument("--data", help="JSON data")
    data_input.add_argument("--data-file", type=Path, help="Read private JSON data without placing it in process arguments")
    show.add_argument("--id", default="")
    show.add_argument("--floating", action="store_true", help="Default: float over desktop")
    show.add_argument("--canvas", action="store_true", help="Group with other canvas cards")
    show.add_argument("--expires", type=int, default=120)
    show.add_argument("--revision", type=int, default=0)
    show.add_argument("--reopen", action="store_true")
    manage = sub.add_parser("manage")
    manage.add_argument("id")
    manage.add_argument("action", choices=("dismiss", "pin", "unpin", "float", "canvas", "select"))
    manage.add_argument("--index", type=int, help="1-based choice index for action=select")
    manage.add_argument("--dismiss", action="store_true", help="Dismiss widget after selecting a choice")
    approval = sub.add_parser("approval")
    approval.add_argument("id")
    approval.add_argument("decision", choices=("approve", "cancel"))
    send = sub.add_parser("send")
    send.add_argument("message")
    args = parser.parse_args(argv)
    try:
        if args.command == "send":
            result = asyncio.run(send_text(args.message))
        elif args.command == "approval":
            result = asyncio.run(voice_request(compact({
                "command": "resolve_approval", "id": args.id, "approve": args.decision == "approve",
            }), timeout=30))
            if not isinstance(result, dict) or result.get("ok") is not True:
                raise RuntimeError("The action could not be resolved. Check whether it is still pending.")
        elif args.command == "show":
            if args.data_file and args.data_file.stat().st_size > 48000:
                raise ValueError("Widget data exceeds 48 KiB")
            data = json.loads(args.data_file.read_text() if args.data_file else args.data)
            widget = make_widget(args.kind, args.title, data, widget_id=args.id,
                                 presentation="canvas" if args.canvas else "floating", expires_seconds=args.expires, revision=args.revision, reopen=args.reopen)
            result = shell_call("present", widget)
        elif args.command == "manage":
            payload = {"id": args.id, "action": args.action}
            if args.action == "select":
                if args.index is None or not 1 <= args.index <= 9:
                    raise ValueError("Selecting a choice requires --index between 1 and 9")
                payload["index"] = args.index
                if args.dismiss:
                    payload["dismiss"] = True
            result = shell_call("manage", payload)
        else:
            result = shell_call(args.command)
        print(compact(result))
        return 0
    except (OSError, ValueError, RuntimeError, TimeoutError, subprocess.SubprocessError) as error:
        print(compact({"ok": False, "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
