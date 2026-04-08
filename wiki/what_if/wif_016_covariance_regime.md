# WHAT_IF: WIF-016 — Covariance Regime Instability at N~24 Transition Point

[VAPI:Phase166:VAPI_WHAT_IF.md:MEASURED]

## Classification

| Field | Value |
|-------|-------|
| Layer | W1 (Protocol Risk) |
| Status | MITIGATED (Phase 157 — cov_stability_check() + regime labels) |
| Filed | 2026-04-04 (AutoResearch cycle 6) |
| Phase mitigated | 157 |

## W1 — Failure Mode

Legitimate touchpad_corners enrollment growth from N=11 to N=24 crosses Phase 142's
`COV_MIN_RATIO=3.0` threshold (N/p = 24/8 = 3.0), triggering a silent covariance
regime switch that collapses P1/P3 distance from 3.276 to ~0.127 — invalidating
tournament eligibility without any fraudulent sessions.

**Adversary exploit:** Capture 3 sessions targeting a competitor's enrollment, push
their N/p to exactly 3.0, collapse their separation ratio. Economically motivated:
tournament exclusion of competitor has direct prize-pool benefit.

**Cryptographic grounding:** Phase 153 `SeparationRatioRegistry` commits ratio=1.261
at N=11. Live re-evaluation at N=24 disagrees — verifiable on-chain/off-chain
inconsistency.

## Mechanism

At N=11 (diagonal, N/p=1.375 < 3.0):
- P1 vs P3 distance = **3.276** (discriminating)

If N grows to N=24 (N/p=3.0, switches to full covariance):
- P1 vs P3 distance collapses to **~0.127** (97% suppression — Phase 141 artifact)

## Mitigation — Phase 157

```python
cov_regime_status: "diagonal_stable" | "transition_warning" | "full_covariance_active"
```

- `COV_STABILITY_MARGIN_NP = 0.5` — flags transition zone N/p ∈ [2.5, 3.5]
- `EnrollmentAutoGuidanceAgent` urgency = HIGH in transition zone
- Resolution: stay diagonal until N/p ≥ 5.0 (N ≥ 40/player)
- `cov_regime_status` field in `enrollment_auto_guidance_log`

## W2 — Opportunity (Phase 157)

Adaptive covariance-aware probe sequencing: `recommended_action` adapts to covariance
transition zone. First biometric enrollment system with Mahalanobis covariance-regime-aware
sequencing.

## Related Pages

- [[separation_ratio]]
- [[l4_thresholds]]
- [[agent_fleet]]
- [[wif_012_enrollment_count_gate]]
