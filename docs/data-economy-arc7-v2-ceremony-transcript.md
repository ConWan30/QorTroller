# Data Economy Arc 7 — VAPIReplayProofVerifier_v2 (PoSR) Trusted Setup Ceremony

**Date:** 2026-06-25 (UTC)
**Branch at ceremony time:** `feat/l9-consistency-adversarial-harness`
**Circuit:** `contracts/circuits/VAPIReplayProofVerifier_v2.circom` (Arc 6 PoSR; additive to Arc 5 v1)
**Curve:** BN254 (alt-bn128) · **Protocol:** Groth16
**Sibling transcript:** `docs/data-economy-arc5-ceremony-transcript.md` (Arc 5 v1; procedure mirrored here)

---

## 0. Why this document

Same rationale as the Arc 5 transcript §0: a snarkjs Groth16 setup is a one-shot
MPC whose soundness rests on **≥1 contributor honestly zeroizing toxic-waste
entropy**. This document is the public, auditor-reproducible provenance record
for the v2 (PoSR recency) ceremony so a third party can replay
`snarkjs zkey verify` against the published hashes.

---

## 1. Inputs (verifiable, pre-existing)

| Artifact | Path | Origin |
|---|---|---|
| Circuit source | `contracts/circuits/VAPIReplayProofVerifier_v2.circom` | Arc 6 PoSR Commit 3; additive to Arc 5 v1 |
| R1CS | `contracts/circuits/VAPIReplayProofVerifier_v2.r1cs` | 2,771 constraints · 2,781 wires · 9 public + 5 private inputs + 1 output |
| Powers of tau | `contracts/circuits/pot15_final.ptau` | Phase 237 / Arc 5 ceremony artifact (2^15 = 32,768 ceiling); reused per spec §3.4 — 2,771 ≪ 32,768 |

**Circuit hash (snarkjs, 16 × 32-bit words):**

```
f57f53bc 53670af5 221af33d c4294162
321d56e8 7d4d352d 5aa2a079 f6063afd
6499e2cb 87b87d6d 67463049 22922044
518e92bd 37dc0bd7 01963ab4 251f7270
```

This hash MUST appear identically in every contribution and the beacon. Drift = contributions not against the same circuit.

---

## 2. Phase 1 setup (no entropy)

```
npx snarkjs groth16 setup VAPIReplayProofVerifier_v2.r1cs pot15_final.ptau \
    VAPIReplayProofVerifier_v2_0000.zkey
```

Deterministic given inputs; no toxic waste introduced.

---

## 3. Contributions

### 3.1 Contribution #1 — `claude-code-arc7v2-c1-20260625T192245Z`

| Field | Value |
|---|---|
| Contributor | Claude Code (scripted) |
| Timestamp (UTC) | `2026-06-25T19:22:45Z` |
| Entropy source | `head -c 64 /dev/urandom \| base64` (64-byte buffer) |
| Entropy disposition | Piped to snarkjs via shell var; `unset` immediately after; no disk write |

**Toxic-waste honesty claim:** the entropy var existed only in the contributing
shell process for one snarkjs invocation, then was explicitly `unset`. Best
treated as a known-class "single computer, automated" contribution.

**Contribution #1 hash (leading words):**

```
d7a665ec c7c9da4c bb67bf08 c132a9ff
69859aeb 3bbe4301 38537340 6547b32b
```

Verified clean: `snarkjs zkey verify … VAPIReplayProofVerifier_v2_0001.zkey` → `ZKey Ok!`

> **Contributor-diversity note.** This testnet ceremony used **one scripted
> contributor + beacon** (vs Arc 5's scripted-#1 + operator-interactive-#2). The
> Groth16 soundness guarantee holds with ≥1 honest contributor, so this is
> cryptographically sound for IoTeX testnet (chain ID 4690). The operator may
> add an interactive contribution #2 (re-ceremony) before any mainnet move — see §8.

---

## 4. Beacon

A public, post-contribution, unpredictable-at-contribution-time randomness
source, chained 2^10 times into the final zkey.

| Field | Value |
|---|---|
| Source | IoTeX testnet finalized block hash |
| Block number | `45008286` (`0x2aec59e`) |
| Block hash (beacon hex) | `9eb9c9bd4b04c4bfaf11540fff19e62aab8e7ab4b53f671c1d58070bae04db7f` |
| Iterations | `10` (2^10 = 1024 rounds) |
| Beacon name | `iotex-testnet-block-45008286-0x9eb9c9bd-2026-06-25` |
| Sampled at | after contribution #1 landed (block was latest−5 at ceremony time) |

**Command:**

```bash
npx snarkjs zkey beacon VAPIReplayProofVerifier_v2_0001.zkey \
    VAPIReplayProofVerifier_v2_final.zkey \
    9eb9c9bd4b04c4bfaf11540fff19e62aab8e7ab4b53f671c1d58070bae04db7f 10 \
    -n="iotex-testnet-block-45008286-0x9eb9c9bd-2026-06-25"
```

Final zkey verified: `snarkjs zkey verify … VAPIReplayProofVerifier_v2_final.zkey` → `ZKey Ok!`

**Independent beacon verification:**

```bash
curl -X POST https://babel-api.testnet.iotex.io -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_getBlockByNumber","params":["0x2aec59e",false],"id":1}'
# → result.hash == 0x9eb9c9bd4b04c4bfaf11540fff19e62aab8e7ab4b53f671c1d58070bae04db7f
```

---

## 5. Outputs

| Artifact | Path | Tracked? | Purpose |
|---|---|---|---|
| Final zkey | `bridge/vapi_bridge/replay_proof_pipeline/zk_artifacts/VAPIReplayProofVerifier_v2_final.zkey` | NO (`.zkey` gitignored) | Runtime `groth16 fullprove` input |
| Verification key | `contracts/circuits/VAPIReplayProofVerifier_v2_verification_key.json` | YES | `protocol=groth16 · curve=bn128 · nPublic=10` |
| Witness wasm | `…/zk_artifacts/VAPIReplayProofVerifier_v2_js/` | NO (gitignored) | Runtime proving |
| Solidity verifier | `contracts/contracts/Groth16VerifierVAPIReplayProof_v2.sol` | YES | On-chain inner verifier (snarkjs `Groth16Verifier` renamed → `Groth16VerifierVAPIReplayProof_v2` to disambiguate, per Arc 5 INV-VHR-CEREMONY-001 precedent) |

`nPublic=10` = 9 circuit public inputs + 1 output, matching the
`VAPIReplayProofVerifier_v2` wrapper's 10-element `publicInputs` assumption.

---

## 6. Deploy chain (post-ceremony)

1. Deploy `Groth16VerifierVAPIReplayProof_v2` → inner verifier address.
2. `VAPI_VHR_V2_GROTH16_ADDR=<inner> VAPI_TBR_ADDRESS=0x962440312a995b21d4E203bE6d93021CC22bA051 VAPI_VHR_V2_DEPLOY_CONFIRM=1 npx hardhat run scripts/deploy-vapi-replay-proof-verifier-v2.js --network iotex_testnet` → wrapper address.
3. Set `REPLAY_PROOF_VERIFIER_V2_ADDRESS` in `bridge/.env`.

Wrapper constructor asserts both addresses non-zero + `PROOF_TYPE == keccak256("VAPI-REPLAY-PROOF-v2")`.

---

## 7. Reproducibility — auditor checklist

```bash
cd contracts/circuits
npx snarkjs zkey verify VAPIReplayProofVerifier_v2.r1cs pot15_final.ptau \
    VAPIReplayProofVerifier_v2_final.zkey   # → ZKey Ok! + the §3/§4 hashes
```

---

## 8. Mainnet caveat

Contributor diversity is **1 (scripted) + beacon**. Appropriate for IoTeX
testnet under the Arc 7 v2 deploy. A mainnet promotion should re-run with
**≥3 independent human contributors, each from a different machine, each
publicly attesting entropy discipline** — same caveat Arc 5 carries.

---

## 9. Status

- Phase 1 setup: complete (§2)
- Contributions: complete, 1 scripted (§3.1)
- Beacon: applied, IoTeX-anchored block 45008286 (§4)
- Artifact production: complete (§5) — Solidity verifier compiles (`npx hardhat compile` ✓, 63 files)
- Wallet spend during ceremony: **0 IOTX** (entirely local snarkjs computation)
- On-chain deploy of inner verifier + wrapper: see §6 (scoped-kill-switch, operator-confirmed)
