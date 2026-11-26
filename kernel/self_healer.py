"""Autonomous Self-Healing Subsystem for JARVIS OS.

Detects, diagnoses, and automatically remediates operational anomalies across:
1. Audio capture & playback streams (unmuting, volume restoration, PipeWire restart)
2. Systemd user services (reset-failed, stale socket/PID purging, bounded restart)
3. Sockets & IPC (stale lock/socket unlinking)
4. Disk & Memory resources (cache eviction, temporary buffer pruning)
5. Incident logging and recovery intimation
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import gc
import json
import logging
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("jarvis.self_healer")


@dataclass(frozen=True)
class HealResult:
    """Outcome of an automated self-healing action."""
    success: bool
    subsystem: str
    issue: str
    action_taken: str
    details: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "subsystem": self.subsystem,
            "issue": self.issue,
            "action_taken": self.action_taken,
            "details": self.details,
            "timestamp": self.timestamp,
        }


class AutoHealer:
    """Core autonomous self-healing orchestrator for JARVIS OS."""

    @staticmethod
    def _run_cmd(cmd: List[str], timeout: float = 5.0) -> Tuple[int, str, str]:
        """Execute a synchronous command safely with timeout."""
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            return res.returncode, res.stdout.strip(), res.stderr.strip()
        except subprocess.TimeoutExpired:
            return 124, "", f"Command timed out after {timeout}s: {' '.join(cmd)}"
        except Exception as exc:
            return 1, "", str(exc)

    @classmethod
    async def _async_run_cmd(cls, cmd: List[str], timeout: float = 5.0) -> Tuple[int, str, str]:
        """Execute an asynchronous command safely with timeout."""
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return (
                proc.returncode if proc.returncode is not None else 0,
                stdout_b.decode(errors="replace").strip(),
                stderr_b.decode(errors="replace").strip(),
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
            return 124, "", f"Command timed out after {timeout}s"
        except Exception as exc:
            return 1, "", str(exc)

    # -------------------------------------------------------------------------
    # 1. Audio Subsystem Self-Healing
    # -------------------------------------------------------------------------

    @classmethod
    async def heal_microphone_mute(cls, source: Optional[str] = None) -> HealResult:
        """Automatically unmute microphone in PulseAudio/PipeWire."""
        cmd = ["pactl", "set-source-mute", source or "@DEFAULT_SOURCE@", "0"]
        rc, _, err = await cls._async_run_cmd(cmd, timeout=3.0)
        if rc == 0:
            log.info("AutoHealer: Successfully unmuted microphone (source=%s)", source or "default")
            return HealResult(
                success=True,
                subsystem="audio",
                issue="Microphone was muted in system settings",
                action_taken=f"Unmuted microphone source '{source or 'default'}' via pactl",
            )
        return HealResult(
            success=False,
            subsystem="audio",
            issue="Microphone muted but failed to unmute",
            action_taken=f"Failed to unmute microphone source '{source or 'default'}'",
            details=err,
        )

    @classmethod
    async def heal_microphone_volume(
        cls, source: Optional[str] = None, target_percent: int = 80
    ) -> HealResult:
        """Automatically restore microphone capture volume to healthy level."""
        target_vol = max(10, min(100, int(target_percent)))
        cmd = ["pactl", "set-source-volume", source or "@DEFAULT_SOURCE@", f"{target_vol}%"]
        rc, _, err = await cls._async_run_cmd(cmd, timeout=3.0)
        if rc == 0:
            log.info("AutoHealer: Successfully restored microphone volume to %d%%", target_vol)
            return HealResult(
                success=True,
                subsystem="audio",
                issue="Microphone volume was zero or degraded",
                action_taken=f"Restored microphone volume to {target_vol}% via pactl",
            )
        return HealResult(
            success=False,
            subsystem="audio",
            issue="Microphone volume was zero",
            action_taken=f"Failed to set microphone volume to {target_vol}%",
            details=err,
        )

    @classmethod
    def heal_pipewire(cls) -> HealResult:
        """Restart PipeWire and WirePlumber user audio services."""
        cmd = ["systemctl", "--user", "restart", "pipewire.service", "wireplumber.service"]
        rc, _, err = cls._run_cmd(cmd, timeout=8.0)
        if rc == 0:
            log.info("AutoHealer: Successfully restarted PipeWire and WirePlumber")
            return HealResult(
                success=True,
                subsystem="audio",
                issue="PipeWire/WirePlumber audio daemon degraded or unresponsive",
                action_taken="Restarted pipewire.service and wireplumber.service",
            )
        return HealResult(
            success=False,
            subsystem="audio",
            issue="PipeWire/WirePlumber restart failed",
            action_taken="Attempted to restart pipewire and wireplumber services",
            details=err,
        )

    @classmethod
    def heal_hanging_audio_sinks(cls) -> HealResult:
        """Terminate orphaned or hanging audio subprocesses (pw-play, pw-record)."""
        terminated_pids: List[int] = []
        my_pid = os.getpid()

        for proc_name in ("pw-play", "pw-record"):
            rc, out, _ = cls._run_cmd(["pgrep", "-f", proc_name])
            if rc == 0 and out:
                for line in out.splitlines():
                    p_str = line.strip()
                    if p_str.isdigit():
                        pid = int(p_str)
                        if pid == my_pid:
                            continue
                        try:
                            os.kill(pid, signal.SIGTERM)
                            time.sleep(0.05)
                            try:
                                os.kill(pid, 0)
                                os.kill(pid, signal.SIGKILL)
                            except OSError:
                                pass
                            terminated_pids.append(pid)
                        except OSError:
                            pass

        if terminated_pids:
            log.info("AutoHealer: Terminated %d hanging audio sink/source process(es): %s",
                     len(terminated_pids), terminated_pids)
            return HealResult(
                success=True,
                subsystem="audio",
                issue="Hanging audio sink/source processes detected (pw-play / pw-record)",
                action_taken=f"Terminated {len(terminated_pids)} hanging audio process(es) (PIDs: {terminated_pids})",
                details=f"PIDs: {terminated_pids}",
            )
        return HealResult(
            success=True,
            subsystem="audio",
            issue="Hanging audio sink check performed",
            action_taken="No hanging audio sinks detected",
        )

    @classmethod
    def heal_voice_session(cls, restart_service: bool = False) -> HealResult:
        """Auto-heal degraded voice session by purging hanging sinks, stale sockets, and resetting state."""
        actions: List[str] = []

        # 1. Clean up hanging audio sink processes
        sink_res = cls.heal_hanging_audio_sinks()
        if "Terminated" in sink_res.action_taken:
            actions.append(sink_res.action_taken)

        # 2. Clean up stale sockets
        stale_socks = cls.heal_stale_sockets()
        if stale_socks:
            actions.append(f"Purged {len(stale_socks)} stale socket(s)")

        # 3. Check voice service / restart if requested or failed
        rc_active, stdout_active, _ = cls._run_cmd(
            ["systemctl", "--user", "is-active", "jarvis-voice.service"], timeout=3.0
        )
        if restart_service or rc_active != 0 or stdout_active not in ("active", "activating"):
            rc_load, _, _ = cls._run_cmd(
                ["systemctl", "--user", "cat", "jarvis-voice.service"], timeout=3.0
            )
            if rc_load == 0:
                svc_res = cls.heal_service("jarvis-voice.service", user_scope=True)
                if svc_res.success:
                    actions.append("Restarted jarvis-voice.service")

        action_summary = "; ".join(actions) if actions else "Verified voice session integrity, no anomalies found"
        log.info("AutoHealer: heal_voice_session completed: %s", action_summary)
        return HealResult(
            success=True,
            subsystem="voice",
            issue="Voice session degradation or disconnect loop bottleneck",
            action_taken=action_summary,
            details=f"Service status: {stdout_active}, Actions: {actions}",
        )

    # -------------------------------------------------------------------------
    # 2. Service & Process Self-Healing
    # -------------------------------------------------------------------------

    @classmethod
    def heal_service(cls, service_name: str, user_scope: bool = True) -> HealResult:
        """Auto-heal a systemd user or system service in failed/degraded state."""
        clean_name = service_name if service_name.endswith((".service", ".timer", ".socket")) else f"{service_name}.service"
        scope_flag = ["--user"] if user_scope else []

        # 1. Clean up known stale runtime sockets/pid files before restarting
        cls.heal_stale_sockets()

        # 2. Reset failed counter
        cls._run_cmd(["systemctl", *scope_flag, "reset-failed", clean_name], timeout=4.0)

        # 3. Restart the service
        rc, _, err = cls._run_cmd(["systemctl", *scope_flag, "restart", clean_name], timeout=10.0)
        if rc != 0:
            return HealResult(
                success=False,
                subsystem="service",
                issue=f"Service '{clean_name}' failed to restart",
                action_taken=f"Attempted reset-failed and restart on '{clean_name}'",
                details=err,
            )

        # 4. Verify service is active
        time.sleep(0.5)
        rc_active, stdout_active, _ = cls._run_cmd(["systemctl", *scope_flag, "is-active", clean_name], timeout=3.0)
        if rc_active == 0 and stdout_active in ("active", "activating"):
            log.info("AutoHealer: Successfully healed and restarted service '%s'", clean_name)
            return HealResult(
                success=True,
                subsystem="service",
                issue=f"Service '{clean_name}' was failed or stopped",
                action_taken=f"Cleared failure state, purged stale sockets, and restarted '{clean_name}'",
                details=f"State: {stdout_active}",
            )

        return HealResult(
            success=False,
            subsystem="service",
            issue=f"Service '{clean_name}' restarted but remains inactive",
            action_taken=f"Restarted '{clean_name}' but is-active returned {stdout_active}",
            details=stdout_active,
        )

    @classmethod
    def heal_runaway_processes(cls, cpu_threshold: float = 80.0) -> HealResult:
        """Detect and terminate runaway or frozen processes consuming excessive CPU."""
        my_pid = os.getpid()
        my_ppid = os.getppid()

        # Critical system process names that must NEVER be terminated
        PROTECTED_COMM = {
            "systemd", "init", "kthreadd", "dbus-daemon", "pipewire",
            "wireplumber", "pulseaudio", "sshd", "login", "agetty",
            "bash", "zsh", "fish", "sudo", "sway", "hyprland",
            "Xorg", "Xwayland", "waybar", "gnome-shell", "tmux",
        }

        rc, out, err = cls._run_cmd(
            ["ps", "-eo", "pid,ppid,%cpu,comm,args", "--sort=-%cpu", "--no-headers"],
            timeout=4.0,
        )
        if rc != 0 or not out:
            return HealResult(
                success=False,
                subsystem="cpu",
                issue="Failed to inspect running processes",
                action_taken="Could not retrieve process list",
                details=err,
            )

        terminated: List[Dict[str, Any]] = []

        for line in out.splitlines():
            parts = line.strip().split(None, 4)
            if len(parts) < 4:
                continue
            try:
                pid = int(parts[0])
                ppid = int(parts[1])
                cpu_pct = float(parts[2])
                comm = parts[3]
                args = parts[4] if len(parts) > 4 else comm
            except (ValueError, IndexError):
                continue

            if cpu_pct < cpu_threshold:
                # Output is sorted descending by %cpu; subsequent entries are below threshold
                break

            # Never kill protected system processes, init, or ourselves/parents
            if pid in (0, 1, 2, my_pid, my_ppid):
                continue
            if comm in PROTECTED_COMM or comm.startswith("kworker/"):
                continue

            # Terminate runaway process safely
            try:
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.05)
                try:
                    os.kill(pid, 0)
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass
                terminated.append({"pid": pid, "comm": comm, "cpu": cpu_pct})
                log.warning("AutoHealer: Terminated runaway process %s (PID %d, CPU %.1f%%)", comm, pid, cpu_pct)
            except OSError as exc:
                log.debug("AutoHealer: Could not terminate PID %d (%s): %s", pid, comm, exc)

        if terminated:
            summary = ", ".join(f"{t['comm']}[PID {t['pid']}, {t['cpu']}% CPU]" for t in terminated)
            return HealResult(
                success=True,
                subsystem="cpu",
                issue=f"Runaway process(es) exceeded {cpu_threshold}% CPU threshold",
                action_taken=f"Terminated {len(terminated)} runaway process(es): {summary}",
                details=json.dumps(terminated),
            )

        return HealResult(
            success=True,
            subsystem="cpu",
            issue=f"Process CPU check against threshold {cpu_threshold}%",
            action_taken="No runaway processes detected",
        )

    # -------------------------------------------------------------------------
    # 3. Sockets & IPC Self-Healing
    # -------------------------------------------------------------------------

    @classmethod
    def heal_stale_sockets(cls, socket_dir: Optional[Path] = None) -> List[HealResult]:
        """Detect and unlink dead Unix domain socket files with no listening daemon."""
        results: List[HealResult] = []
        runtime_dir = Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}")
        search_dirs = [runtime_dir / "jarvis", runtime_dir] if socket_dir is None else [socket_dir]

        for sdir in search_dirs:
            if not sdir.exists():
                continue
            for entry in sdir.glob("*.sock"):
                if not entry.is_socket():
                    continue
                # Test if any process is actively listening on this socket
                dead_socket = False
                try:
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                        client.settimeout(0.2)
                        client.connect(str(entry))
                except ConnectionRefusedError:
                    # File exists on disk, but no listener exists (stale crash leftover)
                    dead_socket = True
                except (FileNotFoundError, OSError):
                    pass

                if dead_socket:
                    try:
                        entry.unlink(missing_ok=True)
                        log.info("AutoHealer: Removed stale socket file '%s'", entry)
                        results.append(HealResult(
                            success=True,
                            subsystem="ipc",
                            issue=f"Stale Unix socket file '{entry.name}' left over after crash",
                            action_taken=f"Unlinked dead socket '{entry}'",
                        ))
                    except OSError as exc:
                        results.append(HealResult(
                            success=False,
                            subsystem="ipc",
                            issue=f"Unable to unlink dead socket '{entry.name}'",
                            action_taken=f"Failed unlinking '{entry}'",
                            details=str(exc),
                        ))

        return results

    # -------------------------------------------------------------------------
    # 4. Storage & Memory Resource Self-Healing
    # -------------------------------------------------------------------------

    @classmethod
    def heal_disk(cls, target_mount: str = "/") -> HealResult:
        """Safely reclaim disk space by purging temporary caches and logs."""
        freed_bytes = 0
        repo_root = Path(__file__).resolve().parents[1]

        # Targets safe to prune automatically:
        prune_dirs = [
            Path.home() / ".cache" / "jarvis" / "alerts",
            Path.home() / ".cache" / "jarvis" / "audio",
            repo_root / ".pytest_cache",
        ]

        for pdir in prune_dirs:
            if pdir.exists() and pdir.is_dir():
                try:
                    for item in pdir.glob("**/*"):
                        if item.is_file():
                            freed_bytes += item.stat().st_size
                            item.unlink(missing_ok=True)
                except Exception as exc:
                    log.debug("Disk auto-prune notice for %s: %s", pdir, exc)

        freed_mb = freed_bytes / (1024 * 1024)
        log.info("AutoHealer: Reclaimed %.2f MB of disk space", freed_mb)
        return HealResult(
            success=True,
            subsystem="storage",
            issue=f"Disk space pressure on '{target_mount}'",
            action_taken=f"Purged transient caches and alert audio, reclaiming {freed_mb:.1f} MB",
            details=f"Freed bytes: {freed_bytes}",
        )

    @classmethod
    def heal_memory(cls) -> HealResult:
        """Trigger Python garbage collection and release internal object pools."""
        collected = gc.collect()
        log.info("AutoHealer: Executed garbage collection, freed %d unreachable objects", collected)
        return HealResult(
            success=True,
            subsystem="memory",
            issue="Elevated system RAM utilization",
            action_taken=f"Invoked gc.collect() to release internal object pools ({collected} objects collected)",
            details=f"Objects collected: {collected}",
        )

    # -------------------------------------------------------------------------
    # 5. Cognitive Bitemporal Memory Healing
    # -------------------------------------------------------------------------

    @classmethod
    def heal_memory_staleness(
        cls,
        fact_store: Optional[Any] = None,
        now: Optional[float] = None,
    ) -> List[HealResult]:
        """Scan long-term memory facts for temporal staleness and auto-heal them."""
        try:
            from memory.store import LocalFactStore
            from memory.staleness_detector import (
                scan_memory_staleness,
                add_pending_clarification,
                ClarificationRequest,
            )
        except ImportError as exc:
            log.warning("AutoHealer: jarvis_memory not available for staleness scan: %s", exc)
            return []

        if fact_store is None:
            try:
                fact_store = LocalFactStore()
            except Exception as exc:
                log.warning("AutoHealer: Failed to initialize LocalFactStore: %s", exc)
                return []

        issues = scan_memory_staleness(fact_store, now=now)
        repairs: List[HealResult] = []

        for issue in issues:
            if not issue.safe_to_auto_heal:
                # Ambiguous contradiction -> Escalate to human gate
                clarification = ClarificationRequest(
                    id=f"clarify-{int(time.time()*1000)}",
                    created_at=time.time(),
                    detector=issue.detector,
                    entity_key=issue.entity_key,
                    fact_indexes=[issue.fact_index] + ([issue.colliding_with_index] if issue.colliding_with_index is not None else []),
                    fact_texts=[issue.fact_text] + ([issue.colliding_text] if issue.colliding_text else []),
                    prompt=issue.clarification_prompt or f"Please clarify fact: {issue.fact_text}",
                )
                add_pending_clarification(clarification)
                repairs.append(
                    HealResult(
                        success=True,
                        subsystem="memory_cognition",
                        issue=f"Contradiction in memory ({issue.entity_key or 'unkeyed'})",
                        action_taken="Escalated to pending clarification queue for user guidance",
                        details=issue.clarification_prompt,
                    )
                )
                continue

            # Safe auto-healing
            if issue.suggested_action == "close":
                fact_store.close_fact(
                    issue.fact_index,
                    reason=f"{issue.detector}_expired" if issue.detector == "ttl" else f"{issue.detector}_invalidated",
                    valid_to=issue.expiry_time or (now or time.time()),
                )
                repairs.append(
                    HealResult(
                        success=True,
                        subsystem="memory_cognition",
                        issue=f"Stale Memory Fact: {issue.fact_text[:40]}...",
                        action_taken=f"Closed fact via {issue.detector} detector (Reason: {issue.reason})",
                        details=issue.reason,
                    )
                )
            elif issue.suggested_action == "supersede" and issue.colliding_text:
                fact_store.close_fact(
                    issue.fact_index,
                    reason="superseded",
                    superseded_by=issue.colliding_text,
                    valid_to=now or time.time(),
                )
                repairs.append(
                    HealResult(
                        success=True,
                        subsystem="memory_cognition",
                        issue=f"Superseded Memory Fact: {issue.fact_text[:40]}...",
                        action_taken=f"Marked fact superseded by '{issue.colliding_text[:30]}...'",
                        details=issue.reason,
                    )
                )
            elif issue.suggested_action == "decay" and issue.new_confidence is not None:
                fact_store.update_confidence(issue.fact_index, issue.new_confidence)
                repairs.append(
                    HealResult(
                        success=True,
                        subsystem="memory_cognition",
                        issue=f"Degraded Fact Confidence: {issue.fact_text[:40]}...",
                        action_taken=f"Decayed confidence to {issue.new_confidence:.2f}",
                        details=issue.reason,
                    )
                )

        return repairs

    # -------------------------------------------------------------------------
    # 6. Delegation & Agent Orchestration Self-Healing
    # -------------------------------------------------------------------------

    @classmethod
    def heal_delegation_failures(
        cls,
        db_path: Optional[Path] = None,
        orchestrator: Optional[Any] = None,
        project_root: Optional[Path] = None,
    ) -> List[HealResult]:
        """Detect and heal failed agent delegations in delegations.sqlite3 or orchestrator."""
        results: List[HealResult] = []
        root = project_root or Path(__file__).resolve().parents[1]
        target_db = Path(db_path) if db_path else root / ".jarvis-orchestration" / "delegations.sqlite3"

        # 1. Clean up stale orchestration locks
        orch_dir = target_db.parent if target_db.exists() else root / ".jarvis-orchestration"
        if orch_dir.exists():
            for lock_name in ("owner.lock", "workspace-snapshots.lock"):
                lock_file = orch_dir / lock_name
                if lock_file.exists():
                    try:
                        fd = os.open(lock_file, os.O_RDWR)
                        try:
                            import fcntl
                            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                            fcntl.flock(fd, fcntl.LOCK_UN)
                        except (BlockingIOError, OSError):
                            pass
                        finally:
                            os.close(fd)
                    except OSError:
                        pass

        # 2. Inspect delegations.sqlite3 for failed or interrupted jobs
        if target_db.exists():
            try:
                import sqlite3
                conn = sqlite3.connect(str(target_db), timeout=5.0)
                try:
                    c = conn.cursor()
                    rows = c.execute(
                        "SELECT id, request_key, data FROM jobs "
                        "WHERE data LIKE '%\"state\": \"failed\"%' "
                        "OR data LIKE '%\"state\": \"interrupted\"%' "
                        "OR data LIKE '%ECONNREFUSED%' "
                        "OR data LIKE '%usage limit%'"
                    ).fetchall()

                    for job_id, req_key, data_raw in rows:
                        try:
                            job = json.loads(data_raw)
                        except (TypeError, ValueError):
                            continue

                        output = str(job.get("output", ""))
                        agent = job.get("agent", "unknown")
                        is_conn_err = "ECONNREFUSED" in output or "connection refused" in output.lower()
                        is_quota_err = any(p in output.lower() for p in ("usage limit", "upgrade to pro", "429", "quota"))

                        if is_conn_err or is_quota_err or job.get("state") in ("failed", "interrupted"):
                            issue_type = (
                                "Connection refused (ECONNREFUSED)" if is_conn_err else
                                "Usage/Quota limit exceeded" if is_quota_err else
                                f"Job state {job.get('state')}"
                            )
                            try:
                                from harness.personas import get_fallback_candidates
                                fallbacks = get_fallback_candidates(agent)
                                rec_target = next((f for f in fallbacks if f != agent), "opencode")
                            except Exception:
                                rec_target = "opencode"

                            if not job.get("healed"):
                                job["healed"] = True
                                job["healing_timestamp"] = time.time()
                                job["failover_candidate"] = rec_target
                                job["healing_recommendation"] = f"Failover from {agent} to {rec_target} due to {issue_type}"
                                c.execute("UPDATE jobs SET data=? WHERE id=?", (json.dumps(job), job_id))
                                conn.commit()

                                log.info("AutoHealer: Healed delegation failure in job %s (%s: %s -> %s)",
                                         job_id, agent, issue_type, rec_target)
                                results.append(HealResult(
                                    success=True,
                                    subsystem="delegation",
                                    issue=f"Agent '{agent}' job {job_id[:8]} encountered {issue_type}",
                                    action_taken=f"Remediated delegation ledger and assigned failover target '{rec_target}'",
                                    details=f"Job {job_id}: {issue_type}",
                                ))
                finally:
                    conn.close()
            except Exception as exc:
                log.warning("AutoHealer: Failed inspecting delegations.sqlite3: %s", exc)

        # 3. If live orchestrator is provided, heal failed jobs in memory
        if orchestrator is not None and hasattr(orchestrator, "jobs"):
            for jid, ojob in list(orchestrator.jobs.items()):
                if ojob.get("state") == "failed" and not ojob.get("healed_by_watchdog"):
                    agent = ojob.get("agent")
                    out = ojob.get("output", "")
                    try:
                        from harness.agent_orchestrator import detect_failover_reason
                        reason = detect_failover_reason(out, ojob.get("exit_code"))
                    except Exception:
                        reason = None
                    if reason:
                        fallback = None
                        if hasattr(orchestrator, "select_fallback_agent"):
                            fallback = orchestrator.select_fallback_agent(agent, attempted={agent})
                        ojob["healed_by_watchdog"] = True
                        if hasattr(orchestrator, "mark_agent_unhealthy"):
                            orchestrator.mark_agent_unhealthy(agent, reason=reason)
                        results.append(HealResult(
                            success=True,
                            subsystem="delegation",
                            issue=f"Active orchestrator job {jid} failed on {agent} ({reason})",
                            action_taken=f"Marked {agent} unhealthy and prepared failover to {fallback or 'opencode'}",
                            details=f"Failover reason: {reason}",
                        ))

        return results

    # -------------------------------------------------------------------------
    # 7. Test-Job Watchdog
    # -------------------------------------------------------------------------

    @classmethod
    def test_job_watchdog(
        cls,
        max_duration_seconds: float = 300.0,
        orchestrator: Optional[Any] = None,
        db_path: Optional[Path] = None,
        project_root: Optional[Path] = None,
    ) -> List[HealResult]:
        """Watchdog for stuck, hung, or timed-out test/delegation jobs."""
        results: List[HealResult] = []
        root = project_root or Path(__file__).resolve().parents[1]
        target_db = Path(db_path) if db_path else root / ".jarvis-orchestration" / "delegations.sqlite3"
        now_ts = time.time()

        # 1. Watchdog active orchestrator processes
        if orchestrator is not None:
            active_jobs = getattr(orchestrator, "jobs", {})
            processes = getattr(orchestrator, "processes", {})
            for jid, job in list(active_jobs.items()):
                state = job.get("state")
                if state in ("running", "queued"):
                    proc = processes.get(jid)
                    if proc is not None:
                        try:
                            os.kill(proc.pid, 0)
                        except (ProcessLookupError, OSError):
                            job["state"] = "failed"
                            job["error"] = "Process terminated unexpectedly (detected by watchdog)"
                            processes.pop(jid, None)
                            results.append(HealResult(
                                success=True,
                                subsystem="test_job_watchdog",
                                issue=f"Job {jid} process PID {proc.pid} vanished unexpectedly",
                                action_taken=f"Reaped ghost process for job {jid} and updated state to failed",
                            ))
                            continue

                    created_at_str = job.get("created_at")
                    elapsed = 0.0
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(created_at_str)
                        elapsed = (datetime.now().astimezone() - dt).total_seconds()
                    except Exception:
                        pass

                    if elapsed > max_duration_seconds:
                        job["state"] = "timed_out"
                        job["cancel_requested"] = True
                        if proc is not None:
                            try:
                                proc.kill()
                            except Exception:
                                pass
                            processes.pop(jid, None)
                        results.append(HealResult(
                            success=True,
                            subsystem="test_job_watchdog",
                            issue=f"Job {jid} hung for {elapsed:.1f}s (exceeded limit {max_duration_seconds}s)",
                            action_taken=f"Killed hung job {jid} and marked timed_out",
                        ))

        # 2. Watchdog ledger database jobs that never reached a terminal state
        if target_db.exists():
            try:
                import sqlite3
                conn = sqlite3.connect(str(target_db), timeout=5.0)
                try:
                    c = conn.cursor()
                    rows = c.execute(
                        "SELECT id, data FROM jobs "
                        "WHERE data LIKE '%\"state\": \"running\"%' "
                        "OR data LIKE '%\"state\": \"queued\"%'"
                    ).fetchall()

                    for jid, data_raw in rows:
                        try:
                            job = json.loads(data_raw)
                        except (TypeError, ValueError):
                            continue

                        state = job.get("state")
                        updated_at = job.get("updated_at")
                        elapsed = 0.0
                        if isinstance(updated_at, (int, float)):
                            elapsed = now_ts - updated_at
                        elif isinstance(updated_at, str):
                            try:
                                from datetime import datetime
                                dt = datetime.fromisoformat(updated_at)
                                elapsed = (datetime.now().astimezone() - dt).total_seconds()
                            except Exception:
                                pass

                        if elapsed > max_duration_seconds or state in ("running", "queued"):
                            job["state"] = "timed_out"
                            job["summary"] = f"Watchdog detected stale job in {state} state for {elapsed:.1f}s."
                            job["watchdog_recovered"] = True
                            c.execute("UPDATE jobs SET data=? WHERE id=?", (json.dumps(job), jid))
                            conn.commit()
                            results.append(HealResult(
                                success=True,
                                subsystem="test_job_watchdog",
                                issue=f"Ledger job {jid} was stalled in '{state}' for {elapsed:.1f}s",
                                action_taken=f"Watchdog transitioned stalled job {jid} to timed_out",
                            ))
                finally:
                    conn.close()
            except Exception as exc:
                log.warning("AutoHealer: test_job_watchdog ledger scan notice: %s", exc)

        return results

    # -------------------------------------------------------------------------
    # 8. Composite Remediation Dispatcher
    # -------------------------------------------------------------------------

    @classmethod
    def auto_heal_action(
        cls, alert_type: str, resource_name: str, details: str = ""
    ) -> Optional[HealResult]:
        """Map a detected alert type to its corresponding automated healing action."""
        t = alert_type.lower()
        if t in ("service_failure", "server_down"):
            return cls.heal_service(resource_name)
        elif t in ("memory_critical", "memory_high"):
            return cls.heal_memory()
        elif t in ("disk_exhaustion", "disk_full"):
            return cls.heal_disk()
        elif t in ("memory_staleness", "cognitive_drift", "fact_contradiction"):
            res = cls.heal_memory_staleness()
            return res[0] if res else None
        elif t in ("network_down",):
            # Attempt to restart user networking bridge if local
            return cls.heal_stale_sockets()[0] if cls.heal_stale_sockets() else None
        elif t in ("cpu_overload", "cpu_critical", "cpu_high", "runaway_process", "process_bottleneck"):
            return cls.heal_runaway_processes()
        elif t in ("voice_failure", "voice_degraded", "voice_session", "voice_stuck", "voice_hang", "voice_disconnect"):
            return cls.heal_voice_session()
        elif t in ("audio_sink_hang", "hanging_audio_sink"):
            return cls.heal_hanging_audio_sinks()
        elif t in ("delegation_failure", "agent_failure", "agent_quota_exceeded", "agent_disconnect"):
            res = cls.heal_delegation_failures()
            return res[0] if res else None
        elif t in ("test_job_stalled", "job_watchdog", "stuck_test_job", "delegation_timeout"):
            res = cls.test_job_watchdog()
            return res[0] if res else None
        return None

    @classmethod
    def scan_and_heal(cls) -> List[HealResult]:
        """Perform a full system diagnostic scan and apply safe auto-repairs."""
        repairs: List[HealResult] = []

        # 1. Clean up dead Unix sockets
        stale_socks = cls.heal_stale_sockets()
        repairs.extend(stale_socks)

        # 2. Clean up hanging audio sinks
        try:
            sink_res = cls.heal_hanging_audio_sinks()
            if "Terminated" in sink_res.action_taken:
                repairs.append(sink_res)
        except Exception as exc:
            log.warning("AutoHealer: Audio sink heal notice: %s", exc)

        # 3. Check for failed systemd user services
        rc, out, _ = cls._run_cmd(["systemctl", "--user", "--failed", "--plain", "--no-legend"])
        if rc == 0 and out:
            for line in out.splitlines():
                parts = line.strip().split()
                if parts:
                    unit_name = parts[0]
                    # Automatically heal failed jarvis units
                    if any(prefix in unit_name for prefix in ("jarvis", "omarchy", "pipewire", "wireplumber")):
                        res = cls.heal_service(unit_name, user_scope=True)
                        repairs.append(res)

        # 4. Check memory pressure
        mem_res = cls.heal_memory()
        repairs.append(mem_res)

        # 5. Check and auto-heal runaway processes (threshold 90%)
        try:
            cpu_res = cls.heal_runaway_processes(cpu_threshold=90.0)
            if "Terminated" in cpu_res.action_taken:
                repairs.append(cpu_res)
        except Exception as exc:
            log.warning("AutoHealer: Runaway process heal notice: %s", exc)

        # 6. Scan and auto-heal cognitive memory staleness
        try:
            mem_repairs = cls.heal_memory_staleness()
            repairs.extend(mem_repairs)
        except Exception as exc:
            log.warning("AutoHealer: Memory staleness scan failed: %s", exc)

        # 7. Scan and auto-heal delegation failures and watchdog test jobs
        try:
            delegation_repairs = cls.heal_delegation_failures()
            repairs.extend(delegation_repairs)
            watchdog_repairs = cls.test_job_watchdog()
            repairs.extend(watchdog_repairs)
        except Exception as exc:
            log.warning("AutoHealer: Delegation/watchdog healing notice: %s", exc)

        return repairs
