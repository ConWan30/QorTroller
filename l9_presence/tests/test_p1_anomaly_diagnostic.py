"""P1 anomaly diagnostic tests — design §8 acceptance tests T1-T8 + the T-H* decision logic.

Pins: closed-enum labels only (no free text) · never emits SEPARATED · untagged excluded from peers ·
pre-registered order H1->H2->H3->H5->H4 · frozen thresholds equal P0-A constants · H4 honest-None when
no aim-matched comparator · offline schema string.
"""
from __future__ import annotations

import numpy as np

from l9_presence.p1_anomaly_diagnostic import (
    GENUINE_LOW_COUPLING,
    HIGH_RESIDUAL,
    INCONCLUSIVE,
    LAG_REGIME,
    MARGINAL_AIM,
    MARGINAL_AIM_BAND,
    STUDY_SCHEMA,
    classify_p1_anomaly,
    session_metrics,
)
from l9_presence.presence_separation_study import AIM_ACTIVITY_MIN, TAU_HUMAN
from l9_presence.session_recorder import SessionData


def _m(player, coupling, aim, lag, dec, label="human", duration_bin=60):
    """A synthetic session-metrics dict (bypasses the oracle to test the T-H* logic directly)."""
    return {"player": player, "label": label, "coupling": coupling, "aim": aim, "lag_ms": lag,
            "decoupled_energy": dec, "duration_bin": duration_bin, "aim_active": aim >= AIM_ACTIVITY_MIN}


def _corpus(p1, peers):
    return [_m("P1", *r) for r in p1] + [_m("P2", *r) for r in peers[:len(peers)//2]] \
        + [_m("P3", *r) for r in peers[len(peers)//2:]]


# ------------------------------------------------------------------- T3/T4 closed-enum + no SEPARATED
def test_labels_are_closed_enum_never_separated():
    # P1 marginal aim (12 < 20.4, < peers 50), peers strong
    rep = classify_p1_anomaly(_corpus(
        p1=[(0.09, 12, 200, 0.99)] * 6, peers=[(0.5, 50, 30, 0.6)] * 6))
    assert rep.primary in (MARGINAL_AIM, HIGH_RESIDUAL, LAG_REGIME, GENUINE_LOW_COUPLING, INCONCLUSIVE)
    assert rep.to_dict()["schema"] == STUDY_SCHEMA and rep.to_dict().get("verdict") is None
    assert rep.p0a_v2_separated_unchanged is True


# ------------------------------------------------------------------- H1 primary (marginal aim first)
def test_marginal_aim_wins_first_in_order():
    # P1 low aim (12 < 20.4) AND high dec -> both H1 and H2 True; order puts MARGINAL_AIM primary
    rep = classify_p1_anomaly(_corpus(
        p1=[(0.09, 12, 200, 0.99)] * 6, peers=[(0.5, 50, 30, 0.6)] * 6))
    assert rep.primary == MARGINAL_AIM
    assert HIGH_RESIDUAL in rep.secondaries          # stacks as secondary note


# ------------------------------------------------------------------- H2 when aim NOT marginal
def test_high_residual_when_aim_is_not_marginal():
    # P1 aim high (40 > 20.4) so H1 fails; dec high -> H2 primary
    rep = classify_p1_anomaly(_corpus(
        p1=[(0.09, 40, 30, 0.99)] * 6, peers=[(0.5, 50, 30, 0.6)] * 6))
    assert rep.primary == HIGH_RESIDUAL


# ------------------------------------------------------------------- H3 lag regime
def test_lag_regime_gap():
    # P1 aim high (H1 fail), dec low (H2 fail), lag gap >= 100 -> H3
    rep = classify_p1_anomaly(_corpus(
        p1=[(0.09, 40, 250, 0.6)] * 6, peers=[(0.5, 50, 30, 0.6)] * 6))
    assert rep.primary == LAG_REGIME


# ------------------------------------------------------------------- H0 insufficient n
def test_inconclusive_when_focus_n_below_5():
    rep = classify_p1_anomaly(_corpus(p1=[(0.09, 12, 200, 0.99)] * 3, peers=[(0.5, 50, 30, 0.6)] * 6))
    assert rep.primary == INCONCLUSIVE and "n=3" in rep.reason


# ------------------------------------------------------------------- H4 honest-None (no aim overlap)
def test_h4_untestable_when_no_aim_matched_comparator():
    # P1 aim ~12 (band ~9.6-14.4); peers aim 50 -> 0 peers in band -> T-H4 pass is None (untestable)
    rep = classify_p1_anomaly(_corpus(
        p1=[(0.09, 12, 30, 0.6)] * 6, peers=[(0.5, 50, 30, 0.6)] * 6))
    assert rep.tests["T-H4_GENUINE_LOW"]["pass"] is None
    assert "no aim-matched comparator" in rep.tests["T-H4_GENUINE_LOW"]["detail"]


# ------------------------------------------------------------------- T5 untagged excluded from peers
def test_untagged_excluded_from_peer_pool():
    corpus = ([_m("P1", 0.09, 12, 200, 0.99)] * 6 + [_m("P2", 0.5, 50, 30, 0.6)] * 6
              + [_m("?", 0.1, 12, 200, 0.99)] * 6)   # untagged mimic P1 but must NOT pool into peers
    rep = classify_p1_anomaly(corpus, comparators=("P2", "P3"))
    assert "?" in rep.per_player                      # reported
    # peers = P2 only (untagged excluded) -> peer median aim 50, so H1 (P1 12 < 50) still holds
    assert rep.primary == MARGINAL_AIM


# ------------------------------------------------------------------- thresholds frozen == P0-A
def test_thresholds_frozen_equal_p0a():
    assert abs(MARGINAL_AIM_BAND - 2.0 * AIM_ACTIVITY_MIN) < 1e-9
    assert TAU_HUMAN == 0.20


# ------------------------------------------------------------------- session_metrics real path (T1)
def test_session_metrics_real_scoring_path():
    n = 1200
    t = np.linspace(0, 10000, n)
    sx = 128 + 70 * np.sin(2 * np.pi * 0.6 * t / 1000.0)
    yaw = np.cumsum(sx - 128.0) * 0.001
    m = session_metrics(SessionData(t, sx, np.full(n, 128.0), t, yaw, np.zeros(n), "human", None, "P1"))
    assert m["player"] == "P1" and m["aim_active"] is True
    assert 0.0 <= m["coupling"] <= 1.0 and m["duration_s"] > 0 and "decoupled_energy" in m
