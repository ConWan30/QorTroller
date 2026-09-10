"""Local consent view analog. Does not talk to chain unless explicitly unpaused.

v0 default: CHAIN_SUBMISSION_PAUSED. Returns the local consent record only.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def chain_paused() -> bool:
    raw = (os.getenv("CHAIN_SUBMISSION_PAUSED") or "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def read_local_consent(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    data["chain_view"] = None
    data["chain_paused"] = chain_paused()
    if chain_paused():
        data["note"] = (data.get("note") or "") + " | chain view skipped (CHAIN_SUBMISSION_PAUSED)"
    return data
