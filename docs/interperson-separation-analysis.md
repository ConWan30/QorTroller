# VAPI Inter-Person Biometric Separation Analysis

**Date:** 2026-03-08  
**Sessions:** N=69 captured, 24 included, 0 excluded (polling-rate filter)  
**Players:** 3 (Player 1: hw_005–hw_044, Player 2: hw_045–hw_058, Player 3: hw_059–hw_073)  
**Feature space:** 13-dimensional L4 biometric fingerprint (4 active after zero-variance exclusion)  
**Window size:** 1025 frames  
**Distance metric:** Full Mahalanobis on active features (Tikhonov-regularized covariance)

> **Auto-excluded features (zero variance across all sessions):** `trigger_resistance_change_rate`, `trigger_onset_velocity_l2`, `trigger_onset_velocity_r2`, `grip_asymmetry`, `tremor_peak_hz`, `tremor_band_power`, `touch_position_variance`, `press_timing_jitter_variance`, `touchpad_spatial_entropy`  
> These features are structurally zero in the current N=69 corpus (game-specific or hardware field added after capture). They are reported below but excluded from Mahalanobis computation.

## Executive Summary

| Metric | Value |
|--------|-------|
| Mean intra-player distance | 0.573 |
| Mean inter-player distance | 0.428 |
| **Separation ratio (inter/intra)** | **0.748** |
| Leave-one-out classification accuracy | 45.8% (11/24) |

**Conclusion:** NO SEPARATION — fingerprint does not distinguish between players

The 11-feature L4 fingerprint shows **weak or no inter-player separation** (ratio 0.75). This may reflect insufficient session diversity, feature space limitations (e.g., touchpad features all zero in current dataset), or genuine similarity of play styles across players. Intra-player consistency detection remains valid despite low inter-player separation.

## Per-Player Statistics

| Player   | Sessions | Intra Mean | Intra Std | Intra Min | Intra Max | Intra Median |
| -------- | -------- | ---------- | --------- | --------- | --------- | ------------ |
| Player 1 | 10       | 0.310      | 0.205     | 0.042     | 0.567     | 0.363        |
| Player 2 | 8        | 0.949      | 1.120     | 0.013     | 3.721     | 0.806        |
| Player 3 | 6        | 0.459      | 0.453     | 0.013     | 1.365     | 0.344        |

## Inter-Player Distance Matrix (Mahalanobis)

Distance between each pair of player mean feature vectors using the shared global covariance.

|          | Player 1 | Player 2 | Player 3 |
| -------- | -------- | -------- | -------- |
| Player 1 | —        | 0.642    | 0.177    |
| Player 2 | 0.642    | —        | 0.465    |
| Player 3 | 0.177    | 0.465    | —        |

## Intra-Player Distance Distribution

Mahalanobis distance from each session's mean feature vector to its player's centroid, using the global covariance.

**Player 1** (N=10 sessions, mean=0.310):
  0.567, 0.043, 0.330, 0.454, 0.042, 0.161, 0.052, 0.396, 0.534, 0.523

**Player 2** (N=8 sessions, mean=0.949):
  1.125, 0.888, 0.875, 3.721, 0.073, 0.738, 0.162, 0.013

**Player 3** (N=6 sessions, mean=0.459):
  0.133, 0.552, 1.365, 0.533, 0.156, 0.013

## Feature Means by Player

Per-feature mean values for each player's session set. Features with high inter-player variation are the strongest biometric discriminators.

| Feature                          | Player 1                | Player 2                 | Player 3                 | Inter-Range |
| -------------------------------- | ----------------------- | ------------------------ | ------------------------ | ----------- |
| micro_tremor_accel_variance      | 1860.8599 (+/-791.7307) | 3228.8363 (+/-3126.3083) | 2237.5638 (+/-1372.9978) | 1367.9764   |
| accel_magnitude_spectral_entropy | 4.2495 (+/-0.3153)      | 4.3663 (+/-0.3788)       | 4.2948 (+/-0.2478)       | 0.1168      |
| stick_autocorr_lag1              | 0.0018 (+/-0.0053)      | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0018      |
| stick_autocorr_lag5              | 0.0011 (+/-0.0032)      | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0011      |
| trigger_resistance_change_rate   | 0.0000 (+/-0.0000)      | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000      |
| trigger_onset_velocity_l2        | 0.0000 (+/-0.0000)      | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000      |
| trigger_onset_velocity_r2        | 0.0000 (+/-0.0000)      | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000      |
| grip_asymmetry                   | 1.0000 (+/-0.0000)      | 1.0000 (+/-0.0000)       | 1.0000 (+/-0.0000)       | 0.0000      |
| tremor_peak_hz                   | 0.0000 (+/-0.0000)      | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000      |
| tremor_band_power                | 0.0000 (+/-0.0000)      | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000      |
| touch_position_variance          | 0.0000 (+/-0.0000)      | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000      |
| press_timing_jitter_variance     | 0.0000 (+/-0.0000)      | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000      |
| touchpad_spatial_entropy         | 0.0000 (+/-0.0000)      | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000      |

## Leave-One-Out Classification Results

Each session was classified to the nearest player centroid (Mahalanobis) using the global covariance. Player mean vectors were computed from ALL sessions (no held-out centroid recomputation — this is a bias-aware first-pass estimate).

**Accuracy: 45.8% (11/24 sessions correctly assigned)**

Misclassified sessions:

| Session                                      | True Player | Predicted | Best Dist |
| -------------------------------------------- | ----------- | --------- | --------- |
| terminal_cal_P1/tremor_seed_20260411T201135Z | Player 1    | Player 3  | 0.219     |
| terminal_cal_P1/tremor_seed_20260411T214848Z | Player 1    | Player 2  | 0.109     |
| terminal_cal_P1/tremor_seed_20260411T215716Z | Player 1    | Player 2  | 0.119     |
| terminal_cal_P2/tremor_seed_20260405T032335Z | Player 2    | Player 1  | 0.484     |
| terminal_cal_P2/tremor_seed_20260405T032940Z | Player 2    | Player 1  | 0.245     |
| terminal_cal_P2/tremor_seed_20260405T204530Z | Player 2    | Player 1  | 0.233     |
| terminal_cal_P2/tremor_seed_20260411T140708Z | Player 2    | Player 3  | 4.186     |
| terminal_cal_P2/tremor_seed_20260411T143454Z | Player 2    | Player 1  | 0.098     |
| terminal_cal_P3/tremor_seed_20260405T202721Z | Player 3    | Player 1  | 0.044     |
| terminal_cal_P3/tremor_seed_20260405T204725Z | Player 3    | Player 1  | 0.375     |
| terminal_cal_P3/tremor_seed_20260411T142608Z | Player 3    | Player 2  | 0.900     |
| terminal_cal_P3/tremor_seed_20260411T144306Z | Player 3    | Player 1  | 0.356     |
| terminal_cal_P3/tremor_seed_20260411T164734Z | Player 3    | Player 1  | 0.027     |

## Excluded Sessions

No sessions excluded.

## Recommendations for L4 Multi-Person Calibration

### Implications for VAPI Protocol

1. **Player-specific fingerprinting needs more features.** The current separation ratio of 0.75 suggests feature augmentation or longer session windows before per-player identification is reliable.

2. **Touchpad biometrics.** All 69 sessions show zero touchpad activity (touch_active=False throughout). Adding the `touch_active`/`touch0_x` fields from capture_session.py Phase 17 will add player-specific thumb-resting patterns as a discriminator. This is expected to improve separation significantly.

3. **Micro-tremor variance.** The gyro-based still-frame filter (gyro_mag < 0.01) applies to raw LSB gyro values (range ~-350 to +350). With raw IMU values in the hundreds, most frames fail this threshold — the effective still-frame count is low. Consider calibrating the threshold to `gyro_mag < IMU_NOISE_FLOOR` (empirical: 332.99 LSB, 95th pct) to capture more tremor frames.

4. **Multi-session calibration window.** The live L4 oracle uses EMA over sessions. For inter-player separation in tournament contexts, accumulate ≥10 sessions per player before computing player centroid. The current N=8 sessions/player average is marginal for Player 2/3.

5. **Full covariance vs. diagonal.** This analysis uses a full Tikhonov-regularized covariance matrix (off-diagonal terms included). The live L4 oracle currently uses a diagonal approximation. Upgrading to full covariance (TODO in the source) would better capture feature correlations and improve both intra-player consistency detection and inter-player separation.

6. **Tremor FFT window length.** The 50-frame window used here (vs 120-frame in live oracle) at 1000 Hz gives a frequency resolution of 20 Hz/bin, which is too coarse to resolve the 8-12 Hz physiological tremor band. The live oracle uses 120-frame windows (8.3 Hz/bin). For reliable tremor band power, a 1024-frame window at 1000 Hz would give 0.98 Hz/bin resolution (noted in CLAUDE.md as a known gap).

---
*Generated by `scripts/analyze_interperson_separation.py` — VAPI Phase 17, 2026-03-08*