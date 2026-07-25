"""RWM NOV-2 — multi-checkpoint inventory over L0 leaves (CANDIDATE).

v0 does NOT re-encode locator marks. L0 stop still paints checkpoint_index=0.
This inventory maps logical checkpoints → frame_index for steward addressing.

See docs/a2a/retina-witness-mark-ladder/nov-2-implementation-plan.md.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Iterable

from vapi_bridge.rwm_dispute_escrow import (
    EscrowError,
    load_l0_chain,
    verify_l0_archive,
)

SCHEMA = "qortroller-rwm-checkpoint-inventory-v0"
NOTE = (
    "L0 stop-path still paints locator checkpoint_index=0 on all frames; "
    "this inventory is steward addressing, not re-encoded marks."
)


class InventoryError(ValueError):
    """Fail-closed inventory error."""


def default_checkpoint_indices(n_frames: int) -> list[int]:
    """Default quintile indices {0, n//4, n//2, 3n//4, n-1}, unique, sorted."""
    if n_frames < 1:
        return []
    if n_frames == 1:
        return [0]
    raw = [0, n_frames // 4, n_frames // 2, (3 * n_frames) // 4, n_frames - 1]
    return sorted(set(int(i) for i in raw if 0 <= int(i) < n_frames))


def build_inventory(
    archive_dir: Path | str,
    *,
    checkpoint_indices: Iterable[int] | None = None,
    created_ts_ns: int | None = None,
) -> dict[str, Any]:
    """Build checkpoint inventory from a verified L0 archive."""
    d = Path(archive_dir)
    l0 = load_l0_chain(d)
    if not verify_l0_archive(d, l0):
        raise InventoryError("L0 chain does not re-verify — refuse inventory")

    frames = list(l0["frames"])
    n = len(frames)
    # frames may not be dense indices; map by frame_index field
    by_idx: dict[int, dict[str, Any]] = {int(f["frame_index"]): f for f in frames}
    sorted_idxs = sorted(by_idx.keys())
    n_frames = len(sorted_idxs)

    if checkpoint_indices is None:
        # use positions into sorted frame list, then map to frame_index
        pos = default_checkpoint_indices(n_frames)
        frame_idxs = [sorted_idxs[p] for p in pos]
    else:
        frame_idxs = sorted({int(i) for i in checkpoint_indices})
        for i in frame_idxs:
            if i not in by_idx:
                raise InventoryError(f"frame_index {i} not in L0 frames")

    chain_hex = list(l0["chain_hex"])
    # chain_hex is parallel to frames[] order in L0 build — index by order in frames list
    order = {int(f["frame_index"]): i for i, f in enumerate(frames)}

    checkpoints = []
    for cp_i, fi in enumerate(frame_idxs):
        row = by_idx[fi]
        ord_i = order[fi]
        chain_at = chain_hex[ord_i] if ord_i < len(chain_hex) else chain_hex[-1]
        checkpoints.append(
            {
                "checkpoint_index": cp_i,
                "frame_index": fi,
                "frame_hash_hex": row["frame_hash_hex"],
                "chain_hex_at_frame": chain_at,
            }
        )

    ts = int(created_ts_ns) if created_ts_ns is not None else time.time_ns()
    return {
        "schema": SCHEMA,
        "candidate": True,
        "session_id": l0["session_id"],
        "l0_chain_tip_hex": chain_hex[-1],
        "n_frames": n_frames,
        "n_checkpoints": len(checkpoints),
        "checkpoints": checkpoints,
        "note": NOTE,
        "created_ts_ns": ts,
    }


def verify_inventory(
    inv: dict[str, Any],
    archive_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Verify inventory structure and optional L0 archive hash match."""
    checks: list[dict[str, Any]] = []

    def _chk(name: str, ok: bool, note: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "note": note})

    try:
        if inv.get("schema") != SCHEMA:
            _chk("schema", False, f"expected {SCHEMA}")
            return {"ok": False, "checks": checks}

        cps = inv.get("checkpoints") or []
        _chk("n_checkpoints", int(inv.get("n_checkpoints", -1)) == len(cps))
        idxs = [int(c["checkpoint_index"]) for c in cps]
        _chk("cp_index_dense", idxs == list(range(len(cps))))
        frame_idxs = [int(c["frame_index"]) for c in cps]
        _chk("frame_indices_unique", len(frame_idxs) == len(set(frame_idxs)))

        if archive_dir is not None:
            d = Path(archive_dir)
            l0 = load_l0_chain(d)
            l0_ok = verify_l0_archive(d, l0)
            _chk("l0_chain_disk", l0_ok)
            if l0_ok:
                by_idx = {int(f["frame_index"]): f for f in l0["frames"]}
                _chk("session_id", inv.get("session_id") == l0["session_id"])
                _chk(
                    "l0_tip",
                    (inv.get("l0_chain_tip_hex") or "").lower() == l0["chain_hex"][-1].lower(),
                )
                for c in cps:
                    fi = int(c["frame_index"])
                    if fi not in by_idx:
                        _chk(f"frame_{fi}", False, "missing in L0")
                        continue
                    row = by_idx[fi]
                    _chk(
                        f"hash_{fi}",
                        c.get("frame_hash_hex") == row["frame_hash_hex"],
                        "inventory hash matches L0",
                    )
        else:
            _chk("archive_optional", True)

    except Exception as e:  # noqa: BLE001
        _chk("exception", False, repr(e)[:200])
        return {"ok": False, "checks": checks}

    return {"ok": all(c["ok"] for c in checks), "checks": checks}
