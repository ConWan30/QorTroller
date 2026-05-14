/**
 * poseidon_bn254_debug.ts -- Phase O4-W3B-POSEIDON-AS Stream V.2
 *
 * Per-round-state-emitting mirror of poseidon_bn254.ts, for the V.2 per-round
 * differential test. The production module returns ONLY the final state[0];
 * a final-output match (V.1) can mask a bug whose error happens to cancel by
 * the last round (an MDS transposition, a round-constant index slip, or an
 * S-box applied to the wrong lane in a partial round can all final-cancel on
 * specific inputs). V.2 closes that gap by asserting EVERY intermediate round
 * state is byte-identical to the circomlibjs reference.
 *
 * Anti-drift discipline: this file does NOT re-implement field arithmetic or
 * re-declare the C/M constants. It imports the EXACT same fieldAdd / fieldMul /
 * pow5 / feFromBytesBE / feToBytesBE from poseidon_bn254.ts and the EXACT same
 * C_Tn / M_Tn constants from poseidon_constants.generated.ts that the
 * production permutation uses. Only the permutation LOOP is re-expressed here,
 * with one
 * change: it writes the full state after each round's MDS mix into an output
 * buffer instead of discarding it. If the production loop and this debug loop
 * ever diverge in round structure, V.2's own final-round check (which must
 * agree with V.1's final output) catches it.
 *
 * Output buffer layout (big-endian 32-byte field elements, densely packed):
 *   round r, state element i  ->  byte offset (r * t + i) * 32
 * Total size = (R_F + R_P) * t * 32 bytes.
 *   t=2: 64 rounds * 2 *32 =  4096 bytes
 *   t=3: 65 rounds * 3 *32 =  6240 bytes
 *   t=9: 71 rounds * 9 *32 = 20448 bytes
 *
 * `roundStates[r]` is the state AFTER round r's MDS mix -- this matches the
 * capture point in poseidon_vector_generator.js naivePoseidon() exactly
 * (verified against generator lines 137-154).
 */

import {
  fieldAdd,
  fieldMul,
  pow5,
  feFromBytesBE,
  feToBytesBE,
} from "./poseidon_bn254";
import {
  C_T2, M_T2,
  C_T3, M_T3,
  C_T9, M_T9,
} from "./poseidon_constants.generated";

// Full-round count is constant across all arities (matches poseidon_bn254.ts).
const N_ROUNDS_F: i32 = 8;

// Partial-round counts per arity (matches poseidon_bn254.ts R_P_T* constants).
const R_P_T2: i32 = 56;
const R_P_T3: i32 = 57;
const R_P_T9: i32 = 63;

// --- trivial helpers (poseidon_bn254.ts keeps these internal/unexported) ---

function feZero(): StaticArray<u64> {
  const r = new StaticArray<u64>(4);
  r[0] = 0; r[1] = 0; r[2] = 0; r[3] = 0;
  return r;
}

function feCopy(a: StaticArray<u64>): StaticArray<u64> {
  const r = new StaticArray<u64>(4);
  r[0] = a[0]; r[1] = a[1]; r[2] = a[2]; r[3] = a[3];
  return r;
}

// Read field element `elemIdx` out of a flat 4-limbs-per-element array.
function feFromFlat(flat: StaticArray<u64>, elemIdx: i32): StaticArray<u64> {
  const base = elemIdx * 4;
  const r = new StaticArray<u64>(4);
  r[0] = flat[base];
  r[1] = flat[base + 1];
  r[2] = flat[base + 2];
  r[3] = flat[base + 3];
  return r;
}

// ---------------------------------------------------------------------------
// Debug permutation -- identical round structure to poseidon_bn254.ts
// poseidonPermute(), but writes the full state after each round's MDS mix.
// ---------------------------------------------------------------------------
function poseidonPermuteDebug(
  inputs: StaticArray<StaticArray<u64>>,
  t: i32,
  rP: i32,
  C: StaticArray<u64>,
  M: StaticArray<u64>,
  outPtr: i32
): void {
  // state = [0, ...inputs]
  const state = new StaticArray<StaticArray<u64>>(t);
  state[0] = feZero();
  for (let i = 1; i < t; i++) {
    state[i] = feCopy(inputs[i - 1]);
  }

  const totalRounds: i32 = N_ROUNDS_F + rP;
  const halfF: i32 = N_ROUNDS_F / 2; // 4

  for (let r = 0; r < totalRounds; r++) {
    // 1. AddRoundConstants
    for (let i = 0; i < t; i++) {
      const c = feFromFlat(C, r * t + i);
      state[i] = fieldAdd(state[i], c);
    }

    // 2. S-box (x^5)
    const isFullRound: bool = (r < halfF) || (r >= halfF + rP);
    if (isFullRound) {
      for (let i = 0; i < t; i++) {
        state[i] = pow5(state[i]);
      }
    } else {
      state[0] = pow5(state[0]);
    }

    // 3. MDS mix
    const newState = new StaticArray<StaticArray<u64>>(t);
    for (let i = 0; i < t; i++) {
      let acc = feZero();
      for (let j = 0; j < t; j++) {
        const m = feFromFlat(M, i * t + j);
        const term = fieldMul(m, state[j]);
        acc = fieldAdd(acc, term);
      }
      newState[i] = acc;
    }
    for (let i = 0; i < t; i++) {
      state[i] = newState[i];
    }

    // CAPTURE: write the full post-MDS state for round r into the output
    // buffer. round r, element i -> byte offset (r*t + i)*32.
    for (let i = 0; i < t; i++) {
      feToBytesBE(state[i], outPtr + (r * t + i) * 32);
    }
  }
}

// ---------------------------------------------------------------------------
// Debug arity entry points
// ---------------------------------------------------------------------------
//
// Each returns a freshly allocated ArrayBuffer of size (R_F+R_P)*t*32 holding
// every intermediate round state, big-endian 32-byte field elements, densely
// packed. The pytest layer (V.2) splits this back into round_states and
// asserts byte-identical match to the circomlibjs per-round states stored in
// poseidon_test_vectors.json.

// poseidon_t2_debug -- circomlib Poseidon(1); 1x32B input.
export function poseidon_t2_debug(in0: ArrayBuffer): ArrayBuffer {
  const inputs = new StaticArray<StaticArray<u64>>(1);
  inputs[0] = feFromBytesBE(<i32>changetype<usize>(in0));
  const totalRounds = N_ROUNDS_F + R_P_T2;
  const buf = new ArrayBuffer(totalRounds * 2 * 32);
  poseidonPermuteDebug(inputs, 2, R_P_T2, C_T2, M_T2, <i32>changetype<usize>(buf));
  return buf;
}

// poseidon_t3_debug -- circomlib Poseidon(2); 2x32B inputs.
export function poseidon_t3_debug(in0: ArrayBuffer, in1: ArrayBuffer): ArrayBuffer {
  const inputs = new StaticArray<StaticArray<u64>>(2);
  inputs[0] = feFromBytesBE(<i32>changetype<usize>(in0));
  inputs[1] = feFromBytesBE(<i32>changetype<usize>(in1));
  const totalRounds = N_ROUNDS_F + R_P_T3;
  const buf = new ArrayBuffer(totalRounds * 3 * 32);
  poseidonPermuteDebug(inputs, 3, R_P_T3, C_T3, M_T3, <i32>changetype<usize>(buf));
  return buf;
}

// poseidon_t9_debug -- circomlib Poseidon(8); 8x32B inputs in one 256B buffer.
export function poseidon_t9_debug(inputs: ArrayBuffer): ArrayBuffer {
  const ptr = changetype<usize>(inputs);
  const fes = new StaticArray<StaticArray<u64>>(8);
  for (let k = 0; k < 8; k++) {
    fes[k] = feFromBytesBE(<i32>ptr + k * 32);
  }
  const totalRounds = N_ROUNDS_F + R_P_T9;
  const buf = new ArrayBuffer(totalRounds * 9 * 32);
  poseidonPermuteDebug(fes, 9, R_P_T9, C_T9, M_T9, <i32>changetype<usize>(buf));
  return buf;
}
