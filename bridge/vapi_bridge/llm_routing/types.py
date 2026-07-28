"""Core types for the LLM routing layer.

BackendId, TaskClass, RouteResult (the response envelope),
and supporting type aliases. No policy logic, no backend adapters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Literal


# ── Backend identifiers ───────────────────────────────

BackendId = Literal["quicksilver", "nim", "local", "fallback"]
"""Valid backend identifiers. Used in chain definitions,
health tracking, and provenance records."""


# ── Task classes ──────────────────────────────────────

TaskClass = Literal[
    "assistant",
    "guardian_advisory",
    "offline",
    "sovereign_strict",
]
"""Task class labels that drive chain selection in task_split mode.
Maps to a specific backend chain via RoutingPolicy.task_chain."""


# ── Route mode presets ────────────────────────────────

RouteMode = Literal[
    "auto",
    "failover",
    "primary_only",
    "cheap",
    "local",
    "cloud",
    "task_split",
    "pin:quicksilver",
    "pin:nim",
    "pin:local",
]
"""LLM_ROUTE_MODE env var values. Each maps to a RoutingPolicy preset."""


# ── Response envelope ─────────────────────────────────

@dataclass
class RouteResult:
    """The response envelope every caller receives.

    Honesty fields are on the envelope — not buried in provenance
    or logs. Every caller sees them without opt-in.
    """

    # ── Core ──────────────────────────────────────────
    content: Optional[str]
    """The text response from the backend, or None on failure."""
    success: bool
    """True if a backend returned a response, False otherwise."""
    error: Optional[str] = None
    """Error code or message. Machine-parseable codes:
    - no_llm_on_level0    — task_class is Level 0 protocol work
    - no_backends_available — no configured+healthy backends
    - no_local_backend    — LLM_REFUSE_CLOUD=true but LOCAL is down
    - all_backends_exhausted — every backend in the chain failed
    - timeout             — timeout with failover_on_timeout=false
    - 4xx / auth / 429    — authentication or rate limit error
    """

    # ── Honesty fields ────────────────────────────────
    backend: str = ""
    """Which backend served: 'quicksilver' | 'nim' | 'local' | 'fallback'."""
    model: str = ""
    """Model name as reported by the backend (e.g. 'deepseek-v4-flash')."""
    route_mode: str = ""
    """The active route mode at time of request (e.g. 'failover')."""
    primary_attempted: str = ""
    """The configured primary backend, regardless of who served."""
    attempts: List[str] = field(default_factory=list)
    """Backends tried in order before success. Empty = first backend succeeded."""
    fallback_used: bool = False
    """True if the serving backend was not the primary."""
    degraded: bool = False
    """True if the serving backend was in DEGRADED health state."""
    latency_ms: float = 0.0
    """Total wall-clock time for the full chain walk, in milliseconds."""
    live: bool = False
    """True if the response came from a real backend, not a stub or cache."""

    # ── Provenance ────────────────────────────────────
    provenance: Optional["ProvenanceRecord"] = None
    """Full provenance trace for audit. Optional for the caller,
    always present on the wire."""


@dataclass
class ProvenanceRecord:
    """Full provenance trace for a single routing decision.

    Stored in the session DB for audit trails. The caller doesn't
    need to parse this for normal operation — the honesty fields
    on RouteResult cover the common questions.
    """

    call_id: str
    """Unique identifier: 'llm_{timestamp}_{uuid[:8]}'."""
    timestamp: float
    """Unix timestamp when the request started."""
    backend: str
    """Which backend served."""
    model: str
    """Model name as reported by the backend."""
    route_mode: str
    """Route mode at time of request."""
    attempts: List[str]
    """Backends tried before success."""
    fallback_used: bool
    """True if not the primary."""
    latency_ms: float
    """Total wall time."""


# ── Health types ──────────────────────────────────────

HealthState = Literal["UNKNOWN", "HEALTHY", "DEGRADED", "UNHEALTHY", "COOLDOWN"]
"""Per-backend health state machine states."""


@dataclass
class BackendHealth:
    """Runtime health state for a single backend."""
    state: HealthState = "UNKNOWN"
    failures: int = 0
    last_failure: float = 0.0
    cooldown_until: float = 0.0
    last_success: float = 0.0