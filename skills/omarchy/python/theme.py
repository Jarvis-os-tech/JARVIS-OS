"""
omarchy_skills.python.theme
Theme, background, and visual styling controls for Omarchy.
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, Any

_BIN_PATH = Path(__file__).resolve().parent.parent / "bin" / "omarchy_ctrl"

async def _call_native(action: str, target: str = "") -> Dict[str, Any]:
    bin_str = str(_BIN_PATH) if _BIN_PATH.exists() else "omarchy_ctrl"
    args = [bin_str, "theme", action]
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

async def next_background() -> Dict[str, Any]:
    """Cycle to the next background wallpaper for the active theme."""
    return await _call_native("next_bg")

async def get_current_theme() -> Dict[str, Any]:
    """Get the active Omarchy theme name."""
    return await _call_native("current")

async def set_theme(theme_name: str) -> Dict[str, Any]:
    """Apply an Omarchy theme by name."""
    return await _call_native("set", theme_name)

async def list_themes() -> Dict[str, Any]:
    """List all installed Omarchy themes."""
    return await _call_native("list")

async def open_theme_switcher() -> Dict[str, Any]:
    """Open interactive graphical theme switcher."""
    return await _call_native("switcher")
