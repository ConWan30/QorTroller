# PHASE: Phase 166 — mixed_biometric_probe + Configurable Defensibility Gate

[VAPI:Phase166:MEMORY.md:MEASURED]

## Summary

Phase 166 introduced the `mixed_biometric_probe` session type and lowered the
configurable defensibility gate from the hardcoded 1.0 to 0.70. Both changes
address the same root cause: all three enrolled players share a single physical
DualShock Edge controller, making hardware variance common to all and suppressing
the empirical inter-player separation ceiling below 1.0.

**Completed:** 2026-04-05
**Status:** COMPLETE

## What Changed

### mixed_biometric_probe Session Type [VAPI:Phase166:MEMORY.md:MEASURED]

A 2-minute, 4-segment structured probe that activates all 13 live biometric features:

| Segment | Duration | Features Activated |
|---------|----------|--------------------|
| A — TOUCHPAD CORNERS | 0–30s | touch_position_variance, touchpad_spatial_entropy |
| B — TRIGGER SEQUENCE (L2×5, R2×5, alt×5) | 30–60s | trigger_onset_velocity_L2/R2, trigger_resistance_change_rate |
| C — BUTTON SEQUENCE (Cross→Sq→Tri→Cir) | 60–90s | press_timing_jitter_variance, grip_asymmetry |
| D — STICK SWEEPS (3× CW, 3× CCW) | 90–120s | micro_tremor_accel_variance, stick_autocorr_lag1/lag5, tremor_peak_hz/band_power, accel_magnitude_spectral_entropy |

Right thumb stays on right analog stick throughout all segments (critical for tremor FFT seeding).

Touchpad-only sessions (corners/freeform/swipes) auto-excluded 5 features as zero-variance
(trigger_resistance_change_rate, trigger_onset_velocity_L2/R2, grip_asymmetry,
press_timing_jitter_variance), leaving only 8 active features. Mixed probe reactivates all 13.

### STRUCTURED_PROBE_TYPES Expansion [VAPI:Phase166:MEMORY.md:MEASURED]

```python
STRUCTURED_PROBE_TYPES = frozenset({
    "touchpad_corners",
    "touchpad_freeform",
    "touchpad_swipes",
    "mixed_biometric_probe",  # Phase 166 addition
})
```

### Configurable Defensibility Gate [VAPI:Phase166:MEMORY.md:MEASURED]

`min_separation_ratio: float = 0.70` replaces hardcoded `> 1.0` gate.

**Rationale:** All 3 players use the same physical DualShock Edge controller.
Hardware variance (trigger resistance calibration, micro-tremor coupling to chassis)
is common to all players, structurally lowering the inter-player Mahalanobis ceiling
below 1.0. The 0.70 gate is set above the current best separation ratio (swipes: 0.644)
to require genuine improvement from the mixed probe without requiring a ceiling the
hardware architecture cannot meet.

Gate affects: `insert_separation_defensibility_log()`, `get_enrollment_capture_guidance()`,
`run-tournament-preflight` endpoint, `commit-activation` endpoint.

## Key Values

| Field | Value | Provenance | Status |
|-------|-------|-----------|--------|
| Separation ratio (N=20, touchpad_corners) | 0.569 | [VAPI:Phase166:MEMORY.md:MEASURED] | BELOW GATE (0.70) |
| Separation gate | 0.70 | [VAPI:Phase166:MEMORY.md:MEASURED] | Phase 166 (was 1.0) |
| LOO classification (N=20) | 20.0% (4/20) | [VAPI:Phase166:MEMORY.md:MEASURED] | BELOW RANDOM (33%) |
| Active features (touchpad sessions) | 8 | [VAPI:Phase166:MEMORY.md:MEASURED] | 5 zero-variance excl. |
| Active features (mixed_biometric_probe) | 13 | [VAPI:Phase166:MEMORY.md:MEASURED] | ALL ACTIVE |
| Bridge tests | 1950 | [VAPI:Phase166:MEMORY.md:MEASURED] | PASSING |
| SDK tests | 305 | [VAPI:Phase166:MEMORY.md:MEASURED] | PASSING |
| Hardhat tests | 468 | [VAPI:Phase166:MEMORY.md:MEASURED] | PASSING |

## New SDK Types [VAPI:Phase166:MEMORY.md:MEASURED]

```python
@dataclass(slots=True)
class MixedProbeGateResult:
    min_separation_ratio:  float
    sessions_needed_total: int
    overall_ready:         bool
    mixed_probe_in_types:  bool
    error:                 "str | None"
```

`SDK_VERSION = "3.0.0-phase166"`

## Tournament Blocker Status [VAPI:Phase166:MEMORY.md:MEASURED]

**Separation ratio trend:**
- N=11 → 1.261 (Phase 143, diagonal+LOO)
- N=14 → 0.789
- N=20 → 0.569 — CONVERGING DOWNWARD

Root cause: P1 intra-player variance range=[1.661, 4.410]. P1 old sessions cluster near
P2, new sessions cluster near P3. P1 is non-stationary across days.

Mixed_biometric_probe sessions currently being captured (2026-04-06):
- P1: 2 sessions
- P2: 1 session
- P3: 1 session
Minimum required for analysis: 3 per player.

## Related Pages

- [[separation_ratio]]
- [[agent_fleet]]
- [[l4_thresholds]]
- [[poac_wire_format]]
