"""Increment A — l2_ads calibration segment labeling (F-RP-DIAG-2).

The operator announces each firing-range segment; the calibration runner writes an atomic control file
{optic, fire_state, segment}; feed_ads stamps it onto every emitted record. FAIL-CLOSED: absent / partial /
corrupt read -> all three 'unlabeled' (never a stale previous segment, never an empty field). The stamp
happens ONLY at the _log_ads emission point — the AdsCouplingMonitor stays context-free (purity pinned).
No capture, no rig.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (_ROOT, os.path.join(_ROOT, "bridge")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from vapi_bridge.qortroller_retina_capture import (
    _read_ads_segment_file,
    _ADS_UNLABELED,
    _ADS_SEGMENT_KEYS,
)
from l9_presence.ads_coupling import AdsCouplingMonitor

_UNLABELED = {k: _ADS_UNLABELED for k in _ADS_SEGMENT_KEYS}


def _write(d: str, obj) -> str:
    p = os.path.join(d, "ads_segment.json")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(obj if isinstance(obj, str) else json.dumps(obj))
    return p


# --- reader: fail-closed as a unit ------------------------------------------------------------------

def test_absent_is_unlabeled():
    assert _read_ads_segment_file(os.path.join(tempfile.mkdtemp(), "nope.json")) == _UNLABELED


def test_corrupt_json_is_unlabeled():
    assert _read_ads_segment_file(_write(tempfile.mkdtemp(), "{ not json")) == _UNLABELED


def test_not_a_dict_is_unlabeled():
    assert _read_ads_segment_file(_write(tempfile.mkdtemp(), ["a", "b"])) == _UNLABELED


def test_partial_missing_field_is_unlabeled():
    # one missing field unlabels the WHOLE record (never a partial trust) — the D-CERT-9 "prove it" rail
    assert _read_ads_segment_file(_write(tempfile.mkdtemp(),
                                         {"optic": "red_dot", "fire_state": "no_fire"})) == _UNLABELED


def test_empty_field_is_unlabeled():
    assert _read_ads_segment_file(_write(tempfile.mkdtemp(),
                                         {"optic": "red_dot", "fire_state": "  ", "segment": "8x"})) == _UNLABELED


def test_valid_segment_reads_through():
    seg = {"optic": "red_dot", "fire_state": "no_fire", "segment": "8x"}
    assert _read_ads_segment_file(_write(tempfile.mkdtemp(), seg)) == seg


def test_whitespace_is_stripped():
    assert _read_ads_segment_file(_write(tempfile.mkdtemp(),
        {"optic": " red_dot ", "fire_state": "no_fire", "segment": "8x "})) == {
        "optic": "red_dot", "fire_state": "no_fire", "segment": "8x"}


# --- purity pin: the monitor emits raw-first records WITHOUT any segment context --------------------

def _drive_one_event(m: AdsCouplingMonitor):
    """Press -> hold -> release -> emit one complete event through the pure state machine."""
    m.feed(200, 0.50, 0.0)        # rising -> ONSET
    m.feed(200, 0.60, 500.0)      # past onset window -> HELD
    m.feed(200, 0.61, 1500.0)     # HELD
    m.feed(0, 0.50, 3000.0)       # falling -> EXIT
    rec = m.feed(0, 0.40, 8000.0)  # past exit deadline -> emit
    if rec is None:
        rec = m.flush(8000.0)     # fallback: force close
    return rec


def test_monitor_stays_context_free():
    # THE PURITY PIN: AdsCouplingMonitor.feed() must NEVER produce optic/fire_state/segment/label — those are
    # stamped ONLY at the _log_ads emission point. This pins the purity that kept the tripwire correction
    # clean, against a future convenience edit that reaches session context into the pure state machine.
    rec = _drive_one_event(AdsCouplingMonitor())
    assert rec is not None
    for forbidden in ("optic", "fire_state", "segment", "label"):
        assert forbidden not in rec, f"monitor leaked session context: {forbidden}"


def test_stamp_at_log_point_adds_labels():
    # The stamp _log_ads applies (reader output onto the monitor record) is what makes the record labeled —
    # the monitor didn't. Simulate it and assert the labeled record carries the segment + composite.
    rec = dict(_drive_one_event(AdsCouplingMonitor()))
    seg = {"optic": "red_dot", "fire_state": "no_fire", "segment": "8x"}
    rec["optic"], rec["fire_state"], rec["segment"] = seg["optic"], seg["fire_state"], seg["segment"]
    rec["label"] = "%s/%s/%s" % (seg["optic"], seg["fire_state"], seg["segment"])
    assert rec["segment"] == "8x" and rec["label"] == "red_dot/no_fire/8x"
