"""RWM NOV-3 — ledger-native dispute escrow (CANDIDATE, not FROZEN-v1).

Offline selective-disclosure over L0 RWM session leaves. Pure module: no bridge
process, no SQLite, no network, no stop-path hook.

Honest ceiling: membership + binding of L0 per-frame hashes into a committed set;
reveal a subset for dispute. Not ZK value-hiding, not re-encode proof, not Path B.

See docs/a2a/retina-witness-mark-ladder/nov-3-implementation-plan.md.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

SCHEMA = "qortroller-rwm-dispute-escrow-v0"
DOMAIN_ROOT = b"VAPI-RWM-DISPUTE-ESCROW-v0"
DOMAIN_LEAF = b"VAPI-RWM-DISPUTE-LEAF-v0"

L0_CHAIN_NAME = "rwm_manifest_chain.json"


class EscrowError(ValueError):
    """Fail-closed build/verify error (never invent leaves)."""


def load_l0_chain(archive_dir: Path | str) -> dict[str, Any]:
    """Load rwm_manifest_chain.json from an L0 archive directory."""
    d = Path(archive_dir)
    p = d / L0_CHAIN_NAME
    if not p.is_file():
        raise EscrowError(f"missing {L0_CHAIN_NAME} under {d}")
    rec = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(rec, dict) or not rec.get("frames"):
        raise EscrowError("L0 chain has no frames")
    if not rec.get("chain_hex"):
        raise EscrowError("L0 chain has no chain_hex")
    return rec


def verify_l0_archive(archive_dir: Path | str, l0: dict[str, Any] | None = None) -> bool:
    """Third-party path: re-hash marked/ bytes and verify_session_chain."""
    from vapi_bridge.retina_capture_manifest import verify_session_chain

    d = Path(archive_dir)
    rec = l0 if l0 is not None else load_l0_chain(d)
    frames: list[tuple[bytes, int]] = []
    for f in rec["frames"]:
        path = d / f["file"]
        if not path.is_file():
            return False
        dig = hashlib.sha256(path.read_bytes()).digest()
        if dig.hex() != f["frame_hash_hex"]:
            return False
        frames.append((dig, int(f["ts_ns"])))
    chain = [bytes.fromhex(h) for h in rec["chain_hex"]]
    return bool(
        verify_session_chain(
            rec["session_id"],
            rec["device_id_hex"],
            int(rec["genesis_ts_ns"]),
            frames,
            chain,
        )
    )


def compute_leaf(
    session_id: str,
    device_id_hex: str,
    frame_index: int,
    frame_hash_hex: str,
) -> str:
    """Leaf preimage hash (hex) per plan §4.1."""
    device_id = bytes.fromhex(device_id_hex)
    if len(device_id) != 32:
        raise EscrowError(f"device_id_hex must decode to 32 bytes, got {len(device_id)}")
    frame_hash = bytes.fromhex(frame_hash_hex)
    if len(frame_hash) != 32:
        raise EscrowError(f"frame_hash_hex must decode to 32 bytes, got {len(frame_hash)}")
    if not (0 <= int(frame_index) <= 0xFFFFFFFF):
        raise EscrowError(f"frame_index out of range: {frame_index}")
    return hashlib.sha256(
        DOMAIN_LEAF
        + session_id.encode("utf-8")
        + device_id
        + int(frame_index).to_bytes(4, "big")
        + frame_hash
    ).hexdigest()


def compute_commitment_root(
    session_id: str,
    l0_chain_tip_hex: str,
    leaf_hashes: list[str],
    inventory: list[str],
) -> str:
    """Set commitment root per plan §4.2 (SD-1 shape, L0 tip as parent binding)."""
    tip = bytes.fromhex(l0_chain_tip_hex)
    if len(tip) != 32:
        raise EscrowError(f"l0_chain_tip_hex must decode to 32 bytes, got {len(tip)}")
    set_size = len(leaf_hashes)
    return hashlib.sha256(
        DOMAIN_ROOT
        + session_id.encode("utf-8")
        + tip
        + set_size.to_bytes(4, "big")
        + ",".join(sorted(leaf_hashes)).encode("utf-8")
        + ",".join(sorted(inventory)).encode("utf-8")
    ).hexdigest()


def _rows_by_index(l0: dict[str, Any]) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for f in l0["frames"]:
        idx = int(f["frame_index"])
        out[idx] = f
    return out


def build_escrow(
    archive_dir: Path | str,
    reveal_indices: list[int],
    reason: str,
    *,
    case_id: str = "",
    external_ref: str = "",
    include_media: bool = False,
    created_ts_ns: int | None = None,
) -> dict[str, Any]:
    """Build a CANDIDATE dispute escrow package. Fail-closed on bad L0 / indices / reason."""
    if not isinstance(reason, str) or len(reason.strip()) < 10:
        raise EscrowError("reason must be a string of at least 10 characters")
    if not reveal_indices:
        raise EscrowError("reveal_indices must be non-empty (zero-reveal escrow is noise)")

    d = Path(archive_dir)
    l0 = load_l0_chain(d)
    if not verify_l0_archive(d, l0):
        raise EscrowError("L0 chain does not re-verify from archive disk bytes — refuse to invent leaves")

    session_id = l0["session_id"]
    device_id_hex = l0["device_id_hex"]
    tip_hex = l0["chain_hex"][-1]
    by_idx = _rows_by_index(l0)

    reveal_set = sorted({int(i) for i in reveal_indices})
    for i in reveal_set:
        if i not in by_idx:
            raise EscrowError(f"reveal frame_index {i} not present in L0 frames")

    inventory: list[str] = []
    leaf_hashes: list[str] = []
    # Stable order by frame_index for construction; root sorts again.
    for idx in sorted(by_idx.keys()):
        row = by_idx[idx]
        inv = f"frame_{idx}"
        leaf = compute_leaf(session_id, device_id_hex, idx, row["frame_hash_hex"])
        inventory.append(inv)
        leaf_hashes.append(leaf)

    root = compute_commitment_root(session_id, tip_hex, leaf_hashes, inventory)

    revealed = []
    for idx in reveal_set:
        row = by_idx[idx]
        leaf = compute_leaf(session_id, device_id_hex, idx, row["frame_hash_hex"])
        revealed.append(
            {
                "frame_index": idx,
                "frame_hash_hex": row["frame_hash_hex"],
                "source": row.get("source", ""),
                "marked_relpath": row["file"],
                "leaf_hash": leaf,
            }
        )

    ts = int(created_ts_ns) if created_ts_ns is not None else time.time_ns()
    return {
        "schema": SCHEMA,
        "candidate": True,
        "domain_tag_commitment": DOMAIN_ROOT.decode("ascii"),
        "session_id": session_id,
        "device_id_hex": device_id_hex,
        "l0_genesis_ts_ns": int(l0["genesis_ts_ns"]),
        "l0_chain_tip_hex": tip_hex,
        "l0_frame_count": len(by_idx),
        "set_size": len(leaf_hashes),
        "inventory": sorted(inventory),
        "leaf_hashes": sorted(leaf_hashes),
        "commitment_root": root,
        "revealed_frame_indices": reveal_set,
        "revealed": revealed,
        "reason": reason.strip(),
        "case_id": case_id or "",
        "external_ref": external_ref or "",
        "include_media": bool(include_media),
        "created_ts_ns": ts,
    }


def verify_escrow(
    escrow: dict[str, Any],
    archive_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Recompute leaves + root; optionally re-hash revealed marked files + L0 chain."""
    checks: list[dict[str, Any]] = []

    def _chk(name: str, ok: bool, note: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "note": note})

    try:
        if escrow.get("schema") != SCHEMA:
            _chk("schema", False, f"expected {SCHEMA}")
            return {"ok": False, "checks": checks}

        session_id = escrow["session_id"]
        device_id_hex = escrow["device_id_hex"]
        tip = escrow["l0_chain_tip_hex"]
        leaf_hashes = list(escrow["leaf_hashes"])
        inventory = list(escrow["inventory"])
        _chk(
            "set_size",
            int(escrow.get("set_size", -1)) == len(leaf_hashes) == len(inventory),
            f"set_size={escrow.get('set_size')} leaves={len(leaf_hashes)} inv={len(inventory)}",
        )
        root = compute_commitment_root(session_id, tip, leaf_hashes, inventory)
        _chk("commitment_root", root == escrow.get("commitment_root"), "recomputed root matches package")

        reason = escrow.get("reason") or ""
        _chk("reason_len", isinstance(reason, str) and len(reason) >= 10)

        revealed = escrow.get("revealed") or []
        indices = escrow.get("revealed_frame_indices") or []
        _chk("reveal_nonempty", bool(revealed) and bool(indices))
        _chk(
            "reveal_index_set",
            sorted({int(i) for i in indices}) == sorted({int(r["frame_index"]) for r in revealed}),
        )

        leaf_set = set(leaf_hashes)
        for r in revealed:
            leaf = compute_leaf(
                session_id,
                device_id_hex,
                int(r["frame_index"]),
                r["frame_hash_hex"],
            )
            _chk(
                f"revealed_leaf_{r['frame_index']}",
                leaf == r.get("leaf_hash") and leaf in leaf_set,
            )

        if archive_dir is not None:
            d = Path(archive_dir)
            l0_ok = verify_l0_archive(d)
            _chk("l0_chain_disk", l0_ok, "third-party L0 re-verify from archive")
            if l0_ok:
                for r in revealed:
                    path = d / r["marked_relpath"]
                    if not path.is_file():
                        _chk(f"media_{r['frame_index']}", False, "marked file missing")
                        continue
                    dig = hashlib.sha256(path.read_bytes()).hexdigest()
                    _chk(
                        f"media_hash_{r['frame_index']}",
                        dig == r["frame_hash_hex"],
                        "disk marked hash matches reveal row",
                    )
        else:
            _chk("archive_optional", True, "no archive_dir — hash-only package verify")

        # NOV-2 additive: optional session_bind (absent = backward-compat)
        sb = escrow.get("session_bind")
        if sb is not None:
            from vapi_bridge.rwm_session_bind import verify_bind

            br = verify_bind(sb, archive_dir=archive_dir)
            _chk("session_bind_verify", br["ok"], "nested bind package re-checks")
            # If bind_ok declared false, package is still structurally valid but
            # stewards must not treat cross-primitive as proven — check still ok.
            if br.get("bind_ok") is False and sb.get("bind_kind") not in (None, "none", ""):
                _chk(
                    "session_bind_not_ok",
                    True,
                    "bind_ok=false — treat as L0/NOV-3 only (informational pass)",
                )

    except Exception as e:  # noqa: BLE001 — report as failed check
        _chk("exception", False, repr(e)[:200])
        return {"ok": False, "checks": checks}

    ok = all(c["ok"] for c in checks)
    return {"ok": ok, "checks": checks}
