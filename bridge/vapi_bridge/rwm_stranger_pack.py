"""RWM NOV-1 / NOV-1.1 — portable stranger-verify dispute pack (CANDIDATE).

Modes:
  sd1_inline_media_v0  — full leaf_hashes list (NOV-1)
  merkle_inline_media_v0 — Merkle root + log-N proofs; no full leaf list (NOV-1.1)

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
from typing import Any, Literal

from vapi_bridge.rwm_dispute_escrow import (
    EscrowError,
    compute_commitment_root,
    compute_leaf,
    load_l0_chain,
    verify_l0_archive,
)

SCHEMA = "qortroller-rwm-stranger-pack-v0"
MODE_SD1 = "sd1_inline_media_v0"
MODE_MERKLE = "merkle_inline_media_v0"
MODES = frozenset({MODE_SD1, MODE_MERKLE})

# NOV-1.1 Merkle domain tags (CANDIDATE — distinct from WMP SD-2)
_DOMAIN_M_LEAF = b"VAPI-RWM-MERKLE-LEAF-v0"
_DOMAIN_M_NODE = b"VAPI-RWM-MERKLE-NODE-v0"
_DOMAIN_M_COMMIT = b"VAPI-RWM-STRANGER-MERKLE-v0"

PackMode = Literal["sd1_inline_media_v0", "merkle_inline_media_v0"]


class StrangerPackError(ValueError):
    """Fail-closed build/verify error."""


def _merkle_leaf_tag(leaf_hash_hex: str) -> str:
    return hashlib.sha256(_DOMAIN_M_LEAF + bytes.fromhex(leaf_hash_hex)).hexdigest()


def _merkle_node(left_hex: str, right_hex: str) -> str:
    return hashlib.sha256(
        _DOMAIN_M_NODE + bytes.fromhex(left_hex) + bytes.fromhex(right_hex)
    ).hexdigest()


def merkle_layers(sorted_tagged_leaves: list[str]) -> list[list[str]]:
    """Bottom-up layers; odd count duplicates last (same discipline as WMP SD-2)."""
    if not sorted_tagged_leaves:
        raise StrangerPackError("empty merkle leaves")
    layers = [list(sorted_tagged_leaves)]
    cur = list(sorted_tagged_leaves)
    while len(cur) > 1:
        nxt: list[str] = []
        for i in range(0, len(cur), 2):
            a = cur[i]
            b = cur[i + 1] if i + 1 < len(cur) else cur[i]
            nxt.append(_merkle_node(a, b))
        layers.append(nxt)
        cur = nxt
    return layers


def merkle_inclusion_proof(layers: list[list[str]], index: int) -> list[dict[str, Any]]:
    proof: list[dict[str, Any]] = []
    idx = index
    for layer in layers[:-1]:
        sib = idx ^ 1
        sib_hash = layer[sib] if sib < len(layer) else layer[idx]
        proof.append({"hash": sib_hash, "sibling_left": (idx % 2 == 1)})
        idx //= 2
    return proof


def verify_merkle_inclusion(tagged_leaf: str, proof: list[dict[str, Any]], root: str) -> bool:
    h = tagged_leaf
    for step in proof:
        if step.get("sibling_left"):
            h = _merkle_node(step["hash"], h)
        else:
            h = _merkle_node(h, step["hash"])
    return h == root


def merkle_commitment_root(
    session_id: str,
    l0_chain_tip_hex: str,
    set_size: int,
    inventory: list[str],
    merkle_root_hex: str,
) -> str:
    tip = bytes.fromhex(l0_chain_tip_hex)
    if len(tip) != 32:
        raise StrangerPackError("l0_chain_tip_hex must be 32 bytes")
    mroot = bytes.fromhex(merkle_root_hex)
    if len(mroot) != 32:
        raise StrangerPackError("merkle_root must be 32 bytes")
    return hashlib.sha256(
        _DOMAIN_M_COMMIT
        + session_id.encode("utf-8")
        + tip
        + int(set_size).to_bytes(4, "big")
        + mroot
        + ",".join(sorted(inventory)).encode("utf-8")
    ).hexdigest()


def _load_l0_leaves(archive_dir: Path) -> tuple[dict[str, Any], dict[int, dict], list[str], list[str], str]:
    l0 = load_l0_chain(archive_dir)
    if not verify_l0_archive(archive_dir, l0):
        raise StrangerPackError("L0 chain does not re-verify — refuse to invent leaves")
    session_id = l0["session_id"]
    device_id_hex = l0["device_id_hex"]
    tip_hex = l0["chain_hex"][-1]
    by_idx = {int(f["frame_index"]): f for f in l0["frames"]}
    inventory: list[str] = []
    leaf_hashes: list[str] = []
    for idx in sorted(by_idx.keys()):
        row = by_idx[idx]
        inventory.append(f"frame_{idx}")
        leaf_hashes.append(
            compute_leaf(session_id, device_id_hex, idx, row["frame_hash_hex"])
        )
    return l0, by_idx, inventory, leaf_hashes, tip_hex


def _read_revealed_media(
    d: Path,
    by_idx: dict[int, dict],
    session_id: str,
    device_id_hex: str,
    reveal_set: list[int],
) -> list[dict[str, Any]]:
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
    return revealed


def build_stranger_pack(
    archive_dir: Path | str,
    reveal_indices: list[int],
    reason: str,
    *,
    case_id: str = "",
    mode: str = MODE_SD1,
    created_ts_ns: int | None = None,
) -> dict[str, Any]:
    """Build a portable pack from a verified L0 archive. Media inlined for reveals only."""
    if not isinstance(reason, str) or len(reason.strip()) < 10:
        raise StrangerPackError("reason must be a string of at least 10 characters")
    if not reveal_indices:
        raise StrangerPackError("reveal_indices must be non-empty")
    mode = (mode or MODE_SD1).strip()
    if mode not in MODES:
        raise StrangerPackError(f"mode must be one of {sorted(MODES)}")

    d = Path(archive_dir)
    l0, by_idx, inventory, leaf_hashes, tip_hex = _load_l0_leaves(d)
    session_id = l0["session_id"]
    device_id_hex = l0["device_id_hex"]

    reveal_set = sorted({int(i) for i in reveal_indices})
    for i in reveal_set:
        if i not in by_idx:
            raise StrangerPackError(f"reveal frame_index {i} not present in L0 frames")

    revealed = _read_revealed_media(d, by_idx, session_id, device_id_hex, reveal_set)
    ts = int(created_ts_ns) if created_ts_ns is not None else time.time_ns()
    inv_sorted = sorted(inventory)

    if mode == MODE_SD1:
        root = compute_commitment_root(session_id, tip_hex, leaf_hashes, inventory)
        return {
            "schema": SCHEMA,
            "candidate": True,
            "mode": MODE_SD1,
            "session_id": session_id,
            "device_id_hex": device_id_hex,
            "l0_chain_tip_hex": tip_hex,
            "set_size": len(leaf_hashes),
            "inventory": inv_sorted,
            "leaf_hashes": sorted(leaf_hashes),
            "commitment_root": root,
            "revealed": revealed,
            "revealed_frame_indices": reveal_set,
            "reason": reason.strip(),
            "case_id": case_id or "",
            "created_ts_ns": ts,
        }

    # MODE_MERKLE (NOV-1.1)
    # Tree over sorted *tagged* leaves; map leaf_hash -> position in sorted tagged list
    leaf_to_tagged = {lh: _merkle_leaf_tag(lh) for lh in leaf_hashes}
    sorted_tagged = sorted(leaf_to_tagged.values())
    layers = merkle_layers(sorted_tagged)
    merkle_root = layers[-1][0]
    commit = merkle_commitment_root(session_id, tip_hex, len(leaf_hashes), inv_sorted, merkle_root)

    for r in revealed:
        lh = r["leaf_hash"]
        tagged = leaf_to_tagged[lh]
        pos = sorted_tagged.index(tagged)
        r["merkle_tagged_leaf"] = tagged
        r["inclusion_proof"] = merkle_inclusion_proof(layers, pos)

    return {
        "schema": SCHEMA,
        "candidate": True,
        "mode": MODE_MERKLE,
        "session_id": session_id,
        "device_id_hex": device_id_hex,
        "l0_chain_tip_hex": tip_hex,
        "set_size": len(leaf_hashes),
        "inventory": inv_sorted,
        # intentional: no full leaf_hashes list
        "merkle_root": merkle_root,
        "commitment_root": commit,
        "revealed": revealed,
        "revealed_frame_indices": reveal_set,
        "reason": reason.strip(),
        "case_id": case_id or "",
        "created_ts_ns": ts,
    }


def verify_stranger_pack(pack: dict[str, Any]) -> dict[str, Any]:
    """Archive-free verify for sd1 or merkle modes."""
    checks: list[dict[str, Any]] = []

    def _chk(name: str, ok: bool, note: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "note": note})

    try:
        if pack.get("schema") != SCHEMA:
            _chk("schema", False, f"expected {SCHEMA}")
            return {"ok": False, "checks": checks}

        mode = pack.get("mode")
        _chk("mode", mode in MODES, str(mode))
        session_id = pack["session_id"]
        device_id_hex = pack["device_id_hex"]
        tip = pack["l0_chain_tip_hex"]
        inventory = list(pack.get("inventory") or [])
        revealed = list(pack.get("revealed") or [])
        set_size = int(pack.get("set_size", -1))

        reason = pack.get("reason") or ""
        _chk("reason_len", isinstance(reason, str) and len(reason) >= 10)
        _chk("reveal_nonempty", bool(revealed))
        _chk("inventory_size", len(inventory) == set_size or set_size < 0, f"inv={len(inventory)} set={set_size}")

        if mode == MODE_SD1:
            leaf_hashes = list(pack.get("leaf_hashes") or [])
            _chk(
                "set_size",
                set_size == len(leaf_hashes) == len(inventory),
            )
            root = compute_commitment_root(session_id, tip, leaf_hashes, inventory)
            _chk(
                "commitment_root",
                root == pack.get("commitment_root"),
                "recomputed root matches package",
            )
            leaf_set = set(leaf_hashes)
            for r in revealed:
                idx = int(r["frame_index"])
                ok_media, dig = _check_media(r, idx, _chk)
                if not ok_media:
                    continue
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

        elif mode == MODE_MERKLE:
            mroot = pack.get("merkle_root") or ""
            _chk("merkle_root_len", len(mroot) == 64)
            try:
                expect_commit = merkle_commitment_root(
                    session_id, tip, set_size, inventory, mroot
                )
            except StrangerPackError as e:
                _chk("commitment_build", False, str(e)[:80])
                expect_commit = ""
            _chk(
                "commitment_root",
                expect_commit == pack.get("commitment_root"),
                "header commitment recomputes over tip+size+inv+merkle_root",
            )
            _chk("no_full_leaf_list", "leaf_hashes" not in pack or not pack.get("leaf_hashes"),
                 "merkle mode must not ship full leaf_hashes")

            for r in revealed:
                idx = int(r["frame_index"])
                ok_media, dig = _check_media(r, idx, _chk)
                if not ok_media:
                    continue
                try:
                    leaf = compute_leaf(session_id, device_id_hex, idx, dig)
                except EscrowError as e:
                    _chk(f"leaf_compute_{idx}", False, str(e)[:80])
                    continue
                _chk(f"leaf_{idx}", leaf == r.get("leaf_hash"), "leaf matches media")
                tagged = _merkle_leaf_tag(leaf)
                if r.get("merkle_tagged_leaf"):
                    _chk(f"tagged_{idx}", r["merkle_tagged_leaf"] == tagged)
                proof = r.get("inclusion_proof") or []
                _chk(
                    f"merkle_proof_{idx}",
                    verify_merkle_inclusion(tagged, proof, mroot),
                    "inclusion reaches merkle_root",
                )

        _chk("archive_free", True, "verify_stranger_pack needs no archive_dir")

    except Exception as e:  # noqa: BLE001
        _chk("exception", False, repr(e)[:200])
        return {"ok": False, "checks": checks}

    return {"ok": all(c["ok"] for c in checks), "checks": checks}


def _check_media(
    r: dict[str, Any],
    idx: int,
    _chk: Any,
) -> tuple[bool, str]:
    b64 = r.get("marked_png_b64") or ""
    try:
        media = base64.b64decode(b64, validate=True)
    except Exception:  # noqa: BLE001
        _chk(f"media_b64_{idx}", False, "base64 decode failed")
        return False, ""
    dig = hashlib.sha256(media).hexdigest()
    ok = dig == r.get("frame_hash_hex")
    _chk(f"media_hash_{idx}", ok, "sha256(media) == frame_hash_hex")
    return ok, dig
