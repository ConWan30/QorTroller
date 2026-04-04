# WHAT_IF Entry — AutoResearch Cycle 6 (2026-04-04)

**Source**: AutoResearch cycle 6, score=1.000
**Phase**: 156 → 157 candidates

---

## WIF-016 — Covariance Regime Instability: Silent Separation Ratio Collapse at N~24 (Phase 157 candidate)

**W1 — Failure mode**: Legitimate enrollment growth from N=11 to N=24 touchpad_corners sessions crosses the Phase 142 `COV_MIN_RATIO=3.0` diagonal auto-fallback threshold (N/p = 24/8 = 3.0), triggering a covariance regime switch that silently collapses P1/P3 inter-player distance from 3.276 to ~0.127 — invalidating tournament eligibility without any fraudulent sessions.

**Implication**: `get_separation_defensibility_status()` re-evaluates dynamically using current session data. An N/p crossing event at N=24 causes `defensible=True` to flip to `defensible=False` with no clear root cause visible to operators. `EnrollmentAutoGuidanceAgent` continues reporting `sessions_needed_total > 0` even though the 10/player count threshold was met. Adversary exploit: capture exactly 3 sessions targeting a competitor's enrollment to push their N/p from 2.625 to 3.0, triggering the regime flip and invalidating their eligibility.

**Cryptographic grounding**: Phase 153 SeparationRatioRegistry commits `SHA-256(ratio_str + N + players_sorted + ts_ns)` on-chain at N=11. The live dynamic evaluation at N=24 would disagree — creating a verifiable on-chain/off-chain inconsistency. Economically motivated: tournament exclusion of a competing player has direct prize-pool benefit.

**Mitigation**: Phase 157 `COV_STABILITY_MARGIN_NP=0.5` check in `get_separation_defensibility_status()`:
```python
if abs(n_over_p - COV_MIN_RATIO) < COV_STABILITY_MARGIN_NP:
    flags.append("COVARIANCE_TRANSITION_WARNING")
    urgency_level = "HIGH"
```
`EnrollmentAutoGuidanceAgent` escalates `urgency_level` to HIGH on COVARIANCE_TRANSITION_WARNING. Resolution path: either lock `COV_MIN_RATIO` at a very high value (stay diagonal permanently) or grow enrollment to N/p ≥ 5.0 (N ≥ 40/player) before enabling full covariance.

**Status**: OPEN — Phase 157 candidate

---

## WIF-017 — Adaptive Covariance-Aware Probe Sequencing (Phase 157 candidate)

**W2 — Opportunity**: Extend `EnrollmentAutoGuidanceAgent` with `cov_regime_status` field that prevents blind enrollment growth into the N/p covariance instability zone.

**Mechanism**:
1. `cov_regime_status` field in `enrollment_auto_guidance_log`: `"diagonal_stable"` (N/p < 2.5), `"transition_warning"` (2.5 ≤ N/p < 3.5), `"full_covariance_active"` (N/p ≥ 3.5)
2. When `"transition_warning"`: `recommended_action` switches from `"capture_touchpad_corners"` to `"evaluate_covariance_regime_before_capture"`
3. If operator continues: system recommends capturing ≥ 10 additional sessions per player (bypassing instability zone; target N/p ≥ 5.0)
4. `COV_STABILITY_MARGIN_NP=0.5` config field (default; adjustable)

**Why it works**: Transforms passive session counting into active covariance regime management. The N/p transition zone (2.5–3.5) is now explicitly surfaced before it triggers a separation ratio collapse.

**Phase candidate**: Phase 157 — `cov_stability_check()` in `analyze_interperson_separation.py` + `COV_STABILITY_MARGIN_NP` config + `cov_regime_status` column in `enrollment_auto_guidance_log` + updated `EnrollmentAutoGuidanceAgent` logic (~2h effort)

**Exclusive because**:
- Requires Phase 142 COV_MIN_RATIO auto-fallback + Phase 143 LOO + Phase 150 defensibility gate + Phase 156 enrollment guidance — all VAPI-exclusive infrastructure
- First biometric enrollment system with Mahalanobis covariance-regime-aware enrollment sequencing guidance

**Status**: NEW — Phase 157 candidate
