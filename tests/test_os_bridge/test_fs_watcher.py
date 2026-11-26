"""Unit tests for FsWatcher filtering."""
import pytest
from pathlib import Path
from control.bridge.fs_watcher import FsWatcher, INCOMPLETE_EXTENSIONS


def test_fs_watcher_extensions():
    # Incomplete download extensions should be recognized
    assert ".part" in INCOMPLETE_EXTENSIONS
    assert ".crdownload" in INCOMPLETE_EXTENSIONS
    assert ".tmp" in INCOMPLETE_EXTENSIONS
    assert ".download" in INCOMPLETE_EXTENSIONS
    assert ".aria2" in INCOMPLETE_EXTENSIONS

    # Normal extensions should not be in incomplete set
    assert ".pdf" not in INCOMPLETE_EXTENSIONS
    assert ".png" not in INCOMPLETE_EXTENSIONS
    assert ".zip" not in INCOMPLETE_EXTENSIONS
