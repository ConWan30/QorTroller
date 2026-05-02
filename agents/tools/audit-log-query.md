# audit-log-query

## Purpose

Convenience wrapper over `AuditLog.getLatestCheckpoint()` and historical checkpoint queries on the live AuditLog contract (Stream 2-deploy at `0xb7059391323eACFcb3d150a7EBFd80275a77E25F` on IoTeX testnet chain ID 4690).

## Activation phase availability

- **O0**: Tool defined; AuditLog LIVE; zero checkpoints (Tessera upstream feed deferred to P1+).
- **O1**: Active. Guardian queries checkpoint state to detect freshness issues, missing publication, or upstream feed degradation.
- **O2**: Same as O1. Checkpoint queries inform audit draft composition.

## Tool definition

| Operation | Inputs | Outputs | Activation |
|-----------|--------|---------|------------|
| `get_latest_checkpoint()` | None | Tuple (merkleRoot bytes32, treeSize uint256, timestamp uint256) | O1+ |
| `total_checkpoints()` | None | uint256 count | O1+ |
| `get_checkpoint_at(index)` | uint256 index | Tuple as above | O1+ |

## Error handling

- **Empty AuditLog**: `get_latest_checkpoint` returns sentinel-zero tuple. Tool surfaces explicitly so caller knows AuditLog is fresh-deploy / no checkpoints yet.
- **Checkpoint timestamp >3600s old**: tool includes freshness flag in result metadata for downstream skills (the AuditLog contract enforces ±3600s timestamp tolerance per Pass 2C Section 10 Note 9).
- **RPC unreachable**: surfaced via underlying `iotex-rpc-query`.

## Composability

Composed by:
- [`operational-diagnostic`](../skills/operational-diagnostic/SKILL.md) (Guardian)
- [`audit-drafting`](../skills/audit-drafting/SKILL.md) (Guardian) — referencing latest checkpoint in audit entries

## Examples

```python
root, size, ts = get_latest_checkpoint()
if root == bytes32(0):
    # P0 state: AuditLog deployed, no checkpoints; Tessera feed not live
    surface_finding("audit_log_empty_phase_o0_state")
```
