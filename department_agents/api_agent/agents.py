"""Service-bounded agents for the API Agent department."""
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

Dispatch = Callable[[str, dict], Awaitable[dict]]


@dataclass(frozen=True)
class APIAgent:
    name: str
    role: str
    tools: frozenset[str]

    async def execute(self, tool: str, arguments: dict, dispatch: Dispatch) -> dict:
        if tool not in self.tools:
            raise ValueError(f"{self.name} cannot execute tool: {tool}")
        return await dispatch(tool, arguments)


AGENTS = (
    APIAgent(
        "API Blueprint Agent",
        "Proposes structured API blueprints from web problems using Gemini 2.5 Flash.",
        frozenset({"api_anything_propose"}),
    ),
    APIAgent(
        "API Reverse Engineering Agent",
        "Learns API operations via traffic capture and validates them with NVIDIA NIM.",
        frozenset({"api_anything_learn"}),
    ),
    APIAgent(
        "API Execution Agent",
        "Executes verified learned API calls across sites with idempotency and safety bounds.",
        frozenset({"api_anything_call"}),
    ),
    APIAgent(
        "Omarchy API Daemon",
        "Lightweight background bridge connecting api-anything MCP with Gemini 2.5 Flash and NVIDIA NIM.",
        frozenset({
            "api_anything_search", "api_anything_list_operations", "api_anything_call",
            "api_anything_propose", "api_anything_learn",
        }),
    ),
)

AGENT_BY_TOOL = {tool: agent for agent in AGENTS for tool in agent.tools}
AGENT_NAMES = [agent.name for agent in AGENTS]
