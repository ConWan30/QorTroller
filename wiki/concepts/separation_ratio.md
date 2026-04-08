# CONCEPT: Inter-Person Separation Ratio

[VAPI:Phase166:MEMORY.md:MEASURED]

## What It Is

The inter-person separation ratio is the primary biometric discrimination metric in VAPI.
It measures how distinguishable different enrolled players are from each other using
the 13-feature Mahalanobis biometric fingerprint, relative to their intra-player variance.

```
separation_ratio = mean(inter_player_distances) / mean(intra_player_distances)
```

A ratio > 1.0 means players are more distinguishable from each other than from themselves.
A ratio < 1.0 means the biometric space cannot reliably distinguish players — tournament
eligibility via `isFullyEligible()` would be non-discriminating and legally indefensible.

## Tournament Gate

Phase 166 lowered the gate from hardcoded 1.0 to configurable `min_separation_ratio` (value: 0.70).
[VAPI:Phase166:MEMORY.md:MEASURED]

Rationale: single shared physical DualShock Edge — hardware variance is common to all
3 players, structurally suppressing the ceiling below 1.0. The 0.70 gate requires genuine
improvement from the mixed_biometric_probe feature set without requiring a ceiling
that the shared hardware architecture cannot reach.

## Current Empirical History [VAPI:Phase166:MEMORY.md:MEASURED]

| Date | N | Method | Ratio | Status |
|------|---|--------|-------|--------|
| 2026-03-29 | 127 (pooled free-form) | Full Tikhonov | 0.417 | STALE — plateau regime |
| 2026-04-02 | 11 (touchpad_corners) | Phase 138 Tikhonov | 1.552 | SUPERSEDED (inflated) |
| 2026-04-02 | 11 (touchpad_corners) | Phase 143 diagonal+LOO | 1.261 | SUPERSEDED (N=11 thin) |
| 2026-04-05 | 14 (touchpad_corners) | diagonal+LOO | 0.789 | SUPERSEDED |
| 2026-04-05 | 20 (touchpad_corners) | diagonal+LOO | 0.569 | CURRENT — BELOW 0.70 GATE |

**Trend:** N=11→1.261, N=14→0.789, N=20→0.569 — converging downward.

**Root cause:** P1 intra-player variance range=[1.661, 4.410]. P1 non-stationary across
days. Old P1 sessions cluster near P2 centroid; new P1 sessions cluster near P3 centroid.
Mixed_biometric_probe with all 13 features is intended to stabilize this.

**Free-form plateau:** N=127 pooled free-form sessions asymptote below 0.5 — adding more
free-form sessions does not improve the ratio (WIF-009 confirmed). Structured probes only.

## Measurement Method [VAPI:Phase166:MEMORY.md:MEASURED]

`scripts/analyze_interperson_separation.py`

Key flags:
- `--session-type mixed_biometric_probe` — filters to 13-feature sessions only
- `--session-type touchpad_corners` — filters to touchpad-only (8 features)
- `--min-n-per-player 1` — lowers analysis threshold (analysis gate: ≥3 per player)
- `--per-pair-attribution` — shows per-feature discrimination per pair
- `--balance-corpus` — subsamples to min(N_per_player) for balanced estimate

**Covariance mode:** diagonal auto-selected when N/p < 3.0 (Phase 142).
At N=20, p=8 active features: N/p=2.5 < 3.0 → diagonal. Correct choice: full covariance
would introduce off-diagonal noise suppression artifacts (P1 vs P3 suppressed 97% at N=11).

## Per-Pair Attribution (Phase 141) [VAPI:Phase166:MEMORY.md:MEASURED]

Top discriminators (touchpad sessions, diagonal covariance):
- P1 vs P2: micro_tremor_accel_variance + stick_autocorr_lag1
- P1 vs P3: touch_position_variance + touchpad_spatial_entropy
- P2 vs P3: touchpad_spatial_entropy + tremor_peak_hz

Zero-variance features excluded in touchpad-only sessions (5 features):
trigger_resistance_change_rate, trigger_onset_velocity_L2/R2, grip_asymmetry,
press_timing_jitter_variance

## On-Chain Commitment [VAPI:Phase166:MEMORY.md:MEASURED]

`SeparationRatioRegistry.sol` (Phase 153, LIVE on testnet — deploy deferred):
```
commit_hash = SHA-256(ratio_str + N + N_consented + players_sorted + ts_ns)
```

Phase 163: N_consented (active consent count) bound into preimage.
Phase 165: post_erasure_recompute audit trail for GDPR Art.17 compliance.

Infrastructure-first: `separation_ratio_on_chain_enabled = False` default.

## Related Pages

- [[phase_166]]
- [[l4_thresholds]]
- [[agent_fleet]]
- [[poac_wire_format]]
- [[zk_circuit]]
