"""
ToolRegistry — VAPI-EXT Phase 204+

Range-validated tool registration across sub-protocols.

Design: tool number collisions between sub-protocols are a startup error,
not a runtime mystery. Without range ownership enforcement, VAPI_MOBILE
adding tool #150 and PRAGMA_JUDGE also adding tool #150 would produce
undefined behavior. With this registry, the second registration raises
immediately at startup.

Sub-protocols register their tool ranges in SubProtocolRegistry first,
then call register_tool_range() with their ToolDefinition list.

VAPI_CORE tools (1-149) are registered at BridgeAgent startup via the
[PERMITTED MODIFICATION] one-line addition to bridge_agent.py.
"""
from __future__ import annotations

import dataclasses
from typing import Callable, Optional

from .sub_protocol_registry import SubProtocolRegistry


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ToolNumberConflictError(Exception):
    """Raised when a tool number is already registered."""


class ToolRangeViolationError(Exception):
    """Raised when a tool number falls outside the sub-protocol's declared range."""


# ---------------------------------------------------------------------------
# ToolDefinition
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class ToolDefinition:
    """Descriptor for a VAPI tool.

    Fields:
        number           — globally unique tool number (1–149 for VAPI core)
        name             — snake_case name (e.g., "get_separation_ratio_status")
        description      — human-readable purpose
        handler          — the actual tool function (or placeholder callable)
        sub_protocol     — owning sub-protocol ("VAPI_CORE", "VAPI_MOBILE", etc.)
        phase_introduced — VAPI phase when this tool was added
        schema           — OpenAPI-compatible parameter schema dict
    """
    number: int
    name: str
    description: str
    handler: Callable
    sub_protocol: str
    phase_introduced: int
    schema: dict = dataclasses.field(default_factory=dict)


# ---------------------------------------------------------------------------
# ToolRegistry (singleton)
# ---------------------------------------------------------------------------

class ToolRegistry:
    """Singleton registry for VAPI tools across all sub-protocols.

    All tool numbers must be globally unique. Each tool number must fall
    within the range declared by its sub-protocol in SubProtocolRegistry.

    Usage:
        reg = ToolRegistry.instance()
        reg.register_tool(tool_def)
        reg.get_tool(149)
        reg.get_tools_for_protocol("VAPI_CORE")
    """

    _instance: Optional["ToolRegistry"] = None

    def __init__(self) -> None:
        self._tools: dict[int, ToolDefinition] = {}

    @classmethod
    def instance(cls) -> "ToolRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def _reset(cls) -> None:
        """Test-only helper — resets singleton."""
        cls._instance = None

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_tool(self, tool: ToolDefinition) -> None:
        """Register a single tool.

        Raises:
            ToolNumberConflictError: if the tool number is already registered.
            ToolRangeViolationError: if the number is outside the sub-protocol's
                                     declared tool_range in SubProtocolRegistry.
        """
        if not isinstance(tool, ToolDefinition):
            raise TypeError(f"Expected ToolDefinition, got {type(tool)}")

        if tool.number in self._tools:
            existing = self._tools[tool.number]
            raise ToolNumberConflictError(
                f"Tool number {tool.number} ('{tool.name}') is already registered "
                f"as '{existing.name}' for sub-protocol '{existing.sub_protocol}'."
            )

        self._validate_range(tool)
        self._tools[tool.number] = tool

    def register_tool_range(self, tools: list[ToolDefinition]) -> None:
        """Batch-register tools atomically.

        Validates ALL tools before applying any. If any validation fails,
        no tools are registered (all-or-nothing atomicity).
        """
        # Validate all first — collect errors before mutating state
        for tool in tools:
            if not isinstance(tool, ToolDefinition):
                raise TypeError(f"Expected ToolDefinition, got {type(tool)}")
            if tool.number in self._tools:
                existing = self._tools[tool.number]
                raise ToolNumberConflictError(
                    f"Tool number {tool.number} ('{tool.name}') is already registered "
                    f"as '{existing.name}' for sub-protocol '{existing.sub_protocol}'."
                )
            self._validate_range(tool)

        # All valid — apply
        for tool in tools:
            self._tools[tool.number] = tool

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_tool(self, number: int) -> ToolDefinition:
        """Returns the tool for the given number. Raises KeyError if not found."""
        if number not in self._tools:
            raise KeyError(f"Tool number {number} is not registered.")
        return self._tools[number]

    def get_all_tools(self) -> dict[int, ToolDefinition]:
        """Returns a copy of the full registry: {number: ToolDefinition}."""
        return dict(self._tools)

    def get_tools_for_protocol(self, protocol_name: str) -> list[ToolDefinition]:
        """Returns all tools registered under the given sub-protocol."""
        return [t for t in self._tools.values() if t.sub_protocol == protocol_name]

    def is_registered(self, number: int) -> bool:
        return number in self._tools

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_range(self, tool: ToolDefinition) -> None:
        """Validate that tool.number falls within the sub-protocol's declared range."""
        reg = SubProtocolRegistry.instance()
        proto_cfg = reg.get(tool.sub_protocol)
        if proto_cfg is None:
            raise ToolRangeViolationError(
                f"Sub-protocol '{tool.sub_protocol}' is not registered in SubProtocolRegistry. "
                f"Call SubProtocolRegistry.instance().register() before registering tools."
            )
        lo, hi = proto_cfg.tool_range
        if not (lo <= tool.number <= hi):
            raise ToolRangeViolationError(
                f"Tool number {tool.number} ('{tool.name}') is outside "
                f"'{tool.sub_protocol}' tool range [{lo}, {hi}]."
            )
