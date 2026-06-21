"""Tests for the presence<->retina binding correlator (pure logic, no DB)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from l9_presence.adversarial.cocapture_binding import (  # noqa: E402
    BindingMode,
    ProbeRow,
    RetinaRow,
    correlate,
)
from l9_presence.presence_retina_consistency import DEFAULT_WINDOW_NS  # noqa: E402

DEV = "a" * 64
S = 1_000_000_000  # 1 second in ns


def _probe(ts_s, cls="HUMAN", lat=300.0, rh=None):
    return ProbeRow(device_id=DEV, ts_ns=int(ts_s * S), classification=cls,
                    latency_ms=lat, record_hash=rh)


def _retina(ts_s, rh="deadbeef" * 8, dev=DEV, anomaly=10):
    return RetinaRow(device_id=dev, ts_ns=int(ts_s * S), record_hash=rh, anomaly_count=anomaly)


def test_temporal_pair_within_window():
    rep = correlate([_probe(100.0)], [_retina(100.5)])
    p = rep.pairs[0]
    assert p.bound and p.mode is BindingMode.TEMPORAL_PROTOTYPE
    assert p.cryptographically_bound is False
    assert p.offset_ns == int(0.5 * S)
    assert rep.coverage() == 1.0 and rep.crypto_coverage() == 0.0


def test_outside_window_is_unbound():
    # retina 3 s away, window is 2 s -> unbound
    rep = correlate([_probe(100.0)], [_retina(103.0)])
    p = rep.pairs[0]
    assert not p.bound and p.mode is BindingMode.UNBOUND
    assert p.anchor_record_hash is None
    assert rep.coverage() == 0.0


def test_nearest_of_several_wins():
    rep = correlate([_probe(100.0)],
                    [_retina(101.5, rh="far"), _retina(100.2, rh="near"), _retina(98.6, rh="mid")])
    p = rep.pairs[0]
    assert p.retina.record_hash == "near"
    assert abs(p.offset_ns) == int(0.2 * S)


def test_device_mismatch_never_binds():
    rep = correlate([_probe(100.0)], [_retina(100.1, dev="b" * 64)])
    assert not rep.pairs[0].bound


def test_record_hash_production_binds_regardless_of_time():
    # probe stamped with a record_hash; the matching retina row is 10 s away (far outside
    # the temporal window) yet binds cryptographically because the anchor is shared.
    rh = "cafef00d" * 8
    rep = correlate([_probe(100.0, rh=rh)], [_retina(110.0, rh=rh)])
    p = rep.pairs[0]
    assert p.mode is BindingMode.RECORD_HASH_PRODUCTION
    assert p.cryptographically_bound is True
    assert p.anchor_record_hash == rh
    assert rep.crypto_coverage() == 1.0
    assert rep.to_dict()["binding_is_cryptographic"] is True


def test_crypto_preferred_over_temporal():
    # an in-window temporal candidate exists, but a hash-matching row should win
    rh = "1234abcd" * 8
    rep = correlate([_probe(100.0, rh=rh)],
                    [_retina(100.1, rh="other"), _retina(105.0, rh=rh)])
    p = rep.pairs[0]
    assert p.cryptographically_bound is True and p.retina.ts_ns == int(105.0 * S)


def test_human_coverage_math():
    rep = correlate(
        [_probe(100.0, "HUMAN"), _probe(200.0, "HUMAN"), _probe(300.0, "NO_RESPONSE")],
        [_retina(100.1), _retina(300.1)],  # HUMAN@100 bound, HUMAN@200 unbound, NR@300 bound
    )
    assert rep.n_human == 2 and rep.n_human_bound == 1
    assert rep.human_coverage() == 0.5
    assert rep.coverage() == 2 / 3


def test_crypto_coverage_zero_without_probe_hash():
    # current real-data shape: probes carry NO record_hash -> 0% cryptographic
    rep = correlate([_probe(100.0), _probe(200.0)], [_retina(100.1), _retina(200.1)])
    assert rep.coverage() == 1.0
    assert rep.crypto_coverage() == 0.0
    assert rep.to_dict()["binding_is_cryptographic"] is False


def test_markdown_carries_honesty_banner():
    md = correlate([_probe(100.0)], [_retina(100.1)]).to_markdown()
    assert "TEMPORAL CORRELATION (prototype)" in md
    assert "NOT a cryptographic proof" in md
    assert "record_hash" in md


def test_markdown_production_banner_when_all_crypto():
    rh = "ffeeddcc" * 8
    md = correlate([_probe(100.0, rh=rh)], [_retina(100.0, rh=rh)]).to_markdown()
    assert "CRYPTOGRAPHIC BINDING (production)" in md


def test_empty_inputs_fail_open():
    rep = correlate([], [])
    assert rep.n_probes == 0 and rep.coverage() == 0.0
    assert rep.to_dict()["binding_is_cryptographic"] is False
    assert rep.offset_stats_ms()["n"] == 0
    # render must not raise on empty
    assert "Binding Report" in rep.to_markdown()


def test_window_is_engine_default():
    # the join window is the SAME 2.0 s the engine's check_binding enforces
    rep = correlate([_probe(100.0)], [_retina(101.99)])
    assert rep.window_ns == DEFAULT_WINDOW_NS
    assert rep.pairs[0].bound  # 1.99 s < 2.0 s
    rep2 = correlate([_probe(100.0)], [_retina(102.01)])
    assert not rep2.pairs[0].bound  # 2.01 s > 2.0 s


def test_offset_stats_ms():
    rep = correlate(
        [_probe(100.0), _probe(200.0), _probe(300.0)],
        [_retina(100.1), _retina(200.5), _retina(300.9)],  # offsets 100, 500, 900 ms
    )
    st = rep.offset_stats_ms()
    assert st["n"] == 3 and st["min_ms"] == 100.0 and st["median_ms"] == 500.0 and st["max_ms"] == 900.0
