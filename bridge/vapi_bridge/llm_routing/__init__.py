"""llm_routing — pure policy + types (R0).

No network. No FROZEN/PV-CI surface. Claude is not a backend target.
"""

from .policy import default_config, is_level0_task, ordered_candidates, refuse_if_level0
from .types import (
    LEVEL0_TAG_TOKENS,
    LEVEL0_TASK_CLASSES,
    BackendId,
    Level0RefuseError,
    NoBackendAvailableError,
    RouteAttempt,
    RouteConfig,
    RouteMode,
    RouteResult,
    TaskClass,
)

__all__ = [
    "BackendId",
    "LEVEL0_TAG_TOKENS",
    "LEVEL0_TASK_CLASSES",
    "Level0RefuseError",
    "NoBackendAvailableError",
    "RouteAttempt",
    "RouteConfig",
    "RouteMode",
    "RouteResult",
    "TaskClass",
    "default_config",
    "is_level0_task",
    "ordered_candidates",
    "refuse_if_level0",
]
