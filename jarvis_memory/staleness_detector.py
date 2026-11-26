"""Bitemporal Cognitive Self-Healing Memory & Staleness Detectors for JARVIS OS.

Based on the bitemporal cognitive memory architecture ("What happens to that memory in six months?"):
1. Two time dimensions: Valid Time (real-world applicability) vs. Transaction Time (recording time).
2. Immutable Audit Trail: Nothing is ever deleted, only closed or superseded.
3. 4 Zero-Model-Call Deterministic Staleness Detectors:
   - TtlDetector: Absolute & relative expiration scan (until 4pm, today only, expires date).
   - KeyCollisionDetector: Singleton entity collision & contradiction detection.
   - OsRealityDetector: Grounding against host OS filesystem, systemd units, and binaries.
   - TemporalDecayDetector: Category-aware half-life confidence decay.
4. Human-In-The-Loop Escalation Gate for ambiguous contradictions.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
import shutil
import time
from typing import Any, Dict, List, Optional, Tuple

from .paths import get_config_dir
from .store import Fact, LocalFactStore

log = logging.getLogger("jarvis.memory.staleness")


@dataclass
class StalenessIssue:
    """A detected anomaly or temporal staleness in a memory fact."""

    fact_index: int
    fact_text: str
    detector: str  # "ttl", "key_collision", "os_reality", "temporal_decay"
    reason: str
    suggested_action: str  # "close", "supersede", "escalate", "decay"
    entity_key: str = ""
    new_confidence: Optional[float] = None
    expiry_time: Optional[float] = None
    colliding_with_index: Optional[int] = None
    colliding_text: Optional[str] = None
    clarification_prompt: Optional[str] = None
    safe_to_auto_heal: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ClarificationRequest:
    """A question queued for the user when automatic resolution would be speculative."""

    id: str
    created_at: float
    detector: str
    entity_key: str
    fact_indexes: List[int]
    fact_texts: List[str]
    prompt: str
    status: str = "pending"  # "pending", "resolved", "dismissed"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Pending Clarifications Queue (Human-In-The-Loop Escalation Gate)
# ---------------------------------------------------------------------------

def _clarifications_path() -> Path:
    return get_config_dir() / "pending_clarifications.json"


def get_pending_clarifications(path: Optional[Path] = None) -> List[ClarificationRequest]:
    p = path or _clarifications_path()
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        requests: List[ClarificationRequest] = []
        for item in data:
            if isinstance(item, dict) and item.get("status") == "pending":
                requests.append(
                    ClarificationRequest(
                        id=str(item.get("id", "")),
                        created_at=float(item.get("created_at", 0.0)),
                        detector=str(item.get("detector", "")),
                        entity_key=str(item.get("entity_key", "")),
                        fact_indexes=list(item.get("fact_indexes", [])),
                        fact_texts=list(item.get("fact_texts", [])),
                        prompt=str(item.get("prompt", "")),
                        status=str(item.get("status", "pending")),
                    )
                )
        return requests
    except Exception as exc:
        log.warning("Failed to read pending clarifications: %s", exc)
        return []


def add_pending_clarification(
    req: ClarificationRequest, path: Optional[Path] = None
) -> None:
    p = path or _clarifications_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    existing: List[Dict[str, Any]] = []
    if p.exists():
        try:
            existing = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(existing, list):
                existing = []
        except Exception:
            existing = []

    # Deduplicate by prompt
    for item in existing:
        if item.get("prompt") == req.prompt and item.get("status") == "pending":
            return

    existing.append(req.to_dict())
    tmp_path = p.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(p)


def resolve_clarification(
    clarification_id: str,
    status: str = "resolved",
    path: Optional[Path] = None,
) -> bool:
    p = path or _clarifications_path()
    if not p.exists():
        return False
    try:
        items = json.loads(p.read_text(encoding="utf-8"))
        updated = False
        for item in items:
            if item.get("id") == clarification_id:
                item["status"] = status
                item["resolved_at"] = time.time()
                updated = True
        if updated:
            tmp_path = p.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp_path.replace(p)
        return updated
    except Exception as exc:
        log.warning("Failed to resolve clarification %s: %s", clarification_id, exc)
        return False


# ---------------------------------------------------------------------------
# 1. TTL Expiration Detector (Zero Model Calls)
# ---------------------------------------------------------------------------

class TtlDetector:
    """Detects facts that have elapsed their temporal validity window."""

    _RE_UNTIL_TIME = re.compile(r"\buntil\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", re.IGNORECASE)
    _RE_VALID_DATE = re.compile(
        r"\b(?:valid\s+(?:until|through)|expires?\s+(?:on|at)?)\s*(\d{4}-\d{2}-\d{2})\b",
        re.IGNORECASE,
    )
    _RE_VALID_SLASH_DATE = re.compile(
        r"\b(?:valid\s+(?:until|through)|expires?\s+(?:on|at)?)\s*(\d{1,2})/(\d{1,2})/(\d{2,4})\b",
        re.IGNORECASE,
    )
    _RE_TODAY_ONLY = re.compile(r"\b(?:today\s+only|just\s+for\s+today)\b", re.IGNORECASE)
    _RE_DURATION = re.compile(
        r"\bfor\s+the\s+next\s+(\d+)\s*(hour|minute|day|week|month)s?\b",
        re.IGNORECASE,
    )
    _RE_TEMPORARY = re.compile(r"\b(?:temporarily|for\s+now|temporary(?:\s+status)?)\b", re.IGNORECASE)

    @classmethod
    def parse_ttl(cls, text: str, created_at: float) -> Optional[float]:
        """Extract a deterministic expiration timestamp from fact text without model calls."""
        # 1. "until HH[:MM] [am/pm]"
        m_time = cls._RE_UNTIL_TIME.search(text)
        if m_time:
            hour = int(m_time.group(1))
            minute = int(m_time.group(2) or 0)
            ampm = (m_time.group(3) or "").lower()
            if ampm == "pm" and hour < 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
            # Anchor to created_at day
            dt_created = datetime.fromtimestamp(created_at)
            dt_expire = dt_created.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return dt_expire.timestamp()

        # 2. "valid until YYYY-MM-DD" or "expires YYYY-MM-DD"
        m_date = cls._RE_VALID_DATE.search(text)
        if m_date:
            try:
                dt = datetime.strptime(m_date.group(1), "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59
                )
                return dt.timestamp()
            except ValueError:
                pass

        # 3. "valid until MM/DD/YYYY"
        m_slash = cls._RE_VALID_SLASH_DATE.search(text)
        if m_slash:
            m, d, y = int(m_slash.group(1)), int(m_slash.group(2)), int(m_slash.group(3))
            if y < 100:
                y += 2000
            try:
                dt = datetime(y, m, d, 23, 59, 59)
                return dt.timestamp()
            except ValueError:
                pass

        # 4. "today only"
        if cls._RE_TODAY_ONLY.search(text):
            dt_created = datetime.fromtimestamp(created_at)
            dt_expire = dt_created.replace(hour=23, minute=59, second=59)
            return dt_expire.timestamp()

        # 5. "for the next N hours/days/weeks"
        m_dur = cls._RE_DURATION.search(text)
        if m_dur:
            val = int(m_dur.group(1))
            unit = m_dur.group(2).lower()
            multipliers = {
                "minute": 60,
                "hour": 3600,
                "day": 86400,
                "week": 7 * 86400,
                "month": 30 * 86400,
            }
            return created_at + (val * multipliers.get(unit, 3600))

        # 6. "temporarily" / "for now" -> defaults to 24-hour expiration window
        if cls._RE_TEMPORARY.search(text):
            return created_at + 86400

        return None

    @classmethod
    def check_fact(
        cls, fact: Fact, index: int, now: Optional[float] = None
    ) -> Optional[StalenessIssue]:
        current_time = now if now is not None else time.time()

        # Check explicit valid_to field first
        if fact.valid_to is not None and fact.valid_to <= current_time:
            exp_str = datetime.fromtimestamp(fact.valid_to).strftime("%Y-%m-%d %H:%M:%S")
            return StalenessIssue(
                fact_index=index,
                fact_text=fact.text,
                detector="ttl",
                reason=f"Explicit valid_to elapsed at {exp_str}",
                suggested_action="close",
                expiry_time=fact.valid_to,
                safe_to_auto_heal=True,
            )

        # Parse text for temporal expiration markers
        ttl = cls.parse_ttl(fact.text, fact.created_at)
        if ttl is not None and ttl <= current_time:
            exp_str = datetime.fromtimestamp(ttl).strftime("%Y-%m-%d %H:%M:%S")
            return StalenessIssue(
                fact_index=index,
                fact_text=fact.text,
                detector="ttl",
                reason=f"Parsed temporal TTL expired at {exp_str}",
                suggested_action="close",
                expiry_time=ttl,
                safe_to_auto_heal=True,
            )

        return None


# ---------------------------------------------------------------------------
# 2. Key Collision & Contradiction Detector (Zero Model Calls)
# ---------------------------------------------------------------------------

class KeyCollisionDetector:
    """Detects singleton entity key collisions and contradictory preferences."""

    # Regex rules for extracting canonical entity keys
    _KEY_RULES: List[Tuple[str, re.Pattern]] = [
        ("preference:theme", re.compile(r"\b(?:prefers?|uses?|switched to|theme is)\s+(dark|light)\s+mode\b", re.IGNORECASE)),
        ("preference:shell", re.compile(r"\b(?:prefers?|default shell is|uses shell|switched to)\s+(zsh|bash|fish)\b", re.IGNORECASE)),
        ("preference:editor", re.compile(r"\b(?:prefers?|default editor is|uses?)\s+(neovim|nvim|vim|vscode|emacs|cursor|sublime)\b", re.IGNORECASE)),
        ("preference:browser", re.compile(r"\b(?:prefers?|default browser is|uses?)\s+(firefox|chrome|brave|zen|edge|safari)\b", re.IGNORECASE)),
        ("user:location", re.compile(r"\b(?:lives in|moved to|relocated to|located in|currently living in)\s+([a-zA-Z\s]+?)(?:\.|$|,|\s+since|\s+for)", re.IGNORECASE)),
        ("system:port", re.compile(r"\b(?:listens on port|running on port|port is)\s+(\d+)\b", re.IGNORECASE)),
        ("user:current_project", re.compile(r"\b(?:working on|focusing on|current project is)\s+([a-zA-Z0-9_\-]+)\b", re.IGNORECASE)),
    ]

    _EXPLICIT_KEY_RE = re.compile(r"(?:^|[\s\[])(?:key|slot|entity):\s*([a-zA-Z0-9_\.:-]+)", re.IGNORECASE)
    _TRANSITION_RE = re.compile(r"\b(?:moved to|switched to|now using|updated to|changed to|new preference is|as of)\b", re.IGNORECASE)

    @classmethod
    def extract_entity_key(cls, text: str) -> str:
        # Check explicit slot tag
        m_exp = cls._EXPLICIT_KEY_RE.search(text)
        if m_exp:
            return m_exp.group(1).lower().strip()

        # Check domain patterns
        for key, pattern in cls._KEY_RULES:
            if pattern.search(text):
                return key

        return ""

    @classmethod
    def check_collisions(cls, facts: List[Fact]) -> List[StalenessIssue]:
        issues: List[StalenessIssue] = []

        # Map entity_key -> list of (index, Fact)
        by_key: Dict[str, List[Tuple[int, Fact]]] = {}
        for idx, fact in enumerate(facts):
            if not fact.is_active:
                continue
            key = fact.entity_key or cls.extract_entity_key(fact.text)
            if key:
                by_key.setdefault(key, []).append((idx, fact))

        for key, entries in by_key.items():
            if len(entries) <= 1:
                continue

            # Sort by created_at ascending
            entries.sort(key=lambda x: x[1].created_at)

            # Compare adjacent or conflicting entries
            for i in range(len(entries) - 1):
                idx1, f1 = entries[i]
                idx2, f2 = entries[i + 1]

                # If text is identical, LocalFactStore deduplication already handles it
                if f1.text.strip().lower() == f2.text.strip().lower():
                    continue

                # Check if newer fact has clear transition language
                has_transition = bool(cls._TRANSITION_RE.search(f2.text))
                significantly_newer = (f2.created_at - f1.created_at) > 60.0  # at least 1 min newer

                if has_transition or significantly_newer:
                    # Safe to supersede older fact with newer fact
                    issues.append(
                        StalenessIssue(
                            fact_index=idx1,
                            fact_text=f1.text,
                            detector="key_collision",
                            reason=f"Superseded by newer assertion for {key} ('{f2.text}')",
                            suggested_action="supersede",
                            entity_key=key,
                            colliding_with_index=idx2,
                            colliding_text=f2.text,
                            safe_to_auto_heal=True,
                        )
                    )
                else:
                    # Ambiguous contradiction -> Escalate to human gate!
                    issues.append(
                        StalenessIssue(
                            fact_index=idx1,
                            fact_text=f1.text,
                            detector="key_collision",
                            reason=f"Contradictory facts detected for singleton key {key}",
                            suggested_action="escalate",
                            entity_key=key,
                            colliding_with_index=idx2,
                            colliding_text=f2.text,
                            clarification_prompt=(
                                f"I found conflicting entries regarding your {key.replace('preference:', 'preferred ').replace('user:', '')}: "
                                f"'{f1.text}' versus '{f2.text}'. Which one would you prefer I keep?"
                            ),
                            safe_to_auto_heal=False,
                        )
                    )

        return issues


# ---------------------------------------------------------------------------
# 3. OS Reality Grounding Detector (Zero Model Calls)
# ---------------------------------------------------------------------------

class OsRealityDetector:
    """Grounds facts against physical OS reality (paths, services, binaries)."""

    _PATH_RE = re.compile(
        r"(?<![\w/])(/(?:home|etc|var|usr|opt|tmp)/[a-zA-Z0-9_.\-]+(?:/[a-zA-Z0-9_.\-]+)*|~/[a-zA-Z0-9_.\-]+(?:/[a-zA-Z0-9_.\-]+)*)"
    )
    _SERVICE_RE = re.compile(r"\b([a-zA-Z0-9_\-]+\.service)\b", re.IGNORECASE)
    _CLI_TOOL_RE = re.compile(r"\b(?:command|binary|tool)\s+`?([a-zA-Z0-9_\-]+)`?\b", re.IGNORECASE)

    # Unit paths to check for systemd services
    _SYSTEMD_SEARCH_PATHS = [
        Path("/etc/systemd/system"),
        Path("/usr/lib/systemd/system"),
        Path.home() / ".config/systemd/user",
        Path("/etc/systemd/user"),
        Path("/usr/lib/systemd/user"),
    ]

    @classmethod
    def check_fact(cls, fact: Fact, index: int) -> Optional[StalenessIssue]:
        text = fact.text

        # 1. Check Filesystem Paths
        for match in cls._PATH_RE.finditer(text):
            raw_path = match.group(1).rstrip(".,:;)]'\"")
            expanded = os.path.expanduser(raw_path)
            # Only invalidate if path is asserted to exist or be a config/file
            if not os.path.exists(expanded):
                # Verify that the text frames it as an existing resource
                if any(k in text.lower() for k in ("path", "file", "config", "stored at", "located at", "directory", "folder", "script", "saved at")):
                    return StalenessIssue(
                        fact_index=index,
                        fact_text=text,
                        detector="os_reality",
                        reason=f"Referenced filesystem path does not exist on host: {raw_path}",
                        suggested_action="close",
                        safe_to_auto_heal=True,
                    )

        # 2. Check Systemd Services
        for match in cls._SERVICE_RE.finditer(text):
            service = match.group(1)
            # Check unit paths
            unit_exists = any((search_dir / service).exists() for search_dir in cls._SYSTEMD_SEARCH_PATHS)
            if not unit_exists:
                # Also check shutil.which if service is standard
                if any(k in text.lower() for k in ("service", "unit", "running", "enabled")):
                    return StalenessIssue(
                        fact_index=index,
                        fact_text=text,
                        detector="os_reality",
                        reason=f"Referenced systemd service unit was not found: {service}",
                        suggested_action="close",
                        safe_to_auto_heal=True,
                    )

        # 3. Check CLI Tools / Binaries
        for match in cls._CLI_TOOL_RE.finditer(text):
            tool = match.group(1)
            # Common false positives to ignore
            if tool.lower() in ("pipewire", "wireplumber", "python", "bash", "sh", "systemctl"):
                continue
            if shutil.which(tool) is None:
                return StalenessIssue(
                    fact_index=index,
                    fact_text=text,
                    detector="os_reality",
                    reason=f"Referenced CLI binary not found in PATH: {tool}",
                    suggested_action="close",
                    safe_to_auto_heal=True,
                )

        return None


# ---------------------------------------------------------------------------
# 4. Temporal Decay Detector (Zero Model Calls)
# ---------------------------------------------------------------------------

class TemporalDecayDetector:
    """Applies domain-aware half-life confidence decay for unverified facts."""

    # Half-life in seconds by detected domain
    HALF_LIVES = {
        "status": 2 * 86400,        # 2 days for ephemeral status / bugs
        "task": 30 * 86400,         # 30 days for active projects / tasks
        "environment": 14 * 86400,  # 14 days for volatile system metrics
        "preference": 365 * 86400,  # 1 year for user preferences
    }

    @classmethod
    def categorize(cls, text: str) -> str:
        lowered = text.lower()
        if any(w in lowered for w in ("currently", "today", "now debugging", "feeling", "investigating", "temporary")):
            return "status"
        if any(w in lowered for w in ("project", "task", "milestone", "reading", "learning", "working on")):
            return "task"
        if any(w in lowered for w in ("kernel", "ip address", "ram", "display", "monitor", "version")):
            return "environment"
        return "preference"

    @classmethod
    def check_fact(
        cls, fact: Fact, index: int, now: Optional[float] = None
    ) -> Optional[StalenessIssue]:
        current_time = now if now is not None else time.time()
        last_verified = fact.last_verified_at or fact.created_at
        if last_verified <= 0:
            return None

        elapsed = current_time - last_verified
        if elapsed < 86400:  # less than 1 day old
            return None

        cat = cls.categorize(fact.text)
        half_life = cls.HALF_LIVES.get(cat, cls.HALF_LIVES["preference"])

        # Exponential decay: c(t) = c_0 * (0.5 ^ (elapsed / half_life))
        decay_factor = 0.5 ** (elapsed / half_life)
        new_conf = round(fact.confidence * decay_factor, 3)

        # Severely decayed facts (< 0.35 confidence) are closed
        if new_conf < 0.35:
            days = elapsed / 86400.0
            return StalenessIssue(
                fact_index=index,
                fact_text=fact.text,
                detector="temporal_decay",
                reason=f"Confidence decayed to {new_conf:.2f} (< 0.35) after {days:.1f} days without verification",
                suggested_action="close",
                new_confidence=new_conf,
                safe_to_auto_heal=True,
            )

        # Noticeable decay (< fact.confidence - 0.1) triggers confidence adjustment
        if (fact.confidence - new_conf) >= 0.1:
            return StalenessIssue(
                fact_index=index,
                fact_text=fact.text,
                detector="temporal_decay",
                reason=f"Fact confidence decayed from {fact.confidence:.2f} to {new_conf:.2f}",
                suggested_action="decay",
                new_confidence=new_conf,
                safe_to_auto_heal=True,
            )

        return None


# ---------------------------------------------------------------------------
# Composite Memory Staleness Scanner
# ---------------------------------------------------------------------------

def scan_memory_staleness(
    store: LocalFactStore, now: Optional[float] = None
) -> List[StalenessIssue]:
    """Scan all active facts in *store* using the 4 deterministic staleness detectors."""
    facts = store.list()
    issues: List[StalenessIssue] = []
    current_time = now if now is not None else time.time()

    # 1. TTL Expiration & OS Reality & Temporal Decay per fact
    for idx, fact in enumerate(facts):
        if not fact.is_active:
            continue

        # Detector 1: TTL
        ttl_issue = TtlDetector.check_fact(fact, idx, now=current_time)
        if ttl_issue:
            issues.append(ttl_issue)
            continue  # TTL closure takes precedence

        # Detector 3: OS Reality
        os_issue = OsRealityDetector.check_fact(fact, idx)
        if os_issue:
            issues.append(os_issue)
            continue

        # Detector 4: Temporal Decay
        decay_issue = TemporalDecayDetector.check_fact(fact, idx, now=current_time)
        if decay_issue:
            issues.append(decay_issue)

    # 2. Key Collisions & Contradictions across entire set
    collision_issues = KeyCollisionDetector.check_collisions(facts)
    issues.extend(collision_issues)

    return issues
