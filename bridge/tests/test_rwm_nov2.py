"""NOV-2 session bind + checkpoint inventory + SHARE postcard — T1–T10."""
from __future__ import annotations

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

from vapi_bridge.rwm_checkpoint_inventory import (  # noqa: E402
    build_inventory,
    default_checkpoint_indices,
    verify_inventory,
)
from vapi_bridge.rwm_dispute_escrow import build_escrow, verify_escrow  # noqa: E402
from vapi_bridge.rwm_session_bind import (  # noqa: E402
    BindError,
    attach_bind,
    build_bind,
    verify_bind,
)
from vapi_bridge.rwm_share_postcard import to_share, verify_share  # noqa: E402

DEVICE = "ab" * 32


def _seed_l0(dst: Path, n: int = 8, size: int = 64) -> None:
    import os

    import retina_capture_daemon as d

    dst.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        img = np.full((size, size, 3), (i * 17) % 256, dtype=np.uint8)
        cv2.imwrite(str(dst / f"panel_{i:04d}.png"), img)
    os.environ["RWM_L0_DAEMON_ENABLED"] = "true"
    os.environ["RWM_DEVICE_ID_HEX"] = DEVICE
    d._issue_rwm_l0("nov2_test", 1_700_000_100, dst)
    assert (dst / "rwm_manifest_chain.json").is_file()


# T1
def test_t1_bind_none_ok(tmp_path):
    arch = tmp_path / "a"
    _seed_l0(arch, n=6)
    b = build_bind(arch, bind_kind="none")
    assert b["bind_ok"] is True
    assert b["bind_kind"] == "none"
    r = verify_bind(b, archive_dir=arch)
    assert r["ok"] is True, r


# T2
def test_t2_poac_tip_match(tmp_path):
    arch = tmp_path / "a"
    _seed_l0(arch, n=6)
    tip = "aa" * 32
    b = build_bind(arch, bind_kind="poac_segment", poac_source=tip)
    assert b["bind_ok"] is True
    assert b["poac_tip_hex"] == tip
    r = verify_bind(b, archive_dir=arch)
    assert r["ok"] is True, r


# T3 — wrong kind missing tip → bind_ok false
def test_t3_poac_missing_tip_soft(tmp_path):
    arch = tmp_path / "a"
    _seed_l0(arch, n=6)
    b = build_bind(arch, bind_kind="poac_segment", poac_source=None)
    assert b["bind_ok"] is False
    r = verify_bind(b, archive_dir=arch)
    assert r["ok"] is True, r  # structural ok; field matches declared false


# T4
def test_t4_require_bind_raises(tmp_path):
    arch = tmp_path / "a"
    _seed_l0(arch, n=6)
    with pytest.raises(BindError):
        build_bind(arch, bind_kind="poac_segment", require_bind=True)


# T5
def test_t5_checkpoint_default_matches_l0(tmp_path):
    arch = tmp_path / "a"
    _seed_l0(arch, n=8)
    inv = build_inventory(arch)
    assert inv["n_checkpoints"] >= 2
    r = verify_inventory(inv, arch)
    assert r["ok"] is True, r
    # default for n=8: 0,2,4,6,7
    assert default_checkpoint_indices(8) == [0, 2, 4, 6, 7]


# T6
def test_t6_checkpoint_wrong_hash_fails(tmp_path):
    arch = tmp_path / "a"
    _seed_l0(arch, n=6)
    inv = build_inventory(arch)
    inv["checkpoints"][0]["frame_hash_hex"] = "ff" * 32
    r = verify_inventory(inv, arch)
    assert r["ok"] is False


# T7 / T8
def test_t7_t8_share_redaction(tmp_path):
    arch = tmp_path / "a"
    _seed_l0(arch, n=6)
    escrow = build_escrow(arch, [0, 2], "tournament dispute: sample frames")
    card = to_share(escrow)
    assert "device_id_hex" not in card
    assert "leaf_hashes" not in card
    assert "inventory" not in card
    assert card["commitment_root"] == escrow["commitment_root"]
    assert card["revealed_frame_indices"] == [0, 2]
    r = verify_share(card)
    assert r["ok"] is True, r


# T9
def test_t9_escrow_without_bind_still_verifies(tmp_path):
    arch = tmp_path / "a"
    _seed_l0(arch, n=6)
    pkg = build_escrow(arch, [0, 1], "tournament dispute: sample frames")
    assert "session_bind" not in pkg
    r = verify_escrow(pkg, arch)
    assert r["ok"] is True, r


# T10
def test_t10_escrow_with_bind_attached(tmp_path):
    arch = tmp_path / "a"
    _seed_l0(arch, n=6)
    pkg = build_escrow(arch, [0, 3], "tournament dispute: sample frames")
    bind = build_bind(arch, bind_kind="gic_tip", gic_source="bb" * 32)
    merged = attach_bind(pkg, bind)
    assert merged["session_bind"]["bind_ok"] is True
    r = verify_escrow(merged, arch)
    assert r["ok"] is True, r
    # bind_ok false still structural for escrow
    bind2 = build_bind(arch, bind_kind="dual")  # missing tips
    assert bind2["bind_ok"] is False
    merged2 = attach_bind(pkg, bind2)
    r2 = verify_escrow(merged2, arch)
    assert r2["ok"] is True, r2


def test_default_indices_edge():
    assert default_checkpoint_indices(0) == []
    assert default_checkpoint_indices(1) == [0]
    assert default_checkpoint_indices(2) == [0, 1]
