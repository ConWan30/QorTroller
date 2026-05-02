---
name: cryptographic-signing
description: Sign agent-produced content using the agent's KMS-managed secp256k1 commit-signing key per Pass 2C Section 12 amendment. Both Sentry and Guardian invoke this skill to authenticate their outputs cryptographically.
---

## Purpose

Every agent-produced artifact (draft attestation, audit entry, provenance record) is bound to the agent's identity through a cryptographic signature. This skill produces those signatures by invoking the agent's KMS-managed key (per Pass 2C Section 12 amendment: AWS KMS in `us-east-1`, `KeySpec=ECC_SECG_P256K1`, `KeyUsage=SIGN_VERIFY`).

Signatures provide cryptographic continuity across the agent's lifecycle. Without this skill's outputs, downstream attestation primitives (AGENT_COMMIT v1, PHYSICAL_DATA_ATTESTATION v1) cannot bind to the agent's identity.

## Activation phase availability

**O0 (DORMANT)**: Skill defined; KMS keys not yet provisioned (Section 6.3 implementation pending). Skill cannot execute.

**O1 (Shadow Mode)**: Active once Section 6.3 KMS keys exist. Agent signs draft attestation hashes. Signed drafts live in side-channel artifacts (NOT committed, NOT anchored on-chain). Operator inspects signature alongside draft content for review. The signing capability exists, but the signed artifact's destination is off-chain only.

**O2 (Suggestion Mode)**: Active. Agent signs commit hashes that are about to be anchored. Signatures become inputs to AGENT_COMMIT v1 and PHYSICAL_DATA_ATTESTATION v1 anchoring (which themselves require commit landing via operator-approved PRs).

## Skill scope

- Sign arbitrary 32-byte digests via `aws kms sign --key-id alias/<agent>-signing --message <digest> --message-type DIGEST --signing-algorithm ECDSA_SHA_256`.
- Return the DER-encoded ECDSA signature.
- Include public key fingerprint (first 8 bytes of `aws kms get-public-key`) in signature metadata for verification context.

## Skill boundaries

- **No key extraction.** AWS KMS Option (a) per Pass 2C Section 12.6: key material never leaves AWS KMS HSM.
- **No multi-key aggregation.** Each agent signs only with its own KMS key (`alias/vapi-anchor-sentry-signing` for Sentry; `alias/vapi-guardian-signing` for Guardian).
- **No signing of arbitrary external content.** Inputs MUST be 32-byte digests produced by VAPI's specified hash formulas (AGENT_COMMIT v1, PHYSICAL_DATA_ATTESTATION v1, etc.). No free-form message signing.
- **No signing without lane authorization.** Sentry cannot sign artifacts from Guardian's lane; Guardian cannot sign artifacts from Sentry's lane. Lane check happens upstream of this skill.

## Composing tools

- [`kms-sign`](../../tools/kms-sign.md) — boto3 wrapper invoking `kms:Sign`
- [`iotex-rpc-query`](../../tools/iotex-rpc-query.md) (optional) — verify the signature recovers to the agent's expected ECDSA address before publishing

## Verification considerations

- Signed output should round-trip: operator can take the (digest, signature, public-key) tuple and verify externally with `openssl dgst -sha256 -verify` or any standard ECDSA verifier.
- The skill includes `kms:Sign` API response metadata (request ID, timestamp) for AWS CloudTrail correlation.

## Failure modes

- **KMS unreachable**: AWS KMS API error. Skill surfaces; downstream skill MUST halt rather than substitute a fallback signature.
- **IAM permission denied**: bridge IAM role lacks `kms:Sign` on the requested key. Skill surfaces as finding; suggests IAM policy review.
- **Digest length mismatch**: input is not 32 bytes. Skill rejects with explicit error.
- **Section 6.3 not yet implemented**: KMS key alias does not resolve. Skill surfaces with explicit reference to the pending Section 6.3 work.
