"""(ii) R2-onset — unit tests for the offline coupling study analyzer (F-R2ONSET-1 honest-t0).

analyze_fire must: recover the fire instant t0 in device space by mono-extrapolation from the last
pre-frame (clamped into [anchor, post0]); report the FULL [lat_lo, lat_pt, lat_hi] uncertainty interval;
REJECT stale/large-reference-gap fires (the 20s rapid-fire artifacts) via the plausibility bound; and fall
back honestly to stale_pre when the monotonic anchor is absent. No bridge, no corpus, no presence claim.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from poep_ring_coupling_study import analyze_fire, GAP_REPORT_MS  # noqa: E402

_A = 1_000_000    # anchor device_ts
_TPMS = 3000


def _f(r2, dev, tmono=None):
    d = {"r2": r2, "device_ts": dev}
    if tmono is not None:
        d["t_mono"] = tmono
    return d


def _rec(post, probe_mono=100.02, hold=15):
    r = {
        "schema": "qortroller-poep-ring-dump-v0", "nonce": "t", "probe_hold_ms": hold,
        "probe_device_ts": _A, "device_ticks_per_ms": _TPMS,
        "pre_series": [_f(0, _A - 6000, 99.98), _f(0, _A - 3000, 99.99), _f(0, _A, 100.0)],
        "post_series": post,
    }
    if probe_mono is not None:
        r["probe_ts_mono"] = probe_mono
    return r


def test_mono_extrap_t0_with_uncertainty_interval():
    # fire 20ms after the anchor's t_mono -> mono_extrap t0; onset ~200ms in the post window.
    post = [_f(0, _A + 65_000, 100.05),                          # actuator-window frame, no R2 move
            _f(60, _A + 660_000, 100.30), _f(66, _A + 663_000, 100.301), _f(70, _A + 666_000, 100.302)]
    out = analyze_fire(_rec(post))
    assert out["t0_method"] == "mono_extrap"
    assert out["plausible"] is True
    # the honest ordering: lat_lo <= lat_pt <= lat_hi (t0 in [anchor, post0])
    assert out["lat_lo_ms"] <= out["lat_pt_ms"] <= out["lat_hi_ms"]
    assert out["reference_gap_ms"] is not None and out["reference_gap_ms"] < GAP_REPORT_MS
    assert out["max_dR2_post"] >= 60.0                           # the R2 reaction is in the post window


def test_large_reference_gap_fire_is_rejected():
    # a rapid-fire artifact: post frames far from the (stale, frozen) anchor -> huge reference gap.
    # R2 still moves, but the fire MUST be implausible (this is the 20s-artifact rejection).
    post = [_f(0, _A + 18_000_000, 106.0),                       # ~6000ms reference gap
            _f(60, _A + 18_600_000, 106.2), _f(66, _A + 18_603_000, 106.201), _f(70, _A + 18_606_000, 106.202)]
    out = analyze_fire(_rec(post))
    assert out["reference_gap_ms"] > GAP_REPORT_MS
    assert out["plausible"] is False                            # large gap -> not trustworthy -> rejected


def test_no_onset_when_r2_stays_quiet():
    post = [_f(0, _A + 65_000, 100.05), _f(0, _A + 660_000, 100.30), _f(1, _A + 663_000, 100.301)]
    out = analyze_fire(_rec(post))
    assert out["gated_onset_ms"] is None and out["plausible"] is False


def test_stale_pre_fallback_when_no_monotonic_anchor():
    # dumps lacking probe_ts_mono resolve t0 = anchor device_ts, method stale_pre (honest, not silent).
    post = [_f(60, _A + 660_000, 100.30), _f(66, _A + 663_000, 100.301), _f(70, _A + 666_000, 100.302)]
    out = analyze_fire(_rec(post, probe_mono=None))
    assert out["t0_method"] == "stale_pre"
    assert out["lat_lo_ms"] <= out["lat_pt_ms"] <= out["lat_hi_ms"]


def test_handles_missing_device_ts_frames():
    post = [{"r2": 90}, {"r2": 90}, _f(90, _A + 660_000, 100.30)]   # first two lack device_ts
    out = analyze_fire(_rec(post))
    assert out["n_post_with_dev_ts"] == 1


def test_read_at_fire_gold_t0_gives_tight_interval():
    # C read-at-fire: a fresh drain tick just BEFORE post0 -> method read_at_fire + a TIGHT uncertainty
    # interval (vs the wide mono-extrap gap). post0 = _A+65000; t0_read = _A+63000 (0.67ms before post0).
    post = [_f(0, _A + 65_000, 100.05),
            _f(60, _A + 660_000, 100.30), _f(66, _A + 663_000, 100.301), _f(70, _A + 666_000, 100.302)]
    rec = _rec(post)
    rec["t0_read_device_ts"] = _A + 63_000
    out = analyze_fire(rec)
    assert out["t0_method"] == "read_at_fire"
    assert out["plausible"] is True
    assert out["reference_gap_ms"] < 5.0                        # gold read -> tight t0 uncertainty
    assert out["lat_hi_ms"] - out["lat_lo_ms"] < 5.0           # tight [lo, hi] interval
    assert out["lat_lo_ms"] <= out["lat_pt_ms"] <= out["lat_hi_ms"]


def test_read_at_fire_accepts_fresh_tick_beyond_stale_post0():
    # LIVE RP regime (grok C-verify): post0 is a stale BUFFERED sample (sampled before the fire, delivered
    # late in a burst); the drain read-at-fire tick is FRESHER and EXCEEDS post0. Must still resolve
    # read_at_fire (the window must NOT require t0_read <= post0).
    post = [_f(0, _A + 65_000, 100.05),                  # stale-buffered pre-fire sample (before t0_read)
            _f(60, _A + 800_000, 100.40), _f(66, _A + 803_000, 100.401), _f(70, _A + 806_000, 100.402)]
    rec = _rec(post)
    rec["t0_read_device_ts"] = _A + 200_000              # fresh drain tick AFTER post0 (_A+65000)
    out = analyze_fire(rec)
    assert out["t0_method"] == "read_at_fire"
    assert out["plausible"] is True
    assert out["lat_lo_ms"] <= out["lat_pt_ms"] <= out["lat_hi_ms"]
    assert out["reference_gap_ms"] < 5.0                # tight (one drain interval), not the pre->post gap


def test_read_at_fire_ignored_when_wildly_out_of_window():
    # a garbage/zero read tick must NOT be trusted -> fall back to mono_extrap (honest).
    post = [_f(60, _A + 660_000, 100.30), _f(66, _A + 663_000, 100.301), _f(70, _A + 666_000, 100.302)]
    rec = _rec(post)
    rec["t0_read_device_ts"] = _A + 999_999_999          # far outside [anchor, post0] window
    out = analyze_fire(rec)
    assert out["t0_method"] == "mono_extrap"
