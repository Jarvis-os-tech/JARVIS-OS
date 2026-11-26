"""Read installed local agent paths without invoking package-manager wrappers."""
from pathlib import Path
import os
import shutil

_LAYOUT = {
    'codex': ('codex/latest/bin/codex',),
    'claude': ('claude/latest/claude',),
    'opencode': ('npm-opencode-cli/latest/node_modules/.bin/opencode',),
    'gemini': ('gemini/latest/node_modules/.bin/gemini',),
    'antigravity': (),
    'omp': ('github-can1357-oh-my-pi/latest/omp', 'oh-my-pi/latest/omp'),
    'pi': ('pi/latest/pi/pi',),
    'crush': ('crush/latest/crush', 'crush/latest/crush_*/crush'),
    'hermes': (),
    'api_agent': (),
}


def installed_executables(home=None):
    home = Path(home or Path.home())
    root = home / '.local/share/mise/installs'
    result = {}
    for agent, patterns in _LAYOUT.items():
        candidates = [path for pattern in patterns for path in root.glob(pattern)
                      if path.is_file() and os.access(path, os.X_OK)]
        if agent == 'antigravity':
            cli = home / '.local/bin/agy'
            result[agent] = shutil.which('agy') or (str(cli) if cli.is_file() and os.access(cli, os.X_OK) else None)
        elif agent == 'api_agent':
            daemon_ts = home / 'Projects/api-anything/daemon/daemon.ts'
            result[agent] = str(daemon_ts) if daemon_ts.is_file() else None
        else:
            result[agent] = str(candidates[0]) if candidates else shutil.which(agent)
    return result


def installed_path(home=None):
    root = Path(home or Path.home()) / '.local/share/mise/installs'
    entries = [str(Path(path).parent) for path in installed_executables(home).values() if path]
    node = root / 'node/latest/bin'
    if (node / 'node').is_file():
        entries.append(str(node))
    return os.pathsep.join(dict.fromkeys(entries + os.environ.get('PATH', '').split(os.pathsep)))
