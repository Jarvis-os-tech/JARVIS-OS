"""Restricted geometry execution; no API keys, network, or project-store mounts."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time

from .projects import WorkspaceError


def availability():
    if not importlib.util.find_spec('build123d'):
        return 'Install the CAD dependencies with setup.sh, then restart Ada.'
    if not shutil.which('bwrap'):
        return 'Install bubblewrap to enable isolated CAD builds (sudo apt install bubblewrap).'
    return ''


def command(mode, inputs, output):
    cmd = ['bwrap', '--unshare-all', '--die-with-parent', '--new-session', '--cap-drop', 'ALL', '--clearenv']
    for path in ('/usr', '/lib', '/lib64'):
        if Path(path).exists():
            cmd += ['--ro-bind', path, path]
    if Path('/etc/ld.so.cache').exists():
        cmd += ['--ro-bind', '/etc/ld.so.cache', '/etc/ld.so.cache']
    cmd += ['--ro-bind', sys.prefix, '/runtime', '--ro-bind', str(Path(__file__).with_name('cad_worker.py')), '/worker.py',
            '--ro-bind', str(inputs), '/input', '--bind', str(output), '/output',
            '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp', '--chdir', '/output']
    for key, value in {'HOME': '/tmp', 'PATH': '/runtime/bin:/usr/bin', 'OPENBLAS_NUM_THREADS': '1',
                       'OMP_NUM_THREADS': '1', 'PYTHONDONTWRITEBYTECODE': '1'}.items():
        cmd += ['--setenv', key, value]
    return cmd + ['--', '/runtime/bin/python', '-I', '/worker.py', mode]


def run_worker(mode, inputs, output, cancelled=lambda: False):
    output.mkdir(parents=True, exist_ok=True)
    message = availability()
    if message:
        raise WorkspaceError(message)
    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen(command(mode, inputs, output), stdout=log, stderr=log,
                                   env={'PATH': '/usr/bin:/bin'}, start_new_session=True)
        deadline = time.monotonic() + 120
        try:
            while process.poll() is None:
                if cancelled():
                    raise WorkspaceError('CAD generation was cancelled.')
                if time.monotonic() > deadline:
                    raise WorkspaceError('This CAD build exceeded the two-minute geometry limit. Simplify the design and retry.')
                time.sleep(0.15)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        if process.returncode:
            log.seek(0, os.SEEK_END)
            log.seek(max(0, log.tell() - 5000))
            detail = log.read().decode('utf-8', errors='replace')
            raise WorkspaceError(f'CAD {mode} failed: {detail.strip()[:4000]}')
    for file in output.rglob('*'):
        if file.is_symlink() or (file.is_file() and file.stat().st_size > 20 * 1024**2):
            raise WorkspaceError('Generated CAD output exceeds the supported file limits.')
