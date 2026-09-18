"""
J.A.R.V.I.S. High-Fidelity Terminal Logger & Display System.
Provides ANSI colored badges, structured log streams, error highlighting in bright red,
and a futuristic Cyber-HUD terminal layout.
"""

import os
import sys
import re
import time
import logging
from datetime import datetime
from typing import Optional, Any

# ── ANSI Escape Codes ────────────────────────────────────────────────────────
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"
UNDERLINE = "\033[4m"

# Foreground Colors
BLACK = "\033[30m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"

# Bold / High-Intensity Colors
B_RED = "\033[1;31m"
B_GREEN = "\033[1;32m"
B_YELLOW = "\033[1;33m"
B_BLUE = "\033[1;34m"
B_MAGENTA = "\033[1;35m"
B_CYAN = "\033[1;36m"
B_WHITE = "\033[1;37m"

# Background Colors
BG_RED = "\033[41m"
BG_BLUE = "\033[44m"
BG_CYAN = "\033[46m"


def _time_str() -> str:
    """Current timestamp in HH:MM:SS format."""
    return datetime.now().strftime("%H:%M:%S")


def log_info(msg: str, source: str = "Core"):
    """Standard informational log with cyan branding."""
    t = f"{DIM}[{_time_str()}]{RESET}"
    tag = f"{B_CYAN}[INFO]{RESET}"
    src = f"{DIM}[{source}]{RESET}" if source else ""
    print(f"{t} {tag} {src} {msg}")


def log_success(msg: str, source: str = "Core"):
    """Positive success confirmation with green highlight."""
    t = f"{DIM}[{_time_str()}]{RESET}"
    tag = f"{B_GREEN}[OK]{RESET}"
    src = f"{DIM}[{source}]{RESET}" if source else ""
    print(f"{t} {tag} {src} {msg}")


def log_warn(msg: str, source: str = "Core"):
    """Warning message in high-visibility yellow."""
    t = f"{DIM}[{_time_str()}]{RESET}"
    tag = f"{B_YELLOW}[WARN]{RESET}"
    src = f"{DIM}[{source}]{RESET}" if source else ""
    print(f"{t} {tag} {src} {YELLOW}{msg}{RESET}")


def log_error(msg: str, source: str = "Core", exc: Optional[Exception] = None):
    """
    Error logging: marked explicitly as [ERROR] and printed in BOLD BRIGHT RED.
    Mandatory: When there is an error, format it with [ERROR] in red text.
    """
    t = f"{DIM}[{_time_str()}]{RESET}"
    tag = f"{B_RED}[ERROR]{RESET}"
    src = f"{B_RED}[{source}]{RESET}" if source else ""
    print(f"{t} {tag} {src} {B_RED}{msg}{RESET}")
    if exc:
        import traceback
        lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
        for line in "".join(lines).strip().splitlines():
            print(f"{DIM}          ↳ {RESET}{RED}{line}{RESET}")


def log_reminder(msg: str, action: str = "ALERT"):
    """Clean and dedicated reminder notification badge."""
    t = f"{DIM}[{_time_str()}]{RESET}"
    if action == "ALERT":
        tag = f"{B_YELLOW}[REMINDER]{RESET} {B_WHITE}🔔{RESET}"
        print(f"{t} {tag} {B_YELLOW}{msg}{RESET}")
    elif action == "DONE":
        tag = f"{B_GREEN}[REMINDER]{RESET} {B_GREEN}✓{RESET}"
        print(f"{t} {tag} {GREEN}{msg}{RESET}")
    else:
        tag = f"{B_CYAN}[REMINDER]{RESET} ⏰"
        print(f"{t} {tag} {msg}")


def log_tool(name: str, status: str = "executing", duration_ms: Optional[float] = None):
    """Tool invocation and dispatch logging in purple/magenta."""
    t = f"{DIM}[{_time_str()}]{RESET}"
    tag = f"{B_MAGENTA}[TOOL]{RESET}"
    dur = f" {DIM}({duration_ms:.0f}ms){RESET}" if duration_ms is not None else ""
    print(f"{t} {tag} ⚡ {B_WHITE}{name}{RESET} ⟶ {status}{dur}")


def log_voice(text: str, role: str = "JARVIS"):
    """Spoken voice turn logging in tactical blue."""
    t = f"{DIM}[{_time_str()}]{RESET}"
    tag = f"{B_BLUE}[VOICE]{RESET}"
    print(f"{t} {tag} 🎙 {B_WHITE}{role}:{RESET} {text}")


def print_banner(persona: str = "JARVIS", port: int = 8000, socket_path: str = "/tmp/jarvis_audio.sock", tools_count: int = 74):
    """
    Renders an elegant, high-aesthetic J.A.R.V.I.S. OS Cyber-HUD startup banner.
    """
    box_w = 76
    title = "⚡ J.A.R.V.I.S. OS — AUTONOMOUS CORE ENGINE ONLINE ⚡"
    sub_title = "High-Fidelity Real-Time Voice & Multimodal Operating System"

    def _vis_len(s: str) -> int:
        return len(re.sub(r'\033\[[0-9;]*m', '', s))

    def _row(content: str) -> str:
        pad = max(0, (box_w - 2) - _vis_len(content))
        return f"{B_CYAN}│{RESET}{content}{' ' * pad}{B_CYAN}│{RESET}"

    print(f"\n{B_CYAN}╭" + "─" * (box_w - 2) + f"╮{RESET}")
    print(_row(f" {B_WHITE}{title.center(box_w - 4)}{RESET} "))
    print(_row(f" {DIM}{sub_title.center(box_w - 4)}{RESET} "))
    print(f"{B_CYAN}├" + "─" * (box_w - 2) + f"┤{RESET}")
    print(_row(f"  {B_WHITE}• REST & WebSocket API :{RESET} {CYAN}http://127.0.0.1:{port}{RESET}"))
    print(_row(f"  {B_WHITE}• Audio Gateway Socket :{RESET} {CYAN}{socket_path}{RESET}"))
    print(_row(f"  {B_WHITE}• Active Voice Persona :{RESET} {B_GREEN}{persona.upper()}{RESET} {DIM}(Gemini Live Full-Duplex){RESET}"))
    print(_row(f"  {B_WHITE}• Actuators & Skills   :{RESET} {B_YELLOW}{tools_count} registered tools{RESET} {DIM}(Native Sub-5ms){RESET}"))
    print(_row(f"  {B_WHITE}• Temporal Scheduler   :{RESET} {B_MAGENTA}Autonomous Smart Reminders Active{RESET}"))
    print(f"{B_CYAN}╰" + "─" * (box_w - 2) + f"╯{RESET}\n")


class JarvisLogFormatter(logging.Formatter):
    """Custom logging.Formatter to route standard library logs to Jarvis colors."""
    def format(self, record):
        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        lvl = record.levelname
        name = record.name

        if record.levelno >= logging.ERROR:
            tag = f"{B_RED}[ERROR]{RESET}"
            msg = f"{B_RED}{record.getMessage()}{RESET}"
        elif record.levelno >= logging.WARNING:
            tag = f"{B_YELLOW}[WARN]{RESET}"
            msg = f"{YELLOW}{record.getMessage()}{RESET}"
        elif record.levelno >= logging.INFO:
            tag = f"{B_CYAN}[INFO]{RESET}"
            msg = record.getMessage()
        else:
            tag = f"{DIM}[DEBUG]{RESET}"
            msg = f"{DIM}{record.getMessage()}{RESET}"

        return f"{DIM}[{timestamp}]{RESET} {tag} {DIM}[{name}]{RESET} {msg}"


def setup_global_logger():
    """Configures root logger with Jarvis formatting and red error handling."""
    root = logging.getLogger()
    # Suppress verbose standard logs from uvicorn/http
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("websockets").setLevel(logging.WARNING)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JarvisLogFormatter())
    root.handlers = [handler]

    # Global unhandled exception hook: always print in bold red text marked as [ERROR]
    def _uncaught_exception_hook(exctype, value, tb):
        import traceback
        t = f"{DIM}[{_time_str()}]{RESET}"
        print(f"\n{t} {B_RED}[ERROR] [CRITICAL] Uncaught exception: {value}{RESET}")
        for line in traceback.format_tb(tb):
            for sub in line.splitlines():
                print(f"{DIM}          ↳ {RESET}{RED}{sub}{RESET}")

    sys.excepthook = _uncaught_exception_hook
