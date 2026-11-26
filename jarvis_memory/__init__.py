"""Sovereign memory engine for JARVIS OS."""
from __future__ import annotations

from .config import Config, MemoryConfig, load_config
from .paths import DEFAULT_CONFIG_DIR, get_config_dir
from .scanner import InjectionScanner
from .store import Fact, LocalFactStore
from .staleness_detector import (
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
from .chunking import chunk_text, ChunkConfig
from .knowledge import KnowledgeStore
from .vector_store import VectorStore
from .embeddings import (
    EmbeddingError,
    EmbeddingProvider,
    GeminiEmbeddingProvider,
    OllamaEmbeddingProvider,
    StaticEmbeddingProvider,
    DeterministicFakeEmbeddingProvider,
)
from .bridge import MemoryBridge, MemoryError
from .skills import MemorySkills, DesktopSkills, SkillError
from .service_facade import UniversalMemoryService
from .importers import SiblingSessionImporter

__all__ = [
    "Config",
    "MemoryConfig",
    "load_config",
    "DEFAULT_CONFIG_DIR",
    "get_config_dir",
    "InjectionScanner",
    "LocalFactStore",
    "Fact",
    "StalenessIssue",
    "ClarificationRequest",
    "TtlDetector",
    "KeyCollisionDetector",
    "OsRealityDetector",
    "TemporalDecayDetector",
    "scan_memory_staleness",
    "get_pending_clarifications",
    "add_pending_clarification",
    "resolve_clarification",
    "chunk_text",
    "ChunkConfig",
    "KnowledgeStore",
    "VectorStore",
    "EmbeddingError",
    "EmbeddingProvider",
    "GeminiEmbeddingProvider",
    "OllamaEmbeddingProvider",
    "StaticEmbeddingProvider",
    "DeterministicFakeEmbeddingProvider",
    "MemoryBridge",
    "MemoryError",
    "MemorySkills",
    "DesktopSkills",
    "SkillError",
    "UniversalMemoryService",
    "SiblingSessionImporter",
]
