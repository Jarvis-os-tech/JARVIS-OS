"""
omarchy_skills.python.capture
Desktop capture capabilities: smart screenshot, fullscreen screenshot, OCR text, and QR decode.
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, Any

_BIN_PATH = Path(__file__).resolve().parent.parent / "bin" / "omarchy_ctrl"

async def _call_native(action: str, target: str = "") -> Dict[str, Any]:
    bin_str = str(_BIN_PATH) if _BIN_PATH.exists() else "omarchy_ctrl"
    args = [bin_str, "capture", action]
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

async def take_screenshot(mode: str = "smart") -> Dict[str, Any]:
    """Capture a screenshot ('smart' for region/window, 'fullscreen' for full monitor)."""
    return await _call_native(mode)

async def capture_text_ocr() -> Dict[str, Any]:
    """Extract text from a selected screen region via OCR."""
    return await _call_native("text")

async def capture_qr() -> Dict[str, Any]:
    """Decode a QR code from a screen region."""
    return await _call_native("qr")
