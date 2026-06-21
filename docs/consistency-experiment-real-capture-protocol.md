# Consistency Experiment — Phase 2 Real-Capture Protocol (gold standard)

**Status:** SPEC. Hardware/operator/participant-gated (like MINIMAL_PAD). This is the
experiment that the synthetic Phase 1 cannot answer and that decides whether the
L9 × Trio-Retina consistency fusion is a deployable gate or a forensic-only
instrument. Companion: `docs/l9-retina-presence-consistency-fusion.md` §5, the Phase 1
harness `l9_presence/adversarial/`, and the synthetic result
`audits/consistency-experiment-synthetic-2026-06-21.md`.

> **Pre-registration discipline (read first).** All estimands, decision thresholds,
> sample sizes, and the kill criterion in §2 MUST be frozen **before** any capture and
> committed to git. No threshold is chosen or moved after seeing data. The synthetic
> run already showed the answer reduces to two numbers; this protocol measures them
> honestly or it is worthless.

## 0. Single-subject scope (N=1 elite) — CRITICAL, overrides the population framing below

For the first run the only elite player is the operator themselves (**N=1**). This is a
legitimate single-subject pilot, but it carries a hard asymmetry that governs every claim:

- **One subject can FALSIFY the gate, not VALIDATE it.** If retina falsely flags *this
  operator's* genuine elite play at a high rate, that is strong evidence the gate fails — if
  it cannot survive one elite player it will not survive the diverse tail → **KILL / strong
  negative**. If retina's FPR on this operator is *low*, that is **ENCOURAGING but cannot
  PASS** the gate; a population false-positive bound needs many elite players.
- All measured rates are **within-subject** (this operator, this controller, this game). They
  estimate *this operator's* retina FPR/TPR, not the population's.
- Therefore the first run's best-case outcome is **"not killed — proceed to multi-subject
  capture,"** never "gate validated." The ≥10-player / population thresholds in §2 and §7 are
  retained as the PASS bar for a *future* multi-subject run, not this one.
- **Single-subject confound to control:** with one person producing all five classes, the
  operator must not let knowledge of the class bias play (e.g. unconsciously playing
  "twitchier" when labelled PRO_SKILL). Capture PRO_SKILL and HUMAN_CLEAN as ordinary ranked
  sessions labelled *after* the fact by performance, not as performances *for* the camera.

## 1. The single decision question

Phase 1 proved (and a test pins) that the fusion's behaviour on the hard boundary is
fully determined by retina's trajectory ROC:

- **machine-assist catch rate ≈ `retina_tpr_aimassist`**
- **pro-skill false-accusation rate == `retina_fpr_proskill`** (by construction — presence is PRESENT for both aim-assist and elite play, so it adds zero discrimination there).

So Phase 2 measures exactly those two numbers **on real data**:
1. **`retina_tpr_aimassist`** — P(retina judges trajectory IMPLAUSIBLE | real aim-assist active).
2. **`retina_fpr_proskill`** — P(retina judges trajectory IMPLAUSIBLE | real elite genuine play). **This is the killer.**

Everything else (the contextual classes — BOT / relay / replay) Phase 1 already showed
the fusion handles; Phase 2 confirms them on real data but they are not the decision.

## 2. Pre-registered estimands, decision rule, and KILL criterion

**FROZEN 2026-06-21 — pre-registration.** These values are committed to git BEFORE any
capture exists. They MUST NOT be edited after data is collected — changing any of them
invalidates the pre-registration, and any run against changed thresholds must be declared
a new, separately-named experiment. The git history of this file is the immutability proof.

| Pre-registered quantity | FROZEN value | Rationale |
|---|---|---|
| TPR target (catch) | **≥ 0.80** | a gate that misses >20% of aim-assist windows is weak but arguable |
| FPR ceiling (elite false-accuse) | **≤ 0.02** | accusing >2% of elite-play windows is tournament-fatal |
| Players per class (multi-subject PASS run) | **≥ 10** | minimum for cross-subject generalisation; NOT required for the N=1 kill-test |
| Elite-play windows (PRO_SKILL) | **≥ 300** | Rule of Three: 0 FPs in 300 windows ⇒ 95% CI upper bound ≈ 1% |
| Game / controller | **NCAA CFB 26 / certified Edge (CFI-ZCP1)** | matches the validated Phase-G tier; transfer to other titles is out of scope |

**Decision rule (pre-registered):** the fusion is a **viable real-time gate** iff there
exists an operating point with **catch ≥ TPR-target AND elite false-accusation ≤ FPR-ceiling**,
with the FPR ceiling met at the **upper bound of its 95% CI** (not the point estimate).

**KILL criterion (pre-registered):** if no operating point satisfies both — specifically
if the elite-play false-accusation CI upper bound exceeds the FPR ceiling — the **gate
thesis is dead**. The honest outcome is then explicit: the fusion remains valuable as a
**forensic / adjudication instrument and a contextual disambiguator** (Phase 1 confirmed
that value), but it is **not** a real-time tournament gate. We say so and stop; we do not
move the threshold.

## 3. Capture matrix (5 classes, REAL)

All sessions captured with the bridge running, `RETINA_PERCEPTION_ENABLED=true`,
L6B/PoEP capture active, on the certified Edge, one labelled class per session.

| Class | Participant | Setup | Captured signals |
|---|---|---|---|
| `HUMAN_CLEAN` | ≥10 ordinary players | normal play, no assist | presence (PoEP challenge) + retina anomaly + L4 distance |
| `PRO_SKILL` | **≥10 elite players** (the hard recruit) | normal play, genuinely fast/aggressive | same — this is the false-positive measurement |
| `HUMAN_AIM_ASSIST` | ≥10 players | real, documented aim-assist active downstream of the controller, in an isolated research sandbox (§4) | same — the true-positive measurement |
| `HUMAN_RELAY` | ≥10 player+bot rigs | human passes the PoEP challenge; a bot drives play between challenges | same — confirms relay framing on real data |
| `BOT_FULL` | scripted rig | no human; scripted input | same — confirms no-human contextualisation |

**`PRO_SKILL` is the load-bearing, hardest-to-recruit class.** A protocol that captures the
other four but not enough genuine elite players has NOT run the experiment — it has skipped
the one measurement that matters. Do not declare a result without it.

## 4. Ethics, consent, privacy, dual-use (gating — non-optional)

This captures real human reflex/behavioural data and uses real cheat software. The same
lens that dropped the microphone surface (`TRACK1-LESSON-003`: BIPA / GDPR Art. 9 / CIPA
attach to capture-and-storage regardless of downstream use) applies here.

- **Informed consent** from every participant, naming exactly what is recorded and retained.
- **Derived metrics only.** Persist φ-sanitised features + per-window oracle outputs
  (presence verdict, retina anomaly_count, L4 distance) — **never raw biometric streams**.
  Retain the minimum needed to recompute the two rates.
- **Dual-use containment.** Real aim-assist runs in an **isolated, offline research sandbox**;
  no cheat software is developed, modified, or distributed — only existing documented tools
  are observed for **defensive measurement**. The captured cheat data is for this experiment
  only. Bridge runs with `CHAIN_SUBMISSION_PAUSED=true`; no on-chain writes.
- **Withdrawal + erasure** honoured (GDPR Art. 17), consistent with the protocol's existing
  consent rails.

## 5. Binding & labelling (experiment-only, by construction)

Controlled co-capture: each labelled session is a single participant, single class, single
time window on one `device_id`. Presence probes (`l6b_probe_log`), retina rows
(`retina_event_log`), and L4 (`records.pitl_l4_distance`) within that session window belong
to the same triple **by construction** — bind by `device_id` + session time-window. The
class label is the session's assigned class (operator-recorded, not inferred).

This deliberately does **not** require the production `record_hash` binding (the
`l6b_probe_log`-has-no-`record_hash` gap from the agent audit). That binding is a separate
§6 production-integration concern, gated on this experiment coming back viable.

## 6. Pipeline (reuses the Phase 1 harness)

Only the data source changes; the evaluator and engine are unchanged.

1. **New component:** `l9_presence/adversarial/real_sessions.py` — a loader that reads the
   captured DB rows for each labelled session window and assembles real `LabeledWindow`s
   (presence from PoEP/L6B rows, trajectory from `retina_event_log.anomaly_count`, L4 from
   `records.pitl_l4_distance`), with `provenance=REAL`, `provisional=False`.
2. **Reuse unchanged:** `signal_adapter.window_to_signals`, `presence_retina_consistency.assemble_consistency`,
   `consistency_eval.run_experiment` / `to_markdown`.
3. **Runner:** extend `scripts/run_consistency_experiment.py` with `--real --db <path>
   --sessions <labels.json>` (bypasses `synthetic_sessions.py`).
4. **Output:** `audits/consistency-experiment-real-<date>.md` + `.json` with the 5×6
   confusion, the two measured rates **with 95% CIs** (Wilson interval), and the
   pre-registered decision-rule evaluation (PASS / KILL).

## 7. Sample size & power

- To bound `retina_fpr_proskill` ≤ 0.02 at 95% confidence you need enough elite-play windows
  that the Wilson upper bound clears the ceiling — with a low observed FP count, **≥300
  windows** (Rule of Three gives ~1% upper bound at 0 FPs in 300). Capture more if early FPs
  appear.
- For `retina_tpr_aimassist` ≥ 0.80, a few hundred aim-assist windows give a tight enough CI.
- **Single-subject (N=1) first run:** spread the ≥300 elite windows across **many distinct
  sessions / days** for this one operator, so the within-subject rate is not a single sitting's
  idiosyncrasy. This bounds *this operator's* retina FPR only. The **≥10-distinct-players** bar
  is retained for the future multi-subject PASS run; until then no cross-subject (population)
  claim may be made (the N=37/3-player thinness this whole arc has criticised applies here too).

## 8. Analysis discipline

1. Capture all five classes blind to the running rates (operator labels by session, does not
   tune anything mid-capture).
2. After capture closes, run the evaluator **once**. Compute the two rates + CIs.
3. Evaluate the **pre-registered** decision rule. Record PASS or KILL verbatim.
4. No threshold changes, no class exclusions, no re-runs-until-green. If the result is KILL,
   the artifact says KILL and the fusion's home is forensic-only.

## 9. Outputs

- `audits/consistency-experiment-real-<date>.md` / `.json` (the result).
- A per-class operator attestation in the `audits/cco-phase-g-*-attestation` style
  (participant counts, consent confirmation, sandbox confirmation, the two rates + CIs).
- A one-line CLAUDE.md NOTE recording PASS/KILL and the measured rates.

## 10. Threats to validity (state honestly in the result)

- **Transfer:** rates are for one game + the certified Edge. Other titles / controller
  classes are unmeasured.
- **Adversary adaptation:** once trajectory-authenticity is the gate, aim-assist vendors add
  humanisation; a PASS today is a moving target, not a permanent wall.
- **Elite-sampling bias:** ≥10 elite players is a floor; pro trajectory diversity is large
  and a clean result on 10 does not guarantee the tail.
- **Synthetic ≠ real cheat:** Phase 1 modelled oracle behaviour; only this protocol observes
  real aim-assist signatures, which may be easier or harder than modelled.

## 11. Decision tree (what each outcome means)

**N=1 first run can only land in the first two boxes — PASS is reserved for a future
multi-subject run (per §0).**

- **ENCOURAGE — not killed** (N=1 first run, this operator's elite FPR is low and catch is
  high): the gate is *not falsified*. Proceed to recruit ≥10 elite players for a real PASS
  attempt. This is the best outcome available to the single-subject run; it is NOT validation.
- **PASS** (multi-subject only: operating point meets TPR-target AND FPR-ceiling-at-CI-upper-bound
  across ≥10 elite players): the disagreement gate is real on this tier — proceed to the
  production `record_hash` binding and FSCA-lattice integration (§6), still default-OFF behind
  operator activation.
- **KILL** (no such operating point): the gate thesis is dead on the evidence. The fusion's
  honest, retained value is **forensic / adjudication + contextual disambiguation** (Phase 1
  confirmed). Document KILL, do not deploy as a gate, do not move the threshold.
- **INCONCLUSIVE** (insufficient elite N / wide CIs): not a result. Capture more `PRO_SKILL`
  before claiming anything.
