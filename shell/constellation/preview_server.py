#!/usr/bin/env python3
"""JARVIS OS Constellation HUD Preview Server.

Serves the standalone Constellation HUD on http://127.0.0.1:8765.
Can be viewed in any web browser, Hyprland webview overlay, or Electron wrapper.
"""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
import sys
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

DIRECTORY = Path(__file__).resolve().parent

class JarvisHUDHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIRECTORY), **kwargs)

    def end_headers(self):
        # Enable CORS and disable aggressive caching for local development
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def translate_path(self, path):
        # Map /static/* directly into directory root
        url = urlsplit(path)
        if url.path.startswith("/static/"):
            rel = url.path[8:].lstrip("/")
            return str(DIRECTORY / rel)
        return super().translate_path(path)

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == "/api/voice":
            state = {}
            runtime_dir = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
            try:
                state_file = runtime_dir / "jarvis/state.json"
                if state_file.is_file():
                    state = json.loads(state_file.read_text(encoding="utf-8"))
                    if time.time() - float(state.get("status_written_at", 0)) > 8:
                        state = {}
            except Exception:
                state = {}
            data = json.dumps({
                "connected": state.get("connected") is True or state.get("state") in {"idle", "listening", "thinking", "speaking"},
                "state": state.get("state", "idle"),
                "energy": float(state.get("microphone_rms", 0.0) or 0.0),
                "voice": state.get("voice", "Zephyr"),
                "volume": float(state.get("volume", 0.75)),
                "muted": bool(state.get("muted", False))
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if url.path == "/api/settings":
            data = json.dumps({
                "settings": {
                    "model": "gemini-3.8-live",
                    "voice": "Zephyr",
                    "volume": 0.75,
                    "reduced_motion": False
                },
                "configured": True,
                "voices": {"Zephyr": "Bright", "Puck": "Upbeat", "Charon": "Informative"}
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        super().do_GET()

    def do_POST(self):
        url = urlsplit(self.path)
        if url.path in {"/api/voice/action", "/api/workspace/action"}:
            size = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(size)) if size > 0 else {}
            data = json.dumps({"ok": True, "result": body}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_response(404)
        self.end_headers()

def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8899
    server_address = ("127.0.0.1", port)
    httpd = ThreadingHTTPServer(server_address, JarvisHUDHandler)
    print(f"============================================================")
    print(f"  JARVIS OS Constellation HUD Preview Server Active")
    print(f"  URL: http://127.0.0.1:{port}/")
    print(f"  Directory: {DIRECTORY}")
    print(f"============================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping HUD server.")
        httpd.server_close()

if __name__ == "__main__":
    main()
