# P-WAVE-0 — synthetic waveform-shape separability (FLIP-A ladder rung 3, 2026-07-15)

**De-risk before touching the capture layer.** The flip splits into FLIP-A (host-trusted presence vs
external macros — the only path earnable without silicon) and FLIP-B (device-attested, needs firmware/SE
— hardware-gated). Target: **FLIP-A** (grok round-21). Its ladder needs waveform-shape as a discriminator.
Before wiring the capture change to store raw waveforms (rung 2), P-WAVE-0 asks the cheap question first:
**does the SHAPE of the post-fire IMU reflex curve separate a biomechanical response from a canned macro
at all?** If not, storing real waveforms buys nothing.

## Method
`l9_presence/poep_waveform_shape.py` — a **physics-motivated shape gate** (NOT a fitted ML model; grok
round-16 killed offline scalar models). A human involuntary grip-jerk is modelled as an underdamped
second-order response (bounded-jerk rise, overshoot, damped settle, band-limited); canned macros as
step / rectangular pulse / linear triangle / in-band random. Six shape features per curve — `rise_samples`,
`overshoot_ratio`, `rise_sign_changes`, `max_jerk`, `hf_ratio`, `tail_slope` — with round human-physics
thresholds (not fitted to the synthetic data).

## Result — NAIVE canned shapes separable, **conditional on settle-to-plateau** (demoted per grok round-22)
The honest, narrow result is **not** "shape separates macros." It is:

> **Textbook underdamped step response ≠ NAIVE canned shapes (step/pulse/triangle/random) — IFF reflexes
> settle-to-plateau, which is UNKNOWN until real capture.** Shape does **NOT** bound a *settling* adversary.

| naive class | passes gate (FAR) | | settling adversary (the LIMIT) | passes gate (FAR) |
|---|---|---|---|---|
| macro_step | 0.00 | | adv_ramp_hold | **0.34** |
| macro_pulse | 0.00 | | adv_decayed_exp | **0.11** |
| macro_triangle | 0.00 | | adv_smart_settle | **0.64** |
| macro_random | 0.00 | | | |
| human (model) FRR | 0.027 | | | |

`naive_canned_separated = True` (human FRR ≤ 0.10 **and** worst naive FAR ≤ 0.05).
`shape_bounds_settling_adversary = **False**` — the harness reports this explicitly, not hidden.

**Why the demotion (grok round-22, circularity attack — held):** the first pass failed the triangle
(FAR 0.58); adding `tail_slope` closed it — but that feature kills *the triangle generator*, not
"macros can't look human." grok constructed settling non-reflex shapes (decayed-exp → plateau, ramp-hold,
smart-settle) that **sail through** the gate (FAR up to 0.64). So the gate separates the four *self-authored
naive templates*, not shape in general. The human model is also idealized (forced overshoot, smooth rise,
settles by construction) → the low FRR **overstates** how distinctive real reflexes are.

## Honest caveats — caveat 1 is now the RESULT CONDITION, not a footnote
1. **Settle-to-plateau is the load-bearing conditional, not an aside.** The entire triangle separation (and
   thus the PASS) hinges on `tail_slope`, which presumes a real grip reflex settles to a raised plateau. If
   real reflexes **relax back to baseline** (equally physical — stretch reflex + relaxation), then either
   keep `tail_slope` → human FRR blows up, or drop it → triangle FAR returns. **This is the single empirical
   question rung 2 (real waveform capture) must answer.**
2. **Does NOT bound a settling adversary.** decayed-exp / ramp-hold / smart-settle pass the gate (FAR ≫ 0.05).
   Shape alone is therefore **insufficient** for FLIP-A; it needs the settle-vs-baseline resolution + a
   multi-feature model + force-challenge device-auth + catch trials.
3. **Synthetic.** Both human and macros are models. Real Edge reflexes (co-contraction, gravity/posture,
   multi-peak, partial relaxation, pad coupling) are not modelled.
4. **Not HIL-tested** (rung 4, rig-gated) and **not FLIP-B** (a compromised host replaying a real waveform
   passes trivially — firmware/SE territory).

## Conclusion + next
P-WAVE-0 shows **textbook-underdamped ≠ naive canned**, **not** that waveform shape is a robust FLIP-A
discriminator. That is still enough **engineering justification** to build rung 2 (capture + store the raw
post-fire IMU window, hashed into the candidate commitment, consent-bound, gitignored) — **to TEST the
settle-to-plateau assumption on real reflexes**, not because separability is proven. Rung 2 is rig-gated;
rung 4 (the HIL rig) is the real adversarial test. `poep_enabled` / `L6B_ENABLED` / `L6_CHALLENGES_ENABLED`
stay **False**. 6 P-WAVE-0 tests green; PV-CI 183; no chain/FROZEN/PoAC edit.

## Rung-2 FIRST CLEAN LIVE RESULT (2026-07-16, registered Edge) — caveat 2 answered directionally
First real reflex-waveform capture on the registered Edge (`--sharp`: single 120ms jolt, 900ms window →
clean stimulus-free tail). Aggregates only; per-reflex curves are operator biometric (gitignored). N=8
challenges, all felt + reacted (class HUMAN, peaks 1.4k–4.4k LSB); 6/8 live-verify PASS.

**The settle-vs-baseline answer (P-WAVE-0 caveat 2) — DEMOTED per grok round-24
(`docs/a2a/poep/round-24-grok-rig-findings.txt`):** of 7 determinate reflexes —
**settled=4 · slight_drift=3 · returning=0**; median tail_slope **−0.004** (≈ flat). **Zero return-to-baseline.**
Honest read: settle-to-plateau is **NOT FALSIFIED** on N=7 one-session (returning=0 is interesting) — but it is
**NOT ESTABLISHED**. The shape path stays **alive under condition, not proven**. This is a *directional
one-session hint*, not a population or protocol claim. Bankable beyond a hint needs ≥3 independent sessions
on this Edge + ≥2–3 operators + ≥30 determinate tails; protocol-grade needs ≥50 usable / ≥5 operators. Do
NOT write "the settle assumption holds."

**Three banked rig MEASUREMENT findings (FLIP-A ladder inputs — none freeze a threshold):**
1. Settle-to-plateau **not falsified, not established** (returning=0, N=7) — shape path alive under condition.
2. **The [80,300] ms band's UPPER bound is a DATA-QUALITY filter, NOT a security gate** (grok round-24). A
   macro can sample any in-band latency (A-RAND/A-JITTER FAR≈1 on the band alone), so the ceiling never was
   the anti-bot mechanism — security is nonce schedule + silent pre-fire + shape + catch-trials + (later)
   force-binding. Genuine surprise reactions ran 216–318 ms (one failed by **1 ms** at 301 ms), so the 300 ms
   ceiling is currently **wrong for surprise-mode**. Recalibrate the ceiling by a PRE-REGISTERED rule
   (`min(cap, ceil(p95 + fixed_margin))`, margin fixed first, p95 from HELD-OUT sessions only) — not post-hoc
   widening. Until N suffices, treat the upper band as soft QA / REPORT, not a hard reject. (Lower bound =
   too-fast = pre-press stays a real security edge.)
3. **Shape gate is a MEASUREMENT channel, not a gate, at N≈8** (0.0 real-data pass — the synthetic
   damped-oscillator model does not transfer to real reflexes). Keep extracting the 6 features + tail class on
   every challenge; do NOT hard-reject on shape or fit PASS/FAIL cuts until a multi-session/multi-operator real
   distribution is banked.

**Honest next move (grok round-24): REST-until-more-rig-data.** Everything that freezes bands or shape
thresholds is rig-gated (more sessions on this Edge + ≥2–3 operators; ≥50 usable surprise rows before a
presence floor is credible). Do not over-build tooling on N=8.

**Rig-hardware note:** the Edge adaptive-trigger actuator jammed mid-session (RIGID went unfelt); recovered
under vigorous PULSE and then fired reliably on brief `--sharp` jolts. Reliable-feel default is PULSE +
sustained re-issue (`.\scripts\poep_live.ps1`); clean-shape is `--sharp` (`-Sharp`) with the 900 ms window.
`poep_enabled` stays False.
