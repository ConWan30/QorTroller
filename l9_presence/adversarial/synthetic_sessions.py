"""Synthetic, PARAMETERISED session generator for the consistency experiment.

This is NOT real capture. It models the EXPECTED per-class oracle behaviour with
explicit, tunable parameters -- crucially the two retina-axis unknowns that the
whole fusion hinges on:

  - ``retina_tpr_cheat``      P(retina flags IMPLAUSIBLE | machine-automated input)  [true positive]
  - ``retina_fpr_proskill``   P(retina flags IMPLAUSIBLE | elite genuine play) [the killer FP]

Because these are parameters, the experiment is a SENSITIVITY ANALYSIS: it shows
how the fusion's catch-rate and false-accusation-rate move as a function of the
retina trajectory-ROC. It deliberately does not assume retina is good -- it lets
you ask "if retina's pro-skill false-positive rate is X, the fusion falsely
accuses X of elite players." Real values for these parameters require Phase 2.

L4 thresholds mirror config defaults (continuity 5.367 / anomaly 7.009); the
module is standalone so they are restated here with that provenance noted.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from .session_class import LabeledSession, LabeledWindow, Provenance, SessionClass

# config.py defaults (l4_continuity_threshold / l4_anomaly_threshold), restated
# here to keep l9_presence standalone. Provenance: bridge/vapi_bridge/config.py.
L4_CONTINUITY = 5.367
L4_ANOMALY = 7.009


@dataclass(frozen=True)
class SynthParams:
    # --- the two load-bearing retina-axis unknowns (Phase-2 measures the truth) ---
    retina_tpr_cheat: float = 0.85       # catch rate on machine-automated-input windows
    retina_fpr_proskill: float = 0.15    # FALSE flag rate on genuine elite play
    # --- supporting modelled rates ---
    retina_fpr_clean: float = 0.03       # false flag on ordinary clean play
    bot_implausible_rate: float = 0.90   # bot trajectory looks implausible
    relay_presence_rate: float = 0.40    # fraction of relay windows carrying a (relayed) presence proof
    # presence reliability for genuine humans (challenge pass rate)
    human_presence_pass: float = 0.97


def _l4_nominal(rng: random.Random) -> float:
    return rng.uniform(0.5, L4_CONTINUITY - 0.5)  # below continuity = nominal


def _l4_anomalous(rng: random.Random) -> float:
    return rng.uniform(L4_ANOMALY + 0.5, L4_ANOMALY + 5.0)  # above anomaly threshold


def _window(rng, sid, i, klass, *, challenged, reacted, in_band, dev_auth, anomaly, l4, provisional):
    return LabeledWindow(
        session_id=sid,
        ts_ns=1_782_000_000_000_000_000 + i * 1_000_000_000,
        presence_challenged=challenged,
        presence_reacted=reacted,
        presence_in_band=in_band,
        device_auth_pass=dev_auth,
        retina_anomaly_count=anomaly,
        l4_distance=l4,
        class_label=klass,
        provenance=Provenance.SYNTHETIC,
        provisional=provisional,
    )


def _gen_session(rng: random.Random, klass: SessionClass, sid: str,
                 windows: int, p: SynthParams) -> LabeledSession:
    wins = []
    for i in range(windows):
        if klass is SessionClass.HUMAN_CLEAN:
            ok = rng.random() < p.human_presence_pass
            anomaly = 1 if rng.random() < p.retina_fpr_clean else 0
            wins.append(_window(rng, sid, i, klass, challenged=True, reacted=ok, in_band=ok,
                                dev_auth=ok, anomaly=anomaly, l4=_l4_nominal(rng), provisional=False))

        elif klass is SessionClass.BOT_FULL:
            # challenge issued, bot fails liveness (REJECT); trajectory mostly implausible
            anomaly = 1 if rng.random() < p.bot_implausible_rate else 0
            l4 = _l4_anomalous(rng) if rng.random() < 0.5 else _l4_nominal(rng)
            wins.append(_window(rng, sid, i, klass, challenged=True, reacted=False, in_band=False,
                                dev_auth=False, anomaly=anomaly, l4=l4, provisional=False))

        elif klass is SessionClass.HUMAN_INPUT_MACRO:
            # REAL human (presence passes) + machine-automated input (implausible @ TPR)
            ok = rng.random() < p.human_presence_pass
            anomaly = 1 if rng.random() < p.retina_tpr_cheat else 0
            wins.append(_window(rng, sid, i, klass, challenged=True, reacted=ok, in_band=ok,
                                dev_auth=ok, anomaly=anomaly, l4=_l4_nominal(rng), provisional=False))

        elif klass is SessionClass.HUMAN_RELAY:
            # bot trajectory throughout; a (relayed) presence proof is bound only sometimes
            relayed = rng.random() < p.relay_presence_rate
            anomaly = 1 if rng.random() < p.bot_implausible_rate else 0
            wins.append(_window(rng, sid, i, klass, challenged=relayed,
                                reacted=relayed, in_band=relayed, dev_auth=relayed,
                                anomaly=anomaly, l4=_l4_nominal(rng), provisional=False))

        else:  # PRO_SKILL -- elite genuine human; retina MAY wrongly flag (the FP risk)
            ok = rng.random() < p.human_presence_pass
            anomaly = 1 if rng.random() < p.retina_fpr_proskill else 0
            # provisional=True: synthetic pro-skill is the weakest proxy (honesty rail)
            wins.append(_window(rng, sid, i, klass, challenged=True, reacted=ok, in_band=ok,
                                dev_auth=ok, anomaly=anomaly, l4=_l4_nominal(rng), provisional=True))

    provisional = klass is SessionClass.PRO_SKILL
    return LabeledSession(session_id=sid, class_label=klass,
                          provenance=Provenance.SYNTHETIC, windows=wins, provisional=provisional)


def generate_labeled_sessions(
    *, seed: int = 0, n_per_class: int = 50, windows_per_session: int = 8,
    params: SynthParams | None = None,
) -> list[LabeledSession]:
    """Generate n_per_class sessions for each of the 5 classes (deterministic by seed)."""
    p = params or SynthParams()
    rng = random.Random(seed)
    out: list[LabeledSession] = []
    for klass in SessionClass:
        for k in range(n_per_class):
            out.append(_gen_session(rng, klass, f"{klass.value}_{k:04d}", windows_per_session, p))
    return out
