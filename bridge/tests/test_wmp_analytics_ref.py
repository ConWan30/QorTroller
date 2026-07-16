"""WMP UC-5 analytics reference tests. Pins the consent-gate rails (grok round-1 highest-risk hammers),
the aggregate math, the provenance row-commitment binding, and the output triple. These vectors are the
parity contract the wasm port must reproduce (docs/wmp-uc5-wasm-analytics-design.md).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from bridge.vapi_bridge.wmp.analytics_ref import (
    ConsentError,
    aggregate,
    gate_rows,
    row_commitment,
)

_MARKET = 1 << 3           # MARKETPLACE consent bit
_GEC_A = "aa" * 32
_GEC_B = "bb" * 32


def _row(field="session_tick_count", value=100, consent=_MARKET, cross=True, gec=_GEC_A):
    return {"field_id": field, "value_i64": value, "consent_bits": consent,
            "cross_aggregate_ok": cross, "gamer_export_commitment": gec}


# --- consent + allowlist rails (fail-closed) --------------------------------------------------------

def test_missing_consent_bit_fails_closed():
    with pytest.raises(ConsentError):
        gate_rows([_row(consent=1 << 1)], requested_category="MARKETPLACE")  # only RESEARCH bit set


def test_field_not_in_allowlist_fails_closed():
    with pytest.raises(ConsentError):
        gate_rows([_row(field="imu_tremor_variance")], requested_category="MARKETPLACE")


def test_cross_gamer_requires_every_row_flag():
    rows = [_row(gec=_GEC_A, cross=True), _row(gec=_GEC_B, cross=False)]  # 2 gamers, one not opted-in
    with pytest.raises(ConsentError):
        gate_rows(rows, requested_category="MARKETPLACE")


def test_single_gamer_does_not_need_cross_flag():
    gate_rows([_row(gec=_GEC_A, cross=False), _row(gec=_GEC_A, cross=False)], requested_category="MARKETPLACE")


def test_bad_gamer_commitment_hex_rejected():
    with pytest.raises(ConsentError):
        row_commitment(_row(gec="xyz"))


# --- provenance binding: consent is IN the preimage (grok's rail) -----------------------------------

def test_row_commitment_is_deterministic_and_consent_bound():
    r = _row(value=42, consent=_MARKET)
    c1 = row_commitment(r)
    assert c1 == row_commitment(dict(r)) and len(c1) == 64
    # flipping the consent bits changes the commitment -> a host can't forge consent silently
    assert row_commitment({**r, "consent_bits": _MARKET | 1}) != c1
    # flipping the value or the cross flag also changes it
    assert row_commitment({**r, "value_i64": 43}) != c1
    assert row_commitment({**r, "cross_aggregate_ok": not r["cross_aggregate_ok"]}) != c1


# --- aggregate math + the triple --------------------------------------------------------------------

def test_count_sum_mean_p50():
    rows = [_row(value=v) for v in (10, 20, 30, 40)]
    assert aggregate(rows, op="count", field_id="session_tick_count", requested_category="MARKETPLACE")["statistic"]["payload"]["value"] == "4"
    assert aggregate(rows, op="sum", field_id="session_tick_count", requested_category="MARKETPLACE")["statistic"]["payload"]["value"] == "100"
    mean = aggregate(rows, op="mean", field_id="session_tick_count", requested_category="MARKETPLACE")["statistic"]["payload"]
    assert mean["value"] == "25000" and mean["scale"] == "milli"    # 25.000 as milli, no float
    p50 = aggregate(rows, op="p50", field_id="session_tick_count", requested_category="MARKETPLACE")["statistic"]["payload"]
    assert p50["value"] == "20"                                      # integer lower-median of [10,20,30,40]


def test_hist_over_verdict_class():
    rows = [_row(field="verdict_class", value=v) for v in (1, 1, 2, 3, 1)]
    r = aggregate(rows, op="hist", field_id="verdict_class", requested_category="MARKETPLACE")
    assert r["statistic"]["payload"]["bins"] == {"1": 3, "2": 1, "3": 1}


def test_triple_shape_and_commitment_set():
    rows = [_row(value=v) for v in (5, 15)]
    t = aggregate(rows, op="sum", field_id="session_tick_count", requested_category="MARKETPLACE",
                  wasm_sha256="de" * 32)
    assert set(t) >= {"statistic", "input_commitment_set", "applet_version", "ceiling"}
    cs = t["input_commitment_set"]
    assert cs["algo"] == "sha256-sorted-leaf-merkle-v0" and cs["n"] == 2 and len(cs["root"]) == 64
    # leaves are the row commitments, emitted SORTED so the buyer re-derives the root without guessing order
    assert cs["leaves"] == sorted(row_commitment(r) for r in rows)
    assert t["applet_version"]["crate"] == "w3bstream_applet"


def test_aggregate_fails_closed_on_unconsented_field_selection():
    rows = [_row(field="session_tick_count", consent=1 << 1)]   # RESEARCH only, request MARKETPLACE
    with pytest.raises(ConsentError):
        aggregate(rows, op="sum", field_id="session_tick_count", requested_category="MARKETPLACE")
