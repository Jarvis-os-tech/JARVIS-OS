"""Durable, draft-first YouTube production workflow owned by JARVIS."""
from __future__ import annotations

from datetime import datetime
import fcntl
from functools import wraps
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any
import uuid


FORMATS = frozenset({"short", "weekly_update"})
LANGUAGES = frozenset({"te", "te-en-metadata"})
REVIEW_STATES = frozenset({"review_required", "changes_requested"})
EPISODE_ID = re.compile(r"episode_[0-9]{8}_[a-f0-9]{8}")


class YouTubeProductionError(ValueError):
    pass


def _episode_mutation(method):
    @wraps(method)
    def locked(self, episode_id, *args, **kwargs):
        with self._path(episode_id).with_suffix(".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            return method(self, episode_id, *args, **kwargs)
    return locked


class YouTubeProductionDepartment:
    def __init__(self, state_dir: Path | None = None):
        state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
        self.state_dir = state_dir or state_home / "jarvis/youtube-production"
        self.episodes_dir = self.state_dir / "episodes"
        self.episodes_dir.mkdir(parents=True, exist_ok=True)

    def create_brief(self, topic: str, *, format: str = "short",
                     audience: str = "Telugu AI builders", language: str = "te",
                     goal: str = "Explain the latest JARVIS development") -> dict[str, Any]:
        topic = topic.strip()
        if not topic or len(topic) > 300:
            raise YouTubeProductionError("Topic must contain 1 to 300 characters")
        if format not in FORMATS or language not in LANGUAGES:
            raise YouTubeProductionError("Unsupported format or language")
        now = self._now()
        episode = {
            "episode_id": f"episode_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}",
            "status": "idea",
            "revision": 0,
            "brief": {"topic": topic, "format": format, "audience": audience.strip()[:200],
                      "language": language, "goal": goal.strip()[:500]},
            "agents": {}, "draft": None, "approval": None,
            "created_at": now, "updated_at": now,
        }
        self._write(episode)
        return self._summary(episode)

    @_episode_mutation
    def stage_draft(self, episode_id: str, *, script: str, title: str,
                    description: str, sources: list[str], storyboard: list[str],
                    thumbnail_prompt: str = "", gemini_prompt: str = "",
                    review_notes: str = "", expected_update: str | None = None) -> dict[str, Any]:
        episode = self._read(episode_id)
        if expected_update is not None and episode["updated_at"] != expected_update:
            raise YouTubeProductionError("Episode changed during draft preparation")
        if episode["status"] not in {"idea", "researched", "scripted", "planned", "changes_requested"}:
            raise YouTubeProductionError(f"Cannot stage a draft from {episode['status']}")
        cleaned_sources = [item.strip() for item in sources if isinstance(item, str) and item.strip()]
        cleaned_storyboard = [item.strip() for item in storyboard if isinstance(item, str) and item.strip()]
        if not script.strip() or not title.strip() or not description.strip():
            raise YouTubeProductionError("Script, title, and description are required")
        if not cleaned_sources or not cleaned_storyboard:
            raise YouTubeProductionError("At least one source and storyboard scene are required")
        draft = {
            "script": script.strip(), "title": title.strip(), "description": description.strip(),
            "sources": cleaned_sources, "storyboard": cleaned_storyboard,
            "thumbnail_prompt": thumbnail_prompt.strip(), "video_path": None,
            "audience_setting": None, "target_channel": None,
            "gemini_prompt": gemini_prompt.strip(), "review_notes": review_notes.strip(),
            "revision": episode["revision"] + 1,
        }
        draft["review_hash"] = self._review_hash(draft)
        episode.update(status="review_required", draft=draft, approval=None,
                       revision=int(episode.get("revision", 0)) + 1, updated_at=self._now())
        episode["agents"] = {
            "Fact and Rights Reviewer": "review_required",
            "Quality Reviewer": "review_required", "Approval Manager": "waiting",
        }
        self._write(episode)
        return self.review_package(episode_id)

    def review_package(self, episode_id: str) -> dict[str, Any]:
        episode = self._read(episode_id)
        if not episode.get("draft"):
            raise YouTubeProductionError("Episode does not have a staged draft")
        return {**self._summary(episode), "brief": episode["brief"], "draft": episode["draft"],
                "agents": episode["agents"], "approval": episode["approval"]}

    def pending_reviews(self) -> dict[str, Any]:
        reviews = []
        for path in sorted(self.episodes_dir.glob("episode_*.json")):
            try:
                episode = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if episode.get("status") in REVIEW_STATES:
                reviews.append(self._summary(episode))
        return {"status": "completed", "pending_count": len(reviews), "episodes": reviews}

    @_episode_mutation
    def request_changes(self, episode_id: str, feedback: str) -> dict[str, Any]:
        episode = self._read(episode_id)
        if episode["status"] != "review_required" or not feedback.strip():
            raise YouTubeProductionError("A staged review and feedback are required")
        episode.update(status="changes_requested", approval=None, updated_at=self._now())
        episode["review_feedback"] = feedback.strip()[:2000]
        episode["agents"]["Approval Manager"] = "changes_requested"
        self._write(episode)
        return self._summary(episode)

    @_episode_mutation
    def approve(self, episode_id: str, review_hash: str) -> dict[str, Any]:
        episode = self._read(episode_id)
        if episode["status"] != "review_required" or not episode.get("draft"):
            raise YouTubeProductionError("Only a staged review can be approved")
        actual = episode["draft"]["review_hash"]
        if (not re.fullmatch(r"[a-f0-9]{64}", review_hash)
                or not hmac.compare_digest(review_hash, actual)
                or not hmac.compare_digest(self._review_hash(episode["draft"]), actual)):
            raise YouTubeProductionError("Approval does not match the current reviewed draft")
        episode["status"] = "approved"
        episode["approval"] = {"review_hash": actual, "approved_at": self._now(),
                               "publishing_enabled": False}
        episode["agents"]["Approval Manager"] = "approved"
        episode["updated_at"] = self._now()
        self._write(episode)
        return {**self._summary(episode), "publishing_enabled": False,
                "message": "Draft approved. Publishing remains disabled in the draft-only release."}

    def status(self, episode_id: str) -> dict[str, Any]:
        return self._summary(self._read(episode_id))

    def draft_context(self, episode_id: str) -> dict[str, Any]:
        episode = self._read(episode_id)
        if episode["status"] not in {"idea", "changes_requested"}:
            raise YouTubeProductionError("Create a brief or request changes before preparing a draft")
        return {"brief": episode["brief"], "feedback": episode.get("review_feedback", ""),
                "previous_draft": episode.get("draft"), "updated_at": episode["updated_at"]}

    def _path(self, episode_id: str) -> Path:
        if not EPISODE_ID.fullmatch(episode_id):
            raise YouTubeProductionError("Invalid episode ID")
        return self.episodes_dir / f"{episode_id}.json"

    def _read(self, episode_id: str) -> dict[str, Any]:
        path = self._path(episode_id)
        if not path.is_file():
            raise YouTubeProductionError("Episode not found")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise YouTubeProductionError("Episode state is unreadable") from error
        if not isinstance(value, dict) or value.get("episode_id") != episode_id:
            raise YouTubeProductionError("Episode state is invalid")
        return value

    def _write(self, episode: dict[str, Any]) -> None:
        path = self._path(episode["episode_id"])
        payload = json.dumps(episode, indent=2, ensure_ascii=False) + "\n"
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    @staticmethod
    def _review_hash(draft: dict[str, Any]) -> str:
        reviewed = {key: draft[key] for key in (
            "script", "title", "description", "sources", "storyboard", "thumbnail_prompt",
            "video_path", "audience_setting", "target_channel")}
        if "revision" in draft:
            reviewed.update({key: draft[key] for key in ("revision", "gemini_prompt", "review_notes")})
        return hashlib.sha256(json.dumps(reviewed, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    @staticmethod
    def _now() -> str:
        return datetime.now().astimezone().isoformat(timespec="microseconds")

    @staticmethod
    def _summary(episode: dict[str, Any]) -> dict[str, Any]:
        return {key: episode.get(key) for key in (
            "episode_id", "status", "revision", "created_at", "updated_at")}
