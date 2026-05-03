// Mulberry32 — Tommy Ettinger's 32-bit deterministic PRNG.
//
// Reference: https://gist.github.com/tommyettinger/46a8745332448839143505d203312c0a
// Choice rationale (PDF §"Hash-derivation function"): Mulberry32 is the appropriate
// choice here precisely because it is *not* cryptographic. This is a *visual* seed,
// and using a non-crypto PRNG for visual seeding is the documented community pattern.
// Choosing a cryptographic PRNG would falsely imply that the visual output carries
// security-relevant entropy, which is the opposite of honesty-first.
//
// Period: 2^32 ≈ 4.29 billion 32-bit values. Sufficient for visual seeding;
// inappropriate for any cryptographic use. This constraint is enforced at the
// boundary by INV-BRP-3 (draft) — keccak256 calls must pass through deriveBrpSeed,
// not produce randomness directly.

/**
 * Construct a Mulberry32 PRNG given a uint32 seed.
 *
 * Returns a function that emits a float in [0, 1) on each call. Determinism:
 * same seed → identical infinite sequence.
 *
 * @param seed Unsigned 32-bit integer. Out-of-range values are coerced via `>>> 0`.
 */
export function mulberry32(seed: number): () => number {
  let state = seed >>> 0;
  return function next(): number {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
