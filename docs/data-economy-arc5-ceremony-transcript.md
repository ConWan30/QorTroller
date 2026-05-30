# Data Economy Arc 5 — VAPIReplayProofVerifier Trusted Setup Ceremony

**Date:** 2026-05-30 (UTC)
**Branch at ceremony time:** `feat/gameplay-workflow-layer`
**Circuit commit:** `1605c91b` (Arc 5 Commit 2/5)
**Curve:** BN254 (alt-bn128)
**Protocol:** Groth16

---

## 0. Why this document

A snarkjs Groth16 setup ceremony is a one-shot multi-party computation. Its
soundness rests on **at least one contributor honestly zeroizing their
toxic-waste entropy.** This document captures the public ceremony transcript
so:

1. Any third party can reproduce-verify the contribution hashes by replaying
   `snarkjs zkey verify` against the published intermediate zkeys.
2. The Arc 5 deploy decision has an auditable provenance: which artifacts
   came from which inputs, in which order, against which beacon.
3. If a re-ceremony is ever needed (mainnet, additional contributors,
   key-compromise), this transcript pins exactly what is being superseded.

---

## 1. Inputs (verifiable, pre-existing)

| Artifact | Path | Hash / origin |
|---|---|---|
| Circuit source | `contracts/circuits/VAPIReplayProofVerifier.circom` | Arc 5 Commit 2 (`1605c91b`); 553 non-linear constraints |
| R1CS | `contracts/circuits/VAPIReplayProofVerifier.r1cs` | Output of `./circom.exe VAPIReplayProofVerifier.circom --r1cs --wasm --sym -l node_modules` |
| Powers of tau | `contracts/circuits/pot15_final.ptau` | Phase 237 ZK-SEPPROOF ceremony artifact (2^15 constraint ceiling), reused per spec §3.4 |

**Circuit hash (Poseidon, 16 × 32-bit words):**

```
b7463575 6b35fdd2 79efa824 87764933
f80829c2 920c0af2 4436b49b fa7dfb4a
32dadd0c 54dbfca9 12621027 f4fd26b7
0fbb8cbe 81681fb2 f09aa622 c335345f
```

This hash MUST appear identically in every contribution and the beacon
output below. Any drift means the contributions are not against the same
circuit.

---

## 2. Phase 1 setup (no entropy)

```
npx snarkjs groth16 setup \
    VAPIReplayProofVerifier.r1cs \
    pot15_final.ptau \
    VAPIReplayProofVerifier_0000.zkey
```

Produces the initial Phase 2 zkey from the Phase 1 PTAU. No toxic waste
introduced here — this step is deterministic given the inputs.

---

## 3. Contributions

The ceremony soundness guarantee: **if at least one contributor honestly
discards their entropy, the resulting setup is sound.** Two independent
contributors participated.

### 3.1 Contribution #1 — `claude-code-arc5-c1-20260530T033927Z`

| Field | Value |
|---|---|
| Contributor | Claude Code (scripted) |
| Timestamp (UTC) | `2026-05-30T03:39:27Z` |
| Entropy source | `head -c 64 /dev/urandom \| base64` (64-byte buffer, base64-encoded) |
| Entropy disposition | Piped to snarkjs via shell env var; `unset` immediately after; no disk write |

**Toxic-waste honesty claim:** The entropy variable existed only in the
contributing shell process for the duration of one snarkjs invocation, then
was explicitly unset. As best a scripted contributor can claim, the toxic
waste does not persist. Production-grade ceremonies typically include
human contributors at this step who can vouch for their personal entropy
discipline separately; this contribution is best treated as a known-class
"single computer, automated" contribution.

**Contribution hash:**

```
b592f700 56c4ac2c 24bd1f7c f72b5353
7cdccb7c c5454f61 33db4400 ed33e525
30541b97 73897b03 efeeb160 7c038f6f
93771f17 e7838208 60ded319 4ef1c9ec
```

**Command:**

```bash
C1_ENTROPY=$(head -c 64 /dev/urandom | base64 | tr -d '\n=') && \
echo "$C1_ENTROPY" | npx snarkjs zkey contribute \
    VAPIReplayProofVerifier_0000.zkey \
    VAPIReplayProofVerifier_0001.zkey \
    --name="claude-code-arc5-c1-20260530T033927Z" -v && \
unset C1_ENTROPY
```

Verified clean: `npx snarkjs zkey verify ... VAPIReplayProofVerifier_0001.zkey` → `ZKey Ok!`

### 3.2 Contribution #2 — `operator-arc5-c2-20260530T034320Z`

| Field | Value |
|---|---|
| Contributor | Operator (interactive) |
| Timestamp (UTC) | `2026-05-30T03:43:20Z` |
| Entropy source | Interactive bash-mash typed into snarkjs `Enter a random text. (Entropy):` prompt |
| Entropy disposition | Typed into stdin; not saved to disk by snarkjs; PowerShell session scrollback at operator's discretion |

**Toxic-waste honesty claim:** Standard snarkjs interactive contribution.
Operator-provided entropy was used by snarkjs and discarded; persistence
of the entropy beyond the session depends on the operator's terminal
scrollback hygiene. The operator vouched for their own contribution.

**Contribution hash:**

```
b310c9a1 d4938cb2 4f23257d e09e0e83
656cf61e d86ebbc4 c04e90ff 9c5f6239
b7ed9b62 4295c3cc 4954de98 feea50af
810bdb5e 2fc3c1b2 3f740956 a39937de
```

**Command (PowerShell):**

```powershell
$ts = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
npx snarkjs zkey contribute `
    VAPIReplayProofVerifier_0001.zkey `
    VAPIReplayProofVerifier_0002.zkey `
    --name="operator-arc5-c2-$ts" -v
```

Verified clean: `npx snarkjs zkey verify ... VAPIReplayProofVerifier_0002.zkey` → `ZKey Ok!` Both contributions
listed in chain.

---

## 4. Beacon

A public, post-contribution, unpredictable-at-contribution-time randomness
source is hashed and chained 2^10 times into the final zkey. The beacon
prevents either contributor from grinding their entropy against a
pre-known final state.

| Field | Value |
|---|---|
| Source | IoTeX testnet finalized block hash |
| Block number | `44188831` (`0x2a13e9f`) |
| Block hash (full) | `0x1a25681ce484b57c500eb578b142c6b8436d846f6b7fb4ebfff2869d0e79eb7b` |
| Beacon hex (32 bytes) | `1a25681ce484b57c500eb578b142c6b8436d846f6b7fb4ebfff2869d0e79eb7b` |
| Iterations | `10` (i.e. 2^10 = 1024 hash chain rounds) |
| Beacon name | `iotex-testnet-block-44188831-0x1a25681c-2026-05-30` |
| Block fetched at | `~2026-05-30T03:45Z` (after both contributions) |

**Why an IoTeX block hash:**

- Public + permanent — any third party can query the IoTeX RPC and confirm
  the hash for block `44188831` matches.
- Sampled AFTER both contributions landed — neither contributor could have
  ground their entropy to anticipate this block hash.
- Aligns with the protocol's L1 anchor — same chain Arc 5's wrapper deploys
  to (chain ID 4690).

**Command:**

```bash
BEACON_HEX="1a25681ce484b57c500eb578b142c6b8436d846f6b7fb4ebfff2869d0e79eb7b"
BEACON_NAME="iotex-testnet-block-44188831-0x1a25681c-2026-05-30"
npx snarkjs zkey beacon \
    VAPIReplayProofVerifier_0002.zkey \
    VAPIReplayProofVerifier_final.zkey \
    "$BEACON_HEX" 10 -n="$BEACON_NAME"
```

**Beacon contribution hash:**

```
2a873d0e 6e00d36a 3a2c4c15 3004411f
e1fb613d 04121888 505f22de 3f037a88
3fafe027 2addd83d 1f9dbd71 e3ae83bd
5803148b ebe7cd18 b7b790fd 08ca3583
```

Final zkey verified: `npx snarkjs zkey verify ... VAPIReplayProofVerifier_final.zkey` → `ZKey Ok!`

---

## 5. Outputs

| Artifact | Path | Tracked in git? | Purpose |
|---|---|---|---|
| Final zkey | `bridge/vapi_bridge/replay_proof_pipeline/zk_artifacts/VAPIReplayProofVerifier_final.zkey` | NO (`.zkey` gitignored) | Runtime — snarkjs `groth16 fullprove` input |
| Verification key (JSON) | `contracts/circuits/VAPIReplayProofVerifier_verification_key.json` and `zk_artifacts/` | YES (mirrors Phase 237 precedent) | Off-chain verification; auditor-reproducible |
| Witness wasm | `bridge/vapi_bridge/replay_proof_pipeline/zk_artifacts/VAPIReplayProofVerifier.wasm` | NO (`.wasm` gitignored) | Runtime — snarkjs `groth16 fullprove` input |
| Solidity verifier | `contracts/contracts/Groth16VerifierVAPIReplayProof.sol` | YES | On-chain verifier; renamed from snarkjs default `Groth16Verifier` to disambiguate from `Groth16VerifierZKSepProof` |

The `.zkey` and `.wasm` are not committed for size + provenance reasons —
they can be regenerated from this transcript and the inputs in section 1.
The Solidity verifier + verification_key.json + this transcript are the
canonical record.

---

## 6. Post-ceremony invariants

After the ceremony, **two new invariants** should land alongside the
verifier deploy:

- `INV-VHR-CEREMONY-001` — `Groth16VerifierVAPIReplayProof.sol` exists at
  `contracts/contracts/` with `contract Groth16VerifierVAPIReplayProof` as
  the entry symbol (the snarkjs default `contract Groth16Verifier` is
  renamed to disambiguate from Phase 237's `Groth16VerifierZKSepProof`).
- `INV-VHR-CEREMONY-002` — `VAPIReplayProofVerifier_verification_key.json`
  exists with `protocol == "groth16"` and `curve == "bn128"` matching the
  circuit's BN254 declaration.

These are added in the same commit that lands this transcript (separately
from the Arc 5 build arc Commits 1-5, since the ceremony happens
post-build).

---

## 7. Reproducibility — auditor checklist

Any third party can verify this ceremony with:

```bash
cd contracts/circuits
# Re-derive R1CS from Commit 1605c91b's source
./circom.exe VAPIReplayProofVerifier.circom --r1cs -l node_modules
# Confirm circuit hash matches §1
sha256sum VAPIReplayProofVerifier.r1cs

# Each contribution claim — verify against the intermediate zkeys
# (they're NOT in this repo by default; ask the operator for copies):
npx snarkjs zkey verify VAPIReplayProofVerifier.r1cs pot15_final.ptau \
    VAPIReplayProofVerifier_0001.zkey   # → ZKey Ok + contribution-1 hash
npx snarkjs zkey verify VAPIReplayProofVerifier.r1cs pot15_final.ptau \
    VAPIReplayProofVerifier_0002.zkey   # → adds contribution-2 hash
npx snarkjs zkey verify VAPIReplayProofVerifier.r1cs pot15_final.ptau \
    VAPIReplayProofVerifier_final.zkey  # → adds beacon hash

# Verify beacon source independently
curl -X POST https://babel-api.testnet.iotex.io \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_getBlockByNumber","params":["0x2a13e9f",false],"id":1}'
# → result.hash should equal 0x1a25681ce484b57c500eb578b142c6b8436d846f6b7fb4ebfff2869d0e79eb7b
```

---

## 8. Mainnet caveat

This ceremony's contributor diversity is **2 (one scripted, one
interactive)** — the same as Phase 237's order of magnitude (3
contributors) but with one scripted-contributor caveat that mainnet
practitioners may consider too narrow. For a mainnet promotion path the
ceremony should be re-run with **≥3 independent human contributors,
each from a different machine, each publicly attesting their entropy
discipline.** This artifact set is appropriate for IoTeX testnet (chain
ID 4690) under the Arc 5 deploy-hold lift; a re-ceremony decision is
left to the operator for any future mainnet move.

---

## 9. Status

- **Phase 1 setup:** complete (§2)
- **Phase 2 contributions:** complete, 2 of ≥1 required (§3.1, §3.2)
- **Beacon:** applied, IoTeX-anchored (§4)
- **Artifact production:** complete (§5)
- **Smoke tests:** Solidity compile passes (`npx hardhat compile` ✓);
  end-to-end real-proof smoke test pending the circomlibjs Poseidon helper
  (the second of the two gates documented in
  `docs/data-economy-deploy-hold-and-arc5-readiness.md` §4).
- **On-chain deploy of `Groth16VerifierVAPIReplayProof.sol`:** HELD pending
  operator GO + `VAPI_REPLAY_PROOF_DEPLOY_CONFIRM=1` (the wrapper deploy
  feeds its address into `scripts/deploy-vapi-replay-proof-verifier.js`).
- **Wallet spend during ceremony:** 0 IOTX (entirely local snarkjs
  computation).
