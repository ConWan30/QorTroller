# CCO Phase G — FAR/FRR Review (2026-06-20)

**DB:** `C:\Users\Contr\.vapi\bridge.db`  
**Script:** `python scripts/cco_phase_g_far_frr_report.py`  
**Reclassify replay:** `python scripts/l6b_corpus_reclassify_report.py`

## Method

Proxy metrics for desk L6B corpus (not live tournament gate rates):

| Metric | Definition |
|--------|------------|
| **FAR proxy** | Share of rows with classification ∈ {BOT, INCONCLUSIVE, NO_RESPONSE} |
| **FRR proxy** | Share of HUMAN rows without `reflex_verdict=REFLEX_OBSERVED` |

True-latency replay (`human_max=350`) supplements legacy index×8ms classifications.

## Per-tier results (stored classifications)

### MID_TIER — `sony_dualsense_v1` (N=130)

| Field | Value |
|-------|-------|
| HUMAN / REFLEX_OBSERVED | 50 / 50 |
| FRR proxy (HUMAN subset) | **0.0** |
| FAR proxy (full tier) | 0.6154 (80 non-HUMAN calibration rows) |
| HUMAN latency p50 | 185.97 ms |
| HUMAN peak p50 | 972.79 LSB |

**Read:** Mid-tier device-auth verifier (`rumble_imu`) measured on 50 HUMAN rows. Full-corpus FAR proxy is inflated by deliberate calibration failures and inconclusive captures — not a production false-accept rate.

### PREMIUM_EDGE — `sony_dualshock_edge_v1` (N=210)

| Field | Value |
|-------|-------|
| Stored HUMAN | 0 |
| reflex_verdict set | 0 |
| FAR proxy | 1.0 (all stored non-HUMAN) |

**Read:** Edge desk corpus predates reflex_verdict backfill on stored rows. True-latency replay across full DB @350ms yields 88 HUMAN / 314 total — Edge-specific replay per profile recommended before VALIDATED attestation on reflex path.

### MINIMAL_PAD

Deferred via `CCO_PHASE_G_DEFERRED_TIERS=MINIMAL_PAD` — no reference hardware.

## True-latency replay (all profiles)

```
@ human_max=350: HUMAN=88, BOT=18, INCONCLUSIVE=83, NO_RESPONSE=125 (N=314)
force=200 subset @350: HUMAN=38, BOT=4, INCONCLUSIVE=14, NO_RESPONSE=23 (N=79)
```

## Operator actions

1. Accept MID_TIER + PREMIUM_EDGE corpus gates (N≥50 reached).
2. Set `CCO_PHASE_G_DEFERRED_TIERS=MINIMAL_PAD`.
3. After sign-off: `CCO_PHASE_G_VALIDATED_TIERS=MID_TIER,PREMIUM_EDGE` (optional PREMIUM_EDGE caveat above).
4. Phase C: `RumbleImuVerifier` ships with measured baseline — `poep_enabled` remains false.
