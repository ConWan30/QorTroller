"""NOV-1 stranger pack — T1–T5 (plan)."""
from __future__ import annotations

import base64
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "bridge"))
sys.path.insert(0, str(_REPO / "scripts"))

np = pytest.importorskip("numpy")
pytest.importorskip("cv2")
import cv2  # noqa: E402

from vapi_bridge.rwm_stranger_pack import (  # noqa: E402
    SCHEMA,
    StrangerPackError,
    build_stranger_pack,
    verify_stranger_pack,
)

DEVICE = "cd" * 32


def _seed_l0(dst: Path, n: int = 8, size: int = 64) -> None:
    import os

    import retina_capture_daemon as d

    dst.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        img = np.full((size, size, 3), (i * 19) % 256, dtype=np.uint8)
        cv2.imwrite(str(dst / f"panel_{i:04d}.png"), img)
    os.environ["RWM_L0_DAEMON_ENABLED"] = "true"
    os.environ["RWM_DEVICE_ID_HEX"] = DEVICE
    d._issue_rwm_l0("nov1_test", 1_700_000_200, dst)
    assert (dst / "rwm_manifest_chain.json").is_file()


# T1
def test_t1_build_verify_archive_free(tmp_path):
    arch = tmp_path / "a"
    _seed_l0(arch, n=6)
    pack = build_stranger_pack(arch, [0, 2, 5], "tournament dispute: sample frames")
    assert pack["schema"] == SCHEMA
    assert pack["candidate"] is True
    assert len(pack["revealed"]) == 3
    assert all("marked_png_b64" in r for r in pack["revealed"])
    # verify WITHOUT archive_dir
    r = verify_stranger_pack(pack)
    assert r["ok"] is True, r


# T2
def test_t2_bit_flip_media_fails(tmp_path):
    arch = tmp_path / "a"
    _seed_l0(arch, n=6)
    pack = build_stranger_pack(arch, [0, 1], "tournament dispute: sample frames")
    raw = base64.b64decode(pack["revealed"][0]["marked_png_b64"])
    flipped = bytes([raw[0] ^ 0xFF]) + raw[1:]
    pack["revealed"][0]["marked_png_b64"] = base64.b64encode(flipped).decode("ascii")
    r = verify_stranger_pack(pack)
    assert r["ok"] is False
    assert any(not c["ok"] and "media_hash" in c["name"] for c in r["checks"])


# T3
def test_t3_wrong_leaf_fails_root(tmp_path):
    arch = tmp_path / "a"
    _seed_l0(arch, n=6)
    pack = build_stranger_pack(arch, [0, 3], "tournament dispute: sample frames")
    pack["commitment_root"] = "ff" * 32
    r = verify_stranger_pack(pack)
    assert r["ok"] is False
    assert any(c["name"] == "commitment_root" and not c["ok"] for c in r["checks"])


# T4
def test_t4_empty_reveal_refused(tmp_path):
    arch = tmp_path / "a"
    _seed_l0(arch, n=4)
    with pytest.raises(StrangerPackError):
        build_stranger_pack(arch, [], "tournament dispute: sample frames")


# T5 — no network imports in module hot path (structural)
def test_t5_module_is_offline_only():
    import vapi_bridge.rwm_stranger_pack as m

    src = Path(m.__file__).read_text(encoding="utf-8")
    assert "urllib" not in src
    assert "requests" not in src
    assert "http.client" not in src
    assert "socket" not in src
