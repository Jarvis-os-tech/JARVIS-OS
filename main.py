#!/usr/bin/env python3
"""
J.A.R.V.I.S. Root Orchestrator Entrypoint.
Run directly with: python main.py
"""

import sys
import os
import subprocess
import signal
import time
# Auto re-execute with virtual environment if needed before importing any 3rd party dependencies
REQUIRED_PKGS = ["dotenv", "fastapi", "uvicorn", "websockets", "jinja2"]
missing = []
for pkg in REQUIRED_PKGS:
    try:
        __import__(pkg)
    except ImportError:
        missing.append(pkg)

if missing:
    venv_candidates = [
        os.path.expanduser("~/.venv/bin/python"),
        os.path.expanduser("~/.venv/bin/python3"),
        os.path.expanduser("~/.hermes/hermes-agent/.venv/bin/python"),
        os.path.join(os.getcwd(), "venv", "bin", "python"),
        os.path.join(os.getcwd(), ".venv", "bin", "python"),
    ]
    for cand in venv_candidates:
        if os.path.exists(cand) and cand != sys.executable:
            print(f"[Launcher] Switching to configured Python environment: {cand}")
            os.execv(cand, [cand] + sys.argv)
            sys.exit(0)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.getcwd(), ".env"))
    load_dotenv()
except ImportError:
    pass

# Add current directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

try:
    from brain.main import main as core_main
except ImportError:
    from core_engine.main import main as core_main

RUST_GATEWAY_CANDIDATES = [
    os.path.join(os.path.dirname(__file__), "gateway", "audio_rust", "target", "release", "jarvis-gateway"),
    os.path.join(os.path.dirname(__file__), "gateway_rust", "target", "release", "jarvis-gateway"),
]
RUST_GATEWAY_BIN = next((p for p in RUST_GATEWAY_CANDIDATES if os.path.exists(p)), RUST_GATEWAY_CANDIDATES[0])


def ensure_gateway_service():
    """Ensure the 24/7 Python Telegram & Heartbeat gateway service is running."""
    try:
        service_name = "jarvis-gateway.service"
        res = subprocess.run(["systemctl", "--user", "is-active", service_name],
                             capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip() == "active":
            print("\033[2m[Launcher]\033[0m \033[1;32m[OK]\033[0m 24/7 JARVIS-OS Gateway service active & running.")
            return

        # Check legacy fallback
        res_legacy = subprocess.run(["systemctl", "--user", "is-active", "friday-gateway.service"],
                                    capture_output=True, text=True)
        if res_legacy.returncode == 0 and res_legacy.stdout.strip() == "active":
            print("\033[2m[Launcher]\033[0m \033[1;32m[OK]\033[0m 24/7 JARVIS-OS Gateway service active & running (legacy).")
            return

        print("\033[2m[Launcher]\033[0m \033[1;36m[INFO]\033[0m 🔄 Starting 24/7 JARVIS-OS Gateway service...")
        subprocess.run(["systemctl", "--user", "start", service_name], capture_output=True)
    except Exception as e:
        print(f"\033[2m[Launcher]\033[0m \033[1;31m[ERROR] Gateway service check failed: {e}\033[0m")


def spawn_rust_audio_gateway():
    """
    Spawns the Rust audio gateway in the background if compiled.
    """
    if os.path.exists(RUST_GATEWAY_BIN):
        try:
            proc = subprocess.Popen(
                [RUST_GATEWAY_BIN, "--socket-path", "/tmp/jarvis_audio.sock"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return proc
        except Exception as e:
            print(f"\033[2m[Launcher]\033[0m \033[1;31m[ERROR] Rust audio gateway failed: {e}\033[0m")
    return None


def ensure_ui_built():
    """Ensure the React 19 UI is compiled in dist/ for seamless presentation."""
    root_dir = os.path.dirname(os.path.abspath(__file__))
    dist_index = os.path.join(root_dir, "dist", "index.html")
    if not os.path.exists(dist_index):
        print("\033[2m[Launcher]\033[0m \033[1;36m[INFO]\033[0m 📦 UI dist bundle missing. Compiling React 19 frontend UI...")
        try:
            subprocess.run(["npm", "run", "build"], check=True, cwd=root_dir)
            print("\033[2m[Launcher]\033[0m \033[1;32m[OK]\033[0m UI build complete.")
        except Exception as e:
            print(f"\033[2m[Launcher]\033[0m \033[1;31m[ERROR] UI build failed: {e}\033[0m")


if __name__ == "__main__":
    ensure_gateway_service()
    ensure_ui_built()
    rust_proc = None
    if "--standalone-audio" in sys.argv:
        sys.argv.remove("--standalone-audio")
        rust_proc = spawn_rust_audio_gateway()
        if rust_proc:
            print(f"[Launcher] 🎙 Rust Microsecond Audio Gateway started (PID: {rust_proc.pid})")

    try:
        core_main()
    finally:
        if rust_proc and rust_proc.poll() is None:
            print("[Launcher] Stopping Rust Audio Gateway...")
            rust_proc.terminate()
            try:
                rust_proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                rust_proc.kill()
