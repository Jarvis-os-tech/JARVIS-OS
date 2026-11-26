"""Explicit tool ownership for the CLI-Agent department."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

Dispatch = Callable[[str, dict], Awaitable[dict]]


@dataclass(frozen=True)
class CLIAgent:
    name: str
    tools: frozenset[str]

    async def execute(self, tool: str, arguments: dict, dispatch: Dispatch) -> dict:
        if tool not in self.tools:
            raise ValueError(f"{self.name} cannot execute tool: {tool}")
        return await dispatch(tool, arguments)


AGENTS = (
    CLIAgent("CLI Harness Agent", frozenset({
        "cli_hub_list", "cli_hub_search", "cli_hub_info", "cli_hub_install",
        "cli_hub_uninstall", "cli_hub_launch", "cli_hub_matrix_list",
        "cli_hub_matrix_preflight", "cli_hub_matrix_install",
        "delegate_agent",
    })),
    CLIAgent("API Discovery Agent", frozenset({
        "api_anything_search", "api_anything_list_operations", "api_anything_call",
        "api_anything_propose", "api_anything_learn", "integration_service_status",
    })),
    CLIAgent("Platform Connection Agent", frozenset({
        "open_platform_authorization", "check_platform_connection", "connect_platform",
        "execute_platform_action", "list_connected_platforms", "disconnect_platform",
        "composio_connection_status", "composio_authorize", "composio_search_tools",
        "composio_execute_tool",
    })),
    CLIAgent("Retrieval Agent", frozenset({
        "reach_search", "reach_read", "reach_transcript", "reach_status",
    })),
)
AGENT_BY_TOOL = {tool: agent for agent in AGENTS for tool in agent.tools}
AGENT_NAMES = [agent.name for agent in AGENTS]
