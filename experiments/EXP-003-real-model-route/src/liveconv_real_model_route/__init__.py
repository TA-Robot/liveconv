"""EXP-003 metadata-redacted real-model Gateway route harness."""

from .config import RunConfiguration
from .registry import ProfileRegistry
from .suite import run_route_suite

__all__ = ["ProfileRegistry", "RunConfiguration", "run_route_suite"]
__version__ = "0.1.0"
