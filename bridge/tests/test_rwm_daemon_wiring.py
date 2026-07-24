"""RWM L0 daemon wiring (D6) — A2A rounds 02-06, grok design D1-D7 + 2 accepted flags.

Covers the four cases the design named:
  1. F-RWM-9 size guard reached through the daemon (frame too small -> skipped, not crashed)
  2. Integration: real chain built + verifies; bit-flip a marked file -> verify FAILS
  3. Monotonicity: non-monotonic source mtimes still yield strictly-increasing stored ts_ns
  4. Flag-off: stop path byte-identical when RWM_L0_DAEMON_ENABLED is unset

cv2-guarded: the marked-frame encoder is a real PNG write. cv2/opencv-python is NOT a
declared CI dependency (see docs/a2a/ci-debt/backlog.md), so these skip there rather than
failing on an absent encoder.
"""
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

from vapi_bridge.retina_capture_manifest import verify_session_chain  # noqa: E402


def _daemon():
    import retina_capture_daemon as d
    return d


DEVICE = "a" * 64


def _seed(dst: Path, n: int, size: int = 64) -> None:
    """n archived crops, named exactly as _archive_ring writes them."""
    dst.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        img = np.full((size, size, 3), (i * 7) % 256, dtype=np.uint8)
        cv2.imwrite(str(dst / f"panel_{i:04d}.png"), img)


def _run(monkeypatch, dst: Path, *, enabled=True, device=DEVICE):
    d = _daemon()
    monkeypatch.setenv("RWM_L0_DAEMON_ENABLED", "true" if enabled else "")
    if device is None:
        monkeypatch.delenv("RWM_DEVICE_ID_HEX", raising=False)
    else:
        monkeypatch.setenv("RWM_DEVICE_ID_HEX", device)
    d._issue_rwm_l0("testlabel", 1700000000, dst)
    p = dst / "rwm_manifest_chain.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


# --- 4. flag-off / fail-open: the stop path must be untouched --------------------------

def test_flag_off_writes_nothing(tmp_path, monkeypatch):
    """Default-OFF (D5). No manifest, no marked/ dir, no mutation of the archive."""
    _seed(tmp_path, 3)
    before = sorted(p.name for p in tmp_path.iterdir())
    assert _run(monkeypatch, tmp_path, enabled=False) is None
    assert not (tmp_path / "marked").exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_missing_device_id_skips_and_never_fabricates(tmp_path, monkeypatch):
    """D2: device_id is env-sourced; absent -> skip. A manifest that invents the device
    it attests is worse than no manifest."""
    _seed(tmp_path, 3)
    assert _run(monkeypatch, tmp_path, device=None) is None
    assert not (tmp_path / "rwm_manifest_chain.json").exists()


def test_empty_archive_skips(tmp_path, monkeypatch):
    tmp_path.mkdir(parents=True, exist_ok=True)
    assert _run(monkeypatch, tmp_path) is None


def test_none_dst_is_safe(tmp_path, monkeypatch):
    """Ring was empty -> _archive_ring returned None -> RWM must no-op, not raise."""
    d = _daemon()
    monkeypatch.setenv("RWM_L0_DAEMON_ENABLED", "true")
    monkeypatch.setenv("RWM_DEVICE_ID_HEX", DEVICE)
    d._issue_rwm_l0("testlabel", 1700000000, None)   # must not raise


# --- 2. integration: chain builds, verifies, and detects tampering ---------------------

def test_chain_builds_and_self_verifies(tmp_path, monkeypatch):
    dst = tmp_path / "arch"
    _seed(dst, 5)
    rec = _run(monkeypatch, dst)
    assert rec is not None
    assert rec["schema"] == "qortroller-rwm-session-chain-v0"
    assert rec["candidate"] is True
    assert rec["device_id_hex"] == DEVICE
    assert len(rec["frames"]) == 5
    assert len(rec["chain_hex"]) == 6            # genesis + 5 entries
    assert rec["locator"]["checkpoint_index"] == 0    # r06: stays 0 at L0
    # marked sidecar written; originals untouched (r02-q2)
    assert len(list((dst / "marked").glob("panel_*.png"))) == 5
    assert len(list(dst.glob("panel_*.png"))) == 5


def test_bitflip_in_marked_file_breaks_verification(tmp_path, monkeypatch):
    """The whole point: tamper-evidence over the bytes actually on disk (D3 step 4)."""
    dst = tmp_path / "arch"
    _seed(dst, 4)
    rec = _run(monkeypatch, dst)
    assert rec is not None

    frames = [(bytes.fromhex(f["frame_hash_hex"]), f["ts_ns"]) for f in rec["frames"]]
    chain = [bytes.fromhex(h) for h in rec["chain_hex"]]
    assert verify_session_chain(rec["session_id"], rec["device_id_hex"],
                                rec["genesis_ts_ns"], frames, chain) is True

    # flip one byte in a marked file, re-hash it as a verifier would
    import hashlib
    victim = dst / rec["frames"][1]["file"]
    raw = bytearray(victim.read_bytes())
    raw[-1] ^= 0x01
    victim.write_bytes(bytes(raw))
    frames[1] = (hashlib.sha256(victim.read_bytes()).digest(), frames[1][1])

    assert verify_session_chain(rec["session_id"], rec["device_id_hex"],
                                rec["genesis_ts_ns"], frames, chain) is False


# --- 3. monotonicity (D4 + Flag 2) -----------------------------------------------------

def test_non_monotonic_mtimes_still_yield_increasing_ts(tmp_path, monkeypatch):
    """Source mtimes deliberately go BACKWARD (NTP-correction shape). Stored ts_ns must
    still be strictly increasing -- and the schema must say those are session time, not
    filesystem truth (Flag 2)."""
    import os as _os
    dst = tmp_path / "arch"
    _seed(dst, 5)
    base = 1_700_000_000
    for i, p in enumerate(sorted(dst.glob("panel_*.png"))):
        t = base - i * 10          # strictly DECREASING
        _os.utime(p, (t, t))

    rec = _run(monkeypatch, dst)
    assert rec is not None
    ts = [f["ts_ns"] for f in rec["frames"]]
    assert ts == sorted(ts) and len(set(ts)) == len(ts), f"not strictly increasing: {ts}"
    assert "monotonic SESSION time" in rec["ts_ns_semantics"]
    assert "not filesystem wall-clock truth" in rec["ts_ns_semantics"]


# --- 1. F-RWM-9 size guard, reached through the daemon --------------------------------

def test_frame_too_small_for_block_is_skipped_not_crashed(tmp_path, monkeypatch):
    """A frame smaller than block_px raises inside composite_mark_onto_frame (F-RWM-9).
    The daemon edge decides skip-vs-fatal -- and it chooses skip, per D5 fail-open. This
    is exactly why the library raises instead of silently returning a wrong frame."""
    dst = tmp_path / "arch"
    _seed(dst, 3, size=64)
    _seed(dst, 0)
    tiny = np.zeros((16, 16, 3), dtype=np.uint8)      # < RWM_BLOCK_PX (32)
    cv2.imwrite(str(dst / "panel_9999.png"), tiny)

    rec = _run(monkeypatch, dst)
    assert rec is not None
    assert len(rec["frames"]) == 3                     # tiny one skipped, run survived
    assert all("9999" not in f["source"] for f in rec["frames"])
