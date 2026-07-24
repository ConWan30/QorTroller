---
name: biometric-calibration
description: Reference for the PITL nine-level stack, the L4 biometric feature space and thresholds, the calibration corpus state, and the humanity-probability formula. Read when working on separation ratio, L4/L5/L6 layers, corpus capture, or any anti-cheat scoring change.
---

# Biometric calibration reference

Domain reference, moved out of the always-loaded context. The numbers below are
measured, not aspirational — several are load-bearing for tournament gating.

## The constraints that bite

- **Separation ratio is the tournament gate**, and the honest number depends
  entirely on which corpus you measure. Free-form gameplay does not separate
  players (~0.06 on the full N=217 corpus) — that is the known WIF-009 plateau,
  not a bug, and it must never be quoted as the gate metric. Structured probes
  are what separate.
- **Per-player L4 thresholds can only tighten, never loosen** — enforced by
  `min()` in code. A recalibration that would raise a threshold is dropped.
- **L2C returns `None` in dead-zone stick games** (NCAA CFB 26), so its 0.10
  weight resolves to a 0.5 neutral prior. Any humanity-formula discussion has to
  acknowledge this phantom weight — the formula runs as effective 4-signal on
  that corpus. CFB 27 differs: the right stick is active in play, so L2C may
  compute non-None there.
- **`accel_magnitude_spectral_entropy` is a bot-vs-human discriminator only.**
  Player means are nearly identical (4.878 / 4.882 / 4.767). Never claim it
  improves separation.
- Stable EMA track updates on NOMINAL sessions only.

## PITL Nine-Level Stack

| Layer | Code | Type | Signal |
|-------|------|------|--------|
| L0 | — | Structural | HID presence |
| L1 | — | Structural | PoAC chain integrity |
| L2 | 0x28 | Hard cheat | IMU gravity + HID/XInput discrepancy |
| L3 | 0x29/0x2A | Hard cheat | TinyML behavioral classifier |
| L2B | 0x31 | Advisory | IMU-button causal latency |
| L2C | 0x32 | Advisory | Stick-IMU cross-correlation (inactive in dead-zone stick games) |
| L4 | 0x30 | Advisory | 12-feature Mahalanobis biometric fingerprint |
| L5 | 0x2B | Advisory | Temporal rhythm (CV, entropy, quantization) |
| L6 | — | Advisory | Active haptic challenge-response (disabled by default) |

Hard codes {0x28, 0x29, 0x2A} block tournament eligibility.
L2C returns None in dead-zone stick games (NCAA CFB 26) — 0.10 weight resolves to 0.5 neutral prior.

## Calibration Corpus State (2026-04-11) — 3-PLAYER CORPUS (P4 ELIMINATED)

- Total session files: **153 terminal + ~64 hw = 217 total** (5 excluded; massive new captures 2026-04-11)
  - Player 1: 50 terminal sessions (hw_005–hw_042 exc. 2 polling-rate + terminal_cal_P1; **8 touchpad_corners sessions**)
  - Player 2: 55 terminal sessions (terminal_cal_P2; **11 touchpad_corners sessions**)
  - Player 3: 48 terminal sessions (terminal_cal_P3; **10 touchpad_corners sessions**)
  - Player 4: **ELIMINATED** — confirmed same person as Player 3; all terminal_cal_P4 files moved to terminal_cal_P3
  - 5 excluded (polling_rate_hz outside [800, 1100]: hw_043, hw_044, hw_067, hw_069, hw_073)
- **CURRENT STATE (2026-04-20, UPDATED): AIT DEFENSIBILITY GATE CLEAR — all players >=10 sessions**
  - **AIT probe (Phase 229, 2026-04-18)**: ratio=**1.199**, all_pairs_above_1=**True** (N=24: P1=6/P2=5/P3=13) — Phase 229 baseline
  - **AIT corpus (Phase 231, 2026-04-20)**: N=37 total — P1=13/P2=10/P3=14; all players >=10; ait_defensibility_ok=True; STAGED_GRADUATION_ENABLED=true
  - AIT inter-player: P1vP2=1.850, P1vP3=1.846, P2vP3=1.349 — ALL >1.0 (TOURNAMENT BLOCKER CLEARED for AIT)
  - AIT LOO accuracy: 66.7% (16/24); cov_mode=full (N/p=6.0 > COV_MIN_RATIO=3.0)
  - AIT features [4]: accel_tremor_peak_hz (4096-pt FFT 4-15 Hz, parabolic interp) + roll_cos/roll_sin/pitch_cos (gravity postural fingerprint, circular encoding)
  - AIT physics: L2 hold at 50% (90-180 analog), 30s; still-hold activates accel tremor (right_stick=128 neutral); gravity vector anatomically stable per player in normal gaming posture
  - **Touchpad corners (superseded for primary gate)**: N=35, ratio=0.728 (2026-04-11); P2/P3 biometric proximity structurally prevents crossing 1.0; diagnostic ceiling confirmed
  - **tremor_resting corpus (2026-04-12)**: ratio=0.748 (N=24); all_pairs_p0_ok=False (P1vP3=0.032 per G-001); tremor_peak_hz now non-zero via Phase 205 AccelTremorFFT; P3 non-stationarity still limiting
  - **Path forward**: AIT defensibility gate CLEAR (Phase 231 — P1=13/P2=10/P3=14 all>=10); run POST /agent/activate-graduation-stage {agent_id: "ruling_enforcement_agent"} to execute Stage 1; then run --session-type ait --write-snapshot to persist N=37 corpus to DB
  - NOTE: Phase 231 COMPLETE — ait_defensibility_ok=True (11th P0 condition); STAGED_GRADUATION_ENABLED=true; Stage 1 pending API call; Phase 230 NOTE: insert_ait_session() mirrors to separation_defensibility_log; all_pairs_p0_ok=True
  - WIF-024: CLOSED Phase 165 — post_erasure_recompute audit trail implemented
- **Full corpus (N=217, all session types)**: ratio=0.060 — EXPECTED/KNOWN (free-form gameplay doesn't separate players; this is the WIF-009 plateau regime result; never use this as the tournament gate metric)
- **PHASE 143 RESULT (2026-04-02): N=11 — historical baseline (superseded by N=14 above)**
  - Separation ratio: **1.261** (diagonal covariance, N/p=1.375 < 3.0, Phase 142 auto-fallback)
  - Classification: **63.6% (7/11, proper LOO)** — honest estimate (Phase 143); 4 misclassified sessions
  - Inter-player pairs: P1 vs P2=2.868, P1 vs P3=3.276, P2 vs P3=2.243
  - Intra-player: P1 mean=2.963 (N=3), P2 mean=1.976 (N=4), P3 mean=1.711 (N=4)
  - NOTE: diagonal covariance correct for N=11; full Tikhonov suppressed P1/P3 to 0.127 (97% suppression)
  - Per-pair attribution: P1vP2 top=micro_tremor+stick_autocorr; P1vP3 top=touch_position_variance+touchpad_spatial_entropy
- **PHASE 138 RESULT (2026-04-02): Full Tikhonov covariance (SUPERSEDED by Phase 143)**
  - Separation ratio: **1.552** — inflated by full covariance; P1 vs P3 distance=0.127 was noise-suppressed
  - Classification: 63.6% (7/11, biased-centroid LOO) — same classification but different error profile
  - Inter-player pairs: P1 vs P2=1.428, P1 vs P3=0.127, P2 vs P3=1.304
  - Intra-player: P1 mean=0.839 (N=3, full covariance), P2 mean=0.505, P3 mean=0.499
  - **P1/P3 distance=0.127 was covariance noise artifact** — diagonal (Phase 142) gives P1vP3=3.276
- **PHASE 137B RESULT (2026-03-30): PRE-MERGE reference only**
  - Ratio was 1.469 (N=11, 4 players P1=3/P2=4/P3=3/P4=1) — P4 counted as separate → SUPERSEDED
  - P3 vs P4 distance=0.074 was intra-player variance (same person), incorrectly counted as inter-player
- **PHASE 137A RESULT (2026-03-30): WIF-007 balanced corpus confirmation**
  - Balanced ratio: **1.611** (n=3/player, N=12 balanced; seed=42; per-player equalization)
  - WIF-007 confirmed: P1's 53 sessions bias global covariance; balanced ratio >> pooled ratio
  - Reliable estimate requires ≥10 sessions/player balanced
- Full corpus separation ratio: **0.417 pooled** (N=127 pre-merge, 2026-03-29) — STALE, superseded by 1.261 (diagonal+LOO, touchpad_corners, Phase 143)
  - Classification rate on full corpus: 30.8% — free-form gameplay insufficient for separation
- L4 thresholds CONFIRMED (2026-04-02): ran threshold_calibrator.py on all 74 hw_*.json → anomaly=**7.009**, continuity=**5.367** — IDENTICAL to stored values; staleness is dimension-only (calib_dim=12 vs live_dim=13); touchpad_spatial_entropy is structurally 0 in gameplay sessions so adding it doesn't change thresholds; thresholds remain valid for gameplay sessions
- Phase 139 COMPLETE: _TERMINAL_CAL_ONLY_TYPES fast-path in analyze_interperson_separation.py — skips 74 hw_* sessions when session_type_filter in {touchpad_corners, freeform, swipes, ...}; reduces analysis runtime from 120s+ to <30s; Bridge +8 (1734→1742); SDK 233 unchanged; Hardhat 462 unchanged
- Phase 144 COMPLETE: --player-quality-report flag; _compute_player_quality_scores() per-player stability/probe-type/enrollment-ready/recommendations; ENROLLMENT_STABILITY_THRESHOLD=0.70 ENROLLMENT_MIN_PROBE_TYPES=2; Bridge +8 (1774→1782); SDK 233 unchanged; Hardhat 462 unchanged
- Phase 140 COMPLETE: --probe-comparison flag; runs all 3 touchpad probe types (corners/freeform/swipes) and outputs comparison table with ratio/classification/inter/intra/P1vP3; Bridge +8 (1742→1750); SDK 233 unchanged; Hardhat 462 unchanged
- Touchpad coverage: P1=6 touchpad_corners, P2=7 touchpad_corners, **P3=7 touchpad_corners** (total 20, 2026-04-05)
  - touchpad_freeform and touchpad_swipes: roughly symmetric with corners; exact counts from analysis script

## L4 Calibration State (Phase 57, N=74)

- Calibration corpus: hw_005–hw_078 (N=74 including newer tremor/touchpad sessions)
- Feature space: 12 features, 10 active (Phase 46 added accel_magnitude_spectral_entropy; Phase 57 added press_timing_jitter_variance)
- Active features (10): trigger_resistance_change_rate(excl), trigger_onset_velocity_L2,
  trigger_onset_velocity_R2, micro_tremor_accel_variance, grip_asymmetry,
  stick_autocorr_lag1, stick_autocorr_lag5, tremor_peak_hz, tremor_band_power,
  accel_magnitude_spectral_entropy, touch_position_variance(excl pending recapture),
  press_timing_jitter_variance (index 11 — normalised IBI variance; human 0.001–0.05; bot macro <0.00005)
- Structurally zero / excluded: trigger_resistance_change_rate, touch_position_variance
  (touchpad_active_fraction replaced by accel_magnitude_spectral_entropy in Phase 46)
- L4 anomaly threshold: **7.009** (mean+3σ, Phase 57, N=74, 12-feature space — was 6.726 Phase 46)
- L4 continuity threshold: **5.367** (mean+2σ, Phase 57, N=74, 12-feature space — was 5.097 Phase 46)
- Threshold rise (+4.2%/+5.3%): expected — press_timing_jitter_variance adds real variance, expands Mahalanobis distribution
- Inter-person separation ratio: 0.362 — L4 is intra-player anomaly detector only
- Human false positive rate: ~2.9% (expected at 3σ)

## accel_magnitude_spectral_entropy (Phase 46, index 9)

Replaces structurally-zero touchpad_active_fraction.
Physics: Shannon entropy of the 0–500 Hz power spectrum of DC-removed ||accel||.
Requires 1000 Hz polling — cannot be computed on standard HID (125–250 Hz) devices.
Ring buffer: 1024 frames, follows Phase 41 pattern (returns 0.0 until filled).
Human range: 3–8.6 bits, tightly centered at 4.8–4.9 bits (std 1.303).
Static injection: 0.0 (variance guard). Random noise: ~9.0 bits (detectable).
Player means nearly identical (P1: 4.878, P2: 4.882, P3: 4.767) — bot-vs-human
discriminator only, NOT inter-player identifier. Does not improve separation ratio.
Negative result documented: docs/phase-coherence-calibration.md (accel_phase_coherence
ruled out — gravity dominates accel during still frames in handheld gaming grip).

## Humanity Probability Formula (Phase 46)

Without L6 (default):
  humanity_probability = 0.28·p_L4 + 0.27·p_L5 + 0.20·p_E4 + 0.15·p_L2B + 0.10·p_L2C
  NOTE: p_L2C resolves to 0.5 neutral prior in dead-zone stick games (NCAA CFB 26).
  Formula runs as effective 4-signal in practice for this game corpus.
  CFB 27 caveat (2026-07-18, cfb27-r02): the 26 dead-zone assumption does NOT transfer — 27's right
  stick is ACTIVE in-play (Tackle Stick + carrier moves), so L2C may compute non-None; the weight
  stays advisory 0.10 (telemetry-shape change, not a reweight; profile `ncaa_cfb_27` registered).

With L6 active:
  p_human = 0.23·p_L4 + 0.22·p_L5 + 0.15·p_E4 + 0.15·p_L6 + 0.15·p_L2B + 0.10·p_L2C

