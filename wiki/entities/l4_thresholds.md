# ENTITY: L4 Mahalanobis Thresholds

[VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]

## Overview

L4 is the biometric anomaly detection layer of the PITL stack. It computes a
13-dimensional Mahalanobis distance from each session's feature vector to the
player's calibrated centroid. Two thresholds gate the result:

- **Anomaly threshold:** Sessions exceeding this are flagged `0x30 BIOMETRIC_ANOMALY`
- **Continuity threshold:** Sessions exceeding this fail the continuity gate

Both are advisory — they contribute to `humanity_probability` but never hard-block
tournament eligibility alone.

## Current Values [VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]

| Threshold | Value | Calibration | Status |
|-----------|-------|-------------|--------|
| l4_mahalanobis_anomaly | **7.009** | Phase 57, N=74, mean+3sigma | STALE (calib_dim=12, live_dim=13) |
| l4_mahalanobis_continuity | **5.367** | Phase 57, N=74, mean+2sigma | STALE (calib_dim=12, live_dim=13) |

**Staleness:** Phase 121 added `touchpad_spatial_entropy` (feature index 12), expanding
live feature space to 13 dimensions. Calibration was run on 12-dimensional data.
Staleness does not invalidate the thresholds for gameplay sessions (touchpad_spatial_entropy
is structurally 0 in gameplay), but blocks tournament preflight P0 gate.

## Human False Positive Rate [VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]

~2.9% at 3-sigma anomaly threshold. This is the expected rate from the Mahalanobis
chi-squared distribution with 12 degrees of freedom.

## Calibration Rules [VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]

- Never modify thresholds without `threshold_calibrator.py` against N≥74 real sessions
- Per-player thresholds can only **tighten** (min() enforced — never loosen)
- Mode 6 living calibration: ±15% per cycle maximum
- Stable EMA track: only updates on NOMINAL sessions (not ANOMALY or BOT sessions)
- Bounds: anomaly [5.0–15.0], continuity [3.0–10.0] (Phase 124 enforcement)

## N=171 Recalibration Pending [VAPI:Phase166:MEMORY.md:MEASURED]

N=171 sessions (including mixed_biometric_probe) produced:
- Recommended anomaly: **6.563** (vs current 7.009, −6.4%)
- Recommended continuity: **5.114** (vs current 5.367, −4.7%)

These values must NOT be applied until `recalibrate_l4_pipeline.py` is run properly
against the 13-feature mixed_biometric_probe corpus. The N=171 corpus mixes 8-feature
touchpad sessions with 13-feature mixed probe sessions — requires proper dim=13 calibration.

## Related Pages

- [[poac_wire_format]]
- [[zk_circuit]]
- [[separation_ratio]]
- [[phase_166]]
