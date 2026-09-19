"""
Cognee Universal Memory Bridge for JARVIS-OS.

Provides an asynchronous and synchronous client to connect JARVIS-OS agents
to the centralized Cognee knowledge graph, vector store, and MCP server.

Guarantees:
- Non-blocking execution (graceful fallback if Cognee container is offline).
- Multi-agent dataset scoping (jarvis_knowledge, session_dialogue, agent_memories).
- Full support for remember (Add->Cognify), recall (Graph & Vector Search), and cognify.
"""

import os
import time
import json
import logging
import threading
from typing import Dict, Any, List, Optional

logger = logging.getLogger("jarvis.cognee_bridge")

DEFAULT_API_URL = os.environ.get("COGNEE_API_URL", "http://127.0.0.1:8020")
DEFAULT_MCP_URL = os.environ.get("COGNEE_MCP_URL", "http://127.0.0.1:8021/mcp")
DEFAULT_DATASET = os.environ.get("COGNEE_DATASET", "jarvis_knowledge")
DEFAULT_API_KEY = os.environ.get("COGNEE_API_KEY", "")
COGNEE_ENABLED = os.environ.get("COGNEE_ENABLED", "true").lower() in ("1", "true", "yes", "on")


class CogneeBridge:
    """
    Client bridge for Cognee Knowledge Graph & Semantic Memory.
    Delegates to Cognee REST API when online, safely fails over to no-op if offline.
    """

    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "CogneeBridge":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(
        self,
        api_url: str = DEFAULT_API_URL,
        mcp_url: str = DEFAULT_MCP_URL,
        default_dataset: str = DEFAULT_DATASET,
        api_key: str = DEFAULT_API_KEY,
        enabled: bool = COGNEE_ENABLED,
    ):
        self.api_url = api_url.rstrip("/")
        self.mcp_url = mcp_url
        self.default_dataset = default_dataset
        self.api_key = api_key or os.environ.get("COGNEE_API_KEY", "")
        self.enabled = enabled

        # Cached availability to prevent blocking on repeated calls when offline
        self._is_available: Optional[bool] = None
        self._last_health_check: float = 0.0
        self._health_check_ttl: float = 15.0  # re-check every 15s

    def _headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Construct standard HTTP headers with API key authentication."""
        h = {"User-Agent": "JARVIS-OS/1.0"}
        if self.api_key:
            h["X-Api-Key"] = self.api_key
        if extra:
            h.update(extra)
        return h

    def is_available(self, force: bool = False) -> bool:
        """Checks if Cognee REST API is reachable with a rapid timeout."""
        if not self.enabled:
            return False

        now = time.time()
        if not force and self._is_available is not None and (now - self._last_health_check) < self._health_check_ttl:
            return self._is_available

        try:
            import urllib.request
            req = urllib.request.Request(f"{self.api_url}/health", headers={"User-Agent": "JARVIS-OS/1.0"})
            with urllib.request.urlopen(req, timeout=0.8) as resp:
                self._is_available = (resp.status == 200)
        except Exception:
            self._is_available = False

        self._last_health_check = now
        return self._is_available

    # ─── High-Level Memory Operations ────────────────────────────────────

    def remember(
        self,
        text: str,
        dataset_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        run_cognify: bool = True,
        wait: bool = False,
    ) -> Dict[str, Any]:
        """
        Store information in Cognee.
        If wait=True: runs synchronously and returns completed result.
        If wait=False (default): fires in background thread to avoid blocking voice loop.
        """
        if not self.is_available():
            return {"success": False, "reason": "cognee_offline", "detail": "Cognee service is not reachable"}

        dataset = dataset_name or self.default_dataset

        def _do_post():
            try:
                import requests
                # Cognee 1.0+ /api/v1/remember expects form data with raw_data and datasetName
                res = requests.post(
                    f"{self.api_url}/api/v1/remember",
                    headers=self._headers(),
                    data={
                        "raw_data": [text],
                        "datasetName": dataset,
                        "run_in_background": "false" if wait else "true",
                    },
                    timeout=45.0 if wait else 5.0,
                )
                if res.status_code == 200:
                    return {"success": True, "data": res.json()}
                else:
                    logger.debug(f"Cognee remember non-200: {res.status_code} {res.text}")
                    return {"success": False, "status_code": res.status_code, "error": res.text}
            except Exception as e:
                logger.debug(f"Cognee remember error: {e}")
                return {"success": False, "error": str(e)}

        if wait:
            return _do_post()

        # Run in thread so callers (like voice turns) never stall
        t = threading.Thread(target=_do_post, daemon=True)
        t.start()
        return {"success": True, "status": "queued"}

    def recall(
        self,
        query: str,
        search_type: str = "GRAPH_COMPLETION",
        dataset_name: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve structured entities, relationships, or semantic chunks from Cognee.
        """
        if not self.is_available():
            return []

        dataset = dataset_name or self.default_dataset
        try:
            import requests
            payload = {
                "query": query,
                "datasets": [dataset] if dataset else None,
                "search_type": search_type,
                "top_k": limit,
            }
            res = requests.post(
                f"{self.api_url}/api/v1/search",
                headers=self._headers({"Content-Type": "application/json"}),
                json=payload,
                timeout=25.0,
            )
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return data.get("results", [data])
                return []
            else:
                logger.debug(f"Cognee recall error: {res.status_code} {res.text}")
                return []
        except Exception as e:
            logger.debug(f"Cognee recall error: {e}")
            return []

    def trigger_cognify_async(self, dataset_name: Optional[str] = None) -> None:
        """Asynchronously triggers graph generation and entity extraction."""
        dataset = dataset_name or self.default_dataset

        def _do_cognify():
            try:
                import urllib.request
                payload = json.dumps({"dataset_name": dataset}).encode("utf-8")
                url = f"{self.api_url}/api/v1/cognify"
                req = urllib.request.Request(
                    url,
                    data=payload,
                    headers=self._headers({"Content-Type": "application/json"}),
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10.0) as resp:
                    pass
            except Exception as e:
                logger.debug(f"Cognee cognify error: {e}")

        t = threading.Thread(target=_do_cognify, daemon=True)
        t.start()

    def sync_vault(self, vault_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Scans Obsidian vault markdown files (MEMORY.md, USER.md, facts, knowledge)
        and synchronizes them into the Cognee Knowledge Graph.
        """
        if not self.is_available():
            return {"success": False, "reason": "cognee_offline"}

        from .config import VAULT_ROOT, FACTS_DIR, MEMORY_MD, USER_MD
        target_vault = vault_path or VAULT_ROOT

        files_to_sync = []
        if os.path.exists(MEMORY_MD):
            files_to_sync.append(("MEMORY.md", MEMORY_MD, "system_memory"))
        if os.path.exists(USER_MD):
            files_to_sync.append(("USER.md", USER_MD, "user_profile"))

        if os.path.exists(FACTS_DIR):
            for f in os.listdir(FACTS_DIR):
                if f.endswith(".md"):
                    files_to_sync.append((f, os.path.join(FACTS_DIR, f), "fact"))

        synced_count = 0
        for name, path, kind in files_to_sync:
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    content = fh.read().strip()
                if content:
                    self.remember(
                        content,
                        dataset_name="jarvis_vault",
                        metadata={"filename": name, "kind": kind, "source": "obsidian_vault"},
                        run_cognify=False
                    )
                    synced_count += 1
            except Exception as e:
                logger.debug(f"Failed to sync {name}: {e}")

        # Trigger cognify on the dataset once batch ingestion is queued
        self.trigger_cognify_async("jarvis_vault")
        return {"success": True, "files_synced": synced_count, "dataset": "jarvis_vault"}

    def status(self) -> Dict[str, Any]:
        """Provides health and configuration diagnostics for Cognee."""
        is_up = self.is_available(force=True)
        return {
            "enabled": self.enabled,
            "connected": is_up,
            "api_url": self.api_url,
            "mcp_url": self.mcp_url,
            "default_dataset": self.default_dataset,
            "last_check": self._last_health_check,
            "service_type": "Docker Container (cognee/cognee + cognee/cognee-mcp)",
        }


# Global singleton instance
cognee_bridge = CogneeBridge.get_instance()
