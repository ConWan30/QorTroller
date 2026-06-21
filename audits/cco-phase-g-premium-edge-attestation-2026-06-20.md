# CCO Phase G — PREMIUM_EDGE Operator Attestation (2026-06-20)

| Field | Value |
|-------|-------|
| Tier | PREMIUM_EDGE |
| Primary profile | `sony_dualshock_edge_v1` |
| Corpus N | 210 (gate ≥50 **REACHED**) |
| Measurement grade (attested) | **VALIDATED** (corpus gate + adaptive_force regression) |
| Challenge verifier | `AdaptiveForceVerifier` (Edge P4a path) |
| L6B reflex backfill | **PARTIAL** — stored rows lack reflex_verdict; replay recommended |

## Attestation scope

Operator attests that:

1. Per-tier L6B corpus N≥50 is satisfied for DualShock Edge desk captures.
2. PoEP `adaptive_force` regression parity preserved (`test_poep_calibration.py` Edge fixtures).
3. Stored-classification FAR review shows 0 HUMAN rows — **honest caveat:** legacy storage used index latency; true-latency replay shows HUMAN signal in combined corpus. Partner language must cite Edge adaptive-force path separately from mid-tier `rumble_imu`.

## Env activation

Included in `CCO_PHASE_G_VALIDATED_TIERS=PREMIUM_EDGE` alongside MID_TIER when operator accepts corpus gate + adaptive_force parity.

## Follow-up (non-blocking)

- Backfill `reflex_verdict` on Edge `l6b_probe_log` rows via diagnostic replay.
- Empirical Unknown #1 adaptive-trigger separability remains Stage A measurement.

**Operator:** attested 2026-06-20 (corpus gate + Edge verifier regression; reflex backfill deferred).
