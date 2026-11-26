"""Route integration tools through their existing validated skill dispatcher."""

from .agents import AGENTS, AGENT_BY_TOOL, Dispatch


class CLIAgentDepartment:
    @staticmethod
    def handles(tool: str, arguments: dict) -> bool:
        if tool == "delegate_agent":
            return arguments.get("agent") == "antigravity"
        return tool in AGENT_BY_TOOL

    def __init__(self, dispatch: Dispatch):
        self.agents = AGENTS
        self._dispatch = dispatch

    async def execute(self, tool: str, arguments: dict) -> dict:
        agent = AGENT_BY_TOOL.get(tool)
        if agent is None or not self.handles(tool, arguments):
            raise ValueError(f"CLI-Agent department does not own tool: {tool}")
        return await agent.execute(tool, arguments, self._dispatch)
