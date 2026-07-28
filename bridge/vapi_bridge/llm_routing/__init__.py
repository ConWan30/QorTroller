"""LLM routing infrastructure for QorTroller agentic reasoning.

Provides a three-tier backend router (QuickSilver, NIM, LOCAL) with
explicit policy, failover, and honesty fields on every response.
"""

from __future__ import annotations

from .router import LLMRouter
from .types import RouteResult, ProvenanceRecord
from .policy import RoutingPolicy, RoutingDecision, resolve_policy_from_env, LEVEL_0_TASKS
from .health import HealthCache

from .backends.quicksilver import QuickSilverBackend
from .backends.nim import NimBackend
from .backends.local import LocalBackend

__all__ = [
    "LLMRouter",
    "RouteResult",
    "ProvenanceRecord",
    "RoutingPolicy",
    "RoutingDecision",
    "resolve_policy_from_env",
    "LEVEL_0_TASKS",
    "QuickSilverBackend",
    "NimBackend",
    "LocalBackend",
    "HealthCache",
]