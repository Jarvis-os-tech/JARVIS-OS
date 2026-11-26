"""Universal Import Aliasing Bootstrapper for JARVIS OS Modular Restructure.

Enables seamless transition between legacy package names and normalized pillars:
- core -> kernel
- voice_layer -> voice
- audio -> voice
- jarvis_control -> control
- jarvis_os_bridge -> control.bridge
- jarvis_memory -> memory
- orchestration -> harness
- departments -> department_agents
- widget_engine -> widgets
"""
import sys
import importlib
import importlib.abc
import importlib.machinery
from pathlib import Path

ROOT = Path(__file__).resolve().parent

ALIASES = {
    "core": "kernel",
    "voice_layer": "voice",
    "audio": "voice",
    "jarvis_control": "control",
    "jarvis_os_bridge": "control.bridge",
    "jarvis_memory": "memory",
    "orchestration": "harness",
    "departments": "department_agents",
    "widget_engine": "widgets",
    "proactive": "kernel.proactive",
}

class DummyLoader(importlib.abc.Loader):
    def __init__(self, target_mod):
        self.target_mod = target_mod

    def create_module(self, spec):
        return self.target_mod

    def exec_module(self, module):
        pass

class UniversalAliasFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in sys.modules:
            mod = sys.modules[fullname]
            loader = DummyLoader(mod)
            spec = importlib.machinery.ModuleSpec(fullname, loader, origin=getattr(mod, "__file__", None))
            if hasattr(mod, "__path__"):
                spec.submodule_search_locations = list(mod.__path__)
            return spec

        parts = fullname.split(".")
        root_pkg = parts[0]

        # If root_pkg exists directly as a real package on disk, do not intercept
        root_dir = ROOT / root_pkg
        if (root_dir / "__init__.py").exists():
            return None

        # Check if root_pkg is an alias
        if root_pkg not in ALIASES:
            return None

        # Ensure parent packages are loaded first in hierarchical order
        for i in range(1, len(parts)):
            parent_alias = ".".join(parts[:i])
            if parent_alias not in sys.modules:
                importlib.import_module(parent_alias)

        target_root = ALIASES[root_pkg]
        target_fullname = ".".join([target_root] + parts[1:])

        if target_fullname in sys.modules:
            mod = sys.modules[target_fullname]
        else:
            mod = importlib.import_module(target_fullname)

        sys.modules[fullname] = mod
        if len(parts) > 1:
            parent_name = ".".join(parts[:-1])
            if parent_name in sys.modules:
                setattr(sys.modules[parent_name], parts[-1], mod)

        loader = DummyLoader(mod)
        spec = importlib.machinery.ModuleSpec(fullname, loader, origin=getattr(mod, "__file__", None))
        if hasattr(mod, "__path__"):
            spec.submodule_search_locations = list(mod.__path__)
        return spec

if not any(isinstance(finder, UniversalAliasFinder) for finder in sys.meta_path):
    sys.meta_path.insert(0, UniversalAliasFinder())
