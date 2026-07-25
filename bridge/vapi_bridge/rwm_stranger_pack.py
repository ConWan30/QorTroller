"""RWM NOV-1 — portable stranger-verify dispute pack (CANDIDATE, not FROZEN-v1).

Offline pack: SD-1 set commitment + pack-local marked media for revealed frames.
Third party can verify_stranger_pack(pack) with NO archive_dir.

Honest ceiling: membership of revealed L0 marked-frame hashes under a committed set.
Not re-encode proof, not Path B, not FROZEN.

See docs/a2a/retina-witness-mark-ladder/nov-1-implementation-plan.md.
"""
from __future__ import annotations

import base64
import hashlib
import time
from pathlib import Path
from typing import Any

from vapi_bridge.rwm_dispute_escrow import (
    EscrowError,
    compute_commitment_root,
    compute_leaf,
    load_l0_chain,
    verify_l0_archive,
)

SCHEMA = "qortroller-rwm-stranger-pack-v0"
MODE = "sd1_inline_media_v0"


class StrangerPackError(ValueError):
    """Fail-closed build/verify error."""


def build_stranger_pack(
    archive_dir: Path | str,
    reveal_indices: list[int],
    reason: str,
    *,
    case_id: str = "",
    created_ts_ns: int | None = None,
) -> dict[str, Any]:
    """Build a portable pack from a verified L0 archive. Media inlined for reveals only."""
    if not isinstance(reason, str) or len(reason.strip()) < 10:
        raise StrangerPackError("reason must be a string of at least 10 characters")
    if not reveal_indices:
        raise StrangerPackError("reveal_indices must be non-empty")

    d = Path(archive_dir)
    l0 = load_l0_chain(d)
    if not verify_l0_archive(d, l0):
        raise StrangerPackError("L0 chain does not re-verify — refuse to invent leaves")

    session_id = l0["session_id"]
    device_id_hex = l0["device_id_hex"]
    tip_hex = l0["chain_hex"][-1]
    by_idx = {int(f["frame_index"]): f for f in l0["frames"]}

    reveal_set = sorted({int(i) for i in reveal_indices})
    for i in reveal_set:
        if i not in by_idx:
            raise StrangerPackError(f"reveal frame_index {i} not present in L0 frames")

    inventory: list[str] = []
    leaf_hashes: list[str] = []
    for idx in sorted(by_idx.keys()):
        row = by_idx[idx]
        inventory.append(f"frame_{idx}")
        leaf_hashes.append(
            compute_leaf(session_id, device_id_hex, idx, row["frame_hash_hex"])
        )

    root = compute_commitment_root(session_id, tip_hex, leaf_hashes, inventory)

    revealed: list[dict[str, Any]] = []
    for idx in reveal_set:
        row = by_idx[idx]
        media_path = d / row["file"]
        if not media_path.is_file():
            raise StrangerPackError(f"marked media missing for frame {idx}: {media_path}")
        media = media_path.read_bytes()
        media_hash = hashlib.sha256(media).hexdigest()
        if media_hash != row["frame_hash_hex"]:
            raise StrangerPackError(
                f"frame {idx}: disk media hash != L0 frame_hash_hex (archive drift)"
            )
        leaf = compute_leaf(session_id, device_id_hex, idx, media_hash)
        revealed.append(
            {
                "frame_index": idx,
                "frame_hash_hex": media_hash,
                "leaf_hash": leaf,
                "marked_png_b64": base64.b64encode(media).decode("ascii"),
            }
        )

    ts = int(created_ts_ns) if created_ts_ns is not None else time.time_ns()
    return {
        "schema": SCHEMA,
        "candidate": True,
        "mode": MODE,
        "session_id": session_id,
        "device_id_hex": device_id_hex,
        "l0_chain_tip_hex": tip_hex,
        "set_size": len(leaf_hashes),
        "inventory": sorted(inventory),
        "leaf_hashes": sorted(leaf_hashes),
        "commitment_root": root,
        "revealed": revealed,
        "revealed_frame_indices": reveal_set,
        "reason": reason.strip(),
        "case_id": case_id or "",
        "created_ts_ns": ts,
    }


def verify_stranger_pack(pack: dict[str, Any]) -> dict[str, Any]:
    """Archive-free verify: media hashes + leaf membership + SD-1 root recompute."""
    checks: list[dict[str, Any]] = []

    def _chk(name: str, ok: bool, note: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "note": note})

    try:
        if pack.get("schema") != SCHEMA:
            _chk("schema", False, f"expected {SCHEMA}")
            return {"ok": False, "checks": checks}

        _chk("mode", pack.get("mode") == MODE, str(pack.get("mode")))
        session_id = pack["session_id"]
        device_id_hex = pack["device_id_hex"]
        tip = pack["l0_chain_tip_hex"]
        leaf_hashes = list(pack["leaf_hashes"])
        inventory = list(pack["inventory"])
        revealed = list(pack.get("revealed") or [])

        _chk(
            "set_size",
            int(pack.get("set_size", -1)) == len(leaf_hashes) == len(inventory),
        )
        root = compute_commitment_root(session_id, tip, leaf_hashes, inventory)
        _chk(
            "commitment_root",
            root == pack.get("commitment_root"),
            "recomputed root matches package",
        )

        reason = pack.get("reason") or ""
        _chk("reason_len", isinstance(reason, str) and len(reason) >= 10)
        _chk("reveal_nonempty", bool(revealed))

        leaf_set = set(leaf_hashes)
        for r in revealed:
            idx = int(r["frame_index"])
            b64 = r.get("marked_png_b64") or ""
            try:
                media = base64.b64decode(b64, validate=True)
            except Exception:  # noqa: BLE001
                _chk(f"media_b64_{idx}", False, "base64 decode failed")
                continue
            dig = hashlib.sha256(media).hexdigest()
            _chk(
                f"media_hash_{idx}",
                dig == r.get("frame_hash_hex"),
                "sha256(media) == frame_hash_hex",
            )
            try:
                leaf = compute_leaf(session_id, device_id_hex, idx, dig)
            except EscrowError as e:
                _chk(f"leaf_compute_{idx}", False, str(e)[:80])
                continue
            _chk(
                f"leaf_{idx}",
                leaf == r.get("leaf_hash") and leaf in leaf_set,
                "leaf matches and is in set",
            )

        # no network / no archive — pure package checks only
        _chk("archive_free", True, "verify_stranger_pack needs no archive_dir")

    except Exception as e:  # noqa: BLE001
        _chk("exception", False, repr(e)[:200])
        return {"ok": False, "checks": checks}

    return {"ok": all(c["ok"] for c in checks), "checks": checks}
