/**
 * poseidon_bn254.ts -- Phase O4-W3B-POSEIDON-AS Stream I.1
 *
 * Protocol-internal AssemblyScript implementation of the Poseidon hash over
 * the BN254 scalar field, for the three arities the VAPI W3bstream applet
 * `validate_poac_record.ts` needs (per pass-3 revision of
 * wiki/phases/phase_o4_w3b_poseidon_as.md):
 *
 *   t=2  = circomlib Poseidon(1)  -- deviceIdHash      (1 input)
 *   t=3  = circomlib Poseidon(2)  -- nullifierHash     (2 inputs)
 *   t=9  = circomlib Poseidon(8)  -- featureCommitment (8 inputs)
 *
 * It MUST produce byte-identical output to circomlibjs 0.1.7 (the canonical
 * oracle). The algorithm is the naive reference permutation from
 * circomlibjs/src/poseidon_reference.js; the C/M constants are REPLICATED from
 * circomlibjs/src/poseidon_constants.json via poseidon_constants_gen.js.
 *
 * Stream I.1a (this commit): BN254 prime constant + 256-bit modular arithmetic
 *   over 4xu64 little-endian limbs (fieldAdd / fieldSub / fieldMul / pow5) +
 *   field-element load/store helpers. NO Poseidon permutation, NO arity entry
 *   points yet (those land in I.1b).
 *
 * Field element representation:
 *   StaticArray<u64> length 4, little-endian limbs (limb[0] = least significant
 *   64 bits). Every field element produced by this module is fully reduced
 *   (strictly < p).
 *
 * Modular reduction strategy: the 64x64->128 multiply has no native u128 in
 * AssemblyScript, so it is done via 32-bit limb splitting into a 512-bit
 * (8x u64) product. Reduction of the 512-bit product mod p is binary
 * long-division (shift-and-subtract): correctness over speed -- the W3bstream
 * applet runs occasionally, not in a hot loop. The BN254 prime is REPLICATED
 * from the reference, never invented.
 *
 * BN254 scalar field prime p =
 *   21888242871839275222246405745257275088548364400416034343698204186575808495617
 */

// ---------------------------------------------------------------------------
// BN254 scalar field prime -- PINNED CONSTANT
// ---------------------------------------------------------------------------
//
// 32-byte big-endian encoding of p (this is the byte order circomlibjs
// F.toObject() / fromObject() use, and the canonical applet wire encoding):
//   0x30644e72 e131a029 b85045b6 8181585d 2833e848 79b97091 43e1f593 f0000001
//
// This byte literal is PV-CI-pinnable (INV-POSEIDON-AS-002 candidate); any
// drift in the prime is a modular-reduction correctness break.
export const BN254_PRIME_BE: StaticArray<u8> = [
  0x30, 0x64, 0x4e, 0x72, 0xe1, 0x31, 0xa0, 0x29,
  0xb8, 0x50, 0x45, 0xb6, 0x81, 0x81, 0x58, 0x5d,
  0x28, 0x33, 0xe8, 0x48, 0x79, 0xb9, 0x70, 0x91,
  0x43, 0xe1, 0xf5, 0x93, 0xf0, 0x00, 0x00, 0x01,
];

// 4x u64 little-endian limb encoding of the same prime p.
//   limb[0] = 0x43e1f593f0000001  (least significant)
//   limb[1] = 0x2833e84879b97091
//   limb[2] = 0xb85045b68181585d
//   limb[3] = 0x30644e72e131a029  (most significant)
export const BN254_PRIME_LIMBS: StaticArray<u64> = [
  0x43e1f593f0000001,
  0x2833e84879b97091,
  0xb85045b68181585d,
  0x30644e72e131a029,
];

// ---------------------------------------------------------------------------
// Field element type + small constructors
// ---------------------------------------------------------------------------
//
// A field element is a StaticArray<u64> of length 4, little-endian limbs.

// Allocate a fresh zero field element.
function feZero(): StaticArray<u64> {
  const r = new StaticArray<u64>(4);
  r[0] = 0; r[1] = 0; r[2] = 0; r[3] = 0;
  return r;
}

// Allocate a field element from a small u64 value (value assumed < p, which is
// trivially true for any u64 since p > 2^253).
export function feFromU64(v: u64): StaticArray<u64> {
  const r = new StaticArray<u64>(4);
  r[0] = v; r[1] = 0; r[2] = 0; r[3] = 0;
  return r;
}

// Copy a field element.
function feCopy(a: StaticArray<u64>): StaticArray<u64> {
  const r = new StaticArray<u64>(4);
  r[0] = a[0]; r[1] = a[1]; r[2] = a[2]; r[3] = a[3];
  return r;
}

// ---------------------------------------------------------------------------
// 256-bit limb comparison
// ---------------------------------------------------------------------------
//
// Returns -1 if a < b, 0 if a == b, 1 if a > b. Operates on 4x u64 LE limbs.
function feCmp(a: StaticArray<u64>, b: StaticArray<u64>): i32 {
  for (let i = 3; i >= 0; i--) {
    const ai = a[i];
    const bi = b[i];
    if (ai < bi) return -1;
    if (ai > bi) return 1;
  }
  return 0;
}

// Compare a 4-limb value against the BN254 prime.
function feCmpPrime(a: StaticArray<u64>): i32 {
  for (let i = 3; i >= 0; i--) {
    const ai = a[i];
    const pi = BN254_PRIME_LIMBS[i];
    if (ai < pi) return -1;
    if (ai > pi) return 1;
  }
  return 0;
}

// ---------------------------------------------------------------------------
// 256-bit add / sub with carry / borrow (raw, no modular reduction)
// ---------------------------------------------------------------------------
//
// rawAdd256: r = a + b over 4 limbs; returns the carry-out (0 or 1).
function rawAdd256(a: StaticArray<u64>, b: StaticArray<u64>, r: StaticArray<u64>): u64 {
  let carry: u64 = 0;
  for (let i = 0; i < 4; i++) {
    const ai = a[i];
    const bi = b[i];
    const s1 = ai + bi;
    const c1: u64 = s1 < ai ? 1 : 0;
    const s2 = s1 + carry;
    const c2: u64 = s2 < s1 ? 1 : 0;
    r[i] = s2;
    carry = c1 + c2;
  }
  return carry;
}

// rawSub256: r = a - b over 4 limbs; returns the borrow-out (0 or 1).
function rawSub256(a: StaticArray<u64>, b: StaticArray<u64>, r: StaticArray<u64>): u64 {
  let borrow: u64 = 0;
  for (let i = 0; i < 4; i++) {
    const ai = a[i];
    const bi = b[i];
    const d1 = ai - bi;
    const b1: u64 = ai < bi ? 1 : 0;
    const d2 = d1 - borrow;
    const b2: u64 = d1 < borrow ? 1 : 0;
    r[i] = d2;
    borrow = b1 + b2;
  }
  return borrow;
}

// Subtract the BN254 prime from a 4-limb value in place; returns borrow-out.
function subPrimeInPlace(a: StaticArray<u64>): u64 {
  let borrow: u64 = 0;
  for (let i = 0; i < 4; i++) {
    const ai = a[i];
    const pi = BN254_PRIME_LIMBS[i];
    const d1 = ai - pi;
    const b1: u64 = ai < pi ? 1 : 0;
    const d2 = d1 - borrow;
    const b2: u64 = d1 < borrow ? 1 : 0;
    a[i] = d2;
    borrow = b1 + b2;
  }
  return borrow;
}

// ---------------------------------------------------------------------------
// Field add / sub (mod p)
// ---------------------------------------------------------------------------
//
// Inputs are assumed already reduced (< p). Output is reduced (< p).

// fieldAdd: r = (a + b) mod p.
export function fieldAdd(a: StaticArray<u64>, b: StaticArray<u64>): StaticArray<u64> {
  const r = feZero();
  const carry = rawAdd256(a, b, r);
  // a, b < p < 2^254, so a + b < 2^255 -- carry is at most informational, but
  // handle it for full generality. If there was a carry OR r >= p, subtract p.
  if (carry != 0 || feCmpPrime(r) >= 0) {
    subPrimeInPlace(r);
  }
  return r;
}

// fieldSub: r = (a - b) mod p.
export function fieldSub(a: StaticArray<u64>, b: StaticArray<u64>): StaticArray<u64> {
  const r = feZero();
  const borrow = rawSub256(a, b, r);
  if (borrow != 0) {
    // a < b: r currently holds (a - b) + 2^256. Add p to bring it into range.
    // Since a, b < p, the true result (a - b mod p) = (a - b) + p, and
    // (a - b) + 2^256 + p overflows back to (a - b) + p exactly.
    const tmp = feZero();
    rawAdd256(r, BN254_PRIME_LIMBS, tmp);
    r[0] = tmp[0]; r[1] = tmp[1]; r[2] = tmp[2]; r[3] = tmp[3];
  }
  return r;
}

// ---------------------------------------------------------------------------
// 256x256 -> 512 multiply via 32-bit limb splitting
// ---------------------------------------------------------------------------
//
// AssemblyScript has no native u128. We split each 4x u64 operand into 8x u32
// half-limbs and accumulate the schoolbook product into a 16x u32 result
// (== 8x u64, a 512-bit product). All partial products are u32*u32 -> u64,
// which is exact and native.
//
// Result `prod` is a StaticArray<u32> length 16, little-endian half-limbs.
function mul256to512(a: StaticArray<u64>, b: StaticArray<u64>): StaticArray<u32> {
  // Split a and b into 8 u32 half-limbs each (little-endian).
  const ah = new StaticArray<u32>(8);
  const bh = new StaticArray<u32>(8);
  for (let i = 0; i < 4; i++) {
    const av = a[i];
    const bv = b[i];
    ah[2 * i] = <u32>(av & 0xffffffff);
    ah[2 * i + 1] = <u32>(av >> 32);
    bh[2 * i] = <u32>(bv & 0xffffffff);
    bh[2 * i + 1] = <u32>(bv >> 32);
  }

  // Accumulate into a 16-limb (u64-wide accumulators to hold carries) result.
  const acc = new StaticArray<u64>(16);
  for (let i = 0; i < 16; i++) acc[i] = 0;

  for (let i = 0; i < 8; i++) {
    let carry: u64 = 0;
    const ai: u64 = <u64>ah[i];
    for (let j = 0; j < 8; j++) {
      const partial: u64 = ai * (<u64>bh[j]); // u32*u32 -> fits in u64 exactly
      const sum: u64 = acc[i + j] + (partial & 0xffffffff) + carry;
      acc[i + j] = sum & 0xffffffff;
      carry = (sum >> 32) + (partial >> 32);
    }
    // Propagate the final carry into the higher limbs.
    let k = i + 8;
    while (carry != 0 && k < 16) {
      const sum: u64 = acc[k] + carry;
      acc[k] = sum & 0xffffffff;
      carry = sum >> 32;
      k++;
    }
  }

  const prod = new StaticArray<u32>(16);
  for (let i = 0; i < 16; i++) prod[i] = <u32>(acc[i] & 0xffffffff);
  return prod;
}

// ---------------------------------------------------------------------------
// 512-bit mod p via binary long division (shift-and-subtract)
// ---------------------------------------------------------------------------
//
// Reduces a 512-bit value (16x u32 little-endian) modulo the BN254 prime.
// Classic schoolbook binary long division: walk bits from MSB to LSB,
// shifting a running remainder left by 1 and bringing in the next bit, then
// conditionally subtracting p whenever the remainder >= p.
//
// The remainder never exceeds 256 bits during the process (since after each
// conditional subtraction it is strictly < p < 2^254, and a left-shift-by-1
// of a value < 2^254 is < 2^255, well within 4x u64). Correctness over speed:
// 512 iterations, each O(1) limb ops -- entirely adequate for an applet.
function mod512(prod: StaticArray<u32>): StaticArray<u64> {
  // Running remainder as 4x u64 LE limbs.
  const rem = feZero();

  // Iterate bit positions 511 .. 0.
  for (let bit = 511; bit >= 0; bit--) {
    // 1. Shift rem left by 1 bit.
    let carry: u64 = 0;
    for (let i = 0; i < 4; i++) {
      const v = rem[i];
      rem[i] = (v << 1) | carry;
      carry = v >> 63;
    }
    // (any bit shifted out of the top would be a correctness violation -- but
    //  as argued above rem stays < 2^254 before each shift, so carry-out of
    //  limb 3 is always 0; we do not need to handle it.)

    // 2. Bring in bit `bit` of prod.
    const wordIdx = bit >> 5;        // which u32 half-limb
    const bitIdx = bit & 31;         // which bit within it
    const inBit: u64 = <u64>((prod[wordIdx] >> bitIdx) & 1);
    rem[0] = rem[0] | inBit;

    // 3. If rem >= p, subtract p.
    if (feCmpPrime(rem) >= 0) {
      subPrimeInPlace(rem);
    }
  }
  return rem;
}

// ---------------------------------------------------------------------------
// Field multiply (mod p)
// ---------------------------------------------------------------------------
//
// fieldMul: r = (a * b) mod p. Inputs assumed reduced; output reduced.
export function fieldMul(a: StaticArray<u64>, b: StaticArray<u64>): StaticArray<u64> {
  const prod = mul256to512(a, b);
  return mod512(prod);
}

// ---------------------------------------------------------------------------
// S-box: x^5 mod p
// ---------------------------------------------------------------------------
//
// pow5: r = (x^5) mod p. Computed as x2 = x*x; x4 = x2*x2; r = x4*x.
export function pow5(x: StaticArray<u64>): StaticArray<u64> {
  const x2 = fieldMul(x, x);
  const x4 = fieldMul(x2, x2);
  return fieldMul(x4, x);
}

// ---------------------------------------------------------------------------
// Field element <-> 32-byte big-endian buffer helpers
// ---------------------------------------------------------------------------
//
// circomlibjs F.toObject() / fromObject() use 32-byte big-endian encoding.
// The W3bstream applet wire format also uses 32-byte big-endian field
// elements. These helpers convert between that on-wire encoding and the
// internal 4x u64 little-endian limb representation.

// feFromBytesBE: read a 32-byte big-endian buffer at `ptr` into a field
// element. The value is reduced mod p if it is >= p (matching circomlibjs
// fromObject(), which reduces). `ptr` must point to >= 32 readable bytes.
export function feFromBytesBE(ptr: i32): StaticArray<u64> {
  const r = feZero();
  // Big-endian: byte 0 is the most significant. limb[3] is the most
  // significant limb. limb[3] holds bytes [0..7], limb[2] holds [8..15], etc.
  for (let limb = 0; limb < 4; limb++) {
    // limb `limb` corresponds to bytes [ (3-limb)*8 .. (3-limb)*8 + 7 ]
    const base = (3 - limb) * 8;
    let v: u64 = 0;
    for (let k = 0; k < 8; k++) {
      v = (v << 8) | (<u64>load<u8>(ptr + base + k));
    }
    r[limb] = v;
  }
  // Reduce if >= p (binary subtract-once is insufficient if value >= 2p, but a
  // 32-byte input is < 2^256 < 6p, so up to 5 subtractions could be needed;
  // loop until reduced).
  while (feCmpPrime(r) >= 0) {
    subPrimeInPlace(r);
  }
  return r;
}

// feToBytesBE: write a field element as a 32-byte big-endian buffer at
// `outPtr`. `outPtr` must point to >= 32 writable bytes. The element is
// assumed already reduced (< p); every element produced by this module is.
export function feToBytesBE(a: StaticArray<u64>, outPtr: i32): void {
  for (let limb = 0; limb < 4; limb++) {
    const base = (3 - limb) * 8;
    const v = a[limb];
    for (let k = 0; k < 8; k++) {
      // Most significant byte of the limb goes to the lowest byte offset.
      const shift: u64 = <u64>(56 - 8 * k);
      store<u8>(outPtr + base + k, <u8>((v >> shift) & 0xff));
    }
  }
}

// ---------------------------------------------------------------------------
// I.1a smoke-test entry points
// ---------------------------------------------------------------------------
//
// These small exported functions let the I.1a Node harness verify the
// modular-arithmetic layer on known small inputs WITHOUT a Poseidon
// permutation (which lands in I.1b). Each returns a small u64 derived from a
// field-element result so the harness can assert exact values.
//
//   smoke_fieldMul_small(x, y) = (x * y) mod p, returned as limb[0] (valid
//     while x*y < 2^64, i.e. small inputs).
//   smoke_pow5_small(x)        = (x^5) mod p, returned as limb[0] (valid while
//     x^5 < 2^64).
//   smoke_add_small(x, y)      = (x + y) mod p, returned as limb[0].
//   smoke_sub_small(x, y)      = (x - y) mod p, returned as limb[0] (valid
//     while x >= y).

export function smoke_fieldMul_small(x: u64, y: u64): u64 {
  const r = fieldMul(feFromU64(x), feFromU64(y));
  return r[0];
}

export function smoke_pow5_small(x: u64): u64 {
  const r = pow5(feFromU64(x));
  return r[0];
}

export function smoke_add_small(x: u64, y: u64): u64 {
  const r = fieldAdd(feFromU64(x), feFromU64(y));
  return r[0];
}

export function smoke_sub_small(x: u64, y: u64): u64 {
  const r = fieldSub(feFromU64(x), feFromU64(y));
  return r[0];
}

// smoke_prime_limb(i): returns limb i of the pinned BN254 prime -- lets the
// harness confirm the prime constant compiled in correctly.
export function smoke_prime_limb(i: i32): u64 {
  return BN254_PRIME_LIMBS[i];
}

// smoke_fieldSub_wrap(): computes (0 - 1) mod p and returns its limb[0]; the
// correct answer is p - 1, so limb[0] must equal 0x43e1f593f0000000.
export function smoke_fieldSub_wrap(): u64 {
  const r = fieldSub(feFromU64(0), feFromU64(1));
  return r[0];
}

// ===========================================================================
// Stream I.1b -- Poseidon(BN254) permutation + arity entry points
// ===========================================================================
//
// Algorithm (the naive reference from circomlibjs/src/poseidon_reference.js):
//
//   t = inputs.length + 1                  // internal state width
//   N_ROUNDS_F = 8                         // full rounds (constant)
//   N_ROUNDS_P = R_P per arity             // partial rounds
//   state = [0, ...inputs]                 // initState 0 prepended
//   for r in 0 .. (R_F + R_P):
//     state[i] = (state[i] + C[r*t + i]) mod p   for all i   // AddRoundConstants
//     if r < R_F/2 OR r >= R_F/2 + R_P:                      // FULL round
//       state[i] = pow5(state[i]) for all i
//     else:                                                  // PARTIAL round
//       state[0] = pow5(state[0])  // ONLY state[0]
//     state[i] = sum_j( M[i][j] * state[j] ) mod p  for all i // MDS mix
//   return state[0]
//
// The C/M constants are REPLICATED in poseidon_constants.generated.ts (emitted
// by poseidon_constants_gen.js from circomlibjs/src/poseidon_constants.json).

import {
  C_T2, M_T2,
  C_T3, M_T3,
  C_T9, M_T9,
} from "./poseidon_constants.generated";

// Full-round count is constant across all arities.
const N_ROUNDS_F: i32 = 8;

// ---------------------------------------------------------------------------
// Constants accessors -- read a field element from a flat StaticArray<u64>
// ---------------------------------------------------------------------------
//
// The generated C/M arrays store 4 little-endian limbs per field element.
// feFromFlat copies element `elemIdx` out of the flat array into a fresh
// 4-limb field element.
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
// Poseidon permutation (generic over arity)
// ---------------------------------------------------------------------------
//
// `inputs` is an array of `t-1` field elements. `C` is the flat round-constant
// array (length t*(R_F+R_P)*4 limbs). `M` is the flat MDS matrix (length
// t*t*4 limbs). `t` is the internal state width; `rP` the partial-round count.
// Returns state[0] after the full permutation.
function poseidonPermute(
  inputs: StaticArray<StaticArray<u64>>,
  t: i32,
  rP: i32,
  C: StaticArray<u64>,
  M: StaticArray<u64>
): StaticArray<u64> {
  // state = [0, ...inputs]
  const state = new StaticArray<StaticArray<u64>>(t);
  state[0] = feZero();
  for (let i = 1; i < t; i++) {
    state[i] = feCopy(inputs[i - 1]);
  }

  const totalRounds: i32 = N_ROUNDS_F + rP;
  const halfF: i32 = N_ROUNDS_F / 2; // 4

  for (let r = 0; r < totalRounds; r++) {
    // 1. AddRoundConstants: state[i] += C[r*t + i]
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
      // partial round -- S-box on state[0] only
      state[0] = pow5(state[0]);
    }

    // 3. MDS mix: newState[i] = sum_j( M[i][j] * state[j] )
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
  }

  return state[0];
}

// ---------------------------------------------------------------------------
// Arity entry points
// ---------------------------------------------------------------------------
//
// All inputs are 32-byte big-endian field elements; all outputs are a freshly
// allocated 32-byte big-endian ArrayBuffer holding the canonical reduced
// field element (matching circomlibjs F.toObject() byte order).
//
// Round-constant counts per arity (from circomlibjs/src/poseidon_reference.js
// N_ROUNDS_P, indexed [t-2]):
//   t=2  R_P=56     t=3  R_P=57     t=9  R_P=63

const R_P_T2: i32 = 56;
const R_P_T3: i32 = 57;
const R_P_T9: i32 = 63;

// Helper: read a 32-byte big-endian field element out of an ArrayBuffer.
function feFromArrayBuffer(buf: ArrayBuffer): StaticArray<u64> {
  // changetype<usize> gives the data pointer of the ArrayBuffer payload.
  const ptr = changetype<usize>(buf);
  return feFromBytesBE(<i32>ptr);
}

// Helper: allocate a 32-byte ArrayBuffer and write a field element into it
// big-endian.
function feToArrayBuffer(a: StaticArray<u64>): ArrayBuffer {
  const buf = new ArrayBuffer(32);
  const ptr = changetype<usize>(buf);
  feToBytesBE(a, <i32>ptr);
  return buf;
}

// poseidon_t2 -- circomlib Poseidon(1); 1x32B input. For deviceIdHash.
export function poseidon_t2(in0: ArrayBuffer): ArrayBuffer {
  const inputs = new StaticArray<StaticArray<u64>>(1);
  inputs[0] = feFromArrayBuffer(in0);
  const out = poseidonPermute(inputs, 2, R_P_T2, C_T2, M_T2);
  return feToArrayBuffer(out);
}

// poseidon_t3 -- circomlib Poseidon(2); 2x32B inputs. For nullifierHash.
export function poseidon_t3(in0: ArrayBuffer, in1: ArrayBuffer): ArrayBuffer {
  const inputs = new StaticArray<StaticArray<u64>>(2);
  inputs[0] = feFromArrayBuffer(in0);
  inputs[1] = feFromArrayBuffer(in1);
  const out = poseidonPermute(inputs, 3, R_P_T3, C_T3, M_T3);
  return feToArrayBuffer(out);
}

// poseidon_t9 -- circomlib Poseidon(8); 8x32B inputs packed into one 256-byte
// ArrayBuffer (input k at byte offset k*32). For featureCommitment.
export function poseidon_t9(inputs: ArrayBuffer): ArrayBuffer {
  const ptr = changetype<usize>(inputs);
  const fes = new StaticArray<StaticArray<u64>>(8);
  for (let k = 0; k < 8; k++) {
    fes[k] = feFromBytesBE(<i32>ptr + k * 32);
  }
  const out = poseidonPermute(fes, 9, R_P_T9, C_T9, M_T9);
  return feToArrayBuffer(out);
}
