"""UC-4 verified play-resume tests.

Pins: session grouping + per-kind field copy · authored_best = per-session MAX never sum (the
double-count rail) · the CEILING block present verbatim (claim-ceiling rail — advisory, not
population/identity certified, no rank) · verifier fail-closed on tamper / missing cited file /
field drift / totals drift · honest empty resume · pre-U1 session_display fallback · duplicate
source kept-first-with-note. Pure fixtures; no real audits dir required.
"""
from __future__ import annotations

import json

from l9_presence.play_resume import (CEILING, SCHEMA, build_play_resume, sha256_bytes,
                                     verify_play_resume)


def _mk(tmp_path, name, doc):
    p = tmp_path / name
    raw = json.dumps(doc).encode()
    p.write_bytes(raw)
    return {"path": str(p), "sha256": sha256_bytes(raw), "doc": doc}


def _sources(tmp_path):
    kas1 = _mk(tmp_path, "kas1.json", {"session_id": "s1", "session_display": "m1",
                                       "verdict": "AUTHORED_SESSION", "authored_kills": 11,
                                       "own_deaths": 2, "commitment": "c1", "span_ms": [0, 9]})
    kas2 = _mk(tmp_path, "kas2.json", {"session_id": "s2", "session_display": "m2",
                                       "verdict": "INSUFFICIENT_KILLS", "authored_kills": 0,
                                       "own_deaths": 1, "commitment": "c2", "span_ms": [0, 9]})
    def2 = _mk(tmp_path, "def2.json", {"session_id": "s2", "session_display": "m2",
                                       "verdict": "DEFERRED_AUTHORED_SESSION",
                                       "deferred_authored": 2, "window_latency_pad_ms": 4000.0,
                                       "source_kas_commitment": "c2"})
    posp1 = _mk(tmp_path, "posp1.json", {"session_id": "s1", "session_display": "m1",
                                         "verdict": "SYNCHRONIZED"})
    return ([dict(kas1, kind="kas"), dict(kas2, kind="kas"),
             dict(def2, kind="deferred"), dict(posp1, kind="posp")],
            {"kas1": kas1, "kas2": kas2, "def2": def2, "posp1": posp1})


def _loader_for(tmp_path):
    def _load(path):
        try:
            return open(path, "rb").read()
        except OSError:
            return None
    return _load


def test_grouping_totals_and_best_is_max_not_sum(tmp_path):
    srcs, _ = _sources(tmp_path)
    r = build_play_resume(srcs)
    assert r["schema"] == SCHEMA and r["totals"]["sessions"] == 2
    assert r["totals"]["authored_kills_live"] == 11
    assert r["totals"]["authored_kills_deferred"] == 2
    assert r["totals"]["authored_kills_best"] == 13        # 11 + max(0,2) — max per session, not 11+0+2 summed twice
    assert r["totals"]["posp_synchronized"] == 1


def test_ceiling_block_verbatim():
    r = build_play_resume([])
    assert r["ceiling"] == CEILING                          # claim-ceiling rail
    assert r["ceiling"]["advisory"] is True
    assert r["ceiling"]["population_certified"] is False
    assert r["ceiling"]["identity_certified"] is False
    assert "counts and verdicts only" in r["ceiling"]["rank_claim"]


def test_verify_roundtrip_ok(tmp_path):
    srcs, _ = _sources(tmp_path)
    v = verify_play_resume(build_play_resume(srcs), _loader_for(tmp_path))
    assert v["ok"], [c for c in v["checks"] if not c["ok"]]


def test_verify_fails_on_tampered_cited_file(tmp_path):
    srcs, files = _sources(tmp_path)
    r = build_play_resume(srcs)
    open(files["kas1"]["path"], "ab").write(b" ")           # tamper AFTER assembly
    v = verify_play_resume(r, _loader_for(tmp_path))
    assert not v["ok"]
    assert any("sha256" in c["name"] and not c["ok"] for c in v["checks"])


def test_verify_fails_on_missing_cited_file(tmp_path):
    srcs, files = _sources(tmp_path)
    r = build_play_resume(srcs)
    import os
    os.remove(files["def2"]["path"])
    v = verify_play_resume(r, _loader_for(tmp_path))
    assert not v["ok"]                                      # MISSING is never a silent pass
    assert any("ref_present" in c["name"] and not c["ok"] for c in v["checks"])


def test_verify_fails_on_field_drift(tmp_path):
    srcs, _ = _sources(tmp_path)
    r = build_play_resume(srcs)
    r["sessions"][0]["kas"]["authored_kills"] = 99          # resume lies about the cited doc
    v = verify_play_resume(r, _loader_for(tmp_path))
    assert not v["ok"]
    assert any("fields" in c["name"] and not c["ok"] for c in v["checks"])


def test_verify_fails_on_totals_drift(tmp_path):
    srcs, _ = _sources(tmp_path)
    r = build_play_resume(srcs)
    r["totals"]["authored_kills_best"] += 1
    v = verify_play_resume(r, _loader_for(tmp_path))
    assert not v["ok"]


def test_empty_resume_honest_and_verifies():
    r = build_play_resume([])
    assert r["totals"]["sessions"] == 0 and r["sessions"] == []
    v = verify_play_resume(r, lambda p: None)
    assert v["ok"]                                          # empty is honest, not a failure


def test_pre_u1_display_fallback_and_duplicate_note(tmp_path):
    a = _mk(tmp_path, "a.json", {"session_display": "old_match",   # no session_id (pre-U1)
                                 "verdict": "AUTHORED_SESSION", "authored_kills": 3,
                                 "own_deaths": 0, "commitment": "cx", "span_ms": None})
    dup = _mk(tmp_path, "b.json", {"session_display": "old_match",
                                   "verdict": "AUTHORED_SESSION", "authored_kills": 7,
                                   "own_deaths": 0, "commitment": "cy", "span_ms": None})
    r = build_play_resume([dict(a, kind="kas"), dict(dup, kind="kas")])
    assert r["totals"]["sessions"] == 1
    assert r["sessions"][0]["kas"]["authored_kills"] == 3   # first kept
    assert any("duplicate kas" in n for n in r["notes"])    # loud, never silent overwrite
