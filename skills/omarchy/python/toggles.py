"""
omarchy_skills.python.toggles
Feature toggles for Omarchy: nightlight, bar, touchpad, screensaver, idle.
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, Any

_BIN_PATH = Path(__file__).resolve().parent.parent / "bin" / "omarchy_ctrl"

async def _call_native(action: str, target: str = "") -> Dict[str, Any]:
    bin_str = str(_BIN_PATH) if _BIN_PATH.exists() else "omarchy_ctrl"
    args = [bin_str, "toggle", action]
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

async def toggle_nightlight() -> Dict[str, Any]:
    """Toggle screen color temperature nightlight (hyprsunset)."""
    return await _call_native("nightlight")

async def toggle_bar() -> Dict[str, Any]:
    """Toggle status bar visibility without killing the shell."""
    return await _call_native("bar")

async def toggle_touchpad() -> Dict[str, Any]:
    """Enable, disable, or toggle laptop touchpad."""
    return await _call_native("touchpad")

async def toggle_screensaver() -> Dict[str, Any]:
    """Toggle screensaver mode."""
    return await _call_native("screensaver")

async def stay_awake() -> Dict[str, Any]:
    """Prevent sleep and automatic idle timeout."""
    return await _call_native("stay_awake")
