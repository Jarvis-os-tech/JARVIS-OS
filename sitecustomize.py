"""Universal Import Aliasing Bootstrapper for JARVIS OS Modular Restructure.

Enables seamless transition between legacy package names and normalized pillars:
- core <-> kernel
- voice_layer <-> voice
- audio <-> voice
- jarvis_control <-> control
- jarvis_os_bridge <-> control.bridge
- jarvis_memory <-> memory
- orchestration <-> harness
- departments <-> department_agents
- widget_engine <-> widgets
- ui.jarvis_widgets <-> widgets
- ui.jarvis_shell <-> shell
"""
import sys
import importlib
import importlib.abc
from pathlib import Path

ROOT = Path(__file__).resolve().parent

ALIASES = {
    "core": "kernel",
    "kernel": "core",
    "voice_layer": "voice",
    "voice": "voice_layer",
    "jarvis_control": "control",
    "control": "jarvis_control",
    "jarvis_os_bridge": "control.bridge",
    "jarvis_memory": "memory",
    "memory": "jarvis_memory",
    "orchestration": "harness",
    "harness": "orchestration",
    "departments": "department_agents",
    "department_agents": "departments",
    "widget_engine": "widgets",
    "widgets": "widget_engine",
}

class UniversalAliasFinder(importlib.abc.MetaPathFinder):
    _in_progress = set()

    def find_spec(self, fullname, path=None, target=None):
        if fullname in self._in_progress:
            return None

        parts = fullname.split(".")
        root_pkg = parts[0]

        # If root_pkg exists directly as a real package on disk, do not intercept
        root_dir = ROOT / root_pkg
        if (root_dir / "__init__.py").exists():
            return None

        # Check if root_pkg is an alias
        if root_pkg not in ALIASES:
            return None

        target_root = ALIASES[root_pkg]
        target_fullname = ".".join([target_root] + parts[1:])

        # If target is already in sys.modules, reuse it directly
        if target_fullname in sys.modules:
            mod = sys.modules[target_fullname]
            sys.modules[fullname] = mod
            return getattr(mod, "__spec__", None)

        self._in_progress.add(fullname)
        try:
            mod = importlib.import_module(target_fullname)
            sys.modules[fullname] = mod
            if len(parts) > 1:
                parent_name = ".".join(parts[:-1])
                if parent_name in sys.modules:
                    setattr(sys.modules[parent_name], parts[-1], mod)
            return getattr(mod, "__spec__", None)
        except Exception:
            return None
        finally:
            self._in_progress.discard(fullname)

if not any(isinstance(finder, UniversalAliasFinder) for finder in sys.meta_path):
    sys.meta_path.insert(0, UniversalAliasFinder())
