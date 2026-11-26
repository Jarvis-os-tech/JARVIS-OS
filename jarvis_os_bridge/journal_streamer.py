"""Structured systemd Journal Streamer & Proactive Anomaly Detector for JARVIS OS.

Continuously tails journald JSON stream asynchronously to detect OOM-kills,
kernel segfaults, storage errors, and service crashes before the user experiences failure.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import time
from typing import Any, Callable, Dict, Optional

from .constants import (
    EVENT_JOURNAL_DISK_ERROR,
    EVENT_JOURNAL_OOM_KILL,
    EVENT_JOURNAL_SEGFAULT,
    EVENT_JOURNAL_SERVICE_FAILED,
)

log = logging.getLogger("jarvis.bridge.journal")

EventCallback = Callable[[str, Dict[str, Any]], None]

# Regex patterns for critical system anomalies
PATTERN_OOM = re.compile(r"(?:oom[-_]killer|oom_kill_process|Out of memory: Kill process\s+(\d+)\s+\(([^)]+)\))", re.I)
PATTERN_SEGFAULT = re.compile(r"(\S+)\[(\d+)\]:\s*segfault at [0-9a-f]+ ip [0-9a-f]+ sp [0-9a-f]+ error \d+(?: in (\S+))?", re.I)
PATTERN_COREDUMP = re.compile(r"Process (\d+) \(([^)]+)\) of user \d+ dumped core", re.I)
PATTERN_DISK_ERROR = re.compile(r"(?:I/O error|Buffer I/O error|EXT4-fs error|BTRFS: error|read-only file system)", re.I)
PATTERN_SERVICE_FAIL = re.compile(r"(?:Unit\s+(\S+)\s+has\s+failed|Failed with result '([^']+)')", re.I)


class JournalStreamer:
    """Async streamer for systemd journal anomalies."""

    def __init__(self, on_event: Optional[EventCallback] = None):
        self.on_event = on_event
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._dedup_cache: Dict[str, float] = {}

    async def start(self) -> None:
        """Launch journalctl follower and start processing stream."""
        if not shutil.which("journalctl"):
            log.warning("journalctl binary not found; JournalStreamer inactive")
            return

        self._running = True
        self._task = asyncio.create_task(self._stream_loop())
        log.info("JournalStreamer task initiated")

    async def close(self) -> None:
        """Terminate journalctl subprocess and background task."""
        self._running = False
        if self._proc:
            try:
                self._proc.terminate()
                await asyncio.wait_for(self._proc.wait(), timeout=2.0)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None

        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        log.info("JournalStreamer closed")

    def _should_dedup(self, key: str, window_seconds: float = 60.0) -> bool:
        """Check if an alert signature has already been emitted within the window."""
        now = time.monotonic()
        last = self._dedup_cache.get(key, 0.0)
        # Prune expired keys
        if len(self._dedup_cache) > 500:
            self._dedup_cache = {k: v for k, v in self._dedup_cache.items() if now - v < 300.0}

        if now - last < window_seconds:
            return True
        self._dedup_cache[key] = now
        return False

    def _emit(self, event_name: str, payload: Dict[str, Any]) -> None:
        if self.on_event and callable(self.on_event):
            try:
                self.on_event(event_name, payload)
            except Exception as err:
                log.error("Error in JournalStreamer callback for %s: %s", event_name, err)

    async def _stream_loop(self) -> None:
        """Tails journalctl output in JSON format."""
        backoff = 1.0
        while self._running:
            try:
                cmd = [
                    "journalctl",
                    "--lines=0",
                    "--follow",
                    "--output=json",
                    "--priority=err..emerg",  # Only inspect errors and above by default
                ]

                self._proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                backoff = 1.0
                log.info("journalctl streamer spawned (PID %d)", self._proc.pid)

                assert self._proc.stdout is not None
                while self._running:
                    line = await self._proc.stdout.readline()
                    if not line:
                        break  # EOF / process died

                    try:
                        entry = json.loads(line.decode("utf-8", errors="replace").strip())
                        self._analyze_entry(entry)
                    except Exception:
                        continue

            except asyncio.CancelledError:
                break
            except Exception as err:
                log.warning("Journal stream interrupted: %s; restarting in %.1fs", err, backoff)
                await asyncio.sleep(backoff)
                backoff = min(15.0, backoff * 1.5)

    def _analyze_entry(self, entry: Dict[str, Any]) -> None:
        raw_msg = entry.get("MESSAGE", "")
        if isinstance(raw_msg, list):
            msg = bytes(raw_msg).decode("utf-8", errors="replace")
        else:
            msg = str(raw_msg)

        comm = str(entry.get("_COMM", entry.get("SYSLOG_IDENTIFIER", "kernel")))
        unit = str(entry.get("_SYSTEMD_USER_UNIT", entry.get("_SYSTEMD_UNIT", "")))
        pid = str(entry.get("_PID", ""))

        # 1. Out of Memory (OOM) Killer
        oom_match = PATTERN_OOM.search(msg)
        if oom_match or "oom-killer" in msg.lower():
            victim = oom_match.group(2) if (oom_match and oom_match.group(2)) else comm
            dedup_key = f"oom_{victim}"
            if not self._should_dedup(dedup_key, window_seconds=120.0):
                self._emit(EVENT_JOURNAL_OOM_KILL, {
                    "process": victim,
                    "pid": oom_match.group(1) if oom_match and oom_match.group(1) else pid,
                    "message": msg,
                    "unit": unit,
                })
            return

        # 2. Segfault or Core Dump
        seg_match = PATTERN_SEGFAULT.search(msg)
        core_match = PATTERN_COREDUMP.search(msg)
        if seg_match or core_match or "sigsegv" in msg.lower():
            proc_name = (
                seg_match.group(1) if seg_match
                else (core_match.group(2) if core_match else comm)
            )
            dedup_key = f"crash_{proc_name}"
            if not self._should_dedup(dedup_key, window_seconds=60.0):
                self._emit(EVENT_JOURNAL_SEGFAULT, {
                    "process": proc_name,
                    "pid": seg_match.group(2) if seg_match else (core_match.group(1) if core_match else pid),
                    "library": seg_match.group(3) if seg_match else None,
                    "message": msg,
                    "unit": unit,
                })
            return

        # 3. Disk / Filesystem errors
        if PATTERN_DISK_ERROR.search(msg):
            dedup_key = f"disk_err_{comm}_{hash(msg) % 1000}"
            if not self._should_dedup(dedup_key, window_seconds=180.0):
                self._emit(EVENT_JOURNAL_DISK_ERROR, {
                    "component": comm,
                    "message": msg,
                })
            return

        # 4. Service failure
        srv_match = PATTERN_SERVICE_FAIL.search(msg)
        if srv_match and unit:
            failed_unit = srv_match.group(1) or unit
            reason = srv_match.group(2) or "Failed"
            dedup_key = f"service_{failed_unit}"
            if not self._should_dedup(dedup_key, window_seconds=120.0):
                self._emit(EVENT_JOURNAL_SERVICE_FAILED, {
                    "unit": failed_unit,
                    "reason": reason,
                    "message": msg,
                })
