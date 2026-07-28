"""LLM routing policy — pure functions, no I/O, no network.

R0 deliverable: ordered candidate selection by RouteMode + TaskClass.
Does not call backends. Does not read env. Does not mint commitments.
"""

from __future__ import annotations

from .types import (
    LEVEL0_TAG_TOKENS,
    LEVEL0_TASK_CLASSES,
    BackendId,
    Level0RefuseError,
    RouteConfig,
    RouteMode,
    TaskClass,
)

# Preferred order when mode=task_split (design §3).
_TASK_SPLIT_ORDER: dict[TaskClass, tuple[BackendId, ...]] = {
    TaskClass.ASSISTANT: (BackendId.QUICKSILVER, BackendId.LOCAL),
    TaskClass.GUARDIAN_ADVISORY: (BackendId.NIM, BackendId.LOCAL, BackendId.QUICKSILVER),
    TaskClass.OFFLINE: (BackendId.LOCAL,),
    TaskClass.SOVEREIGN_STRICT: (BackendId.LOCAL,),
}

_CLOUD_BACKENDS = frozenset({BackendId.QUICKSILVER, BackendId.NIM})


def is_level0_task(task_class: TaskClass, tags: frozenset[str] | None = None) -> bool:
    """True if this request must be refused (no LLM on protocol truth surfaces)."""
    if task_class in LEVEL0_TASK_CLASSES:
        return True
    if tags:
        normalized = {t.strip().lower() for t in tags if t}
        if normalized & LEVEL0_TAG_TOKENS:
            return True
    return False


def refuse_if_level0(task_class: TaskClass, tags: frozenset[str] | None = None) -> None:
    """Raise Level0RefuseError when the task is Level-0 tagged."""
    if is_level0_task(task_class, tags):
        detail = ""
        if tags:
            hit = sorted(t for t in tags if t.strip().lower() in LEVEL0_TAG_TOKENS)
            if hit:
                detail = f"tags={hit}"
        raise Level0RefuseError(task_class, detail)


def _apply_nim_assistant_rail(
    candidates: list[BackendId],
    task_class: TaskClass,
    cfg: RouteConfig,
) -> list[BackendId]:
    """NIM stays Guardian-shaped unless explicitly allowed for assistant tasks."""
    if task_class == TaskClass.ASSISTANT and not cfg.allow_nim_for_assistant:
        return [b for b in candidates if b != BackendId.NIM]
    return candidates


def _apply_refuse_cloud(candidates: list[BackendId], cfg: RouteConfig) -> list[BackendId]:
    if not cfg.refuse_cloud:
        return candidates
    return [b for b in candidates if b not in _CLOUD_BACKENDS]


def _dedupe_preserve(order: list[BackendId]) -> list[BackendId]:
    seen: set[BackendId] = set()
    out: list[BackendId] = []
    for b in order:
        if b not in seen:
            seen.add(b)
            out.append(b)
    return out


def ordered_candidates(
    task_class: TaskClass,
    cfg: RouteConfig,
    *,
    tags: frozenset[str] | None = None,
    configured: frozenset[BackendId] | None = None,
    healthy: frozenset[BackendId] | None = None,
) -> tuple[BackendId, ...]:
    """Return ordered backend candidates for this task.

    Pure policy. Filters:
      1. Level-0 refuse (raises)
      2. Mode-specific order
      3. NIM-for-assistant rail
      4. refuse_cloud
      5. optional configured/healthy filters (caller-supplied; R0 tests inject these)

    Empty result means no candidate survived — caller raises NoBackendAvailableError.
    """
    refuse_if_level0(task_class, tags)

    if cfg.mode == RouteMode.PRIMARY_ONLY:
        candidates = [cfg.primary]
    elif cfg.mode == RouteMode.FAILOVER:
        candidates = list(cfg.ordered_slots())
    elif cfg.mode == RouteMode.TASK_SPLIT:
        base = _TASK_SPLIT_ORDER.get(task_class)
        if base is None:
            # Unknown / Level-0 already refused; fall back to config slots.
            candidates = list(cfg.ordered_slots())
        else:
            candidates = list(base)
    else:
        candidates = list(cfg.ordered_slots())

    candidates = _apply_nim_assistant_rail(candidates, task_class, cfg)
    candidates = _apply_refuse_cloud(candidates, cfg)
    candidates = _dedupe_preserve(candidates)

    if configured is not None:
        candidates = [b for b in candidates if b in configured]
    if healthy is not None:
        candidates = [b for b in candidates if b in healthy]

    return tuple(candidates)


def default_config() -> RouteConfig:
    """Design-default: failover QS → LOCAL; NIM not in assistant path."""
    return RouteConfig(
        mode=RouteMode.FAILOVER,
        primary=BackendId.QUICKSILVER,
        secondary=BackendId.LOCAL,
        tertiary=None,
        allow_nim_for_assistant=False,
        refuse_cloud=False,
        failover_on_timeout=True,
    )
