"""
SQLite Persistence — Records, devices, and submission tracking.

DECON-1 Stream 2 Phase 2.0.5 — `vapi_bridge.store` converted from a single
module to a package. The full prior body lives in `._core`. Public API is
re-exported here byte-identically so every existing `from vapi_bridge.store
import X` and `from vapi_bridge import store; store.X` keeps working.

Phase 2.1+ extracts one leaf domain at a time into sibling files
(`.zkba_vpm`, `.marketplace`, ...) as `*Mixin` classes; `Store` in `_core`
gains them via MRO. No call-site churn at any stage.
"""

from ._core import (
    CorpusRegressionError,
    PoACRecord,
    STATUS_BATCHED,
    STATUS_DEAD_LETTER,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_SUBMITTED,
    STATUS_VERIFIED,
    Store,
    log,
)

__all__ = [
    "CorpusRegressionError",
    "PoACRecord",
    "STATUS_BATCHED",
    "STATUS_DEAD_LETTER",
    "STATUS_FAILED",
    "STATUS_PENDING",
    "STATUS_SUBMITTED",
    "STATUS_VERIFIED",
    "Store",
    "log",
]
