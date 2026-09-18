"""
omarchy_skills.python
Unified Python API for Omarchy Desktop & System Control.
"""

from . import hyprland
from . import theme
from . import toggles
from . import system
from . import capture
from . import launcher

__all__ = [
    "hyprland",
    "theme",
    "toggles",
    "system",
    "capture",
    "launcher",
]
