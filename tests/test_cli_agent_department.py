import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from departments.cli_agent import AGENTS, CLIAgentDepartment


def test_nim_plan_uses_primary_model_and_preserves_desktop_target(monkeypatch):
    from importlib import import_module
    from types import SimpleNamespace

    from departments.cli_agent.planning import plan_connection
    client_module = import_module('departments.linkedin.nim_client')

    seen = []

    class Client:
        def __init__(self, config):
            assert config.model_primary == config.model_flagship == config.model_deep_reasoning
            assert config.max_retries == 1

        def generate(self, messages, **kwargs):
            seen.extend(messages)
            return SimpleNamespace(success=True, content='Inspect the desktop window', model='nano')

    config = SimpleNamespace(api_key='fixture-key', model_primary='nano')
    monkeypatch.setattr(client_module, 'nim_client', SimpleNamespace(cfg=config))
    monkeypatch.setattr(client_module, 'NIMClient', Client)
    assert plan_connection('Connect to the Antigravity desktop app')['model'] == 'nano'
    assert seen == [{'role': 'user', 'content': 'Connect to the Antigravity desktop app'}]
    with pytest.raises(ValueError, match='Remove credentials'):
        plan_connection('Use fixture-key')


@pytest.mark.asyncio
async def test_jarvis_lists_cli_agent_as_a_separate_department():
    from skills.skills import DesktopSkills

    desktop = DesktopSkills()
    result = await desktop.execute('list_system_agents', {})
    members = [entry for entry in result['agents'] if entry.get('department') == 'CLI Agent']
    assert result['department_counts']['CLI Agent'] == len(AGENTS)
    assert {entry['name'] for entry in members} == {agent.name for agent in AGENTS}
    assert all(entry['registered'] and entry['available'] is None for entry in members)


@pytest.mark.asyncio
async def test_failed_plan_stops_before_delegation(monkeypatch):
    from types import SimpleNamespace

    from departments.cli_agent import service
    from orchestration.evolution import EvolutionManager

    fail = AsyncMock(side_effect=ValueError('NIM unavailable'))
    monkeypatch.setattr(service, 'request', fail)
    manager = EvolutionManager.__new__(EvolutionManager)
    manager.orchestrator = SimpleNamespace()
    manager.can_run = lambda: True
    manager._snapshot = AsyncMock()
    manager._verify = AsyncMock()
    manager._save = lambda job: None
    manager._stage = AsyncMock()
    job = {'id': 'test', 'department': 'CLI Agent', 'requested_action': 'connect to app',
           'state': 'queued', 'cancel_requested': False, 'error': None}
    await manager._run(job)
    assert job['state'] == 'failed'
    assert job['error'] == 'ValueError: NIM unavailable'
    fail.assert_awaited_once_with('plan', {'request': 'connect to app'})
    manager._stage.assert_not_awaited()


@pytest.mark.asyncio
async def test_service_dispatches_a_plan_and_rejects_execution(monkeypatch):
    import asyncio
    from unittest.mock import Mock

    from departments.cli_agent import service

    planner = Mock(return_value={'model': 'nano', 'output': 'Inspect desktop'})
    monkeypatch.setattr(service, 'plan_connection', planner)
    server = service.CLIAgentService()

    async def send(operation):
        reader = asyncio.StreamReader()
        reader.feed_data(json.dumps({'operation': operation, 'arguments': {'request': 'desktop app'}}).encode() + b'\n')
        writer = Mock(drain=AsyncMock())
        await server.handle(reader, writer)
        return json.loads(writer.write.call_args.args[0])

    assert (await send('plan'))['plan']['model'] == 'nano'
    assert (await send('execute'))['ok'] is False
    planner.assert_called_once_with('desktop app')


def test_every_existing_integration_tool_has_one_owner():
    owned = [tool for agent in AGENTS for tool in agent.tools]
    assert len(owned) == len(set(owned))
    manifests = Path(__file__).resolve().parents[1] / "skill_manifests"
    expected = {
        skill["name"]
        for name in ("cli-anything", "api-anything", "composio", "agent-reach")
        for skill in json.loads((manifests / f"{name}.json").read_text())["skills"]
    }
    assert set(owned) == expected | {"delegate_agent"}


@pytest.mark.asyncio
@pytest.mark.parametrize("agent", AGENTS, ids=lambda agent: agent.name)
async def test_department_forwards_arguments_and_unverified_result_unchanged(agent):
    result = {"ok": False, "unverified": True, "error": "Authorization required"}
    dispatch = AsyncMock(return_value=result)
    tool = sorted(agent.tools)[0]
    arguments = {"request_key": "stable-key", "allow_writes": False}
    assert await CLIAgentDepartment(dispatch).execute(tool, arguments) is result
    dispatch.assert_awaited_once_with(tool, arguments)


@pytest.mark.asyncio
async def test_desktop_routes_antigravity_through_cli_department(monkeypatch, tmp_path):
    from skills.skills import DesktopSkills

    desktop = DesktopSkills()
    dispatch = AsyncMock(return_value={"status": "queued"})
    monkeypatch.setattr(desktop, "_execute_validated", dispatch)
    handler = AsyncMock(wraps=CLIAgentDepartment(dispatch).execute)
    monkeypatch.setattr(CLIAgentDepartment, "execute", handler)
    args = {"agent": "antigravity", "prompt": "Reply with OK only.", "workspace": str(tmp_path)}
    assert await desktop.execute("delegate_agent", args) == {"status": "queued"}
    handler.assert_awaited_once_with("delegate_agent", args)


@pytest.mark.asyncio
async def test_rejects_unknown_and_other_agents_tools_before_dispatch():
    dispatch = AsyncMock()
    with pytest.raises(ValueError, match="does not own tool"):
        await CLIAgentDepartment(dispatch).execute("execute_shell", {})
    with pytest.raises(ValueError, match="cannot execute tool"):
        await AGENTS[0].execute("reach_read", {}, dispatch)
    dispatch.assert_not_awaited()


@pytest.mark.asyncio
async def test_preserves_dispatch_errors():
    dispatch = AsyncMock(side_effect=RuntimeError("Permission denied"))
    with pytest.raises(RuntimeError, match="Permission denied"):
        await CLIAgentDepartment(dispatch).execute("cli_hub_launch", {"name": "gimp"})
