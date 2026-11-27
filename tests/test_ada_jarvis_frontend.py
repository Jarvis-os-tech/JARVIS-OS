"""Tests for the Ada Jarvis frontend interface and widget engine in JARVIS OS."""

import json
from pathlib import Path
import subprocess
import time
import urllib.request
import urllib.error
import threading
import sys
import os
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ADA_DIR = REPO_ROOT / "shell" / "ada"
FRONTEND_DIR = ADA_DIR / "frontend"


def test_complete_frontend_assets_present():
    """Verify all core frontend stylesheets, scripts, audio worklets, and vendor modules exist."""
    assert FRONTEND_DIR.is_dir(), "Frontend directory must exist"
    
    # Stylesheets
    required_css = [
        "style.css", "workspace.css", "constellation.css",
        "inventory.css", "cad.css", "printing.css", "gestures.css"
    ]
    for css in required_css:
        assert (FRONTEND_DIR / css).is_file(), f"Missing stylesheet: {css}"

    # Visualizer & Orb scripts
    assert (FRONTEND_DIR / "voice-core.js").is_file(), "voice-core.js missing"
    assert (FRONTEND_DIR / "orb.js").is_file(), "orb.js missing"
    assert (FRONTEND_DIR / "orb-fallback.js").is_file(), "orb-fallback.js missing"

    # Audio Engine & Worklets (Web Audio API)
    audio_dir = FRONTEND_DIR / "audio"
    assert audio_dir.is_dir(), "audio directory missing"
    assert (audio_dir / "engine.js").is_file(), "audio/engine.js missing"
    assert (audio_dir / "capture-worklet.js").is_file(), "audio/capture-worklet.js missing"
    assert (audio_dir / "playback-worklet.js").is_file(), "audio/playback-worklet.js missing"
    assert (audio_dir / "pcm.js").is_file(), "audio/pcm.js missing"

    # Workspace & Widgets
    assert (FRONTEND_DIR / "workspace.js").is_file(), "workspace.js missing"
    assert (FRONTEND_DIR / "project-layout.js").is_file(), "project-layout.js missing"
    assert (FRONTEND_DIR / "document-view.js").is_file(), "document-view.js missing"
    assert (FRONTEND_DIR / "cad.js").is_file(), "cad.js missing"
    assert (FRONTEND_DIR / "cad-viewer.js").is_file(), "cad-viewer.js missing"
    assert (FRONTEND_DIR / "inventory.js").is_file(), "inventory.js missing"
    assert (FRONTEND_DIR / "printing.js").is_file(), "printing.js missing"
    assert (FRONTEND_DIR / "gestures.js").is_file(), "gestures.js missing"

    # Three.js vendor library
    three_module = FRONTEND_DIR / "vendor" / "three" / "build" / "three.module.js"
    assert three_module.is_file(), "three.module.js missing"
    assert three_module.stat().st_size > 100_000, "three.module.js appears truncated"


def test_orb_and_voice_core_exports_and_states():
    """Verify voice-core.js exports createVoiceCore and orb.js implements states and fallback."""
    voice_core = (FRONTEND_DIR / "voice-core.js").read_text(encoding="utf-8")
    assert "export function createVoiceCore(canvas)" in voice_core or "export function createVoiceCore(" in voice_core
    assert "EffectComposer" in voice_core
    assert "UnrealBloomPass" in voice_core

    orb = (FRONTEND_DIR / "orb.js").read_text(encoding="utf-8")
    assert "class JarvisOrb" in orb
    assert "createVoiceCore" in orb
    assert "CanvasOrb" in orb
    assert "useFallback" in orb

    # Check that required state colors are defined
    for state in ["connecting", "idle", "listening", "thinking", "speaking", "reconnecting", "error", "exiting"]:
        assert f"{state}:" in orb, f"State '{state}' missing in orb.js"


def test_desktop_js_voice_ui_action_and_web_audio():
    """Verify desktop.js integrates Web Audio API and implements the complete VoiceUIAction engine."""
    desktop_js = (ADA_DIR / "desktop.js").read_text(encoding="utf-8")
    
    # Web Audio API
    assert "AudioEngine" in desktop_js
    assert "initAudioEngine" in desktop_js

    # WebGL Core with fallback
    assert "JarvisOrb" in desktop_js

    # VoiceUIAction engine
    assert "export async function voiceUIAction(args)" in desktop_js or "async function voiceUIAction(args)" in desktop_js
    assert "set_volume" in desktop_js
    assert "set_motion" in desktop_js
    assert "set_voice" in desktop_js
    assert "set_microphone_level" in desktop_js
    assert "pause_microphone" in desktop_js
    assert "settings" in desktop_js
    assert "scroll" in desktop_js
    assert "projects" in desktop_js
    assert "tab" in desktop_js

    # Exposed to window for external IPC / Wayland messages
    assert "window.voiceUIAction = voiceUIAction" in desktop_js
    assert "window.handleUIRequest = handleUIRequest" in desktop_js


@pytest.fixture(scope="module")
def desktop_server():
    """Starts the Ada desktop server on an isolated test port."""
    port = 8977
    os.environ["JARVIS_ADA_PORT"] = str(port)
    if str(ADA_DIR) not in sys.path:
        sys.path.insert(0, str(ADA_DIR))
    import desktop

    thread = threading.Thread(target=desktop.main, daemon=True)
    thread.start()
    time.sleep(1.2)
    yield f"http://127.0.0.1:{port}"


def test_desktop_server_http_endpoints(desktop_server):
    """Verify the desktop server answers workspace, voice, settings, and static requests."""
    base = desktop_server
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())

    # 1. GET / sets session cookie for browser/webview requests
    with opener.open(f"{base}/") as res:
        assert res.status == 200
        html = res.read().decode("utf-8")
        assert "desktop.js" in html
        assert 'id="orb"' in html

    # 2. GET /desktop.js (static frontend asset, works without explicit API token)
    with urllib.request.urlopen(f"{base}/desktop.js") as res:
        assert res.status == 200
        js = res.read().decode("utf-8")
        assert "voiceUIAction" in js

    # 3. GET /api/workspace (authenticated via session cookie)
    with opener.open(f"{base}/api/workspace") as res:
        assert res.status == 200
        data = json.loads(res.read().decode("utf-8"))
        assert "projects" in data

    # 4. GET /api/voice (authenticated via session cookie)
    with opener.open(f"{base}/api/voice") as res:
        assert res.status == 200
        voice = json.loads(res.read().decode("utf-8"))
        assert "state" in voice
        assert "connected" in voice
        assert "energy" in voice

    # 5. GET /api/settings (authenticated via session cookie)
    with opener.open(f"{base}/api/settings") as res:
        assert res.status == 200
        settings = json.loads(res.read().decode("utf-8"))
        assert "settings" in settings
        assert "voices" in settings
        assert "Zephyr" in settings["voices"]

    # 6. POST /api/voice/action (VoiceUIAction execution, authenticated via session cookie)
    payload = json.dumps({"action": "set_volume", "amount": 80}).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/api/voice/action",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    with opener.open(req) as res:
        assert res.status == 200
        out = json.loads(res.read().decode("utf-8"))
        assert out.get("ok") is True
        assert out.get("amount") == 80

    # 7. Security: API endpoints reject unauthenticated requests and untrusted hosts
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(f"{base}/api/workspace")
    assert exc.value.code == 403
    exc.value.close()

    unauth_post = urllib.request.Request(
        f"{base}/api/voice/action",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(unauth_post)
    assert exc.value.code == 403
    exc.value.close()

    bad_host_req = urllib.request.Request(f"{base}/desktop.js", headers={"Host": "evil.example"})
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(bad_host_req)
    assert exc.value.code == 403
    exc.value.close()

    # 8. Localhost Host header and X-Jarvis-Token header are accepted consistently
    import desktop
    localhost_req = urllib.request.Request(
        f"{base}/api/voice",
        headers={"Host": "localhost:8977", "X-Jarvis-Token": desktop.TOKEN},
    )
    with urllib.request.urlopen(localhost_req) as res:
        assert res.status == 200


def test_voice_subsystem_lock_preservation():
    """Verify that no locked files in voice_layer or audio were modified."""
    # Check git status for voice_layer changes
    result = subprocess.run(
        ["git", "diff", "--name-only", "voice/assets/"],
        capture_output=True,
        text=True,
        check=True
    )
    assert result.stdout.strip() == "", f"Protected audio files were modified: {result.stdout}"
