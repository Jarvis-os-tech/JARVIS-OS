"""CLI-Agent department: bounded ownership over existing integration tools."""

from .agents import AGENTS, AGENT_BY_TOOL, AGENT_NAMES, CLIAgent
from .department import CLIAgentDepartment

__all__ = ["AGENTS", "AGENT_BY_TOOL", "AGENT_NAMES", "CLIAgent", "CLIAgentDepartment"]
