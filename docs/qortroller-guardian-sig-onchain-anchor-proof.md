# QorTroller — Tier-2 Proof: Guardian Signature Anchored on IoTeX

**Claim proven:** a commitment to a **Guardian AWS-KMS-HSM signature** is recorded
**on-chain on IoTeX testnet** — independently verifiable by anyone, no AWS access
required.

**Result: PROVEN** · 2026-05-20

Tier-1 proved Guardian autonomously *signs* via an AWS KMS HSM at 0 IOTX
(`docs/qortroller-guardian-kms-autonomous-sign-proof.md`). Tier-2 records a
32-byte commitment to such a signature on IoTeX so a third party can confirm —
months later — that the attestation existed on-chain at a specific block.

## The on-chain anchor (confirmed)

| Field | Value |
|---|---|
| network | IoTeX testnet (chain ID 4690) |
| contract | AdjudicationRegistry `0x44CF981f46a52ADE56476Ce894255954a7776fb4` |
| function | `recordAdjudication(bytes32 deviceIdHash, bytes32 poadHash, bool dualVeto)` |
| deviceIdHash attribution | `SHA-256("VAPI_GUARDIAN_SIG_ANCHOR_v1")` |
| **tx_hash** | `0x1e868a80bc56ff9fa8461b31414717dc564c0967a7835e46e3b1db4907e4ddc5` |
| **block** | 43820170 · status **1** · gasUsed 143115 |
| **attestation_hash (poadHash)** | `862c98387540a8b6cf5a30f3d00f4f3def9e0cf9a1b4d30a260bc80705c68c01` |
| on-chain `isRecorded(attestation_hash)` | **True** |
| Guardian key | `ECC_SECG_P256K1` (curve secp256k1), HSM-backed |
| signature verified at creation | KMS-side **True** + independent local **True** |
| wallet | `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692` |
| this-tx cost | **≈0.286 IOTX** (testnet; per-tx hard cap 0.50) |

The attestation commitment is defined as:
`attestation_hash = SHA-256( b"VAPI-GUARDIAN-SIG-ANCHOR-v1" || guardian_pubkey_der || sha256(subject) || signature_der )`
where `subject = draft://commit_hashes/<repo HEAD at signing>`.

## Verify it yourself (no AWS)
1. Query `AdjudicationRegistry.isRecorded(0x862c98387540a8b6cf5a30f3d00f4f3def9e0cf9a1b4d30a260bc80705c68c01)` at `0x44CF981f46a52ADE56476Ce894255954a7776fb4` on IoTeX testnet → returns `true`.
2. Inspect tx `0x1e868a80...` (block 43820170, status 1) on an IoTeX testnet explorer.

## Honesty / scope (read this)
- **Testnet only** — no real economic value at risk. Single bounded tx.
- **Cost transparency for the full Tier-2 attempt:** wallet 14.903826 → 14.257596 IOTX = **0.646 IOTX total**, of which **~0.36 IOTX was wasted on two out-of-gas reverts** before the gas limit was corrected. Root cause: the bridge's `record_adjudication` / `record_gate_attestation_on_chain` wrappers use static low gas (80k/100k) that hits IoTeX `status 101` (out-of-gas) for this two-SSTORE op; the proven fix (used here on the successful tx) is dynamic `estimate_gas * 1.25` ≈ 179k, exactly as `anchor_corpus_snapshot` already does. The reverts are documented rather than hidden.
- **Preimage caveat:** the successful run's exact `(digest, signature)` preimage was **not retained** (the one-shot script crashed *after* broadcast but *before* persisting the signature, due to a now-fixed missing `wait_for_transaction_receipt`). So `attestation_hash 862c98...` is a valid, on-chain, verified-at-creation commitment to a Guardian secp256k1 KMS-HSM signature, but it is **not preimage-reproducible** from saved data. A fully preimage-reproducible artifact (signature persisted to `operator_agent_signature_log` + this doc auto-generated) is available by re-running the now-fixed `scripts/guardian_sig_anchor_tier2.py` (≈0.29 IOTX).
- The kill-switch was lifted **process-scoped only** for this operator-confirmed one-shot; `bridge/.env` stays `CHAIN_SUBMISSION_PAUSED=true` and a bridge restart re-engages it. Autonomous on-chain anchoring by the executor remains a separate, un-taken tier.
