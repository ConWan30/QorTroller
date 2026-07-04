"""Tests for the Increment-B B2 unification — ONE events_root per session window over BOTH lobes.

Pins: dual-lobe events land in one root; the root is order-INDEPENDENT (compute_events_root sorts) and
DETERMINISTIC (re-derive -> identical); the two lobes never collide (tagged); lobe labelling is honest
(screen-only session labels screen-only). Uses the existing retina_state_commitment root — NO new frozen tag.
"""
from __future__ import annotations

import pytest

pytest.importorskip("cv2")   # bridge import pulls the retina stack

from l9_presence import killfeed_screen_event as se  # noqa: E402
from vapi_bridge.retina_session_root import (  # noqa: E402
    LOBE_HID, LOBE_SCREEN, unify_session_events_root,
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


def test_session_screen_events_only_authored():
    comps = [{"verdict": "AUTHORED_PRESENT", "killer_first_ms": 1100.0, "ts_ms": 6100.0, "composite_score": 0.8,
              "engine": "rapidocr_ppocrv6_small", "match_kind": "exact", "raw_read": "Qortrola30"},
             {"verdict": "OWN_DEATH", "ts_ms": 7000.0}, {"verdict": "UNVERIFIABLE", "ts_ms": 8000.0}]
    evs = se.session_screen_events(comps)
    assert len(evs) == 1 and evs[0]["t_ms"] == 1100.0 and evs[0]["engine"] == "rapidocr_ppocrv6_small"
