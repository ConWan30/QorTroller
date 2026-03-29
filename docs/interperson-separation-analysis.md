# VAPI Inter-Person Biometric Separation Analysis

**Date:** 2026-03-08  
**Sessions:** N=69 captured, 117 included, 5 excluded (polling-rate filter)  
**Players:** 3 (Player 1: hw_005–hw_044, Player 2: hw_045–hw_058, Player 3: hw_059–hw_073)  
**Feature space:** 13-dimensional L4 biometric fingerprint (11 active after zero-variance exclusion)  
**Window size:** 1025 frames  
**Distance metric:** Full Mahalanobis on active features (Tikhonov-regularized covariance)

> **Auto-excluded features (zero variance across all sessions):** `trigger_resistance_change_rate`, `press_timing_jitter_variance`  
> These features are structurally zero in the current N=69 corpus (game-specific or hardware field added after capture). They are reported below but excluded from Mahalanobis computation.

## Executive Summary

| Metric | Value |
|--------|-------|
| Mean intra-player distance | 0.681 |
| Mean inter-player distance | 0.284 |
| **Separation ratio (inter/intra)** | **0.417** |
| Leave-one-out classification accuracy | 30.8% (36/117) |

**Conclusion:** NO SEPARATION — fingerprint does not distinguish between players

The 11-feature L4 fingerprint shows **weak or no inter-player separation** (ratio 0.42). This may reflect insufficient session diversity, feature space limitations (e.g., touchpad features all zero in current dataset), or genuine similarity of play styles across players. Intra-player consistency detection remains valid despite low inter-player separation.

## Per-Player Statistics

| Player   | Sessions | Intra Mean | Intra Std | Intra Min | Intra Max | Intra Median |
| -------- | -------- | ---------- | --------- | --------- | --------- | ------------ |
| Player 1 | 53       | 0.728      | 0.897     | 0.015     | 4.451     | 0.299        |
| Player 2 | 34       | 0.692      | 0.525     | 0.109     | 2.334     | 0.459        |
| Player 3 | 27       | 0.667      | 0.449     | 0.125     | 1.865     | 0.619        |
| Player 4 | 3        | 0.637      | 0.227     | 0.445     | 0.956     | 0.511        |

## Inter-Player Distance Matrix (Mahalanobis)

Distance between each pair of player mean feature vectors using the shared global covariance.

|          | Player 1 | Player 2 | Player 3 | Player 4 |
| -------- | -------- | -------- | -------- | -------- |
| Player 1 | —        | 0.327    | 0.469    | 0.494    |
| Player 2 | 0.327    | —        | 0.143    | 0.187    |
| Player 3 | 0.469    | 0.143    | —        | 0.086    |
| Player 4 | 0.494    | 0.187    | 0.086    | —        |

## Intra-Player Distance Distribution

Mahalanobis distance from each session's mean feature vector to its player's centroid, using the global covariance.

**Player 1** (N=53 sessions, mean=0.728):
  1.502, 0.299, 0.039, 4.392, 0.126, 0.031, 1.335, 0.201, 0.287, 0.097, 0.253, 0.143, 0.150, 0.104, 0.239, 0.288, 1.414, 1.393, 0.451, 0.155, 1.468, 0.222, 0.191, 0.015, 0.689, 0.205, 0.784, 0.217, 1.877, 0.053, 0.153, 1.017, 0.046, 1.406, 0.236, 0.425, 0.496, 0.088, 4.451, 0.487, 1.484, 1.353, 0.909, 1.421, 0.294, 1.224, 1.185, 0.897, 0.599, 0.888, 0.220, 0.058, 0.647

**Player 2** (N=34 sessions, mean=0.692):
  1.186, 0.707, 0.215, 0.913, 0.304, 0.650, 0.195, 2.334, 0.148, 0.301, 0.116, 0.281, 0.344, 0.477, 0.792, 0.948, 0.838, 1.098, 1.176, 1.731, 0.998, 0.442, 0.367, 0.109, 0.389, 0.396, 0.429, 0.931, 0.394, 1.800, 0.114, 1.154, 1.013, 0.253

**Player 3** (N=27 sessions, mean=0.667):
  1.671, 0.619, 0.646, 0.422, 0.979, 0.350, 0.307, 0.272, 0.132, 0.125, 0.959, 0.249, 1.035, 0.349, 0.283, 1.044, 1.044, 0.266, 0.692, 0.296, 0.966, 1.214, 0.709, 0.562, 0.176, 0.777, 1.865

**Player 4** (N=3 sessions, mean=0.637):
  0.445, 0.956, 0.511

## Feature Means by Player

Per-feature mean values for each player's session set. Features with high inter-player variation are the strongest biometric discriminators.

| Feature                          | Player 1                 | Player 2                 | Player 3                 | Player 4                 | Inter-Range |
| -------------------------------- | ------------------------ | ------------------------ | ------------------------ | ------------------------ | ----------- |
| micro_tremor_accel_variance      | 8189.2669 (+/-6197.4775) | 6451.6560 (+/-4476.2357) | 5685.5481 (+/-4068.3685) | 5545.4994 (+/-3625.6608) | 2643.7675   |
| tremor_peak_hz                   | 0.7349 (+/-1.3165)       | 3.9314 (+/-13.6255)      | 4.2067 (+/-14.9321)      | 0.0000 (+/-0.0000)       | 4.2067      |
| touchpad_spatial_entropy         | 0.3633 (+/-0.8696)       | 0.6574 (+/-1.1219)       | 0.3517 (+/-0.7790)       | 1.5971 (+/-1.3247)       | 1.2454      |
| accel_magnitude_spectral_entropy | 4.7936 (+/-0.6995)       | 4.8787 (+/-1.0092)       | 4.7074 (+/-1.2349)       | 4.4134 (+/-0.3049)       | 0.4653      |
| stick_autocorr_lag1              | 0.1122 (+/-0.0834)       | 0.0592 (+/-0.0786)       | 0.0548 (+/-0.0709)       | 0.0040 (+/-0.0057)       | 0.1081      |
| stick_autocorr_lag5              | 0.1005 (+/-0.0767)       | 0.0523 (+/-0.0696)       | 0.0471 (+/-0.0615)       | 0.0029 (+/-0.0040)       | 0.0977      |
| grip_asymmetry                   | 1.0481 (+/-0.1411)       | 1.0336 (+/-0.1073)       | 1.0830 (+/-0.2589)       | 1.0000 (+/-0.0000)       | 0.0830      |
| touch_position_variance          | 0.0066 (+/-0.0160)       | 0.0090 (+/-0.0165)       | 0.0040 (+/-0.0088)       | 0.0193 (+/-0.0152)       | 0.0153      |
| trigger_onset_velocity_r2        | 0.0032 (+/-0.0047)       | 0.0050 (+/-0.0214)       | 0.0020 (+/-0.0028)       | 0.0000 (+/-0.0000)       | 0.0050      |
| tremor_band_power                | 0.0029 (+/-0.0032)       | 0.0022 (+/-0.0030)       | 0.0020 (+/-0.0026)       | 0.0000 (+/-0.0000)       | 0.0029      |
| trigger_onset_velocity_l2        | 0.0011 (+/-0.0021)       | 0.0006 (+/-0.0016)       | 0.0010 (+/-0.0022)       | 0.0000 (+/-0.0000)       | 0.0011      |
| trigger_resistance_change_rate   | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000      |
| press_timing_jitter_variance     | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000      |

## Leave-One-Out Classification Results

Each session was classified to the nearest player centroid (Mahalanobis) using the global covariance. Player mean vectors were computed from ALL sessions (no held-out centroid recomputation — this is a bias-aware first-pass estimate).

**Accuracy: 30.8% (36/117 sessions correctly assigned)**

Misclassified sessions:

| Session                                            | True Player | Predicted | Best Dist |
| -------------------------------------------------- | ----------- | --------- | --------- |
| hw_005                                             | Player 1    | Player 4  | 1.009     |
| hw_006                                             | Player 1    | Player 2  | 0.060     |
| hw_011                                             | Player 1    | Player 4  | 0.842     |
| hw_019                                             | Player 1    | Player 2  | 0.105     |
| hw_021                                             | Player 1    | Player 4  | 0.922     |
| hw_023                                             | Player 1    | Player 4  | 0.052     |
| hw_027                                             | Player 1    | Player 2  | 0.148     |
| hw_029                                             | Player 1    | Player 4  | 0.199     |
| hw_031                                             | Player 1    | Player 4  | 0.298     |
| hw_036                                             | Player 1    | Player 4  | 0.525     |
| hw_039                                             | Player 1    | Player 2  | 0.112     |
| hw_040                                             | Player 1    | Player 4  | 0.075     |
| hw_041                                             | Player 1    | Player 4  | 0.035     |
| hw_045                                             | Player 2    | Player 1  | 0.863     |
| hw_046                                             | Player 2    | Player 1  | 0.386     |
| hw_047                                             | Player 2    | Player 3  | 0.073     |
| hw_048                                             | Player 2    | Player 4  | 0.739     |
| hw_049                                             | Player 2    | Player 1  | 0.033     |
| hw_050                                             | Player 2    | Player 4  | 0.476     |
| hw_051                                             | Player 2    | Player 1  | 0.133     |
| hw_052                                             | Player 2    | Player 1  | 2.011     |
| hw_053                                             | Player 2    | Player 4  | 0.050     |
| hw_054                                             | Player 2    | Player 1  | 0.029     |
| hw_056                                             | Player 2    | Player 4  | 0.105     |
| hw_057                                             | Player 2    | Player 1  | 0.034     |
| hw_058                                             | Player 2    | Player 1  | 0.155     |
| hw_060                                             | Player 3    | Player 1  | 0.153     |
| hw_061                                             | Player 3    | Player 1  | 0.178     |
| hw_062                                             | Player 3    | Player 1  | 0.052     |
| hw_063                                             | Player 3    | Player 1  | 0.512     |
| hw_064                                             | Player 3    | Player 1  | 0.124     |
| hw_065                                             | Player 3    | Player 2  | 0.169     |
| hw_066                                             | Player 3    | Player 2  | 0.131     |
| hw_068                                             | Player 3    | Player 4  | 0.105     |
| hw_070                                             | Player 3    | Player 2  | 0.077     |
| hw_071                                             | Player 3    | Player 1  | 0.492     |
| hw_072                                             | Player 3    | Player 4  | 0.212     |
| terminal_cal_P1/natural_grip_20260326T234127Z      | Player 1    | Player 4  | 0.033     |
| terminal_cal_P1/resting_baseline_20260326T233432Z  | Player 1    | Player 4  | 0.992     |
| terminal_cal_P1/spectral_accel_20260327T011014Z    | Player 1    | Player 4  | 0.861     |
| terminal_cal_P1/stick_sweeps_20260327T000958Z      | Player 1    | Player 4  | 0.416     |
| terminal_cal_P1/touchpad_corners_20260327T031241Z  | Player 1    | Player 4  | 0.927     |
| terminal_cal_P1/touchpad_corners_20260327T230404Z  | Player 1    | Player 2  | 0.083     |
| terminal_cal_P1/touchpad_corners_20260328T142201Z  | Player 1    | Player 4  | 0.731     |
| terminal_cal_P1/touchpad_freeform_20260327T030955Z | Player 1    | Player 4  | 0.693     |
| terminal_cal_P1/touchpad_freeform_20260328T141850Z | Player 1    | Player 4  | 0.132     |
| terminal_cal_P1/touchpad_swipes_20260327T030742Z   | Player 1    | Player 4  | 0.394     |
| terminal_cal_P2/button_sequence_20260327T021315Z   | Player 2    | Player 3  | 0.654     |
| terminal_cal_P2/natural_grip_20260327T015604Z      | Player 2    | Player 4  | 0.778     |
| terminal_cal_P2/natural_grip_20260329T032252Z      | Player 2    | Player 4  | 0.664     |
| terminal_cal_P2/resting_baseline_20260327T015045Z  | Player 2    | Player 4  | 0.925     |
| terminal_cal_P2/resting_baseline_20260329T031701Z  | Player 2    | Player 4  | 1.003     |
| terminal_cal_P2/spectral_accel_20260327T022944Z    | Player 2    | Player 3  | 1.646     |
| terminal_cal_P2/stick_sweeps_20260327T022131Z      | Player 2    | Player 4  | 0.843     |
| terminal_cal_P2/touchpad_corners_20260328T003556Z  | Player 2    | Player 1  | 0.116     |
| terminal_cal_P2/touchpad_corners_20260328T153820Z  | Player 2    | Player 1  | 0.051     |
| terminal_cal_P2/touchpad_corners_20260329T203046Z  | Player 2    | Player 4  | 0.211     |
| terminal_cal_P2/touchpad_freeform_20260328T003347Z | Player 2    | Player 1  | 0.102     |
| terminal_cal_P2/touchpad_freeform_20260328T153604Z | Player 2    | Player 4  | 0.255     |
| terminal_cal_P2/touchpad_freeform_20260329T005231Z | Player 2    | Player 1  | 0.608     |
| terminal_cal_P2/touchpad_freeform_20260329T202820Z | Player 2    | Player 1  | 0.081     |
| terminal_cal_P2/touchpad_swipes_20260328T003136Z   | Player 2    | Player 1  | 1.476     |
| terminal_cal_P2/touchpad_swipes_20260328T153354Z   | Player 2    | Player 4  | 0.086     |
| terminal_cal_P2/touchpad_swipes_20260329T005021Z   | Player 2    | Player 4  | 0.981     |
| terminal_cal_P2/touchpad_swipes_20260329T202559Z   | Player 2    | Player 1  | 0.689     |
| terminal_cal_P2/trigger_rhythm_20260327T020442Z    | Player 2    | Player 3  | 0.113     |
| terminal_cal_P3/button_sequence_20260328T014042Z   | Player 3    | Player 4  | 1.004     |
| terminal_cal_P3/natural_grip_20260328T005708Z      | Player 3    | Player 4  | 0.320     |
| terminal_cal_P3/resting_baseline_20260328T003917Z  | Player 3    | Player 4  | 1.013     |
| terminal_cal_P3/resting_baseline_20260328T011813Z  | Player 3    | Player 4  | 1.013     |
| terminal_cal_P3/spectral_accel_20260328T015847Z    | Player 3    | Player 4  | 0.227     |
| terminal_cal_P3/stick_sweeps_20260328T014814Z      | Player 3    | Player 4  | 0.677     |
| terminal_cal_P3/touchpad_corners_20260327T232204Z  | Player 3    | Player 4  | 0.256     |
| terminal_cal_P3/touchpad_corners_20260328T161059Z  | Player 3    | Player 4  | 0.933     |
| terminal_cal_P3/touchpad_freeform_20260327T231922Z | Player 3    | Player 1  | 0.748     |
| terminal_cal_P3/touchpad_freeform_20260328T160809Z | Player 3    | Player 1  | 0.246     |
| terminal_cal_P3/touchpad_swipes_20260327T231705Z   | Player 3    | Player 4  | 0.528     |
| terminal_cal_P3/touchpad_swipes_20260328T160459Z   | Player 3    | Player 2  | 0.076     |
| terminal_cal_P3/trigger_rhythm_20260328T011017Z    | Player 3    | Player 4  | 0.745     |
| terminal_cal_P3/trigger_rhythm_20260328T013207Z    | Player 3    | Player 1  | 1.400     |
| terminal_cal_P4/touchpad_freeform_20260329T032705Z | Player 4    | Player 1  | 0.466     |

## Excluded Sessions

| Session | Reason                                       | Polling Rate Hz |
| ------- | -------------------------------------------- | --------------- |
| hw_043  | polling_rate_hz=203.6 outside [800.0,1100.0] | 203.55          |
| hw_044  | polling_rate_hz=492.7 outside [800.0,1100.0] | 492.67          |
| hw_067  | polling_rate_hz=72.2 outside [800.0,1100.0]  | 72.16           |
| hw_069  | polling_rate_hz=307.1 outside [800.0,1100.0] | 307.14          |
| hw_073  | polling_rate_hz=49.7 outside [800.0,1100.0]  | 49.7            |

## Recommendations for L4 Multi-Person Calibration

### Implications for VAPI Protocol

1. **Player-specific fingerprinting needs more features.** The current separation ratio of 0.42 suggests feature augmentation or longer session windows before per-player identification is reliable.

2. **Touchpad biometrics.** All 69 sessions show zero touchpad activity (touch_active=False throughout). Adding the `touch_active`/`touch0_x` fields from capture_session.py Phase 17 will add player-specific thumb-resting patterns as a discriminator. This is expected to improve separation significantly.

3. **Micro-tremor variance.** The gyro-based still-frame filter (gyro_mag < 0.01) applies to raw LSB gyro values (range ~-350 to +350). With raw IMU values in the hundreds, most frames fail this threshold — the effective still-frame count is low. Consider calibrating the threshold to `gyro_mag < IMU_NOISE_FLOOR` (empirical: 332.99 LSB, 95th pct) to capture more tremor frames.

4. **Multi-session calibration window.** The live L4 oracle uses EMA over sessions. For inter-player separation in tournament contexts, accumulate ≥10 sessions per player before computing player centroid. The current N=29 sessions/player average is marginal for Player 2/3.

5. **Full covariance vs. diagonal.** This analysis uses a full Tikhonov-regularized covariance matrix (off-diagonal terms included). The live L4 oracle currently uses a diagonal approximation. Upgrading to full covariance (TODO in the source) would better capture feature correlations and improve both intra-player consistency detection and inter-player separation.

6. **Tremor FFT window length.** The 50-frame window used here (vs 120-frame in live oracle) at 1000 Hz gives a frequency resolution of 20 Hz/bin, which is too coarse to resolve the 8-12 Hz physiological tremor band. The live oracle uses 120-frame windows (8.3 Hz/bin). For reliable tremor band power, a 1024-frame window at 1000 Hz would give 0.98 Hz/bin resolution (noted in CLAUDE.md as a known gap).

---
*Generated by `scripts/analyze_interperson_separation.py` — VAPI Phase 17, 2026-03-08*