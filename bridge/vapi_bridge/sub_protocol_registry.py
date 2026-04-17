"""
Sub-Protocol Registry — VAPI-EXT Phase
Phase 204+ baseline. Enables isolated sub-protocols (VAPI_MOBILE, PRAGMA_JUDGE)
to register with VAPI infrastructure without modifying core files.

The registry is a singleton. VAPI_CORE is pre-registered at import time.
Sub-protocols call SubProtocolRegistry.instance().register(config) as their
first action to declare presence, ranges, and namespaces.

Design principle: sub-protocols share infrastructure without modifying core.
Five integration points: SubProtocolRegistry, FederationBus namespace,
MigrationRunner SQL files, CoherenceRuleLoader _rules.py files, ToolRegistry.
"""
from __future__ import annotations

import dataclasses
from typing import Optional


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class SubProtocolConflictError(Exception):
    """Raised when a sub-protocol registration conflicts with an existing one."""


# ---------------------------------------------------------------------------
# SubProtocolConfig
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class SubProtocolConfig:
    """Immutable descriptor for a sub-protocol attached to VAPI infrastructure.

    Fields:
        name                    — globally unique identifier (e.g., "VAPI_CORE", "VAPI_MOBILE")
        event_namespace         — prefix for all bus events published by this sub-protocol
                                  (e.g., "mobile.", "pragma."); "" = no prefix (VAPI_CORE only)
        agent_range             — (first_agent_number, last_agent_number) inclusive
        tool_range              — (first_tool_number, last_tool_number) inclusive
        table_prefix            — SQLite table name prefix (e.g., "mobile_", "pragma_");
                                  "" = no prefix (VAPI_CORE only)
        contract_source_type    — value stored in AdjudicationRegistry sourceType
                                  (e.g., "VAPI", "VAPI_MOBILE", "PRAGMA_JUDGE")
        version                 — phase string at registration time (e.g., "phase204")
        dry_run                 — whether this sub-protocol is in dry_run mode at registration
        active                  — False after deactivate(); history is preserved
        permitted_vapi_interfaces — explicit list of VAPI interface calls this sub-protocol
                                  may make. Serves as the isolation contract declaration:
                                  any Claude Code session building this sub-protocol must
                                  not call anything not on this list. This field is
                                  documentation-enforced (not runtime-enforced) — it provides
                                  the architectural boundary that prevents isolation decay.
                                  Format: "ClassName.method_name" strings.
                                  Example: ["VAPIProtocolLens.isFullyEligible",
                                            "AdjudicationRegistry.anchorAdjudication"]
                                  Empty list = no VAPI calls permitted (maximally isolated).
                                  VAPI_CORE = None (unrestricted, owns the core).
    """
    name: str
    event_namespace: str
    agent_range: tuple           # (first, last) inclusive
    tool_range: tuple            # (first, last) inclusive
    table_prefix: str
    contract_source_type: str
    version: str
    dry_run: bool = True
    active: bool = True
    permitted_vapi_interfaces: Optional[list] = None  # None = unrestricted (VAPI_CORE only)


# ---------------------------------------------------------------------------
# VAPI_CORE baseline — pre-registered at module import
# ---------------------------------------------------------------------------

_VAPI_CORE = SubProtocolConfig(
    name="VAPI_CORE",
    event_namespace="",       # no prefix — all existing VAPI events pass through unchanged
    agent_range=(1, 36),      # Agents #1–#36 (Phase 193 FleetSignalCoherenceAgent)
    tool_range=(1, 149),      # Tools #1–#149 (Phase 195 get_protocol_metabolism_index)
    table_prefix="",          # no prefix — backward compatible with all existing tables
    contract_source_type="VAPI",
    version="phase204",
    dry_run=True,
    active=True,
)


# ---------------------------------------------------------------------------
# SubProtocolRegistry (singleton)
# ---------------------------------------------------------------------------

class SubProtocolRegistry:
    """Singleton registry for VAPI sub-protocols.

    VAPI_CORE is pre-registered at the first call to instance(). All
    subsequent sub-protocols register via instance().register(config).

    Collision detection covers: name uniqueness, agent_range overlap,
    tool_range overlap, event_namespace uniqueness (non-empty only),
    table_prefix uniqueness (non-empty only), contract_source_type uniqueness.

    Usage:
        reg = SubProtocolRegistry.instance()
        reg.register(my_config)
        reg.is_registered("MY_PROTOCOL")
        reg.get_registered()  # → dict[name, SubProtocolConfig]
    """

    _instance: Optional["SubProtocolRegistry"] = None

    def __init__(self) -> None:
        # name → SubProtocolConfig
        self._protocols: dict[str, SubProtocolConfig] = {}

    @classmethod
    def instance(cls) -> "SubProtocolRegistry":
        """Return the singleton, creating and seeding it on first call."""
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._protocols["VAPI_CORE"] = _VAPI_CORE
        return cls._instance

    @classmethod
    def _reset(cls) -> None:
        """Test-only helper — resets singleton so each test starts clean."""
        cls._instance = None

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, config: SubProtocolConfig) -> None:
        """Register a sub-protocol.

        Raises SubProtocolConflictError on any collision.
        """
        if not isinstance(config, SubProtocolConfig):
            raise TypeError(f"Expected SubProtocolConfig, got {type(config)}")

        if config.name in self._protocols:
            raise SubProtocolConflictError(
                f"Sub-protocol '{config.name}' is already registered."
            )

        # Validate ranges
        self._validate_range(config.agent_range, "agent_range", config.name)
        self._validate_range(config.tool_range, "tool_range", config.name)

        for existing in self._protocols.values():
            if not existing.active:
                continue
            # Agent range overlap
            if self._ranges_overlap(config.agent_range, existing.agent_range):
                raise SubProtocolConflictError(
                    f"Agent range {config.agent_range} for '{config.name}' overlaps "
                    f"with '{existing.name}' range {existing.agent_range}."
                )
            # Tool range overlap
            if self._ranges_overlap(config.tool_range, existing.tool_range):
                raise SubProtocolConflictError(
                    f"Tool range {config.tool_range} for '{config.name}' overlaps "
                    f"with '{existing.name}' range {existing.tool_range}."
                )
            # Event namespace collision (non-empty only; "" = VAPI_CORE global, no collision)
            if config.event_namespace and existing.event_namespace:
                if config.event_namespace == existing.event_namespace:
                    raise SubProtocolConflictError(
                        f"Event namespace '{config.event_namespace}' for '{config.name}' "
                        f"is already owned by '{existing.name}'."
                    )
            # Table prefix collision (non-empty only)
            if config.table_prefix and existing.table_prefix:
                if config.table_prefix == existing.table_prefix:
                    raise SubProtocolConflictError(
                        f"Table prefix '{config.table_prefix}' for '{config.name}' "
                        f"is already owned by '{existing.name}'."
                    )
            # contract_source_type must be globally unique
            if config.contract_source_type == existing.contract_source_type:
                raise SubProtocolConflictError(
                    f"contract_source_type '{config.contract_source_type}' for "
                    f"'{config.name}' is already used by '{existing.name}'."
                )

        self._protocols[config.name] = config

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_registered(self) -> dict[str, SubProtocolConfig]:
        """Returns a shallow copy of all registrations (including inactive)."""
        return dict(self._protocols)

    def get_active(self) -> dict[str, SubProtocolConfig]:
        """Returns only active (non-deactivated) sub-protocols."""
        return {k: v for k, v in self._protocols.items() if v.active}

    def is_registered(self, name: str) -> bool:
        """True if the name is in the registry (active or inactive)."""
        return name in self._protocols

    def is_active(self, name: str) -> bool:
        """True only if registered AND active."""
        return name in self._protocols and self._protocols[name].active

    def get(self, name: str) -> Optional[SubProtocolConfig]:
        """Returns config for name, or None if not registered."""
        return self._protocols.get(name)

    def tool_range_owner(self, tool_number: int) -> Optional[str]:
        """Returns the name of the sub-protocol that owns the given tool number, or None."""
        for name, cfg in self._protocols.items():
            if cfg.active and cfg.tool_range[0] <= tool_number <= cfg.tool_range[1]:
                return name
        return None

    def agent_range_owner(self, agent_number: int) -> Optional[str]:
        """Returns the name of the sub-protocol that owns the given agent number, or None."""
        for name, cfg in self._protocols.items():
            if cfg.active and cfg.agent_range[0] <= agent_number <= cfg.agent_range[1]:
                return name
        return None

    # ------------------------------------------------------------------
    # Deactivation
    # ------------------------------------------------------------------

    def deactivate(self, name: str) -> None:
        """Mark a sub-protocol as inactive.

        The record is preserved for audit; ranges are freed for re-use.
        VAPI_CORE cannot be deactivated.
        """
        if name not in self._protocols:
            raise KeyError(f"Sub-protocol '{name}' is not registered.")
        if name == "VAPI_CORE":
            raise SubProtocolConflictError("VAPI_CORE cannot be deactivated.")
        existing = self._protocols[name]
        # Replace with an inactive copy
        self._protocols[name] = dataclasses.replace(existing, active=False)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ranges_overlap(a: tuple, b: tuple) -> bool:
        """True if inclusive ranges [a[0], a[1]] and [b[0], b[1]] overlap."""
        return a[0] <= b[1] and b[0] <= a[1]

    @staticmethod
    def _validate_range(r: tuple, field: str, name: str) -> None:
        if not (isinstance(r, tuple) and len(r) == 2):
            raise ValueError(f"{field} for '{name}' must be a 2-tuple, got {r!r}")
        if r[0] > r[1]:
            raise ValueError(
                f"{field} for '{name}' has first > last: {r}. "
                "Use (first_number, last_number) inclusive."
            )
