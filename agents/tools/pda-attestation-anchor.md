# pda-attestation-anchor

## Purpose

Anchor PHYSICAL_DATA_ATTESTATION v1 attestations on `AgentAdjudicationRegistry` (Stream 2-deploy at `0x4767c5Ab7ed705E810903BE764fa4090B639C10A`) via the bridge chain wrapper `chain.anchor_pda_attestation()`. **Sentry-specific.**

## Activation phase availability

- **O0**: Tool defined; chain wrapper exists at `bridge/vapi_bridge/physical_data_attestation.py` (Stream 3-prep Session 2, commit `412a6f0e`). Tool not invoked.
- **O1**: Inactive. PDA v1 anchoring requires on-chain transaction; O1 produces drafts only.
- **O2**: Active. Anchoring fires after PR containing the draft attestation is merged via operator approval.

## Tool definition

| Operation | Inputs | Outputs | Activation |
|-----------|--------|---------|------------|
| `anchor(hardware_data_hash, attestation_type, ts_ns)` | 32-byte data hash; canonical attestation_type string; nanosecond timestamp | Tx hash + attestation commitment | O2 only |
| `is_recorded(commitment)` | 32-byte attestation commitment | bool | O1+ (read) |

## Error handling

- **Anti-replay revert**: commitment already recorded. Tool surfaces; usually indicates duplicate draft slipped through review.
- **`CHAIN_SUBMISSION_PAUSED=true`**: bridge kill-switch active (per Phase 237.5 Path C+). Tool returns immediately with kill-switch flag; caller MUST NOT retry.
- **Insufficient gas**: bridge wallet balance below threshold. Tool surfaces; operator action required.
- **Invalid attestation_type**: not in canonical vocabulary (CORPUS_SNAPSHOT, PoAC_CHAIN_ROOT, FLEET_COHERENCE_OBSERVATION, AUDIT_ENTRY, etc.). Tool rejects upstream.
- **Vocabulary expansion needed**: a new attestation_type requires governance event per Pass 2C Section 10 Note 3 before this tool can accept it.

## Composability

Composed by:
- [`provenance-recording`](../skills/provenance-recording/SKILL.md) (skill, Sentry, O2 only)

## Examples

```python
# Sentry anchors a CORPUS_SNAPSHOT attestation at O2 (after PR merge)
tx_hash, commitment = anchor(
    hardware_data_hash=corpus_snapshot_root,
    attestation_type="CORPUS_SNAPSHOT",
    ts_ns=time.time_ns()
)
```
