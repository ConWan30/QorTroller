"""Tests for the adversarial consistency-experiment harness.

SCOPE HONESTY: synthetic, parameterised. These prove the harness WIRING and the
structural findings (esp. that the fusion's pro-skill false-accusation rate equals
the retina false-positive parameter). They do NOT prove real-world separation.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from l9_presence.adversarial.consistency_eval import run_experiment  # noqa: E402
from l9_presence.adversarial.session_class import SessionClass  # noqa: E402
from l9_presence.adversarial.signal_adapter import evaluate_window, window_to_signals  # noqa: E402
from l9_presence.adversarial.synthetic_sessions import (  # noqa: E402
    SynthParams,
    generate_labeled_sessions,
)
from l9_presence.presence_retina_consistency import ConsistencyVerdict, check_binding  # noqa: E402


def _gen(klass, params, n=5, windows=4, seed=0):
    sessions = generate_labeled_sessions(seed=seed, n_per_class=n, windows_per_session=windows, params=params)
    return [s for s in sessions if s.class_label is klass]


def _verdicts(sessions):
    return [evaluate_window(w).verdict for s in sessions for w in s.windows]


def test_binding_passes_by_construction():
    p = SynthParams(human_presence_pass=1.0)
    s = _gen(SessionClass.HUMAN_CLEAN, p)[0]
    presence, trajectory, _ = window_to_signals(s.windows[0])
    assert check_binding(presence, trajectory).bound is True


def test_human_clean_is_consistent_human():
    p = SynthParams(human_presence_pass=1.0, retina_fpr_clean=0.0)
    assert all(v is ConsistencyVerdict.CONSISTENT_HUMAN for v in _verdicts(_gen(SessionClass.HUMAN_CLEAN, p)))


def test_aim_assist_catch_at_full_tpr():
    p = SynthParams(human_presence_pass=1.0, retina_tpr_cheat=1.0)
    vs = _verdicts(_gen(SessionClass.HUMAN_INPUT_MACRO, p))
    assert all(v is ConsistencyVerdict.INCONSISTENT_PRESENCE_WITHOUT_AUTHENTIC_TRAJECTORY for v in vs)


def test_bot_full_never_consistent_human():
    p = SynthParams(bot_implausible_rate=1.0)
    vs = _verdicts(_gen(SessionClass.BOT_FULL, p))
    assert ConsistencyVerdict.CONSISTENT_HUMAN not in vs
    # REJECT + IMPLAUSIBLE => the two oracles agree "no genuine human activity"
    assert all(v is ConsistencyVerdict.CONSISTENT_INACTIVE for v in vs)


def test_relay_unrelayed_windows_are_indeterminate():
    # no presence proof bound + implausible trajectory => single-oracle => INDETERMINATE
    p = SynthParams(relay_presence_rate=0.0, bot_implausible_rate=1.0)
    vs = _verdicts(_gen(SessionClass.HUMAN_RELAY, p))
    assert all(v is ConsistencyVerdict.INDETERMINATE for v in vs)


def test_relay_relayed_windows_are_caught():
    # relayed presence proof + bot (implausible) trajectory => the machine-assist catch
    p = SynthParams(relay_presence_rate=1.0, bot_implausible_rate=1.0)
    vs = _verdicts(_gen(SessionClass.HUMAN_RELAY, p))
    assert all(v is ConsistencyVerdict.INCONSISTENT_PRESENCE_WITHOUT_AUTHENTIC_TRAJECTORY for v in vs)


def test_proskill_false_accusation_equals_retina_fp_param():
    """The load-bearing identity: the fusion's pro-skill false-accusation rate is
    EXACTLY retina_fpr_proskill -- the fusion does not rescue this boundary."""
    for fpr in (0.0, 1.0):
        p = SynthParams(human_presence_pass=1.0, retina_fpr_proskill=fpr)
        sessions = generate_labeled_sessions(seed=1, n_per_class=10, windows_per_session=6, params=p)
        result = run_experiment(sessions, p)
        assert result["metrics"]["false_accusation_rate"]["PRO_SKILL"] == fpr


def test_machine_assist_catch_rate_full_tpr():
    p = SynthParams(human_presence_pass=1.0, retina_tpr_cheat=1.0)
    sessions = generate_labeled_sessions(seed=2, n_per_class=10, windows_per_session=6, params=p)
    assert run_experiment(sessions, p)["metrics"]["machine_assist_catch_rate"] == 1.0


def test_confusion_rows_sum_to_n_windows():
    p = SynthParams()
    sessions = generate_labeled_sessions(seed=3, n_per_class=8, windows_per_session=5, params=p)
    result = run_experiment(sessions, p)
    for c in SessionClass:
        assert sum(result["confusion"][c.value].values()) == result["n_windows"][c.value] == 8 * 5


def test_provisional_flags():
    p = SynthParams()
    sessions = generate_labeled_sessions(seed=4, n_per_class=3, windows_per_session=3, params=p)
    result = run_experiment(sessions, p)
    assert result["provisional"] is True
    pro = [s for s in sessions if s.class_label is SessionClass.PRO_SKILL]
    assert all(s.provisional for s in pro)
    assert all(w.provisional for s in pro for w in s.windows)


def test_result_shape():
    p = SynthParams()
    sessions = generate_labeled_sessions(seed=5, n_per_class=2, windows_per_session=2, params=p)
    result = run_experiment(sessions, p)
    assert result["schema"] == "vapi-consistency-experiment-v1"
    assert "confusion" in result and "metrics" in result and "params" in result
    assert "contextual_security_rate" in result["metrics"]
