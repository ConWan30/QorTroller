# WHAT_IF: W1-002 — Separation Ratio Calibration Deadline

[VAPI:Phase166:VAPI_WHAT_IF.md:MEASURED]

## Classification

| Field | Value |
|-------|-------|
| Layer | W1 (Protocol Risk) |
| Status | PARTIALLY RESOLVED — touchpad_corners 0.569 BELOW 0.70 gate (N=20); free-form 0.417 BLOCKER |
| First identified | Phase 108 (2026-03-10) |
| Breakthrough | Phase 143 (2026-04-02) — touchpad_corners reached 1.261 at N=11 |
| Degraded | Phase 166 — N=20 convergence shows 0.569 (below 0.70 gate) |

## Failure Mode

Inter-person separation ratio remains below the tournament gate if touchpad
recapture sessions are indefinitely deferred. Token launch is gated on ratio
above `min_separation_ratio` — non-negotiable. All tournament readiness conditions
remain unmet until this resolves.

## Current State [VAPI:Phase166:MEMORY.md:MEASURED]

| Measurement | N | Ratio | Status |
|------------|---|-------|--------|
| touchpad_corners (2026-04-05) | 20 | **0.569** | BELOW 0.70 GATE |
| touchpad_corners (2026-04-02) | 11 | 1.261 | SUPERSEDED (thin N) |
| Full corpus free-form (2026-03-29) | 127 | 0.417 | BLOCKER |

**Trend:** N=11→1.261, N=14→0.789, N=20→0.569 — converging downward.

**Root cause:** P1 non-stationary across days. Old P1 sessions cluster near P2 centroid;
new P1 sessions cluster near P3 centroid. P1 intra-player variance range=[1.661, 4.410].

## Active Path Forward

mixed_biometric_probe (Phase 166) activates all 13 features across 4 segments:
- 30s touchpad_corners
- 30s trigger_sequence
- 30s button_sequence
- 30s stick_sweeps

Goal: stabilize P1 sessions with full-feature capture to reduce intra-player variance.
Minimum 3 sessions per player needed before analysis is possible.

## Invariants

- min_separation_ratio: 0.70 (Phase 166 configurable gate, was hardcoded 1.0)
- Token launch gated on separation ratio confirmed above gate — non-negotiable
- Free-form gameplay sessions do NOT improve ratio (WIF-009 CONFIRMED)

## Related Pages

- [[separation_ratio]]
- [[l4_thresholds]]
- [[phase_166]]
- [[w1_009_freeform_plateau]]
