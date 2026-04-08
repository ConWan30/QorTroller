# WHAT_IF: W2-001 — Proof of Adjudication (PoAd) as Composable Primitive

[VAPI:Phase166:VAPI_WHAT_IF.md:MEASURED]

## Classification

| Field | Value |
|-------|-------|
| Layer | W2 (Novel Opportunity) |
| Status | COMPLETE (Phase 111 + Phase 112) |
| First identified | Phase 111 planning (2026-03-27) |

## Opportunity

Second on-chain primitive enabling tournament contracts to verify clean adjudication
history alongside `isFullyEligible()`. Creates composable DUAL primitive gate:
`PoAC + PoAd`.

## Mechanism

```
PoAd_hash = SHA-256(sorted(node_verdicts_json) + quorum_str + ts_ns_str)
```

- `AdjudicationRegistry.sol` stores per-cycle digests (Phase 111, LIVE)
- `hasCleanAdjudicationHistory(deviceId, lookback_days)` query
- Tournament integrators: `isFullyEligible() AND isRecorded(poadHash)` — dual gate
- `VAPIDualPrimitiveGate.sol`: `isDualEligible()` = `isFullyEligible() AND isRecorded()`

## Composable Proof Stack [VAPI:Phase166:MEMORY.md:MEASURED]

| Primitive | Hash | Contract | Phase |
|-----------|------|----------|-------|
| PoAC | SHA-256(raw[:164]) | PITLSessionRegistry | 1 (FROZEN) |
| PoAd | SHA-256(sorted_verdicts+quorum+ts_ns) | AdjudicationRegistry | 111 |
| PoFC | SHA-256(sorted_verdicts+ratio+ts_ns) | fleet_consensus_snapshot_log | 157 |
| PoHBG | SHA-256(device_id+pack('>IIIQ',...)+ts_ns) | pohbg_log | 158 |

## Exclusivity

- Presupposes ioSwarm node_verdicts anchored to PoAC chain (SHA-256(raw[:164]) + 228B format)
- No competitor has distributed per-device adjudication records
- Only valid because PoAC is already anchored on IoTeX L1

## Related Pages

- [[poac_wire_format]]
- [[agent_fleet]]
- [[zk_circuit]]
