"""GP-4 — tests for the gameplay-embedded PoEP session path (A2A-POEP-GAMEPLAY, round-01 + round-04).

   T-GP-1  MENU / UNKNOWN activity -> no challenge (fail-closed scheduler).
   T-GP-2  ACTIVE_GAMEPLAY + delay elapsed -> challenge allowed.
   T-GP-3  summary fail-closed (dry_plumbing_ok False) when below the GO verify-pass floor.
   T-GP-4  round-04: a DRY session reaches dry_plumbing_ok=True but NEVER
           presence_session_candidate_ok=True (+ T-GP-4b low-activity fails closed).
   T-GP-5  catch FA rate surfaces + over-budget fails closed (+ T-GP-5b clean-within-budget plumbing_ok).
   T-GP-6  every public output carries poep_enabled is False + is_presence_verdict is False.
   T-GP-7  summary carries session_id + device_id + the FLIP-A host-trusted claim, NEVER identity/FLIP-B.
   T-GP-8  round-04: live-mode + all-GO-live + bridge activity is the ONLY presence-candidate path.
   T-GP-9  round-04: a dry-mode state file claiming live_hardware=True is overridden to not-live.
   T-GP-10 round-04: untrusted cli_inject activity cannot mint a candidate even in live mode.
   T-GP-11 round-04: a single GO pass is below MIN_GO_VERIFY_PASS -> not even dry_plumbing_ok.
   + classify_activity precedence/fail-closed + scheduler determinism.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from l9_presence.poep_gameplay_session import (  # noqa: E402
    ActivityState,
    ChallengeKind,
    GAMEPLAY_ACTIVE_FRACTION_FLOOR,
    PlaySession,
    SessionChallengeEvent,
    classify_activity,
    next_challenge_delay_s,
    plan_catch_kind,
    session_from_dict,
    session_to_dict,
    should_issue_challenge,
    summarize_session,
)


def _go(passed: bool, live: bool = False) -> SessionChallengeEvent:
    return SessionChallengeEvent(
        kind=ChallengeKind.GO, ts_ns=1, nonce="n",
        verify={"ok": passed, "poep_enabled": False, "is_presence_verdict": False},
        live_hardware=live)


def _nogo(fa: bool) -> SessionChallengeEvent:
    return SessionChallengeEvent(
        kind=ChallengeKind.NO_GO, ts_ns=1, nonce="n",
        verify={"ok": False, "poep_enabled": False, "is_presence_verdict": False},
        catch={"kind": "NO_GO", "human_ok": (not fa), "peak_lsb": (1200.0 if fa else 100.0)},
        live_hardware=False)


def _session_with(challs, activity, *, mode="dry", activity_source="cli_inject"):
    s = PlaySession(session_id="sid1", device_id="dev1", player_label="P1", t_start_ns=1,
                    mode=mode, activity_source=activity_source)
    s.activity_samples = list(activity)
    s.challenges = list(challs)
    return s


# ── T-GP-1 ────────────────────────────────────────────────────────────────────

def test_t_gp_1_menu_unknown_no_challenge():
    # delay elapsed, but activity is not ACTIVE -> never fire
    assert should_issue_challenge(ActivityState.MENU, time_since_last_s=999, delay_s=90) is False
    assert should_issue_challenge(ActivityState.UNKNOWN, time_since_last_s=999, delay_s=90) is False


# ── T-GP-2 ────────────────────────────────────────────────────────────────────

def test_t_gp_2_active_and_delay_elapsed_allows_challenge():
    assert should_issue_challenge(ActivityState.ACTIVE_GAMEPLAY, time_since_last_s=120, delay_s=90) is True
    # not yet elapsed -> no fire even when active
    assert should_issue_challenge(ActivityState.ACTIVE_GAMEPLAY, time_since_last_s=30, delay_s=90) is False


# ── T-GP-3 ────────────────────────────────────────────────────────────────────

def test_t_gp_3_summary_fail_closed_zero_go_pass():
    s = _session_with([_go(False), _go(False)], [ActivityState.ACTIVE_GAMEPLAY] * 4)
    out = summarize_session(s)
    assert out["dry_plumbing_ok"] is False
    assert out["presence_session_candidate_ok"] is False
    assert out["gates"]["go_ok"] is False


# ── T-GP-4 (round-04: dry_plumbing_ok True but candidate_ok False for DRY) ─────

def test_t_gp_4_dry_plumbing_ok_but_never_candidate():
    activity = [ActivityState.ACTIVE_GAMEPLAY] * 3 + [ActivityState.MENU]  # 0.75 >= floor
    s = _session_with([_go(True), _go(True)], activity)  # 2 passes meets the raised floor
    out = summarize_session(s)
    assert out["gates"]["go_ok"] is True
    assert out["gates"]["activity_ok"] is True
    assert out["dry_plumbing_ok"] is True
    # F-GP-2: a DRY session (default mode) can NEVER be a presence candidate.
    assert out["presence_session_candidate_ok"] is False
    assert out["mode"] == "dry"
    assert out["live_hardware"] is False


def test_t_gp_4b_low_activity_fraction_fails_closed():
    activity = [ActivityState.ACTIVE_GAMEPLAY] + [ActivityState.MENU] * 3  # 0.25 < floor
    s = _session_with([_go(True), _go(True)], activity)
    out = summarize_session(s)
    assert out["gates"]["activity_ok"] is False
    assert out["dry_plumbing_ok"] is False
    assert out["presence_session_candidate_ok"] is False


# ── T-GP-5 ────────────────────────────────────────────────────────────────────

def test_t_gp_5_catch_fa_rate_in_summary():
    # 2 GO pass (meets floor) + 1 clean NO_GO + 1 FA NO_GO -> fa_rate 0.5 > budget -> nogo_ok False
    activity = [ActivityState.ACTIVE_GAMEPLAY] * 4
    s = _session_with([_go(True), _go(True), _nogo(fa=False), _nogo(fa=True)], activity)
    out = summarize_session(s)
    assert out["n_nogo"] == 2
    assert out["n_nogo_human_fa"] == 1
    assert out["human_fa_rate"] == 0.5
    assert out["gates"]["nogo_ok"] is False          # FA rate over budget
    assert out["dry_plumbing_ok"] is False


def test_t_gp_5b_clean_nogo_within_budget_plumbing_ok():
    activity = [ActivityState.ACTIVE_GAMEPLAY] * 4
    s = _session_with([_go(True), _go(True), _nogo(fa=False)], activity)
    out = summarize_session(s)
    assert out["human_fa_rate"] == 0.0
    assert out["gates"]["nogo_ok"] is True
    assert out["dry_plumbing_ok"] is True
    assert out["presence_session_candidate_ok"] is False  # still dry


# ── round-04 honesty tests ────────────────────────────────────────────────────

def test_t_gp_8_live_mode_trusted_activity_is_the_only_candidate_path():
    """F-GP-2: only a live-mode session with all-GO-live + bridge-attested activity is a candidate."""
    activity = [ActivityState.ACTIVE_GAMEPLAY] * 4
    s = _session_with([_go(True, live=True), _go(True, live=True)], activity,
                      mode="live", activity_source="bridge")
    out = summarize_session(s)
    assert out["dry_plumbing_ok"] is True
    assert out["effective_live"] is True
    assert out["activity_trusted"] is True
    assert out["presence_session_candidate_ok"] is True
    assert out["live_hardware"] is True


def test_t_gp_9_state_file_spoof_of_live_hardware_defeated():
    """F-GP-4: a DRY-mode session that hand-edits a challenge to live_hardware=True is STILL not-live."""
    activity = [ActivityState.ACTIVE_GAMEPLAY] * 4
    # dry mode, but a challenge row LIES that it was live hardware
    s = _session_with([_go(True, live=True), _go(True, live=True)], activity,
                      mode="dry", activity_source="bridge")
    out = summarize_session(s)
    assert out["effective_live"] is False          # dry mode overrides the per-row lie
    assert out["live_hardware"] is False
    assert out["presence_session_candidate_ok"] is False


def test_t_gp_10_untrusted_cli_activity_cannot_mint_candidate():
    """F-GP-4/V2: even a live-mode session with CLI-inject activity is not a candidate."""
    activity = [ActivityState.ACTIVE_GAMEPLAY] * 4
    s = _session_with([_go(True, live=True), _go(True, live=True)], activity,
                      mode="live", activity_source="cli_inject")
    out = summarize_session(s)
    assert out["activity_trusted"] is False
    assert out["presence_session_candidate_ok"] is False


def test_t_gp_11_raised_floor_single_pass_not_enough():
    """F-GP-5: one GO pass is below MIN_GO_VERIFY_PASS -> not even dry_plumbing_ok."""
    from l9_presence.poep_gameplay_session import MIN_GO_VERIFY_PASS
    assert MIN_GO_VERIFY_PASS >= 2
    activity = [ActivityState.ACTIVE_GAMEPLAY] * 4
    s = _session_with([_go(True)], activity, mode="live", activity_source="bridge")
    out = summarize_session(s)
    assert out["dry_plumbing_ok"] is False
    assert out["presence_session_candidate_ok"] is False


# ── T-GP-6 ────────────────────────────────────────────────────────────────────

def test_t_gp_6_all_outputs_poep_disabled():
    s = _session_with([_go(True)], [ActivityState.ACTIVE_GAMEPLAY] * 2)
    out = summarize_session(s)
    assert out["poep_enabled"] is False
    assert out["is_presence_verdict"] is False
    # round-trip through serialization does not leak an enable
    d = session_to_dict(s)
    out2 = summarize_session(session_from_dict(d))
    assert out2["poep_enabled"] is False


# ── T-GP-7 ────────────────────────────────────────────────────────────────────

def test_t_gp_7_summary_ids_and_flip_a_claim_only():
    s = _session_with([_go(True)], [ActivityState.ACTIVE_GAMEPLAY] * 2)
    out = summarize_session(s)
    assert out["session_id"] == "sid1"
    assert out["device_id"] == "dev1"
    claim_blob = (out["claim"] + " " + out["flip"]).lower()
    assert "flip-a" in claim_blob and "host-trusted" in claim_blob
    # MUST NOT claim identity or anti-compromised-PC (FLIP-B)
    assert "identity" not in out["claim"].lower() or "not identity" in out["claim"].lower()
    assert "flip-b" in out["flip"].lower() and "not flip-b" in out["flip"].lower()


# ── classify_activity ─────────────────────────────────────────────────────────

def test_classify_activity_precedence_and_fail_closed():
    assert classify_activity({"gameplay_context": "ACTIVE_GAMEPLAY"}) == ActivityState.ACTIVE_GAMEPLAY
    assert classify_activity({"gameplay_context": "MENU_DETECTED"}) == ActivityState.MENU
    assert classify_activity({"trigger_active_fraction": 0.3}) == ActivityState.ACTIVE_GAMEPLAY
    assert classify_activity({"trigger_active_fraction": 0.0}) == ActivityState.MENU
    assert classify_activity({"trigger_active": True}) == ActivityState.ACTIVE_GAMEPLAY
    assert classify_activity({"trigger_active": False, "stick_active": False}) == ActivityState.MENU
    # fail-closed
    assert classify_activity({}) == ActivityState.UNKNOWN
    assert classify_activity({"gameplay_context": "NULL"}) == ActivityState.UNKNOWN
    assert classify_activity("not-a-dict") == ActivityState.UNKNOWN


# ── scheduler determinism ─────────────────────────────────────────────────────

def test_scheduler_deterministic_under_seed_and_bounds():
    r1 = random.Random(42)
    r2 = random.Random(42)
    d1 = next_challenge_delay_s(r1, 90, 300)
    d2 = next_challenge_delay_s(r2, 90, 300)
    assert d1 == d2
    assert 90 <= d1 <= 300
    # plan_catch_kind is deterministic under seed + honors ratio
    r = random.Random(7)
    kinds = [plan_catch_kind(4, r) for _ in range(200)]
    n_nogo = sum(1 for k in kinds if k == ChallengeKind.NO_GO)
    assert 0 < n_nogo < 200  # ~20% NO_GO, never all-or-nothing


def test_scheduler_bad_bounds_raise():
    import pytest
    with pytest.raises(ValueError):
        next_challenge_delay_s(random.Random(0), 300, 90)
