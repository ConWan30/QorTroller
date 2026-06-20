# CCO T0 Presence Policy v1

**Document ID:** CCO-T0-POLICY-v1  
**Version:** 1.0  
**Date:** 2026-06-19  
**Status:** Operator decision — **CLOSES F-V3-002**  
**Parent:** [`CCO_POEP_FUSION_v4.md`](CCO_POEP_FUSION_v4.md) §5 (F-V3-002)  
**Blocks:** Phase C PoEP wiring; unblocks Phase A oracle contract (read-only)

---

## Decision

**F-V3-002 resolved: Option C — split verdict types.**

| Verdict / tier band | Engine | Corpus model | Gating today |
|---------------------|--------|--------------|--------------|
| **P-T0** (reflex-band floor) | **L6B** — `L6bReflexAnalyzer` per-session (80–280 ms involuntary accel reflex) | Per-session; **not** PoEP population band | `L6B_ENABLED=false` default; operator N≥50 hard rule still applies to **live** L6B activation |
| **P-T2 / P-T3** (rich biometric + tournament PoEP bundle) | **PoEP** — `l9_presence/` three-layer mechanism | Population liveness + device-auth; N≥50 L6B gate for `PRESENT` | `poep_enabled=false`, P4 ceremony **GATED** |
| **P-T1** | **Not separately assigned in v1** | Collapses into conservative ceiling between T0 and PoEP bundle | **[UNVALIDATED]** until per-class measurement |

### Option C semantics (normative)

1. **`REFLEX_OBSERVED`** — Telemetry-only verdict from L6B path when reflex lands in human band for **this session**. Does **not** imply tournament eligibility, `PRESENT`, or PoEP commitment. Grantable in principle on first contact with any controller that can receive stimulus + register input (subject to L6B activation policy).

2. **`PRESENT`** — PoEP bundle verdict only (`liveness_pass` ∧ `device_auth_pass` ∧ freshness). Reserved for **P-T2/P-T3** characterization path. Never issued from L6B alone.

3. **PoEP population liveness (`poep_calibration.liveness_score`)** remains the model for PoEP tiers — Option C does **not** fork PoEP P2 to per-session population bypass for `PRESENT`.

4. **CCO presence ceiling** may advertise `P-T3_candidate` for Edge-class profiles; oracle must still label characterization `UNCHARACTERIZED` for T1+ until empirical gates clear (honest ceiling, not honest claim).

---

## Rationale (operator-facing)

- **v3 universal solvent:** T0 reflex tests the human, not sensor fidelity → L6B per-session is the correct engine for the floor verdict type.
- **PoEP discipline:** Tournament-grade embodied presence stays on the PoEP stack with its existing N≥50 / P4 gates — not diluted into L6B.
- **Partner honesty:** Dashboards and APIs can show `REFLEX_OBSERVED` without implying anti-cheat certification; `PRESENT` remains scarce and gated.

---

## What this decision does not do

- Does **not** lift `L6B_ENABLED`, `poep_enabled`, or `L6_CHALLENGES_ENABLED` defaults.
- Does **not** register `QORTROLLER-POEP-v0` as FROZEN-v1.
- Does **not** implement `CapabilityOracle` (Phase A contract only — see [`CCO_PHASE_A_ORACLE_CONTRACT_v1.md`](CCO_PHASE_A_ORACLE_CONTRACT_v1.md)).
- Does **not** resolve F-V3-001 (on-chain presence tier repurposing remains **DESIGN**).

---

## Implementation gates (unchanged)

| Gate | Status |
|------|--------|
| Phase A code (`CapabilityOracle.resolve`) | **HOLD** until silicon status confirmed or demand-side pilot materializes |
| Phase C PoEP parameterization | Blocked on Phase A + characterization |
| Live `REFLEX_OBSERVED` in production | Blocked on `L6B_ENABLED` + operator activation |
| Live `PRESENT` | Blocked on PoEP P4 checklist |

---

## Document history

| Date | Change |
|------|--------|
| 2026-06-19 | Operator records Option C; closes F-V3-002 |
