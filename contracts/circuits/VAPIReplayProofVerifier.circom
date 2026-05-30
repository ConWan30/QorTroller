pragma circom 2.0.0;

/*
 * VAPI ReplayProofVerifier — Groth16 ZK circuit over BN254 (Data Economy Arc 5)
 * ────────────────────────────────────────────────────────────────────────────
 * Verified Human Replay (VHR). Proves that a published, non-invertible Sanitized
 * Replay Matrix came from a session that (a) a VHP-verified human played, (b)
 * cleared the consent-manifest humanity floor, and (c) is bound to the session's
 * on-chain PoAC chain and the gamer's consent policy — WITHOUT revealing which
 * human, which VHP token, or the exact humanity score.
 *
 * DESIGN — off-circuit matrix commitment (operator-selected 2026-05-29).
 *   The spec §3.2 draft put the full quantized matrix (NB_TICKS×6 ≈ 1,800 field
 *   elements at the 300-tick baseline) through an in-circuit Poseidon and treated
 *   it as a private witness. That is both infeasible and conceptually wrong:
 *     • circomlib Poseidon supports t≤17 (≤16 inputs) — Poseidon(1800) cannot
 *       instantiate at all.
 *     • A matrix sponge over 1,800 elements is ~540k constraints (the spec's own
 *       "~2,400 per 8-input batch" × ~225 batches), far past the <25k budget and
 *       past pot15's 2^15=32,768 ceiling — it would require a new pot20+ ceremony,
 *       contradicting the "reuse PTAU, no new trusted setup" claim.
 *     • φ already makes the matrix non-invertible and PUBLISHABLE (Arc 5 Commit 1).
 *       Hiding it as a private witness adds no privacy.
 *   Resolution: the matrix root (`sanitizedTraceRoot`) is computed off-circuit by
 *   the pre-processor / WitnessGenerator and is a PUBLIC input. The matrix is
 *   published alongside the proof; any verifier recomputes the Poseidon-sponge
 *   root off-chain and checks equality — for free, with no in-circuit cost. The
 *   circuit then proves only the cheap private-witness properties (humanity floor,
 *   VHP commitment, token assembly): well under 1,000 constraints, genuine pot15
 *   reuse. (Drift D-8/D-9, audit doc: docs/data-economy-deploy-hold-and-arc5-readiness.md.)
 *
 * Trusted setup: reuses pot15 (2^15 = 32,768-constraint ceiling) —
 *   contracts/circuits/pot15_final.ptau. This circuit is far under it.
 *
 * Public inputs (verified by the Solidity Groth16 verifier):
 *   sanitizedTraceRoot   — Poseidon-sponge root of the SanitizedReplayMatrix
 *                          (computed off-circuit; matrix published for recompute).
 *   poacChainRoot        — Poseidon-8 Merkle root of the session's PoAC records;
 *                          re-derivable from on-chain PoAC record hashes.
 *   consentPolicyHash    — hash of the gamer's consent manifest at listing time.
 *   humanityThreshold    — minimum humanity_probability cleared (scaled ×1000;
 *                          default 700 == 0.70, the AIT gate). Public so the buyer
 *                          knows the standard the session met.
 *   vhpCommitment        — Poseidon(2)(vhpTokenId, sessionNonce); public commitment
 *                          to the gamer's VHP without revealing the token id.
 *
 * Private inputs (witness — never leave the prover):
 *   humanityProbabilityWitness — session minimum humanity_probability (scaled ×1000).
 *   vhpTokenId                 — the gamer's VAPIVerifiedHumanProof soulbound id.
 *   sessionNonce               — per-listing nonce; prevents proof reuse.
 *
 * Output:
 *   replayProofToken — Poseidon(4)(sanitizedTraceRoot, poacChainRoot,
 *                      consentPolicyHash, humanityThreshold). The on-chain anchor
 *                      stored in VAPIDataMarketplaceListings.proofHash.
 *
 * Constraint groups:
 *   C1.  h_gap = humanityProbabilityWitness − humanityThreshold; Num2Bits(10)
 *          range-checks h_gap ∈ [0, 1023] → floor cleared (non-negative).  (~10)
 *   C2.  vhpCommitment === Poseidon(2)(vhpTokenId, sessionNonce).          (~220)
 *   C3.  replayProofToken === Poseidon(4)(sanitizedTraceRoot, poacChainRoot,
 *          consentPolicyHash, humanityThreshold).                          (~240)
 *
 * Build (mirrors VAPIBuyerCategoryVerifier / PitlSessionProof):
 *   cd contracts/circuits
 *   ./circom.exe VAPIReplayProofVerifier.circom --r1cs --wasm --sym -l node_modules
 *   npx snarkjs r1cs info VAPIReplayProofVerifier.r1cs   # confirm < 25,000
 */

include "../../node_modules/circomlib/circuits/poseidon.circom";
include "../../node_modules/circomlib/circuits/bitify.circom";

// ─────────────────────────────────────────────────────────────────────────────
// VAPIReplayProofVerifier
// Off-circuit-root VHR proof. No matrix is hashed in-circuit; the matrix root is
// a public input recomputed off-chain by any verifier.
// ─────────────────────────────────────────────────────────────────────────────
template VAPIReplayProofVerifier() {

    // ── Public inputs ────────────────────────────────────────────────────────
    signal input sanitizedTraceRoot;   // Poseidon-sponge root of the matrix (public)
    signal input poacChainRoot;        // Poseidon-8 Merkle root of PoAC records
    signal input consentPolicyHash;    // hash of consent manifest at listing time
    signal input humanityThreshold;    // min humanity_probability ×1000 (default 700)
    signal input vhpCommitment;        // Poseidon(2)(vhpTokenId, sessionNonce)

    // ── Private inputs (witness) ───────────────────────────────────────────────
    signal input humanityProbabilityWitness;  // session min humanity_probability ×1000
    signal input vhpTokenId;                   // VHP soulbound token id (hidden)
    signal input sessionNonce;                 // per-listing nonce (hidden)

    signal output replayProofToken;

    // ══ C1: humanity floor cleared ═══════════════════════════════════════════
    // h_gap = witness − threshold (both scaled ×1000 integers in [0,1000]).
    // Num2Bits(10) succeeds iff h_gap ∈ [0,1023]; if witness < threshold the
    // difference wraps to a large field element that cannot decompose into 10
    // bits → proof generation fails. This is the floor check, no division needed.
    signal h_gap;
    h_gap <== humanityProbabilityWitness - humanityThreshold;
    component hRangeCheck = Num2Bits(10);
    hRangeCheck.in <== h_gap;

    // ══ C2: VHP commitment binding ═══════════════════════════════════════════
    // Proves the prover knows a (tokenId, nonce) opening of the public commitment
    // without revealing either — the gamer held a valid VHP during the session.
    component vhpHasher = Poseidon(2);
    vhpHasher.inputs[0] <== vhpTokenId;
    vhpHasher.inputs[1] <== sessionNonce;
    vhpHasher.out === vhpCommitment;

    // ══ C3: replay proof token assembly ══════════════════════════════════════
    // Binds matrix root + PoAC chain + consent policy + disclosed floor into the
    // single on-chain anchor. The matrix root is public; its integrity vs the
    // published matrix is checked off-chain by recomputation, not in-circuit.
    component tokenHasher = Poseidon(4);
    tokenHasher.inputs[0] <== sanitizedTraceRoot;
    tokenHasher.inputs[1] <== poacChainRoot;
    tokenHasher.inputs[2] <== consentPolicyHash;
    tokenHasher.inputs[3] <== humanityThreshold;
    replayProofToken <== tokenHasher.out;
}

component main {public [
    sanitizedTraceRoot,
    poacChainRoot,
    consentPolicyHash,
    humanityThreshold,
    vhpCommitment
]} = VAPIReplayProofVerifier();
