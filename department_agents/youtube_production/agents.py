"""Specialist ownership for the JARVIS YouTube Production Department."""
from dataclasses import dataclass


@dataclass(frozen=True)
class YouTubeProductionAgent:
    name: str
    stage: str


AGENTS = (
    YouTubeProductionAgent("Channel Strategist", "strategy"),
    YouTubeProductionAgent("Topic Researcher", "research"),
    YouTubeProductionAgent("Telugu Script Writer", "script"),
    YouTubeProductionAgent("Fact and Rights Reviewer", "evidence"),
    YouTubeProductionAgent("Storyboard Agent", "storyboard"),
    YouTubeProductionAgent("Voice and Audio Agent", "audio"),
    YouTubeProductionAgent("Visual Production Agent", "visuals"),
    YouTubeProductionAgent("Video Assembly Agent", "assembly"),
    YouTubeProductionAgent("Thumbnail Agent", "thumbnail"),
    YouTubeProductionAgent("SEO Agent", "metadata"),
    YouTubeProductionAgent("Quality Reviewer", "quality"),
    YouTubeProductionAgent("Approval Manager", "approval"),
    YouTubeProductionAgent("Publisher Agent", "publishing"),
    YouTubeProductionAgent("Analytics and Learning Agent", "learning"),
)

AGENT_NAMES = tuple(agent.name for agent in AGENTS)
