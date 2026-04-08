# WHAT_IF: W1-001 — ioSwarm Node-Pool Homogeneity

[VAPI:Phase166:VAPI_WHAT_IF.md:MEASURED]

## Classification

| Field | Value |
|-------|-------|
| Layer | W1 (Protocol Risk) |
| Status | BLOCKED — VAPISwarmOperatorGate.sol code-complete, deploy pending |
| First identified | Phase 109A (2026-03-15) |
| Phase candidate | Phase 112 |

## Failure Mode

MINT_QUORUM=0.80 trivially satisfied if all 5 ioSwarm nodes are operated by
the same entity, collapsing distributed consensus to a 1-party signature.

Soulbound VHP tokens could be minted without genuine distributed authorization.
The swarm fingerprint (SHA-256 of node_verdicts) is cryptographically valid but
economically meaningless — the distributed guarantee is voided.

This is **indistinguishable from legitimate quorum on-chain** without external
staker_address diversity verification.

## Detection

- All 5 node staker_addresses identical or controlled by same entity
- Swarm fingerprint shows self-consistency but not distributed consensus
- No way to detect from on-chain data alone without VAPISwarmOperatorGate

## Mitigation

- VAPISwarmOperatorGate.sol: enforces minimum 3 distinct staker addresses in node pool
- Stake-weight cap: 1.5× per node prevents whale capture
- `isSufficientlyDecentralized()` as 5th gate on POST /agent/mint-vhp

**Current blocke:** wallet ~0.35 IOTX < ~0.40 needed for deployment.

## Invariants Preserved

- MINT_QUORUM = 0.80 (Phase 110 FROZEN)
- BLOCK_QUORUM = 0.67 (Phase 109A FROZEN)
- ioswarm_enabled = False default (never change without live registered nodes)

## Related Pages

- [[agent_fleet]]
- [[epistemic_consensus]]
- [[poac_wire_format]]
