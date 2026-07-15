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
    fresh_nonce,
    nonce_derived_delay_s,
)

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
