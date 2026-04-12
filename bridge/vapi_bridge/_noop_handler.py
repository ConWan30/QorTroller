"""
_noop — placeholder handler for ToolDefinition manifest entries.

VAPI_CORE tools have real handlers wired inside BridgeAgent and
CalibrationIntelligenceAgent. The ToolDefinition objects in
vapi_core_tools.py exist only for range-ownership registration in
ToolRegistry — real dispatch is never routed through this callable.
"""
from __future__ import annotations


def _noop(**kwargs: object) -> None:
    """No-op placeholder for ToolDefinition.handler in the manifest."""
