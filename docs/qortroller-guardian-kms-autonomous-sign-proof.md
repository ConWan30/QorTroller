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

---

## Live autonomous run — bridge autoloop (2026-05-20)

The proof above was reproduced by the **running bridge's own PATH-B autoloop**
(not a script): after a clean restart, the live executor picked up Guardian's
operator-accepted `kms-sign` draft #2 and signed it autonomously via the AWS KMS
HSM, then marked the draft executed. Bridge log:

```
kms_client: describe_key success agent=guardian key_id=84c42c7c-4c77-453e-9ce3-cf39164b16d0
            key_spec=ECC_SECG_P256K1 key_usage=SIGN_VERIFY key_state=Enabled
live_write_executor: Phase O-TIER1: Guardian autonomous KMS-HSM signature OK draft=2
            kms_verified=True (0 IOTX, off-chain)
live_write_executor: Phase O1-D-PATH-B: agent=guardian draft=2 action=kms-sign
            tx=local:kmssign:2 cost=0.000000 IOTX
```

- The resulting **live** signature (operator_agent_signature_log) independently
  re-verified against Guardian's KMS public key with `cryptography`: **True**
  (curve `secp256k1`), no AWS trust.
- KMS key id `84c42c7c-4c77-453e-9ce3-cf39164b16d0`, `ECC_SECG_P256K1`, HSM-backed.

**Finding + fix (recorded for honesty):** the first live run signed draft #2
**twice** because two executor instances were spawned concurrently (a v1.1
always-spawn + the v2 autoloop both active). Both signatures were valid and cost
0 IOTX, and the run self-terminated once the draft was marked executed (no
drain, no churn). This was root-fixed by de-duplicating the spawn (exactly one
executor per config) and hardened with an atomic `claim_draft_for_execution`
gate that makes draft execution **strictly-once** even if more than one executor
ever runs again.
