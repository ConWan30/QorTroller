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
