# CCO Phase G — Controller-Class Empirical Research Program v1

| Field | Value |
|---|---|
| Status | **Tier 3 DRAFT** — research scaffold; default-OFF surfacing |
| Date | 2026-06-20 |
| Parent | `CCO_POEP_FUSION_v4.md` §Phase G; `CCO_PHASE_A_ORACLE_CONTRACT_v1.md` |
| Code | `bridge/vapi_bridge/cco_controller_class_research.py` |
| Tests | `bridge/tests/test_cco_controller_class_research.py` |

---

## 0. Purpose

Phase G prevents **universal partner language** before three controller classes are empirically characterized. The fusion doc names the tiers; this document and module make the **measurement debt** machine-readable on session-status when `CCO_RESEARCH_SURFACE_ENABLED=true` (default **false**).

**Honesty rail:** `UNVALIDATED` ≠ broken — it means *no corpus-backed claim* for that class yet. `PARTIAL` on `PREMIUM_EDGE` reflects Edge-only L6B/PoEP partial measurement, not class-wide tournament readiness.

---

## 1. Three research tiers

| Tier | Example profiles | Partner claim ceiling | Measurement grade (2026-06-20) |
|------|------------------|----------------------|------------------------------|
| **MINIMAL_PAD** | HORI fight stick | P-T0 | UNVALIDATED |
| **MID_TIER** | DualSense, SCUF, Xbox Elite S2 | P-T1 | UNVALIDATED |
| **PREMIUM_EDGE** | DualShock Edge, Battle Beaver Edge override | P-T3 (ceiling only) | PARTIAL (Edge corpus only) |

Unknown or generic profiles map to **MINIMAL_PAD** (conservative floor).

---

## 2. Session-status block

When enabled, `identity_grid.controller_class_research`:

```jsonc
"controller_class_research": {
  "schema": "qortroller-controller-class-research-v1",
  "enabled": true,
  "grade": "PARTIAL",
  "controller_class_tier": "PREMIUM_EDGE",
  "profile_id": "sony_dualshock_edge_v1",
  "characterization_status": "PARTIAL_EDGE_ONLY",
  "partner_claim_ceiling": "P-T3",
  "measurement_gates_pending": ["..."],
  "policy_ref": "CCO_POEP_FUSION_v4_PHASE_G",
  "honesty_rail": "..."
}
```

---

## 3. Reference device (composability cross-link)

Demo device `581a836c…` is **PREMIUM_EDGE** class with **both** MFG identity (I1) and PoEP presence (`off_chain_verifiable` after F-COMPOSE-2 live scan). It is the worked example of a fully-composable Edge device — not evidence that mid-tier or minimal-pad classes are characterized.

---

## 4. Promotion criteria (future)

| Grade | Requires |
|-------|----------|
| UNVALIDATED → PARTIAL | Per-class N≥50 structured probe corpus + verifier stub replaced with measured FAR/FRR |
| PARTIAL → VALIDATED | Operator attestation via `CCO_PHASE_G_VALIDATED_TIERS` after FAR/FRR review + separation/defensibility gate for that class's primary challenge type |

No automatic promotion — operator-fired only.

---

## 5. Measurement execution

Per-tier corpus progress is aggregated from `l6b_probe_log.cco_profile_id` via:

```bash
python scripts/cco_phase_g_measurement_status.py
```

Desk capture tags probes with `--cco-profile-id` on `scripts/l6b_desk_reaction_session.py`. Full operator procedure: **`docs/cco-phase-g-measurement-runbook.md`**.

When `CCO_RESEARCH_SURFACE_ENABLED=true`, `GET /player/session-status` includes dynamic `corpus_n` / `corpus_gate_reached` on the research block (grade promotes UNVALIDATED→PARTIAL at N≥50 per tier; VALIDATED never auto-assigned).
