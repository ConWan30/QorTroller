# kms-sign

## Purpose

Boto3 wrapper around AWS KMS `Sign` API. Produces ECDSA secp256k1 signatures over 32-byte digests using the agent's KMS-managed signing key (per Pass 2C Section 12 amendment: AWS KMS in `us-east-1`, `KeySpec=ECC_SECG_P256K1`).

## Activation phase availability

- **O0**: Tool defined; KMS keys not yet provisioned (Section 6.3 implementation pending). Tool cannot execute until Section 6.3 completes.
- **O1**: Active for draft signing. Signs draft attestation hashes that live in side-channel artifacts. Output not committed, not anchored.
- **O2**: Active for commit signing. Signs hashes that become inputs to AGENT_COMMIT v1 / PHYSICAL_DATA_ATTESTATION v1 anchoring (after operator-approved PR merge).

## Tool definition

| Operation | Inputs | Outputs | Activation |
|-----------|--------|---------|------------|
| `sign(key_alias, digest_32b)` | KMS key alias (e.g., `alias/vapi-anchor-sentry-signing`); 32-byte SHA-256 digest | DER-encoded ECDSA signature; KMS request ID | O1+ |
| `get_public_key(key_alias)` | KMS key alias | DER-encoded SubjectPublicKeyInfo | O1+ |

## Error handling

- **`AccessDeniedException`**: bridge IAM role lacks `kms:Sign` on the requested key. Tool surfaces; suggests IAM policy review per Pass 2C Section 12.6 D3.
- **`KeyUnavailableException`**: KMS key in unusable state (deleted, disabled). Surfaces as critical — agent identity may need DID rotation per Pass 2C Section 10 Note 6.
- **`ValidationException` (digest length)**: input is not exactly 32 bytes. Tool rejects with explicit error.
- **AWS region/credential misconfiguration**: surfaces with hint to check `bridge/.env` for `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION=us-east-1`.
- **Section 6.3 not yet implemented**: KMS key alias does not resolve. Tool surfaces with explicit reference to the pending Section 6.3 implementation session.

## Composability

Composed by:
- [`cryptographic-signing`](../skills/cryptographic-signing/SKILL.md) (skill)
- Indirectly by [`provenance-recording`](../skills/provenance-recording/SKILL.md) and [`audit-drafting`](../skills/audit-drafting/SKILL.md) via the signing skill

## Examples

```python
# Sentry signs a draft PHYSICAL_DATA_ATTESTATION v1 hash at O1
digest = compute_pda_v1_hash(hardware_data_hash, agent_id, "CORPUS_SNAPSHOT", ts_ns)
signature, request_id = sign("alias/vapi-anchor-sentry-signing", digest)
# Signature held in side-channel artifact for operator review; no on-chain anchor at O1
```
