"""Routing policy: explicit rules for backend selection.

Policy is applied in order: PIN → CUT → FILTER → GATE → SORT → WALK.
No heuristics, no "best" scoring, no implicit fallback.
Every decision is recorded in RoutingDecision for audit.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional, List, Dict, FrozenSet


# ── Level 0 reject set ────────────────────────────────

LEVEL_0_TASKS: FrozenSet[str] = frozenset({
    "poac",
    "invariant_gate",
    "chain_write",
    "adjudication",
    "events_root",
    "kas",
    "classify",
})
"""Task classes that the router must refuse.

These are deterministic protocol paths — PoAC hash chains, PV-CI
invariant gates, on-chain transactions, live adjudication, events
root commitments, KAS authorship, and path classification. The
router returns error 'no_llm_on_level0' for any of these.
"""


# ── Task class chains (for task_split mode) ───────────

DEFAULT_TASK_CHAINS: Dict[str, List[str]] = {
    "assistant":         ["quicksilver", "local"],
    "guardian_advisory": ["nim", "local", "quicksilver"],
    "offline":           ["local"],
    "sovereign_strict":  ["local"],
}
"""Per-task backend chains for LLM_ROUTE_MODE=task_split.

assistant:         QuickSilver primary, LOCAL fallback. NIM excluded by default.
guardian_advisory: NIM primary (hardened), LOCAL secondary, QS tertiary.
offline:           LOCAL only. No cloud.
sovereign_strict:  LOCAL only. Refuses cloud even if available.
"""


# ── Policy dataclasses ────────────────────────────────

@dataclass
class RoutingPolicy:
    """Explicit rules governing which backend serves a request.

    Applied in order: PIN → CUT → FILTER → GATE → SORT → WALK.
    The resulting chain is what the router walks.
    """

    # ── Chain slots ──────────────────────────────────
    primary: str = "quicksilver"
    """First backend to try. Overridable via LLM_PRIMARY env var."""
    secondary: str = "local"
    """Fallback if primary is down. Overridable via LLM_SECONDARY env var."""
    tertiary: str = ""
    """Third slot. Empty = stop at secondary. Overridable via LLM_TERTIARY env var."""

    # ── Mode ─────────────────────────────────────────
    mode: str = "auto"
    """LLM_ROUTE_MODE value. Drives chain assembly logic."""

    # ── Overrides (checked first, highest precedence) ─
    pinned_backend: Optional[str] = None
    """Force every request to one backend. Debug / maintenance only."""
    excluded_backends: FrozenSet[str] = field(default_factory=frozenset)
    """Backends to skip entirely. Example: {'nim'} during maintenance."""
    refuse_cloud: bool = False
    """When True, ALL cloud backends are removed from the chain.
    Equivalent to LLM_REFUSE_CLOUD=true."""

    # ── Filters (checked second) ─────────────────────
    require_capability: Optional[str] = None
    """Skip backends that don't advertise this capability.
    Example: 'TOOLS' filters out local (CHAT-only)."""
    max_cost_usd_per_call: Optional[float] = None
    """Skip backends whose estimated cost exceeds this threshold.
    LOCAL is always $0; cloud backends report cost via health()."""

    # ── Reordering (checked last) ────────────────────
    prefer_cheapest: bool = False
    """When True, reorder chain so cheaper backends are tried first.
    LOCAL → NIM → QuickSilver instead of default."""

    # ── Task split ───────────────────────────────────
    task_chain: Dict[str, List[str]] = field(default_factory=lambda: dict(DEFAULT_TASK_CHAINS))
    """Per-task backend chains. Only used when mode='task_split'."""

    # ── Tuning ───────────────────────────────────────
    timeout_seconds: int = 30
    """Per-request timeout for the entire chain walk."""
    max_failures: int = 3
    """Consecutive failures before a backend is marked unhealthy."""
    cooldown_seconds: int = 300
    """How long a backend stays in cooldown before retry."""
    health_cache_seconds: int = 30
    """How long to cache health() results."""
    failover_on_timeout: bool = True
    """When True, timeout → try next backend. When False, timeout → error."""
    allow_nim_for_assistant: bool = False
    """When True, NIM is available for assistant tasks.
    When False (default), assistant tasks never route through NIM."""


@dataclass
class RoutingDecision:
    """Why a particular backend was chosen (or not).

    Recorded on every RouteResult for audit.
    """

    policy: RoutingPolicy
    """The policy that was applied."""
    chain_before_filter: List[str]
    """The chain before any policy filtering."""
    chain_after_filter: List[str]
    """The chain after policy was applied."""
    skipped_reasons: Dict[str, str]
    """Backend ID → why it was skipped. Empty if all succeeded."""
    selected_backend: Optional[str]
    """Which backend served, or None if all failed."""
    fallback_used: bool
    """True if the serving backend was not the primary."""


# ── Env var resolution ────────────────────────────────

_MODE_MAP = {
    "auto": {},
    "failover": {},
    "primary_only": {"max_failures": 0},  # no failover
    "cheap": {"prefer_cheapest": True},
    "local": {"excluded_backends": frozenset({"quicksilver", "nim"})},
    "cloud": {"excluded_backends": frozenset({"local"})},
    "task_split": {},
}


def resolve_policy_from_env() -> RoutingPolicy:
    """Build a RoutingPolicy from environment variables.

    Reads LLM_ROUTE_MODE, LLM_PRIMARY, LLM_SECONDARY, LLM_TERTIARY,
    LLM_REFUSE_CLOUD, LLM_ALLOW_NIM_FOR_ASSISTANT, LLM_FAILOVER_ON_TIMEOUT,
    LLM_HEALTH_CACHE_S, and LLM_ROUTER_* env vars.
    """
    mode = os.environ.get("LLM_ROUTE_MODE", "auto").strip().lower()

    # ── Handle pin:* modes ───────────────────────────
    if mode.startswith("pin:"):
        backend = mode.removeprefix("pin:")
        return RoutingPolicy(
            mode=mode,
            pinned_backend=backend if backend in ("quicksilver", "nim", "local") else None,
        )

    # ── Base policy from mode ────────────────────────
    mode_overrides = _MODE_MAP.get(mode, {})

    # Build kwargs from env, filtered to avoid duplicate keys
    def _env_bool(key, default):
        return os.environ.get(key, default).lower() == "true"

    def _env_int(key, default):
        return int(os.environ.get(key, default))

    env_kwargs = {
        "primary": os.environ.get("LLM_PRIMARY", "quicksilver"),
        "secondary": os.environ.get("LLM_SECONDARY", "local"),
        "tertiary": os.environ.get("LLM_TERTIARY", ""),
        "refuse_cloud": _env_bool("LLM_REFUSE_CLOUD", "false"),
        "allow_nim_for_assistant": _env_bool("LLM_ALLOW_NIM_FOR_ASSISTANT", "false"),
        "failover_on_timeout": _env_bool("LLM_FAILOVER_ON_TIMEOUT", "true"),
        "health_cache_seconds": _env_int("LLM_HEALTH_CACHE_S", "30"),
        "timeout_seconds": _env_int("LLM_ROUTER_TIMEOUT_SECONDS", "30"),
        "max_failures": _env_int("LLM_ROUTER_MAX_FAILURES", "3"),
        "cooldown_seconds": _env_int("LLM_ROUTER_COOLDOWN_SECONDS", "300"),
    }
    # Remove keys that mode_overrides provides — those take precedence
    for k in mode_overrides:
        env_kwargs.pop(k, None)

    policy = RoutingPolicy(
        mode=mode,
        **mode_overrides,
        **env_kwargs,
    )

    # ── LLM_ROUTER_CHAIN raw override ────────────────
    chain_raw = os.environ.get("LLM_ROUTER_CHAIN", "")
    if chain_raw and mode in ("auto", "failover"):
        parts = [p.strip() for p in chain_raw.split(",") if p.strip()]
        if len(parts) >= 1:
            policy.primary = parts[0]
        if len(parts) >= 2:
            policy.secondary = parts[1]
        if len(parts) >= 3:
            policy.tertiary = parts[2]

    return policy