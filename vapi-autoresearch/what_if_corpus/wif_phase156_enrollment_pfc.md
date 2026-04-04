# WHAT_IF Entry — Phase 156 Session (Cycle 4)

**Source**: AutoResearch cycle 4 (2026-04-04), score=1.000
**Phase**: 156 → 157 candidates

---

## WIF-012 — Enrollment Count-Gate Spoofing (Phase 157 candidate)

**W1 — Failure mode**: `enrollment_complete` fires on `sessions_needed_total==0` without requiring `defensible=True` from `separation_defensibility_log`, allowing adversarial count-gate bypass.

**Implication**: Agent #20 EnrollmentAutoGuidanceAgent triggers `enrollment_complete` bus event → TournamentActivationChainAgent when session count threshold met, regardless of whether separation ratio is defensible (>1.0 with ≥10/player). A strategic adversary captures exactly `min_n_per_player` (10) sessions of arbitrary type, satisfying the count without achieving tournament-viable separation.

**Cryptographic/Economic grounding**: `defensible=True` in `separation_defensibility_log` requires:
- All players ≥ `min_n_per_player` sessions
- `ratio > 1.0`  
- All inter-player pairs > 1.0
This is a cryptographically committed gate. Bypassing it is economically motivated (VHP mint → tournament entry → prize eligibility).

**Mitigation**: Phase 157 dual-condition enforcement:
```python
overall_ready = (sessions_needed_total == 0) AND (defensible == True)
```
Where `defensible` comes from `get_separation_defensibility_status()`.

**Status**: OPEN — Phase 157 candidate

---

## WIF-013 — Fleet Consensus Snapshot (PoFC) as Third Composable Proof (Phase 157 candidate)

**W2 — Opportunity**: Agent #21 FleetConsensusSnapshotAgent computes SHA-256(sorted(agent_verdicts) + separation_ratio + ts_ns) as "Proof of Fleet Consensus" (PoFC), creating a composable triple: PoAC + PoAd + PoFC.

**Mechanism**:
1. Agent #21 polls all 20 agent verdicts on 1h schedule
2. Sorts verdicts (canonical order), appends separation_ratio + ts_ns
3. Computes SHA-256 hash = PoFC
4. Stores in `fleet_consensus_snapshot_log` table
5. Anchors on-chain via `SeparationRatioRegistry.sol` pattern (same SHA-256 commitment format)
6. Exposes via GET /agent/fleet-consensus-snapshot
7. Downstream tournament contracts can require `PoAC AND PoAd AND PoFC` for triple-proof composability

**Why it works**: PoFC proves that the fleet as a whole agrees on the current system state. Unlike individual agent verdicts, PoFC is Byzantine-fault-tolerant (requires consensus across 20 independent agents).

**Phase candidate**: Phase 157 — FleetConsensusSnapshotAgent (agent #21), ~2h effort.

**Exclusive because**: 
- Requires VAPI's 20-agent autonomous fleet infrastructure
- Requires PoAC (physiological) + PoAd (on-chain adjudication registry, Phase 111) already deployed
- No competing gaming DePIN protocol has 20-agent fleet + PoAC + PoAd + fleet consensus hash composability

**Status**: NEW — Phase 157 candidate
