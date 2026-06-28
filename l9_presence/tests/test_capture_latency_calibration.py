"""Tests for the cross-channel latency calibration capture (scripts/capture_latency_calibration.py).

Pure parser coverage: harvesting RGC-diag status lines from a bridge log into ChannelLag sessions, the
None-channel skip rule, malformed-line tolerance, and the JSONL round-trip the calibrate step consumes.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_REPO, "scripts"))

import capture_latency_calibration as cap  # noqa: E402
from l9_presence.cross_channel_latency import ChannelLag, LatencyVerdict, assess_latency_agreement  # noqa: E402

_FULL = ("2026-06-28 10:00:00 INFO RGC diag: {'started': True, 'frames_seen': 120, "
         "'coupling_score': 0.42, 'negative_control': 0.03, 'lag_ms': 145.0, "
         "'th_coupling': 0.38, 'th_null': 0.04, 'th_lag_ms': 150.0, "
         "'th2_coupling': 0.31, 'th2_null': 0.02, 'th2_lag_ms': 148.0, 'ts_source': 'timespan'}")
_PARTIAL = ("2026-06-28 10:00:20 INFO RGC diag: {'started': True, 'frames_seen': 240, "
            "'coupling_score': 0.40, 'negative_control': 0.05, 'lag_ms': 150.0, "
            "'th_coupling': None, 'th_null': None, 'th_lag_ms': None, "
            "'th2_coupling': 0.30, 'th2_null': 0.02, 'th2_lag_ms': 152.0}")


def test_parse_rgc_diag_extracts_and_skips_noise():
    text = "\n".join(["unrelated log line", _FULL, "RGC diag: {not valid python", _PARTIAL])
    diags = cap.parse_rgc_diag(text)
    assert len(diags) == 2                       # the malformed dict line is skipped, not raised
    assert diags[0]["ts_source"] == "timespan" and diags[0]["frames_seen"] == 120


def test_sample_to_channels_full_and_partial():
    full = cap.sample_to_channels(cap.parse_rgc_diag(_FULL)[0])
    assert {c.channel for c in full} == {"geometric", "b1_flash", "b2_killmark"}   # 3 channels
    assert any(abs(c.lag_ms - 145.0) < 1e-9 for c in full)
    partial = cap.sample_to_channels(cap.parse_rgc_diag(_PARTIAL)[0])
    assert {c.channel for c in partial} == {"geometric", "b2_killmark"}            # B1 None -> dropped


def test_harvest_roundtrip_and_feeds_assessment(tmp_path):
    log = tmp_path / "bridge.log"
    log.write_text("\n".join([_FULL, _PARTIAL, _FULL]), encoding="utf-8")
    out = tmp_path / "genuine.jsonl"
    n = cap._harvest(str(log), str(out), min_channels=2)
    assert n == 3                                 # all three samples have >= 2 channels
    sessions = cap.load_sessions(str(out))
    assert len(sessions) == 3
    assert all(isinstance(c, ChannelLag) for c in sessions[0])
    # the 3-channel genuine sample's lags cluster -> the gate reads PRESENT_COHERENT
    r = assess_latency_agreement(sessions[0])
    assert r.verdict is LatencyVerdict.PRESENT_COHERENT


def test_harvest_min_channels_filter(tmp_path):
    log = tmp_path / "b.log"
    # one full (3ch) + one single-channel-only sample (geometric only -> filtered at min_channels=2)
    single = ("RGC diag: {'coupling_score': 0.4, 'negative_control': 0.03, 'lag_ms': 145.0, "
              "'th_coupling': None, 'th_lag_ms': None, 'th2_coupling': None, 'th2_lag_ms': None}")
    log.write_text("\n".join([_FULL, single]), encoding="utf-8")
    out = tmp_path / "o.jsonl"
    assert cap._harvest(str(log), str(out), min_channels=2) == 1   # the single-channel sample is dropped
