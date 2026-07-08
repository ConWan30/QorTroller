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
