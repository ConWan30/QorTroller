# VAPI Separation Decision Framework
## Pre-Capture Decision Protocol · Phase 208 · 2026-04-13

**Current State (2026-04-13):**
- tremor_resting: **1.349** (N=15, P1=5/P2=5/P3=5) — ratio above 1.0 but all_pairs_p0_ok FAILS (P1vP3=0.039)
- touchpad_corners: 0.728 (N=35) — BLOCKER
- P1+P2 two-player analysis in progress — assessing if two-player corpus clears all_pairs gate
- WIF-039: CorpusRatioRegressionGuard Phase 208 candidate (see VAPI_WHAT_IF.md)

**Purpose:** This document specifies the decision tree that governs what action to take
based on tremor_resting capture results with Phase 205 AccelTremorFFT active. It must
be read and understood before the first tremor_resting capture session.

**Authoritative tool:** `python scripts/analyze_interperson_separation.py --stratify-by-session-type`

---

## Decision Gate A — Run Stratified Analysis First

Before capturing additional tremor_resting sessions for any player, run:

```bash
python scripts/analyze_interperson_separation.py --stratify-by-session-type
```

This produces a per-type breakdown (ratio, P2vP3 distance, P3 intra_mean, P3 intra_std)
and a diagnostic verdict. The diagnostic verdict determines which path below applies.

---

## Decision Tree

```
RUN --stratify-by-session-type
        |
        v
[DIAGNOSIS: SESSION_TYPE_CONTAMINATION]          [DIAGNOSIS: GENUINE NON-STATIONARITY]       [DIAGNOSIS: MIXED / insufficient data]
cross-type range > 0.5                            cross-type range <= 0.5 OR                  Neither criterion clearly met
AND within-type mean < 0.8                        within-type mean >= 0.8
        |                                                  |                                          |
        v                                                  v                                          v
Path A (below)                                    Path B (below)                              Path C (below)
```

---

## Path A — SESSION_TYPE_CONTAMINATION

**What this means:** P3's centroids differ significantly across session types. When all
session types are pooled, the global centroid sits between them, inflating intra-player
variance. P3 is likely stable *within* each individual probe type.

**Decision:** PROCEED with tremor_resting captures. The correct analytical workflow is
always `--session-type tremor_resting` (never pooled). The separation analysis
for tournament gate must be run per-type.

**Action sequence:**
1. Capture tremor_resting sessions: P1, P2, P3 (minimum 3 each; target 5+ each)
2. Run: `python scripts/analyze_interperson_separation.py --session-type tremor_resting`
3. Check separation ratio and P2vP3 distance
4. If ratio > 1.0 AND all_pairs_above_1=True → proceed to SeparationRatioRegistry.sol commit
5. If ratio < 1.0 → capture 3 more sessions per player and re-run

**Note:** Never commit to SeparationRatioRegistry.sol using the pooled corpus ratio (0.060
full corpus, 0.728 touchpad_corners+tremor_seed mixed). Only per-type ratios are defensible.

---

## Path B — GENUINE PHYSIOLOGICAL NON-STATIONARITY

**What this means:** P3's biometric variance is high even *within* individual session types.
Adding more sessions of the same type will not tighten P3's centroid — the variance reflects
real physiological variability (e.g., tremor intensity varies day-to-day).

**Decision:** DO NOT proceed to SeparationRatioRegistry.sol commit. Activate
TremorRestingConvergenceOracle monitoring (Phase 202) and watch the velocity trend.

**Action sequence:**
1. Capture tremor_resting sessions (P1, P2, P3 — minimum 3 each)
2. Run `analyze_interperson_separation.py --session-type tremor_resting` after each batch
3. Insert snapshot: `POST /agent/tremor-convergence-snapshot` (manual trigger with measured ratio)
4. Monitor `GET /agent/tremor-convergence-status`:
   - `convergence_stable=True` (velocity >= 0 for 2 consecutive) → proceed to Path A actions
   - `non_convergence_detected=True` (consecutive_negative >= 5) → **HARD STOP** (see below)

**NON-CONVERGENCE HARD STOP (non_convergence_detected=True):**
When `non_convergence_detected=True` fires:
- Halt tremor_resting captures for P3 immediately
- The RATIO_VELOCITY_NEGATIVE ORPHAN rule in FleetSignalCoherenceAgent blocks
  VHP MINT_QUORUM=0.80 — this is the correct behavior
- File a WIF entry describing P3's non-stationarity with:
  - Current ratio, velocity trend, consecutive_negative count
  - Hypothesis: physiological cause (medication change, sleep, injury) vs. protocol artifact
- Do NOT proceed to SeparationRatioRegistry.sol commit while non_convergence_detected=True

**Resolution options (NON-CONVERGENCE state):**
- Option R1: Capture P3 sessions across multiple calendar days (min 3-day spacing) to
  test whether variance is day-dependent or persistent
- Option R2: Add a new structured probe type with higher discriminative signal for P3
  (e.g., per-finger grip pressure pattern if future hardware supports it)
- Option R3: Accept that P3 requires a larger N to stabilize (capture N=15+ sessions,
  then re-evaluate)

---

## Path C — MIXED / INSUFFICIENT DATA

**What this means:** The stratified analysis cannot clearly diagnose the root cause
because there are fewer than `_N_NONCONV_THRESHOLD=5` entries per session type
for at least one player.

**Decision:** Capture more sessions before making a trajectory decision.

**Action sequence:**
1. Capture 3 tremor_resting sessions per player (P1, P2, P3)
2. Re-run `--stratify-by-session-type`
3. If diagnosis is now clear → follow Path A or Path B
4. If still MIXED after 5+ sessions per player → default to Path B (conservative)

---

## Capture Protocol — Tremor Resting Sessions

**Prerequisites:**
- Phase 205 AccelTremorFFT must be active (bridge running with `ACCEL_TREMOR_FALLBACK_ENABLED=true`)
- Controller at rest (do not touch any buttons/sticks during capture)
- Place controller flat on table or hold in resting grip — minimal arm movement

**Commands:**

```bash
# Player 1
python scripts/capture_session.py --duration 30 \
  --notes "tremor_resting P1 post-Phase205-AccelTremorFFT" \
  --output sessions/human/terminal_cal_P1/tremor_resting_P1_001.json

# Player 2
python scripts/capture_session.py --duration 30 \
  --notes "tremor_resting P2 post-Phase205-AccelTremorFFT" \
  --output sessions/human/terminal_cal_P2/tremor_resting_P2_001.json

# Player 3
python scripts/capture_session.py --duration 30 \
  --notes "tremor_resting P3 post-Phase205-AccelTremorFFT" \
  --output sessions/human/terminal_cal_P3/tremor_resting_P3_001.json
```

The filename stem must start with `tremor_resting` — `_detect_session_type()` in
`analyze_interperson_separation.py` infers the probe type from the filename stem.

**Post-capture analysis:**

```bash
# Run stratified analysis
python scripts/analyze_interperson_separation.py --stratify-by-session-type

# Run tremor_resting-only separation analysis
python scripts/analyze_interperson_separation.py --session-type tremor_resting

# Check convergence status (requires bridge running)
# GET /agent/tremor-convergence-status
```

---

## Commitment Gate (before SeparationRatioRegistry.sol)

All of the following must pass before committing a ratio to `SeparationRatioRegistry.sol`:

| Condition | Check | Status |
|-----------|-------|--------|
| separation_ok | ratio >= 1.0 (per-type, not pooled) | Run preflight |
| all_pairs_p0_ok | all_pairs_above_1=True | Run preflight |
| biometric_ttl_ok | credential_age_days < 90.0 | Run preflight |
| convergence_stable | TremorRestingConvergenceOracle: velocity >= 0 for 2 consecutive | GET /agent/tremor-convergence-status |
| non_convergence_clear | non_convergence_detected=False | GET /agent/tremor-convergence-status |

All five conditions must be True simultaneously. The tournament preflight (POST /agent/run-tournament-preflight)
checks the first three. The convergence conditions must be checked separately via the
TremorRestingConvergenceOracle endpoint until they are wired into the preflight gate.

---

## Invariants

- Pooled corpus ratio (0.060 full corpus, 0.728 mixed types) is NEVER the tournament gate metric
- Per-type separation analysis is the correct and only defensible measurement method
- `non_convergence_detected=True` is a HARD STOP — never override without documented diagnosis
- SeparationRatioRegistry.sol commit requires ALL FIVE conditions above, not just ratio > 1.0
