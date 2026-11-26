"""Exercise the gate with genuinely passing, skipped and broken test runs."""
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest

from harness.release_manager import ReleaseManager
from scripts.behavior_gate import ROOT, load_contract, main, source_digest


def test_fingerprint_tracks_department_schema_and_ignores_local_state(tmp_path, monkeypatch):
    monkeypatch.setattr('scripts.behavior_gate.ROOT', tmp_path)
    department = tmp_path / 'departments' / 'memory'
    department.mkdir(parents=True)
    schema = department / 'schema.sql'
    schema.write_text('SELECT 1;')
    before = source_digest()
    schema.write_text('SELECT 2;')
    after = source_digest()
    assert after != before
    (department / 'state').mkdir()
    (department / 'state' / 'local.json').write_text('{}')
    assert source_digest() == after


def test_fingerprint_ignores_dist_and_disk_image_suffixes(tmp_path, monkeypatch):
    monkeypatch.setattr('scripts.behavior_gate.ROOT', tmp_path)
    packaging = tmp_path / 'packaging'
    packaging.mkdir()
    script = packaging / 'build'
    script.write_text('echo ok\n')
    baseline = source_digest()

    dist = packaging / 'dist'
    dist.mkdir()
    (dist / 'artifact.txt').write_text('ignored build artifact')
    for suffix in ('.raw', '.iso', '.img', '.qcow2', '.vmdk', '.ova', '.ISO'):
        (packaging / f'image{suffix}').write_bytes(b'binary image data')

    assert source_digest() == baseline


def test_fingerprint_streams_and_guards_large_files(tmp_path, monkeypatch):
    monkeypatch.setattr('scripts.behavior_gate.ROOT', tmp_path)
    monkeypatch.setattr('scripts.behavior_gate.MAX_DIGEST_FILE_BYTES', 16)
    monkeypatch.setattr(Path, 'read_bytes', Mock(side_effect=AssertionError('should stream instead of read_bytes')))

    scripts_dir = tmp_path / 'scripts'
    scripts_dir.mkdir()
    small = scripts_dir / 'small.py'
    small.write_bytes(b'1234567890')
    large = scripts_dir / 'large.bin'
    large.write_bytes(b'x' * 32)

    digest_before = source_digest()
    large.write_bytes(b'y' * 64)
    digest_after = source_digest()
    assert digest_after != digest_before


@pytest.mark.parametrize('body,passed', [
    ('def test_example(): assert True', True),
    ('def test_example(): assert False', False),
    ('def test_example(): pytest.skip("unavailable")', False),
    ('@pytest.mark.xfail(reason="known bug")\ndef test_example(): assert False', False),
    ('@pytest.mark.xfail(reason="unexpected pass")\ndef test_example(): assert True', False),
    ('@pytest.fixture(autouse=True)\ndef setup(): raise RuntimeError("setup failed")\ndef test_example(): pass', False),
    ('@pytest.fixture(autouse=True)\ndef setup():\n yield\n raise RuntimeError("teardown failed")\ndef test_example(): pass', False),
    ('def test_different(): pass', False),
    ('@pytest.mark.parametrize("value", [1, 2])\ndef test_example(value): assert value > 0', True),
])
def test_real_pytest_runs_cannot_silently_weaken_gate(tmp_path, body, passed):
    (tmp_path / 'test_example.py').write_text('import pytest\n' + body + '\n')
    report = tmp_path / 'result.json'
    bootstrap = (
        'import pytest\nfrom scripts.behavior_gate import BehaviorResults\n'
        'cases = [{"id":"EXAMPLE-1", "expectation":"example", '
        '"tests":["test_example.py::test_example"]}]\n'
        f'raise SystemExit(pytest.main(["-q", "test_example.py"], '
        f'plugins=[BehaviorResults(cases, {str(report)!r})]))\n'
    )
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
    result = subprocess.run([sys.executable, '-c', bootstrap], cwd=tmp_path,
                            env=env, capture_output=True, text=True, timeout=15)
    assert (result.returncode == 0) is passed, result.stdout + result.stderr
    payload = json.loads(report.read_text())
    assert payload['passed'] is passed


def test_empty_or_duplicate_contracts_are_rejected(tmp_path):
    path = tmp_path / 'contracts.json'
    for cases in ([], [dict(id='X', expectation='x', tests=[])],
                  [dict(id='X', expectation='x', tests=['../outside.py::test_x'])]):
        path.write_text(json.dumps({'schema_version': 1, 'cases': cases}))
        with pytest.raises(ValueError):
            load_contract(path)


def test_release_missing_gate_blocks_before_running_candidate(tmp_path, monkeypatch):
    run = Mock()
    monkeypatch.setattr('harness.release_manager.subprocess.run', run)
    with pytest.raises(RuntimeError, match='lacks the required'):
        ReleaseManager(tmp_path / 'runtime').verify_behavior(tmp_path, sys.executable)
    run.assert_not_called()


@pytest.mark.parametrize('exit_code,report,accepted', [
    (1, {'passed': True}, False),
    (0, {'passed': False}, False),
    (0, None, False),
    (0, {'passed': True}, True),
])
def test_release_requires_success_and_fresh_gate_evidence(tmp_path, monkeypatch, exit_code, report, accepted):
    (tmp_path / 'scripts').mkdir()
    (tmp_path / 'scripts/behavior_gate.py').write_text('# candidate runner')
    (tmp_path / 'behavior-gate.json').write_text('{"passed":true}')  # stale evidence

    def run(*args, **kwargs):
        if report is not None:
            (tmp_path / 'behavior-gate.json').write_text(json.dumps(report))
        return subprocess.CompletedProcess([], exit_code, '', '')

    monkeypatch.setattr('harness.release_manager.subprocess.run', run)
    manager = ReleaseManager(tmp_path / 'runtime')
    if accepted:
        manager.verify_behavior(tmp_path, sys.executable)
    else:
        with pytest.raises(RuntimeError):
            manager.verify_behavior(tmp_path, sys.executable)


def test_timeout_replaces_stale_success_with_failure(tmp_path, monkeypatch):
    path = tmp_path / 'report.json'
    path.write_text('{"passed":true}')
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired('synthetic test runner', 1)
    monkeypatch.setattr('scripts.behavior_gate.subprocess.run', timeout)
    assert main(['--report', str(path), '--timeout', '1']) == 1
    payload = json.loads(path.read_text())
    assert payload['passed'] is False and 'timed out' in payload['error']
