"""P-WAVE-0 — synthetic waveform-shape separability harness (FLIP-A ladder rung 3, grok round-21).

The de-risk question BEFORE we change the capture layer to store raw waveforms: does the SHAPE of the
post-fire IMU reflex curve separate a biomechanical human response from a canned macro at all? If even
synthetic canned shapes are not separable by physics-motivated shape features, storing real waveforms
buys nothing and we pivot. If they ARE separable, waveform capture+store (rung 2) is worth wiring, and
the real test becomes the physical hardware-in-the-loop rig (rung 4, rig-gated).

This is NOT an ML model (grok round-16 killed offline scalar models — a scalar-matching macro clears
any fitted boundary). It is a PHYSICS-MOTIVATED SHAPE GATE: a human involuntary grip-jerk is an
underdamped second-order response (smooth bounded-jerk rise, overshoot, damped settle, band-limited);
canned macro shapes (step / rectangular pulse / linear triangle / in-band random) violate one or more of
those physics. The gate thresholds are round human-physics numbers, NOT fitted to the synthetic data.

HONEST SCOPE (what a PASS here does and does NOT mean):
  - PROVES: shape features separate a biomechanical-curve MODEL from canned/synthetic macro shapes.
  - Does NOT prove separability against a PHYSICAL hardware-in-the-loop rig that jerks the pad
    (rung 4 — open empirics, rig-gated) NOR against a compromised host replaying a real human waveform
    (that is FLIP-B / firmware-attestation territory, structurally out of host-side FLIP-A scope).
  - poep_enabled / L6B_ENABLED stay False. This is a de-risk harness, not a presence claim.

Pure stdlib; deterministic under a seed.
"""
from __future__ import annotations

import math
import random
import zlib

NAIVE_MACRO_CLASSES = ("macro_step", "macro_pulse", "macro_triangle", "macro_random")
# grok round-22: SETTLING non-reflex shapes that pass the tail_slope gate -> shape alone does NOT bound
# them. Reported as the harness's OWN LIMIT (expected to pass; they are the honest boundary).
SETTLING_ADVERSARY_CLASSES = ("adv_ramp_hold", "adv_decayed_exp", "adv_smart_settle")
MACRO_CLASSES = NAIVE_MACRO_CLASSES        # back-compat: "naive" is what the PASS is about
CLASSES = ("human",) + NAIVE_MACRO_CLASSES + SETTLING_ADVERSARY_CLASSES

N_SAMPLES = 40           # ~320 ms reflex window at ~8 ms/poll (aligned to reflex onset at sample 0)
DT_S = 0.008

# --- physics-motivated human-shape gate thresholds (round numbers, NOT fitted) ----------------------
RISE_SAMPLES_MIN = 2         # 16 ms   — a human jerk is not an instantaneous step
RISE_SAMPLES_MAX = 16        # 128 ms  — nor an arbitrarily slow ramp
OVERSHOOT_MIN = 0.03         # underdamped response overshoots then settles BELOW peak
RISE_SIGN_CHANGES_MAX = 3    # the rise is smooth, not noisy
MAX_JERK_MAX = 0.60          # bounded jerk (normalized) — a step edge blows past this
HF_RATIO_MAX = 0.50          # band-limited energy — steps/noise push high-frequency energy up
TAIL_SLOPE_MIN = -0.030      # the reflex SETTLES to a plateau (tail ~flat); a triangle keeps DESCENDING
#                              *** EMPIRICAL ASSUMPTION (rung-2 gate): this presumes a real grip reflex
#                              settles-to-plateau rather than returns-to-baseline. That is exactly the
#                              question real waveform capture (rung 2) must confirm; if reflexes actually
#                              relax back to baseline, the triangle class is NOT shape-separable and this
#                              threshold must be dropped. Documented, not assumed silently. ***


# --- shape features (pure stdlib) -------------------------------------------------------------------

def _diff(seq: list[float]) -> list[float]:
    return [seq[i + 1] - seq[i] for i in range(len(seq) - 1)]


def waveform_shape_features(w: list[float]) -> dict:
    """Physics features of a reflex accel-magnitude curve. Latency-independent (onset-aligned)."""
    n = len(w)
    base = w[0]
    peak = max(w)
    pidx = w.index(peak)
    amp = (peak - base) or 1e-9

    lo, hi = base + 0.1 * amp, base + 0.9 * amp
    t10 = next((i for i in range(pidx + 1) if w[i] >= lo), 0)
    t90 = next((i for i in range(pidx + 1) if w[i] >= hi), pidx)
    rise_samples = max(1, t90 - t10)

    tail = w[int(0.75 * n):] or w[-1:]
    settle = sum(tail) / len(tail)
    overshoot_ratio = (peak - settle) / amp           # >0 iff it overshoots then settles below peak

    d_rise = _diff(w[:pidx + 1]) or [0.0]
    rise_sign_changes = sum(1 for i in range(1, len(d_rise))
                            if (d_rise[i] > 0) != (d_rise[i - 1] > 0))

    fd = _diff(w)
    sd = _diff(fd)
    max_jerk = (max((abs(x) for x in sd), default=0.0) / amp)
    e1 = sum(x * x for x in fd) or 1e-9
    e2 = sum(x * x for x in sd)
    hf_ratio = e2 / e1

    decay_samples = max(1, n - 1 - pidx)
    # tail slope: mean per-sample change over the last quarter, normalized by amp. A settled damped
    # response is ~flat here; a triangle ramp is still descending (strongly negative).
    tail_diffs = _diff(w[int(0.75 * n):]) or [0.0]
    tail_slope = (sum(tail_diffs) / len(tail_diffs)) / amp
    return {
        "rise_samples": rise_samples,
        "overshoot_ratio": overshoot_ratio,
        "rise_sign_changes": rise_sign_changes,
        "max_jerk": max_jerk,
        "hf_ratio": hf_ratio,
        "rise_decay_asym": rise_samples / decay_samples,
        "tail_slope": tail_slope,
        "peak_frac": pidx / max(1, n - 1),          # where the peak sits (rung-2: >0.75 => still rising, no tail)
    }


def human_shape_gate(f: dict) -> bool:
    """A waveform passes the human-shape gate iff ALL physics conditions hold (fail-closed)."""
    return (
        RISE_SAMPLES_MIN <= f["rise_samples"] <= RISE_SAMPLES_MAX
        and f["overshoot_ratio"] >= OVERSHOOT_MIN
        and f["rise_sign_changes"] <= RISE_SIGN_CHANGES_MAX
        and f["max_jerk"] <= MAX_JERK_MAX
        and f["hf_ratio"] <= HF_RATIO_MAX
        and f["tail_slope"] >= TAIL_SLOPE_MIN
    )


# --- synthetic generators ---------------------------------------------------------------------------

def synth_human(rng: random.Random, *, amp: float = 2000.0, base: float = 200.0) -> list[float]:
    """Underdamped 2nd-order step response + tremor + sensor noise (a biomechanical grip-jerk model)."""
    zeta = rng.uniform(0.28, 0.5)                     # damping -> overshoot 15-40%
    wn = rng.uniform(45.0, 75.0)                      # natural freq -> few-sample rise
    wd = wn * math.sqrt(1.0 - zeta * zeta)
    phi = math.acos(zeta)
    f_tremor = rng.uniform(6.0, 12.0)                 # physiological tremor band (Hz)
    a_tremor = rng.uniform(0.01, 0.04)
    noise = rng.uniform(0.005, 0.02)
    w = []
    for i in range(N_SAMPLES):
        t = i * DT_S
        step = 1.0 - (1.0 / math.sqrt(1.0 - zeta * zeta)) * math.exp(-zeta * wn * t) * math.sin(wd * t + phi)
        step = max(0.0, step)
        trem = a_tremor * math.sin(2.0 * math.pi * f_tremor * t)
        val = base + amp * (step + trem) + rng.gauss(0.0, noise * amp)
        w.append(val)
    return w


def synth_macro_step(rng: random.Random, *, amp: float = 2000.0, base: float = 200.0) -> list[float]:
    k = rng.randint(2, 6)
    return [base + (amp if i >= k else 0.0) + rng.gauss(0.0, 0.01 * amp) for i in range(N_SAMPLES)]


def synth_macro_pulse(rng: random.Random, *, amp: float = 2000.0, base: float = 200.0) -> list[float]:
    a = rng.randint(2, 6)
    b = a + rng.randint(6, 16)
    return [base + (amp if a <= i < b else 0.0) + rng.gauss(0.0, 0.01 * amp) for i in range(N_SAMPLES)]


def synth_macro_triangle(rng: random.Random, *, amp: float = 2000.0, base: float = 200.0) -> list[float]:
    peak_i = rng.randint(N_SAMPLES // 3, 2 * N_SAMPLES // 3)
    w = []
    for i in range(N_SAMPLES):
        frac = (i / peak_i) if i <= peak_i else max(0.0, 1.0 - (i - peak_i) / (N_SAMPLES - peak_i))
        w.append(base + amp * frac + rng.gauss(0.0, 0.01 * amp))
    return w


def synth_macro_random(rng: random.Random, *, amp: float = 2000.0, base: float = 200.0) -> list[float]:
    return [base + amp * rng.uniform(0.2, 1.0) for _ in range(N_SAMPLES)]


# --- SETTLING ADVERSARIES (grok round-22): non-reflex shapes that rise + settle-to-plateau, so they
# satisfy tail_slope and pass the human-shape gate. NOT reflexes; included to demonstrate honestly that
# shape alone does NOT bound a settling adversary -- the harness's own limit, not hidden. -------------

def synth_adv_ramp_hold(rng: random.Random, *, amp: float = 2000.0, base: float = 200.0) -> list[float]:
    """Linear rise -> small overshoot bump -> HOLD flat. Settles, but a trivial non-reflex construction."""
    k = rng.randint(3, 8)
    os = rng.uniform(0.05, 0.15)
    w = []
    for i in range(N_SAMPLES):
        if i < k:
            v = amp * (i / k)
        elif i < k + 3:
            v = amp * (1.0 + os)
        else:
            v = amp
        w.append(base + v + rng.gauss(0.0, 0.01 * amp))
    return w


def synth_adv_decayed_exp(rng: random.Random, *, amp: float = 2000.0, base: float = 200.0) -> list[float]:
    """Fast rise then relax to a RAISED plateau (peak*plateau). Settles above baseline; not a reflex."""
    tau = rng.uniform(0.02, 0.05)
    plateau = rng.uniform(0.75, 0.95)
    w = []
    for i in range(N_SAMPLES):
        t = i * DT_S
        rise = 1.0 - math.exp(-t / 0.02)
        relax = plateau + (1.0 - plateau) * math.exp(-t / tau)
        w.append(base + amp * rise * relax + rng.gauss(0.0, 0.01 * amp))
    return w


def synth_adv_smart_settle(rng: random.Random, *, amp: float = 2000.0, base: float = 200.0) -> list[float]:
    """A macro that 'learns the gate': smoothstep rise -> overshoot -> exp settle to plateau."""
    k = rng.randint(3, 7)
    os = rng.uniform(0.1, 0.3)
    plateau_i = k + 2
    w = []
    for i in range(N_SAMPLES):
        if i < k:
            x = i / k
            smooth = x * x * (3.0 - 2.0 * x)          # smoothstep -> smooth bounded-jerk rise
            v = amp * smooth * (1.0 + os)
        else:
            v = amp * (1.0 + os * math.exp(-(i - plateau_i) / 4.0))  # overshoot -> settle to amp
        w.append(base + v + rng.gauss(0.0, 0.012 * amp))
    return w


_GENERATORS = {
    "human": synth_human,
    "macro_step": synth_macro_step,
    "macro_pulse": synth_macro_pulse,
    "macro_triangle": synth_macro_triangle,
    "macro_random": synth_macro_random,
    "adv_ramp_hold": synth_adv_ramp_hold,
    "adv_decayed_exp": synth_adv_decayed_exp,
    "adv_smart_settle": synth_adv_smart_settle,
}

# --- separability report ----------------------------------------------------------------------------

FRR_BAR = 0.10               # human curves that WRONGLY fail the shape gate
FAR_BAR = 0.05               # NAIVE canned macro shapes that WRONGLY pass the shape gate


def class_pass_rate(cls: str, *, n: int = 400, seed: int = 0xF00D) -> float:
    """Fraction of class `cls` that PASSES the human-shape gate. Per-class seed uses adler32 (STABLE
    across processes -- Python's salted hash() made banked numbers irreproducible, grok round-22)."""
    rng = random.Random((seed ^ zlib.adler32(cls.encode())) & 0xFFFFFFFF)
    gen = _GENERATORS[cls]
    return sum(1 for _ in range(n) if human_shape_gate(waveform_shape_features(gen(rng)))) / n


def separability_report(*, n: int = 400, seed: int = 0xF00D) -> dict:
    """Human FRR + NAIVE-macro FAR (the conditional PASS) + SETTLING-adversary FAR (the honest limit).

    The PASS is deliberately NARROW (grok round-22): it certifies only that textbook naive canned shapes
    (step/pulse/triangle/random) are separable from the human MODEL, AND it is CONDITIONAL on the
    settle-to-plateau assumption (drop `tail_slope` and the triangle returns). It does NOT certify that
    shape bounds a SETTLING adversary -- those FARs are reported alongside, and they are high.
    """
    human_frr = 1.0 - class_pass_rate("human", n=n, seed=seed)
    naive_far = {c: class_pass_rate(c, n=n, seed=seed) for c in NAIVE_MACRO_CLASSES}
    settling_far = {c: class_pass_rate(c, n=n, seed=seed) for c in SETTLING_ADVERSARY_CLASSES}
    worst_naive = max(naive_far.values())
    naive_separated = (human_frr <= FRR_BAR) and (worst_naive <= FAR_BAR)
    return {
        "human_frr": human_frr,
        "naive_macro_far": naive_far,
        "worst_naive_far": worst_naive,
        "settling_adversary_far": settling_far,          # THE HONEST LIMIT — these pass the gate
        "worst_settling_far": max(settling_far.values()),
        "frr_bar": FRR_BAR,
        "far_bar": FAR_BAR,
        "naive_canned_separated": naive_separated,       # the narrow, conditional PASS
        "shape_bounds_settling_adversary": max(settling_far.values()) <= FAR_BAR,  # expected FALSE
        "n_per_class": n,
        "claim": "SYNTHETIC + CONDITIONAL. Separates the human MODEL from NAIVE canned shapes "
                 "(step/pulse/triangle/random) ONLY IF reflexes settle-to-plateau (the tail_slope "
                 "assumption -- UNKNOWN until real capture, rung 2). Does NOT bound a SETTLING adversary "
                 "(decayed-exp / ramp-hold / smart-settle pass the gate), a physical HIL rig (rung 4), or "
                 "a compromised host (FLIP-B). Engineering justification to build rung-2 capture, NOT a "
                 "separability result. poep_enabled stays False.",
    }


if __name__ == "__main__":  # pragma: no cover
    import json
    print(json.dumps(separability_report(), indent=2))
