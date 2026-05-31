# Phase 240 Step 4 — [SPEC TITLE HERE]

**Status:** TEMPLATE — fill in then invoke `spec-to-ship` agent.
**Phase context:** Phase 240+ candidate per `CLAUDE.md` roadmap_post_stage_1.
**Prerequisite gates** (must read TRUE before this spec ships):
- [ ] GIC_100 deposited (✅ already done — head `0x0e9d453d…`)
- [ ] N≥50 calibration sessions per player (currently P1=13, P2=10, P3=14 — **NOT YET MET**)
- [ ] Stage 1 graduation activated (currently `STAGED_GRADUATION_ENABLED=true` pending API call)
- [ ] Any Phase-240-specific gate listed below

> **Honest warning:** Phase 240's L6-Response per CLAUDE.md is hardware+corpus-gated.
> Do NOT activate `L6_CHALLENGES_ENABLED` without N≥50 per player. This template is
> structured so the spec-to-ship agent will refuse to run when the gate isn't met.

---

## Goal

> One paragraph, plain English. What does this step accomplish? Why now?
> What's the user-visible behavior change?

[FILL IN. Example: "Add a sub-perceptual haptic test-pulse to the
DualSense Edge adaptive trigger during normal gameplay, capture the
gamer's reflex response in the 80-280 ms window, and surface the
per-stimulus reaction-time delta as a new L6-Response advisory layer
in the humanity_probability formula. Activation gated on
`L6_RESPONSE_ENABLED=true` AND per-player N≥50 calibration. Default
OFF."]

---

## Acceptance Tests

> Each bullet is a real test case the agent will write. Format:
> `[T-PHASE240-S4-N: <one-line test name>]`. Be specific about what
> assertion the test makes. Avoid "should work" — name the contract.

- [ ] [T-PHASE240-S4-1: <name>] — <one-line assertion>
- [ ] [T-PHASE240-S4-2: <name>] — <one-line assertion>
- [ ] [T-PHASE240-S4-3: <name>] — <one-line assertion>
- [ ] [T-PHASE240-S4-4: <name>] — <one-line assertion>
- [ ] [T-PHASE240-S4-5: <name>] — <one-line assertion>
- [ ] [T-PHASE240-S4-6: dormant-OFF default] — agent + tests pass with
      L6_RESPONSE_ENABLED unset; no behavior change observed
- [ ] [T-PHASE240-S4-7: gate-refuses-below-N50] — when any player has
      <50 calibration sessions, the activation path raises a clear
      error (no silent activation)

---

## Files Touched

> ALL files the agent may create or edit. ANY other file = novelty signal
> (agent pauses + asks). Be exhaustive — under-specifying causes pauses.

**NEW:**
- `bridge/vapi_bridge/<l6_response_or_similar>.py`
- `bridge/tests/test_<l6_response_or_similar>.py`
- `docs/phase-240-step-4-<topic>.md` (optional design doc)

**MODIFIED:**
- `bridge/vapi_bridge/config.py` — `+L6_RESPONSE_ENABLED` flag (default False)
- `bridge/vapi_bridge/<humanity_probability_aggregator>.py` — weight integration
- `scripts/vapi_invariant_gate.py` — `+INV-L6R-001/002/...`
- `CLAUDE.md` — recent-NOTE entry (one line)

---

## Regression Surfaces

> Test suites that MUST stay green. Include the baseline pass count at
> the moment of spec authorship — the agent compares against this number.
> Use the form: `<suite name>: <baseline> passing[, <known-pre-existing-failures>]`.

- `bridge/tests/test_replay_pre_processor.py` : 11 passing
- `bridge/tests/test_replay_witness_generator.py` : 35 passing
- `bridge/tests/test_replay_proof_pipeline.py` : 21 passing
- `bridge/tests/test_replay_curator_hook.py` : 11 passing
- `bridge/tests/test_replay_groth16_prover.py` : 4 passing
- `bridge/tests/test_replay_live_session_hook.py` : 10 passing
- `bridge/tests/test_replay_posr.py` : 15 passing
- `contracts` Hardhat suite : 743 passing, 13 pre-existing failures (DO NOT regress)
- PV-CI gate (`scripts/vapi_invariant_gate.py`) : 167 invariants pass

---

## CLAUDE.md Note

> One single line, ≤500 chars, dropped into the recent-NOTE block at top
> of CLAUDE.md. Follow the existing NOTE convention (emoji + headline +
> bold key terms + memory pointer). Drop the "memory:" pointer at the
> end if a new memory file is being written.

[FILL IN. Example: "NOTE: 🤚 PHASE 240 STEP 4 — L6-RESPONSE HAPTIC LAYER
SHIPPED 2026-XX-XX — N=X commit arc adds sub-perceptual adaptive-trigger
test-pulse + 80-280ms reflex-band capture; default OFF
(`L6_RESPONSE_ENABLED=false`); refuses activation below N≥50 per player;
+M new tests; PV-CI 167→XXX (+INV-L6R-001/...). Memory:
`project_phase_240_step_4_l6_response_shipped`."]

---

## Honesty Rails

> Spec-specific defer-not-fabricate constraints. Inherited from the
> agent's universal rails, plus any specific to this step.

- L6-Response MUST default to OFF (`L6_RESPONSE_ENABLED=false`).
- Activation MUST refuse when any player has <50 calibration sessions
  (raise a clear error citing the corpus state — never silently fall
  through).
- Sub-perceptual amplitudes only (≤60/255). Higher amplitudes would
  affect play experience.
- No haptic command may be issued during AN active PS5-haptic event
  (avoids conflict per the L6-Passive design note in CLAUDE.md).
- Per-player baselines computed from GIC_100+ corpus only — no synthetic
  baselines.

---

## Operator-Fired Steps (OUT of agent scope)

> What stays outside the spec-to-ship loop. Agent does NOT execute these.

- Initial corpus expansion to N≥50 per player (requires real gameplay
  sessions — gamer-time, not agent-time).
- Production `L6_RESPONSE_ENABLED=true` flag flip in `.env` + bridge
  restart (operator decision).
- Any on-chain anchor of L6-Response baselines (out of scope; future arc).

---

## Notes for the agent

- This template was hand-authored. If anything below is ambiguous, **pause
  + ask**. Do not invent. Cluster-E-style design decisions are NOT yours
  to make.
- If during implementation you discover a missing acceptance test (e.g.,
  a corner case the spec didn't cover), surface it via AskUserQuestion;
  don't add it silently.
- Phase 240 Step 4 is forward-looking. If prerequisite gates aren't met,
  the loop should refuse to proceed past Step 1 and surface the gate.
