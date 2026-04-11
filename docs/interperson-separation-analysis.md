# VAPI Inter-Person Biometric Separation Analysis

**Date:** 2026-03-08  
**Sessions:** N=69 captured, 29 included, 0 excluded (polling-rate filter)  
**Players:** 3 (Player 1: hw_005–hw_044, Player 2: hw_045–hw_058, Player 3: hw_059–hw_073)  
**Feature space:** 13-dimensional L4 biometric fingerprint (8 active after zero-variance exclusion)  
**Window size:** 1025 frames  
**Distance metric:** Full Mahalanobis on active features (Tikhonov-regularized covariance)

> **Auto-excluded features (zero variance across all sessions):** `trigger_resistance_change_rate`, `trigger_onset_velocity_l2`, `trigger_onset_velocity_r2`, `grip_asymmetry`, `press_timing_jitter_variance`  
> These features are structurally zero in the current N=69 corpus (game-specific or hardware field added after capture). They are reported below but excluded from Mahalanobis computation.

## Executive Summary

| Metric | Value |
|--------|-------|
| Mean intra-player distance | 0.763 |
| Mean inter-player distance | 0.761 |
| **Separation ratio (inter/intra)** | **0.998** |
| Leave-one-out classification accuracy | 48.3% (14/29) |

**Conclusion:** NO SEPARATION — fingerprint does not distinguish between players

The 11-feature L4 fingerprint shows **weak or no inter-player separation** (ratio 1.00). This may reflect insufficient session diversity, feature space limitations (e.g., touchpad features all zero in current dataset), or genuine similarity of play styles across players. Intra-player consistency detection remains valid despite low inter-player separation.

## Per-Player Statistics

| Player   | Sessions | Intra Mean | Intra Std | Intra Min | Intra Max | Intra Median |
| -------- | -------- | ---------- | --------- | --------- | --------- | ------------ |
| Player 1 | 8        | 0.622      | 0.433     | 0.155     | 1.592     | 0.579        |
| Player 2 | 11       | 0.502      | 0.323     | 0.148     | 0.950     | 0.302        |
| Player 3 | 10       | 1.165      | 0.574     | 0.247     | 2.088     | 1.226        |

## Inter-Player Distance Matrix (Mahalanobis)

Distance between each pair of player mean feature vectors using the shared global covariance.

|          | Player 1 | Player 2 | Player 3 |
| -------- | -------- | -------- | -------- |
| Player 1 | —        | 0.749    | 1.133    |
| Player 2 | 0.749    | —        | 0.401    |
| Player 3 | 1.133    | 0.401    | —        |

## Intra-Player Distance Distribution

Mahalanobis distance from each session's mean feature vector to its player's centroid, using the global covariance.

**Player 1** (N=8 sessions, mean=0.622):
  0.800, 0.568, 0.590, 0.256, 1.592, 0.770, 0.155, 0.240

**Player 2** (N=11 sessions, mean=0.502):
  0.260, 0.174, 0.148, 0.667, 0.302, 0.950, 0.942, 0.219, 0.769, 0.200, 0.887

**Player 3** (N=10 sessions, mean=1.165):
  1.119, 1.885, 1.333, 0.870, 0.605, 0.247, 1.542, 0.512, 1.450, 2.088

## Feature Means by Player

Per-feature mean values for each player's session set. Features with high inter-player variation are the strongest biometric discriminators.

| Feature                          | Player 1                 | Player 2                 | Player 3                 | Inter-Range |
| -------------------------------- | ------------------------ | ------------------------ | ------------------------ | ----------- |
| micro_tremor_accel_variance      | 4164.6736 (+/-2177.2678) | 7571.1409 (+/-2811.8171) | 9462.1722 (+/-6136.8974) | 5297.4987   |
| tremor_peak_hz                   | 12.0829 (+/-30.3143)     | 0.7975 (+/-2.4743)       | 2.1131 (+/-3.2704)       | 11.2854     |
| accel_magnitude_spectral_entropy | 4.1685 (+/-0.2737)       | 4.0110 (+/-0.2651)       | 3.9278 (+/-0.5225)       | 0.2407      |
| touchpad_spatial_entropy         | 1.4949 (+/-0.2794)       | 1.3408 (+/-0.4407)       | 1.3248 (+/-0.4207)       | 0.1701      |
| stick_autocorr_lag1              | 0.0085 (+/-0.0147)       | 0.0073 (+/-0.0205)       | 0.0020 (+/-0.0061)       | 0.0064      |
| stick_autocorr_lag5              | 0.0047 (+/-0.0082)       | 0.0060 (+/-0.0176)       | 0.0010 (+/-0.0029)       | 0.0051      |
| touch_position_variance          | 0.0310 (+/-0.0157)       | 0.0265 (+/-0.0187)       | 0.0284 (+/-0.0140)       | 0.0045      |
| tremor_band_power                | 0.0004 (+/-0.0007)       | 0.0001 (+/-0.0003)       | 0.0000 (+/-0.0000)       | 0.0004      |
| trigger_resistance_change_rate   | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000      |
| trigger_onset_velocity_l2        | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000      |
| trigger_onset_velocity_r2        | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000      |
| grip_asymmetry                   | 1.0000 (+/-0.0000)       | 1.0000 (+/-0.0000)       | 1.0000 (+/-0.0000)       | 0.0000      |
| press_timing_jitter_variance     | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000      |

## Leave-One-Out Classification Results

Each session was classified to the nearest player centroid (Mahalanobis) using the global covariance. Player mean vectors were computed from ALL sessions (no held-out centroid recomputation — this is a bias-aware first-pass estimate).

**Accuracy: 48.3% (14/29 sessions correctly assigned)**

Misclassified sessions:

| Session                                           | True Player | Predicted | Best Dist |
| ------------------------------------------------- | ----------- | --------- | --------- |
| terminal_cal_P1/touchpad_corners_20260327T230404Z | Player 1    | Player 2  | 0.201     |
| terminal_cal_P1/touchpad_corners_20260405T210157Z | Player 1    | Player 2  | 0.024     |
| terminal_cal_P2/touchpad_corners_20260328T003556Z | Player 2    | Player 3  | 0.147     |
| terminal_cal_P2/touchpad_corners_20260329T203046Z | Player 2    | Player 1  | 0.245     |
| terminal_cal_P2/touchpad_corners_20260404T191532Z | Player 2    | Player 3  | 0.108     |
| terminal_cal_P2/touchpad_corners_20260405T033521Z | Player 2    | Player 1  | 0.336     |
| terminal_cal_P2/touchpad_corners_20260405T210457Z | Player 2    | Player 3  | 0.544     |
| terminal_cal_P2/touchpad_corners_20260411T142422Z | Player 2    | Player 1  | 0.247     |
| terminal_cal_P2/touchpad_corners_20260411T144124Z | Player 2    | Player 3  | 0.205     |
| terminal_cal_P2/touchpad_corners_20260411T164609Z | Player 2    | Player 3  | 0.491     |
| terminal_cal_P3/touchpad_corners_20260327T232204Z | Player 3    | Player 1  | 0.240     |
| terminal_cal_P3/touchpad_corners_20260328T161059Z | Player 3    | Player 1  | 0.807     |
| terminal_cal_P3/touchpad_corners_20260329T032924Z | Player 3    | Player 1  | 0.324     |
| terminal_cal_P3/touchpad_corners_20260329T215413Z | Player 3    | Player 1  | 0.344     |
| terminal_cal_P3/touchpad_corners_20260404T203748Z | Player 3    | Player 2  | 0.205     |

## Excluded Sessions

No sessions excluded.

## Recommendations for L4 Multi-Person Calibration

### Implications for VAPI Protocol

1. **Player-specific fingerprinting needs more features.** The current separation ratio of 1.00 suggests feature augmentation or longer session windows before per-player identification is reliable.

2. **Touchpad biometrics.** All 69 sessions show zero touchpad activity (touch_active=False throughout). Adding the `touch_active`/`touch0_x` fields from capture_session.py Phase 17 will add player-specific thumb-resting patterns as a discriminator. This is expected to improve separation significantly.

3. **Micro-tremor variance.** The gyro-based still-frame filter (gyro_mag < 0.01) applies to raw LSB gyro values (range ~-350 to +350). With raw IMU values in the hundreds, most frames fail this threshold — the effective still-frame count is low. Consider calibrating the threshold to `gyro_mag < IMU_NOISE_FLOOR` (empirical: 332.99 LSB, 95th pct) to capture more tremor frames.

4. **Multi-session calibration window.** The live L4 oracle uses EMA over sessions. For inter-player separation in tournament contexts, accumulate ≥10 sessions per player before computing player centroid. The current N=10 sessions/player average is marginal for Player 2/3.

5. **Full covariance vs. diagonal.** This analysis uses a full Tikhonov-regularized covariance matrix (off-diagonal terms included). The live L4 oracle currently uses a diagonal approximation. Upgrading to full covariance (TODO in the source) would better capture feature correlations and improve both intra-player consistency detection and inter-player separation.

6. **Tremor FFT window length.** The 50-frame window used here (vs 120-frame in live oracle) at 1000 Hz gives a frequency resolution of 20 Hz/bin, which is too coarse to resolve the 8-12 Hz physiological tremor band. The live oracle uses 120-frame windows (8.3 Hz/bin). For reliable tremor band power, a 1024-frame window at 1000 Hz would give 0.98 Hz/bin resolution (noted in CLAUDE.md as a known gap).

---
*Generated by `scripts/analyze_interperson_separation.py` — VAPI Phase 17, 2026-03-08*