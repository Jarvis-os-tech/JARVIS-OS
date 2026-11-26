"""Hyprland compositor socket monitor and bounded SessionContext ring buffer.

Streams real-time events from Hyprland's socket2 (.socket2.sock) to track:
- Active window (class, title, address)
- Active workspace and monitor
- Window openings, title changes, moves, and closures
Maintains a bounded SessionContext ring buffer (last 10 items) and injects
compact ambient desktop context into voice turns for deictic resolution.
"""
from __future__ import annotations

import asyncio
from collections import deque
import json
import logging
import os
from pathlib import Path
import re
import time
from typing import Any, Dict, Optional

from core.desktop_session import recover_desktop_environment

log = logging.getLogger("jarvis.hypr_monitor")

_DEICTIC_RE = re.compile(r"\b(?:this|that|it|current)\b", re.IGNORECASE)
_FILE_DEICTIC_RE = re.compile(
    r"\b(?:this|that|the)\s+(?:file|doc|document|pdf|image|photo|picture|screenshot|recording|video|note|folder|directory|path)\b",
    re.IGNORECASE,
)
_WIDGET_DEICTIC_RE = re.compile(r"\b(?:this|that|the)\s+(?:widget|card|panel|canvas)\b", re.IGNORECASE)
_APP_DEICTIC_RE = re.compile(r"\b(?:this|that|the)\s+(?:app|application|program)\b", re.IGNORECASE)
_WINDOW_DEICTIC_RE = re.compile(r"\b(?:this|that|the)\s+(?:window|tab|screen|pane)\b", re.IGNORECASE)


def _clean_text(value: Any, limit: int = 120) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = re.sub(r"[\x00-\x1f\x7f]+", " ", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > limit:
        return cleaned[: limit - 3].rstrip() + "..."
    return cleaned


def _normalize_address(raw: Any) -> str:
    if not isinstance(raw, str):
        return ""
    addr = raw.strip().lower()
    if not addr or addr in ("0", "0x0", ","):
        return ""
    if not addr.startswith("0x"):
        if re.fullmatch(r"[0-9a-f]+", addr):
            addr = f"0x{addr}"
        else:
            return ""
    if addr == "0x0":
        return ""
    return addr


class SessionContext:
    """Bounded ring buffer (last N items) of ambient desktop and interaction state."""

    def __init__(self, maxlen: int = 10) -> None:
        self.maxlen = max(1, int(maxlen))
        self.items: deque[Dict[str, Any]] = deque(maxlen=self.maxlen)
        self.active_window: Dict[str, str] = {"class": "", "title": "", "address": ""}
        self.workspace: str = ""
        self.monitor: str = ""
        self.last_file_path: str = ""
        self.last_launched_app: str = ""
        self.last_widget_id: str = ""

    @property
    def has_context(self) -> bool:
        return bool(
            self.items
            or any(self.active_window.values())
            or self.workspace
            or self.monitor
            or self.last_file_path
            or self.last_launched_app
            or self.last_widget_id
        )

    def _append(self, entry: Dict[str, Any]) -> None:
        comparable = {k: v for k, v in entry.items() if k != "timestamp"}
        if self.items:
            latest = {k: v for k, v in self.items[-1].items() if k != "timestamp"}
            if latest == comparable:
                return
        entry["timestamp"] = time.time()
        self.items.append(entry)

    def record_window(
        self,
        window_class: str = "",
        title: str = "",
        address: str = "",
        workspace: str = "",
        monitor: str = "",
    ) -> None:
        w_class = _clean_text(window_class, 80)
        w_title = _clean_text(title, 100)
        w_addr = _normalize_address(address)
        if w_class or w_title or w_addr:
            self.active_window = {
                "class": w_class,
                "title": w_title,
                "address": w_addr,
            }
        if workspace:
            self.workspace = _clean_text(str(workspace), 40)
        if monitor:
            self.monitor = _clean_text(str(monitor), 40)
        if w_class or w_title or w_addr:
            if (
                self.items
                and self.items[-1].get("kind") == "window"
                and not self.items[-1].get("address")
                and w_addr
                and self.items[-1].get("class") == w_class
                and self.items[-1].get("title") == w_title
            ):
                self.items[-1]["address"] = w_addr
                self.items[-1]["workspace"] = self.workspace
                self.items[-1]["monitor"] = self.monitor
                self.items[-1]["timestamp"] = time.time()
                return
            self._append({
                "kind": "window",
                "class": w_class,
                "title": w_title,
                "address": w_addr,
                "workspace": self.workspace,
                "monitor": self.monitor,
            })

    def clear_window(self, address: str = "") -> None:
        norm = _normalize_address(address)
        current_addr = self.active_window.get("address", "")
        if not norm or not current_addr or norm == current_addr:
            self.active_window = {"class": "", "title": "", "address": ""}

    def record_workspace(self, workspace: str, monitor: str = "") -> None:
        ws = _clean_text(str(workspace), 40)
        if not ws:
            return
        self.workspace = ws
        if monitor:
            self.monitor = _clean_text(str(monitor), 40)
        self._append({
            "kind": "workspace",
            "workspace": self.workspace,
            "monitor": self.monitor,
        })

    def record_monitor(self, monitor: str, workspace: str = "") -> None:
        mon = _clean_text(str(monitor), 40)
        if not mon:
            return
        self.monitor = mon
        if workspace:
            self.workspace = _clean_text(str(workspace), 40)
        self._append({
            "kind": "monitor",
            "monitor": self.monitor,
            "workspace": self.workspace,
        })

    def record_file(self, path: str) -> None:
        cleaned = _clean_text(path, 260)
        if not cleaned:
            return
        self.last_file_path = cleaned
        self._append({"kind": "file", "path": cleaned})

    def record_app(self, app: str) -> None:
        cleaned = _clean_text(app, 80)
        if not cleaned:
            return
        self.last_launched_app = cleaned
        self._append({"kind": "app", "app": cleaned})

    def record_widget(self, widget_id: str) -> None:
        cleaned = _clean_text(widget_id, 80)
        if not cleaned:
            return
        self.last_widget_id = cleaned
        self._append({"kind": "widget", "widget_id": cleaned})

    def record_from_tool(
        self,
        name: str,
        arguments: Optional[Dict[str, Any]] = None,
        result: Any = None,
    ) -> None:
        """Update context ring buffer from executed OS/desktop tool results."""
        args = arguments if isinstance(arguments, dict) else {}
        parsed_result: Optional[Dict[str, Any]] = None
        if isinstance(result, dict):
            parsed_result = result
        elif isinstance(result, str) and result.lstrip().startswith("{"):
            try:
                loaded = json.loads(result)
                if isinstance(loaded, dict):
                    parsed_result = loaded
            except (ValueError, TypeError):
                parsed_result = None

        if name in ("launch_app", "open_application"):
            app_val = args.get("app") or args.get("name")
            if isinstance(app_val, str) and app_val.strip():
                self.record_app(app_val)

        if name in (
            "read_file", "write_file", "edit_file", "append_file", "inspect_file",
            "move_path", "copy_path", "trash_path", "delete_path", "list_files",
            "file_operation", "take_screenshot", "screen_record", "recent_files",
        ):
            for key in ("path", "file_path", "destination", "source", "target"):
                val = args.get(key)
                if isinstance(val, str) and val.strip():
                    self.record_file(val)
                    break
            if parsed_result:
                for key in ("path", "file_path", "output_path"):
                    val = parsed_result.get(key)
                    if isinstance(val, str) and val.strip():
                        self.record_file(val)
                        break
                files = parsed_result.get("files")
                if isinstance(files, list) and files:
                    first = files[0]
                    if isinstance(first, str) and first.strip():
                        self.record_file(first)
                    elif isinstance(first, dict) and isinstance(first.get("path"), str):
                        self.record_file(first["path"])

        if name in ("show_widget", "manage_widget", "manage_canvas"):
            wid = args.get("widget_id") or args.get("id")
            if not wid and parsed_result:
                wid = parsed_result.get("widget_id") or parsed_result.get("id")
            if isinstance(wid, str) and wid.strip():
                self.record_widget(wid)

    def resolve_deictic(self, text: str) -> Optional[Dict[str, Any]]:
        """Resolve deictic references ('this', 'that') without read_screen."""
        if not isinstance(text, str) or not text.strip():
            return None
        if not _DEICTIC_RE.search(text):
            return None

        if _FILE_DEICTIC_RE.search(text) and self.last_file_path:
            return {"kind": "file", "value": self.last_file_path}
        if _WIDGET_DEICTIC_RE.search(text) and self.last_widget_id:
            return {"kind": "widget", "value": self.last_widget_id}
        if _APP_DEICTIC_RE.search(text):
            app = self.active_window.get("class") or self.last_launched_app
            if app:
                return {"kind": "app", "value": app}
        if _WINDOW_DEICTIC_RE.search(text) and any(self.active_window.values()):
            return {
                "kind": "window",
                "value": dict(self.active_window),
                "workspace": self.workspace,
                "monitor": self.monitor,
            }

        if any(self.active_window.values()):
            return {
                "kind": "window",
                "value": dict(self.active_window),
                "workspace": self.workspace,
                "monitor": self.monitor,
            }
        if self.last_file_path:
            return {"kind": "file", "value": self.last_file_path}
        if self.last_widget_id:
            return {"kind": "widget", "value": self.last_widget_id}
        if self.last_launched_app:
            return {"kind": "app", "value": self.last_launched_app}
        return None

    def format_compact(self, text: str = "") -> str:
        """Render compact, prompt-safe single-line desktop context."""
        if not self.has_context:
            return ""
        parts: list[str] = []
        w_class = self.active_window.get("class", "")
        w_title = self.active_window.get("title", "")
        w_addr = self.active_window.get("address", "")
        if w_class or w_title or w_addr:
            win_desc = w_class or "Window"
            if w_title:
                win_desc += f' "{_clean_text(w_title, 60)}"'
            if w_addr:
                win_desc += f" ({w_addr})"
            parts.append(f"window={win_desc}")
        if self.workspace:
            parts.append(f"ws={self.workspace}")
        if self.monitor:
            parts.append(f"mon={self.monitor}")
        if self.last_file_path:
            parts.append(f"last_file={_clean_text(self.last_file_path, 120)}")
        if self.last_launched_app:
            parts.append(f"last_app={self.last_launched_app}")
        if self.last_widget_id:
            parts.append(f"last_widget={self.last_widget_id}")
        resolved = self.resolve_deictic(text) if text else None
        if resolved:
            if resolved["kind"] == "window":
                target = resolved["value"].get("class") or resolved["value"].get("title") or resolved["value"].get("address")
            else:
                target = resolved["value"]
            if target:
                parts.append(f"deictic={resolved['kind']}:{target}")
        if not parts:
            return ""
        return "[Desktop Context: " + " | ".join(parts) + "]"

    def snapshot(self) -> Dict[str, Any]:
        return {
            "active_window": dict(self.active_window),
            "workspace": self.workspace,
            "monitor": self.monitor,
            "last_file_path": self.last_file_path,
            "last_launched_app": self.last_launched_app,
            "last_widget_id": self.last_widget_id,
            "history": list(self.items),
        }


class HyprlandMonitor:
    def __init__(self, context: Optional[SessionContext] = None) -> None:
        self.context = context or SessionContext(maxlen=10)
        self.signature = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "")
        self.runtime_dir = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
        self.active_window: Dict[str, Any] = {}
        self.active_workspace: str = "1"
        self.active_monitor: str = ""
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_aw_at = 0.0
        self._last_v2_at = 0.0

    def _resolve_signature(self) -> str:
        sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE") or self.signature
        if not sig:
            recovered = recover_desktop_environment({"XDG_RUNTIME_DIR": str(self.runtime_dir)})
            sig = recovered.get("HYPRLAND_INSTANCE_SIGNATURE", "")
        return sig

    @property
    def socket_path(self) -> Path:
        return self.runtime_dir / "hypr" / self._resolve_signature() / ".socket2.sock"

    @property
    def command_socket_path(self) -> Path:
        return self.runtime_dir / "hypr" / self._resolve_signature() / ".socket.sock"

    @property
    def has_context(self) -> bool:
        return self.context.has_context or bool(self.active_window or self.active_monitor)

    def prompt_context(self, text: str = "") -> str:
        """Return compact desktop context for turn injection, or '' when uninitialized."""
        if not self.has_context:
            return ""
        return self.context.format_compact(text)

    def get_desktop_context(self, text: str = "") -> str:
        """Return a compact description of the current screen context."""
        if self.context.has_context:
            return self.context.format_compact(text)
        title = self.active_window.get("title", "")
        w_class = self.active_window.get("class", "")
        if title or w_class:
            return f'[Active Window: {w_class or "App"} - "{title}" on workspace {self.active_workspace}]'
        return f"[Workspace {self.active_workspace} active, no focused window]"

    async def _query_json(self, command: str) -> Any:
        sock = self.command_socket_path
        if not sock.exists():
            return None
        try:
            async with asyncio.timeout(1.0):
                reader, writer = await asyncio.open_unix_connection(str(sock))
                try:
                    writer.write(f"j/{command}".encode("utf-8"))
                    await writer.drain()
                    raw = await reader.read(65536)
                finally:
                    writer.close()
                    await writer.wait_closed()
            if not raw:
                return None
            return json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            return None

    async def refresh_snapshot(self) -> bool:
        """Seed active window, workspace, and monitor from Hyprland command socket."""
        ws_data, win_data = await asyncio.gather(
            self._query_json("activeworkspace"),
            self._query_json("activewindow"),
        )
        updated = False
        if isinstance(ws_data, dict):
            ws_name = ws_data.get("name") or ws_data.get("id")
            if ws_name is not None and str(ws_name).strip():
                self.active_workspace = str(ws_name).strip()
                updated = True
            mon = ws_data.get("monitor")
            if isinstance(mon, str) and mon.strip():
                self.active_monitor = mon.strip()
                updated = True
            if updated:
                self.context.record_workspace(self.active_workspace, self.active_monitor)

        if isinstance(win_data, dict) and (win_data.get("address") or win_data.get("class") or win_data.get("title")):
            addr = _normalize_address(win_data.get("address", ""))
            w_class = _clean_text(win_data.get("class", ""), 80)
            w_title = _clean_text(win_data.get("title", ""), 100)
            ws_obj = win_data.get("workspace")
            if isinstance(ws_obj, dict):
                ws_name = ws_obj.get("name") or ws_obj.get("id")
                if ws_name is not None and str(ws_name).strip():
                    self.active_workspace = str(ws_name).strip()
            self.active_window = {"class": w_class, "title": w_title, "address": addr}
            self.context.record_window(
                window_class=w_class,
                title=w_title,
                address=addr,
                workspace=self.active_workspace,
                monitor=self.active_monitor,
            )
            updated = True
        return updated

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._listen_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _listen_loop(self) -> None:
        while self._running:
            sock_file = self.socket_path
            if not sock_file.exists():
                await asyncio.sleep(2.0)
                continue
            try:
                reader, writer = await asyncio.open_unix_connection(str(sock_file))
                log.info("Connected to Hyprland event socket: %s", sock_file)
                await self.refresh_snapshot()
                while self._running:
                    line_bytes = await reader.readline()
                    if not line_bytes:
                        break
                    line = line_bytes.decode("utf-8", errors="replace").strip()
                    if ">>" in line:
                        event, _, data = line.partition(">>")
                        self._handle_event(event, data)
                writer.close()
                await writer.wait_closed()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.debug("Hyprland socket reconnecting: %s", e)
                await asyncio.sleep(2.0)

    def _handle_event(self, event: str, data: str) -> None:
        now = time.monotonic()
        if event == "activewindow":
            w_class, _, title = data.partition(",")
            w_class = _clean_text(w_class, 80)
            title = _clean_text(title, 100)
            self._last_aw_at = now
            if not w_class and not title:
                self.active_window = {}
                self.context.clear_window()
                return
            addr = self.active_window.get("address", "") if (now - self._last_v2_at) <= 0.05 else ""
            self.active_window = {"class": w_class, "title": title, "address": addr}
            self.context.record_window(
                window_class=w_class,
                title=title,
                address=addr,
                workspace=self.active_workspace,
                monitor=self.active_monitor,
            )
        elif event == "activewindowv2":
            addr = _normalize_address(data)
            self._last_v2_at = now
            if not addr:
                self.active_window = {}
                self.context.clear_window()
                return
            if (now - self._last_aw_at) <= 0.05 or addr == _normalize_address(self.active_window.get("address", "")):
                self.active_window["address"] = addr
            else:
                self.active_window = {"class": "", "title": "", "address": addr}
            self.context.record_window(
                window_class=self.active_window.get("class", ""),
                title=self.active_window.get("title", ""),
                address=addr,
                workspace=self.active_workspace,
                monitor=self.active_monitor,
            )
        elif event == "windowtitlev2":
            raw_addr, _, title = data.partition(",")
            addr = _normalize_address(raw_addr)
            if addr and addr == _normalize_address(self.active_window.get("address", "")):
                self.active_window["title"] = _clean_text(title, 100)
                self.context.record_window(
                    window_class=self.active_window.get("class", ""),
                    title=self.active_window["title"],
                    address=addr,
                    workspace=self.active_workspace,
                    monitor=self.active_monitor,
                )
        elif event == "workspace":
            ws = _clean_text(data, 40)
            if ws:
                self.active_workspace = ws
                self.context.record_workspace(ws, self.active_monitor)
        elif event == "workspacev2":
            _, _, ws_name = data.partition(",")
            ws = _clean_text(ws_name or data, 40)
            if ws:
                self.active_workspace = ws
                self.context.record_workspace(ws, self.active_monitor)
        elif event == "focusedmon":
            mon, _, ws = data.partition(",")
            mon = _clean_text(mon, 40)
            ws = _clean_text(ws, 40)
            if mon:
                self.active_monitor = mon
            if ws:
                self.active_workspace = ws
            self.context.record_monitor(self.active_monitor, self.active_workspace)
        elif event == "focusedmonv2":
            parts = data.split(",", 2)
            mon = _clean_text(parts[0], 40) if parts else ""
            ws = _clean_text(parts[2] if len(parts) > 2 else (parts[1] if len(parts) > 1 else ""), 40)
            if mon:
                self.active_monitor = mon
            if ws:
                self.active_workspace = ws
            self.context.record_monitor(self.active_monitor, self.active_workspace)
        elif event == "movewindowv2":
            parts = data.split(",", 2)
            addr = _normalize_address(parts[0]) if parts else ""
            ws = _clean_text(parts[2] if len(parts) > 2 else "", 40)
            if addr and addr == _normalize_address(self.active_window.get("address", "")) and ws:
                self.active_workspace = ws
                self.context.record_window(
                    window_class=self.active_window.get("class", ""),
                    title=self.active_window.get("title", ""),
                    address=addr,
                    workspace=ws,
                    monitor=self.active_monitor,
                )
        elif event == "closewindow":
            addr = _normalize_address(data)
            if addr and addr == _normalize_address(self.active_window.get("address", "")):
                self.active_window = {}
                self.context.clear_window(addr)
