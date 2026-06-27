---
type: synthesis
id: s-nqpv-defensibility-study-scope
title: NQPV defensibility study scope — the measured human-TAR/adversary-FAR ROC that sets the certified operating point (or honestly returns "fusion does not generalize"), gated on oracle co-capture + the anti-GCAP rail
created: 2026-06-26T16:50:00Z
modified: 2026-06-26T16:50:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 120
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

Scopes the study that promotes the cycle-29 calibrated NQPV model from advisory -> certifying (or kills
it honestly). Full plan: specs/nqpv-defensibility-study.md. Builds on
[[s-nqpv-defensibility-aligning-solution]]. This is the operator/data gate; the note records the scope,
the prerequisites, and the honest-outcome contract.

GOAL: find a defensible operating point (weights, threshold) where fused human-TAR AND adversary-FAR
meet a stated bar SIMULTANEOUSLY, subject to the MANDATORY anti-GCAP rail (fused human-TAR >= best
single-oracle TAR at matched FAR). Output is either a certified (weights, threshold) to inject via
fuse(weights=, threshold=) + an operator-gated nqpv_enabled promotion, OR the honest negative ("does
not generalize at this corpus" -> NQPV stays advisory). Both are valid; success is not the default.

BLOCKING PREREQUISITE: oracle CO-CAPTURE. fuse() is fed retina + PLACEHOLDERS for CCO/PoEP today
(oracle_panel.py), so the study cannot run until CCO (cco_poep_bridge), PoEP, and the full L9/PoCP
verdict are threaded into the seam + persisted per record, bound by device_id+record_hash+time-window.
That wiring is itself a build and the first dependency.

CORPUS (the binding confidence constraint, stated honestly):
  - Human positives: existing N=3 players / ~217 sessions -- but oracle co-capture must be added; N=3 is
    sub-grade for a population/tournament claim (breadth is the standing open lever; BCC harvests it).
  - Adversary negatives (sparse -- must be assembled, per-class FAR required): REPLAY (orphan-input, no
    PoEP) + MACRO/BOT (fails L4/L5/L6 + PoEP) -- synthesizable now; RELAY/cloud-bot (orphan-output) +
    MODIFIED-HW (CCO-FAIL hard-gated) -- more setup. Adversary realism bounds the FAR claim.

METHOD: run fuse() per session -> sweep threshold -> ROC (human-TAR vs adversary-FAR, per-class);
optimize weights (grid/logreg on per-oracle contributions); pick the operating point for target
(TAR>=T, FAR<=F); then the ANTI-GCAP RAIL as a hard go/no-go -- fused TAR at the operating point MUST
be >= the best single-oracle TAR, else REJECT (the exact L9/GCAP 0.806->0.581 failure). The rail is
the kill-switch.

TIERS: PILOT (existing N=3 + synthetic replay/macro -> directional ROC + anti-GCAP feasibility gate;
NOT a tournament claim) then FULL (breadth corpus + real adversaries -> grade claim; gated on breadth).

HONESTY RAILS: measurement-first; no promotion/certifying until the envelope + rail pass (operator
gate, HOLD). The pilot is feasibility, not certification. An honest negative is an expected-possible
outcome (the L9 prior). No FROZEN-v1 / 228B PoAC / chain; the harness is read-only over the corpus; the
model stays default-off advisory until promotion. The SHARPENING (COUPLED_CLEAN-as-presence,
screen-lobe dissolved) ships regardless of the study outcome -- it is the novel use-case, not contingent
on certification. Related: [[s-novel-fusion-m1-presence-assessment]], [[l9-presence-arc]].
