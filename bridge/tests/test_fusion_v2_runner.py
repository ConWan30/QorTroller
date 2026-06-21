"""Test the Fusion v2 calibration runner's synthetic confusion (Phase 3 end-to-end)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, os.path.join(str(Path(__file__).resolve().parent.parent.parent), "scripts"))

import run_fusion_v2_experiment as R  # noqa: E402


def test_synthetic_confusion_separates_clean_and_relay():
    d = R.run_synthetic(seed=0, n_per_class=3)
    assert d["calibration"] == "UNCALIBRATED"
    conf = d["confusion_fusion_verdict"]
    # HUMAN_CLEAN concentrates on LIVE_COHERENT
    assert conf["HUMAN_CLEAN"]["LIVE_COHERENT"] == 3
    # HUMAN_RELAY (replay+relay, 2x rows) never reads LIVE_COHERENT
    assert conf["HUMAN_RELAY"].get("LIVE_COHERENT", 0) == 0
    assert conf["HUMAN_RELAY"]["REPLAY_OR_RELAY"] >= 3


def test_markdown_carries_uncalibrated_caveat():
    d = R.run_synthetic(seed=1, n_per_class=2)
    md = R.to_markdown(d)
    assert "UNCALIBRATED" in md and "N=1 falsifies" in md
    assert "class \\ verdict" in md


def _write_recorded_session(path, n=600, rate_hz=60.0, seed=0):
    """A recorded witness/cocapture-shape .npz (coupled camera, no OCR)."""
    import math
    import random
    import numpy as np
    rng = random.Random(seed)
    dt = 1000.0 / rate_hz
    ts = [i * dt for i in range(n)]
    sx = [128 + 60.0 * math.sin(2 * math.pi * 0.8 * t / 1000.0) for t in ts]
    sy = [128 + 8.0 * math.sin(2 * math.pi * 0.3 * t / 1000.0) for t in ts]
    lag = int(round(40.0 / dt))
    yaw = [rng.gauss(0, 0.4) for _ in range(n)]
    for i in range(lag, n):
        yaw[i] += (sx[i - lag] - 128) * 1.5
    pitch = [rng.gauss(0, 0.4) for _ in range(n)]
    fire = [200.0 if any(ot <= t < ot + 300 for ot in (1000.0, 4000.0)) else 0.0 for t in ts]
    np.savez(path, in_ts=ts, in_sx=sx, in_sy=sy, in_fire=fire,
             mo_ts=ts, mo_yaw=yaw, mo_pitch=pitch, label="human", player="P1")
    return str(path)


def test_from_session_builds_real_derived_confusion(tmp_path):
    p = _write_recorded_session(tmp_path / "P1_01.npz")
    d = R.run_from_session(p)
    assert d["provenance"] == "real_derived"
    assert d["source_session"] == "P1_01.npz"
    assert set(d["classes"]) >= {"HUMAN_CLEAN", "HUMAN_RELAY", "BOT_FULL", "HUMAN_INPUT_MACRO"}
    # base HUMAN_CLEAN: coupling proves presence (no OCR -> coherence INSUFFICIENT -> LIVE_COUPLED)
    base = d["rows"][0]
    assert base["class_label"] == "HUMAN_CLEAN"
    assert base["fusion_verdict"] in ("LIVE_COUPLED", "LIVE_COHERENT")
    # HUMAN_RELAY (replay/relay derived) never reads as a live human
    assert d["confusion_fusion_verdict"]["HUMAN_RELAY"].get("LIVE_COHERENT", 0) == 0
    assert d["confusion_fusion_verdict"]["HUMAN_RELAY"].get("LIVE_COUPLED", 0) == 0


def test_artifact_from_npz_carries_streams(tmp_path):
    p = _write_recorded_session(tmp_path / "P1_02.npz", n=120)
    a = R.artifact_from_npz(p, "HUMAN_CLEAN")
    assert len(a.in_ts) == 120 and len(a.mo_yaw) == 120
    assert a.provenance == "real" and a.hud_texts == []
