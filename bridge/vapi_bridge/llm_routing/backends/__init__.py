"""LLM backend adapters for the three-tier router.

Each adapter wraps an existing or new client behind the LLMBackend interface.
The router only calls LLMBackend methods — it never reaches into client internals.
"""

from __future__ import annotations

from .base import LLMBackend, HealthStatus, ProviderResponse
from .quicksilver import QuickSilverBackend
from .nim import NimBackend
from .local import LocalBackend

__all__ = [
    "LLMBackend",
    "HealthStatus",
    "ProviderResponse",
    "QuickSilverBackend",
    "NimBackend",
    "LocalBackend",
]