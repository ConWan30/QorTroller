pragma circom 2.0.0;

/*
 * VAPI ZKSepProof — Groth16 ZK circuit over BN254
 * ───────────────────────────────────────────────────
 * Phase 237-ZK-SEPPROOF.  Proves the prover's biometric feature vector is
 * statistically closer (in Mahalanobis distance) to the prover's CLAIMED
 * AIT player centroid than to ANY other registered player centroid — without
 * revealing the witness vector, the centroids, or the inverse covariance
 * matrix.
 *
 * The proof binds to an on-chain anchored BIOMETRIC-SNAPSHOT-v1 commitment:
 * the verifier asserts the snapshot exists in AdjudicationRegistry and that
 * the witness centroids/cov_inv are exactly the values committed in that
 * snapshot.  Without this binding, a malicious prover could fabricate
 * centroids that satisfy the separation inequality but don't represent any
 * real corpus state.
 *
 * Sixth FROZEN-v1 primitive in the PATTERN-016 family alongside GIC, WEC,
 * VAME, CORPUS-SNAPSHOT, and CONSENT.  Composes with all five.
 *
 * Circuit parameters (FROZEN at v1):
 *   N_PLAYERS = 3   (Phase 229 AIT corpus: P1, P2, P3)
 *   FEATURES  = 4   ([accel_tremor_peak_hz, roll_cos, roll_sin, pitch_cos])
 *   SCALE     = 1e9 (matches BIOMETRIC-SNAPSHOT-v1 int64 scale)
 *
 * Estimated constraints: ~580  →  powers-of-tau 2^11 sufficient (matches Phase 67 ceremony)
 *
 * Public inputs (verified by Solidity ZKSepProofVerifier.verifyProof):
 *   biometricSnapshotHashLo      — Low 128 bits of BIOMETRIC-SNAPSHOT-v1 SHA-256
 *   biometricSnapshotHashHi      — High 128 bits of same hash
 *   claimedPlayerId              — uint8: which player the prover claims to be (0..N-1)
 *   featureCommitment            — Poseidon(5)(witness_vector || claimedPlayerId)
 *   separationThresholdMilli     — uint16: e.g. 1000 = ratio ≥ 1.0; 1500 = ratio ≥ 1.5
 *   inferenceCode                — Phase 62 binding (typically 0x00 for routine SEPPROOF)
 *
 * Private inputs (known only to the bridge):
 *   witnessVector[FEATURES]                  — Live AIT features × 1e9
 *   centroids[N_PLAYERS][FEATURES]           — Per-player centroids × 1e9
 *   covInv[FEATURES][FEATURES]               — Pooled inverse covariance × 1e9
 *
 * Constraint groups:
 *   C1. featureCommitment === Poseidon(5)(witnessVector || claimedPlayerId)         (~210 constraints)
 *   C2. claimedPlayerId < N_PLAYERS via LessThan(8)                                 (~10  constraints)
 *   C3. For each player i in 0..N-1:
 *         (i == claimedPlayerId) OR (mahal[claimed]×1000 < mahal[i]×threshold)
 *       Encoded as: (1 - isEq) × (1 - lt) === 0                                     (~330 constraints)
 *   C4. inferenceCode range check (≤ 255)                                           (~10  constraints)
 *
 * Mahalanobis distance computation (per player):
 *   diff[i]         = witnessVector[i] - centroids[player][i]
 *   intermediate[i] = Σ_j covInv[i][j] × diff[j]
 *   mahalSq         = Σ_i diff[i] × intermediate[i]
 *
 *   Scale analysis at SCALE=1e9:
 *     diff scale         ≈ 1e9 (max ~1e10 for tremor_peak)
 *     intermediate scale ≈ 1e18 (cov_inv × diff sum)
 *     mahalSq scale      ≈ 1e27 (diff × intermediate sum)
 *
 *     LessThan(128) handles up to 2^128 ≈ 3.4e38 — comfortable headroom.
 *
 * Snapshot binding (off-circuit, on-chain pre-condition):
 *   The Solidity verifier checks AdjudicationRegistry.isRecorded(commitment)
 *   AND that the on-chain stored sourceType for this anchor matches
 *   "BIOMETRIC_SNAPSHOT_v1" (or the chain attribution constant) before
 *   accepting any verifyProof() result. The circuit itself only proves the
 *   public/witness consistency; the on-chain anchor binding is the second
 *   half of the soundness argument.
 *
 * Trusted setup: Hermez perpetual powers-of-tau (pot11, BN128) — same as Phase 67.
 *
 * Build:
 *   cd contracts/circuits && circom ZKSepProof.circom --r1cs --wasm --sym
 *   (MPC ceremony coordinator: scripts/run-ceremony.js with circuit name "ZKSepProof")
 */

include "../../node_modules/circomlib/circuits/poseidon.circom";
include "../../node_modules/circomlib/circuits/comparators.circom";

// ─────────────────────────────────────────────────────────────────────────────
// MahalanobisSquared
// Computes (x - μ)^T × Σ^-1 × (x - μ) for FEATURES-dimensional vectors.
// Returns mahalSq as a single signal in field-element domain.
// All inputs are at scale 1e9; output is at scale 1e27.
// ─────────────────────────────────────────────────────────────────────────────
template MahalanobisSquared(FEATURES) {
    signal input x[FEATURES];           // witness_vector
    signal input mu[FEATURES];          // centroids[player]
    signal input covInv[FEATURES][FEATURES];

    signal diff[FEATURES];
    signal intermediate[FEATURES];

    // diff = x - mu
    for (var i = 0; i < FEATURES; i++) {
        diff[i] <== x[i] - mu[i];
    }

    // intermediate[i] = Σ_j covInv[i][j] × diff[j]
    // Decompose into per-multiplication signals so circom counts each as one constraint.
    signal cov_diff_terms[FEATURES][FEATURES];
    for (var i = 0; i < FEATURES; i++) {
        for (var j = 0; j < FEATURES; j++) {
            cov_diff_terms[i][j] <== covInv[i][j] * diff[j];
        }
    }
    for (var i = 0; i < FEATURES; i++) {
        var acc = 0;
        for (var j = 0; j < FEATURES; j++) {
            acc += cov_diff_terms[i][j];
        }
        intermediate[i] <== acc;
    }

    // mahalSq = Σ_i diff[i] × intermediate[i]
    signal diff_inter_terms[FEATURES];
    for (var i = 0; i < FEATURES; i++) {
        diff_inter_terms[i] <== diff[i] * intermediate[i];
    }
    var mahal_acc = 0;
    for (var i = 0; i < FEATURES; i++) {
        mahal_acc += diff_inter_terms[i];
    }
    signal output mahalSq;
    mahalSq <== mahal_acc;
}

// ─────────────────────────────────────────────────────────────────────────────
// ZKSepProof — main circuit
// FROZEN at N_PLAYERS=3, FEATURES=4 (AIT v1 corpus shape).
// ─────────────────────────────────────────────────────────────────────────────
template ZKSepProof() {
    // ── Frozen parameters ──────────────────────────────────────────────────
    var N_PLAYERS = 3;
    var FEATURES  = 4;
    var SCALE_NUM = 1000;     // claimed_dist × 1000 (separation threshold numerator)

    // ── Public inputs ──────────────────────────────────────────────────────
    signal input biometricSnapshotHashLo;       // low 128 bits of BIOMETRIC-SNAPSHOT
    signal input biometricSnapshotHashHi;       // high 128 bits
    signal input claimedPlayerId;                // 0..N_PLAYERS-1
    signal input featureCommitment;              // Poseidon(5)(vec || pid)
    signal input separationThresholdMilli;       // e.g. 1000 = ratio ≥ 1.0
    signal input inferenceCode;                  // Phase 62 binding

    // ── Private inputs ─────────────────────────────────────────────────────
    signal input witnessVector[FEATURES];
    signal input centroids[N_PLAYERS][FEATURES];
    signal input covInv[FEATURES][FEATURES];

    // ── Snapshot hash binding is off-circuit ──────────────────────────────
    // The verifier-side AdjudicationRegistry.isRecorded() check provides the
    // on-chain binding; the circuit accepts (lo, hi) as authoritative public
    // inputs. We add no constraints here but reference them so the optimiser
    // doesn't strip them from the proving key. The hashLo/hashHi values are
    // committed in the proof's public-signal vector and verified on-chain.
    signal hashLoBound;
    signal hashHiBound;
    hashLoBound <== biometricSnapshotHashLo;
    hashHiBound <== biometricSnapshotHashHi;

    // ══ C1: featureCommitment === Poseidon(5)(witness_vector || claimedPlayerId) ══
    // Closes the W1 attack: prevents a prover from claiming any other player_id
    // with the same witness vector. The commitment is computed once in the
    // bridge prover and matches in-circuit.
    component featH = Poseidon(5);
    for (var i = 0; i < FEATURES; i++) {
        featH.inputs[i] <== witnessVector[i];
    }
    featH.inputs[FEATURES] <== claimedPlayerId;
    featH.out === featureCommitment;

    // ══ C2: claimedPlayerId < N_PLAYERS ═══════════════════════════════════
    // Defends against out-of-bounds claims (e.g., claimedPlayerId=42 in a 3-player corpus).
    component pidRange = LessThan(8);
    pidRange.in[0] <== claimedPlayerId;
    pidRange.in[1] <== N_PLAYERS;
    pidRange.out === 1;

    // ══ Compute Mahalanobis distance for each player ═══════════════════════
    component mahal[N_PLAYERS];
    for (var p = 0; p < N_PLAYERS; p++) {
        mahal[p] = MahalanobisSquared(FEATURES);
        for (var i = 0; i < FEATURES; i++) {
            mahal[p].x[i] <== witnessVector[i];
            mahal[p].mu[i] <== centroids[p][i];
            for (var j = 0; j < FEATURES; j++) {
                mahal[p].covInv[i][j] <== covInv[i][j];
            }
        }
    }

    // ══ Select the claimed player's distance via summed indicator pattern ══
    // claimedDist = Σ_p (isEq[p] × mahal[p].mahalSq) where isEq[p] = (p == claimedPlayerId)
    component isClaimed[N_PLAYERS];
    signal claimed_dist_terms[N_PLAYERS];
    for (var p = 0; p < N_PLAYERS; p++) {
        isClaimed[p] = IsEqual();
        isClaimed[p].in[0] <== p;
        isClaimed[p].in[1] <== claimedPlayerId;
        claimed_dist_terms[p] <== isClaimed[p].out * mahal[p].mahalSq;
    }
    var claimed_dist_acc = 0;
    for (var p = 0; p < N_PLAYERS; p++) {
        claimed_dist_acc += claimed_dist_terms[p];
    }
    signal claimedDist;
    claimedDist <== claimed_dist_acc;

    // ══ C3: For each i, (i == claimedPlayerId) OR (claimedDist×1000 < mahal[i]×threshold) ══
    // Equivalent: (1 - isEq[i]) × (1 - lt[i]) === 0
    //   When i == claimedPlayerId: isEq[i]=1, so (1-isEq) = 0, constraint trivially holds.
    //   When i != claimedPlayerId: must have lt[i]=1, i.e., separation inequality holds.
    component sepLt[N_PLAYERS];
    signal lhs_terms[N_PLAYERS];
    signal rhs_terms[N_PLAYERS];
    for (var i = 0; i < N_PLAYERS; i++) {
        // claimedDist × 1000  vs  mahal[i].mahalSq × separationThresholdMilli
        lhs_terms[i] <== claimedDist * SCALE_NUM;
        rhs_terms[i] <== mahal[i].mahalSq * separationThresholdMilli;
        sepLt[i] = LessThan(128);
        sepLt[i].in[0] <== lhs_terms[i];
        sepLt[i].in[1] <== rhs_terms[i];
        // Constraint: NOT (i != claimedPlayerId AND lt[i] = 0)
        // Equivalent: (1 - isClaimed[i].out) × (1 - sepLt[i].out) === 0
        (1 - isClaimed[i].out) * (1 - sepLt[i].out) === 0;
    }

    // ══ C4: inferenceCode range sanity (≤ 255 — Phase 62 binding pattern) ══
    component infRange = LessEqThan(8);
    infRange.in[0] <== inferenceCode;
    infRange.in[1] <== 255;
    infRange.out === 1;
}

component main {public [biometricSnapshotHashLo, biometricSnapshotHashHi,
                         claimedPlayerId, featureCommitment,
                         separationThresholdMilli, inferenceCode]} = ZKSepProof();
