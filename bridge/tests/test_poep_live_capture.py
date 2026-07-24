"""POEP-LIVE-1 pure-surface tests (no hardware). The runner's security property is the UNPREDICTABLE
nonce-scheduled challenge time + fresh-nonce binding; these tests pin the pure functions that carry it
and confirm the record builder wires straight into the P-LIVE-0 auditor (which the hardware loop then
feeds real reflexes into). poep_enabled must stay False in every record.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.poep_live_capture import (
    DEFAULT_MAX_DELAY_S,
    DEFAULT_MIN_DELAY_S,
    build_live_record,
    csprng_delay_s,
    fresh_nonce,
    nonce_derived_delay_s,
    reflex_curve,
)
from l9_presence.poep_live_verify import waveform_commitment, waveform_digest

DEV = "581a836c98b3a1b6c0f598bfca88e6a3cc3bd7c34591b506692cb40ddf66a9f8"
T0 = 1_000_000_000_000  # challenge fire (ns)


# --- nonce-derived unpredictable delay --------------------------------------------------------------

def test_delay_within_window_and_deterministic_from_nonce():
    n = "0011223344556677" + "8899aabbccddeeff"
    d1 = nonce_derived_delay_s(n)
    d2 = nonce_derived_delay_s(n)
    assert d1 == d2                                   # nonce-committed (a verifier can re-derive)
    assert DEFAULT_MIN_DELAY_S <= d1 <= DEFAULT_MAX_DELAY_S


def test_delay_varies_across_fresh_nonces():
    delays = {nonce_derived_delay_s(fresh_nonce()) for _ in range(200)}
    # a fixed-schedule macro cannot anticipate the onset: many distinct delays across fresh nonces
    assert len(delays) > 20
    assert all(DEFAULT_MIN_DELAY_S <= d <= DEFAULT_MAX_DELAY_S for d in delays)


def test_fresh_nonce_is_unique_and_hex():
    ns = {fresh_nonce() for _ in range(500)}
    assert len(ns) == 500
    assert all(len(n) == 32 and int(n, 16) >= 0 for n in ns)


def test_degenerate_window_returns_min():
    assert nonce_derived_delay_s(fresh_nonce(), min_s=5.0, max_s=5.0) == 5.0


# --- F-POEP-LIVE-1 (ii): independent CSPRNG delay ---------------------------------------------------

def test_csprng_delay_in_window_and_independent_of_nonce():
    # the security-critical delay is drawn from an INDEPENDENT CSPRNG, not the nonce (no bit double-duty)
    for _ in range(200):
        d = csprng_delay_s(min_s=3.0, max_s=12.0)
        assert 3.0 <= d <= 12.0
    delays = {csprng_delay_s(min_s=3.0, max_s=12.0) for _ in range(200)}
    assert len(delays) > 20                       # genuinely random, not a single value


def test_csprng_degenerate_window_returns_min():
    assert csprng_delay_s(min_s=5.0, max_s=5.0) == 5.0


# --- record builder feeds the P-LIVE-0 auditor ------------------------------------------------------

def test_good_reflex_record_passes_live_verify():
    r = build_live_record(
        device_id=DEV, nonce="fresh-abc", t_challenge_ns=T0,
        latency_ms=168.0, peak_lsb=1520.0, precursor_gap_ms=9.0,
        classification="HUMAN_REFLEX", challenge_index=1, delay_s=7.3,
    )
    assert r["verify"]["ok"] is True
    assert r["verify"]["commitment_ok"] is True
    assert r["latency_ms"] == 168.0
    # commitment recomputes from the stored scalars (binding is real, not asserted)
    assert len(r["commitment"]) == 64


def test_out_of_band_reflex_fails_live_verify():
    # 40ms is faster than any human reaction -> anticipation / pre-press -> reaction-band FAIL
    r = build_live_record(
        device_id=DEV, nonce="n2", t_challenge_ns=T0,
        latency_ms=40.0, peak_lsb=1600.0, precursor_gap_ms=5.0,
        classification="AMBIGUOUS", challenge_index=1, delay_s=4.0,
    )
    assert r["verify"]["ok"] is False
    assert any("reaction_band" in x for x in r["verify"]["reasons"])


def test_no_response_fails_honestly_never_spurious_pass():
    # operator did not react: no clean peak -> latency None + peak below IMU floor -> honest FAIL
    r = build_live_record(
        device_id=DEV, nonce="n3", t_challenge_ns=T0,
        latency_ms=None, peak_lsb=120.0, precursor_gap_ms=None,
        classification="NO_RESPONSE", challenge_index=1, delay_s=9.0,
    )
    v = r["verify"]
    assert v["ok"] is False
    assert r["latency_ms"] is None
    # t_response collapses to t_challenge -> not-after-challenge; and peak below floor
    assert any("not_after_challenge" in x for x in v["reasons"])
    assert any("no_imu_corroboration" in x for x in v["reasons"])


def test_record_never_flips_poep_or_claims_presence():
    r = build_live_record(
        device_id=DEV, nonce="n4", t_challenge_ns=T0,
        latency_ms=170.0, peak_lsb=1500.0, precursor_gap_ms=8.0,
        classification="HUMAN_REFLEX", challenge_index=1, delay_s=6.0,
    )
    assert r["verify"]["poep_enabled"] is False
    assert r["verify"]["is_presence_verdict"] is False


def test_record_without_arm_time_has_no_schedule_leg():
    # legacy call (no t_arm_ns) -> schedule not bound, schedule_ok None, still passes
    r = build_live_record(
        device_id=DEV, nonce="leg", t_challenge_ns=T0,
        latency_ms=168.0, peak_lsb=1520.0, precursor_gap_ms=9.0,
        classification="HUMAN", challenge_index=1, delay_s=7.0,
    )
    assert r["schedule_commitment"] is None
    assert r["verify"]["schedule_ok"] is None
    assert r["verify"]["ok"] is True


def test_record_with_arm_time_binds_schedule_and_verifies():
    # (ii): t_arm_ns given -> schedule commitment bound, and t_challenge == t_arm + delay -> schedule_ok
    delay_s = 7.0
    t_arm = T0 - int(delay_s * 1e9)
    r = build_live_record(
        device_id=DEV, nonce="sch", t_challenge_ns=T0,
        latency_ms=168.0, peak_lsb=1520.0, precursor_gap_ms=9.0,
        classification="HUMAN", challenge_index=1, delay_s=delay_s, t_arm_ns=t_arm,
    )
    assert r["schedule_commitment"] is not None and len(r["schedule_commitment"]) == 64
    assert r["t_arm_ns"] == t_arm
    assert r["verify"]["schedule_ok"] is True
    assert r["verify"]["ok"] is True


# --- FLIP-A rung 2: reflex waveform capture --------------------------------------------------------

def _rep(ax, ay, az):
    return {"ax": ax, "ay": ay, "az": az, "t_mono": 0.0}


def test_reflex_curve_dc_removes_baseline():
    # pre baseline magnitude ~1000; post rises above it -> DC-removed curve starts ~0 and rises
    pre = [_rep(1000.0, 0.0, 0.0) for _ in range(5)]
    post = [_rep(1000.0, 0.0, 0.0), _rep(1500.0, 0.0, 0.0), _rep(3000.0, 0.0, 0.0),
            _rep(1200.0, 0.0, 0.0)]
    curve = reflex_curve(pre, post)
    assert curve[0] == 0.0                 # onset-aligned at the baseline
    assert curve[2] == 2000.0              # peak above baseline
    assert len(curve) == len(post)


def test_reflex_curve_empty_post_is_empty():
    assert reflex_curve([_rep(1.0, 1.0, 1.0)], []) == []


def test_record_with_waveform_binds_waveform_commitment():
    wf = [0.0, 500.0, 2000.0, 1200.0, 1000.0, 990.0]
    r = build_live_record(
        device_id=DEV, nonce="wav", t_challenge_ns=T0,
        latency_ms=168.0, peak_lsb=2000.0, precursor_gap_ms=9.0,
        classification="HUMAN", challenge_index=1, delay_s=7.0, waveform=wf,
    )
    assert r["waveform"] == wf
    assert r["waveform_digest"] == waveform_digest(wf)
    assert r["waveform_commitment"] == waveform_commitment(
        nonce="wav", wave_digest=waveform_digest(wf), t_challenge_ns=T0)
    # a swapped waveform breaks the digest -> integrity detectable downstream
    assert waveform_digest(wf) != waveform_digest(wf[:-1] + [0.0])


def test_record_without_waveform_has_no_waveform_fields():
    r = build_live_record(
        device_id=DEV, nonce="now", t_challenge_ns=T0,
        latency_ms=168.0, peak_lsb=2000.0, precursor_gap_ms=9.0,
        classification="HUMAN", challenge_index=1, delay_s=7.0,
    )
    assert r["waveform"] is None
    assert r["waveform_digest"] is None
    assert r["waveform_commitment"] is None
