# NQPV Defensibility Study — RETINA-EXCL-2 generalized to the fusion

**Status:** scoped (not started). The operator/data gate for promoting the NQPV calibrated model from
advisory → certifying. Predecessor: VSD cycle-29 `s-nqpv-defensibility-aligning-solution`; model built
in `165d866c` (`novel_presence_fusion.py`).

## Goal
Determine whether the NQPV calibrated split-output model has a **defensible operating point**
`(weights, threshold)` where **fused human-TAR and adversary-FAR meet a stated bar simultaneously**,
subject to the **mandatory anti-GCAP rail** (fused human-TAR ≥ the best single-oracle TAR at matched
FAR). Output is one of:
- a **certified** `(weights, threshold)` injected via `fuse(weights=…, threshold=…)` + an operator-gated
  `nqpv_enabled` promotion; or
- an **honest negative** — no point clears the bar + rail → the fusion "does not generalize" at this
  corpus (matching the banked L9 prior) → NQPV stays advisory/default-off.

Both outcomes are valid results. The study is not expected to succeed by default.

## Prerequisite (BLOCKING) — oracle co-capture
Each session must record ALL oracle outputs together, bound by `device_id + record_hash + overlapping
time window`:
- CCO tier (hardware class), Retina/L9 verdict (COUPLED_CLEAN / LIVE_COHERENT / PLAUSIBLE / IMPLAUSIBLE
  / INACTIVE), PoEP present (bool), L4/L5/L6 ok (bool).

Today the seam is fed the retina result + **placeholders** for CCO/PoEP (`oracle_panel.py`), so the
study **cannot run** until the real feeds are co-captured (the "wire the real feeds" step). This is the
first dependency, and a build in its own right (thread CCO via `cco_poep_bridge`, PoEP, and the full
L9/PoCP verdict from `dualshock_integration` / session context into the seam + persist them per record).

## Corpus
**Human positives:** real human gameplay with full oracle co-capture. Existing: N=3 players / ~217
sessions (calibration corpus) — but oracle co-capture must be added. **Honest constraint:** N=3 is
sub-grade for a population/tournament claim (the presence reframe's "breadth is the open lever"; BCC
harvests provenance-clean breadth over time). The study's human-TAR confidence is bounded by N.

**Adversary negatives (the sparse side — must be assembled):**
- REPLAY — re-feed recorded human inputs with no live human (orphan-input; no PoEP). Synthesizable now.
- MACRO/BOT — scripted input (fails L4/L5/L6 biometric + forward-dynamics + PoEP reflex). Synthesizable.
- RELAY / cloud-gaming-bot (WormVision-class) — screen outcomes with no explaining input (orphan-output).
  Needs more setup.
- MODIFIED HARDWARE — CCO-FAIL (hard-gated; include to confirm the gate fires).
The adversary realism bounds the FAR claim; per-class breakdown is required (the fusion must catch each
class, not just the average).

## Method (offline harness over the co-captured corpus; read-only)
1. For each session run `fuse()` → `(presence_score, disagreement_index, oracle_contributions, verdict)`.
2. Sweep `threshold` → **ROC** (human-TAR vs adversary-FAR); per-adversary-class FAR breakdown.
3. Optimize `weights` (grid-search / logistic regression on the per-oracle contributions) to maximize
   the operating point — or report that no weighting clears the bar (honest negative).
4. Pick the operating `(weights, threshold)` for the target `(TAR ≥ T, FAR ≤ F)`.
5. **ANTI-GCAP RAIL (hard go/no-go):** compute each single oracle's standalone TAR at matched FAR; the
   fused TAR at the operating point **MUST be ≥ the best single-oracle TAR**. If not → REJECT (fusion
   isn't helping the human side — the exact L9/GCAP collapse, 0.806→0.581). This rail is the kill-switch.

## Acceptance bar
Define a target `(TAR, FAR)` for tournament-grade presence, anchored to the protocol's existing bars
(AIT separation 1.199 N=37; L9 human-TAR 0.806 standalone). "Qualifying" = a defensible simultaneous
`(human-TAR, adversary-FAR)` **and** the anti-GCAP rail passes. If no `(weights, threshold)` clears
both, the conclusion is the honest negative and NQPV stays advisory.

## Tiers
- **PILOT** (buildable once oracle co-capture exists): existing N=3 + synthetic adversaries
  (replay/macro) → directional ROC + the anti-GCAP rail check. A *feasibility gate*, NOT a tournament
  claim. Cheap, surfaces "does fusion even beat the best single oracle here?" early.
- **FULL:** breadth corpus (more humans via BCC harvest) + real adversaries (relay/mod-HW) →
  tournament-grade claim. Gated on breadth (the standing open lever).

## Deliverables
- A **study harness** (runner over the corpus → ROC + per-class FAR + optimized `(weights, threshold)`
  + anti-GCAP check + report). Read-only over the corpus; no chain/PoAC.
- A **report** (ROC, operating point, anti-GCAP result, per-adversary-class breakdown, corpus caveats).
- On pass: the certified `(weights, threshold)` + operator-gated `nqpv_enabled` promotion + (optionally)
  surface the proof in `/bridge/…` + sidecar (NOT 228B PoAC without ceremony). On fail: the
  honest-negative record.

## Sequencing
1. Wire real oracle feeds → co-capture (prerequisite build).
2. Assemble the adversary corpus (synthesize replay/macro now; plan relay/mod-HW).
3. Build the study harness.
4. Run **PILOT** → anti-GCAP feasibility gate.
5. If promising → **FULL** (breadth) → operating point → operator-gated promotion.

## Honesty rails
- The corpus (N=3 humans + sparse adversaries) is the binding confidence constraint; the claim is
  bounded by it. The pilot is feasibility, not certification.
- The anti-GCAP rail is the kill-switch; an honest negative is a valid, expected-possible outcome
  (the L9 prior says fusion may not generalize).
- Measurement-first: no promotion/certifying until the envelope + rail pass — operator-gated (HOLD).
- No FROZEN-v1 / 228B PoAC / chain. Harness is read-only; the model stays default-off advisory until
  promotion. The sharpening (COUPLED_CLEAN-as-presence, screen-lobe dissolved) is unaffected by the
  study outcome — it ships regardless as the novel use-case.
