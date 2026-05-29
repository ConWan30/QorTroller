pragma circom 2.0.0;

/*
 * VAPI BuyerCategoryProof — Groth16 ZK circuit over BN254 (Data Economy Arc 2)
 * ────────────────────────────────────────────────────────────────────────────
 * Proves that a data buyer holds a Curator-issued credential for a claimed
 * category WITHOUT revealing which buyerDID they are. A buyer can prove
 * "I am an authorized ESPORTS buyer with an unexpired credential" while keeping
 * their identity private — the marketplace gate learns the category, not the DID.
 *
 * Constraint-3 design — OPTION (b): Poseidon-commitment membership.
 *   The framework §8 template lists an in-circuit Curator ECDSA-P256 signature
 *   check. ECDSA-in-circuit is very expensive (thousands of constraints) and
 *   duplicates trust the registry already roots on-chain. Instead, the Curator
 *   publishes a Poseidon credential commitment when issuing
 *   (credentialCommitment, a public input here), and this circuit proves the
 *   prover knows the preimage of that commitment. This mirrors QorTroller's
 *   existing anti-replay/commitment pattern (PitlSessionProof C5,
 *   TeamProof nullifiers) and the VAPIBuyerRegistry evidenceHash/event model.
 *   Operator-selected over option (a) — see Arc 2 workflow Phase 1.
 *
 * Circuit parameters:
 *   Trusted setup: reuses pot15 (2^15 = 32,768-constraint ceiling) — see
 *   contracts/circuits/pot15_final.ptau. BuyerCategoryProof is well under it.
 *
 * Public inputs (verified by the Solidity Groth16 verifier):
 *   claimedCategory      — category the buyer asserts (revealed): 1..4 FROZEN enum
 *                          (ACADEMIC=1 / GAME_DEV=2 / ESPORTS=3 / BRAND=4, INV-BUY-001)
 *   currentTimestamp     — verifier-supplied "now" (unix seconds) for expiry
 *   credentialCommitment — Curator-published Poseidon(5) credential commitment
 *   nullifierHash        — anti-replay tag; stored on-chain after use
 *
 * Private inputs (known only to the prover/buyer):
 *   buyerDID         — buyer DID reduced to a BN254 field element (the hidden
 *                      secret; the on-chain bytes32 DID is field-reduced before
 *                      proving, exactly as PitlSessionProof uses deviceIdHash)
 *   credentialNonce  — per-credential random nonce (binds commitment + nullifier)
 *   categoryId       — the actual category in the issued credential
 *   issuedAt         — issuance unix seconds
 *   expiresAt        — expiry unix seconds
 *
 * Constraint groups:
 *   C1.  categoryId === claimedCategory                                  (~1 constraint)
 *   C1b. categoryId ∈ [1, 4] (INV-BUY-001 FROZEN enum domain sanity)     (~80 constraints)
 *   C2.  currentTimestamp < expiresAt (not expired)                      (~70 constraints)
 *   C3.  credentialCommitment === Poseidon(5)(buyerDID, categoryId,
 *          issuedAt, expiresAt, credentialNonce)  [option b membership]  (~600 constraints)
 *   C4.  nullifierHash === Poseidon(2)(buyerDID, credentialNonce)        (~240 constraints)
 *
 * Build (mirrors PitlSessionProof in setup.sh):
 *   cd contracts/circuits
 *   ./circom.exe VAPIBuyerCategoryVerifier.circom --r1cs --wasm --sym -l node_modules
 */

include "../../node_modules/circomlib/circuits/poseidon.circom";
include "../../node_modules/circomlib/circuits/comparators.circom";

// ─────────────────────────────────────────────────────────────────────────────
// BuyerCategoryProof
// Main circuit. Private possession-of-credential proof for a claimed category.
// ─────────────────────────────────────────────────────────────────────────────
template BuyerCategoryProof() {

    // ── Public inputs ──────────────────────────────────────────────────────
    signal input claimedCategory;       // revealed category assertion (1..4)
    signal input currentTimestamp;      // verifier "now" (unix seconds)
    signal input credentialCommitment;  // Curator-published Poseidon(5) commitment
    signal input nullifierHash;         // anti-replay; stored on-chain after use

    // ── Private inputs ─────────────────────────────────────────────────────
    signal input buyerDID;          // field-reduced buyer DID — the hidden secret
    signal input credentialNonce;   // per-credential random nonce
    signal input categoryId;        // actual category in the issued credential
    signal input issuedAt;          // issuance unix seconds
    signal input expiresAt;         // expiry unix seconds

    signal output valid;

    // ══ C1: categoryId === claimedCategory ═══════════════════════════════════
    // The revealed category must equal the category actually in the credential.
    categoryId === claimedCategory;

    // ══ C1b: categoryId ∈ [1, 4] — INV-BUY-001 FROZEN enum domain sanity ═════
    // Mirrors the contract's on-chain categoryId >= ACADEMIC && <= BRAND guard.
    // 8-bit comparators cover [0, 255]; the 1..4 window fits.
    component catMin = GreaterEqThan(8);
    catMin.in[0] <== categoryId;
    catMin.in[1] <== 1;
    catMin.out === 1;

    component catMax = LessEqThan(8);
    catMax.in[0] <== categoryId;
    catMax.in[1] <== 4;
    catMax.out === 1;

    // ══ C2: currentTimestamp < expiresAt (credential not expired) ════════════
    // 64-bit comparator: unix-second timestamps (~2^31) fit comfortably.
    component notExpired = LessThan(64);
    notExpired.in[0] <== currentTimestamp;
    notExpired.in[1] <== expiresAt;
    notExpired.out === 1;

    // ══ C3 (option b): membership against the Curator's published commitment ══
    // Proves the prover holds the preimage of the credential the Curator
    // committed to on-chain — no in-circuit ECDSA needed. A prover who does not
    // know (buyerDID, categoryId, issuedAt, expiresAt, credentialNonce) matching
    // a published credentialCommitment cannot satisfy this constraint.
    component credH = Poseidon(5);
    credH.inputs[0] <== buyerDID;
    credH.inputs[1] <== categoryId;
    credH.inputs[2] <== issuedAt;
    credH.inputs[3] <== expiresAt;
    credH.inputs[4] <== credentialNonce;
    credH.out === credentialCommitment;

    // ══ C4: nullifierHash === Poseidon(2)(buyerDID, credentialNonce) ═════════
    // Anti-replay: one credential yields exactly one nullifier. Stored on-chain
    // after use so the same credential cannot be re-spent. Reveals neither the
    // DID nor the nonce. Matches framework §8 nullifierHash construction.
    component nullH = Poseidon(2);
    nullH.inputs[0] <== buyerDID;
    nullH.inputs[1] <== credentialNonce;
    nullH.out === nullifierHash;

    // All constraints above are assertions; if the proof generates, they hold.
    valid <== 1;
}

component main {public [claimedCategory, currentTimestamp,
                         credentialCommitment, nullifierHash]} = BuyerCategoryProof();
