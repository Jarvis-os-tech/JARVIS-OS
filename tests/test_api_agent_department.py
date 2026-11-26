import pytest
from unittest.mock import AsyncMock

from department_agents.api_agent import AGENTS, AGENT_NAMES, APIAgentDepartment
from skills.skills import DesktopSkills


@pytest.mark.asyncio
async def test_jarvis_lists_api_agent_as_a_registered_department():
    desktop = DesktopSkills()
    result = await desktop.execute('list_system_agents', {})
    members = [entry for entry in result['agents'] if entry.get('department') == 'API Agent']
    assert result['department_counts']['API Agent'] == len(AGENTS) == 4
    assert {entry['name'] for entry in members} == set(AGENT_NAMES)
    assert all(entry['registered'] and entry['available'] is None for entry in members)


def test_api_agent_tools_coverage():
    all_tools = {tool for agent in AGENTS for tool in agent.tools}
    expected = {
        "api_anything_search",
        "api_anything_list_operations",
        "api_anything_call",
        "api_anything_propose",
        "api_anything_learn",
    }
    assert all_tools == expected


@pytest.mark.asyncio
async def test_api_agent_department_dispatches_tools():
    dispatch = AsyncMock(return_value={"ok": True, "results": ["weather_api"]})
    dept = APIAgentDepartment(dispatch)

    assert dept.handles("api_anything_search", {}) is True
    assert dept.handles("unknown_tool", {}) is False

    res = await dept.execute("api_anything_search", {"query": "weather"})
    assert res == {"ok": True, "results": ["weather_api"]}
    dispatch.assert_awaited_once_with("api_anything_search", {"query": "weather"})


@pytest.mark.asyncio
async def test_api_agent_department_rejects_unowned_tool():
    dispatch = AsyncMock()
    dept = APIAgentDepartment(dispatch)
    with pytest.raises(ValueError, match="does not own tool"):
        await dept.execute("cli_hub_launch", {})
    dispatch.assert_not_awaited()
