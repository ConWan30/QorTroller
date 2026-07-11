"""RP-2d deferred-attestation tier tests.

Pins: the verdict matrix (AUTHORED needs K-floor + window overlap; OBSERVED = K-floor
without overlap); window-edge overlap; sha-mismatch anti-tamper poison; session-id
anti-assertion; empty-windows honesty; K floor; min_kills boundary; hygiene inheritance;
the never-live-verdict-string rail; verifier round-trip.
"""
from __future__ import annotations

import os

from l9_presence.kas_deferred import (
    DEFERRED_AUTHORED,
    DEFERRED_AUTHORED_SESSION,
    DEFERRED_OBSERVED,
    DEFERRED_OBSERVED_ONLY,
    UNVERIFIABLE,
    build_deferred_record,
    verify_deferred_record,
)

_SID = "a" * 64
_DISPLAY = "match_test_1000"


def _reads(t0_ms: float, n: int, prefix="c"):
    """n reads spaced 1s apart starting at t0_ms (wall ms) -> ts_ns."""
    return [{"file": f"{prefix}{i}.png", "ts_ns": int((t0_ms + i * 1000) * 1e6),
             "sha256": f"sha_{prefix}{i}", "text": "Qortrola30", "conf": 0.9,
             "slot": "killer"} for i in range(n)]


def _cluster(t0_ms: float, n: int, prefix="c"):
    rd = _reads(t0_ms, n, prefix)
    return {"size": n, "span_ms": (n - 1) * 1000.0,
            "texts": [r["text"] for r in rd], "reads": rd}


def _manifest(clusters):
    files = [{"file": r["file"], "sha256": r["sha256"]}
             for c in clusters for r in c["reads"]]
    return {"schema": "qortroller-session-archive-v1", "session_id": _SID,
            "session_display": _DISPLAY, "count": len(files), "files": files}


def _scan(clusters):
    return {"scan_version": "rp-ocr-precision-v2",
            "archive": f"retina_kf_archive/{_DISPLAY}",
            "engine": "v6-only (ENGINE_V6)", "clusters": clusters}


def _kas(verdict="INSUFFICIENT_KILLS", sid=_SID):
    return {"verdict": verdict, "commitment": "fb" * 32, "session_id": sid,
            "hygiene": {"frame_errs": 0, "frame_stall_s": 0.0, "ts_source": "timespan"}}


def test_authored_session_happy_path():
    """Two K=3 clusters inside windows -> DEFERRED_AUTHORED_SESSION."""
    cl = [_cluster(1000.0, 3, "a"), _cluster(60000.0, 3, "b")]
    r = build_deferred_record(scan=_scan(cl), manifest=_manifest(cl),
                              windows=[(500.0, 4000.0), (59000.0, 65000.0)],
                              kas_record=_kas())
    assert r.verdict == DEFERRED_AUTHORED_SESSION
    assert r.deferred_authored == 2 and r.deferred_observed == 0
    assert r.clusters[0]["verdict"] == DEFERRED_AUTHORED
    assert r.source_kas_commitment == "fb" * 32
    assert r.advisory is True


def test_no_window_overlap_is_observed():
    """K=3 cluster far from any window -> DEFERRED_OBSERVED, session OBSERVED_ONLY."""
    cl = [_cluster(100000.0, 3)]
    r = build_deferred_record(scan=_scan(cl), manifest=_manifest(cl),
                              windows=[(500.0, 4000.0)], kas_record=_kas())
    assert r.verdict == DEFERRED_OBSERVED_ONLY
    assert r.clusters[0]["verdict"] == DEFERRED_OBSERVED
    assert r.clusters[0]["window_hit_ms"] is None


def test_window_edge_overlap_counts():
    """A cluster whose span merely TOUCHES a window edge counts as overlap."""
    cl = [_cluster(4000.0, 3)]                       # span [4000, 6000]
    r = build_deferred_record(scan=_scan(cl), manifest=_manifest(cl),
                              windows=[(1000.0, 4000.0), (99000.0, 99500.0)],
                              kas_record=_kas(), min_kills=1)
    assert r.clusters[0]["verdict"] == DEFERRED_AUTHORED
    assert r.verdict == DEFERRED_AUTHORED_SESSION


def test_below_k_floor_never_attested():
    """Size-2 clusters are un-promotable regardless of window overlap."""
    cl = [_cluster(1000.0, 2)]
    r = build_deferred_record(scan=_scan(cl), manifest=_manifest(cl),
                              windows=[(500.0, 4000.0)], kas_record=_kas())
    assert r.verdict == UNVERIFIABLE          # no K-floor clusters at all
    assert r.unpromotable_clusters == 1
    assert r.clusters[0]["verdict"] is None


def test_min_kills_boundary():
    """One authored cluster < min_kills=2 -> OBSERVED_ONLY with an honest note."""
    cl = [_cluster(1000.0, 3)]
    r = build_deferred_record(scan=_scan(cl), manifest=_manifest(cl),
                              windows=[(500.0, 4000.0)], kas_record=_kas())
    assert r.deferred_authored == 1
    assert r.verdict == DEFERRED_OBSERVED_ONLY
    assert any("below min_kills" in n for n in r.notes)


def test_empty_windows_all_observed():
    """No live windows supplied -> honest: conjunction cannot be established."""
    cl = [_cluster(1000.0, 3)]
    r = build_deferred_record(scan=_scan(cl), manifest=_manifest(cl), windows=[],
                              kas_record=_kas())
    assert r.clusters[0]["verdict"] == DEFERRED_OBSERVED
    assert any("no live R2 windows" in n for n in r.notes)


def test_sha_mismatch_poisons_to_unverifiable():
    """Anti-tamper: a cluster crop whose sha is not in the manifest fails the RECORD."""
    cl = [_cluster(1000.0, 3)]
    man = _manifest(cl)
    man["files"][1]["sha256"] = "tampered"
    r = build_deferred_record(scan=_scan(cl), manifest=man,
                              windows=[(500.0, 4000.0)], kas_record=_kas())
    assert r.verdict == UNVERIFIABLE
    assert any("anti-tamper" in n for n in r.notes)


def test_kas_session_id_mismatch_is_unverifiable():
    cl = [_cluster(1000.0, 3)]
    r = build_deferred_record(scan=_scan(cl), manifest=_manifest(cl),
                              windows=[(500.0, 4000.0)],
                              kas_record=_kas(sid="b" * 64))
    assert r.verdict == UNVERIFIABLE
    assert any("anti-assertion" in n for n in r.notes)


def test_hygiene_fail_inherited():
    """A HYGIENE_FAIL live KAS forbids any deferred claim over the same capture."""
    cl = [_cluster(1000.0, 3)]
    r = build_deferred_record(scan=_scan(cl), manifest=_manifest(cl),
                              windows=[(500.0, 4000.0)],
                              kas_record=_kas(verdict="HYGIENE_FAIL"))
    assert r.verdict == UNVERIFIABLE


def test_v1_scan_rejected():
    """Per-read provenance (v2) is REQUIRED -- a v1 scan cannot join windows/manifest."""
    cl = [_cluster(1000.0, 3)]
    scan = _scan(cl)
    scan["scan_version"] = "rp-ocr-precision-v1"
    r = build_deferred_record(scan=scan, manifest=_manifest(cl),
                              windows=[(500.0, 4000.0)], kas_record=_kas())
    assert r.verdict == UNVERIFIABLE


def test_never_live_verdict_string():
    """The live 'AUTHORED_SESSION' string must never appear as a deferred verdict."""
    cl = [_cluster(1000.0, 3, "a"), _cluster(60000.0, 3, "b")]
    r = build_deferred_record(scan=_scan(cl), manifest=_manifest(cl),
                              windows=[(500.0, 4000.0), (59000.0, 65000.0)],
                              kas_record=_kas())
    assert r.verdict != "AUTHORED_SESSION"
    assert "DEFERRED" in r.verdict
    for c in r.clusters:
        assert c.get("verdict") != "AUTHORED_SESSION"


def test_verifier_round_trip(tmp_path):
    """verify_deferred_record: re-hash crops on disk + recount + arithmetic."""
    import hashlib
    cl = [_cluster(1000.0, 3, "a"), _cluster(60000.0, 3, "b")]
    # write real crop bytes and use their REAL hashes
    man_files = []
    for c in cl:
        for r in c["reads"]:
            p = tmp_path / r["file"]
            p.write_bytes(f"crop-{r['file']}".encode())
            r["sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
            man_files.append({"file": r["file"], "sha256": r["sha256"]})
    man = {"schema": "qortroller-session-archive-v1", "session_id": _SID,
           "session_display": _DISPLAY, "count": len(man_files), "files": man_files}
    rec = build_deferred_record(scan=_scan(cl), manifest=man,
                                windows=[(500.0, 4000.0), (59000.0, 65000.0)],
                                kas_record=_kas())
    assert rec.verdict == DEFERRED_AUTHORED_SESSION
    v = verify_deferred_record(rec.to_dict(), man, str(tmp_path))
    assert v["ok"], [c for c in v["checks"] if not c["ok"]]
    # tamper one crop on disk -> verifier must fail
    (tmp_path / "a1.png").write_bytes(b"tampered bytes")
    v2 = verify_deferred_record(rec.to_dict(), man, str(tmp_path))
    assert not v2["ok"]


def test_slice_scan_by_spans():
    """LUMEN-2 x RP-2d composition: clusters split by match span; outsiders honest."""
    from l9_presence.kas_deferred import slice_scan_by_spans
    cl_m1 = _cluster(10_000.0, 3, "m1")            # midpoint ~11s
    cl_m2 = _cluster(500_000.0, 3, "m2")           # midpoint ~501s
    cl_out = _cluster(900_000.0, 1, "px")          # post-match sighting
    scan = _scan([cl_m1, cl_m2, cl_out])
    parts = slice_scan_by_spans(scan, [(0.0, 100_000.0), (400_000.0, 600_000.0)])
    assert len(parts) == 3
    assert parts[0]["scan"]["clusters"] == [cl_m1]
    assert parts[1]["scan"]["clusters"] == [cl_m2]
    assert parts[2]["span_ms"] is None and parts[2]["scan"]["clusters"] == [cl_out]
    assert parts[0]["scan"]["scan_version"] == "rp-ocr-precision-v2"


def test_slice_empty_spans_all_unassigned():
    from l9_presence.kas_deferred import slice_scan_by_spans
    scan = _scan([_cluster(10_000.0, 3)])
    parts = slice_scan_by_spans(scan, [])
    assert len(parts) == 1 and parts[0]["span_ms"] is None
    assert len(parts[0]["scan"]["clusters"]) == 1


# ==================================================================================================
# Arc A — forward window-latency pad (RP fire->kill lag recovery) + G-VERIFY
# ==================================================================================================

def _real_crop_manifest(tmp_path, cl):
    """Write real crop bytes to tmp_path, set the reads' REAL sha256, return the manifest (so the
    verifier's on-disk re-hash passes). Mirrors test_verifier_round_trip."""
    import hashlib
    files = []
    for c in cl:
        for r in c["reads"]:
            p = tmp_path / r["file"]
            p.write_bytes(f"crop-{r['file']}".encode())
            r["sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
            files.append({"file": r["file"], "sha256": r["sha256"]})
    return {"schema": "qortroller-session-archive-v1", "session_id": _SID,
            "session_display": _DISPLAY, "count": len(files), "files": files}


def test_t1_pad0_lag_demoted_stays_observed():
    """T1 — pad=0 is byte-identical: a kill first appearing after the window end stays OBSERVED."""
    cl = [_cluster(5000.0, 3)]                                  # span[0]=5000, window ends 4000
    r = build_deferred_record(scan=_scan(cl), manifest=_manifest(cl),
                              windows=[(500.0, 4000.0)], kas_record=_kas(),
                              window_latency_pad_ms=0.0)
    assert r.clusters[0]["verdict"] == DEFERRED_OBSERVED
    assert r.window_latency_pad_ms == 0.0


def test_t2_pad_recovers_lag_demoted_kill():
    """T2 — pad>0: kill with span[0] within [w0, w1+pad] -> AUTHORED (the recovery)."""
    cl = [_cluster(5000.0, 3)]                                  # 500 <= 5000 <= 4000+4000
    r = build_deferred_record(scan=_scan(cl), manifest=_manifest(cl),
                              windows=[(500.0, 4000.0)], kas_record=_kas(),
                              window_latency_pad_ms=4000.0)
    assert r.clusters[0]["verdict"] == DEFERRED_AUTHORED
    assert r.window_latency_pad_ms == 4000.0
    assert any("window_latency_pad_ms=4000" in n for n in r.notes)


def test_t3_pre_fire_kill_never_attributes():
    """T3 — forward-only: a kill first appearing BEFORE the fire window (span[0] < w0) stays
    OBSERVED even with a pad (no backward attribution by lingering)."""
    cl = [_cluster(100.0, 3)]                                   # span[0]=100 < window start 500
    r = build_deferred_record(scan=_scan(cl), manifest=_manifest(cl),
                              windows=[(500.0, 4000.0)], kas_record=_kas(),
                              window_latency_pad_ms=4000.0)
    assert r.clusters[0]["verdict"] == DEFERRED_OBSERVED


def test_t4_pad_empty_windows_zero_authored():
    """T4 — input-required: pad>0 with NO windows -> 0 AUTHORED (pad extends windows, never creates)."""
    cl = [_cluster(5000.0, 3)]
    r = build_deferred_record(scan=_scan(cl), manifest=_manifest(cl),
                              windows=[], kas_record=_kas(), window_latency_pad_ms=4000.0)
    assert r.deferred_authored == 0 and r.clusters[0]["verdict"] == DEFERRED_OBSERVED


def test_t5_no_onset_session_zero_authored_at_pad():
    """T5 — anti-cheat guard: a full K-floor session with no R2 onsets (no windows) stays 0 authored
    at pad=4000. Input is REQUIRED; the pad cannot manufacture authorship."""
    cl = [_cluster(5000.0, 3, "a"), _cluster(20000.0, 3, "b"), _cluster(40000.0, 3, "c")]
    r = build_deferred_record(scan=_scan(cl), manifest=_manifest(cl),
                              windows=[], kas_record=_kas(), window_latency_pad_ms=4000.0)
    assert r.deferred_authored == 0 and r.verdict == DEFERRED_OBSERVED_ONLY


def test_t6_window_hit_forward_only_math():
    """T6 — unit on _window_hit: only the END is extended; span[0] before w0 never hits."""
    from l9_presence.kas_deferred import _window_hit
    win = [(500.0, 4000.0)]
    assert _window_hit((5000.0, 7000.0), win, 0.0) is None                 # pad=0 no overlap
    assert _window_hit((1000.0, 3000.0), win, 0.0) == [500.0, 4000.0]      # pad=0 overlap
    assert _window_hit((5000.0, 7000.0), win, 4000.0) == [500.0, 4000.0]   # span0 within w1+pad
    assert _window_hit((8001.0, 9000.0), win, 4000.0) is None              # span0 beyond w1+pad
    assert _window_hit((100.0, 2000.0), win, 4000.0) is None               # span0 < w0 (pre-fire)
    assert _window_hit((5000.0, 7000.0), [], 4000.0) is None               # empty windows


def test_t7_gverify_padded_record_verifies(tmp_path):
    """T7 — G-VERIFY: a pad=4000 record with recovered AUTHORED clusters passes its own verifier
    (the verifier re-derives the padded conjunction from span_ms + window_hit_ms + the stored pad)."""
    cl = [_cluster(5000.0, 3, "a"), _cluster(6000.0, 3, "b")]   # both lag-demoted, recovered at pad
    man = _real_crop_manifest(tmp_path, cl)
    rec = build_deferred_record(scan=_scan(cl), manifest=man,
                                windows=[(500.0, 4000.0)], kas_record=_kas(),
                                window_latency_pad_ms=4000.0)
    assert rec.verdict == DEFERRED_AUTHORED_SESSION and rec.deferred_authored == 2
    v = verify_deferred_record(rec.to_dict(), man, str(tmp_path))
    assert v["ok"], [c for c in v["checks"] if not c["ok"]]
    assert any(c["name"] == "authored_conjunction" for c in v["checks"])   # re-derivation ran


def test_t8_gverify_stripped_pad_fails(tmp_path):
    """T8 — G-VERIFY load-bearing: strip/zero the pad on a padded record -> the AUTHORED clusters no
    longer re-derive (span[0] beyond the unpadded window) -> verify FAILS. Padded authorship without
    the verifier re-applying the pad is not a result."""
    cl = [_cluster(5000.0, 3, "a"), _cluster(6000.0, 3, "b")]
    man = _real_crop_manifest(tmp_path, cl)
    rec = build_deferred_record(scan=_scan(cl), manifest=man,
                                windows=[(500.0, 4000.0)], kas_record=_kas(),
                                window_latency_pad_ms=4000.0)
    d = rec.to_dict()
    d["window_latency_pad_ms"] = 0.0                            # STRIP the pad
    v = verify_deferred_record(d, man, str(tmp_path))
    assert not v["ok"]
    assert any(c["name"] == "authored_conjunction" and not c["ok"] for c in v["checks"])
