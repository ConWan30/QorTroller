"""Tests for the Increment-B B2 unification — ONE events_root per session window over BOTH lobes.

Pins: dual-lobe events land in one root; the root is order-INDEPENDENT (compute_events_root sorts) and
DETERMINISTIC (re-derive -> identical); the two lobes never collide (tagged); lobe labelling is honest
(screen-only session labels screen-only). Uses the existing retina_state_commitment root — NO new frozen tag.
"""
from __future__ import annotations

import pytest

pytest.importorskip("cv2")   # bridge import pulls the retina stack

from l9_presence import killfeed_hid_event as he  # noqa: E402
from l9_presence import killfeed_screen_event as se  # noqa: E402
from vapi_bridge.retina_session_root import (  # noqa: E402
    LOBE_HID, LOBE_SCREEN, cross_lobe_coherence, unify_session_events_root,
)


def _screen(t_ms):
    return se.authored_screen_event({"verdict": "AUTHORED_PRESENT", "killer_first_ms": t_ms, "ts_ms": t_ms + 5000,
                                     "composite_score": 0.8, "anchor": "session_x@0.66"},
                                    engine="rapidocr_ppocrv6_small", raw_read="Qortrola30", match_kind="exact")


def _hid(t_ms, typ="r2_onset"):
    return {"type": typ, "t_ms": t_ms, "input_caused": False}


def test_dual_lobe_one_root_deterministic_and_order_independent():
    scr = [_screen(1100.0), _screen(2200.0)]
    hid = [_hid(1000.0), _hid(2100.0)]
    a = unify_session_events_root(screen_events=scr, hid_events=hid)
    b = unify_session_events_root(screen_events=list(reversed(scr)), hid_events=list(reversed(hid)))
    assert a["events_root"] == b["events_root"] and len(a["events_root"]) == 64   # order-independent + det
    assert a["lobes"] == [LOBE_SCREEN, LOBE_HID] and a["n_screen"] == 2 and a["n_hid"] == 2


def test_lobes_tagged_so_they_never_collide():
    # a screen event and a hid event with identical t must NOT collapse to one canonical line
    scr = unify_session_events_root(screen_events=[_screen(1000.0)], hid_events=[])
    hid = unify_session_events_root(screen_events=[], hid_events=[_hid(1000.0)])
    both = unify_session_events_root(screen_events=[_screen(1000.0)], hid_events=[_hid(1000.0)])
    assert scr["events_root"] != hid["events_root"] != both["events_root"] != scr["events_root"]


def test_screen_only_session_labels_honestly():
    u = unify_session_events_root(screen_events=[_screen(1100.0)])
    assert u["lobes"] == [LOBE_SCREEN] and u["n_hid"] == 0


def test_cross_lobe_coherence_measures_input_to_outcome_latency():
    # the payoff: each screen kill-OUTCOME matched to a preceding HID R2-onset INPUT -> COHERENT + the
    # per-outcome cross-lobe latency (screen frame-capture ts - HID onset device ts) is measured.
    scr = [{"type": "kill_authored", "t_ms": 1120.0, "input_caused": True},
           {"type": "kill_authored", "t_ms": 2200.0, "input_caused": True},
           {"type": "kill_authored", "t_ms": 3300.0, "input_caused": True}]
    hid = [he.hid_onset_event(t_ms=1000.0), he.hid_onset_event(t_ms=2100.0), he.hid_onset_event(t_ms=3200.0)]
    d = cross_lobe_coherence(scr, hid)
    assert d["verdict"] == "COHERENT" and d["n_matched"] == 3 and d["n_hid_inputs"] == 3
    assert d["nearest_preceding_latency_s"] == [0.12, 0.1, 0.1]   # 1120-1000, 2200-2100, 3300-3200 ms
    assert d["calibration"] == "UNCALIBRATED"                # honest: hypothesis until co-capture


def test_cross_lobe_coherence_screen_only_and_fail_open():
    # no HID lobe -> no inputs to explain the outcomes (screen-only session); and garbage never raises
    d = cross_lobe_coherence([{"type": "kill_authored", "t_ms": 1120.0, "input_caused": True}], [])
    assert d["n_hid_inputs"] == 0 and d["n_matched"] == 0
    assert cross_lobe_coherence([{"nonsense": 1}], [{"nonsense": 1}])["calibration"] == "UNCALIBRATED"


def test_session_screen_events_only_authored():
    comps = [{"verdict": "AUTHORED_PRESENT", "killer_first_ms": 1100.0, "ts_ms": 6100.0, "composite_score": 0.8,
              "engine": "rapidocr_ppocrv6_small", "match_kind": "exact", "raw_read": "Qortrola30"},
             {"verdict": "OWN_DEATH", "ts_ms": 7000.0}, {"verdict": "UNVERIFIABLE", "ts_ms": 8000.0}]
    evs = se.session_screen_events(comps)
    assert len(evs) == 1 and evs[0]["t_ms"] == 1100.0 and evs[0]["engine"] == "rapidocr_ppocrv6_small"
