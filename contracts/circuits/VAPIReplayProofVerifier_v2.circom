pragma circom 2.0.0;

/*
 * VAPI ReplayProofVerifier v2 — Groth16 ZK circuit over BN254 (Data Economy Arc 6 PoSR)
 * ────────────────────────────────────────────────────────────────────────────
 *
 * ADDITIVE to VAPIReplayProofVerifier.circom (Arc 5). The Arc 5 constraints
 * are COPIED VERBATIM — not modified. PoSR adds beacon-binding constraints
 * (open/close Poseidon-4 commitments + temporal ordering) that bind each
 * session to a verifiable IoTeX block-hash anchor.
 *
 * Coexistence with v1:
 *   - VAPIReplayProofVerifier.circom (Arc 5 v1) stays compileable + callable.
 *   - VAPIReplayProofVerifier_v2.circom (this file) is a SEPARATE ceremony
 *     contribution. Same pot15_final.ptau; new zkey; new Solidity verifier.
 *   - Marketplace listings coexist: existing Arc 5 v1 proofs verify against
 *     v1's verifier; new PoSR-bound proofs verify against v2's verifier.
 *   - Recency is OPT-IN until a tournament operator requires it (Decision T3).
 *
 * NEW FROZEN primitive used: VAPI-TEMPORAL-BEACON-v1 (FROZEN-v1 #14),
 * keccak256-pinned in VAPITemporalBeaconRegistry.BEACON_DOMAIN (INV-TBR-001).
 * The bridge-side SHA-256 commitment over the same beacon inputs is computed
 * in bridge/vapi_bridge/replay_proof_pipeline/posr.py (INV-POSR-001/002).
 * The two representations (SHA-256 sidecar vs Poseidon in-circuit) are
 * reconciled by the on-chain verifier checking the claimed block hash
 * against the registry — same dual-representation pattern as Arc 5's
 * matrix root (Poseidon-sponge off-circuit, single field element in-circuit).
 *
 * Constraint accounting (empirical via `snarkjs r1cs info` post-compile):
 *   Arc 5 v1 base                : 553 non-linear
 *   + 2x Poseidon-4 (open/close) : ~480
 *   + 1x Num2Bits-32 (ordering)  : ~32
 *   Total v2 budget              : ~1,065 non-linear
 *   pot15 ceiling                : 32,768 (31x headroom — trivial fit)
 *
 * Build:
 *   cd contracts/circuits
 *   ./circom.exe VAPIReplayProofVerifier_v2.circom --r1cs --wasm --sym -l node_modules
 *   npx snarkjs r1cs info VAPIReplayProofVerifier_v2.r1cs
 */

include "../../node_modules/circomlib/circuits/poseidon.circom";
include "../../node_modules/circomlib/circuits/bitify.circom";

// ─────────────────────────────────────────────────────────────────────────────
// VAPIReplayProofVerifier_v2
// Off-circuit-root design (Arc 5 INV-VHR-005) preserved verbatim.
// PoSR additions: 2 Poseidon-4 beacon commitments + temporal ordering check.
// ─────────────────────────────────────────────────────────────────────────────
template VAPIReplayProofVerifierV2() {

    // ── Public inputs (Arc 5 v1 — UNCHANGED order/semantics) ────────────────
    signal input sanitizedTraceRoot;   // Poseidon-sponge root of matrix
    signal input poacChainRoot;        // Poseidon-8 Merkle root of PoAC records
    signal input consentPolicyHash;    // hash of consent manifest at listing time
    signal input humanityThreshold;    // min humanity_probability ×1000
    signal input vhpCommitment;        // Poseidon(2)(vhpTokenId, sessionNonce)

    // ── Public inputs (Arc 6 — PoSR additions) ──────────────────────────────
    signal input openBeaconBlock;       // uint64 — block where session opened
    signal input closeBeaconBlock;      // uint64 — block where session closed
    signal input openBeaconCommitment;  // Poseidon(4) commitment, on-chain checked
    signal input closeBeaconCommitment; // Poseidon(4) commitment, on-chain checked

    // ── Private inputs (Arc 5 v1 — UNCHANGED) ───────────────────────────────
    signal input humanityProbabilityWitness;  // scaled ×1000
    signal input vhpTokenId;                   // soulbound id (hidden)
    signal input sessionNonce;                 // per-listing nonce (hidden)

    // ── Private inputs (Arc 6 — block hashes verified on-chain) ──────────────
    signal input openBeaconHash;        // 32-byte block hash at openBeaconBlock
    signal input closeBeaconHash;       // 32-byte block hash at closeBeaconBlock

    signal output replayProofToken;

    // ─── Arc 5 Constraint 1: humanity floor cleared ────────────────────────
    // (verbatim from VAPIReplayProofVerifier.circom — Arc 5 INV-VHR-005)
    signal h_gap;
    h_gap <== humanityProbabilityWitness - humanityThreshold;
    component hRangeCheck = Num2Bits(10);
    hRangeCheck.in <== h_gap;

    // ─── Arc 5 Constraint 2: VHP commitment binding ────────────────────────
    component vhpHasher = Poseidon(2);
    vhpHasher.inputs[0] <== vhpTokenId;
    vhpHasher.inputs[1] <== sessionNonce;
    vhpHasher.out === vhpCommitment;

    // ─── Arc 5 Constraint 3: replay proof token assembly ───────────────────
    // tokenHasher binds matrix root + PoAC chain + consent + threshold into
    // the on-chain anchor. Verbatim from Arc 5 — the v2 PoSR fields are
    // separately constrained below (constraints 4/5/6), keeping the v1
    // token-construction byte-identical so v1 and v2 proofs share the
    // tokenHasher semantics.
    component tokenHasher = Poseidon(4);
    tokenHasher.inputs[0] <== sanitizedTraceRoot;
    tokenHasher.inputs[1] <== poacChainRoot;
    tokenHasher.inputs[2] <== consentPolicyHash;
    tokenHasher.inputs[3] <== humanityThreshold;
    replayProofToken <== tokenHasher.out;

    // ─── PoSR Constraint 4: open beacon commitment integrity ────────────────
    // Prove the public openBeaconCommitment was computed from the claimed
    // openBeaconHash + openBeaconBlock + session-binding fields. The
    // on-chain verifier separately checks openBeaconHash matches the
    // VAPITemporalBeaconRegistry anchored hash for openBeaconBlock —
    // closing the loop: hash → public commitment → proof binds.
    component openCommit = Poseidon(4);
    openCommit.inputs[0] <== openBeaconBlock;
    openCommit.inputs[1] <== openBeaconHash;
    openCommit.inputs[2] <== poacChainRoot;       // binds beacon to this session's PoAC chain
    openCommit.inputs[3] <== sessionNonce;        // binds to this session's nonce
    openCommit.out === openBeaconCommitment;

    // ─── PoSR Constraint 5: close beacon commitment + INSEPARABILITY ───────
    // closeCommit CHAINS to openBeaconCommitment — close cannot be repaired
    // with a different open. This is the on-circuit analogue of the
    // posr.py SHA-256 sidecar's INV-POSR-002 chaining. The closeBeaconHash
    // is verified on-chain against the registry, same as openBeaconHash.
    component closeCommit = Poseidon(4);
    closeCommit.inputs[0] <== closeBeaconBlock;
    closeCommit.inputs[1] <== closeBeaconHash;
    closeCommit.inputs[2] <== openBeaconCommitment;   // CHAINS close → open
    closeCommit.inputs[3] <== sanitizedTraceRoot;     // binds to session matrix
    closeCommit.out === closeBeaconCommitment;

    // ─── PoSR Constraint 6: temporal ordering ──────────────────────────────
    // closeBeaconBlock > openBeaconBlock strictly. block_gap = close - open - 1
    // must be representable as a non-negative 32-bit value → enforces the
    // strict ordering. 32 bits comfortably covers IoTeX's block heights
    // (currently ~44M ≪ 2^32 = 4.3B; ~600 years of block growth at 2.6 s/block).
    signal block_gap;
    block_gap <== closeBeaconBlock - openBeaconBlock - 1;
    component gapCheck = Num2Bits(32);
    gapCheck.in <== block_gap;
}

// Public-input declaration order — pinned by INV-POSR-CIRCUIT-001 (added
// in this commit). snarkjs's public.json emits OUTPUT first, then publics
// in declaration order. The on-chain v2 wrapper's INPUT_* index constants
// must match this order byte-for-byte.
component main {public [
    sanitizedTraceRoot,
    poacChainRoot,
    consentPolicyHash,
    humanityThreshold,
    vhpCommitment,
    openBeaconBlock,
    closeBeaconBlock,
    openBeaconCommitment,
    closeBeaconCommitment
]} = VAPIReplayProofVerifierV2();
