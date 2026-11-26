"""Tests for Bitemporal Cognitive Self-Healing Memory and Deterministic Staleness Detectors."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
import time
import pytest

from memory.store import Fact, LocalFactStore
from memory.staleness_detector import (
    ClarificationRequest,
    KeyCollisionDetector,
    OsRealityDetector,
    StalenessIssue,
    TemporalDecayDetector,
    TtlDetector,
    add_pending_clarification,
    get_pending_clarifications,
    resolve_clarification,
    scan_memory_staleness,
)
from kernel.self_healer import AutoHealer


@pytest.fixture
def temp_store(tmp_path: Path) -> LocalFactStore:
    jsonl_path = tmp_path / "test_facts.jsonl"
    return LocalFactStore(path=jsonl_path)


def test_bitemporal_fact_defaults():
    now = time.time()
    f = Fact(text="User prefers dark mode", created_at=now, trust="trusted")
    assert f.is_active is True
    assert f.trusted_for_recall is True
    assert f.status == "active"
    assert f.valid_to is None
    assert f.confidence == 1.0


def test_bitemporal_fact_expiration():
    past = time.time() - 3600
    future = time.time() + 3600

    expired_fact = Fact(text="Temporary pass", created_at=past - 7200, valid_to=past, trust="trusted")
    assert expired_fact.is_active is False
    assert expired_fact.trusted_for_recall is False

    active_fact = Fact(text="Future pass", created_at=past, valid_to=future, trust="trusted")
    assert active_fact.is_active is True
    assert active_fact.trusted_for_recall is True


def test_ttl_detector_various_patterns():
    now = 1700000000.0  # reference epoch

    # 1. "expires 2023-01-01" (in past relative to reference epoch)
    f1 = Fact(text="License key expires 2023-01-01", created_at=now - 86400 * 300)
    issue1 = TtlDetector.check_fact(f1, 0, now=now)
    assert issue1 is not None
    assert issue1.detector == "ttl"
    assert issue1.suggested_action == "close"

    # 2. "for the next 2 hours" where 3 hours have passed
    f2 = Fact(text="Do not disturb for the next 2 hours", created_at=now - 3 * 3600)
    issue2 = TtlDetector.check_fact(f2, 1, now=now)
    assert issue2 is not None
    assert issue2.suggested_action == "close"

    # 3. "today only" where created 2 days ago
    f3 = Fact(text="Special task priority today only", created_at=now - 2 * 86400)
    issue3 = TtlDetector.check_fact(f3, 2, now=now)
    assert issue3 is not None
    assert issue3.suggested_action == "close"

    # 4. "for now" (24h temporary) where created 48h ago
    f4 = Fact(text="Using temporary proxy for now", created_at=now - 48 * 3600)
    issue4 = TtlDetector.check_fact(f4, 3, now=now)
    assert issue4 is not None

    # 5. Future unexpired TTL should NOT trigger
    f5 = Fact(text="Visitor pass for the next 5 hours", created_at=now - 3600)
    issue5 = TtlDetector.check_fact(f5, 4, now=now)
    assert issue5 is None


def test_key_collision_detector_supersession():
    now = time.time()
    f1 = Fact(
        text="User prefers dark mode",
        created_at=now - 10000,
        entity_key="preference:theme",
        status="active",
    )
    f2 = Fact(
        text="User switched to light mode for reading",
        created_at=now - 100,
        entity_key="preference:theme",
        status="active",
    )

    issues = KeyCollisionDetector.check_collisions([f1, f2])
    assert len(issues) == 1
    issue = issues[0]
    assert issue.detector == "key_collision"
    assert issue.suggested_action == "supersede"
    assert issue.safe_to_auto_heal is True
    assert issue.colliding_text == f2.text


def test_key_collision_detector_ambiguous_escalation():
    now = time.time()
    # Two conflicting preferences created nearly at the same time without transition language
    f1 = Fact(
        text="User prefers neovim",
        created_at=now - 20,
        entity_key="preference:editor",
        status="active",
    )
    f2 = Fact(
        text="User prefers emacs",
        created_at=now - 10,
        entity_key="preference:editor",
        status="active",
    )

    issues = KeyCollisionDetector.check_collisions([f1, f2])
    assert len(issues) == 1
    issue = issues[0]
    assert issue.detector == "key_collision"
    assert issue.suggested_action == "escalate"
    assert issue.safe_to_auto_heal is False
    assert "conflicting entries" in issue.clarification_prompt.lower()


def test_os_reality_detector(tmp_path: Path):
    # 1. Missing path assertion
    missing_file = "/etc/jarvis/definitely_nonexistent_config_file_98234.yaml"
    f1 = Fact(text=f"Configuration stored at {missing_file}")
    issue1 = OsRealityDetector.check_fact(f1, 0)
    assert issue1 is not None
    assert issue1.detector == "os_reality"
    assert issue1.suggested_action == "close"
    assert missing_file in issue1.reason

    # 2. Existing real path should NOT be flagged
    real_file = tmp_path / "active_config.json"
    real_file.write_text("{}", encoding="utf-8")
    f2 = Fact(text=f"Configuration stored at {real_file}")
    issue2 = OsRealityDetector.check_fact(f2, 1)
    assert issue2 is None


def test_temporal_decay_detector():
    now = time.time()

    # 1. Ephemeral status from 60 days ago (half-life 2 days -> decayed to ~0)
    f_status = Fact(
        text="Currently investigating bug with audio latency",
        created_at=now - 60 * 86400,
        last_verified_at=now - 60 * 86400,
        confidence=1.0,
    )
    issue_status = TemporalDecayDetector.check_fact(f_status, 0, now=now)
    assert issue_status is not None
    assert issue_status.suggested_action == "close"
    assert issue_status.new_confidence < 0.35

    # 2. Core preference from 10 days ago (half-life 365 days -> confidence ~0.98)
    f_pref = Fact(
        text="User prefers Python for scripting",
        created_at=now - 10 * 86400,
        last_verified_at=now - 10 * 86400,
        confidence=1.0,
    )
    issue_pref = TemporalDecayDetector.check_fact(f_pref, 1, now=now)
    # Should not be marked for closure
    assert issue_pref is None or issue_pref.suggested_action != "close"


def test_local_fact_store_bitemporal_operations(temp_store: LocalFactStore):
    now = time.time()

    # Add facts
    assert temp_store.add("Fact 1: Lives in Seattle", entity_key="user:location")
    assert temp_store.add("Fact 2: Temporary pass for today only")
    assert temp_store.count() == 2

    # Verify active facts
    assert len(temp_store.active_facts()) == 2

    # Close fact without deleting ("Nothing is ever deleted, only closed")
    temp_store.close_fact(0, reason="relocated")
    assert temp_store.count() == 2  # still persisted in audit log!
    assert len(temp_store.active_facts()) == 1

    history = temp_store.history("user:location")
    assert len(history) == 1
    assert history[0].status == "relocated"
    assert history[0].valid_to is not None

    # Supersede fact
    temp_store.supersede(1, "Fact 3: Permanent pass issued", entity_key="user:pass")
    assert temp_store.count() == 3  # old fact retained, new fact added
    active = temp_store.active_facts()
    assert len(active) == 1
    assert active[0].text == "Fact 3: Permanent pass issued"


def test_auto_healer_heal_memory_staleness(temp_store: LocalFactStore, tmp_path: Path):
    now = time.time()
    clarification_file = tmp_path / "clarifications.json"

    # Add a TTL-expired fact
    temp_store.add("Temporary access code valid until 2020-01-01")

    # Add an OS reality invalidated fact
    fake_path = "/etc/jarvis/nonexistent_test_spec_77192.json"
    temp_store.add(f"Config path: {fake_path}")

    # Add an ambiguous contradiction
    temp_store.add("User prefers bash for all scripts", entity_key="preference:shell")
    temp_store.add("User prefers zsh for all scripts", entity_key="preference:shell")

    # Patch clarification path for test
    from memory import staleness_detector
    orig_path_fn = staleness_detector._clarifications_path
    staleness_detector._clarifications_path = lambda: clarification_file
    try:
        repairs = AutoHealer.heal_memory_staleness(fact_store=temp_store, now=now)
        assert len(repairs) >= 3

        # Check that expired facts were closed
        active_texts = [f.text for f in temp_store.active_facts()]
        assert "Temporary access code valid until 2020-01-01" not in active_texts
        assert f"Config path: {fake_path}" not in active_texts

        # Check that clarification was queued
        clarifications = get_pending_clarifications(path=clarification_file)
        assert len(clarifications) == 1
        assert clarifications[0].entity_key == "preference:shell"
    finally:
        staleness_detector._clarifications_path = orig_path_fn
