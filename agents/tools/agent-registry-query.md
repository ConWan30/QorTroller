# agent-registry-query

## Purpose

Convenience wrapper over `AgentRegistry.getAgent(agentId)` and related view functions on the live AgentRegistry contract (Stream 2-deploy at `0x9548E9d17c2d40350629b1b88ff1D2c01B0414a4` on IoTeX testnet chain ID 4690).

## Activation phase availability

- **O0**: Tool defined; AgentRegistry LIVE. No agents registered yet (registration is Section 6.4 work).
- **O1**: Active. Agents query their own registration tuple to verify identity, scope hash, status.
- **O2**: Same as O1. Registration query results inform draft/audit composition.

## Tool definition

| Operation | Inputs | Outputs | Activation |
|-----------|--------|---------|------------|
| `get_agent(agent_id)` | bytes32 agentId | Tuple (publicKey bytes, scopeHash bytes32, status uint8) | O1+ |
| `total_agents()` | None | uint256 count | O1+ |
| `is_registered(agent_id)` | bytes32 agentId | bool | O1+ |

## Error handling

- **Agent not registered**: `get_agent` returns zeroed tuple. Tool surfaces as "agent unregistered" finding rather than treating as valid empty registration.
- **Contract reverted**: bubble revert reason to caller.
- **RPC unreachable**: surfaced via underlying `iotex-rpc-query`.

## Composability

Composed by:
- [`on-chain-state-querying`](../skills/on-chain-state-querying/SKILL.md) (skill)
- [`audit-drafting`](../skills/audit-drafting/SKILL.md) (Guardian) — citing agent registration state in audit entries
- [`provenance-recording`](../skills/provenance-recording/SKILL.md) (Sentry) — verifying agent identity before producing PDA v1 attestation

## Examples

```python
# Sentry verifies its own registration before drafting attestation
sentry_agent_id = compute_agent_id(sentry_did_address, sentry_tba_address)
publicKey, scopeHash, status = get_agent(sentry_agent_id)
assert status == 0  # DEFINED at Phase O0 exit
```
