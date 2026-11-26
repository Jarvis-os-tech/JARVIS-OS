"""Unit tests for Unified Background Task Manager in JARVIS OS."""
import asyncio
import pytest
import time

from core.background_tasks import (
    BackgroundTaskManager,
    BackgroundTask,
    get_background_task_manager,
    reset_background_task_manager,
)


@pytest.fixture
def manager():
    return BackgroundTaskManager()


@pytest.mark.asyncio
async def test_submit_successful_task(manager):
    async def sample_work(x, y):
        await asyncio.sleep(0.05)
        return x + y

    task = manager.submit("math_addition", "Adding two numbers", sample_work, 5, 10)
    assert task.status in ("queued", "running")
    assert task.id.startswith("task-")
    assert task.name == "math_addition"
    assert task.description == "Adding two numbers"

    # Wait for completion
    await task._asyncio_task
    assert task.status == "completed"
    assert task.result == 15
    assert task.elapsed_seconds > 0.04

    # Check status and list
    status = manager.status(task.id)
    assert status["status"] == "completed"
    assert status["result"] == 15
    assert "summary" in status

    listed = manager.list_tasks()
    assert len(listed) == 1
    assert listed[0]["id"] == task.id


@pytest.mark.asyncio
async def test_submit_failing_task(manager):
    async def failing_work():
        await asyncio.sleep(0.02)
        raise ValueError("Simulated computation crash")

    task = manager.submit("crash_test", "Testing failure", failing_work)
    await task._asyncio_task

    assert task.status == "failed"
    assert "Simulated computation crash" in task.error

    events = manager.events()
    assert len(events) == 1
    assert events[0]["id"] == f"bg-task:{task.id}"
    assert "failed" in events[0]["text"]

    assert manager.acknowledge_event(events[0]["id"])
    assert len(manager.events()) == 0


@pytest.mark.asyncio
async def test_cancel_task(manager):
    async def infinite_work():
        while True:
            await asyncio.sleep(0.1)

    task = manager.submit("infinite", "Long task", infinite_work)
    await asyncio.sleep(0.02)
    assert task.status == "running"

    assert manager.cancel(task.id)
    assert task.status == "cancelled"

    events = manager.events()
    assert len(events) == 1
    assert "cancelled" in events[0]["text"]


@pytest.mark.asyncio
async def test_adopt_in_flight_task(manager):
    async def running_tool():
        await asyncio.sleep(0.08)
        return {"ok": True, "output": "Done"}

    raw_task = asyncio.create_task(running_tool())
    task = manager.register_in_flight("test_tool", {"arg1": "val"}, raw_task, "Adopted tool test")
    assert task.detached is True
    assert task.status == "running"

    await raw_task
    # Allow done_callback to fire
    await asyncio.sleep(0.01)

    assert task.status == "completed"
    assert task.result == {"ok": True, "output": "Done"}
    assert len(manager.events()) == 1


@pytest.mark.asyncio
async def test_active_summary_and_progress(manager):
    async def tracked_work(task_id):
        manager.update_progress(task_id, "Step 1: Downloading", 25.0)
        await asyncio.sleep(0.05)
        manager.update_progress(task_id, "Step 2: Processing", 75.0)
        await asyncio.sleep(0.05)

    task_id = "task-preassigned"
    # Create task with known id
    task = manager.submit("downloader", "Dataset Download", tracked_work, "temp")
    summary = manager.get_active_summary()
    assert "Dataset Download" in summary

    manager.update_progress(task.id, "Step 1: Downloading", 25.0)
    summary_with_prog = manager.get_active_summary()
    assert "Step 1: Downloading" in summary_with_prog

    await task._asyncio_task
    assert manager.get_active_summary() == ""
