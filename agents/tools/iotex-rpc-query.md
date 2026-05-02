# iotex-rpc-query

## Purpose

Query IoTeX testnet (chain ID 4690) or mainnet (chain ID 4689) via JSON-RPC for view function calls and chain state reads. Used by both agents.

## Activation phase availability

- **O0**: Tool defined, no agent invocations.
- **O1**: Read-only `eth_call`, `eth_getBalance`, `eth_getCode`, `eth_blockNumber`, `eth_getTransactionByHash`, `eth_getLogs`. No transaction submission.
- **O2**: Same read-only operations. Write operations remain reserved (transactions are submitted by the bridge process via `chain.anchor_pda_attestation()` and similar wrappers, not by agents directly).

## Tool definition

| Operation | Inputs | Outputs | Activation |
|-----------|--------|---------|------------|
| `eth_call(to, data, block)` | Contract address; calldata hex; block tag | Return data hex | O1+ |
| `eth_getCode(address, block)` | Address; block tag | Bytecode hex | O1+ |
| `eth_blockNumber()` | None | Latest block number | O1+ |
| `eth_getLogs(filter)` | Topic + address filter | Log entries | O1+ |
| `eth_getTransactionByHash(tx_hash)` | Transaction hash | Transaction record | O1+ |

## Error handling

- **RPC unreachable**: tool returns error with attempted endpoint URL; caller decides retry/halt.
- **Reverted call**: `eth_call` returns revert reason; caller surfaces or handles per skill.
- **Invalid contract address**: returns explicit error (length check, checksum check).
- **Stale block**: tool includes block age in metadata; caller decides freshness threshold.
- **HTTP 4xx/5xx from RPC node**: tool surfaces with status code; common cause is rate limiting on public endpoints.

## Composability

Composed by:
- [`on-chain-state-querying`](../skills/on-chain-state-querying/SKILL.md) (skill)
- [`agent-registry-query`](agent-registry-query.md) (tool wrapper)
- [`audit-log-query`](audit-log-query.md) (tool wrapper)
- [`cryptographic-signing`](../skills/cryptographic-signing/SKILL.md) (optional verification step)

## Examples

```
# Verify Stream 2-deploy contract is live
eth_getCode(address="0x9548E9d17c2d40350629b1b88ff1D2c01B0414a4", block="latest")
→ "0x6080..." (2034 bytes; live AgentRegistry)

# Query AgentScope.scopeRoot for an agent
eth_call(
  to="0xc694692a69bbf1cDAda87d5bc43D345C4579FF13",
  data="0x" + selector("getScopeRoot(bytes32)") + agent_id_hex,
  block="latest"
) → "0x0000...0000"  (bytes32(0); empty Cedar bundle at Phase O0 exit)
```
