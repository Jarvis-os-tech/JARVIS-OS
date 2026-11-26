"""Unified Asynchronous Background Task Manager for JARVIS OS.

Enables concurrent task execution while maintaining an unblocked, responsive
voice conversation loop. Long-running operations, delegated tasks, and tools
detached during user speech execute in the background and report events
through the background announcement bus.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
import time
from typing import Any, Callable, Coroutine
import uuid

log = logging.getLogger("jarvis.background_tasks")

MAX_RETAINED_TASKS = 64
MAX_OUTPUT_BUFFER = 16000


@dataclass
class BackgroundTask:
    id: str
    name: str
    description: str
    tool: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    status: str = "queued"  # queued, running, completed, failed, cancelled
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    progress: str = ""
    progress_percent: float | None = None
    latest_output: str = ""
    result: Any | None = None
    error: str | None = None
    detached: bool = False
    notified: bool = False
    _asyncio_task: asyncio.Task | None = field(default=None, repr=False)

    @property
    def elapsed_seconds(self) -> float:
        if self.started_at is None:
            return 0.0
        end = self.completed_at if self.completed_at is not None else time.time()
        return max(0.0, end - self.started_at)

    def summary(self) -> str:
        if self.status == "completed":
            if isinstance(self.result, dict):
                msg = self.result.get("summary") or self.result.get("message") or self.result.get("text")
                if msg:
                    return str(msg)[:300]
            elif isinstance(self.result, str) and self.result.strip():
                return self.result.strip()[:300]
            return f"Completed in {self.elapsed_seconds:.1f}s."
        elif self.status == "failed":
            return f"Failed: {self.error or 'Unknown error'}."
        elif self.status == "cancelled":
            return "Task was cancelled."
        elif self.status == "running":
            prog = f" ({self.progress})" if self.progress else ""
            return f"Running for {self.elapsed_seconds:.1f}s{prog}."
        return "Queued."

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "tool": self.tool,
            "arguments": self.arguments,
            "status": self.status,
            "created_at": datetime.fromtimestamp(self.created_at, tz=timezone.utc).isoformat(),
            "started_at": datetime.fromtimestamp(self.started_at, tz=timezone.utc).isoformat() if self.started_at else None,
            "completed_at": datetime.fromtimestamp(self.completed_at, tz=timezone.utc).isoformat() if self.completed_at else None,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "progress": self.progress,
            "progress_percent": self.progress_percent,
            "latest_output": self.latest_output[-1000:],
            "result": self.result,
            "error": self.error,
            "detached": self.detached,
            "notified": self.notified,
            "summary": self.summary(),
        }


class BackgroundTaskManager:
    """Manages independent background tasks running concurrently with LiveVoice."""

    def __init__(self, max_retained: int = MAX_RETAINED_TASKS):
        self._tasks: dict[str, BackgroundTask] = {}
        self._events: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=128)
        self._pending_notices: dict[str, dict[str, Any]] = {}
        self._max_retained = max_retained
        self._lock = asyncio.Lock()

    def submit(
        self,
        name: str,
        description: str,
        target: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
        tool: str = "",
        arguments: dict[str, Any] | None = None,
        detached: bool = False,
        **kwargs: Any,
    ) -> BackgroundTask:
        """Submit a coroutine target to execute concurrently in the background."""
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        task = BackgroundTask(
            id=task_id,
            name=name or tool or "background_task",
            description=description or f"Task {name or tool}",
            tool=tool,
            arguments=arguments or {},
            detached=detached,
        )
        self._tasks[task_id] = task

        async_task = asyncio.create_task(
            self._run_task(task, target, *args, **kwargs),
            name=f"jarvis-bg-{task_id}",
        )
        task._asyncio_task = async_task

        self._prune_old_tasks()
        log.info("Started background task %s: '%s'", task_id, task.description)
        return task

    def submit_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None,
        execute_fn: Callable[[str, dict[str, Any] | None], Coroutine[Any, Any, Any]],
        description: str | None = None,
        detached: bool = False,
    ) -> BackgroundTask:
        """Submit an arbitrary tool execution to run in the background."""
        desc = description or self._format_tool_description(name, arguments)
        return self.submit(
            name=name,
            description=desc,
            target=execute_fn,
            name_arg=name,
            arguments_arg=arguments or {},
            tool=name,
            arguments=arguments or {},
            detached=detached,
        )

    def register_in_flight(
        self,
        name: str,
        arguments: dict[str, Any] | None,
        running_task: asyncio.Task,
        description: str | None = None,
    ) -> BackgroundTask:
        """Adopt an already-running asyncio.Task and detach it to the background."""
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        desc = description or self._format_tool_description(name, arguments)
        task = BackgroundTask(
            id=task_id,
            name=name,
            description=desc,
            tool=name,
            arguments=arguments or {},
            status="running",
            started_at=time.time(),
            detached=True,
            _asyncio_task=running_task,
        )
        self._tasks[task_id] = task

        # Attach completion callback
        running_task.add_done_callback(
            lambda fut, t=task: self._handle_adopted_completion(t, fut)
        )
        log.info("Adopted and detached in-flight tool %s to background task %s: '%s'", name, task_id, desc)
        return task

    def _handle_adopted_completion(self, task: BackgroundTask, fut: asyncio.Future) -> None:
        task.completed_at = time.time()
        if fut.cancelled():
            task.status = "cancelled"
            log.info("Detached background task %s was cancelled", task.id)
        elif fut.exception() is not None:
            task.status = "failed"
            task.error = str(fut.exception())
            log.warning("Detached background task %s failed: %s", task.id, task.error)
        else:
            task.status = "completed"
            task.result = fut.result()
            log.info("Detached background task %s completed successfully", task.id)

        self._enqueue_notification(task)

    async def _run_task(
        self,
        task: BackgroundTask,
        target: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        task.status = "running"
        task.started_at = time.time()
        try:
            # Check if name_arg / arguments_arg were forwarded for tool dispatch
            if "name_arg" in kwargs and "arguments_arg" in kwargs:
                n = kwargs.pop("name_arg")
                a = kwargs.pop("arguments_arg")
                result = await target(n, a, *args, **kwargs)
            else:
                result = await target(*args, **kwargs)
            task.result = result
            task.status = "completed"
            log.info("Background task %s (%s) finished successfully in %.2fs", task.id, task.name, task.elapsed_seconds)
        except asyncio.CancelledError:
            task.status = "cancelled"
            log.info("Background task %s (%s) was cancelled", task.id, task.name)
            raise
        except Exception as exc:
            task.status = "failed"
            task.error = str(exc)
            log.warning("Background task %s (%s) failed after %.2fs: %s", task.id, task.name, task.elapsed_seconds, exc)
        finally:
            task.completed_at = time.time()
            self._enqueue_notification(task)

    def _enqueue_notification(self, task: BackgroundTask) -> None:
        notice_id = f"bg-task:{task.id}"
        notice_text = f'Background task "{task.description}" {task.status}. {task.summary()}'
        self._pending_notices[notice_id] = {
            "id": notice_id,
            "task_id": task.id,
            "text": notice_text,
            "timestamp": time.time(),
        }

    def _format_tool_description(self, name: str, args: dict[str, Any] | None) -> str:
        args = args or {}
        if name in ("start_hermes_goal", "start_agent_goal", "create_task_agent"):
            task_txt = args.get("task") or args.get("goal") or args.get("description") or ""
            return f"Agent goal: {task_txt}" if task_txt else f"Agent delegation ({name})"
        elif name == "start_task":
            desc = args.get("description") or "Multi-step filesystem task"
            return str(desc)
        elif name == "task_submit":
            goal = args.get("goal") or "Coding and execution task"
            return str(goal)[:100]
        elif name in ("execute_system_command", "run_in_terminal", "shell"):
            cmd = args.get("command") or args.get("cmd") or ""
            return f"System command: {cmd}" if cmd else "System command execution"
        elif name.startswith("api_anything_"):
            return f"API operation: {name.removeprefix('api_anything_')}"
        elif name in ("web_search", "internet_search"):
            q = args.get("query") or ""
            return f"Web search for: {q}" if q else "Web search"
        elif name == "execute_domain_tool":
            domain = args.get("domain", "")
            tname = args.get("tool_name", "")
            return f"{domain}.{tname} execution"
        return f"{name.replace('_', ' ').capitalize()} task"

    def update_progress(self, task_id: str, progress: str, percent: float | None = None, output_chunk: str = "") -> bool:
        task = self._tasks.get(task_id)
        if not task or task.status not in ("queued", "running"):
            return False
        if progress:
            task.progress = progress
        if percent is not None:
            task.progress_percent = max(0.0, min(100.0, float(percent)))
        if output_chunk:
            task.latest_output = (task.latest_output + output_chunk)[-MAX_OUTPUT_BUFFER:]
        return True

    def cancel(self, task_id: str) -> bool:
        """Cancel a running background task."""
        task = self._tasks.get(task_id)
        if not task or task.status in ("completed", "failed", "cancelled"):
            return False
        task.status = "cancelled"
        if task._asyncio_task and not task._asyncio_task.done():
            task._asyncio_task.cancel()
        task.completed_at = time.time()
        self._enqueue_notification(task)
        log.info("Cancelled background task %s", task_id)
        return True

    def status(self, task_id: str) -> dict[str, Any] | None:
        task = self._tasks.get(task_id)
        return task.to_dict() if task else None

    def list_tasks(self, status: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return [t.to_dict() for t in tasks[:limit]]

    def active_tasks(self) -> list[BackgroundTask]:
        return [t for t in self._tasks.values() if t.status in ("queued", "running")]

    def get_active_summary(self) -> str:
        """Human-readable summary of running tasks for prompt injection or spoken awareness."""
        active = self.active_tasks()
        if not active:
            return ""
        if len(active) == 1:
            t = active[0]
            prog = f", progress: {t.progress}" if t.progress else ""
            return f'1 active background task: "{t.description}" (ID: {t.id}, running for {t.elapsed_seconds:.0f}s{prog})'
        parts = [f'"{t.description}" ({t.id}, {t.elapsed_seconds:.0f}s)' for t in active[:3]]
        extra = f" and {len(active) - 3} more" if len(active) > 3 else ""
        return f"{len(active)} active background tasks: {', '.join(parts)}{extra}"

    def events(self) -> list[dict[str, Any]]:
        """Return pending unacknowledged completion events for spoken delivery."""
        notices = list(self._pending_notices.values())
        # Sort oldest first for natural delivery order
        notices.sort(key=lambda n: n.get("timestamp", 0))
        return notices[:10]

    def acknowledge_event(self, notice_id: str) -> bool:
        if notice_id in self._pending_notices:
            notice = self._pending_notices.pop(notice_id)
            task_id = notice.get("task_id")
            if task_id and task_id in self._tasks:
                self._tasks[task_id].notified = True
            return True
        return False

    def _prune_old_tasks(self) -> None:
        finished = [t for t in self._tasks.values() if t.status in ("completed", "failed", "cancelled")]
        if len(finished) > self._max_retained:
            finished.sort(key=lambda t: t.completed_at or t.created_at)
            for t in finished[: len(finished) - self._max_retained]:
                self._tasks.pop(t.id, None)


# Global singleton instance
_GLOBAL_MANAGER: BackgroundTaskManager | None = None


def get_background_task_manager() -> BackgroundTaskManager:
    global _GLOBAL_MANAGER
    if _GLOBAL_MANAGER is None:
        _GLOBAL_MANAGER = BackgroundTaskManager()
    return _GLOBAL_MANAGER


def reset_background_task_manager() -> BackgroundTaskManager:
    global _GLOBAL_MANAGER
    _GLOBAL_MANAGER = BackgroundTaskManager()
    return _GLOBAL_MANAGER
