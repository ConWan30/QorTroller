"""Tests for l9_presence.killfeed_screen_event — the shared screen-lobe event schema (Increment B, Phase B1).

Pins the D-TRIO-1 clock discipline (event t = kill-row FRAME-CAPTURE ts, with an honest resolution_fallback
flag), the C3 provenance payload (engine/anchor/raw/match_kind), the D-TRIO-2 freshness field, and the
outcome-only + input_caused anti-splice framing. Pure dict transforms."""
from __future__ import annotations

from l9_presence import killfeed_screen_event as se


def _authored(**kw):
    base = {"verdict": "AUTHORED_PRESENT", "killer_first_ms": 1100.0, "ts_ms": 9000.0,
            "read_latency_ms": 100.0, "composite_score": 0.8, "window_members": 3, "anchor": "session_x@0.66"}
    base.update(kw)
    return base


def test_authored_event_uses_frame_capture_clock_and_carries_c3():
    ev = se.authored_screen_event(_authored(), engine="rapidocr_ppocrv6_small", anchor_sha="6f327246",
                                  raw_read="Qortrola30", match_kind="exact", row_freshness=True)
    assert ev["type"] == se.SCREEN_EVENT_AUTHORED
    assert ev["t_ms"] == 1100.0 and ev["clock"] == se.CLOCK_FRAME_CAPTURE   # D-TRIO-1
    assert ev["read_latency_ms"] == 100.0                                   # rides separately
    assert ev["engine"] == "rapidocr_ppocrv6_small" and ev["anchor"] == "6f327246"   # C3
    assert ev["raw_read"] == "Qortrola30" and ev["match_kind"] == "exact"
    assert ev["row_freshness"] is True                                      # D-TRIO-2
    assert ev["input_caused"] is True                                       # anti-splice framing


def test_resolution_fallback_is_flagged_not_silent():
    # no frame-capture anchor -> t falls to the resolution ts BUT the clock field says so (never silently mixed)
    ev = se.authored_screen_event(_authored(killer_first_ms=None))
    assert ev["t_ms"] == 9000.0 and ev["clock"] == se.CLOCK_RESOLUTION_FALLBACK


def test_only_authored_becomes_an_outcome():
    assert se.authored_screen_event({"verdict": "OWN_DEATH", "killer_first_ms": 1.0}) is None
    assert se.authored_screen_event({"verdict": "UNVERIFIABLE", "killer_first_ms": 1.0}) is None
    assert se.authored_screen_event(None) is None


def test_session_provenance_default_fills_c3_when_composites_lack_it():
    # sess_ab case: live composites carry NO engine/match/raw (C3 lives on the candidate_cut log line, not the
    # composite). session_screen_events threads a session-wide provenance default so the screen-lobe events STILL
    # carry the actual live model id — not None. Per-composite C3 (if present) still wins over the default.
    comps = [{"verdict": "AUTHORED_PRESENT", "killer_first_ms": 1100.0, "ts_ms": 6100.0, "composite_score": 0.8},
             {"verdict": "AUTHORED_PRESENT", "killer_first_ms": 2200.0, "ts_ms": 7200.0, "composite_score": 0.9,
              "engine": "tesseract_row_v1", "match_kind": "fuzzy", "raw_read": "qortrola30x"}]
    prov = {"engine": "rapidocr_ppocrv6_small", "anchor_sha": "6f327246", "raw_read": "Qortrola30",
            "match_kind": "exact"}
    evs = se.session_screen_events(comps, provenance=prov)
    assert len(evs) == 2
    assert evs[0]["engine"] == "rapidocr_ppocrv6_small" and evs[0]["match_kind"] == "exact"   # default fills
    assert evs[0]["raw_read"] == "Qortrola30" and evs[0]["anchor"] == "6f327246"
    assert evs[1]["engine"] == "tesseract_row_v1" and evs[1]["match_kind"] == "fuzzy"          # per-composite wins


def test_to_timed_event_seconds_and_outcome():
    ev = se.authored_screen_event(_authored())
    te = se.to_timed_event(ev)
    assert te == {"kind": "outcome", "type": "kill_authored", "t": 1.1, "input_caused": True}   # 1100ms -> 1.1s
    assert se.to_timed_event({"t_ms": None}) is None
    # round-trips into the real TimedEvent
    from vapi_bridge.retina_causal_coherence import TimedEvent
    tev = TimedEvent(**te)
    assert tev.kind == "outcome" and tev.t == 1.1 and tev.input_caused is True
