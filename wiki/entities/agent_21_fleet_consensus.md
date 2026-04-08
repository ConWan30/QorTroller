# ENTITY: Agent #21 — FleetConsensusSnapshotAgent

[VAPI:Phase166:MEMORY.md:MEASURED]

## Overview

Agent #21, introduced in Phase 157. Produces the Proof of Fleet Consensus (PoFC)
by polling all agents every 1,800 seconds. The PoFC hash is the third composable
proof primitive after PoAC (Phase 1) and PoAd (Phase 111).

## PoFC Hash Formula [VAPI:Phase166:MEMORY.md:MEASURED]

```python
pofc_hash = SHA-256(sorted_verdicts + separation_ratio_str + ts_ns)
```

Every 1,800 seconds. Anchors the fleet consensus state cryptographically.

## Composable Proof Triple [VAPI:Phase166:MEMORY.md:MEASURED]

| Primitive | Formula | Phase | Description |
|-----------|---------|-------|-------------|
| PoAC | SHA-256(raw[:164]) | 1 | Per-cognition-cycle hardware proof |
| PoAd | SHA-256(sorted_verdicts+quorum+ts_ns) | 111 | Per-adjudication distributed vote |
| PoFC | SHA-256(sorted_verdicts+ratio+ts_ns) | 157 | Fleet-level consensus snapshot |

## WIF-012 Dual-Condition Gate [VAPI:Phase166:MEMORY.md:MEASURED]

Agent #21 enforces the dual-condition `overall_ready` gate:

```python
overall_ready = (sessions_needed == 0) AND (defensible == True)
```

Both conditions required simultaneously. `enrollment_complete` bus event only fires
when both are True. This closes WIF-012 (count-gate bypass attack).

## WIF-016 Covariance Stability [VAPI:Phase166:MEMORY.md:MEASURED]

`cov_stability_check()` determines covariance regime status:

| Status | Condition | Meaning |
|--------|-----------|---------|
| `diagonal_stable` | N/p < 2.5 | Safe diagonal covariance zone |
| `transition_warning` | N/p ∈ [2.5, 3.5] | Approaching covariance regime switch |
| `full_covariance_active` | N/p > 3.5 | Full covariance — P1/P3 collapse risk |

`COV_STABILITY_MARGIN_NP = 0.5` (Phase 157 threshold).

## Storage

- Table: `fleet_consensus_snapshot_log`
- Methods: `insert_fleet_consensus_snapshot()` + `get_fleet_consensus_snapshot()`
- Config: `fleet_consensus_enabled=True`, `fleet_consensus_snapshot_interval_s=1800`

## API

- `GET /agent/fleet-consensus-snapshot` (6 keys):
  `fleet_consensus_enabled / total_snapshots / latest_pofc_hash /
   latest_agent_count / latest_separation_ratio / timestamp`
- Tool #113: `get_fleet_consensus_snapshot`
- SDK: `FleetConsensusSnapshotResult` (6 slots) + `VAPIFleetConsensus`

## Related Pages

- [[agent_fleet_registry]]
- [[agent_fleet]]
- [[wif_012_enrollment_count_gate]]
- [[wif_016_covariance_regime]]
- [[separation_ratio]]
