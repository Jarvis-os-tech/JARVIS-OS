"""
Hermes Bridge for J.A.R.V.I.S. Python Core Engine.
Enables headless, non-blocking task delegation to the Hermes sub-agent CLI.
Matches the capabilities and contract of server/hermesBridge.ts.
"""

import os
import re
import time
import socket
import shutil
import asyncio
import tempfile
import subprocess
from typing import Dict, Any, Optional, Tuple

TIMEOUT_MS = int(os.getenv("HERMES_TIMEOUT_MS", "180000"))
MAX_TURNS = int(os.getenv("HERMES_MAX_TURNS", "12"))
OMH_TOOLSET_WARN = re.compile(r"Warning:\s*Unknown toolsets:\s*omh", re.IGNORECASE)


def get_hermes_bin() -> str:
    env_bin = os.getenv("HERMES_BIN")
    if env_bin and os.path.exists(env_bin):
        return env_bin
    cand = shutil.which("hermes")
    if cand:
        return cand
    for p in [
        os.path.expanduser("~/.local/bin/hermes"),
        os.path.expanduser("~/.hermes/hermes-agent/bin/hermes"),
        os.path.expanduser("~/.hermes/bin/hermes"),
    ]:
        if os.path.exists(p):
            return p
    return "hermes"


ANSI_ESCAPE = re.compile(r'\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


def clean_hermes_output(raw: str) -> Tuple[str, Optional[str]]:
    # Strip ANSI escape sequences
    clean_raw = ANSI_ESCAPE.sub('', raw)
    lines = clean_raw.splitlines()
    session_id = None
    kept = []
    for line in lines:
        if OMH_TOOLSET_WARN.search(line):
            continue
        if "found but has no messages. Starting fresh" in line:
            continue
        if "Loaded cached tools" in line:
            continue
        sid_match = re.match(r"^\s*session_id:\s*(\S+)", line, re.IGNORECASE)
        if sid_match:
            session_id = sid_match.group(1)
            continue
        # Extract direct response after hermes box divider if present
        if "┊" in line:
            parts = line.split("┊", 1)
            if len(parts) > 1 and parts[1].strip():
                kept.append(parts[1].strip())
                continue
        kept.append(line)

    result_text = "\n".join(kept).strip()
    return result_text, session_id


async def check_hermes_health() -> Dict[str, Any]:
    hermes_bin = get_hermes_bin()
    bin_exists = bool(shutil.which(hermes_bin) or os.path.exists(hermes_bin))
    reachable = False

    # 1. Probe systemd user service first (matches server/hermesBridge.ts)
    try:
        proc = subprocess.run(
            ["systemctl", "--user", "is-active", "hermes-gateway.service"],
            capture_output=True,
            text=True,
            timeout=2.0
        )
        if proc.stdout.strip() == "active":
            reachable = True
    except Exception:
        pass

    # 2. Fall back to socket probe on port 9119
    if not reachable:
        try:
            sock = socket.create_connection(("127.0.0.1", 9119), timeout=0.5)
            sock.close()
            reachable = True
        except Exception:
            pass

    vault_candidates = [
        os.path.join(os.getcwd(), "memory", "vault"),
        os.path.join(os.getcwd(), "jarvis-memory"),
        os.path.join(os.getcwd(), "friday-memory"),
    ]
    vault_path = next((p for p in vault_candidates if os.path.exists(p)), vault_candidates[0])

    return {
        "ok": bin_exists,
        "hermes": {
            "ok": bin_exists,
            "version": "Hermes Agent v0.21.0",
            "gateway": {"url": "127.0.0.1:9119", "reachable": reachable},
        },
        "connected": bin_exists and reachable,
        "delegation": "ready" if bin_exists else "unavailable",
        "vault": vault_path,
        "vaultExists": os.path.exists(vault_path),
    }


async def exec_hermes(
    prompt: str,
    timeout: Optional[float] = None,
    max_turns: Optional[int] = None,
    yolo: bool = True,
    session_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute a single delegated task against Hermes asynchronously and headlessly.
    Passes prompt via temporary file to prevent shell escape issues.
    """
    if not prompt or not prompt.strip():
        return {"success": False, "text": "", "error": "Prompt is required"}

    hermes_bin = get_hermes_bin()
    timeout_sec = (timeout or (TIMEOUT_MS / 1000.0))
    turns = max_turns or MAX_TURNS
    sess = session_name or f"jarvis-delegated-{int(time.time() * 1000)}"

    tmp_file = os.path.join(
        os.getcwd(),
        f".hermes_query_{int(time.time() * 1000)}_{os.urandom(3).hex()}.tmp"
    )

    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write(prompt.strip())

        args = [
            "-p", "default",
            "chat",
            "--continue", sess,
            "--create-if-missing",
            "--query-file", tmp_file,
            "--oneshot",
            "-Q",
            "--max-turns", str(turns),
        ]
        if yolo:
            args.append("--yolo")

        print(f"[HermesBridge] Spawning Hermes sub-agent task: {prompt[:50]}...")
        proc = await asyncio.create_subprocess_exec(
            hermes_bin,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=dict(os.environ),
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            return {
                "success": False,
                "text": "",
                "error": f"Hermes timed out after {timeout_sec:.0f}s (task may have looped).",
            }

        out_str = stdout.decode("utf-8", errors="replace").strip()
        err_str = stderr.decode("utf-8", errors="replace").strip()

        if proc.returncode != 0 and not out_str:
            return {
                "success": False,
                "text": "",
                "error": err_str or f"Hermes process exited with code {proc.returncode}",
            }

        clean_text, session_id = clean_hermes_output(out_str)
        return {
            "success": True,
            "text": clean_text or out_str,
            "sessionId": session_id or sess,
            "raw": out_str,
        }

    except Exception as e:
        return {"success": False, "text": "", "error": f"Hermes execution failed: {str(e)}"}

    finally:
        if os.path.exists(tmp_file):
            try:
                os.unlink(tmp_file)
            except Exception:
                pass
