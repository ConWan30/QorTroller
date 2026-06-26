---
type: synthesis
id: s-nqpv-arc-overall-assessment
title: NQPV Arc — Overall Assessment (cycles 28-36)
created: 2026-06-26T16:30:00Z
modified: 2026-06-26T16:30:00Z
phase: VSD-LOOP
status: final
confidence: certain
effort: 120
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: ["s-novel-fusion-m1-presence-assessment", "s-nqpv-defensibility-aligning-solution"]
---

# NQPV Arc — Overall Assessment

## What it set out to do

Make M1 (recency-bound human-presence proof) real and defensible: prove "a live human, on certified hardware, causally driving the game" — ideally without the screen-lobe privacy gate — and crucially, without overclaiming. It ran as VSD cycles 28→36 plus a real hardware capture campaign and a public SDK surface.

## What was built — a complete, honest vertical

| Layer | What it is | Status |
|-------|------------|--------|
| Sharpening (cycle-28) | screen-lobe gate dissolved via COUPLED_CLEAN (L9/PoCP, no camera) | shipped, default-off |
| Calibrated model (cycle-29) | graded weighted score; missing oracle abstains; single sub-grade oracle outvoted; separate disagreement_index; anti-GCAP by design | shipped |
| Study (cycle-31) | loader + adversary synthesizer + PILOT harness (TAR/FAR + ROC + anti-GCAP rail) | shipped |
| Persistence (cycle-33) | nqpv_cocapture_log + live co-capture | shipped, default-off |
| 1000 Hz corpus + adapter (cycle-35) | real N=10 human biometric corpus → human-positive records | shipped |
| Live p_L4 fix (cycle-36) | corrects NOMINAL-human under-crediting | shipped, default-off, safety-gated |
| Public surface | SDK VAPIPresenceProof + /player/presence-proof, advisory-marked | shipped |

Every layer is default-off, tested, and machine-labeled advisory. PV-CI held at 182 throughout; VSD chain at 37+ links, fully verified.

## The central achievement is epistemic, not just code

The arc's real value is what it refused to claim. It took a promising idea (multi-oracle presence fusion) and subjected it to honest measurement, which produced one load-bearing, empirically-established truth:

> The fusion separates humans from adversaries only when the presence oracles (PoEP + the coupled-retina screen witness) are live.

In every regime available today it cannot — and that is reported as an honest FAIL, not a green light.

This was then confirmed on real human data (cycle-35: 9/10 real sessions classify L4-NOMINAL, yet the study still FAILs in the l4l5l6-only regime because replay-class adversaries carry real human physics). That is the QorTroller thesis — verification over assertion — applied recursively to QorTroller's own newest layer.

## What's genuinely novel / valuable

- Screen-lobe-free presence (COUPLED_CLEAN) — a privacy-preserving presence path that ships regardless of the study outcome.
- The orthogonal-oracle + anti-GCAP architecture — graded fusion that defuses the banked L9 GCAP trap (human-TAR collapse), and the rail held in the regime that did separate.
- An honesty grammar made machine-readable — advisory/certified fields so a public endpoint can't be misread as a certified gate.

## Honest limitations (load-bearing — do not soften)

- N=1 human, N=10 sessions = feasibility, not a population/tournament claim. Breadth is the standing open lever.
- Adversaries are modeled (synthetic), not real captures → FAR measures fusion logic, not empirical real-world FAR.
- Presence oracles are not live → the regime that would certify can't actually run yet.
- Everything is advisory/default-off. Nothing here certifies eligibility.

## What verification-first caught along the way

The arc surfaced and correctly handled several things a less rigorous pass would have shipped silently: the 120 Hz-vs-1000 Hz structural capture flaw (degenerate biometrics), the dual-connection biometric blindness, the passport-gate loosening risk (why the live p_L4 fix is default-off), the lobe-conflation in the public endpoint, and a self-corrected VSD cycle transient. Each became a recorded finding, not a hidden bug.

## The one remaining unlock

Presence-oracle liveness — PoEP (gated on L6B N≥50 calibration) and the coupled-retina screen witness (camera hardware). Everything upstream of it now works, is tested, and is wired to consume it the moment it lands; the harness re-runs unchanged.

## Net

A mature, honest, end-to-end research-and-engineering arc: it built the full machinery to answer "is this a real human playing?", proved exactly what it can and cannot yet claim, and shipped every layer behind honest defaults. It did not deliver certification — and is admirably clear that it didn't. Its highest-value output is a measured, defensible map of the path to certification, with the single remaining gate (presence-oracle liveness) precisely identified and de-risked. For a protocol whose entire premise is "verification over punishment," this arc is that premise turned on itself — and passing.

---

**Verification at time of recording:** PV-CI 182, VSD harness PASS, public surface (VAPIPresenceProof + /player/presence-proof) advisory + default-off where appropriate, nqpv_cocapture_enabled=False, live p_L4 safety-gated.

**Related notes:** s-novel-fusion-m1-presence-assessment, s-nqpv-defensibility-aligning-solution, s-nqpv-study-corpus-harness-built
