"""Strict worker-v1 adapter for the pinned X-VC research model."""

from __future__ import annotations

from typing import Any

__all__ = [
    "DeterministicTestBackend",
    "OfficialXvcBackend",
    "WindowResult",
    "XvcConfiguration",
]


def __getattr__(name: str) -> Any:
    if name not in __all__:
        raise AttributeError(name)
    from . import backend

    return getattr(backend, name)
