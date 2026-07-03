"""Tests for per-session feed-cut anchor auto-generation. The gate-failure (R3) and false-catch (R2) paths
are the load-bearing ones — a bad auto-cut poisons everything downstream, so they get the most coverage."""
from __future__ import annotations

from l9_presence import killfeed_session_anchor as sa


def _cut_ok():
    return ("ANCHOR_OBJ", "sha_abc123")           # (opaque anchor, sha)


def _cut_fail():
    return None


def _mk(**kw):
    kw.setdefault("k_consistency", 3)
    return sa.SessionAnchorGenerator(session_id="s2", **kw)


# --- R2: the bootstrap CATCH gate (false-catch prevention) ------------------------------------------

def test_bootstrap_catch_requires_floor_geometry_AND_fresh_row():
    g = _mk()
    # below floor -> no cut
    assert g.observe_bootstrap(score=0.50, x_frac=0.18, y_frac=0.30, fresh_row=True, cut_fn=_cut_ok) is None
    assert g.regime == sa.BOOTSTRAP
    # clears floor but WRONG SLOT (victim x>0.28) -> no cut
    assert g.observe_bootstrap(score=0.60, x_frac=0.40, y_frac=0.30, fresh_row=True, cut_fn=_cut_ok) is None
    assert g.regime == sa.BOOTSTRAP
    # clears floor, killer slot, but NOT a fresh row (static patch) -> R2 blocks the cut
    assert g.observe_bootstrap(score=0.60, x_frac=0.18, y_frac=0.30, fresh_row=False, cut_fn=_cut_ok) is None
    assert g.regime == sa.BOOTSTRAP
    assert g.status()["bootstrap_catches"] == 0        # cut_fn NEVER invoked on a gated-out catch


def test_bootstrap_catch_all_gates_pass_cuts_candidate():
    g = _mk()
    ev = g.observe_bootstrap(score=0.58, x_frac=0.18, y_frac=0.30, fresh_row=True, cut_fn=_cut_ok)
    assert ev["event"] == "candidate_cut" and ev["candidate_sha"] == "sha_abc123"
    assert g.regime == sa.CANDIDATE
    assert g.active_anchor() == "ANCHOR_OBJ" and g.effective_floor() == 0.66


def test_bootstrap_cut_failure_stays_bootstrap_and_logs():
    g = _mk()
    ev = g.observe_bootstrap(score=0.58, x_frac=0.18, y_frac=0.30, fresh_row=True, cut_fn=_cut_fail)
    assert ev["event"] == "bootstrap_cut_failed"
    assert g.regime == sa.BOOTSTRAP
    assert g.status()["bootstrap_catches"] == 1 and g.status()["failures"][0]["kind"] == "cut_failed"


# --- R3: the promotion / demotion gate --------------------------------------------------------------

def _to_candidate(g):
    g.observe_bootstrap(score=0.58, x_frac=0.18, y_frac=0.30, fresh_row=True, cut_fn=_cut_ok)
    assert g.regime == sa.CANDIDATE


def test_promotion_needs_K_consistent_killer_matches():
    g = _mk(k_consistency=3)
    _to_candidate(g)
    assert g.observe_candidate(score=0.72, x_frac=0.18, y_frac=0.30, is_background=False)["event"] == "candidate_progress"
    assert g.observe_candidate(score=0.70, x_frac=0.18, y_frac=0.30, is_background=False)["event"] == "candidate_progress"
    assert g.regime == sa.CANDIDATE                     # 2/3, not yet
    ev = g.observe_candidate(score=0.80, x_frac=0.18, y_frac=0.30, is_background=False)
    assert ev["event"] == "promoted" and g.regime == sa.PROMOTED
    assert g.active_anchor_tag() == "session_s2@0.66"


def test_below_floor_candidate_match_does_not_count():
    g = _mk(k_consistency=2)
    _to_candidate(g)
    # a candidate crop that scores below the PROMOTE floor does not advance consistency
    assert g.observe_candidate(score=0.60, x_frac=0.18, y_frac=0.30, is_background=False) is None
    assert g.status()["consistent"] == 0 and g.regime == sa.CANDIDATE


def test_candidate_fp_on_background_DEMOTES_and_logs():
    # THE gate-failure path: the auto-cut candidate false-fires in the killer slot on a NEUTRAL frame.
    g = _mk(k_consistency=3)
    _to_candidate(g)
    g.observe_candidate(score=0.75, x_frac=0.18, y_frac=0.30, is_background=False)   # 1 real match
    ev = g.observe_candidate(score=0.70, x_frac=0.18, y_frac=0.30, is_background=True)  # FP on background
    assert ev["event"] == "candidate_demoted_fp"
    assert g.regime == sa.BOOTSTRAP                     # reverted
    assert g.active_anchor() is None                   # candidate discarded
    st = g.status()
    assert st["fp_fires"] == 1 and st["demotions"] == 1
    assert st["failures"][-1]["kind"] == "candidate_fp"


def test_clean_background_does_not_fp():
    g = _mk()
    _to_candidate(g)
    # background crop BELOW the promote floor in killer slot -> not an FP, no effect
    assert g.observe_candidate(score=0.50, x_frac=0.18, y_frac=0.30, is_background=True) is None
    assert g.regime == sa.CANDIDATE and g.status()["fp_fires"] == 0


def test_demote_then_recatch_records_first_failure_never_silent():
    # R3: after a demotion, the next catch is a fresh cut, but the first failure MUST remain on record.
    g = _mk(k_consistency=1)
    _to_candidate(g)
    g.observe_candidate(score=0.70, x_frac=0.18, y_frac=0.30, is_background=True)   # FP -> demote
    assert g.regime == sa.BOOTSTRAP
    # re-catch with a fresh cut
    g.observe_bootstrap(score=0.58, x_frac=0.18, y_frac=0.30, fresh_row=True, cut_fn=lambda: ("A2", "sha_def"))
    assert g.regime == sa.CANDIDATE
    # the ORIGINAL failure is still on record (no silent churn)
    assert any(f["kind"] == "candidate_fp" for f in g.status()["failures"])


# --- R1: regime provenance + coverage honesty -------------------------------------------------------

def test_regime_provenance_tags():
    g = _mk(k_consistency=1)
    assert g.active_anchor_tag() == "bootstrap_feed_v1@0.55"
    _to_candidate(g)
    assert g.active_anchor_tag() == "candidate_s2@0.66"
    g.observe_candidate(score=0.80, x_frac=0.18, y_frac=0.30, is_background=False)
    assert g.regime == sa.PROMOTED and g.active_anchor_tag() == "session_s2@0.66"


def test_coverage_note_zero_kill_session_is_bootstrap_only():
    g = _mk()
    assert "bootstrap-only, no session anchor" in g.coverage_note()
    _to_candidate(g)
    assert "NOT promoted" in g.coverage_note()
    g._regime = sa.PROMOTED
    assert "coverage gap" in g.coverage_note()
