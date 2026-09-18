"""
J.A.R.V.I.S. Python Core Intelligence Brain Package.
"""
import sys

__version__ = "1.0.0"

# Backward-compatibility alias for core_engine
if __name__ in sys.modules:
    sys.modules["core_engine"] = sys.modules[__name__]
