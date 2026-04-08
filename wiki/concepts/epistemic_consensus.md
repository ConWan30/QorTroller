# CONCEPT: Epistemic Consensus

[VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]

## HARDENED — Phase 147

The epistemic consensus threshold was hardened in Phase 147 to close the Phase 98 W1
attack vector. The threshold is cryptographically enforced across all adjudication paths.

## Threshold Values [VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]

| Parameter | Value | Phase | Status |
|-----------|-------|-------|--------|
| W1 (BLOCK) threshold | **0.65** | Phase 147 | HARDENED (was 0.60) |
| BLOCK_QUORUM (ioSwarm MINT) | **0.67** | Phase 109A | FROZEN — fail-CLOSED |
| GENERAL_QUORUM (baseline) | **0.60** | Phase 109A | FROZEN — fail-open |
| triage_prereq_required | **True** | Phase 147 | HARDENED |

## Weight Distributions [VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]

Weight sum **must equal 1.0 exactly** — never deviate.

**Swarm disabled (3-signal):**
```
ClassJ: 0.40 | Supervisor: 0.40 | Triage: 0.20
```

**Swarm enabled (4-signal):**
```
ClassJ: 0.35 | Supervisor: 0.35 | Triage: 0.15 | IoSwarm: 0.15
```

## Phase 98 W1 — Attack Vector (CLOSED by Phase 147)

The Phase 98 W1 vulnerability: with threshold=0.60, `ClassJ(0.40) + Supervisor(0.20) = 0.60`
exactly reached the gate. An adversary could suppress triage divergence below detection
threshold → reduce to a 1-agent gate → single-validator architecture.

**Phase 147 mitigation:**
- Threshold raised to 0.65: ClassJ + Supervisor alone (0.60) no longer reaches the gate
- `triage_prereq_required=True`: triage score > 0.0 required before any verdict
- Result: HOLD verdict if triage absent, regardless of ClassJ + Supervisor sum

**Implication:** Any adjudication discussion referencing threshold=0.60 is describing
pre-Phase-147 behavior only. That vulnerability is CLOSED.

## ACIM Enforcement [VAPI:Phase166:MEMORY.md:MEASURED]

Agent #18 (AgentCalibrationIntegrityMonitor) verifies epistemic threshold every 15 minutes:
- Self-test: `epistemic_consensus_threshold >= 0.65`
- Self-test: `triage_prereq_required == True`
- Self-test: `weight_sum == 1.0`

Any self-test failure fires `calibration_integrity_failure` bus event.

## ioSwarm Quorum Architecture [VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]

```
BLOCK_QUORUM  = 0.67  # enforce threshold; tie → HOLD; hold escalation ×3
MINT_QUORUM   = 0.80  # stricter for irreversible soulbound action; fail-CLOSED
GENERAL_QUORUM= 0.60  # baseline; fail-open
```

- `ioswarm_enabled=False` default — never change without live operator nodes registered
- Tie vote → HOLD (never BLOCK on tie)
- Hold escalation: three consecutive HOLDs → escalate to operator review

## Current State

- `epistemic_triage_prereq_required = True` (Phase 147 default)
- `ioswarm_enabled = False` (awaiting live ioSwarm nodes)
- Phase 98 W1: **CLOSED**
- All weight sums: verified by ACIM (#18) every 15 minutes

## Related Pages

- [[agent_fleet]]
- [[phase_166]]
- [[poac_wire_format]]
- [[zk_circuit]]
