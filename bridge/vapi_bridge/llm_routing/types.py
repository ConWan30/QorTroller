"""LLM routing types — pure, no I/O.

Part of QORTROLLER LLM ROUTER R0 (policy + types only).
Does NOT mint a FROZEN-v1 family. Does NOT touch PoAC / PV-CI / classify.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class BackendId(str, Enum):
    """Named LLM backends. Claude is intentionally absent (operator rail)."""

    QUICKSILVER = "quicksilver"
    NIM = "nim"
    LOCAL = "local"


class TaskClass(str, Enum):
    """Routing task class. Level-0 protocol work is refused, not routed."""

    ASSISTANT = "assistant"
    GUARDIAN_ADVISORY = "guardian_advisory"
    OFFLINE = "offline"
    SOVEREIGN_STRICT = "sovereign_strict"
    LEVEL0 = "level0"


class RouteMode(str, Enum):
    PRIMARY_ONLY = "primary_only"
    FAILOVER = "failover"
    TASK_SPLIT = "task_split"


# Task classes the router must refuse (no LLM on protocol truth surfaces).
LEVEL0_TASK_CLASSES = frozenset({TaskClass.LEVEL0})

# Explicit tokens that call sites may tag as Level-0 work.
LEVEL0_TAG_TOKENS = frozenset(
    {
        "poac",
        "pv_ci",
        "pv-ci",
        "invariant_gate",
        "frozen_v1",
        "events_root",
        "kas_commitment",
        "posp_mint",
        "chain_write",
        "classify_live",
    }
)


@dataclass(frozen=True, slots=True)
class RouteConfig:
    """Immutable routing config snapshot. Built from env by a later step (R2+)."""

    mode: RouteMode = RouteMode.FAILOVER
    primary: BackendId = BackendId.QUICKSILVER
    secondary: Optional[BackendId] = BackendId.LOCAL
    tertiary: Optional[BackendId] = None
    allow_nim_for_assistant: bool = False
    refuse_cloud: bool = False
    failover_on_timeout: bool = True

    def ordered_slots(self) -> tuple[BackendId, ...]:
        slots: list[BackendId] = [self.primary]
        if self.secondary is not None:
            slots.append(self.secondary)
        if self.tertiary is not None:
            slots.append(self.tertiary)
        # Preserve order, drop duplicates.
        seen: set[BackendId] = set()
        out: list[BackendId] = []
        for b in slots:
            if b not in seen:
                seen.add(b)
                out.append(b)
        return tuple(out)


@dataclass(frozen=True, slots=True)
class RouteAttempt:
    backend: BackendId
    ok: bool
    error: Optional[str] = None
    latency_ms: Optional[float] = None


@dataclass(frozen=True, slots=True)
class RouteResult:
    """Honest provenance envelope returned with every routed response."""

    backend: BackendId
    model: str
    content: Any
    fallback_used: bool
    primary_attempted: BackendId
    attempts: tuple[RouteAttempt, ...] = field(default_factory=tuple)
    route_mode: RouteMode = RouteMode.FAILOVER
    task_class: TaskClass = TaskClass.ASSISTANT
    live: bool = True

    def to_provenance_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend.value,
            "model": self.model,
            "fallback_used": self.fallback_used,
            "primary_attempted": self.primary_attempted.value,
            "route_mode": self.route_mode.value,
            "task_class": self.task_class.value,
            "live": self.live,
            "attempts": [
                {
                    "backend": a.backend.value,
                    "ok": a.ok,
                    "error": a.error,
                    "latency_ms": a.latency_ms,
                }
                for a in self.attempts
            ],
        }


class Level0RefuseError(ValueError):
    """Raised when a Level-0 / protocol-truth task is presented to the router."""

    def __init__(self, task_class: TaskClass, detail: str = "") -> None:
        self.task_class = task_class
        msg = f"no_llm_on_level0: task_class={task_class.value}"
        if detail:
            msg = f"{msg} ({detail})"
        super().__init__(msg)


class NoBackendAvailableError(RuntimeError):
    """All configured candidates filtered out or failed."""

    def __init__(self, task_class: TaskClass, attempted: tuple[BackendId, ...]) -> None:
        self.task_class = task_class
        self.attempted = attempted
        super().__init__(
            f"no_backend_available: task_class={task_class.value} "
            f"attempted={[b.value for b in attempted]}"
        )
