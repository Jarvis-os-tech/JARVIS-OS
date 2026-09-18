"""
Dual-Store Memory Engine for J.A.R.V.I.S. Python Core Engine.

This module is a thin backward-compatible wrapper that delegates all
memory operations to the unified memory package.

All actual logic lives in friday-memory/:
  config.py       — paths and constants
  types.py        — dataclasses
  engine.py       — SQLite engine
  vault.py        — Obsidian vault I/O
  hermes_bridge.py — Hermes memory sync
  agent_memory.py — per-agent namespaces
  miner.py        — rule-based extraction
  __init__.py     — public API
"""

import sys
import os
from typing import List, Dict, Any, Optional

# Add memory/vault (or fallback jarvis-memory / friday-memory) to Python path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_memory_vault_candidates = [
    os.path.join(_project_root, "memory", "python"),
    os.path.join(_project_root, "memory", "vault"),
    os.path.join(_project_root, "jarvis-memory"),
    os.path.join(_project_root, "friday-memory"),
]
_jarvis_memory_path = next((p for p in _memory_vault_candidates if os.path.exists(p)), os.path.join(_project_root, "memory", "python"))

if _jarvis_memory_path not in sys.path:
    sys.path.insert(0, os.path.dirname(_jarvis_memory_path))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Import the unified memory system as jarvis_memory and friday_memory
import importlib
import importlib.util

# 1. Register jarvis_memory
_jm_spec = importlib.util.spec_from_file_location(
    "jarvis_memory",
    os.path.join(_jarvis_memory_path, "__init__.py"),
    submodule_search_locations=[_jarvis_memory_path]
)
_jm_module = importlib.util.module_from_spec(_jm_spec)
sys.modules["jarvis_memory"] = _jm_module

MEMORY_SUBMODULES = ("config", "types", "engine", "vault", "hermes_bridge", "agent_memory", "miner", "cognee_bridge")
for submod in MEMORY_SUBMODULES:
    sub_spec = importlib.util.spec_from_file_location(
        f"jarvis_memory.{submod}",
        os.path.join(_jarvis_memory_path, f"{submod}.py"),
        submodule_search_locations=[_jarvis_memory_path]
    )
    sub_module = importlib.util.module_from_spec(sub_spec)
    sys.modules[f"jarvis_memory.{submod}"] = sub_module
    sub_spec.loader.exec_module(sub_module)
    setattr(_jm_module, submod, sub_module)

_jm_spec.loader.exec_module(_jm_module)

# 2. Register friday_memory as backward-compatibility alias
sys.modules["friday_memory"] = _jm_module
for submod in MEMORY_SUBMODULES:
    sys.modules[f"friday_memory.{submod}"] = sys.modules[f"jarvis_memory.{submod}"]

from jarvis_memory import JarvisMemory, FridayMemory


class DualStoreMemory:
    """
    Backward-compatible wrapper around FridayMemory.
    All existing code (prompt_engine, server, gemini_live, actuator_dispatcher)
    imports `memory_engine` from this module. This wrapper ensures they keep working.
    """

    _instance = None

    @classmethod
    def get_instance(cls) -> "DualStoreMemory":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._fm = FridayMemory.get_instance()
        self._cached_snapshot: Optional[Dict[str, Any]] = None

    # ─── Delegated Properties ────────────────────────────────────────────

    @property
    def engine(self):
        return self._fm.engine

    @property
    def vault(self):
        return self._fm.vault

    @property
    def hermes(self):
        return self._fm.hermes

    @property
    def agents(self):
        return self._fm.agents

    @property
    def miner(self):
        return self._fm.miner

    @property
    def cognee(self):
        return getattr(self._fm, "cognee", None)

    # ─── Backward-Compatible API ─────────────────────────────────────────

    def init_daily_session(self) -> str:
        return self._fm.vault.init_daily_session()

    def log_conversation_turn(self, speaker: str, text: str, role: str = "user") -> None:
        self._fm.log_turn(speaker, text, role=role)

    def log_tool_execution(self, tool_name: str, args: Dict[str, Any],
                           result: Dict[str, Any], duration_ms: float = 0.0) -> None:
        self._fm.vault.log_execution(tool_name, args, result, duration_ms)

    def get_memory_notes(self) -> str:
        return self._fm.vault.get_memory()

    def get_user_profile(self) -> str:
        return self._fm.vault.get_user_profile()

    def get_vault_facts_content(self) -> str:
        return self._fm.vault.get_facts()

    def get_vault_knowledge_summary(self) -> str:
        return self._fm.vault.get_knowledge()

    def get_vault_skills_summary(self) -> str:
        # Skills scanning — inline simple version
        import re
        skills_candidates = [
            os.path.join(_project_root, "memory", "vault", "skills"),
            os.path.join(_project_root, "jarvis-memory", "skills"),
            os.path.join(_project_root, "friday-memory", "skills"),
        ]
        skills_dir = next((p for p in skills_candidates if os.path.exists(p)), "")
        if not skills_dir:
            return ""
        skills = []
        for root, _, files in os.walk(skills_dir):
            for f in files:
                if f.lower() == "skill.md":
                    fpath = os.path.join(root, f)
                    parent = os.path.basename(root)
                    try:
                        with open(fpath, "r") as sf:
                            sc = sf.read()
                        dm = re.search(r"description:\s*[\"']?([^\"'\n]+)", sc, re.IGNORECASE)
                        desc = dm.group(1).strip() if dm else f"Skill: {parent}"
                        skills.append(f"- **{parent}**: {desc}")
                    except Exception:
                        skills.append(f"- **{parent}**: Skill module")
        return "\n".join(skills[:40])

    def get_recent_conversations_summary(self, max_days: int = 3) -> str:
        return self._fm.vault.get_recent_conversations(max_days=max_days)

    def get_sqlite_facts(self, limit: int = 20) -> List[Dict[str, Any]]:
        # Map new memory_nodes to old format for compatibility
        nodes = self._fm.engine.get_nodes_by_kind("fact", limit=limit)
        return [
            {
                "id": n.id,
                "category": n.kind,
                "key": n.content[:50],
                "value": n.content,
                "source": n.source,
                "updated_at": str(n.updated_at),
            }
            for n in nodes
        ]

    def save_memory_fact(self, key: str, value: str, category: str = "custom",
                         source: str = "user_added"):
        # Store in new engine
        from jarvis_memory.types import MemoryNode
        node = MemoryNode(
            kind="fact",
            tier=2,  # Persistent
            content=f"{key}: {value}",
            importance=0.7,
            source=source,
        )
        self._fm.engine.store_node(node)
        # Also write vault fact
        self._fm.vault.save_fact(key, value, category=category, source=source)
        # Also store in Cognee Knowledge Graph
        if hasattr(self._fm, "cognee") and self._fm.cognee and self._fm.cognee.is_available():
            self._fm.cognee.remember(f"{key}: {value}", metadata={"category": category, "source": source})
        self._cached_snapshot = None

    def search(self, query: str, limit: int = 8) -> List[Dict[str, Any]]:
        result = self._fm.search(query, limit=limit)
        return result.get("db", []) + result.get("vault", []) + result.get("cognee", [])

    def get_frozen_snapshot(self, force_refresh: bool = False) -> Dict[str, Any]:
        if self._cached_snapshot is not None and not force_refresh:
            return self._cached_snapshot

        formatted_prompt = self._fm.get_context_for_prompt()

        self._cached_snapshot = {
            "user_content": self._fm.vault.get_user_profile(),
            "memory_content": self._fm.vault.get_memory(),
            "vault_facts": self._fm.vault.get_facts(),
            "vault_skills": self.get_vault_skills_summary(),
            "formatted_prompt": formatted_prompt,
            "timestamp": __import__("time").time(),
        }
        return self._cached_snapshot

    def get_vault_status(self) -> Dict[str, Any]:
        vault_st = self._fm.vault.get_status()
        today = vault_st.get("today", "")
        cognee_st = self._fm.cognee.status() if hasattr(self._fm, "cognee") and self._fm.cognee else {}
        return {
            "vault_root": vault_st.get("vault_root", ""),
            "status": "connected",
            "today_conversation_file": f"conversations/{today}.md",
            "total_facts_indexed": vault_st.get("total_facts", 0),
            "total_skills_indexed": len(self.get_vault_skills_summary().splitlines()) if self.get_vault_skills_summary() else 0,
            "total_conversations_logged": vault_st.get("total_conversations", 0),
            "cognee": cognee_st,
            **vault_st,
            "full_status": self._fm.status(),
        }


# ─── Singleton (backward-compatible export) ──────────────────────────────
memory_engine = DualStoreMemory.get_instance()
