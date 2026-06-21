# CCO Phase G — Measurement Runbook

Operator guide for building the per-controller-class L6B reflex corpus required before any partner claim above P-T0/P-T1/P-T3 ceilings.

**Policy:** `wiki/methodology/CCO_PHASE_G_RESEARCH_v1.md`  
**Code:** `bridge/vapi_bridge/cco_controller_class_research.py`  
**Status script:** `python scripts/cco_phase_g_measurement_status.py`

---

## What Phase G means

Phase G prevents **universal partner language** before three controller classes are empirically characterized. Each class needs its own structured L6B probe corpus (target **N≥50 per tier**) before measurement grade can advance from UNVALIDATED toward PARTIAL.

**Honesty rails:**

- `UNVALIDATED` ≠ broken — no corpus-backed claim for that class yet.
- `PARTIAL` on PREMIUM_EDGE reflects Edge-only partial measurement, not class-wide tournament readiness.
- **VALIDATED is never assigned automatically** — operator attestation only.

---

## Three research tiers

| Tier | Example profiles | Hardware needed | Partner ceiling |
|------|------------------|-----------------|-----------------|
| **MINIMAL_PAD** | `hori_fighting_commander_ps5_v1` | HORI fight stick or minimal pad | P-T0 |
| **MID_TIER** | `sony_dualsense_v1`, `scuf_reflex_pro_v1`, `xbox_elite_s2_v1` | DualSense, SCUF, Xbox Elite S2 | P-T1 |
| **PREMIUM_EDGE** | `sony_dualshock_edge_v1`, `battle_beaver_dualshock_edge_v1` | DualShock Edge (CFI-ZCP1) | P-T3 (ceiling only) |

Unknown profiles map to MINIMAL_PAD (conservative).

---

## Environment flags

| Flag | Default | Purpose |
|------|---------|---------|
| `CCO_RESEARCH_SURFACE_ENABLED` | `false` | When `true`, `/operator/player/session-status` includes `identity_grid.controller_class_research` with dynamic corpus grade |
| `CCO_PHASE_G_DEFERRED_TIERS` | `` | Comma-separated tiers without hardware (e.g. `MINIMAL_PAD`) |
| `CCO_PHASE_G_VALIDATED_TIERS` | `` | Operator attestation after FAR/FRR review (e.g. `MID_TIER,PREMIUM_EDGE`) — never auto-set |
| `L6B_ENABLED` | `false` | Production L6B — do **not** enable until operator checklist after N≥50 gate |

---

## Step-by-step capture (desk session)

1. **Stop the bridge** — dual-writer contention on pydualsense will corrupt probes.
2. Connect the target controller over USB.
3. Run desk reaction session with the correct profile tag:

```bash
# PREMIUM_EDGE (DualShock Edge — default for Edge desk work)
python scripts/l6b_desk_reaction_session.py \
  --player P1 --protocol still --count 10 \
  --cco-profile-id sony_dualshock_edge_v1

# MID_TIER example
python scripts/l6b_desk_reaction_session.py \
  --player P1 --protocol still --count 10 \
  --cco-profile-id sony_dualsense_v1

# MINIMAL_PAD example
python scripts/l6b_desk_reaction_session.py \
  --player P1 --protocol still --count 10 \
  --cco-profile-id hori_fighting_commander_ps5_v1
```

4. Repeat until `python scripts/cco_phase_g_measurement_status.py` shows `gate=REACHED` for that tier.
5. Optional: enable research surface and verify session-status:

```bash
# bridge/.env
CCO_RESEARCH_SURFACE_ENABLED=true
```

Then `GET /operator/player/session-status` (header `x-api-key`) should show `corpus_n`, `corpus_target_n`, `corpus_gate_reached`, and per-tier `phase_g_by_tier` with `measurement_grade`.

---

## Post-G closure checklist

1. Run FAR/FRR review: `python scripts/cco_phase_g_far_frr_report.py`
2. Optional replay: `python scripts/l6b_corpus_reclassify_report.py`
3. Record attestation: `audits/cco-phase-g-*-attestation-2026-06-20.md`
4. Set env:

```bash
# bridge/.env
CCO_PHASE_G_DEFERRED_TIERS=MINIMAL_PAD
CCO_PHASE_G_VALIDATED_TIERS=MID_TIER,PREMIUM_EDGE
CCO_RESEARCH_SURFACE_ENABLED=true
```

5. Phase C: mid-tier `RumbleImuVerifier` measured — verify with `pytest l9_presence/tests/test_challenge_verifier.py`
6. Restart bridge; confirm session-status shows `validated_tiers` and `grade=VALIDATED` on attested tiers.

---

## Bridge path (interval auto-probes)

When L6B bridge auto-probes are wired with CCO profile tagging (via `cco_l6b_wiring`), probes land in the same `l6b_probe_log` table. Desk sessions and bridge paths **share** the Phase G aggregation — always tag `cco_profile_id` consistently.

Check untagged rows: status script lists `untagged` profile bucket; re-tag future captures.

---

## Promotion criteria

| Transition | Requires |
|------------|----------|
| UNVALIDATED → PARTIAL | Per-tier N≥50 in `l6b_probe_log` with tagged `cco_profile_id` (automatic grade bump on session-status only) |
| PARTIAL → VALIDATED | Operator attestation + separation/defensibility gate for that class's primary challenge type |

PREMIUM_EDGE baseline grade is PARTIAL (Edge partial corpus) even below N=50 — do not interpret as tournament-grade readiness.

---

## What NOT to claim

- Do **not** claim tournament-grade presence for MINIMAL_PAD or MID_TIER tiers while grade is UNVALIDATED.
- Do **not** claim universal Edge readiness from PREMIUM_EDGE PARTIAL grade — Edge corpus only.
- Do **not** enable `L6B_ENABLED=true` from corpus count alone — run operator FAR/FRR review first.
- Do **not** tell partners VALIDATED status without explicit operator attestation.
- Untagged probes (`cco_profile_id` NULL) do not advance tier-specific gates — fix tagging, do not reinterpret.

---

## Quick checklist

- [ ] Bridge stopped before desk capture
- [ ] `--cco-profile-id` matches physical controller class
- [ ] `cco_phase_g_measurement_status.py` shows tier progress
- [ ] N≥50 per tier before partner-facing PARTIAL language
- [ ] `CCO_RESEARCH_SURFACE_ENABLED=true` only when intentionally surfacing research block
- [ ] No VALIDATED claims without operator sign-off
