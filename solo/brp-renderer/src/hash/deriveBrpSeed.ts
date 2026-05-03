// Renderer-side hash-derivation helper.
//
// Decisions in force:
//   D3 (verification checkpoint): hash library is viem (not ethers). The bit-equivalence
//   of this implementation to the PDF's ethers-form is enforced by canonical-vector tests.
//
// Honesty-first invariants this file commits to:
//   H-3: hash domain is one-way for the renderer. The string "VAPI-BRP-RENDER-v1" is
//        reserved for this purpose and may not be reused.
//   H-4: Mulberry32 (consumer of this seed) is explicitly a *visual* PRNG. No
//        cryptographic claim is ever made about its output. No security-relevant decision
//        is ever made downstream of its output.
//
// PDF reference: §"Hash-derivation function" + §"Block U — Hash domain separation".
// INV-BRP-3 (draft): every keccak256 call from BRP code must pass through this helper.

import { keccak256, toBytes, concat } from "viem";

/**
 * The renderer-side hash domain string. Domain-separated from any FROZEN-v1
 * protocol primitive preimage space. Audit-readable namespace, not a secret.
 */
export const RENDER_DOMAIN = "VAPI-BRP-RENDER-v1" as const;

const DOMAIN_BYTES: Uint8Array = toBytes(RENDER_DOMAIN);

/**
 * Derive a deterministic uint32 seed for a visual PRNG from an opaque,
 * already-finalized verification output.
 *
 * Flow contract: verification → frozen output → BRP renderer → pixels.
 * No arrow goes the other direction. `frozenOutput` is treated as opaque and
 * is never inspected, decoded, or interpreted by this helper or its callers.
 *
 * The function is intentionally tiny and audit-readable.
 */
export function deriveBrpSeed(frozenOutput: Uint8Array): number {
  const digest: Uint8Array = keccak256(
    concat([DOMAIN_BYTES, frozenOutput]),
    "bytes",
  );
  // Take the first 4 bytes as a uint32 seed; Mulberry32 has 32-bit state.
  // The `>>> 0` coerces the JS bitwise result back to an unsigned 32-bit integer,
  // which is the PRNG's input contract.
  const b0 = digest[0] ?? 0;
  const b1 = digest[1] ?? 0;
  const b2 = digest[2] ?? 0;
  const b3 = digest[3] ?? 0;
  return ((b0 << 24) | (b1 << 16) | (b2 << 8) | b3) >>> 0;
}
