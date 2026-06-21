# CCO Phase G — MID_TIER Operator Attestation (2026-06-20)

| Field | Value |
|-------|-------|
| Tier | MID_TIER |
| Primary profile | `sony_dualsense_v1` |
| Corpus N | 130 (gate ≥50 **REACHED**) |
| Measurement grade (attested) | **VALIDATED** |
| Challenge verifier | `RumbleImuVerifier` (`l9_presence/challenge_verifier.py`) |
| PoEP live | **false** (Phase C measurement only) |

## Attestation scope

Operator attests that:

1. Per-tier L6B corpus N≥50 is satisfied for mid-tier controllers.
2. FAR/FRR review completed (`audits/cco-phase-g-far-frr-review-2026-06-20.md`).
3. HUMAN subset (N=50) shows FRR proxy 0.0 with REFLEX_OBSERVED on all HUMAN rows.
4. `rumble_imu` device-auth verifier uses measured baseline from this corpus — not universal partner language for all mid-tier SKUs until each profile is tagged and reviewed.

## Env activation

```env
CCO_PHASE_G_DEFERRED_TIERS=MINIMAL_PAD
CCO_PHASE_G_VALIDATED_TIERS=MID_TIER,PREMIUM_EDGE
CCO_RESEARCH_SURFACE_ENABLED=true
```

## Out of scope

- Tournament-grade P-T1 claims on SCUF/Xbox Elite without per-profile corpus.
- Live PoEP / L6B production enablement (`poep_enabled`, `L6B_ENABLED` unchanged).

**Operator:** attested 2026-06-20 (desk corpus + Phase C verifier measurement).
