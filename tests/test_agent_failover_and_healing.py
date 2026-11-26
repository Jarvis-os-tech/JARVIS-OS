"""Verification tests for autonomous agent failover, fallback, and delegation self-healing.

Covers:
1. Failover error pattern detection (ECONNREFUSED, usage limit, 429, etc.).
2. Autonomous failover execution in AgentOrchestrator for Claude ECONNREFUSED and Codex usage limit.
3. Chained failovers and fallback candidate selection with health cooldowns.
4. Autonomous developer fallback in personas.software_assignments.
5. AutoHealer.heal_delegation_failures on delegations.sqlite3 ledgers and live jobs.
6. AutoHealer.test_job_watchdog for hung/zombie test and delegation jobs.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sqlite3
import tempfile
import time
import pytest

from harness.agent_orchestrator import (
    AGENTS,
    AgentOrchestrator,
    detect_failover_reason,
)
from harness.personas import (
    PERSONAS,
    AGENT_FALLBACK_CANDIDATES,
    get_fallback_candidates,
    software_assignments,
)
from kernel.self_healer import AutoHealer, HealResult


# ==============================================================================
# 1. ERROR PATTERN DETECTION TESTS
# ==============================================================================

def test_detect_failover_reason_claude_econnrefused():
    claude_err = "API Error: Connection refused \u2014 a firewall or proxy may be blocking it (ECONNREFUSED)\n"
    reason = detect_failover_reason(claude_err, exit_code=1)
    assert reason == "connection_refused"


def test_detect_failover_reason_codex_usage_limit():
    codex_err = (
        "OpenAI Codex v0.166.0\n"
        "ERROR: You\u2019ve hit your usage limit. Upgrade to Pro (https://chatgpt.com/explore/pro), "
        "visit https://chatgpt.com/settings/usage to purchase more credits or try again at Nov 9th, 2026 10:25 PM.\n"
    )
    reason = detect_failover_reason(codex_err, exit_code=1)
    assert reason == "quota_limit"


def test_detect_failover_reason_rate_limit_and_429():
    assert detect_failover_reason("ClientError: 429 Too Many Requests") == "quota_limit"
    assert detect_failover_reason("Rate limit exceeded. Please retry later.") == "quota_limit"
    assert detect_failover_reason("insufficient_quota error from API") == "quota_limit"


def test_detect_failover_reason_clean_output():
    assert detect_failover_reason("All unit tests passed successfully.", exit_code=0) is None
    assert detect_failover_reason("", exit_code=1) is None


# ==============================================================================
# 2. PERSONAS FALLBACK & ASSIGNMENT TESTS
# ==============================================================================

def test_personas_fallback_candidates():
    candidates = get_fallback_candidates('claude')
    assert 'opencode' in candidates
    assert 'gemini' in candidates
    assert 'hermes' in candidates

    codex_candidates = get_fallback_candidates('codex')
    assert 'claude' in codex_candidates
    assert 'opencode' in codex_candidates


def test_software_assignments_fallback_when_claude_unhealthy():
    executables = {'hermes': '/bin/hermes', 'opencode': '/bin/opencode', 'claude': '/bin/claude'}
    # Normal case: claude is healthy
    normal = software_assignments(executables)
    assert normal[1]['agent'] == 'claude'
    assert normal[3]['agent'] == 'claude'

    # Unhealthy claude case: only hermes and opencode are healthy
    fallback = software_assignments(executables, healthy_agents={'hermes', 'opencode'})
    assert fallback[1]['agent'] == 'opencode'
    assert fallback[3]['agent'] == 'opencode'


# ==============================================================================
# 3. AGENT ORCHESTRATOR AUTONOMOUS FAILOVER TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_orchestrator_failover_claude_econnrefused_to_opencode(tmp_path):
    """When Claude fails with ECONNREFUSED, orchestrator auto-heals and fails over to opencode."""
    attempts = []

    def mock_builder(agent, executable, prompt, model=None):
        attempts.append(agent)
        if agent == 'claude':
            # Fail with real Claude ECONNREFUSED message
            return [
                "python3", "-c",
                "import sys; "
                "sys.stderr.write('API Error: Connection refused \u2014 a firewall or proxy may be blocking it (ECONNREFUSED)\\n'); "
                "sys.exit(1)"
            ]
        elif agent == 'opencode':
            # Succeed on opencode
            return [
                "python3", "-c",
                "import sys; print('OpenCode task completed successfully'); sys.exit(0)"
            ]
        return ["python3", "-c", "import sys; sys.exit(0)"]

    orch = AgentOrchestrator(
        executables={'claude': '/bin/claude', 'opencode': '/bin/opencode', 'gemini': '/bin/gemini'},
        command_builder=mock_builder
    )

    res = orch.delegate('claude', 'Build payment webhook validator', str(tmp_path), timeout_seconds=30)
    job_id = res['job']['id']

    # Wait for completion
    worker = orch.workers.get(job_id)
    if worker:
        await worker

    status = orch.status(job_id)
    job = status['job']
    assert job['state'] == 'completed'
    assert job['auto_healed'] is True
    assert job['agent'] == 'opencode'
    assert job['initial_agent'] == 'claude'
    assert len(job['failover_history']) == 1
    assert job['failover_history'][0]['agent'] == 'claude'
    assert job['failover_history'][0]['reason'] == 'connection_refused'
    assert 'OpenCode task completed successfully' in job['output']
    assert '[Auto-Healing]' in job['output']

    # Verify claude was marked in cooldown
    assert orch.is_agent_healthy('claude') is False
    assert orch.is_agent_healthy('opencode') is True

    await orch.close()


@pytest.mark.asyncio
async def test_orchestrator_failover_codex_usage_limit_to_gemini(tmp_path):
    """When Codex fails with usage limit, orchestrator auto-heals and fails over to gemini."""
    def mock_builder(agent, executable, prompt, model=None):
        if agent == 'codex':
            return [
                "python3", "-c",
                "import sys; "
                "sys.stderr.write('ERROR: You’ve hit your usage limit. Upgrade to Pro\\n'); "
                "sys.exit(1)"
            ]
        elif agent == 'gemini':
            return [
                "python3", "-c",
                "import sys; print('Gemini research completed'); sys.exit(0)"
            ]
        return ["python3", "-c", "import sys; sys.exit(0)"]

    orch = AgentOrchestrator(
        executables={'codex': '/bin/codex', 'gemini': '/bin/gemini'},
        command_builder=mock_builder
    )

    res = orch.delegate('codex', 'Implement search indexer', str(tmp_path), timeout_seconds=30)
    job_id = res['job']['id']

    worker = orch.workers.get(job_id)
    if worker:
        await worker

    status = orch.status(job_id)
    job = status['job']
    assert job['state'] == 'completed'
    assert job['auto_healed'] is True
    assert job['agent'] == 'gemini'
    assert len(job['failover_history']) == 1
    assert job['failover_history'][0]['reason'] == 'quota_limit'
    assert 'Gemini research completed' in job['output']

    await orch.close()


@pytest.mark.asyncio
async def test_orchestrator_chained_failovers_exhaustion(tmp_path):
    """When all candidate agents fail with quota/connection errors, job cleanly marks failed."""
    def mock_builder(agent, executable, prompt, model=None):
        return [
            "python3", "-c",
            "import sys; sys.stderr.write('ECONNREFUSED connecting to upstream\\n'); sys.exit(1)"
        ]

    orch = AgentOrchestrator(
        executables={'claude': '/bin/claude', 'opencode': '/bin/opencode'},
        command_builder=mock_builder
    )

    res = orch.delegate('claude', 'Chained failure test', str(tmp_path), timeout_seconds=30)
    job_id = res['job']['id']

    worker = orch.workers.get(job_id)
    if worker:
        await worker

    status = orch.status(job_id)
    job = status['job']
    assert job['state'] == 'failed'
    # Both claude and opencode were attempted
    attempted = [h['agent'] for h in job['failover_history']] + [job['agent']]
    assert 'claude' in attempted
    assert 'opencode' in attempted

    await orch.close()


# ==============================================================================
# 4. DELEGATION SELF-HEALING & WATCHDOG TESTS
# ==============================================================================

def test_auto_healer_delegation_failures_on_sqlite(tmp_path):
    """Verify AutoHealer scans delegations.sqlite3, diagnoses ECONNREFUSED and quota, and heals records."""
    db_file = tmp_path / "delegations.sqlite3"
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE jobs (id TEXT PRIMARY KEY, request_key TEXT UNIQUE, fingerprint TEXT, data TEXT)")

    job_claude = {
        "id": "job-claude-01",
        "agent": "claude",
        "state": "failed",
        "output": "API Error: Connection refused \u2014 a firewall or proxy may be blocking it (ECONNREFUSED)\n",
    }
    job_codex = {
        "id": "job-codex-02",
        "agent": "codex",
        "state": "failed",
        "output": "ERROR: You’ve hit your usage limit. Upgrade to Pro\n",
    }
    conn.execute("INSERT INTO jobs VALUES(?, ?, ?, ?)", ("job-claude-01", "req-1", "fp-1", json.dumps(job_claude)))
    conn.execute("INSERT INTO jobs VALUES(?, ?, ?, ?)", ("job-codex-02", "req-2", "fp-2", json.dumps(job_codex)))
    conn.commit()
    conn.close()

    results = AutoHealer.heal_delegation_failures(db_path=db_file)
    assert len(results) == 2
    assert all(r.success for r in results)
    assert any("claude" in r.issue for r in results)
    assert any("codex" in r.issue for r in results)

    # Verify records in database were updated with healing annotations
    conn = sqlite3.connect(str(db_file))
    row1 = conn.execute("SELECT data FROM jobs WHERE id='job-claude-01'").fetchone()[0]
    data1 = json.loads(row1)
    assert data1.get("healed") is True
    assert "opencode" in data1.get("failover_candidate")

    row2 = conn.execute("SELECT data FROM jobs WHERE id='job-codex-02'").fetchone()[0]
    data2 = json.loads(row2)
    assert data2.get("healed") is True
    conn.close()


def test_auto_healer_test_job_watchdog(tmp_path):
    """Verify test_job_watchdog detects hung ledger jobs and resets them to timed_out."""
    db_file = tmp_path / "delegations.sqlite3"
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE jobs (id TEXT PRIMARY KEY, request_key TEXT UNIQUE, fingerprint TEXT, data TEXT)")

    stuck_job = {
        "id": "stuck-test-check-01",
        "agent": "opencode",
        "state": "running",
        "updated_at": time.time() - 500,  # 500 seconds ago
        "output": "Running comprehensive tests...",
    }
    conn.execute("INSERT INTO jobs VALUES(?, ?, ?, ?)", ("stuck-test-check-01", "req-stuck", "fp-stuck", json.dumps(stuck_job)))
    conn.commit()
    conn.close()

    watchdog_results = AutoHealer.test_job_watchdog(max_duration_seconds=100.0, db_path=db_file)
    assert len(watchdog_results) >= 1
    assert watchdog_results[0].success
    assert "timed_out" in watchdog_results[0].action_taken

    # Check updated database record
    conn = sqlite3.connect(str(db_file))
    row = conn.execute("SELECT data FROM jobs WHERE id='stuck-test-check-01'").fetchone()[0]
    data = json.loads(row)
    assert data["state"] == "timed_out"
    assert data["watchdog_recovered"] is True
    conn.close()


def test_auto_healer_action_dispatch():
    """Verify composite remediation dispatcher routes delegation alerts."""
    res_del = AutoHealer.auto_heal_action("delegation_failure", "orchestrator")
    # Might be None or HealResult depending on local delegations.sqlite3
    res_wd = AutoHealer.auto_heal_action("test_job_stalled", "test_runner")
    # Should not raise exception
