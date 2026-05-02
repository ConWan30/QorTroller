# ipfs-pin

## Purpose

Pin content to IPFS via Pinata (per Pass 2C Q7 confirmed). Used for DID document publishing, audit Merkle root publishing, and other content-addressable artifacts.

## Activation phase availability

- **O0**: Tool defined; Pinata account exists per Pass 2C Q7. Pinning happens during Section 6.4 agent registration (DID document pin) — operator-led.
- **O1**: Inactive for agent invocation. Pinning at O1 is operator-led during Section 6.4 setup.
- **O2**: Active for agent invocation. Agents pin audit Merkle roots, updated DID documents (post-rotation), and provenance manifest snapshots.

## Tool definition

| Operation | Inputs | Outputs | Activation |
|-----------|--------|---------|------------|
| `pin_json(content_dict, name)` | JSON-serializable dict; pin name | IPFS CID + Pinata pin metadata | O2 (agent invocation) |
| `pin_bytes(content_bytes, name)` | Raw bytes; pin name | IPFS CID + Pinata pin metadata | O2 |
| `unpin(cid)` | IPFS CID | Removal confirmation | O2 (rare; audit trail preserved) |

## Error handling

- **`PINATA_JWT` env var missing**: tool surfaces with hint to set in `bridge/.env`.
- **Rate limit**: Pinata returns 429; tool surfaces and waits per Pinata's retry-after header.
- **CID mismatch on verify**: tool re-fetches the pinned content and verifies the CID matches; mismatch surfaces as integrity error.
- **Pinata API outage**: tool surfaces; caller decides retry/halt.

## Composability

Composed by:
- [`provenance-recording`](../skills/provenance-recording/SKILL.md) at O2 (DID document updates after rotation; provenance manifest snapshots)
- [`audit-drafting`](../skills/audit-drafting/SKILL.md) at O2 (audit Merkle root pinning when audit aggregates >1 entry)

## Examples

```python
# Sentry pins a rotated DID document at O2 (after KMS key rotation per Pass 2C Note 6)
cid, pin_meta = pin_json(updated_did_document, name="vapi-anchor-sentry.did.v2.json")
# CID becomes input to AgentRegistry update via separate tool
```
