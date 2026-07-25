"""RWM session continuum loader — seed L0 archive + compose with stack/ioID."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "bridge"))
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "scripts"))

np = pytest.importorskip("numpy")
pytest.importorskip("cv2")
import cv2  # noqa: E402

from vapi_bridge.rwm_session_bind import build_bind  # noqa: E402
from vapi_bridge.rwm_session_continuum import (  # noqa: E402
    ContinuumError,
    build_continuum_from_archive,
    load_rwm_surface,
    verify_continuum,
)
from l9_presence.session_continuum import (  # noqa: E402
    OPTICAL_IDENTITY,
    OPTICAL_SESSION,
    SYNCHRONIZED_CONTINUUM,
    EDGE_DEVICE_ID_LIVE,
)

DEVICE = "ab" * 32


def _seed_l0(dst: Path, n: int = 6, size: int = 64) -> None:
    import os

    import retina_capture_daemon as d

    dst.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        img = np.full((size, size, 3), (i * 19) % 256, dtype=np.uint8)
        cv2.imwrite(str(dst / f"panel_{i:04d}.png"), img)
    os.environ["RWM_L0_DAEMON_ENABLED"] = "true"
    os.environ["RWM_DEVICE_ID_HEX"] = DEVICE
    d._issue_rwm_l0("cont_test", 1_700_000_200, dst)
    assert (dst / "rwm_manifest_chain.json").is_file()


def test_load_rwm_surface_verified(tmp_path):
    arch = tmp_path / "a"
    _seed_l0(arch)
    surf = load_rwm_surface(arch)
    assert surf["l0_verified"] is True
    assert surf["device_id_hex"] == DEVICE
    assert len(surf["session_id"]) == 64
    assert surf["n_frames"] == 6


def test_build_optical_session(tmp_path):
    arch = tmp_path / "a"
    _seed_l0(arch)
    cont = build_continuum_from_archive(
        arch, label="cont_test", stamp=1_700_000_200
    )
    assert cont["verdict"] == OPTICAL_SESSION
    assert cont["optical_rwm"] is True
    assert cont["session_join"] is True
    assert cont["device_join"] is True
    assert cont["candidate"] is True
    vr = verify_continuum(cont)
    assert vr["ok"] is True, vr


def test_build_optical_identity_with_ioid(tmp_path):
    arch = tmp_path / "a"
    _seed_l0(arch)
    # re-seed would use DEVICE; pass matching ioID
    ioid = {
        "token_id": 498,
        "did": "did:io:0x0cf36db5",
        "tba": "0xFCee2377",
        "registered_device_id": DEVICE,
    }
    cont = build_continuum_from_archive(
        arch, label="cont_test", stamp=1_700_000_200, ioid=ioid
    )
    assert cont["verdict"] == OPTICAL_IDENTITY
    assert cont["identity_bound"] is True


def test_build_with_nov2_stack(tmp_path):
    arch = tmp_path / "a"
    _seed_l0(arch)
    bind = build_bind(arch, bind_kind="none")
    cont = build_continuum_from_archive(
        arch,
        label="cont_test",
        stamp=1_700_000_200,
        nov2_bind=bind,
    )
    assert cont["verdict"] == OPTICAL_SESSION
    assert cont["stack_cited"] is True
    assert cont["stack"]["nov2_bind"]["ok"] is True


def test_device_mismatch_with_live_edge_ioid(tmp_path):
    """Seed uses test DEVICE; ioID of real Edge must fail closed."""
    arch = tmp_path / "a"
    _seed_l0(arch)
    ioid = {
        "token_id": 498,
        "did": "did:io:0x0cf36db5",
        "registered_device_id": EDGE_DEVICE_ID_LIVE,
    }
    cont = build_continuum_from_archive(
        arch, label="cont_test", stamp=1_700_000_200, ioid=ioid
    )
    assert cont["verdict"] == "UNVERIFIABLE"
    assert cont["identity_bound"] is False


def test_synchronized_when_all_surfaces(tmp_path):
    arch = tmp_path / "a"
    _seed_l0(arch)
    surf = load_rwm_surface(arch)
    ioid = {
        "token_id": 1,
        "did": "did:io:test",
        "registered_device_id": DEVICE,
    }
    poep = {
        "presence_session_candidate_ok": True,
        "device_id": DEVICE,
        "session_id": surf["session_id"],
    }
    cont = build_continuum_from_archive(
        arch,
        label="cont_test",
        stamp=1_700_000_200,
        ioid=ioid,
        poep_live=poep,
    )
    assert cont["verdict"] == SYNCHRONIZED_CONTINUUM


def test_refuse_broken_l0(tmp_path):
    arch = tmp_path / "a"
    _seed_l0(arch)
    # corrupt a marked frame
    marked = list((arch / "marked").glob("*.png"))
    assert marked
    marked[0].write_bytes(b"not-a-png")
    with pytest.raises(ContinuumError):
        load_rwm_surface(arch, require_verified=True)
