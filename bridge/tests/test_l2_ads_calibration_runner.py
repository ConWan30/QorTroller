"""l2_ads calibration runner (Increment B.2) — HALT-PATHS-FIRST tests.

The load-bearing assertions: capture_segment ACTUALLY STOPS the segment (returns halted=True *before*
reaching N events) on either a tripped tripwire or a nonzero unlabeled-record count. A runner that reports
beautifully but keeps capturing would defeat the tripwire one layer up. Then the supporting helpers
(atomic write, tripwire-from-log replay, report, should_halt, transition log). scripts/ + tests only.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (_ROOT, os.path.join(_ROOT, "bridge")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_RUNNER = os.path.join(_ROOT, "scripts", "l2_ads_calibration_runner.py")
_spec = importlib.util.spec_from_file_location("l2_ads_calibration_runner", _RUNNER)
runner = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = runner          # register so @dataclass string-annotation resolution works
_spec.loader.exec_module(runner)

from l9_presence.ads_coupling import ADS_ABSTAIN_UNCALIBRATED
from vapi_bridge.qortroller_retina_capture import _read_ads_segment_file

THR = 40


def _reader(ads, cc):
    def _r(path):
        return cc if "crosscheck" in path else ads
    return _r


def _event(onset, segment="s1", verdict=ADS_ABSTAIN_UNCALIBRATED):
    return {"trigger_context": "ads_event", "onset_ts_ms": onset, "segment": segment, "verdict": verdict}


def _stuck_cc(n):
    # n consecutive raw-high/pyds-low disagreements, n_agree constant -> a sustained stuck run
    return [{"ts_ms": 100.0 + i, "raw_l2": 255, "pyds_l2": 0, "thr": THR, "n_agree": 0, "n_disagree": i + 1}
            for i in range(n)]


def _cap(ads, cc, n_events=15, n_trip=3):
    return runner.capture_segment(
        ads_log="retina_ads.jsonl", crosscheck_log="retina_ads_crosscheck.jsonl",
        segment="s1", optic="high_8x", fire_state="no_fire", n_events=n_events, thr=THR, n_trip=n_trip,
        window_start_ms=0.0, poll_interval_s=0.0, max_wait_s=999.0,
        now_fn=lambda: 1_000_000.0, read_fn=_reader(ads, cc), sleep_fn=lambda _s: None)


# --- HALT PATHS (load-bearing) ---------------------------------------------------------------------

def test_halt_on_tripwire_stops_before_N():
    # only 2 events captured (< N=15), but the crosscheck shows a sustained stuck run -> MUST halt, not wait
    ads = [_event(100), _event(600)]
    report, halted, reason = _cap(ads, _stuck_cc(3), n_events=15)
    assert halted is True and report.tripped is True
    assert report.n_events == 2 < 15               # stopped BEFORE reaching N — the tripwire actually halted
    assert "TRIPWIRE" in reason


def test_halt_on_unlabeled_stops_before_N():
    # a labeled event + an unlabeled record in-window (control-file write failing) -> MUST halt
    ads = [_event(100), {"trigger_context": "ads_event", "onset_ts_ms": 200, "segment": "unlabeled",
                         "verdict": ADS_ABSTAIN_UNCALIBRATED}]
    report, halted, reason = _cap(ads, [], n_events=15)
    assert halted is True and report.unlabeled_count == 1
    assert report.n_events == 1 < 15 and "UNLABELED" in reason


def test_halt_beats_reaching_N():
    # even with N events present, a tripped tripwire halts (halt is checked BEFORE the n_events success path)
    ads = [_event(100 + 50 * i) for i in range(20)]     # >= N events, well-spaced
    report, halted, reason = _cap(ads, _stuck_cc(3), n_events=15)
    assert halted is True and "TRIPWIRE" in reason


def test_clean_session_reaches_N_without_halt():
    ads = [_event(100 + 600 * i) for i in range(15)]    # 15 clean labeled events, no splits, no stuck
    report, halted, reason = _cap(ads, [], n_events=15)
    assert halted is False and report.n_events == 15 and report.tripped is False
    assert report.unlabeled_count == 0 and report.abstain_rate == 1.0


# --- supporting helpers ----------------------------------------------------------------------------

def test_atomic_write_roundtrips_through_reader():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "ads_segment.json")
    runner.atomic_write_segment(p, "high_8x", "no_fire", "s1")
    assert _read_ads_segment_file(p) == {"optic": "high_8x", "fire_state": "no_fire", "segment": "s1"}


def test_tripwire_from_log_sustained_trips_edge_skew_does_not():
    assert runner.tripwire_from_crosscheck_log(_stuck_cc(3), THR, 3)["tripped"] is True
    # edge-skew: single stuck disagreements separated by agreements (n_agree increments between them)
    skew = [{"ts_ms": 100.0, "raw_l2": 255, "pyds_l2": 0, "n_agree": 5, "n_disagree": 1},
            {"ts_ms": 200.0, "raw_l2": 255, "pyds_l2": 0, "n_agree": 9, "n_disagree": 2}]   # agreements between
    assert runner.tripwire_from_crosscheck_log(skew, THR, 3)["tripped"] is False


def test_build_report_counts_and_splits():
    ads = [_event(100), _event(300), _event(2000),                       # 300-100=200<400 -> 1 split
           {"trigger_context": "ads_event", "onset_ts_ms": 4000, "segment": "unlabeled",
            "verdict": ADS_ABSTAIN_UNCALIBRATED}]
    r = runner.build_segment_report(ads, [], segment="s1", optic="o", fire_state="f",
                                    window_start_ms=0.0, window_end_ms=1e9, thr=THR)
    assert r.n_events == 3 and r.split_count == 1 and r.unlabeled_count == 1 and r.abstain_rate == 1.0


def test_should_halt_matrix():
    def _rep(**kw):
        base = dict(segment="s", optic="o", fire_state="f", n_events=1, abstain_rate=1.0, n_disagreements=0,
                    split_count=0, unlabeled_count=0, tripped=False)
        base.update(kw)
        return runner.SegmentReport(**base)
    assert runner.should_halt(_rep(tripped=True))[0] is True
    assert runner.should_halt(_rep(unlabeled_count=2))[0] is True
    assert runner.should_halt(_rep())[0] is False


def test_transition_log_writes_boundary_events():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "session.jsonl")
    runner.log_transition(p, "segment_opened", optic="o", fire_state="f", segment="s1")
    runner.log_transition(p, "segment_closed", segment="s1", n_records=15)
    rows = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    assert rows[0]["event"] == "segment_opened" and rows[1]["event"] == "segment_closed"
    assert rows[1]["n_records"] == 15 and all("ts_ms" in r for r in rows)
