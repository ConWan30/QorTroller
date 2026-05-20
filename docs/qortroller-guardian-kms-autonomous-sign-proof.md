# QorTroller — Tier-1 Proof: Autonomous Guardian KMS-HSM Signature

**Claim proven:** an attested non-human Operator steward (**Guardian**) autonomously
produced a real **AWS-KMS-HSM** ECDSA signature, independently verifiable against
its KMS public key — at **ZERO IOTX** (off-chain crypto; no blockchain transaction).

**Result: PROVEN**  ·  generated 2026-05-20T23:49:27Z

## What was executed
The live-write executor's real autonomous handler `_exec_guardian_kms_sign`
(the exact method the bridge's PATH-B autoloop calls on an accepted Guardian
`kms-sign` draft) was invoked on the current repository commit. No mock: this is
Guardian's provisioned AWS KMS HSM key (`VAPI_KMS_GUARDIAN_ALIAS`).

| Field | Value |
|---|---|
| agent | guardian (Operator Initiative steward, O3_ACTING on IoTeX testnet) |
| subject (signed) | `b0785a1669d8085b69293ce534624fc6bba30692` |
| sha256 digest (32B) | `429749db9cf7f4db8a33390ffaa33a0f9132d80a1dc23bd5eedf502b11e88cb0` |
| signature (DER ECDSA) | `30450220277c4a172159a26a7d17688cbbf75ecfb8e1f5744da0e0775b27c12d4de345c80221008e6d4ea765560006248f5d6ed547a4ebe1698b8e7fdb7c9aaf66d10d8db4ee20` |
| KMS key spec | `ECC_SECG_P256K1` (curve from pubkey: `secp256k1`) |
| executor return tx | `local:kmssign:1779320962` |
| IOTX cost | **0.0** (off-chain — no chain tx) |
| KMS-side verify | **True** |
| independent local verify (cryptography, no AWS trust) | **True** |
| audit row | operator_agent_signature_log id persisted |

## Why this is the headline claim
- **Non-human autonomy:** the signature was produced by Guardian's executor path,
  not a human invoking a CLI — the same code the autonomous loop runs.
- **Hardware-rooted:** the key lives in AWS KMS HSM (`ECC_SECG_P256K1`),
  not a software keyfile.
- **Third-party verifiable:** the signature verifies locally against Guardian's
  public key with no AWS dependency — anyone can check it.
- **Zero economic risk:** KMS signing is an AWS API call, not an IoTeX
  transaction; **0 IOTX** spent, so no token drain is possible from signing.

## Scope / honesty
This proves autonomous HSM **signing**. It does NOT anchor the signature on-chain
(that optional Tier-2 step would cost a small, budget-capped amount of *testnet*
IOTX and is a separate, explicitly-gated decision). Status: testnet, dry-run,
single-operator development phase. No real economic value at risk.
