# CCO Phase G — Stage A Capture Plan / Measurement Runbook

**Status:** Active runbook for closing the Phase G empirical-measurement debt.
**Anchors:** `wiki/methodology/CCO_POEP_FUSION_v4.md` §10 Phase G, §6 maturity matrix;
`wiki/methodology/CCO_PHASE_G_RESEARCH_v1.md`; the three 2026-06-20 attestation audits.

This document makes the Phase G `[UNVALIDATED]` debt concrete: what is already
measured, what remains, and the exact procedure to close each gap.

---

## 1. Verified status (as of 2026-06-21)

| Tier | Primary profile | Corpus N | Gate ≥50 | Grade | Verifier |
|------|-----------------|----------|----------|-------|----------|
| **PREMIUM_EDGE** | `sony_dualshock_edge_v1` | **210** | ✅ REACHED | **VALIDATED** (corpus gate + adaptive_force regression) | `AdaptiveForceVerifier` |
| **MID_TIER** | `sony_dualsense_v1` | **130** | ✅ REACHED | **VALIDATED** (HUMAN N=50, FRR proxy 0.0) | `RumbleImuVerifier` |
| **MINIMAL_PAD** | _(none — commodity pad)_ | 0 | ❌ | **DEFERRED** (no reference hardware) | generic timing (TBD) |

Operator-attested env (per audits):
```
CCO_PHASE_G_VALIDATED_TIERS=MID_TIER,PREMIUM_EDGE
CCO_PHASE_G_DEFERRED_TIERS=MINIMAL_PAD
CCO_RESEARCH_SURFACE_ENABLED=true
```

**Conclusion:** two of three tiers are measured and operator-attested. Phase G is
no longer "scaffold only" for Edge/mid — it is **partially VALIDATED**. The
remaining Stage A debt is the three items in §2.

---

## 2. Remaining Stage A debt (the three open gates)

### G-STAGE-A.1 — MINIMAL_PAD capture (hardware-blocked)
The only fully-unmeasured tier. Blocked on acquiring a commodity pad with **no
adaptive triggers** (the I-0 / P-T0 floor case). Runbook in §3.

### G-STAGE-A.2 — Edge reflex_verdict backfill (quality, non-blocking)
Edge corpus reached the gate, but stored `l6b_probe_log` rows used legacy
index×8ms latency and lack `reflex_verdict`. The true-latency replay
(`human_max=350`) shows HUMAN signal, but the stored rows should be backfilled so
the FAR/FRR artifact reflects true-latency classification. Runbook in §4.

### G-STAGE-A.3 — Empirical Unknown #1 (adaptive-trigger separability)
The deeper research gate from Sensor Stack v2.1: intra- vs inter-player
Mahalanobis separability of the adaptive-trigger force-curve
(N=10 players × 100 pulls × 3 contexts; threshold > 1.0 separation ratio for
PRIMARY-DISCRIMINATOR status). This is a multi-player study, distinct from the
single-operator desk corpus, and remains **[UNVALIDATED]**. Out of scope for the
desk-capture runbook; tracked here so it is not forgotten.

---

## 3. MINIMAL_PAD capture runbook (G-STAGE-A.1)

Mirrors the desk L6B protocol that produced the Edge (N=210) and mid (N=130)
corpora. Target: **N≥50 HUMAN reflex captures** on the minimal pad.

**Hardware precondition:** a commodity USB gamepad WITHOUT adaptive triggers
(e.g., a basic XInput pad). Confirm it enumerates and the bridge resolves a
profile (or falls through to a generic profile). Note its VID/PID.

**Procedure:**
1. Connect the pad via USB; confirm `GET /operator/bridge/retina-status` /
   capture-health shows a stable poll rate and the device is detected (no
   simulation mode).
2. Set the capture profile/tier for the session:
   ```
   DEVICE_PROFILE_ID=<minimal_pad_profile_id>     # or generic
   L6B_ENABLED=true                                # capture only; PoEP stays gated
   ```
   Do NOT set `POEP_ENABLED=true` — capture is measurement, not live verdicts.
3. Run the desk reaction session to collect reflex probes:
   ```
   python scripts/l6b_desk_reaction_session.py --player P1 --target 50
   ```
   (Repeat across ≥1 operator; the Edge/mid corpora were single-operator desk
   captures — match that bar for v1, expand for multi-player later.)
4. Monitor progress:
   ```
   python scripts/l6b_probe_status.py
   python scripts/l6b_live_monitor.py
   ```
5. When N≥50 HUMAN rows exist for the minimal profile, run the FAR/FRR proxy:
   ```
   python scripts/cco_phase_g_far_frr_report.py
   python scripts/cco_phase_g_measurement_status.py
   ```
6. **Device-auth note:** a minimal pad has no adaptive triggers AND no confirmed
   rumble+IMU reflex channel — so its device-auth verifier is **generic timing
   (liveness latency only)**. Per CCO honesty discipline it must return
   `UNCHARACTERIZED` for device-auth and only `REFLEX_OBSERVED` (P-T0) for
   liveness. Do NOT reuse the Edge `adaptive_force` or mid `rumble_imu` baselines
   for the minimal tier — measure or mark UNCHARACTERIZED.

**Promotion (DEFERRED → VALIDATED):** when the gate is reached, write
`audits/cco-phase-g-minimal-pad-attestation-<date>.md` (template §5) and move
`MINIMAL_PAD` from `CCO_PHASE_G_DEFERRED_TIERS` to `CCO_PHASE_G_VALIDATED_TIERS`.

---

## 4. Edge reflex_verdict backfill runbook (G-STAGE-A.2)

```
python scripts/l6b_corpus_reclassify_report.py          # true-latency replay (human_max=350)
python scripts/cco_phase_g_far_frr_report.py            # regenerate FAR/FRR with backfilled verdicts
```
Then regenerate `audits/cco-phase-g-premium-edge-attestation-<date>.md` so the
Edge FAR/FRR cites true-latency HUMAN rows rather than the legacy-index caveat.
Non-blocking: Edge is already VALIDATED on the corpus gate + adaptive_force
regression; this only upgrades the FAR/FRR evidence quality.

---

## 5. Per-tier attestation template

```markdown
# CCO Phase G — <TIER> Operator Attestation (<date>)

| Field | Value |
|-------|-------|
| Tier | <TIER> |
| Primary profile | `<profile_id>` |
| Corpus N | <n> (gate ≥50 <REACHED/NOT REACHED>) |
| Measurement grade (attested) | <VALIDATED / UNVALIDATED> |
| Challenge verifier | `<verifier>` |
| PoEP live | false (Phase C measurement only) |

Operator attests: corpus N≥50; FAR/FRR review completed; HUMAN subset FRR proxy;
device-auth verifier uses measured baseline for THIS tier only (no universal
partner language until each profile is tagged + reviewed).
```

---

## 6. What this does NOT unlock

- **No live PoEP `PRESENT`.** Activation stays operator-gated: `POEP_ENABLED`,
  `L6B_ENABLED`, `CCO_COMPOSABILITY_ENABLED` remain false until an explicit
  activation decision (corpus + env flip + complete telemetry).
- **No "universal" partner language.** Per-tier claims only; minimal/multi-class
  FAR/FRR (G-STAGE-A.3) is still required before any cross-class assurance claim.
- **No on-chain presence tiers.** Lens v3 / presence-tier composition stays
  DESIGN under `CHAIN_SUBMISSION_PAUSED` deploy-hold.
