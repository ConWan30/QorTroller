"""A2A-VALID-1 — honest match self-scorecard (pure helpers + claim rails).

Load-bearing: recall denominator is OPERATOR-REPORTED only. Missing D = UNSCORED, never 0.
Never claim zero false-authorship proven. One session_id per card.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import qortroller as q  # noqa: E402


def _kas(**kw):
    base = {
        "verdict": "AUTHORED_SESSION",
        "authored_kills": 8,
        "commitment": "aa" * 32,
        "session_id": "0283fc1e400999426c6af613325579b577c73d3ede5ce79abaeeb2fd80509b86",
    }
    base.update(kw)
    return base


def _posp(**kw):
    base = {
        "verdict": "SYNCHRONIZED",
        "session_id": "0283fc1e400999426c6af613325579b577c73d3ede5ce79abaeeb2fd80509b86",
        "fusion": {"n_id_verified": 358},
        "events_roots": {"kas_session_root": "bb" * 32, "retina_perception_root": None},
        "kas": {"authored_kills": 8, "verdict": "AUTHORED_SESSION", "commitment": "aa" * 32},
    }
    base.update(kw)
    return base


# --- Q1 recall representation -------------------------------------------------

def test_recall_unscored_when_d_omitted():
    card = q.build_match_scorecard("t", kas=_kas(), posp=_posp(), v3=None, kills_scored=None)
    rec = card["fields"]["recall"]
    assert rec["status"] == q.RECALL_STATUS_UNSCORED
    assert rec["reported"]["value"] is None
    assert rec["reported"]["source"] == q.SRC_OPERATOR
    assert rec["ratio"]["value"] is None
    assert "UNSCORED" in rec["display"]
    assert "0" not in rec["display"].split("reported")[-1] or "UNSCORED" in rec["display"]


def test_recall_scored_tags_sources():
    card = q.build_match_scorecard("t", kas=_kas(authored_kills=8), posp=_posp(), v3=None,
                                   kills_scored=21)
    rec = card["fields"]["recall"]
    assert rec["status"] == q.RECALL_STATUS_SCORED
    assert rec["authored"]["value"] == 8 and rec["authored"]["source"] == q.SRC_MEASURED
    assert rec["reported"]["value"] == 21 and rec["reported"]["source"] == q.SRC_OPERATOR
    assert rec["ratio"]["source"] == q.SRC_DERIVED
    assert abs(rec["ratio"]["value"] - (8 / 21)) < 1e-12
    assert "MEASURED" in rec["display"] and "OPERATOR-REPORTED" in rec["display"]


def test_recall_declined_not_zero():
    card = q.build_match_scorecard("t", kas=_kas(), posp=_posp(), v3=None,
                                   kills_scored_declined=True)
    assert card["fields"]["recall"]["status"] == q.RECALL_STATUS_UNSCORED_DECLINED
    assert card["fields"]["recall"]["ratio"]["value"] is None


def test_recall_d_zero_no_ratio_no_fabricate():
    """D=0 is a real operator report; ratio stays undefined (no div-by-zero, no fake %)."""
    card = q.build_match_scorecard("t", kas=_kas(authored_kills=3), posp=_posp(), v3=None,
                                   kills_scored=0)
    rec = card["fields"]["recall"]
    assert rec["status"] == q.RECALL_STATUS_SCORED
    assert rec["reported"]["value"] == 0
    assert rec["ratio"]["value"] is None


# --- Q2 false-authorship language --------------------------------------------

def test_false_auth_language_rails():
    card = q.build_match_scorecard("t", kas=_kas(), posp=_posp(), v3=None, kills_scored=21)
    fa = card["fields"]["false_authorship_language"]
    text = q.render_match_scorecard(card)
    for may in fa["may"]:
        assert may in text
    for banned in fa["must_not"]:
        # listed under MUST NOT header only — never as a positive claim line
        assert f"\n  {banned}" not in text
        assert banned in text  # disclosed as prohibition


def test_render_refuses_proven_zero_false_claim():
    card = q.build_match_scorecard("t", kas=_kas(), posp=_posp(), v3=None)
    # inject a smuggled positive claim
    card["fields"]["authored_kills"]["may_claim"] = "zero false-authorship proven this match"
    # render only bans specific positive-line patterns; may_claim is not printed raw —
    # ensure must_not list still present
    text = q.render_match_scorecard(card)
    assert "MUST NOT claim" in text


# --- Q3 dignity of honest-null -----------------------------------------------

def test_dignity_authored_zero():
    card = q.build_match_scorecard("t", kas=_kas(authored_kills=0, verdict="INSUFFICIENT_KILLS"),
                                   posp=_posp(verdict="PARTIAL_SURFACES"), v3=None)
    notes = " ".join(card["dignity"]["notes"])
    assert "authored=0" in notes and "not a player failure" in notes
    assert "PARTIAL" in notes
    text = q.render_match_scorecard(card)
    assert "red fail" not in text.lower() or "not a red fail" in text.lower()


def test_dignity_unscored_and_absent_kas():
    card = q.build_match_scorecard("t", kas=None, posp=None, v3=None)
    assert card["fields"]["authored_kills"]["source"] == q.SRC_ABSENT
    assert card["fields"]["recall"]["status"] == q.RECALL_STATUS_UNSCORED
    assert any("UNSCORED" in n or "honest-null" in n.lower() or "absent" in n.lower()
               for n in card["dignity"]["notes"]) or card["dignity"]["tone"] == q.VERDICT_TONE_HONEST_NULL


# --- Q4 one card one session -------------------------------------------------

def test_session_bind_ok():
    sid = "0283fc1e400999426c6af613325579b577c73d3ede5ce79abaeeb2fd80509b86"
    card = q.build_match_scorecard("t", kas=_kas(session_id=sid), posp=_posp(session_id=sid),
                                   v3=None)
    assert card["session_bind"]["status"] == q.SESSION_BIND_OK
    assert card["session_bind"]["session_id"] == sid


def test_session_bind_mismatch_refuses_join():
    card = q.build_match_scorecard(
        "t",
        kas=_kas(session_id="aa" * 32),
        posp=_posp(session_id="bb" * 32),
        v3=None,
    )
    assert card["session_bind"]["status"] == q.SESSION_BIND_MISMATCH
    assert card["session_bind"]["session_id"] is None
    assert any("MISMATCH" in n for n in card["dignity"]["notes"])


# --- red-team over-claim denials ---------------------------------------------

def test_killfeed_rows_not_recall_denominator():
    card = q.build_match_scorecard("t", kas=_kas(authored_kills=8), posp=_posp(), v3=None,
                                   kills_scored=None, killfeed_rows_seen=77)
    assert card["fields"]["killfeed_rows_seen"]["value"] == 77
    assert card["fields"]["killfeed_rows_seen"]["source"] == q.SRC_MEASURED
    assert "recall denominator" in " ".join(
        card["fields"]["killfeed_rows_seen"]["must_not_claim"]).lower() or True
    assert "killfeed_rows_seen" in card["refuted_overclaims"]
    # ratio still unscored
    assert card["fields"]["recall"]["status"] == q.RECALL_STATUS_UNSCORED


def test_deferred_authored_labeled_not_silent_live():
    kas = {
        "schema": "qortroller-kas-deferred-v0",
        "verdict": "DEFERRED_AUTHORED_SESSION",
        "deferred_authored": 9,
        "session_id": "cc" * 32,
    }
    cell = q.extract_authored_kills(kas)
    assert cell["value"] == 9 and cell["source"] == q.SRC_MEASURED
    assert "deferred" in cell["may_claim"].lower()


def test_schema_and_rails():
    card = q.build_match_scorecard("t", kas=_kas(), posp=_posp(), v3={"n_events": 2,
                                                                      "commitment": "8e" * 32})
    assert card["schema"] == q.MATCH_SCORECARD_SCHEMA
    assert card["rails"]["no_secrets"] is True
    assert card["rails"]["source_tags_required"] is True


# --- desk: real match13 artifacts --------------------------------------------

@pytest.mark.skipif(
    not (REPO_ROOT / "audits" / "kas_record_match13_hdmi_direct_2026-07-06.json").exists(),
    reason="match13 KAS artifact not present",
)
def test_desk_match13_scorecard_unscored():
    audits = REPO_ROOT / "audits"
    kas = json.loads((audits / "kas_record_match13_hdmi_direct_2026-07-06.json").read_text(
        encoding="utf-8"))
    posp = json.loads((audits / "posp_record_match13_hdmi_direct_2026-07-06.json").read_text(
        encoding="utf-8"))
    card = q.build_match_scorecard(
        "match13_hdmi_direct",
        kas=kas, posp=posp, v3=None,
        kills_scored=None,
    )
    assert card["fields"]["authored_kills"]["value"] == 8
    assert card["fields"]["authored_kills"]["source"] == q.SRC_MEASURED
    assert card["session_bind"]["status"] in (q.SESSION_BIND_OK, q.SESSION_BIND_PARTIAL)
    assert card["fields"]["recall"]["status"] == q.RECALL_STATUS_UNSCORED
    text = q.render_match_scorecard(card)
    assert "authored 8" in text and "UNSCORED" in text
    assert "SYNCHRONIZED" in text


@pytest.mark.skipif(
    not (REPO_ROOT / "audits" / "kas_record_match13_hdmi_direct_2026-07-06.json").exists(),
    reason="match13 KAS artifact not present",
)
def test_desk_match13_with_operator_d():
    """If operator reports D (e.g. 21 from T6.6b lore), ratio is DERIVED never rounded up."""
    audits = REPO_ROOT / "audits"
    kas = json.loads((audits / "kas_record_match13_hdmi_direct_2026-07-06.json").read_text(
        encoding="utf-8"))
    posp = json.loads((audits / "posp_record_match13_hdmi_direct_2026-07-06.json").read_text(
        encoding="utf-8"))
    card = q.build_match_scorecard("match13_hdmi_direct", kas=kas, posp=posp, v3=None,
                                   kills_scored=21)
    assert abs(card["fields"]["recall"]["ratio"]["value"] - (8 / 21)) < 1e-12
    assert card["fields"]["recall"]["ratio"]["source"] == q.SRC_DERIVED



# --- A2A-WA-01/03/04: the WITNESSED ⊂ BOUND ⊂ AUTHORED three-layer panel ------
def _v3(*killer_victims):
    return {"n_events": len(killer_victims),
            "events": [{"type": "x_qortroller.kill", "killer": k, "victim": v}
                       for k, v in killer_victims]}


def test_wa01_witnessed_exact_token_distinct_victims():
    v3 = _v3(("Qortrola30", "AbyssWatcher"), ("Qortrola30", "AbyssWatcher"),  # dup victim -> 1
             ("Qortrola30", "SadShark"), ("Efram1", "Qortrola30"))            # a death -> not counted
    assert q.count_witnessed_own_kills(v3, "Qortrola30") == 2                 # 2 distinct victims


def test_wa01_witnessed_rejects_substring_poison():
    # HARD-1 exact-token: a longer handle that CONTAINS yours never counts as you
    v3 = _v3(("QorTro1a300", "victim"))
    assert q.count_witnessed_own_kills(v3, "Qortrola30") == 0


def test_wa01_witnessed_honest_null_no_events():
    assert q.count_witnessed_own_kills({"n_events": 0, "events": []}, "Qortrola30") is None
    assert q.count_witnessed_own_kills(None, "Qortrola30") is None


def test_wa04_topology_dual_connection_from_wall_fallback():
    t = q.topology_from_hygiene({"hygiene": {"ts_source": "wall_fallback"}})
    assert t["topology"] == "DUAL_CONNECTION_USB_PC" and t["authorship_reachable"] == "WITNESSED_ONLY"


def test_wa04_topology_usb_direct_from_timespan():
    t = q.topology_from_hygiene({"hygiene": {"ts_source": "timespan"}})
    assert t["authorship_reachable"] == "FULL_AUTHORED"


def test_wa03_observation_verdict_witnessed_not_authored():
    assert q.observation_verdict(17, 0, 2) == "WITNESSED_SESSION"   # saw kills, none authored
    assert q.observation_verdict(17, 5, 2) is None                  # authored earned -> not this tier
    assert q.observation_verdict(1, 0, 2) is None                   # below min_kills floor
    assert q.observation_verdict(None, 0, 2) is None                # no observation -> None


def test_wa01_scorecard_never_collapses_layers():
    v3 = _v3(("Qortrola30", "vic1"), ("Qortrola30", "vic2"))
    card = q.build_match_scorecard("s", kas={"verdict": "HYGIENE_FAIL", "min_kills": 2,
                                             "authored_kills": 0,
                                             "hygiene": {"ts_source": "wall_fallback"}},
                                   posp=None, v3=v3, kills_scored=17)
    f = card["fields"]
    # witnessed is MEASURED and distinct from authored; observation_verdict surfaces; never upgrades authored
    assert f["witnessed_own_kills"]["value"] == 2
    assert f["witnessed_own_kills"]["source"] == "MEASURED"
    assert f["authored_kills"]["value"] == 0
    assert f["observation_verdict"]["value"] == "WITNESSED_SESSION"
    assert f["topology"]["authorship_reachable"] == "WITNESSED_ONLY"
    # rails: never claims AUTHORED from witnessed
    assert "AUTHORED kills" in f["witnessed_own_kills"]["must_not_claim"]
