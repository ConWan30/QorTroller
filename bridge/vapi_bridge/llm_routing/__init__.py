"""LLM routing infrastructure for QorTroller agentic reasoning.

Provides router orchestration with QS (QuickSilver) + LOCAL (NIM) failover
and comprehensive provenance tracking for all LLM calls.
"""
from __future__ import annotations

from .router_orchestrator import (
    LLMRouter,
    RouterConfig,
    LLMProvider,
    RouterResult,
    ProvenanceRecord
)
from .local_client import LocalLLMClient
from .qs_client import QuickSilverClient

__all__ = [
    "LLMRouter",
    "RouterConfig", 
    "LLMProvider",
    "RouterResult",
    "ProvenanceRecord",
    "LocalLLMClient",
    "QuickSilverClient"
]