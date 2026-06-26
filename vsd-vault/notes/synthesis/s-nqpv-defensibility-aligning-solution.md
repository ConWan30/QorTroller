---
type: synthesis
id: s-nqpv-defensibility-aligning-solution
title: NQPV defensibility — the qualifying solution: replace the conjunctive string-match tree with a CALIBRATED weighted-disagreement SCORE gated on a measured human-TAR/adversary-FAR ROC, preserving the screen-lobe-dissolving seam + disagreement-as-anti-cheat-signal as the novel use-case
created: 2026-06-26T16:00:00Z
modified: 2026-06-26T16:00:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 90
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

The aligning solution for the half of grok's NQPV that [[s-novel-fusion-m1-presence-assessment]] found
DOESN'T qualify (RETINA-EXCL-2 defensibility). The seam (the SHARPENING) was incorporated as-is +
default-off (`38b62c6a`); this cycle modifies only the DECISION LOGIC, per the fusion's initial
purpose, so the whole NQPV becomes a qualifying presence solution. Builds on
[[s-trio-retina-exclusive-presence-layer]].

INITIAL PURPOSE (preserved verbatim): "a verified human on certified hardware generating real
physics-driven input that causally drives the game, under consent." The seam — CCO (hardware tier) +
Retina/L9 (incl. COUPLED_CLEAN, L9/PoCP, NO screen) + PoEP + L4/L5/L6 + crypto binding + consent, with
LIVE_COHERENT (screen) ADDITIVE — STAYS. That reframe (RETINA-EXCL-1 dissolved) is the novel use-case
and is left untouched.

THE PROBLEM (V-checked in novel_presence_fusion.py): `fuse()` is a binary CONJUNCTIVE string-match
tree ("fail at least one layer"). With sub-grade oracles (L4 EER ~29%, L9 "did not generalize"), any
single oracle's false-negative rejects a real human -> maximizes human false-reject. That IS the
banked GCAP trap (human TAR 0.806 -> 0.581 when layers were stacked). And it ASSERTS defensibility
rather than MEASURING it. The hard side of M1 was never catching bots; it is passing real humans at
grade -- conjunctive fusion makes that side worse.

THE QUALIFYING SOLUTION (modify the decision logic; keep the seam):

  1. CALIBRATED WEIGHTED-DISAGREEMENT SCORE (replaces the conjunctive tree). Presence becomes a graded
     score = weighted combination of per-oracle (signal, confidence, calibrated weight). Each oracle
     casts a GRADED vote, not a binary kill, so a single sub-grade oracle's miss is OUTVOTED, not
     fatal -- directly fixing the human-reject trap. Only CATEGORICAL conditions stay HARD gates:
     hardware-class FAIL (CCO) and consent-revoked -> immediate non-pass regardless of score (those
     are policy/integrity, not graded presence evidence).

  2. SPLIT THE TWO OUTPUTS. (a) the PRESENCE verdict = calibrated score vs a measured threshold;
     (b) the DISAGREEMENT surface (oracles diverging) becomes a SEPARATE evolutionary anti-cheat
     signal that INFORMS (flags for review / adapts weights) but does NOT auto-reject a human. This
     preserves the seam's novelty (disagreement = the novel anti-cheat axis) while making the presence
     verdict defensible -- they were conflated in the prototype.

  3. THE MEASURED STUDY = RETINA-EXCL-2 GENERALIZED TO THE FUSION. Compute the fused score's ROC on a
     real corpus: human positives + adversary negatives (bot / macro / relay / replay / modified-HW).
     Choose the operating threshold that hits a DEFENSIBLE human-TAR AND adversary-FAR SIMULTANEOUSLY.
     MANDATORY anti-GCAP rail: the fused human-TAR MUST be >= the best single oracle's standalone
     human-TAR -- if fusion lowers the human pass-rate, it is rejected (that is the exact L9/GCAP
     failure, made a hard gate on promotion). Weights + threshold come from this study (data), never
     hardcoded constants. Promotion to certifying is gated on this envelope; until then the verdict
     stays advisory + default-off.

  4. KEEP THE SHARPENING. COUPLED_CLEAN (L9, no screen) remains an accepted, weighted presence input ->
     RETINA-EXCL-1 stays dissolved. LIVE_COHERENT (screen) is just one more weighted input when present.

HOW TO REITERATE THE CODE (concrete, per the V-check of fuse()):
  - Add per-oracle weight + confidence to FusedGamerPresenceProof, plus `presence_score: float` and
    `disagreement_index: float`.
  - Replace the elif string-match tree with: hard gates (cco FAIL, consent_revoked) -> weighted score
    over present oracles (missing oracle = abstain, not auto-fail) -> threshold -> verdict; compute
    disagreement_index separately.
  - Wire the REAL oracle feeds (CCO via cco_poep_bridge, PoEP, L9/PoCP) -- they are placeholders today,
    so the seam currently can't emit a real fused verdict at all.
  - Load weights + threshold from calibration/config (set by the study), not literals.

HONESTY RAILS: DIRECTION, not a build -- the calibrated model + study are future operator-gated work.
The seam stays as-is + default-off until the study sets the operating point; no certifying use until
the measured human-TAR/adversary-FAR envelope + the anti-GCAP rail pass. No FROZEN-v1 / 228B PoAC /
chain. The split (graded score for presence; disagreement as a separate anti-cheat signal) is what
lets the same NQPV keep its novelty AND become defensible. Related:
[[s-novel-fusion-m1-presence-assessment]].
