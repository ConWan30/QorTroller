"""UC-15 self-analytics tests.

Pins: the SELF-VIEW ceiling banner renders verbatim · citation footer carries both refs
(path+sha256) + re-verify commands · adversarial session names are HTML-escaped · SVG bars
count = sessions · the self-view guard refuses comparison-shaped inputs · totals surface.
"""
from __future__ import annotations

from l9_presence.self_analytics import (CEILING_BANNER, build_self_analytics_html,
                                        validate_self_view)

_RESUME = {
    "schema": "qortroller-play-resume-v0", "handle": "P1",
    "totals": {"sessions": 2, "posp_synchronized": 1, "authored_kills_live": 11,
               "authored_kills_deferred": 2, "authored_kills_best": 13},
    "sessions": [
        {"session": "m1", "kas": {"verdict": "AUTHORED_SESSION", "authored_kills": 11},
         "posp": {"verdict": "SYNCHRONIZED"}},
        {"session": "m2", "kas": {"verdict": "INSUFFICIENT_KILLS", "authored_kills": 0},
         "deferred": {"verdict": "DEFERRED_AUTHORED_SESSION", "deferred_authored": 2}},
    ],
}
_STRATA = {
    "schema": "qortroller-skill-strata-v0",
    "distribution": {"AUTHORED_HIGH_DENSITY": 1, "AUTHORED_DEFERRED": 1},
    "corpus_eligible_sessions": 2,
    "sessions": [{"session": "m1", "band": "AUTHORED_HIGH_DENSITY", "density_kpm": 1.1},
                 {"session": "m2", "band": "AUTHORED_DEFERRED", "density_kpm": None}],
}
_REFS = {"resume_ref": {"path": "audits/r.json", "sha256": "aa" * 32},
         "strata_ref": {"path": "audits/s.json", "sha256": "bb" * 32}}


def _render(resume=_RESUME, strata=_STRATA):
    return build_self_analytics_html(resume, strata, **_REFS, generated_at="2026-07-11")


def test_ceiling_banner_verbatim():
    page = _render()
    assert CEILING_BANNER in page                       # the self-view rail is VISIBLE
    assert "SELF-VIEW ONLY" in page and "no rank claims" in CEILING_BANNER


def test_citation_footer_refs_and_commands():
    page = _render()
    assert "aa" * 32 in page and "bb" * 32 in page      # both shas cited
    assert "build_play_resume.py verify" in page
    assert "build_skill_strata.py verify" in page


def test_adversarial_session_name_escaped():
    resume = dict(_RESUME)
    resume["sessions"] = [{"session": "<script>alert(1)</script>",
                           "kas": {"verdict": "AUTHORED_SESSION", "authored_kills": 1}}]
    page = build_self_analytics_html(resume, {"distribution": {}, "sessions": [],
                                              "corpus_eligible_sessions": 0},
                                     **_REFS, generated_at="x")
    assert "<script>alert(1)</script>" not in page      # escaped, never active markup
    assert "&lt;script&gt;" in page


def test_svg_bars_one_per_session():
    page = _render()
    assert page.count("<rect ") == len(_RESUME["sessions"])


def test_totals_surface():
    page = _render()
    for v in ("11", "13", "authored — best", "corpus-eligible"):
        assert v in page


def test_self_view_guard_refuses_comparison_inputs():
    assert validate_self_view(_RESUME) is None
    assert validate_self_view({**_RESUME, "leaderboard": []}) is not None
    assert validate_self_view({**_RESUME, "percentile": 99}) is not None
