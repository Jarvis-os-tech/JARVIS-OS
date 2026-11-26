"""Zero-Polling Filesystem Watcher for JARVIS OS.

Uses native Linux inotify to monitor ~/Downloads, config changes,
and desktop theme adjustments via asyncio add_reader (Zero Polling Invariant).
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import inotify_simple
from inotify_simple import flags

from .constants import (
    EVENT_FS_CONFIG_CHANGED,
    EVENT_FS_DOWNLOAD_COMPLETED,
    EVENT_FS_THEME_CHANGED,
)

log = logging.getLogger("jarvis.bridge.fs_watcher")

EventCallback = Callable[[str, Dict[str, Any]], None]

# Temporary extensions to ignore until completed
INCOMPLETE_EXTENSIONS = frozenset({
    ".crdownload",
    ".part",
    ".tmp",
    ".download",
    ".aria2",
})


class FsWatcher:
    """Async inotify watcher for downloads, configurations, and themes."""

    def __init__(self, on_event: Optional[EventCallback] = None):
        self.on_event = on_event
        self._inotify: Optional[inotify_simple.INotify] = None
        self._watch_descriptors: Dict[int, str] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._fd: Optional[int] = None

    def start(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        """Initialize inotify and add watched paths to asyncio reader."""
        self._loop = loop or asyncio.get_running_loop()
        self._inotify = inotify_simple.INotify()
        self._fd = self._inotify.fileno()

        # 1. Downloads folder
        downloads_dir = Path.home() / "Downloads"
        if downloads_dir.exists():
            wd = self._inotify.add_watch(
                str(downloads_dir),
                flags.CLOSE_WRITE | flags.MOVED_TO,
            )
            self._watch_descriptors[wd] = "downloads"

        # 2. Hyprland configuration
        hypr_dir = Path.home() / ".config" / "hypr"
        if hypr_dir.exists():
            wd = self._inotify.add_watch(
                str(hypr_dir),
                flags.CLOSE_WRITE | flags.MOVED_TO,
            )
            self._watch_descriptors[wd] = "hypr_config"

        # 3. Omarchy theme
        theme_dir = Path.home() / ".local" / "state" / "omarchy" / "current" / "theme"
        if theme_dir.exists():
            wd = self._inotify.add_watch(
                str(theme_dir),
                flags.CLOSE_WRITE | flags.MOVED_TO,
            )
            self._watch_descriptors[wd] = "theme"

        self._loop.add_reader(self._fd, self._on_fs_event)
        log.info("FsWatcher registered watches on %d paths (fd %d)", len(self._watch_descriptors), self._fd)

    def close(self) -> None:
        """Clean up inotify watches and reader."""
        if self._loop and self._fd is not None:
            try:
                self._loop.remove_reader(self._fd)
            except Exception:
                pass
            self._fd = None

        if self._inotify:
            try:
                self._inotify.close()
            except Exception:
                pass
            self._inotify = None
        self._watch_descriptors.clear()
        log.info("FsWatcher closed")

    def _emit(self, event_name: str, payload: Dict[str, Any]) -> None:
        if self.on_event and callable(self.on_event):
            try:
                self.on_event(event_name, payload)
            except Exception as err:
                log.error("Error in FsWatcher callback for %s: %s", event_name, err)

    def _on_fs_event(self) -> None:
        """Non-blocking handler called when inotify has event bytes ready."""
        if not self._inotify:
            return
        try:
            events = self._inotify.read(timeout=0)
            for event in events:
                category = self._watch_descriptors.get(event.wd)
                filename = event.name
                if not filename:
                    continue

                if category == "downloads":
                    ext = Path(filename).suffix.lower()
                    if ext in INCOMPLETE_EXTENSIONS or filename.startswith("."):
                        continue
                    full_path = Path.home() / "Downloads" / filename
                    size_bytes = 0
                    try:
                        size_bytes = full_path.stat().st_size
                    except OSError:
                        pass

                    self._emit(EVENT_FS_DOWNLOAD_COMPLETED, {
                        "filename": filename,
                        "path": str(full_path),
                        "size_bytes": size_bytes,
                    })

                elif category == "hypr_config":
                    if filename.endswith(".conf") or filename.endswith(".lua"):
                        self._emit(EVENT_FS_CONFIG_CHANGED, {
                            "component": "hyprland",
                            "file": filename,
                        })

                elif category == "theme":
                    self._emit(EVENT_FS_THEME_CHANGED, {
                        "file": filename,
                    })
        except Exception as err:
            log.warning("Error reading inotify events: %s", err)
