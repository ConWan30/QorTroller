# VAPI Inter-Person Biometric Separation Analysis

**Date:** 2026-03-08  
**Sessions:** N=69 captured, 165 included, 5 excluded (polling-rate filter)  
**Players:** 3 (Player 1: hw_005–hw_044, Player 2: hw_045–hw_058, Player 3: hw_059–hw_073)  
**Feature space:** 13-dimensional L4 biometric fingerprint (11 active after zero-variance exclusion)  
**Window size:** 1025 frames  
**Distance metric:** Full Mahalanobis on active features (Tikhonov-regularized covariance)

> **Auto-excluded features (zero variance across all sessions):** `trigger_resistance_change_rate`, `press_timing_jitter_variance`  
> These features are structurally zero in the current N=69 corpus (game-specific or hardware field added after capture). They are reported below but excluded from Mahalanobis computation.

## Executive Summary

| Metric | Value |
|--------|-------|
| Mean intra-player distance | 0.771 |
| Mean inter-player distance | 0.157 |
| **Separation ratio (inter/intra)** | **0.204** |
| Leave-one-out classification accuracy | 25.5% (42/165) |

**Conclusion:** NO SEPARATION — fingerprint does not distinguish between players

The 11-feature L4 fingerprint shows **weak or no inter-player separation** (ratio 0.20). This may reflect insufficient session diversity, feature space limitations (e.g., touchpad features all zero in current dataset), or genuine similarity of play styles across players. Intra-player consistency detection remains valid despite low inter-player separation.

## Per-Player Statistics

| Player   | Sessions | Intra Mean | Intra Std | Intra Min | Intra Max | Intra Median |
| -------- | -------- | ---------- | --------- | --------- | --------- | ------------ |
| Player 1 | 70       | 0.781      | 0.864     | 0.069     | 4.846     | 0.438        |
| Player 2 | 49       | 0.753      | 0.535     | 0.121     | 2.488     | 0.664        |
| Player 3 | 46       | 0.781      | 0.489     | 0.086     | 2.047     | 0.722        |

## Inter-Player Distance Matrix (Mahalanobis)

Distance between each pair of player mean feature vectors using the shared global covariance.

|          | Player 1 | Player 2 | Player 3 |
| -------- | -------- | -------- | -------- |
| Player 1 | —        | 0.229    | 0.229    |
| Player 2 | 0.229    | —        | 0.014    |
| Player 3 | 0.229    | 0.014    | —        |

## Intra-Player Distance Distribution

Mahalanobis distance from each session's mean feature vector to its player's centroid, using the global covariance.

**Player 1** (N=70 sessions, mean=0.781):
  1.464, 0.180, 0.108, 4.784, 0.268, 0.115, 1.288, 0.347, 0.437, 0.239, 0.401, 0.273, 0.071, 0.223, 0.136, 0.438, 1.371, 1.606, 0.355, 0.299, 1.685, 0.370, 0.096, 0.144, 0.605, 0.346, 0.701, 0.363, 2.119, 0.194, 0.069, 0.951, 0.187, 1.620, 0.136, 0.328, 0.400, 0.230, 4.846, 0.743, 1.257, 1.066, 1.014, 0.392, 1.445, 1.306, 0.836, 1.378, 0.194, 1.170, 0.583, 1.821, 0.070, 1.127, 1.081, 0.504, 0.259, 0.694, 0.140, 0.814, 0.367, 0.195, 0.258, 0.686, 0.796, 0.090, 1.362, 1.138, 1.262, 0.817

**Player 2** (N=49 sessions, mean=0.753):
  1.273, 0.764, 0.217, 0.956, 0.342, 0.678, 0.226, 2.488, 0.159, 0.338, 0.149, 0.291, 0.382, 0.522, 0.822, 1.652, 0.821, 0.993, 0.877, 1.152, 1.234, 1.791, 1.044, 0.486, 0.408, 0.141, 0.404, 0.525, 0.664, 1.119, 0.434, 0.445, 1.003, 0.436, 1.123, 0.294, 1.686, 1.922, 0.128, 1.211, 1.089, 0.191, 0.121, 0.195, 0.313, 1.104, 1.004, 0.999, 0.257

**Player 3** (N=46 sessions, mean=0.781):
  1.832, 0.522, 0.551, 0.316, 0.903, 0.244, 0.189, 0.157, 0.274, 0.086, 0.882, 0.397, 1.233, 1.658, 0.835, 0.506, 0.434, 1.242, 1.243, 0.415, 0.870, 0.447, 1.159, 0.644, 0.223, 0.101, 0.820, 2.047, 1.151, 0.617, 0.852, 1.460, 0.894, 1.288, 1.188, 0.731, 0.094, 0.713, 0.636, 0.229, 0.499, 0.586, 0.881, 1.056, 0.960, 1.840

## Feature Means by Player

Per-feature mean values for each player's session set. Features with high inter-player variation are the strongest biometric discriminators.

| Feature                          | Player 1                 | Player 2                 | Player 3                 | Inter-Range |
| -------------------------------- | ------------------------ | ------------------------ | ------------------------ | ----------- |
| micro_tremor_accel_variance      | 7532.4466 (+/-5745.1622) | 6384.3786 (+/-4388.4025) | 6378.2357 (+/-4409.2659) | 1154.2109   |
| tremor_peak_hz                   | 3.4481 (+/-13.9130)      | 5.3775 (+/-16.8276)      | 4.6861 (+/-15.7259)      | 1.9295      |
| touchpad_spatial_entropy         | 0.5110 (+/-0.8837)       | 0.8038 (+/-1.1360)       | 0.8171 (+/-1.1185)       | 0.3061      |
| accel_magnitude_spectral_entropy | 4.6876 (+/-0.6744)       | 4.6688 (+/-0.9577)       | 4.5153 (+/-1.0194)       | 0.1722      |
| stick_autocorr_lag1              | 0.0887 (+/-0.0851)       | 0.0457 (+/-0.0705)       | 0.0357 (+/-0.0608)       | 0.0530      |
| stick_autocorr_lag5              | 0.0794 (+/-0.0777)       | 0.0404 (+/-0.0625)       | 0.0311 (+/-0.0530)       | 0.0483      |
| grip_asymmetry                   | 1.0374 (+/-0.1245)       | 1.0252 (+/-0.0908)       | 1.0492 (+/-0.2024)       | 0.0240      |
| touch_position_variance          | 0.0090 (+/-0.0163)       | 0.0122 (+/-0.0181)       | 0.0107 (+/-0.0144)       | 0.0032      |
| trigger_onset_velocity_r2        | 0.0025 (+/-0.0043)       | 0.0036 (+/-0.0180)       | 0.0013 (+/-0.0024)       | 0.0023      |
| tremor_band_power                | 0.0022 (+/-0.0030)       | 0.0016 (+/-0.0027)       | 0.0012 (+/-0.0022)       | 0.0010      |
| trigger_onset_velocity_l2        | 0.0009 (+/-0.0019)       | 0.0005 (+/-0.0014)       | 0.0006 (+/-0.0017)       | 0.0004      |
| trigger_resistance_change_rate   | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000      |
| press_timing_jitter_variance     | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000 (+/-0.0000)       | 0.0000      |

## Leave-One-Out Classification Results

Each session was classified to the nearest player centroid (Mahalanobis) using the global covariance. Player mean vectors were computed from ALL sessions (no held-out centroid recomputation — this is a bias-aware first-pass estimate).

**Accuracy: 25.5% (42/165 sessions correctly assigned)**

Misclassified sessions:

| Session                                                | True Player | Predicted | Best Dist |
| ------------------------------------------------------ | ----------- | --------- | --------- |
| hw_005                                                 | Player 1    | Player 3  | 1.238     |
| hw_006                                                 | Player 1    | Player 2  | 0.060     |
| hw_011                                                 | Player 1    | Player 3  | 1.062     |
| hw_019                                                 | Player 1    | Player 3  | 0.131     |
| hw_021                                                 | Player 1    | Player 3  | 1.146     |
| hw_023                                                 | Player 1    | Player 3  | 0.149     |
| hw_029                                                 | Player 1    | Player 3  | 0.384     |
| hw_031                                                 | Player 1    | Player 3  | 0.474     |
| hw_036                                                 | Player 1    | Player 3  | 0.726     |
| hw_040                                                 | Player 1    | Player 3  | 0.130     |
| hw_041                                                 | Player 1    | Player 3  | 0.185     |
| hw_045                                                 | Player 2    | Player 1  | 1.045     |
| hw_046                                                 | Player 2    | Player 1  | 0.537     |
| hw_047                                                 | Player 2    | Player 3  | 0.214     |
| hw_048                                                 | Player 2    | Player 3  | 0.953     |
| hw_049                                                 | Player 2    | Player 1  | 0.120     |
| hw_050                                                 | Player 2    | Player 3  | 0.675     |
| hw_051                                                 | Player 2    | Player 1  | 0.033     |
| hw_052                                                 | Player 2    | Player 1  | 2.261     |
| hw_053                                                 | Player 2    | Player 3  | 0.150     |
| hw_054                                                 | Player 2    | Player 1  | 0.114     |
| hw_055                                                 | Player 2    | Player 1  | 0.127     |
| hw_056                                                 | Player 2    | Player 3  | 0.286     |
| hw_057                                                 | Player 2    | Player 1  | 0.154     |
| hw_058                                                 | Player 2    | Player 1  | 0.293     |
| hw_059                                                 | Player 3    | Player 2  | 1.823     |
| hw_060                                                 | Player 3    | Player 1  | 0.294     |
| hw_061                                                 | Player 3    | Player 1  | 0.323     |
| hw_062                                                 | Player 3    | Player 1  | 0.099     |
| hw_063                                                 | Player 3    | Player 1  | 0.674     |
| hw_064                                                 | Player 3    | Player 1  | 0.066     |
| hw_065                                                 | Player 3    | Player 1  | 0.070     |
| hw_066                                                 | Player 3    | Player 1  | 0.081     |
| hw_068                                                 | Player 3    | Player 2  | 0.278     |
| hw_071                                                 | Player 3    | Player 1  | 0.653     |
| hw_072                                                 | Player 3    | Player 2  | 0.401     |
| terminal_cal_P1/mixed_biometric_probe_20260406T021445Z | Player 1    | Player 2  | 1.158     |
| terminal_cal_P1/mixed_biometric_probe_20260407T225745Z | Player 1    | Player 3  | 0.841     |
| terminal_cal_P1/natural_grip_20260326T234127Z          | Player 1    | Player 3  | 0.180     |
| terminal_cal_P1/resting_baseline_20260326T233432Z      | Player 1    | Player 3  | 1.220     |
| terminal_cal_P1/spectral_accel_20260327T011014Z        | Player 1    | Player 3  | 1.079     |
| terminal_cal_P1/stick_sweeps_20260327T000958Z          | Player 1    | Player 3  | 0.613     |
| terminal_cal_P1/touchpad_corners_20260327T031241Z      | Player 1    | Player 3  | 1.152     |
| terminal_cal_P1/touchpad_corners_20260327T230404Z      | Player 1    | Player 3  | 0.103     |
| terminal_cal_P1/touchpad_corners_20260328T142201Z      | Player 1    | Player 3  | 0.945     |
| terminal_cal_P1/touchpad_corners_20260404T183706Z      | Player 1    | Player 3  | 0.362     |
| terminal_cal_P1/touchpad_corners_20260405T031958Z      | Player 1    | Player 2  | 1.710     |
| terminal_cal_P1/touchpad_freeform_20260327T030955Z     | Player 1    | Player 3  | 0.900     |
| terminal_cal_P1/touchpad_freeform_20260328T141850Z     | Player 1    | Player 3  | 0.278     |
| terminal_cal_P1/touchpad_freeform_20260404T183437Z     | Player 1    | Player 3  | 0.098     |
| terminal_cal_P1/touchpad_freeform_20260405T031703Z     | Player 1    | Player 2  | 0.614     |
| terminal_cal_P1/touchpad_swipes_20260327T030742Z       | Player 1    | Player 3  | 0.591     |
| terminal_cal_P1/touchpad_swipes_20260404T183208Z       | Player 1    | Player 3  | 0.092     |
| terminal_cal_P1/touchpad_swipes_20260405T031009Z       | Player 1    | Player 3  | 0.464     |
| terminal_cal_P1/touchpad_swipes_20260405T031430Z       | Player 1    | Player 3  | 0.572     |
| terminal_cal_P1/tremor_seed_20260405T002729Z           | Player 1    | Player 3  | 1.136     |
| terminal_cal_P1/tremor_seed_20260405T031320Z           | Player 1    | Player 3  | 0.913     |
| terminal_cal_P1/tremor_seed_20260405T204429Z           | Player 1    | Player 3  | 1.037     |
| terminal_cal_P2/button_sequence_20260327T021315Z       | Player 2    | Player 3  | 0.824     |
| terminal_cal_P2/mixed_biometric_probe_20260406T021844Z | Player 2    | Player 1  | 1.577     |
| terminal_cal_P2/mixed_biometric_probe_20260407T224620Z | Player 2    | Player 3  | 0.833     |
| terminal_cal_P2/natural_grip_20260327T015604Z          | Player 2    | Player 3  | 0.991     |
| terminal_cal_P2/natural_grip_20260329T032252Z          | Player 2    | Player 3  | 0.874     |
| terminal_cal_P2/resting_baseline_20260327T015045Z      | Player 2    | Player 3  | 1.150     |
| terminal_cal_P2/resting_baseline_20260329T031701Z      | Player 2    | Player 3  | 1.232     |
| terminal_cal_P2/spectral_accel_20260327T022944Z        | Player 2    | Player 3  | 1.800     |
| terminal_cal_P2/stick_sweeps_20260327T022131Z          | Player 2    | Player 3  | 1.044     |
| terminal_cal_P2/touchpad_corners_20260328T003556Z      | Player 2    | Player 1  | 0.258     |
| terminal_cal_P2/touchpad_corners_20260328T153820Z      | Player 2    | Player 1  | 0.183     |
| terminal_cal_P2/touchpad_corners_20260329T010156Z      | Player 2    | Player 3  | 0.133     |
| terminal_cal_P2/touchpad_corners_20260329T203046Z      | Player 2    | Player 3  | 0.399     |
| terminal_cal_P2/touchpad_corners_20260404T191532Z      | Player 2    | Player 1  | 0.297     |
| terminal_cal_P2/touchpad_corners_20260405T033521Z      | Player 2    | Player 3  | 0.661     |
| terminal_cal_P2/touchpad_corners_20260405T210457Z      | Player 2    | Player 1  | 0.891     |
| terminal_cal_P2/touchpad_freeform_20260328T003347Z     | Player 2    | Player 1  | 0.210     |
| terminal_cal_P2/touchpad_freeform_20260328T153604Z     | Player 2    | Player 3  | 0.441     |
| terminal_cal_P2/touchpad_freeform_20260329T005231Z     | Player 2    | Player 1  | 0.775     |
| terminal_cal_P2/touchpad_freeform_20260329T202820Z     | Player 2    | Player 1  | 0.212     |
| terminal_cal_P2/touchpad_freeform_20260404T191308Z     | Player 2    | Player 3  | 1.120     |
| terminal_cal_P2/touchpad_freeform_20260405T033248Z     | Player 2    | Player 1  | 0.088     |
| terminal_cal_P2/touchpad_freeform_20260405T205509Z     | Player 2    | Player 1  | 1.458     |
| terminal_cal_P2/touchpad_swipes_20260328T003136Z       | Player 2    | Player 1  | 1.695     |
| terminal_cal_P2/touchpad_swipes_20260328T153354Z       | Player 2    | Player 3  | 0.117     |
| terminal_cal_P2/touchpad_swipes_20260329T005021Z       | Player 2    | Player 3  | 1.209     |
| terminal_cal_P2/touchpad_swipes_20260329T202559Z       | Player 2    | Player 1  | 0.861     |
| terminal_cal_P2/touchpad_swipes_20260404T190950Z       | Player 2    | Player 1  | 0.095     |
| terminal_cal_P2/touchpad_swipes_20260405T032414Z       | Player 2    | Player 3  | 0.109     |
| terminal_cal_P2/touchpad_swipes_20260405T033016Z       | Player 2    | Player 3  | 0.188     |
| terminal_cal_P2/touchpad_swipes_20260405T204608Z       | Player 2    | Player 1  | 0.089     |
| terminal_cal_P2/tremor_seed_20260405T032335Z           | Player 2    | Player 3  | 1.101     |
| terminal_cal_P2/tremor_seed_20260405T032940Z           | Player 2    | Player 3  | 1.002     |
| terminal_cal_P2/tremor_seed_20260405T204530Z           | Player 2    | Player 3  | 0.996     |
| terminal_cal_P2/trigger_rhythm_20260327T020442Z        | Player 2    | Player 3  | 0.255     |
| terminal_cal_P3/button_sequence_20260328T014042Z       | Player 3    | Player 2  | 1.235     |
| terminal_cal_P3/mixed_biometric_probe_20260406T022141Z | Player 3    | Player 1  | 1.554     |
| terminal_cal_P3/mixed_biometric_probe_20260407T225423Z | Player 3    | Player 2  | 0.838     |
| terminal_cal_P3/natural_grip_20260328T005708Z          | Player 3    | Player 2  | 0.509     |
| terminal_cal_P3/natural_grip_20260328T012401Z          | Player 3    | Player 2  | 0.434     |
| terminal_cal_P3/resting_baseline_20260328T003917Z      | Player 3    | Player 2  | 1.244     |
| terminal_cal_P3/resting_baseline_20260328T011813Z      | Player 3    | Player 2  | 1.245     |
| terminal_cal_P3/spectral_accel_20260328T015847Z        | Player 3    | Player 2  | 0.419     |
| terminal_cal_P3/stick_sweeps_20260328T014814Z          | Player 3    | Player 2  | 0.870     |
| terminal_cal_P3/touchpad_corners_20260327T232204Z      | Player 3    | Player 2  | 0.451     |
| terminal_cal_P3/touchpad_corners_20260328T161059Z      | Player 3    | Player 2  | 1.162     |
| terminal_cal_P3/touchpad_corners_20260329T032924Z      | Player 3    | Player 2  | 0.647     |
| terminal_cal_P3/touchpad_corners_20260405T203336Z      | Player 3    | Player 1  | 0.596     |
| terminal_cal_P3/touchpad_corners_20260405T210733Z      | Player 3    | Player 1  | 1.821     |
| terminal_cal_P3/touchpad_freeform_20260327T231922Z     | Player 3    | Player 1  | 0.923     |
| terminal_cal_P3/touchpad_freeform_20260328T160809Z     | Player 3    | Player 1  | 0.391     |
| terminal_cal_P3/touchpad_freeform_20260329T032705Z     | Player 3    | Player 1  | 0.625     |
| terminal_cal_P3/touchpad_freeform_20260329T215205Z     | Player 3    | Player 1  | 1.232     |
| terminal_cal_P3/touchpad_freeform_20260404T203515Z     | Player 3    | Player 2  | 0.897     |
| terminal_cal_P3/touchpad_freeform_20260405T203100Z     | Player 3    | Player 1  | 1.060     |
| terminal_cal_P3/touchpad_freeform_20260405T205753Z     | Player 3    | Player 1  | 0.966     |
| terminal_cal_P3/touchpad_swipes_20260327T231705Z       | Player 3    | Player 2  | 0.734     |
| terminal_cal_P3/touchpad_swipes_20260329T032458Z       | Player 3    | Player 2  | 0.716     |
| terminal_cal_P3/touchpad_swipes_20260329T214956Z       | Player 3    | Player 2  | 0.640     |
| terminal_cal_P3/touchpad_swipes_20260405T202817Z       | Player 3    | Player 1  | 0.272     |
| terminal_cal_P3/touchpad_swipes_20260405T204800Z       | Player 3    | Player 1  | 0.358     |
| terminal_cal_P3/tremor_seed_20260405T202721Z           | Player 3    | Player 2  | 0.884     |
| terminal_cal_P3/tremor_seed_20260405T204725Z           | Player 3    | Player 2  | 1.059     |
| terminal_cal_P3/trigger_rhythm_20260328T011017Z        | Player 3    | Player 2  | 0.962     |
| terminal_cal_P3/trigger_rhythm_20260328T013207Z        | Player 3    | Player 1  | 1.612     |

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

1. **Player-specific fingerprinting needs more features.** The current separation ratio of 0.20 suggests feature augmentation or longer session windows before per-player identification is reliable.

2. **Touchpad biometrics.** All 69 sessions show zero touchpad activity (touch_active=False throughout). Adding the `touch_active`/`touch0_x` fields from capture_session.py Phase 17 will add player-specific thumb-resting patterns as a discriminator. This is expected to improve separation significantly.

3. **Micro-tremor variance.** The gyro-based still-frame filter (gyro_mag < 0.01) applies to raw LSB gyro values (range ~-350 to +350). With raw IMU values in the hundreds, most frames fail this threshold — the effective still-frame count is low. Consider calibrating the threshold to `gyro_mag < IMU_NOISE_FLOOR` (empirical: 332.99 LSB, 95th pct) to capture more tremor frames.

4. **Multi-session calibration window.** The live L4 oracle uses EMA over sessions. For inter-player separation in tournament contexts, accumulate ≥10 sessions per player before computing player centroid. The current N=55 sessions/player average is adequate.

5. **Full covariance vs. diagonal.** This analysis uses a full Tikhonov-regularized covariance matrix (off-diagonal terms included). The live L4 oracle currently uses a diagonal approximation. Upgrading to full covariance (TODO in the source) would better capture feature correlations and improve both intra-player consistency detection and inter-player separation.

6. **Tremor FFT window length.** The 50-frame window used here (vs 120-frame in live oracle) at 1000 Hz gives a frequency resolution of 20 Hz/bin, which is too coarse to resolve the 8-12 Hz physiological tremor band. The live oracle uses 120-frame windows (8.3 Hz/bin). For reliable tremor band power, a 1024-frame window at 1000 Hz would give 0.98 Hz/bin resolution (noted in CLAUDE.md as a known gap).

---
*Generated by `scripts/analyze_interperson_separation.py` — VAPI Phase 17, 2026-03-08*