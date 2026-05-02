---
name: on-chain-state-querying
description: Read-only query of VAPI on-chain state across Phase O0 contracts (AgentRegistry, AgentScope, AuditLog, AgentSlashing, AgentAdjudicationRegistry) and supporting infrastructure (ioID, AdjudicationRegistry). Both Sentry and Guardian invoke this skill to verify on-chain truth.
---

## Purpose

Operator agents make claims that depend on on-chain state — agent registration status, scope authority, slashing pending, anchored attestations. This skill produces verified reads of that state without modifying it.

The skill exists because off-chain state can drift (DB cache, file content) but the on-chain state is the protocol's truth source. Agents anchor their reasoning in queries that the operator can independently verify.

## Activation phase availability

**O0 (DORMANT)**: Skill defined, not invoked.

**O1 (Shadow Mode)**: Active. Agent queries on-chain state via IoTeX RPC and includes query results in side-channel snapshots. Read-only.

**O2 (Suggestion Mode)**: Active. Query results inform draft PR composition (e.g., audit entry citing on-chain `AgentSlashing.totalProposals()` value at the time of drafting).

## Skill scope

- Query Phase O0 contract state via `eth_call`:
  - `AgentRegistry.getAgent(agentId)` — agent registration tuple (publicKey, scopeHash, status)
  - `AgentScope.getScopeRoot(agentId)` — operational scope hash
  - `AuditLog.getLatestCheckpoint()` — latest audit Merkle root + treeSize + timestamp
  - `AgentSlashing.totalProposals()` + `getProposal(id)` — slashing state
  - `AgentAdjudicationRegistry.getAnchorCount()` + `getAnchor(id)` — anchored attestations
- Query supporting contract state when relevant:
  - `VAPIioIDRegistry` — DID lookups
  - `AdjudicationRegistry` (Phase 111) — PoAd anchors
- Include block number, RPC endpoint, timestamp in query result snapshot for reproducibility.

## Skill boundaries

- **No on-chain writes.** No `eth_sendTransaction`. Read-only RPC calls only.
- **No transaction simulation that incurs gas estimate side effects.** Pure view function calls.
- **No private state inference.** If a query requires aggregating multiple read calls, surface the aggregation method explicitly so operator can verify.

## Composing tools

- [`iotex-rpc-query`](../../tools/iotex-rpc-query.md) — JSON-RPC client for IoTeX testnet/mainnet
- [`agent-registry-query`](../../tools/agent-registry-query.md) — convenience wrapper over `AgentRegistry.getAgent`
- [`audit-log-query`](../../tools/audit-log-query.md) — convenience wrapper over `AuditLog.getLatestCheckpoint`

## Verification considerations

- Each query result includes `blockNumber` from the RPC response so the operator can re-query at the same block for verification.
- RPC endpoint URL included in snapshot so operator knows which node was queried.
- For high-stakes claims (e.g., audit entries citing slashing state), the agent should query at least 2 block-confirmations after the relevant event to avoid reorg-window claims.

## Failure modes

- **RPC unreachable**: skill surfaces the failure; downstream skills decide whether to halt or proceed with cached state.
- **Contract ABI mismatch**: skill produces an error result; the agent surfaces this as a finding (suggests contract was upgraded without spec update).
- **Stale block number**: if RPC returns a block more than N blocks behind expected, skill surfaces a freshness warning.
