"""Tests for concurrent background tasks and non-blocking LiveVoice execution."""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
import pytest

from kernel.background_tasks import (
    BackgroundTaskManager,
    reset_background_task_manager,
    get_background_task_manager,
)
from control.skills import UnifiedSkills
from voice.config import Config, StandbyConfig
from voice.daemon import LiveVoice
from voice.playback import Playback
from voice.speech import SpeechTurnGate


@pytest.fixture(autouse=True)
def clean_bg_manager():
    mgr = reset_background_task_manager()
    yield mgr
    reset_background_task_manager()


@pytest.fixture
def voice():
    player = Playback("default")
    v = LiveVoice(
        player,
        config=Config(standby=StandbyConfig(enabled=False)),
        speech_gate=SpeechTurnGate(silence_frames=2, tail_seconds=0.1),
    )
    v.connected = True
    v._session = SimpleNamespace(
        send_client_content=AsyncMock(),
        send_tool_response=AsyncMock(),
    )
    return v


@pytest.mark.asyncio
async def test_always_background_tools_admitted_immediately():
    """Verify that tools in VOICE_ALWAYS_BACKGROUND_TOOLS start in background immediately."""
    execute_mock = AsyncMock(return_value={"ok": True, "output": "Hermes goal done"})
    skills = UnifiedSkills()
    skills.execute = execute_mock

    # start_hermes_goal should start immediately in background
    res = await skills.start_voice_background(
        "start_hermes_goal",
        {"task": "Analyze codebase", "role": "researcher"},
    )

    assert res is not None
    assert res["ok"] is True
    assert res["status"] == "started"
    assert res["completed"] is False
    assert res["task_id"].startswith("task-")
    assert "started in the background" in res["message"]

    # The background manager should track the task
    mgr = get_background_task_manager()
    status = mgr.status(res["task_id"])
    assert status is not None
    assert status["tool"] == "start_hermes_goal"

    # Wait for background task to complete
    await asyncio.sleep(0.05)
    status_done = mgr.status(res["task_id"])
    assert status_done["status"] == "completed"


@pytest.mark.asyncio
async def test_inflight_tool_detached_when_user_speaks(voice):
    """Verify that a tool executing synchronously detaches to background when user speaks."""
    tool_finished = asyncio.Event()

    async def slow_tool_execute(name, args):
        await asyncio.sleep(0.5)
        tool_finished.set()
        return {"ok": True, "data": "Slow analysis result"}

    voice.skills = SimpleNamespace(
        declarations=[{"name": "deep_analysis"}],
        execute=slow_tool_execute,
        start_voice_background=AsyncMock(return_value=None),
    )
    voice._reply_authorized = True

    session = SimpleNamespace(send_tool_response=AsyncMock())
    call = SimpleNamespace(
        function_calls=[
            SimpleNamespace(name="deep_analysis", id="call_123", args={"query": "test"})
        ]
    )

    # Spawn handle_tools in background
    handle_task = asyncio.create_task(voice.handle_tools(call, session))

    # Simulate user speaking 0.45s into the execution
    await asyncio.sleep(0.42)
    voice._user_speaking_event.set()
    voice.gate.active = True

    # handle_tools should unblock almost immediately after user speaks
    await asyncio.wait_for(handle_task, timeout=1.0)

    # Gemini Live should have received tool response with status 'started' / detached
    session.send_tool_response.assert_awaited_once()
    responses = session.send_tool_response.call_args.kwargs["function_responses"]
    resp = responses[0].response
    assert resp["ok"] is True
    assert resp["status"] == "started"
    assert resp["result"]["detached_to_background"] is True
    task_id = resp["result"]["task_id"]
    assert "moved to the background" in resp["result"]["message"]

    # Background task should still complete in background
    await asyncio.wait_for(tool_finished.wait(), timeout=1.0)
    await asyncio.sleep(0.05)
    mgr = get_background_task_manager()
    status = mgr.status(task_id)
    assert status["status"] == "completed"


@pytest.mark.asyncio
async def test_background_task_list_and_status_through_skills():
    """Verify listing and querying background tasks via skills adapter."""
    mgr = get_background_task_manager()

    async def dummy_work():
        await asyncio.sleep(0.1)
        return "Finished work"

    task = mgr.submit("custom_job", "Custom background job", dummy_work)

    from skills.skills import DesktopSkills
    desktop = DesktopSkills()
    # Query list_tasks
    task_list = await desktop.execute("list_tasks", {})
    assert "tasks" in task_list
    assert any(t.get("id") == task.id for t in task_list["tasks"])

    # Query task_status
    st = await desktop.execute("task_status", {"task_id": task.id})
    assert st["id"] == task.id
    assert st["name"] == "custom_job"

    # Cancel task
    cancel_res = await desktop.execute("cancel_task", {"task_id": task.id})
    assert cancel_res["status"] == "cancelled"


@pytest.mark.asyncio
async def test_completion_announcement_emitted_in_background_events():
    """Verify background task completion produces notification events for spoken delivery."""
    skills = UnifiedSkills()
    mgr = get_background_task_manager()

    async def quick_job():
        return {"summary": "Compiled 42 assets"}

    task = mgr.submit("build_assets", "Asset compilation", quick_job)
    await task._asyncio_task

    # Check background events in UnifiedSkills
    events = await skills.background_events()
    assert len(events) >= 1
    bg_events = [e for e in events if e.get("id") == f"bg-task:{task.id}"]
    assert len(bg_events) == 1
    assert "completed" in bg_events[0]["text"]
    assert "Asset compilation" in bg_events[0]["text"]

    # Acknowledge event
    await skills.acknowledge_event(f"bg-task:{task.id}")
    events_after = await skills.background_events()
    assert not any(e.get("id") == f"bg-task:{task.id}" for e in events_after)
