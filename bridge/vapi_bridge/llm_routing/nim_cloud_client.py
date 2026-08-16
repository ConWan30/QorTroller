"""Backward-compat shim: LocalLLMClient moved to local_client.py.

Kept as a re-export because the class originally lived here; the canonical
implementation (with a module-level, patchable HardenedNIMClient binding)
is vapi_bridge/llm_routing/local_client.py. Nothing in-tree imports this
module anymore — it exists only to not break any external/dynamic import.
"""
from .local_client import HardenedNIMClient, LocalLLMClient, NIMConfig  # noqa: F401

__all__ = ["LocalLLMClient", "HardenedNIMClient", "NIMConfig"]
