"""UC-2 skill-strata tests.

Pins: deterministic band rules (first-match-wins; every band reachable) · density math + the
provisional threshold boundary · the NO-RANK rail (ceiling verbatim incl. strata_semantics;
wmp_metadata carries the session-not-player string) · re-derivation verifier fail-closed on
resume tamper AND on label tamper · custom threshold honored end-to-end via the methodology
block · EXCLUDED/UNGRADED never corpus-eligible.
"""
from __future__ import annotations

import json

import pytest

from l9_presence.play_resume import sha256_bytes
from l9_presence.skill_strata import (BANDS, CEILING, SCHEMA, band_for_row,
                                      build_strata_report, verify_strata_report, wmp_metadata)

_MIN10 = [0, 600_000]          # 10-minute span


def _row(kas_v=None, kills=0, deferred_v=None, deferred_n=0, posp_v=None, span=_MIN10):
    r = {"session": "s", "session_id": "sid", "span_ms": span}
    if kas_v is not None:
        r["kas"] = {"verdict": kas_v, "authored_kills": kills}
    if deferred_v is not None:
        r["deferred"] = {"verdict": deferred_v, "deferred_authored": deferred_n}
    if posp_v is not None:
        r["posp"] = {"verdict": posp_v}
    return r


def test_band_rules_first_match_wins():
    assert band_for_row(_row(kas_v="HYGIENE_FAIL", kills=20)) == "EXCLUDED_INTEGRITY"
    assert band_for_row(_row(kas_v="UNVERIFIABLE")) == "EXCLUDED_INTEGRITY"
    assert band_for_row(_row(kas_v="AUTHORED_SESSION", kills=14)) == "AUTHORED_HIGH_DENSITY"  # 1.4 kpm
    assert band_for_row(_row(kas_v="AUTHORED_SESSION", kills=5)) == "AUTHORED_STANDARD"       # 0.5 kpm
    assert band_for_row(_row(kas_v="INSUFFICIENT_KILLS",
                             deferred_v="DEFERRED_AUTHORED_SESSION",
                             deferred_n=2)) == "AUTHORED_DEFERRED"
    assert band_for_row(_row(kas_v="INSUFFICIENT_KILLS", posp_v="SYNCHRONIZED")) == "PRESENCE_ONLY"
    assert band_for_row(_row(kas_v="INSUFFICIENT_KILLS")) == "UNGRADED"
    assert set(BANDS) >= {band_for_row(_row(kas_v="HYGIENE_FAIL")),
                          band_for_row(_row(kas_v="AUTHORED_SESSION", kills=14))}


def test_density_boundary_and_missing_span():
    assert band_for_row(_row(kas_v="AUTHORED_SESSION", kills=8)) == "AUTHORED_HIGH_DENSITY"   # 0.8 exact
    assert band_for_row(_row(kas_v="AUTHORED_SESSION", kills=14, span=None)) == "AUTHORED_STANDARD"
    assert band_for_row(_row(kas_v="AUTHORED_SESSION", kills=14, span=[5, 5])) == "AUTHORED_STANDARD"


def test_no_rank_rail_ceiling_and_metadata():
    rep = build_strata_report({"schema": "qortroller-play-resume-v0", "sessions": []})
    assert rep["ceiling"] == CEILING
    assert "never player rank" in rep["ceiling"]["strata_semantics"]
    md = wmp_metadata("AUTHORED_STANDARD")
    assert md["skill_strata_schema"] == SCHEMA
    assert "not player rank" in md["skill_strata_semantics"]
    with pytest.raises(ValueError):
        wmp_metadata("GRANDMASTER")                        # rank-shaped bands cannot exist


def test_distribution_and_corpus_eligibility():
    resume = {"schema": "qortroller-play-resume-v0",
              "sessions": [_row(kas_v="AUTHORED_SESSION", kills=14),
                           _row(kas_v="HYGIENE_FAIL"),
                           _row(kas_v="INSUFFICIENT_KILLS", posp_v="SYNCHRONIZED"),
                           _row(kas_v="INSUFFICIENT_KILLS")]}
    rep = build_strata_report(resume)
    assert rep["distribution"]["AUTHORED_HIGH_DENSITY"] == 1
    assert rep["distribution"]["EXCLUDED_INTEGRITY"] == 1
    assert rep["distribution"]["PRESENCE_ONLY"] == 1
    assert rep["distribution"]["UNGRADED"] == 1
    assert rep["corpus_eligible_sessions"] == 2            # EXCLUDED + UNGRADED never eligible


def _write_resume(tmp_path, sessions):
    resume = {"schema": "qortroller-play-resume-v0", "sessions": sessions}
    p = tmp_path / "resume.json"
    raw = json.dumps(resume).encode()
    p.write_bytes(raw)
    return resume, str(p), sha256_bytes(raw)


def _loader():
    def _load(path):
        try:
            return open(path, "rb").read()
        except OSError:
            return None
    return _load


def test_verify_rederivation_roundtrip(tmp_path):
    resume, path, sha = _write_resume(tmp_path, [_row(kas_v="AUTHORED_SESSION", kills=14)])
    rep = build_strata_report(resume, resume_path=path, resume_sha256=sha)
    v = verify_strata_report(rep, _loader())
    assert v["ok"], [c for c in v["checks"] if not c["ok"]]


def test_verify_fails_on_resume_tamper(tmp_path):
    resume, path, sha = _write_resume(tmp_path, [_row(kas_v="AUTHORED_SESSION", kills=14)])
    rep = build_strata_report(resume, resume_path=path, resume_sha256=sha)
    open(path, "ab").write(b" ")
    v = verify_strata_report(rep, _loader())
    assert not v["ok"]
    assert any(c["name"] == "resume_sha256" and not c["ok"] for c in v["checks"])


def test_verify_fails_on_label_tamper(tmp_path):
    resume, path, sha = _write_resume(tmp_path, [_row(kas_v="INSUFFICIENT_KILLS",
                                                      posp_v="SYNCHRONIZED")])
    rep = build_strata_report(resume, resume_path=path, resume_sha256=sha)
    rep["sessions"][0]["band"] = "AUTHORED_HIGH_DENSITY"   # promote a label dishonestly
    v = verify_strata_report(rep, _loader())
    assert not v["ok"]
    assert any(c["name"] == "rows_rederive" and not c["ok"] for c in v["checks"])


def test_custom_threshold_honored_end_to_end(tmp_path):
    resume, path, sha = _write_resume(tmp_path, [_row(kas_v="AUTHORED_SESSION", kills=5)])
    rep = build_strata_report(resume, resume_path=path, resume_sha256=sha,
                              high_density_kpm=0.4)        # 0.5 kpm clears a 0.4 bar
    assert rep["sessions"][0]["band"] == "AUTHORED_HIGH_DENSITY"
    assert rep["methodology"]["high_density_threshold_kpm"] == 0.4
    v = verify_strata_report(rep, _loader())               # verifier reads threshold from report
    assert v["ok"], [c for c in v["checks"] if not c["ok"]]
