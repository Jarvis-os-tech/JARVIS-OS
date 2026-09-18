"""
omarchy_skills.python.hyprland
High-speed Hyprland window & workspace management via native C++ socket actuator.
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional

_BIN_PATH = Path(__file__).resolve().parent.parent / "bin" / "omarchy_ctrl"

async def _call_native(action: str, target: str = "") -> Dict[str, Any]:
    bin_str = str(_BIN_PATH) if _BIN_PATH.exists() else "omarchy_ctrl"
    args = [bin_str, "hypr", action]
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

async def close_active_window() -> Dict[str, Any]:
    """Close the currently focused Hyprland window instantly."""
    return await _call_native("close_window")

async def close_all_windows() -> Dict[str, Any]:
    """Close all open windows across workspaces."""
    return await _call_native("close_all")

async def toggle_fullscreen() -> Dict[str, Any]:
    """Toggle fullscreen mode for the focused window."""
    return await _call_native("fullscreen")

async def toggle_float() -> Dict[str, Any]:
    """Toggle between floating and tiled mode for the focused window."""
    return await _call_native("float")

async def switch_workspace(workspace: int | str) -> Dict[str, Any]:
    """Switch active workspace (1-10 or name)."""
    return await _call_native("workspace", str(workspace))

async def move_to_workspace(workspace: int | str) -> Dict[str, Any]:
    """Move focused window to a target workspace."""
    return await _call_native("movetoworkspace", str(workspace))

async def next_workspace() -> Dict[str, Any]:
    """Cycle to next workspace."""
    return await _call_native("next_workspace")

async def prev_workspace() -> Dict[str, Any]:
    """Cycle to previous workspace."""
    return await _call_native("prev_workspace")

async def cycle_next_window() -> Dict[str, Any]:
    """Focus next window."""
    return await _call_native("cyclenext")

async def get_active_window() -> Dict[str, Any]:
    """Get active focused window details in JSON format."""
    res = await _call_native("activewindow")
    if res.get("success") and "output" in res:
        try:
            return {"success": True, "window": json.loads(res["output"]), "duration_ms": res.get("duration_ms", 0)}
        except Exception:
            pass
    return res

async def get_workspaces() -> Dict[str, Any]:
    """Get all active workspaces."""
    res = await _call_native("workspaces")
    if res.get("success") and "output" in res:
        try:
            return {"success": True, "workspaces": json.loads(res["output"]), "duration_ms": res.get("duration_ms", 0)}
        except Exception:
            pass
    return res

async def get_clients() -> Dict[str, Any]:
    """Get all open window clients."""
    res = await _call_native("clients")
    if res.get("success") and "output" in res:
        try:
            return {"success": True, "clients": json.loads(res["output"]), "duration_ms": res.get("duration_ms", 0)}
        except Exception:
            pass
    return res
