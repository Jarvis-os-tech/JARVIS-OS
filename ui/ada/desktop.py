#!/usr/bin/env python3
"""Host Ada's project workspace on an interactive Wayland desktop layer."""
from __future__ import annotations

from http.cookies import SimpleCookie
import json
import mimetypes
import os
from pathlib import Path
import secrets
import sys
import threading
import time
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "frontend"
os.umask(0o077)
os.environ["JARVIS_PROJECTS_DIR"] = str(Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local/share")) / "jarvis/ada-projects")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.projects import store, WorkspaceError
from backend.config import (
    read_settings, save_settings, read_overrides, save_overrides,
    save_voice, VoiceSelection, save_audio_preferences, AudioPreferencesUpdate,
    save_instructions, InstructionsUpdate, reset_instructions,
    VOICES, read_default_instructions, preferences_configured, api_key
)

TOKEN = secrets.token_urlsafe(32)

# Shared in-memory queue/record for VoiceUIAction
PENDING_VOICE_ACTIONS: list[dict] = []


class DesktopRequest:
    pass


from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class DesktopRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, body, mime="application/json", code=200, *, cookie=False):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Cookie, X-Jarvis-Token")
        self.send_header("Content-Security-Policy", "default-src 'self' 'unsafe-inline' blob: data:; script-src 'self' 'unsafe-inline' blob:; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; connect-src 'self' ws: wss:; frame-ancestors 'none'; object-src 'none'")
        if cookie:
            self.send_header("Set-Cookie", f"session={TOKEN}; HttpOnly; SameSite=Strict; Path=/")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Cookie, X-Jarvis-Token")
        self.end_headers()

    def _allowed_hosts(self):
        port = self.server.server_port
        return {
            self.server.host,
            f"localhost:{port}",
            f"[::1]:{port}",
            "127.0.0.1",
            "localhost",
            "::1",
            "[::1]",
        }

    def _allowed_origins(self):
        port = self.server.server_port
        return {
            None,
            f"http://{self.server.host}",
            f"http://localhost:{port}",
            f"http://[::1]:{port}",
        }

    def _is_loopback_host(self):
        client_ip = self.client_address[0]
        return client_ip in {"127.0.0.1", "::1", "localhost"} and self.headers.get("Host") in self._allowed_hosts()

    def _has_valid_token(self):
        header_token = self.headers.get("X-Jarvis-Token")
        if header_token and secrets.compare_digest(header_token, TOKEN):
            return True
        cookie_header = self.headers.get("Cookie", "")
        if cookie_header:
            cookie = SimpleCookie()
            try:
                cookie.load(cookie_header)
            except Exception:
                cookie = None
            if cookie and "session" in cookie:
                return secrets.compare_digest(cookie["session"].value, TOKEN)
        return False

    def authorised(self):
        return (
            self._is_loopback_host()
            and self._has_valid_token()
            and self.headers.get("Origin") in self._allowed_origins()
        )

    def do_GET(self):
        url = urlsplit(self.path)
        if not self._is_loopback_host():
            return self.reply({"detail": "Invalid host"}, code=403)
        # Serve main index with session cookie on root or token path
        if url.path in {"/", f"/{TOKEN}"}:
            index_path = ASSETS / "index.html"
            if index_path.is_file():
                html = index_path.read_text(encoding="utf-8").replace('defer src="/static/boot.js?v=12"', 'type="module" src="/desktop.js"')
                return self.reply(html.encode("utf-8"), "text/html; charset=utf-8", cookie=True)
            return self.reply(b"<h1>JARVIS Desktop HUD Assets Not Found</h1>", "text/html", code=404)

        if url.path == "/desktop.js":
            try:
                desktop_js = (ROOT / "desktop.js").read_bytes()
            except OSError as exc:
                return self.reply({"detail": str(exc)}, code=404)
            return self.reply(desktop_js, "text/javascript; charset=utf-8")

        if url.path.startswith("/static/"):
            rel = url.path[8:].lstrip("/")
            path = (ASSETS / rel).resolve()
            if path.is_relative_to(ASSETS) and path.is_file():
                mime = mimetypes.guess_type(path)[0]
                if path.suffix == ".js":
                    mime = "text/javascript"
                elif path.suffix == ".css":
                    mime = "text/css"
                elif path.suffix == ".svg":
                    mime = "image/svg+xml"
                return self.reply(path.read_bytes(), mime or "application/octet-stream")
            return self.reply({"detail": "Resource not found."}, code=404)

        if not self.authorised():
            return self.reply({"detail": "Unauthorized"}, code=403)

        try:
            if url.path == "/api/workspace":
                return self.reply(store.snapshot())

            if url.path == "/api/voice":
                state = {}
                runtime_dir = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
                try:
                    state_file = runtime_dir / "jarvis/state.json"
                    if state_file.is_file():
                        state = json.loads(state_file.read_text(encoding="utf-8"))
                        if time.time() - float(state.get("status_written_at", 0)) > 8:
                            state = {}
                except (OSError, ValueError, TypeError):
                    state = {}
                return self.reply({
                    "connected": state.get("connected") is True or state.get("state") in {"idle", "listening", "thinking", "speaking"},
                    "state": state.get("state", "idle"),
                    "energy": float(state.get("microphone_rms", 0.0) or 0.0),
                    "voice": state.get("voice", "Zephyr"),
                    "volume": float(state.get("volume", 0.75)),
                    "muted": bool(state.get("muted", False))
                })

            if url.path == "/api/settings":
                try:
                    s = read_settings()
                    return self.reply({
                        "settings": s.model_dump(),
                        "configured": bool(api_key()),
                        "preferences_configured": preferences_configured(),
                        "voices": VOICES,
                        "default_instructions": read_default_instructions()
                    })
                except Exception as exc:
                    return self.reply({"detail": str(exc)}, code=422)

            if url.path.startswith("/api/projects/") and url.path.endswith("/file"):
                parts = url.path.split("/")
                project_id = parts[3]
                rel_path = parse_qs(url.query)["path"][0]
                path = store.path(project_id, rel_path)
                mime = mimetypes.guess_type(path)[0]
                return self.reply(path.read_bytes(), mime if mime in {"image/png", "image/jpeg", "image/webp"} else "application/octet-stream")

            return self.reply({"detail": "Resource not found."}, code=404)
        except (WorkspaceError, OSError, ValueError, KeyError, IndexError) as exc:
            self.reply({"detail": str(exc)}, code=404)

    def do_POST(self):
        if not self.authorised():
            return self.reply({"detail": "Unauthorized"}, code=403)

        url = urlsplit(self.path)
        try:
            size = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(size)) if size > 0 else {}
        except Exception as exc:
            return self.reply({"detail": f"Invalid JSON payload: {exc}"}, code=400)

        try:
            if url.path == "/api/workspace/action":
                name = body.get("name")
                args = body.get("arguments", {})
                return self.reply({"result": store.execute(name, args)})

            if url.path == "/api/voice/action":
                # Direct voice UI action execution
                action = body.get("action")
                value = body.get("value")
                amount = body.get("amount")
                PENDING_VOICE_ACTIONS.append({
                    "id": secrets.token_hex(8),
                    "action": action,
                    "value": value,
                    "amount": amount,
                    "timestamp": time.time()
                })
                # If it's a volume or voice setting, apply immediately to settings
                if action == "set_volume" and amount is not None:
                    save_audio_preferences(AudioPreferencesUpdate(volume=float(amount) / 100.0))
                elif action == "set_motion" and value in {"reduced", "full"}:
                    save_audio_preferences(AudioPreferencesUpdate(reduced_motion=(value == "reduced")))
                elif action == "set_voice" and value in VOICES:
                    save_voice(VoiceSelection(voice=value))

                return self.reply({"ok": True, "action": action, "value": value, "amount": amount})

            if url.path == "/api/settings/voice":
                voice = body.get("voice")
                if voice not in VOICES:
                    return self.reply({"detail": "Unsupported voice"}, code=422)
                save_voice(VoiceSelection(voice=voice))
                return self.reply({"settings": read_settings().model_dump(), "voices": VOICES})

            if url.path == "/api/settings/instructions/reset":
                reset_instructions()
                return self.reply({"settings": read_settings().model_dump(), "default": read_default_instructions()})

            if url.path == "/api/settings/instructions/default":
                inst = body.get("instructions", "")
                save_instructions(InstructionsUpdate(instructions=inst), make_default=True)
                return self.reply({"settings": read_settings().model_dump()})

            if url.path == "/api/exit":
                return self.reply({"ok": True, "kiosk": False})

            return self.reply({"detail": "Endpoint not found"}, code=404)
        except Exception as exc:
            return self.reply({"detail": str(exc)}, code=422)

    def do_PATCH(self):
        if not self.authorised():
            return self.reply({"detail": "Unauthorized"}, code=403)

        url = urlsplit(self.path)
        try:
            size = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(size)) if size > 0 else {}
        except Exception as exc:
            return self.reply({"detail": f"Invalid JSON payload: {exc}"}, code=400)

        try:
            if url.path == "/api/settings/audio":
                vol = float(body["volume"]) if "volume" in body and body["volume"] is not None else None
                red = bool(body["reduced_motion"]) if "reduced_motion" in body and body["reduced_motion"] is not None else None
                pause = bool(body.get("pause_microphone_while_speaking", False))
                save_audio_preferences(AudioPreferencesUpdate(volume=vol, reduced_motion=red, pause_microphone_while_speaking=pause))
                s = read_settings()
                return self.reply({
                    "settings": s.model_dump(),
                    "voices": VOICES,
                    "default_instructions": read_default_instructions()
                })

            if url.path == "/api/settings/voice":
                voice = body.get("voice")
                if voice not in VOICES:
                    return self.reply({"detail": "Unsupported voice"}, code=422)
                save_voice(VoiceSelection(voice=voice))
                return self.reply({"settings": read_settings().model_dump(), "voices": VOICES})

            if url.path == "/api/settings/instructions":
                inst = body.get("instructions", "")
                save_instructions(InstructionsUpdate(instructions=inst))
                return self.reply({"settings": read_settings().model_dump()})

            return self.reply({"detail": "Endpoint not found"}, code=404)
        except Exception as exc:
            return self.reply({"detail": str(exc)}, code=422)


def sample():
    if store.projects():
        return
    project = store.execute("create_project", {
        "name": "JARVIS Workspace · Core",
        "brief": "Integrated Voice, Spatial 3D CAD, Inventory & Dynamic Constellation HUD for Omarchy OS.",
        "auto_demo_image": False
    })
    pid = project["id"]
    store.execute("write_file", {
        "project_id": pid,
        "path": "Plan.md",
        "content": "# JARVIS Core Spatial Architecture\n\n## 1. Web Audio API Pipeline\nIntegrate microphone speech capture and high-fidelity speech playback with zero-latency streaming worklets.\n\n## 2. WebGL createVoiceCore\nRender geodesic Arc Reactor core with bloom pass and dynamic particle halo; Canvas fallback on context loss.\n\n## 3. VoiceUIAction Engine\nProcess vocal commands for volume, reduced motion, voice selection, and constellation UI panel toggles."
    })
    for kind, title in [
        ("idea", "PipeWire PCM Echo Cancellation"),
        ("idea", "WebGL Core with Canvas Fallback"),
        ("decision", "Omarchy OS Hyprland Spatial Placement"),
        ("task", "Mount Constellation Widget Engine"),
        ("task", "Verify VoiceUIAction Command Routing")
    ]:
        store.execute("save_card", {"project_id": pid, "kind": kind, "title": title})


def main():
    if os.getenv("JARVIS_ADA_SAMPLE", "1") == "1":
        try:
            sample()
        except Exception as e:
            print(f"[Warning] Failed to seed sample project: {e}", file=sys.stderr)

    port = int(os.getenv("JARVIS_ADA_PORT", "8899"))
    server = ThreadingHTTPServer(("127.0.0.1", port), DesktopRequestHandler)
    server.host = f"127.0.0.1:{server.server_port}"
    print(f"============================================================")
    print(f"  JARVIS ADA Desktop & Widget Engine Active")
    print(f"  URL: http://{server.host}/{TOKEN}")
    print(f"  Directory: {ROOT}")
    print(f"============================================================")

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    has_display = bool(os.getenv("WAYLAND_DISPLAY") or os.getenv("DISPLAY"))
    serve_only = "--serve-only" in sys.argv or "--headless" in sys.argv

    if not has_display or serve_only:
        print("[JARVIS] Running in serve-only headless mode.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down server.")
            server.shutdown()
        return

    try:
        import gi
        gi.require_version("Gtk", "3.0")
        gi.require_version("GtkLayerShell", "0.1")
        gi.require_version("WebKit2", "4.1")
        from gi.repository import Gtk, GtkLayerShell, WebKit2

        window = Gtk.Window()
        GtkLayerShell.init_for_window(window)
        GtkLayerShell.set_namespace(window, "jarvis-ada")
        GtkLayerShell.set_layer(window, GtkLayerShell.Layer.BOTTOM)
        GtkLayerShell.set_keyboard_mode(window, GtkLayerShell.KeyboardMode.ON_DEMAND)
        for edge in (GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT, GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM):
            GtkLayerShell.set_anchor(window, edge, True)
        web = WebKit2.WebView.new_with_context(WebKit2.WebContext.new_ephemeral())
        window.add(web)
        web.load_uri(f"http://{server.host}/{TOKEN}")
        window.connect("destroy", Gtk.main_quit)
        window.show_all()
        Gtk.main()
    except Exception as e:
        print(f"[JARVIS Gtk Warning] Desktop GUI layer skipped: {e}. Keeping HTTP server active.", file=sys.stderr)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            server.shutdown()


if __name__ == "__main__":
    main()
