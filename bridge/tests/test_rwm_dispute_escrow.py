"""NOV-3 dispute escrow — pure tests T1–T10 (plan).

cv2-guarded PNG seeding matches test_rwm_daemon_wiring.py.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "bridge"))
sys.path.insert(0, str(_REPO / "scripts"))

np = pytest.importorskip("numpy")
pytest.importorskip("cv2")
import cv2  # noqa: E402

from vapi_bridge.rwm_dispute_escrow import (  # noqa: E402
    DOMAIN_LEAF,
    DOMAIN_ROOT,
    SCHEMA,
    EscrowError,
    build_escrow,
    compute_commitment_root,
    compute_leaf,
    verify_escrow,
    verify_l0_archive,
)

DEVICE = "ab" * 32


def _seed_l0(dst: Path, n: int = 8, size: int = 64) -> None:
    """Seed a minimal L0 archive via the real daemon helper when possible."""
    import os

    import retina_capture_daemon as d

    dst.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        img = np.full((size, size, 3), (i * 17) % 256, dtype=np.uint8)
        cv2.imwrite(str(dst / f"panel_{i:04d}.png"), img)
    os.environ["RWM_L0_DAEMON_ENABLED"] = "true"
    os.environ["RWM_DEVICE_ID_HEX"] = DEVICE
    d._issue_rwm_l0("escrow_test", 1_700_000_000, dst)
    assert (dst / "rwm_manifest_chain.json").is_file()


# --- T10 golden leaf ---

def test_t10_leaf_preimage_golden():
    session_id = "sess_golden"
    device = "11" * 32
    frame_index = 7
    frame_hash = "22" * 32
    got = compute_leaf(session_id, device, frame_index, frame_hash)
    expected = hashlib.sha256(
        DOMAIN_LEAF
        + session_id.encode("utf-8")
        + bytes.fromhex(device)
        + (7).to_bytes(4, "big")
        + bytes.fromhex(frame_hash)
    ).hexdigest()
    assert got == expected


def test_t10_commitment_root_golden():
    session_id = "sess_golden"
    tip = "33" * 32
    leaves = ["aa" * 32, "bb" * 32]
    inv = ["frame_0", "frame_1"]
    got = compute_commitment_root(session_id, tip, leaves, inv)
    expected = hashlib.sha256(
        DOMAIN_ROOT
        + session_id.encode("utf-8")
        + bytes.fromhex(tip)
        + (2).to_bytes(4, "big")
        + ",".join(sorted(leaves)).encode("utf-8")
        + ",".join(sorted(inv)).encode("utf-8")
    ).hexdigest()
    assert got == expected


# --- T1 happy ---

def test_t1_happy_build_verify(tmp_path):
    arch = tmp_path / "arch"
    _seed_l0(arch, n=6)
    pkg = build_escrow(arch, [0, 2, 5], "tournament dispute: sample frames")
    assert pkg["schema"] == SCHEMA
    assert pkg["candidate"] is True
    assert pkg["revealed_frame_indices"] == [0, 2, 5]
    assert len(pkg["leaf_hashes"]) == 6
    r = verify_escrow(pkg, arch)
    assert r["ok"] is True, r


# --- T2 bitflip ---

def test_t2_bitflip_revealed_marked_fails(tmp_path):
    arch = tmp_path / "arch"
    _seed_l0(arch, n=5)
    pkg = build_escrow(arch, [1, 3], "tournament dispute: bitflip case")
    victim = arch / pkg["revealed"][0]["marked_relpath"]
    raw = bytearray(victim.read_bytes())
    raw[10] ^= 0xFF
    victim.write_bytes(bytes(raw))
    r = verify_escrow(pkg, arch)
    assert r["ok"] is False
    assert any(not c["ok"] and "media" in c["name"] for c in r["checks"]) or any(
        not c["ok"] and c["name"] == "l0_chain_disk" for c in r["checks"]
    )


# --- T3 wrong session ---

def test_t3_wrong_session_id_breaks_root(tmp_path):
    arch = tmp_path / "arch"
    _seed_l0(arch, n=4)
    pkg = build_escrow(arch, [0, 1], "tournament dispute: session swap")
    pkg["session_id"] = "totally_different_session"
    r = verify_escrow(pkg)
    assert r["ok"] is False
    assert any(c["name"] == "commitment_root" and not c["ok"] for c in r["checks"])


# --- T4 unknown index ---

def test_t4_unknown_reveal_index_raises(tmp_path):
    arch = tmp_path / "arch"
    _seed_l0(arch, n=3)
    with pytest.raises(EscrowError, match="not present"):
        build_escrow(arch, [0, 99], "tournament dispute: bad index")


# --- T5 broken L0 ---

def test_t5_broken_l0_refuses_build(tmp_path):
    arch = tmp_path / "arch"
    _seed_l0(arch, n=4)
    # corrupt a marked file so L0 re-verify fails
    marked = sorted((arch / "marked").glob("panel_*.png"))[0]
    raw = bytearray(marked.read_bytes())
    raw[-5] ^= 0x01
    marked.write_bytes(bytes(raw))
    with pytest.raises(EscrowError, match="does not re-verify"):
        build_escrow(arch, [0, 1], "tournament dispute: broken l0")


# --- T6 short reason ---

def test_t6_short_reason_raises(tmp_path):
    arch = tmp_path / "arch"
    _seed_l0(arch, n=3)
    with pytest.raises(EscrowError, match="reason"):
        build_escrow(arch, [0], "short")


# --- T7 full reveal ---

def test_t7_full_reveal_verifies(tmp_path):
    arch = tmp_path / "arch"
    _seed_l0(arch, n=5)
    idxs = list(range(5))
    pkg = build_escrow(arch, idxs, "tournament dispute: full reveal package")
    assert pkg["revealed_frame_indices"] == idxs
    assert verify_escrow(pkg, arch)["ok"] is True


# --- T8 empty reveal ---

def test_t8_empty_reveal_raises(tmp_path):
    arch = tmp_path / "arch"
    _seed_l0(arch, n=3)
    with pytest.raises(EscrowError, match="non-empty"):
        build_escrow(arch, [], "tournament dispute: empty reveal list")


# --- T9 hash-only verify without archive ---

def test_t9_hash_only_verify_no_archive(tmp_path):
    arch = tmp_path / "arch"
    _seed_l0(arch, n=4)
    pkg = build_escrow(arch, [1, 2], "tournament dispute: hash-only verify")
    r = verify_escrow(pkg, archive_dir=None)
    assert r["ok"] is True
    assert any(c["name"] == "archive_optional" and c["ok"] for c in r["checks"])


def test_verify_l0_archive_helper(tmp_path):
    arch = tmp_path / "arch"
    _seed_l0(arch, n=3)
    assert verify_l0_archive(arch) is True
