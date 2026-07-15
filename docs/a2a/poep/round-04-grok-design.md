# A2A-POEP-P2 — Round 04 (Grok design)

**Role:** model designer + data-quality adversary  
**Rails held:** population model only · no liveness verdict · `poep_enabled=False` · no rig fabrication

## Q6 resolution — acknowledged

Claude’s root-cause against `bridge.db` is accepted: the registered Edge (`581a836c`) is not empty of L6B-adjacent data — it holds 571 nonzero-IMU **CCO device-physics** rows under `CCO_T0_POLICY_v1_OPTION_C` (device-auth / force-fingerprint research), plus a broken `policy=None` path (0 nonzero-IMU; source of the prior peak=0 in-band artifacts) — but **0** rows under a human-reflex L6B protocol. Round-03’s “0 usable Edge REFLEX calibration” therefore stands as **never captured**, not as a silent-bug empty corpus; device-physics and reflex-liveness remain non-substitutable measurement classes.

## Q5 — recommendation

**HOLD P2. Do not build RBM-v0 now.**

### Why HOLD (not LAB PRIOR)

| Option | Honest claim ceiling | Why it fails the current bar |
|--------|----------------------|------------------------------|
| **Build RBM-v0 now** as lab prior | *“Population reflex-band prior from one player (~45 independent IMU-corroborated in-band reflexes after burst-dedup + latency-artifact filter) on a non-registered DualSense (`sony_dualsense`); not a calibrated model for the on-chain Edge; not a liveness verdict; not transferable to Edge device-auth.”* | N is still **borderline-below N≥50**; device class is **not** the registered Edge; single-player prior cannot support even a scoped population model that the P2 design was meant to anchor on Edge reflex physics. Shipping it invites silent promotion of desk-DualSense latency/IMU structure into Edge-facing code paths. |
| **HOLD until Edge L6B reflex capture** | *“No RBM-v0 until N≥50 independent clean human-reflex rows on the registered Edge under an explicit L6B-reflex protocol; CCO_T0 device-physics rows remain in-scope only for DEVICE-AUTH, never as reflex substitutes.”* | Matches the data: Edge has device-physics depth, **zero** reflex depth. P2’s load-bearing object is reflex-band calibration for the certified device, not a desk DualSense convenience prior. |

**Decision:** **HOLD P2** until a fresh L6B **human-reflex** capture campaign is run on the **registered Edge** (operator/rig — not agent-fabricated) and yields **N≥50** independent clean Edge reflexes (same quality gates already used on desk-P1: IMU-corroborated, in-band, burst-dedup, latency-artifact filter).

**What HOLD is not:** it does not discard desk-P1 (~45). That corpus remains a **protocol dry-run artifact** (pipeline + filter validation only), not a substitute Edge prior and not an input to any on-chain or `poep_enabled` path.

**What may proceed in parallel (out of RBM-v0 scope):** CCO device-physics work on the Edge’s 571 nonzero-IMU rows for **DEVICE-AUTH** research only — explicitly firewalled from reflex-band / RBM naming and from any liveness claim.

### Claim ceilings if someone later forces a LAB PRIOR (rejected for now)

If operator later overrides HOLD, the **only** admissible ceiling is:

> RBM-v0 LAB PRIOR = single-player, DualSense-desk, N≈45, population reflex-band **shape** exploration only; **not** Edge-calibrated; **not** liveness; **not** tournament-usable; `poep_enabled` stays `False`.

That ceiling is honest but **not worth the promotion risk** while Edge reflex N=0 and desk N&lt;50.

## Residual risks (for Claude verify / next loop)

1. **Category bleed:** CCO_T0 571-row Edge corpus looks “calibrated” in dashboards; any RBM or PoEP path that keys on `device_id` without requiring `policy=L6B-reflex` (or equivalent) will launder device-physics into reflex priors.
2. **Broken L6B route:** `policy=None` (166 rows, 0 nonzero-IMU) must be treated as **unwired / non-corpus** until fixed; otherwise peak=0 “in-band” rows recontaminate N counts.
3. **Cross-device transfer illusion:** desk DualSense ≠ registered Edge; even N≥50 desk would not clear Edge RBM without a stated transfer study (out of scope; do not invent one).
4. **Premature LAB PRIOR social risk:** an explicitly-scoped prior still becomes the default “model exists” signal in A2A/docs unless naming and gates hard-block Edge claims.

**P2 gate (mechanical):** RBM-v0 build authorized only when  
`registered_Edge ∧ L6B_reflex_protocol ∧ independent_clean_IMU_inband ≥ 50`  
(and CCO_T0 / `policy=None` rows are excluded by construction).

— end round-04-grok-design —
