"""Tests for l9_presence.kill_authorship_session — the L4 session-certificate record (Increment 2 step 1).

Pins the closed verdict enum's fail-closed ordering (hygiene beats kill-count — no authorship claim over a
dirty capture), the double-write dedup, coupling-never-gates, and the commitment's determinism +
tamper-evidence. Pure stdlib module; no cv2/bridge needed."""
from __future__ import annotations

from l9_presence import kill_authorship_session as kas


def _c(v="AUTHORED_PRESENT", ts=1000.0, score=0.8, gate=900.0, anchor="session_x@0.66"):
    return {"ts_ms": ts, "verdict": v, "composite_score": score, "window_gate_ms": gate, "anchor": anchor}


_H_OK = {"frame_errs": 0, "frame_stall_s": 0.0, "ts_source": "timespan"}


def test_authored_session_happy_path():
    r = kas.build_session_record(session_label="m1", handle="QorTrola30",
                                 composites=[_c(ts=1000, gate=900), _c(ts=2000, gate=1900, score=0.9)], hygiene=_H_OK)
    assert r.verdict == kas.AUTHORED_SESSION and r.authored_kills == 2
    assert r.anchor_tags == ["session_x@0.66"] and r.span_ms == [1000, 2000]


def test_insufficient_kills_is_honest_not_a_failure():
    r = kas.build_session_record(session_label="m", handle="h", composites=[_c()], hygiene=_H_OK)
    assert r.verdict == kas.INSUFFICIENT_KILLS and r.authored_kills == 1
    z = kas.build_session_record(session_label="m", handle="h",
                                 composites=[_c(v="UNVERIFIABLE")], hygiene=_H_OK)
    assert z.verdict == kas.INSUFFICIENT_KILLS and z.authored_kills == 0


def test_hygiene_fail_beats_kill_count():
    # 5 authored kills but a dirty capture -> HYGIENE_FAIL (never an authorship claim over bad capture).
    comps = [_c(ts=1000.0 + i, gate=900.0 + i * 100) for i in range(5)]   # distinct windows
    for bad in ({"frame_errs": 99, "frame_stall_s": 0.0, "ts_source": "timespan"},
                {"frame_errs": 0, "frame_stall_s": 30.0, "ts_source": "timespan"},
                {"frame_errs": 0, "frame_stall_s": 0.0, "ts_source": "wallclock"}):
        r = kas.build_session_record(session_label="m", handle="h", composites=comps, hygiene=bad)
        assert r.verdict == kas.HYGIENE_FAIL and r.authored_kills == 5 and r.notes


def test_unverifiable_on_missing_inputs():
    assert kas.build_session_record(session_label="m", handle="h", composites=[_c()],
                                    hygiene=None).verdict == kas.UNVERIFIABLE
    assert kas.build_session_record(session_label="m", handle="h", composites=None,
                                    hygiene=_H_OK).verdict == kas.UNVERIFIABLE


def test_double_write_dedup_differing_ts():
    # pre-63f25aa9 double-writes have DIFFERENT ts_ms (flush resolved at tick time, mark_onset at onset
    # time) — dedup keys on the stable window identity (window_gate_ms), not ts. Verified against the real
    # archive: g3mp 10->5, g3br_gatedcut 26->13, post-fix b2trace 10->10 unchanged.
    r = kas.build_session_record(session_label="m", handle="h",
                                 composites=[_c(ts=1000, gate=900), _c(ts=1450, gate=900),
                                             _c(ts=2000, gate=1900), _c(ts=2600, gate=1900)],
                                 hygiene=_H_OK)
    assert r.authored_kills == 2 and r.composites_total == 2
    # distinct windows with coincidentally equal scores stay distinct
    r2 = kas.build_session_record(session_label="m", handle="h",
                                  composites=[_c(ts=1000, gate=900), _c(ts=2000, gate=1900)],
                                  hygiene=_H_OK)
    assert r2.authored_kills == 2


def test_coupling_never_gates_the_verdict():
    # coupling absent, weak, or strong -> same verdict; it rides along as corroboration only.
    for coup in (None, {"coupled_true": 0}, {"coupled_true": 55, "max": 0.585}):
        r = kas.build_session_record(session_label="m", handle="h",
                                     composites=[_c(ts=1000, gate=900), _c(ts=2000, gate=1900)],
                                     hygiene=_H_OK, coupling=coup)
        assert r.verdict == kas.AUTHORED_SESSION and r.coupling_corroboration == coup


def test_b2_events_root_rides_into_the_commitment():
    # B2: the dual-lobe events_root binds the outcomes to the HID commitment — it's IN the commitment body, so
    # changing the root moves the KAS commitment (the certificate references the bound root). It does NOT gate
    # the verdict (still AUTHORED on the same kills).
    kw = dict(session_label="m", handle="h", composites=[_c(ts=1000, gate=900), _c(ts=2000, gate=1900)],
              hygiene=_H_OK)
    base = kas.build_session_record(**kw)
    bound = kas.build_session_record(**kw, events_root="ab" * 32, events_root_scheme="sha256_v1",
                                     events_root_lobes=["screen", "hid"])
    assert bound.verdict == kas.AUTHORED_SESSION and base.verdict == kas.AUTHORED_SESSION   # verdict unchanged
    assert bound.to_dict()["events_root"] == "ab" * 32 and bound.to_dict()["events_root_lobes"] == ["screen", "hid"]
    assert bound.commitment() != base.commitment()          # root is bound into the commitment
    # re-derivation is deterministic
    assert kas.build_session_record(**kw, events_root="ab" * 32, events_root_scheme="sha256_v1",
                                    events_root_lobes=["screen", "hid"]).commitment() == bound.commitment()


def test_cross_lobe_coherence_is_advisory_not_in_the_commitment():
    # the cross-lobe readout is DERIVED from the events already bound by events_root, so it rides in to_dict
    # ONLY — it must NOT move the commitment (unlike events_root, which IS bound). Two records identical except
    # for cross_lobe share a commitment; to_dict surfaces the readout; the verdict is unaffected.
    kw = dict(session_label="m", handle="h", composites=[_c(ts=1000, gate=900), _c(ts=2000, gate=1900)],
              hygiene=_H_OK, events_root="cd" * 32, events_root_scheme="sha256_v1",
              events_root_lobes=["screen", "hid"])
    base = kas.build_session_record(**kw)
    withx = kas.build_session_record(**kw, cross_lobe={"verdict": "COHERENT", "latencies_s": [0.12]})
    assert withx.commitment() == base.commitment()             # advisory -> NOT in the commitment
    assert withx.to_dict()["cross_lobe_coherence"] == {"verdict": "COHERENT", "latencies_s": [0.12]}
    assert base.to_dict()["cross_lobe_coherence"] is None
    assert withx.verdict == kas.AUTHORED_SESSION and base.verdict == kas.AUTHORED_SESSION


def test_commitment_deterministic_and_tamper_evident():
    kw = dict(session_label="m", handle="h", composites=[_c(ts=1000, gate=900), _c(ts=2000, gate=1900)], hygiene=_H_OK)
    a, b = kas.build_session_record(**kw), kas.build_session_record(**kw)
    assert a.commitment() == b.commitment() and len(a.commitment()) == 64
    d = a.to_dict()
    assert d["commitment"] == a.commitment() and d["kas_domain_tag"] == "QORTROLLER-KAS-v0"
    # tamper: any field change moves the commitment
    a.authored_kills = 99
    assert a.commitment() != b.commitment()
