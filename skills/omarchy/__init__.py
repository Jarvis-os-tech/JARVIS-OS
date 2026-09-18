"""
omarchy_skills — Ultra-Fast Built-in Omarchy Agentic Skills for JARVIS-OS.

Powered by a sub-millisecond C++ actuator (`omarchy_ctrl`) with direct Hyprland
Lua socket IPC, native process execution, and comprehensive Python bindings.
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

from .python import hyprland, theme, toggles, system, capture, launcher

_BIN_PATH = Path(__file__).resolve().parent / "bin" / "omarchy_ctrl"

class OmarchySkills:
    """Unified controller for all Omarchy skills."""

    @staticmethod
    async def execute(domain: str, action: str, target: str = "") -> Dict[str, Any]:
        """Execute any Omarchy action using the high-performance C++ actuator."""
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
            return {
                "success": proc.returncode == 0,
                "domain": domain,
                "action": action,
                "output": raw or stderr.decode("utf-8", errors="replace").strip()
            }
        except Exception as e:
            return {"success": False, "domain": domain, "action": action, "error": str(e)}

    # Convenience domain namespaces
    hyprland = hyprland
    theme = theme
    toggles = toggles
    system = system
    capture = capture
    launcher = launcher


async def execute_omarchy_action(domain: str, action: str, target: str = "") -> Dict[str, Any]:
    """Top-level functional executor for Omarchy actions."""
    return await OmarchySkills.execute(domain, action, target)


__all__ = [
    "OmarchySkills",
    "execute_omarchy_action",
    "hyprland",
    "theme",
    "toggles",
    "system",
    "capture",
    "launcher",
]
