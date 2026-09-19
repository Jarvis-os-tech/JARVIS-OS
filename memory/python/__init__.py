"""
JARVIS Memory System — Public API
All memory operations go through this single entry point.

Usage:
    from jarvis_memory import memory
    # or: from friday_memory import memory (backward compatibility alias)

    memory.vault.get_memory()              # Read MEMORY.md
    memory.vault.log_conversation(...)     # Log dialog
    memory.engine.store_node(...)          # Store to SQLite
    memory.engine.search_nodes("query")    # FTS5 search
    memory.hermes.sync()                   # Import Hermes memory
    memory.agents.store("hermes", ...)     # Agent-scoped memory
    memory.agents.build_context("hermes")  # Build agent context
    memory.miner.mine_conversation(...)    # Extract memories
    memory.status()                        # Full system status
"""
from typing import List, Dict, Any, Optional
from .engine import MemoryEngine
from .vault import VaultManager
from .hermes_bridge import HermesBridge
from .agent_memory import AgentMemory
from .miner import MemoryMiner
from .cognee_bridge import CogneeBridge, cognee_bridge
from .config import DB_PATH, VAULT_ROOT, DEFAULT_AGENT_ID
from .types import (
    MemoryNode, ConversationTurn, Session,
    KnowledgeTriple, DiaryEntry, EventMesh,
)


class JarvisMemory:
    """
    Unified memory system for JARVIS OS.

    Components:
      .engine  — SQLite database (structured storage)
      .vault   — Obsidian Markdown vault (human-readable)
      .hermes  — Read-only bridge from Hermes long-term memory
      .agents  — Per-agent memory namespaces
      .miner   — Rule-based memory extraction from conversations
    """

    _instance = None

    @classmethod
    def get_instance(cls) -> "JarvisMemory":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        # Core components
        self.engine = MemoryEngine(DB_PATH)
        self.vault = VaultManager()
        self.hermes = HermesBridge(self.engine)
        self.agents = AgentMemory(self.engine, self.vault)
        self.miner = MemoryMiner(self.engine)
        self.cognee = CogneeBridge.get_instance()

        # Bootstrap daily session
        self.vault.init_daily_session()

    # ─── Convenience Methods ─────────────────────────────────────────────

    def log_turn(self, speaker: str, text: str, role: str = "user",
                 agent_id: str = DEFAULT_AGENT_ID):
        """
        Log a conversation turn to vault (Markdown), engine (SQLite),
        and Cognee (Knowledge Graph).
        """
        import time

        # 1. Log to Obsidian vault
        self.vault.log_conversation(speaker, text)

        # 2. Log to SQLite with single continuous session
        turn = ConversationTurn(
            session_id="continuous",
            role=role,
            content=text.strip(),
        )
        self.engine.store_turn(turn)

        # 3. Non-blocking sync to Cognee Knowledge Graph
        if hasattr(self, "cognee") and self.cognee.is_available():
            self.cognee.remember(
                f"{speaker}: {text.strip()}",
                dataset_name="jarvis_dialogue",
                metadata={"role": role, "speaker": speaker, "agent_id": agent_id, "session": "continuous"}
            )

    def get_recent_conversation_turns(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Get recent dialogue turns from the continuous conversation."""
        turns = self.engine.get_recent_turns(limit=limit)
        results = [
            {
                "id": t.id,
                "role": "agent" if t.role in ("assistant", "agent") else "user",
                "speaker": "JARVIS" if t.role in ("assistant", "agent") else "User (Gopi)",
                "text": t.content,
                "timestamp": t.created_at,
            }
            for t in turns
        ]
        return results

    def get_continuous_dialogue_summary(self, max_turns: int = 15) -> str:
        """Format recent continuous dialogue turns for injecting into prompt context."""
        turns = self.get_recent_conversation_turns(limit=max_turns)
        if not turns:
            return "Continuous conversation active. No previous turns logged yet."
        lines = []
        for t in turns:
            role_label = "Operator Gopi" if t["role"] == "user" else "JARVIS"
            lines.append(f"[{role_label}]: {t['text']}")
        return "\n".join(lines)

    def search(self, query: str, limit: int = 10):
        """Search across SQLite FTS, vault files, and Cognee Knowledge Graph."""
        db_results = self.engine.search_nodes(query, limit=limit)
        vault_results = self.vault.search_vault(query, limit=limit)
        cognee_results = self.cognee.recall(query, limit=limit) if hasattr(self, "cognee") and self.cognee.is_available() else []
        return {
            "db": [{"id": n.id, "kind": n.kind, "content": n.content[:300],
                     "tier": n.tier, "agent": n.agent_id} for n in db_results],
            "vault": vault_results,
            "cognee": cognee_results,
        }

    def get_context_for_prompt(self, agent_id: str = DEFAULT_AGENT_ID) -> str:
        """
        Build the full memory context string for a system prompt.
        Combines: MEMORY.md + USER.md + facts + agent context + continuous conversation history.
        """
        parts = []

        # Core memory
        mem = self.vault.get_memory()
        if mem:
            parts.append(f"=== PERSISTENT KNOWLEDGE (MEMORY.md) ===\n{mem}")

        user = self.vault.get_user_profile()
        if user:
            parts.append(f"=== OPERATOR PROFILE (USER.md) ===\n{user}")

        facts = self.vault.get_facts()
        if facts:
            parts.append(f"=== VERIFIED FACTS ===\n{facts}")

        # Agent-specific context
        agent_ctx = self.agents.build_context(agent_id)
        if agent_ctx:
            parts.append(f"=== AGENT MEMORY ({agent_id}) ===\n{agent_ctx}")

        # Continuous Living Conversation Context
        recent_dialogue = self.get_continuous_dialogue_summary(max_turns=15)
        parts.append(
            f"=== 🔄 CONTINUOUS LIVING CONVERSATION CONTEXT ===\n"
            f"You are in a single, perpetual, unbroken conversation with your operator Gopi.\n"
            f"There are NO isolated sessions. You remember all preceding context, questions, and tasks.\n"
            f"Recent dialogue history:\n{recent_dialogue}"
        )

        return "\n\n".join(parts)

    def status(self):
        """Full memory system status."""
        return {
            "engine": self.engine.get_stats(),
            "vault": self.vault.get_status(),
            "hermes": self.hermes.get_hermes_status(),
            "agents": self.agents.get_agent_stats(),
            "cognee": self.cognee.status() if hasattr(self, "cognee") else {},
        }


# ─── Backward-Compatibility Alias ────────────────────────────────────────
FridayMemory = JarvisMemory

# ─── Singleton Instance ─────────────────────────────────────────────────
jarvis_memory = JarvisMemory.get_instance()
memory = jarvis_memory
