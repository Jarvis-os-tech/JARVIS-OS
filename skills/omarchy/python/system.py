"""
omarchy_skills.python.system
System control, service restarts, power management, and OSD alerts for Omarchy.
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, Any

_BIN_PATH = Path(__file__).resolve().parent.parent / "bin" / "omarchy_ctrl"

async def _call_native(domain: str, action: str, target: str = "") -> Dict[str, Any]:
    bin_str = str(_BIN_PATH) if _BIN_PATH.exists() else "omarchy_ctrl"
    args = [bin_str, domain, action]
    if target:
        args.append(str(target))
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        raw = stdout.decode("utf-8", errors="replace").strip()
        if raw.startswith("{") and raw.endswith("}"):
            return json.loads(raw)
        return {"success": proc.returncode == 0, "output": raw}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def lock_screen() -> Dict[str, Any]:
    """Lock the computer and turn off the display."""
    return await _call_native("system", "lock")

async def sleep_system() -> Dict[str, Any]:
    """Put computer into sleep lock."""
    return await _call_native("system", "sleep")

async def get_system_stats() -> Dict[str, Any]:
    """Retrieve system CPU and memory stats."""
    return await _call_native("system", "stats")

async def restart_audio() -> Dict[str, Any]:
    """Restart audio services and recover stuck PipeWire/USB devices."""
    return await _call_native("restart", "audio")

async def restart_bluetooth() -> Dict[str, Any]:
    """Unblock and restart Bluetooth service."""
    return await _call_native("restart", "bluetooth")

async def restart_wifi() -> Dict[str, Any]:
    """Unblock and restart Wi-Fi networking."""
    return await _call_native("restart", "wifi")

async def restart_shell() -> Dict[str, Any]:
    """Restart Omarchy status bar and shell."""
    return await _call_native("restart", "shell")

async def show_osd(message: str, icon: str = "") -> Dict[str, Any]:
    """Trigger the Omarchy Quickshell on-screen display (OSD) notification banner."""
    return await _call_native("osd", message, icon)
