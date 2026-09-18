"""
JARVIS Memory System — Data Types
All data classes matching the SQLite schema and in-memory representations.
"""

from dataclasses import dataclass, field
from typing import Optional, List
import time
import uuid


def _now_ms() -> int:
    return int(time.time() * 1000)


def _new_id(prefix: str = "mem") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ─── Memory Node (core unit) ────────────────────────────────────────────────

@dataclass
class MemoryNode:
    id: str = field(default_factory=_new_id)
    kind: str = "fact"           # fact|insight|instruction|profile|decision
    tier: int = 0                # 0=working, 1=knowledge, 2=persistent
    content: str = ""
    summary: Optional[str] = None
    parent_id: Optional[str] = None
    tree_level: int = 0
    importance: float = 0.5
    superseded_by: Optional[str] = None
    agent_id: Optional[str] = None
    session_id: Optional[str] = None
    source: str = "auto"         # auto|user|hermes|miner|system_init
    metadata_json: Optional[str] = None
    created_at: int = field(default_factory=_now_ms)
    updated_at: int = field(default_factory=_now_ms)


# ─── Conversation Turn ───────────────────────────────────────────────────────

@dataclass
class ConversationTurn:
    id: str = field(default_factory=lambda: _new_id("turn"))
    session_id: str = ""
    role: str = "user"           # user|assistant|system
    content: str = ""
    tool_name: Optional[str] = None
    tool_call_json: Optional[str] = None
    turn_index: int = 0
    token_count: Optional[int] = None
    created_at: int = field(default_factory=_now_ms)


# ─── Session ─────────────────────────────────────────────────────────────────

@dataclass
class Session:
    id: str = field(default_factory=lambda: _new_id("sess"))
    started_at: int = field(default_factory=_now_ms)
    ended_at: Optional[int] = None
    title: Optional[str] = None
    turn_count: int = 0
    summary: Optional[str] = None
    metadata_json: Optional[str] = None


# ─── Knowledge Triple (subject-predicate-object) ──────────────────────────────

@dataclass
class KnowledgeTriple:
    id: str = field(default_factory=lambda: _new_id("kt"))
    subject: str = ""
    predicate: str = ""
    object: str = ""
    valid_from: int = field(default_factory=_now_ms)
    valid_to: Optional[int] = None
    confidence: float = 0.8
    source_node_id: Optional[str] = None
    source: str = "auto"
    agent_id: Optional[str] = None
    metadata_json: Optional[str] = None
    created_at: int = field(default_factory=_now_ms)


# ─── Diary Entry ─────────────────────────────────────────────────────────────

@dataclass
class DiaryEntry:
    id: str = field(default_factory=lambda: _new_id("diary"))
    agent_id: str = "jarvis-prime"
    session_id: Optional[str] = None
    entry_type: str = "reflection"   # reflection|observation|milestone|error
    content: str = ""
    tags_json: Optional[str] = None
    created_at: int = field(default_factory=_now_ms)


# ─── Event Mesh (cross-agent events) ────────────────────────────────────────

@dataclass
class EventMesh:
    id: str = field(default_factory=lambda: _new_id("evt"))
    event_type: str = ""
    source_agent: str = ""
    target_agent: Optional[str] = None
    payload_json: str = "{}"
    status: str = "pending"      # pending|processed|failed
    created_at: int = field(default_factory=_now_ms)
    processed_at: Optional[int] = None
