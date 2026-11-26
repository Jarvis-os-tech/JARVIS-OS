import json

import pytest

from departments.youtube_production import AGENT_NAMES, YouTubeProductionDepartment, YouTubeProductionError
from skills import DesktopSkills
from orchestration.model_routes import ModelJobs


def _draft(department, episode_id, suffix="one"):
    return department.stage_draft(
        episode_id,
        script=f"తెలుగులో జార్విస్ అప్డేట్ {suffix}",
        title=f"JARVIS Telugu Update {suffix}",
        description="ఈ వారం నిర్మించిన మార్పుల సంక్షిప్త వివరణ.",
        sources=["https://example.com/source"],
        storyboard=["Hook", "Build demonstration", "Summary"],
        thumbnail_prompt="JARVIS hologram with Telugu title",
    )


def test_durable_review_revision_and_exact_approval(tmp_path):
    department = YouTubeProductionDepartment(tmp_path)
    brief = department.create_brief("JARVIS weekly progress")
    episode_id = brief["episode_id"]

    first = _draft(department, episode_id)
    first_hash = first["draft"]["review_hash"]
    assert first["status"] == "review_required"
    assert first["revision"] == 1
    assert YouTubeProductionDepartment(tmp_path).status(episode_id)["status"] == "review_required"

    department.request_changes(episode_id, "Shorten the hook")
    second = _draft(department, episode_id)
    assert second["episode_id"] == episode_id
    assert second["revision"] == 2
    assert second["draft"]["review_hash"] != first_hash

    with pytest.raises(YouTubeProductionError, match="does not match"):
        department.approve(episode_id, first_hash)

    approved = department.approve(episode_id, second["draft"]["review_hash"])
    assert approved["status"] == "approved"
    assert approved["publishing_enabled"] is False
    saved = json.loads((tmp_path / "episodes" / f"{episode_id}.json").read_text())
    assert saved["approval"]["publishing_enabled"] is False


def test_invalid_transitions_and_paths_do_not_mutate_state(tmp_path):
    department = YouTubeProductionDepartment(tmp_path)
    episode_id = department.create_brief("A topic")["episode_id"]
    before = department.status(episode_id)

    with pytest.raises(YouTubeProductionError, match="does not have a staged draft"):
        department.review_package(episode_id)
    with pytest.raises(YouTubeProductionError, match="Invalid episode ID"):
        department.status("../../etc/passwd")
    with pytest.raises(YouTubeProductionError, match="staged review"):
        department.approve(episode_id, "wrong")

    assert department.status(episode_id) == before


@pytest.mark.asyncio
async def test_registered_tools_and_agent_catalog(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    desktop = DesktopSkills()
    try:
        declarations = {item["name"] for item in desktop.declarations}
        assert {
            "youtube_production_create_brief", "youtube_production_stage_draft",
            "youtube_production_status", "youtube_production_review_package",
            "youtube_production_pending_reviews", "youtube_production_request_changes",
            "youtube_production_approve",
        } <= declarations
        assert not {"youtube_production_publish", "youtube_production_schedule"} & declarations

        created = await desktop.execute("youtube_production_create_brief", {
            "topic": "JARVIS daily update", "format": "short", "language": "te",
        })
        assert created["status"] == "idea"
        prompts = []

        async def generate(model, prompt):
            prompts.append(prompt)
            return json.dumps({"review_notes": "Confirm the recording rights."} if len(prompts) == 2 else {
                "script": "ఈ రోజు జార్విస్ గురించి చూద్దాం.", "title": "జార్విస్ అప్‌డేట్",
                "description": "జార్విస్ డెమో", "thumbnail_prompt": "Jarvis dashboard",
                "gemini_prompt": "Use the provided dashboard recording", "storyboard": ["Show the dashboard"],
            })

        desktop._model_jobs = ModelJobs(None, desktop.task_events, generate=generate)
        queued = await desktop.execute("youtube_production_prepare_draft", {
            "episode_id": created["episode_id"], "sources": ["Verified notes: dashboard recording exists."],
        })
        assert queued["status"] == "preparing_draft", queued
        await desktop._youtube_draft_jobs[created["episode_id"]]
        reviewed = await desktop.execute("youtube_production_review_package", {
            "episode_id": created["episode_id"],
        })
        assert reviewed["status"] == "review_required", reviewed
        assert reviewed["draft"]["video_path"] is None
        assert reviewed["draft"]["gemini_prompt"] == "Use the provided dashboard recording"
        assert reviewed["draft"]["review_notes"] == "Confirm the recording rights."
        assert len(prompts) == 2
        catalog = await desktop.execute("list_system_agents", {})
        members = [agent["name"] for agent in catalog["agents"]
                   if agent.get("department") == "YouTube Production"]
        assert tuple(members) == AGENT_NAMES
        assert catalog["department_counts"]["YouTube Production"] == len(AGENT_NAMES)
    finally:
        await desktop.close_agent_jobs()
