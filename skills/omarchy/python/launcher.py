"""
omarchy_skills.python.launcher
Application and tool launchers for Omarchy.
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, Any

_BIN_PATH = Path(__file__).resolve().parent.parent / "bin" / "omarchy_ctrl"

async def _call_native(action: str, target: str = "") -> Dict[str, Any]:
    bin_str = str(_BIN_PATH) if _BIN_PATH.exists() else "omarchy_ctrl"
    args = [bin_str, "launch", action]
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

async def launch_terminal(cmd: str = "") -> Dict[str, Any]:
    """Launch the default terminal emulator."""
    return await _call_native("terminal", cmd)

async def launch_browser(url: str = "") -> Dict[str, Any]:
    """Launch default browser, optionally with a target URL."""
    return await _call_native("browser", url)

async def launch_editor(file_path: str = "") -> Dict[str, Any]:
    """Launch user editor, optionally with a file path."""
    return await _call_native("editor", file_path)

async def launch_spotify() -> Dict[str, Any]:
    """Launch Spotify music client."""
    return await _call_native("spotify")

async def launch_app(app_name: str, args: str = "") -> Dict[str, Any]:
    """Launch an application by name via Omarchy launchers."""
    return await _call_native(app_name, args)
