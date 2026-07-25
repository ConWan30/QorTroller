"""RWM NOV-2 — SHARE-redacted dispute postcard (CANDIDATE).

LOCAL full escrow stays steward-only. SHARE strips device_id and full leaf sets.
Structural verify only — indicative, not full forensic proof.

See docs/a2a/retina-witness-mark-ladder/nov-2-implementation-plan.md.
"""
from __future__ import annotations

import time
from typing import Any

from vapi_bridge.rwm_dispute_escrow import SCHEMA as ESCROW_SCHEMA

SCHEMA = "qortroller-rwm-share-postcard-v0"
REDACTION = [
    "device_id_hex",
    "leaf_hashes",
    "inventory",
    "revealed.media",
]


class ShareError(ValueError):
    """Fail-closed share build error."""


def to_share(
    local_escrow: dict[str, Any],
    *,
    created_ts_ns: int | None = None,
) -> dict[str, Any]:
    """Build SHARE postcard from LOCAL escrow package."""
    if local_escrow.get("schema") != ESCROW_SCHEMA:
        raise ShareError(f"expected escrow schema {ESCROW_SCHEMA}")
    if not local_escrow.get("commitment_root"):
        raise ShareError("escrow missing commitment_root")

    reason = str(local_escrow.get("reason") or "")
    if len(reason) > 200:
        reason = reason[:200]

    bind = local_escrow.get("session_bind")
    bind_ok = None
    bind_kind = None
    if isinstance(bind, dict):
        bind_ok = bool(bind.get("bind_ok"))
        bind_kind = bind.get("bind_kind")

    ts = int(created_ts_ns) if created_ts_ns is not None else time.time_ns()
    return {
        "schema": SCHEMA,
        "candidate": True,
        "session_id": local_escrow["session_id"],
        "commitment_root": local_escrow["commitment_root"],
        "l0_frame_count": int(local_escrow.get("l0_frame_count") or local_escrow.get("set_size") or 0),
        "revealed_frame_indices": list(local_escrow.get("revealed_frame_indices") or []),
        "bind_ok": bind_ok,
        "bind_kind": bind_kind,
        "case_id": local_escrow.get("case_id") or "",
        "reason": reason,
        "redaction": list(REDACTION),
        "created_ts_ns": ts,
    }


def verify_share(postcard: dict[str, Any]) -> dict[str, Any]:
    """Structural verify only (indicative surface)."""
    checks: list[dict[str, Any]] = []

    def _chk(name: str, ok: bool, note: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "note": note})

    try:
        _chk("schema", postcard.get("schema") == SCHEMA)
        _chk("session_id", bool(postcard.get("session_id")))
        root = postcard.get("commitment_root") or ""
        _chk("commitment_root", isinstance(root, str) and len(root) == 64)
        _chk("no_device_id", "device_id_hex" not in postcard)
        _chk("no_leaf_hashes", "leaf_hashes" not in postcard)
        _chk("no_inventory", "inventory" not in postcard)
        idxs = postcard.get("revealed_frame_indices")
        _chk("revealed_indices", isinstance(idxs, list) and len(idxs) >= 1)
        red = postcard.get("redaction") or []
        _chk("redaction_lists_device", "device_id_hex" in red)
    except Exception as e:  # noqa: BLE001
        _chk("exception", False, repr(e)[:200])
        return {"ok": False, "checks": checks}

    return {"ok": all(c["ok"] for c in checks), "checks": checks}
