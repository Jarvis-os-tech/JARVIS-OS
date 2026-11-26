"""Unit tests for JARVIS OS Autonomous Self-Healing Subsystem."""
import asyncio
from pathlib import Path
import socket
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from core.self_healer import AutoHealer, HealResult
from core.system_monitor import AlertAction, AlertStateManager, DesktopNotifier, JarvisVoiceSpeaker


class TestSelfHealer(unittest.IsolatedAsyncioTestCase):

    async def test_heal_microphone_mute_success(self):
        with patch.object(AutoHealer, "_async_run_cmd", AsyncMock(return_value=(0, "", ""))) as mock_cmd:
            res = await AutoHealer.heal_microphone_mute("test_source")
            self.assertTrue(res.success)
            self.assertEqual(res.subsystem, "audio")
            self.assertIn("Unmuted microphone", res.action_taken)
            mock_cmd.assert_awaited_once_with(["pactl", "set-source-mute", "test_source", "0"], timeout=3.0)

    async def test_heal_microphone_mute_failure(self):
        with patch.object(AutoHealer, "_async_run_cmd", AsyncMock(return_value=(1, "", "Connection refused"))):
            res = await AutoHealer.heal_microphone_mute()
            self.assertFalse(res.success)
            self.assertEqual(res.details, "Connection refused")

    async def test_heal_microphone_volume(self):
        with patch.object(AutoHealer, "_async_run_cmd", AsyncMock(return_value=(0, "", ""))) as mock_cmd:
            res = await AutoHealer.heal_microphone_volume("test_source", 80)
            self.assertTrue(res.success)
            self.assertEqual(res.subsystem, "audio")
            self.assertIn("80%", res.action_taken)
            mock_cmd.assert_awaited_once_with(["pactl", "set-source-volume", "test_source", "80%"], timeout=3.0)

    def test_heal_service_success(self):
        # 1. reset-failed -> 0, 2. restart -> 0, 3. is-active -> (0, 'active', '')
        responses = [
            (0, "", ""),          # reset-failed
            (0, "", ""),          # restart
            (0, "active", ""),    # is-active
        ]
        with patch.object(AutoHealer, "_run_cmd", side_effect=responses) as mock_run:
            with patch.object(AutoHealer, "heal_stale_sockets", return_value=[]):
                res = AutoHealer.heal_service("jarvis-voice")
                self.assertTrue(res.success)
                self.assertEqual(res.subsystem, "service")
                self.assertIn("restarted 'jarvis-voice.service'", res.action_taken)

    def test_heal_service_restart_failure(self):
        responses = [
            (0, "", ""),                         # reset-failed
            (1, "", "Job for service failed"),   # restart failed
        ]
        with patch.object(AutoHealer, "_run_cmd", side_effect=responses):
            with patch.object(AutoHealer, "heal_stale_sockets", return_value=[]):
                res = AutoHealer.heal_service("failing-service")
                self.assertFalse(res.success)
                self.assertIn("Job for service failed", res.details)

    def test_heal_stale_sockets(self, tmp_path=None):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            sock_dir = Path(td)
            dead_sock = sock_dir / "dead_daemon.sock"

            # Create a real Unix domain socket file
            srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            srv.bind(str(dead_sock))
            srv.close()  # Closed, so connection will be refused

            self.assertTrue(dead_sock.exists())
            results = AutoHealer.heal_stale_sockets(socket_dir=sock_dir)
            self.assertEqual(len(results), 1)
            self.assertTrue(results[0].success)
            self.assertFalse(dead_sock.exists())

    def test_heal_disk_pruning(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            dummy_cache = Path(td) / "dummy.wav"
            dummy_cache.write_bytes(b"0" * 1024)
            with patch("core.self_healer.Path.home", return_value=Path(td)):
                res = AutoHealer.heal_disk()
                self.assertTrue(res.success)
                self.assertEqual(res.subsystem, "storage")

    def test_heal_memory(self):
        res = AutoHealer.heal_memory()
        self.assertTrue(res.success)
        self.assertEqual(res.subsystem, "memory")
        self.assertIn("gc.collect()", res.action_taken)

    def test_auto_heal_action_routing(self):
        with patch.object(AutoHealer, "heal_service", return_value=HealResult(True, "service", "failed", "restarted")):
            res = AutoHealer.auto_heal_action("service_failure", "jarvis-voice.service")
            self.assertIsNotNone(res)
            self.assertTrue(res.success)

        with patch.object(AutoHealer, "heal_memory", return_value=HealResult(True, "memory", "high RAM", "collected")):
            res = AutoHealer.auto_heal_action("memory_critical", "RAM")
            self.assertIsNotNone(res)
            self.assertTrue(res.success)

        with patch.object(AutoHealer, "heal_disk", return_value=HealResult(True, "storage", "disk full", "pruned")):
            res = AutoHealer.auto_heal_action("disk_exhaustion", "/")
            self.assertIsNotNone(res)
            self.assertTrue(res.success)

    def test_dispatch_actions_auto_heal_integration(self):
        notifier = MagicMock(spec=DesktopNotifier)
        speaker = MagicMock(spec=JarvisVoiceSpeaker)
        engine = AlertStateManager()

        heal_mock = HealResult(
            success=True,
            subsystem="service",
            issue="Service jarvis-voice down",
            action_taken="Restarted jarvis-voice.service successfully",
        )

        with patch.object(AutoHealer, "auto_heal_action", return_value=heal_mock):
            action = AlertAction(
                action_type="ALERT",
                alert_type="service_failure",
                category="service",
                name="jarvis-voice",
                message="Service is inactive",
                urgency="critical",
            )
            engine.dispatch_actions(
                [action],
                notifier=notifier,
                jarvis_speaker=speaker,
                auto_heal=True,
                desktop_notify=True,
                voice_alert=True,
                voice_battery_only=False,
            )

            # Notifier should receive the resolved notice
            notifier.notify.assert_called_once()
            args, kwargs = notifier.notify.call_args
            self.assertIn("[RESOLVED] jarvis-voice", args[0])
            self.assertIn("[Auto-Healed]", args[1])

            # Speaker should announce recovery
            speaker.speak_alert.assert_called_once()
            self.assertIn("System recovered: jarvis-voice was automatically healed", speaker.speak_alert.call_args[0][0])

    def test_heal_delegation_failures(self):
        import json, sqlite3, tempfile
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "delegations.sqlite3"
            conn = sqlite3.connect(str(db_path))
            conn.execute("CREATE TABLE jobs (id TEXT PRIMARY KEY, request_key TEXT UNIQUE, fingerprint TEXT, data TEXT)")
            job = {
                "id": "failed-job-123",
                "agent": "claude",
                "state": "failed",
                "output": "API Error: Connection refused (ECONNREFUSED)",
            }
            conn.execute("INSERT INTO jobs VALUES(?, ?, ?, ?)", ("failed-job-123", "rk1", "fp1", json.dumps(job)))
            conn.commit()
            conn.close()

            results = AutoHealer.heal_delegation_failures(db_path=db_path)
            self.assertEqual(len(results), 1)
            self.assertTrue(results[0].success)
            self.assertEqual(results[0].subsystem, "delegation")
            self.assertIn("Connection refused (ECONNREFUSED)", results[0].issue)

    def test_test_job_watchdog_hung_process(self):
        import time
        mock_proc = MagicMock()
        mock_proc.pid = 999999
        mock_orch = MagicMock()
        mock_orch.jobs = {
            "hung-task-456": {
                "id": "hung-task-456",
                "state": "running",
                "created_at": "2020-01-01T00:00:00+00:00",  # Long ago
            }
        }
        mock_orch.processes = {"hung-task-456": mock_proc}

        with patch("os.kill", side_effect=ProcessLookupError):
            results = AutoHealer.test_job_watchdog(max_duration_seconds=30.0, orchestrator=mock_orch)
            self.assertEqual(len(results), 1)
            self.assertTrue(results[0].success)
            self.assertEqual(results[0].subsystem, "test_job_watchdog")
            self.assertEqual(mock_orch.jobs["hung-task-456"]["state"], "failed")

    def test_auto_heal_action_delegation_routing(self):
        with patch.object(AutoHealer, "heal_delegation_failures", return_value=[HealResult(True, "delegation", "failed", "healed")]):
            res = AutoHealer.auto_heal_action("delegation_failure", "orchestrator")
            self.assertIsNotNone(res)
            self.assertTrue(res.success)
            self.assertEqual(res.subsystem, "delegation")

        with patch.object(AutoHealer, "test_job_watchdog", return_value=[HealResult(True, "test_job_watchdog", "hung", "reaped")]):
            res = AutoHealer.auto_heal_action("test_job_stalled", "test_runner")
            self.assertIsNotNone(res)
            self.assertTrue(res.success)
            self.assertEqual(res.subsystem, "test_job_watchdog")

    def test_heal_hanging_audio_sinks_terminates_pw_play(self):
        # pgrep returns pid 45678 for pw-play, then none for pw-record
        pgrep_results = [
            (0, "45678\n", ""),  # pw-play
            (1, "", ""),          # pw-record
        ]
        with patch.object(AutoHealer, "_run_cmd", side_effect=pgrep_results):
            with patch("os.kill") as mock_kill:
                res = AutoHealer.heal_hanging_audio_sinks()
                self.assertTrue(res.success)
                self.assertEqual(res.subsystem, "audio")
                self.assertIn("Terminated 1 hanging audio process", res.action_taken)
                self.assertIn("45678", res.action_taken)
                mock_kill.assert_any_call(45678, 15)  # SIGTERM

    def test_heal_hanging_audio_sinks_no_sinks(self):
        with patch.object(AutoHealer, "_run_cmd", return_value=(1, "", "")):
            res = AutoHealer.heal_hanging_audio_sinks()
            self.assertTrue(res.success)
            self.assertEqual(res.subsystem, "audio")
            self.assertIn("No hanging audio sinks detected", res.action_taken)

    def test_heal_voice_session(self):
        sink_mock = HealResult(True, "audio", "sinks", "Terminated 1 hanging audio process(es) (PIDs: [423077])")
        with patch.object(AutoHealer, "heal_hanging_audio_sinks", return_value=sink_mock):
            with patch.object(AutoHealer, "heal_stale_sockets", return_value=[]):
                with patch.object(AutoHealer, "_run_cmd", side_effect=[
                    (0, "active", ""),  # is-active jarvis-voice.service
                ]):
                    res = AutoHealer.heal_voice_session()
                    self.assertTrue(res.success)
                    self.assertEqual(res.subsystem, "voice")
                    self.assertIn("Terminated 1 hanging audio process", res.action_taken)

    def test_heal_runaway_processes_terminates_high_cpu(self):
        # ps returns a runaway python process at 98.5% CPU
        ps_output = (
            " 88881      1  98.5 python3         python3 -m runaway_loop\n"
            " 12345      1   2.1 pipewire        pipewire\n"
        )
        with patch.object(AutoHealer, "_run_cmd", return_value=(0, ps_output, "")):
            with patch("os.kill") as mock_kill:
                res = AutoHealer.heal_runaway_processes(cpu_threshold=80.0)
                self.assertTrue(res.success)
                self.assertEqual(res.subsystem, "cpu")
                self.assertIn("Terminated 1 runaway process", res.action_taken)
                self.assertIn("88881", res.action_taken)
                mock_kill.assert_any_call(88881, 15)  # SIGTERM

    def test_heal_runaway_processes_protects_system_and_self(self):
        import os
        my_pid = os.getpid()
        # High CPU on protected system processes (init, systemd, pipewire) and self
        ps_output = (
            f"     1      0  99.0 systemd         /sbin/init\n"
            f" {my_pid}      1  95.0 pytest          pytest\n"
            f"   999      1  92.0 pipewire        pipewire\n"
        )
        with patch.object(AutoHealer, "_run_cmd", return_value=(0, ps_output, "")):
            with patch("os.kill") as mock_kill:
                res = AutoHealer.heal_runaway_processes(cpu_threshold=80.0)
                self.assertTrue(res.success)
                self.assertEqual(res.subsystem, "cpu")
                self.assertIn("No runaway processes detected", res.action_taken)
                mock_kill.assert_not_called()

    def test_auto_heal_action_voice_and_cpu_routing(self):
        with patch.object(AutoHealer, "heal_runaway_processes", return_value=HealResult(True, "cpu", "high cpu", "terminated")):
            res = AutoHealer.auto_heal_action("cpu_overload", "CPU")
            self.assertIsNotNone(res)
            self.assertTrue(res.success)
            self.assertEqual(res.subsystem, "cpu")

            res_runaway = AutoHealer.auto_heal_action("runaway_process", "PID 123")
            self.assertIsNotNone(res_runaway)
            self.assertEqual(res_runaway.subsystem, "cpu")

        with patch.object(AutoHealer, "heal_voice_session", return_value=HealResult(True, "voice", "degraded", "reconnected")):
            res = AutoHealer.auto_heal_action("voice_session", "session")
            self.assertIsNotNone(res)
            self.assertTrue(res.success)
            self.assertEqual(res.subsystem, "voice")

            res_hang = AutoHealer.auto_heal_action("voice_hang", "session")
            self.assertIsNotNone(res_hang)
            self.assertEqual(res_hang.subsystem, "voice")

        with patch.object(AutoHealer, "heal_hanging_audio_sinks", return_value=HealResult(True, "audio", "sinks", "purged")):
            res = AutoHealer.auto_heal_action("audio_sink_hang", "pw-play")
            self.assertIsNotNone(res)
            self.assertTrue(res.success)
            self.assertEqual(res.subsystem, "audio")



if __name__ == "__main__":
    unittest.main()
