"""NQPV adversary-corpus synthesizer (RETINA-EXCL-2 study, critical-path step 5).

Produces MODELED adversary corpus records (label = ``adversary``) so the study harness can measure
the fusion logic's FAR (false-accept rate) against the four orthogonal attack classes. These are the
negative class that pairs with the real human captures loaded by ``nqpv_corpus_loader``.

HONESTY RAIL -- READ THIS BEFORE QUOTING ANY FAR (the entire point of RETINA-EXCL-2 is a defensible
number, so the corpus must not overclaim):
  * These records are SYNTHETIC oracle-output profiles, NOT real captured adversary sessions. A FAR
    computed against them measures the FUSION LOGIC's separation under a MODELED adversary
    oracle-output distribution -- it is a FEASIBILITY gate, not an empirical real-world FAR. The
    empirical FAR needs real adversary captures (FULL-tier study, hardware-gated).
  * The protocol's security claim is ORTHOGONALITY: a false accept requires spoofing ALL of CCO +
    PoEP + coupled-retina + L4/L5/L6 simultaneously. The ``NEAR_MISS_HUMAN`` class models exactly
    that residual attack, behind an explicit ``spoof_all_rate`` knob, so the harness can report FAR
    WITH and WITHOUT the all-oracle-spoof assumption -- never silently bake it in.
  * The synthesizer emits the FULL-oracle profile per class. The harness applies the "PILOT
    projection" (abstain the oracles that are not yet live -- PoEP, coupled-retina) to show that in
    the single-live-oracle pilot regime the fusion CANNOT separate replay/macro-with-human-physics
    from a human. That negative is the load-bearing finding: defensibility REQUIRES the presence
    oracles to be live.

Deterministic: same ``seed`` -> byte-identical corpus (the study corpus must be reproducible).
"""
from __future__ import annotations

import hashlib
import random
from enum import Enum

from vapi_bridge.nqpv_corpus_loader import LABEL_ADVERSARY, NqpvCorpusRecord


class AdversaryClass(str, Enum):
    REPLAY = "REPLAY"                       # legit hardware, replayed human physics, NO live human
    MACRO_INJECTION = "MACRO_INJECTION"     # injected inputs, fails human physics
    RELAY_AIM_ASSIST = "RELAY_AIM_ASSIST"   # live human but output not causal (assist/relay)
    NEAR_MISS_HUMAN = "NEAR_MISS_HUMAN"     # the residual attack: attempts to spoof every oracle


def _synth_id(seed: int, cls: str, i: int, kind: str) -> str:
    return hashlib.sha256(f"{seed}:{cls}:{i}:{kind}".encode()).hexdigest()[:32]


def _record(seed: int, cls: AdversaryClass, i: int, *, cco_tier, l4, poep, coupled, ts_ns) -> NqpvCorpusRecord:
    return NqpvCorpusRecord(
        device_id=_synth_id(seed, cls.value, i, "dev"),
        record_hash=_synth_id(seed, cls.value, i, "rec"),
        ts_ns=ts_ns,
        label=LABEL_ADVERSARY,
        source="synthetic",
        cco_tier=cco_tier,
        l4_l5_l6_ok=l4,
        poep_present=poep,
        retina_coupled_verdict=coupled,
        retina_controller_signal=None,   # synthetic: controller lobe not modeled (metadata only anyway)
        consent_ok=True,                 # adversary operates within a consented session envelope
        humanity_prob=None,
    )


def synthesize(
    *,
    n_per_class: int = 50,
    seed: int = 1337,
    spoof_all_rate: float = 0.0,
    classes: tuple[AdversaryClass, ...] | None = None,
) -> list[NqpvCorpusRecord]:
    """Synthesize ``n_per_class`` adversary records per class.

    ``spoof_all_rate`` (0..1): fraction of ``NEAR_MISS_HUMAN`` records that successfully spoof EVERY
    oracle (the orthogonality-defeating residual attack -> a modeled false accept). At 0.0 (default)
    even the near-miss class leaves the coupled-retina lobe inconsistent (the screen witness is the
    hardest lobe to spoof), so the fusion still catches it; raise it to model a stronger adversary.
    """
    classes = classes or tuple(AdversaryClass)
    rng = random.Random(seed)
    base_ts = 1_700_000_000_000_000_000
    out: list[NqpvCorpusRecord] = []
    for cls in classes:
        for i in range(n_per_class):
            ts = base_ts + i * 1_000_000
            if cls is AdversaryClass.REPLAY:
                # real hardware + replayed real human physics, but NO live presence; the replayed
                # trajectory reads PLAUSIBLE, never LIVE_COHERENT (it is not happening live).
                rec = _record(seed, cls, i, cco_tier="P-T3", l4=True, poep=False,
                              coupled="PLAUSIBLE", ts_ns=ts)
            elif cls is AdversaryClass.MACRO_INJECTION:
                rec = _record(seed, cls, i, cco_tier="P-T3", l4=False, poep=False,
                              coupled="IMPLAUSIBLE", ts_ns=ts)
            elif cls is AdversaryClass.RELAY_AIM_ASSIST:
                # a live human IS at the controller, but the output is not causally theirs.
                rec = _record(seed, cls, i, cco_tier="P-T3", l4=True, poep=True,
                              coupled="IMPLAUSIBLE", ts_ns=ts)
            else:  # NEAR_MISS_HUMAN
                spoofed_all = rng.random() < spoof_all_rate
                rec = _record(
                    seed, cls, i, cco_tier="P-T3", l4=True, poep=True,
                    # spoofed_all defeats even the screen witness -> false accept; otherwise the
                    # coupled lobe stays inconsistent (the orthogonality the protocol relies on).
                    coupled="COUPLED_CLEAN" if spoofed_all else "IMPLAUSIBLE",
                    ts_ns=ts,
                )
            out.append(rec)
    return out
