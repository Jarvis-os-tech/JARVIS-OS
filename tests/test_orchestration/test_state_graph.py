"""Tests for StateGraph, typed working memory, and cyclic retry loops in multi-agent orchestration."""
import asyncio
import pytest
from harness.agent_orchestrator import AgentOrchestrator
from harness.state_graph import TeamStateGraph, EdgeAction


def test_state_graph_data_structures():
    graph = TeamStateGraph(
        team_id="team-test-01",
        goal="Build feature X",
        workspace="/tmp/test",
        total_assignments=2,
        max_retries_per_stage=1,
    )
    assert graph.state == "queued"
    assert graph.total_assignments == 2

    # Record step 0 success
    graph.record_step(
        job_id="job-01",
        agent="hermes",
        index=0,
        prompt="Design spec",
        state="completed",
        output="Architecture spec completed with diagrams.",
    )
    assert len(graph.history) == 1
    assert "stage_0_hermes" in graph.artifacts

    # Edge evaluation for step 0
    edge = graph.evaluate_edge(0, "completed")
    assert edge == EdgeAction.PROCEED

    # Final step completion
    graph.record_step(
        job_id="job-02",
        agent="claude",
        index=1,
        prompt="Implement code",
        state="completed",
        output="Code implemented.",
    )
    edge_final = graph.evaluate_edge(1, "completed")
    assert edge_final == EdgeAction.COMPLETE


def test_state_graph_retry_loops():
    graph = TeamStateGraph(
        team_id="team-test-02",
        goal="Test failure recovery",
        workspace="/tmp/test",
        total_assignments=1,
        max_retries_per_stage=1,
    )

    # First attempt fails
    edge1 = graph.evaluate_edge(0, "failed")
    assert edge1 == EdgeAction.RETRY
    assert graph.retry_counts[0] == 1

    # Context should now include retry diagnostic instructions
    ctx = graph.build_node_context(
        {"agent": "claude", "prompt": "Fix bug"},
        index=0,
        is_retry=True,
        last_failure_output="SyntaxError on line 42",
    )
    assert "CRITIQUE / SELF-HEAL LOOP" in ctx
    assert "SyntaxError on line 42" in ctx

    # Second failure exceeds max_retries (budget is 1 retry)
    edge2 = graph.evaluate_edge(0, "failed")
    assert edge2 == EdgeAction.FAIL


@pytest.mark.asyncio
async def test_team_orchestrator_state_graph_retries(tmp_path):
    """Test that AgentOrchestrator loops back to self-heal upon failure when retries are enabled."""
    call_counts = {"claude": 0}

    def mock_command_builder(agent, executable, prompt, model=None):
        call_counts[agent] = call_counts.get(agent, 0) + 1
        # First call fails, second call succeeds
        if call_counts[agent] == 1:
            return ["python3", "-c", "import sys; sys.stderr.write('Transformed defect detected'); sys.exit(1)"]
        return ["python3", "-c", "import sys; print('Defect resolved after critique loop'); sys.exit(0)"]

    orch = AgentOrchestrator(
        executables={"claude": "/bin/true"},
        command_builder=mock_command_builder
    )

    team_res = orch.delegate_team(
        goal="Self-Healing Loop Test",
        assignments=[
            {"agent": "claude", "prompt": "Implement code with validation"},
        ],
        workspace=str(tmp_path),
        timeout_seconds=30,
        max_retries_per_stage=1,
    )
    team_id = team_res["team"]["id"]

    worker = orch.team_workers.get(team_id)
    if worker:
        await worker

    status = orch.team_status(team_id)
    assert status["team"]["state"] == "completed"
    assert len(status["team"]["jobs"]) == 2  # 1 initial failed attempt + 1 successful retry
    assert call_counts["claude"] == 2

    # Verify StateGraph records
    graph_dict = status["team"]["state_graph"]
    assert graph_dict["state"] == "completed"
    assert len(graph_dict["history"]) == 2
    assert graph_dict["history"][0]["state"] == "failed"
    assert graph_dict["history"][1]["state"] == "completed"
    assert "stage_0_claude" in graph_dict["artifacts"]

    await orch.close()
