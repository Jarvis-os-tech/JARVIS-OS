"""Unit tests for JournalStreamer pattern matching and deduplication."""
import pytest
import time
from control.bridge.journal_streamer import (
    JournalStreamer,
    PATTERN_OOM,
    PATTERN_SEGFAULT,
    PATTERN_COREDUMP,
    PATTERN_DISK_ERROR,
    PATTERN_SERVICE_FAIL,
)
from control.bridge.constants import EVENT_JOURNAL_OOM_KILL


def test_journal_streamer_patterns():
    # Check OOM pattern
    oom_msg = "Out of memory: Kill process 1234 (firefox)"
    assert PATTERN_OOM.search(oom_msg) is not None

    # Check segfault pattern
    seg_msg = "myapp[5678]: segfault at 00000000 ip 00007fa0 sp 00007ffd error 4 in mylib.so"
    assert PATTERN_SEGFAULT.search(seg_msg) is not None

    # Check coredump pattern
    core_msg = "Process 1234 (crashapp) of user 1000 dumped core"
    assert PATTERN_COREDUMP.search(core_msg) is not None

    # Check disk error pattern
    disk_msg = "BTRFS: error (device nvme0n1p2) in btrfs_commit_transaction:2280"
    assert PATTERN_DISK_ERROR.search(disk_msg) is not None


def test_journal_streamer_dedup():
    emitted = []
    streamer = JournalStreamer(on_event=lambda name, payload: emitted.append((name, payload)))

    assert streamer._should_dedup("test_key", window_seconds=60.0) is False
    # Immediate second check should be deduplicated
    assert streamer._should_dedup("test_key", window_seconds=60.0) is True

    # Test analyze_entry emits OOM
    entry = {
        "MESSAGE": "Out of memory: Kill process 9999 (rogue_proc)",
        "_COMM": "rogue_proc",
        "_PID": "9999",
    }
    streamer._analyze_entry(entry)
    assert len(emitted) == 1
    assert emitted[0][0] == EVENT_JOURNAL_OOM_KILL
    assert emitted[0][1]["process"] == "rogue_proc"
