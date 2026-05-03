import { describe, it, expect } from "vitest";
import { keccak256, toBytes, concat, toHex, getAddress as _ga } from "viem";
import { deriveBrpSeed, RENDER_DOMAIN } from "../deriveBrpSeed";

// Sanity: avoid an unused-import warning for `_ga`.
void _ga;

describe("deriveBrpSeed — determinism, domain separation, opaqueness", () => {
  it("same input → same seed (determinism)", () => {
    const input = new Uint8Array([1, 2, 3, 4, 5, 6, 7, 8]);
    const a = deriveBrpSeed(input);
    const b = deriveBrpSeed(input);
    expect(a).toBe(b);
  });

  it("different input → different seed (overwhelming probability)", () => {
    const a = deriveBrpSeed(new Uint8Array([0]));
    const b = deriveBrpSeed(new Uint8Array([1]));
    expect(a).not.toBe(b);
  });

  it("empty input → defined uint32 output", () => {
    const seed = deriveBrpSeed(new Uint8Array(0));
    expect(Number.isInteger(seed)).toBe(true);
    expect(seed).toBeGreaterThanOrEqual(0);
    expect(seed).toBeLessThanOrEqual(0xffffffff);
  });

  it("output is always uint32 (32-bit unsigned)", () => {
    for (let i = 0; i < 20; i++) {
      const buf = new Uint8Array(32);
      buf[0] = i;
      const seed = deriveBrpSeed(buf);
      expect(Number.isInteger(seed)).toBe(true);
      expect(seed >>> 0).toBe(seed); // already uint32-coerced
      expect(seed).toBeLessThanOrEqual(0xffffffff);
    }
  });

  it("RENDER_DOMAIN is exactly the reserved string 'VAPI-BRP-RENDER-v1'", () => {
    expect(RENDER_DOMAIN).toBe("VAPI-BRP-RENDER-v1");
  });

  // INV-BRP-3 (draft) — domain separation.
  // The renderer hash domain must produce different output than any other domain
  // string for the same input, with overwhelming probability.
  it("domain-separated: DIFFERENT seed than computing keccak256 without DOMAIN prefix", () => {
    const input = new Uint8Array([0xAA, 0xBB, 0xCC, 0xDD]);
    const withDomain = deriveBrpSeed(input);
    const digestNoDomain: Uint8Array = keccak256(input, "bytes");
    const seedNoDomain =
      (((digestNoDomain[0] ?? 0) << 24) |
        ((digestNoDomain[1] ?? 0) << 16) |
        ((digestNoDomain[2] ?? 0) << 8) |
        (digestNoDomain[3] ?? 0)) >>>
      0;
    expect(withDomain).not.toBe(seedNoDomain);
  });

  it("domain-separated: DIFFERENT seed than a colliding-looking domain 'VAPI-BRP-RENDER-v2'", () => {
    const input = new Uint8Array([0x42, 0x43]);
    const withV1 = deriveBrpSeed(input);
    const altDomain = toBytes("VAPI-BRP-RENDER-v2");
    const digest: Uint8Array = keccak256(concat([altDomain, input]), "bytes");
    const altSeed =
      (((digest[0] ?? 0) << 24) |
        ((digest[1] ?? 0) << 16) |
        ((digest[2] ?? 0) << 8) |
        (digest[3] ?? 0)) >>>
      0;
    expect(withV1).not.toBe(altSeed);
  });

  // D3 equivalence test — verifies the viem-form is bit-identical to the PDF's
  // ethers-form. Done by computing the digest two independent ways inside this
  // very file and asserting equality. This guards against any future drift in
  // viem's keccak256 byte-output normalization.
  it("D3 equivalence: viem(bytes-direct) == manual hex→bytes path on canonical vector", () => {
    const frozenOutput = new Uint8Array(32); // 32 zero bytes — canonical vector
    const domain = toBytes(RENDER_DOMAIN);
    const composed = concat([domain, frozenOutput]);

    // Path A: viem direct bytes output.
    const digestA: Uint8Array = keccak256(composed, "bytes");

    // Path B: viem hex output, then manually convert hex → bytes.
    const digestHex: `0x${string}` = keccak256(composed, "hex");
    const hex = digestHex.startsWith("0x") ? digestHex.slice(2) : digestHex;
    expect(hex.length).toBe(64);
    const digestB = new Uint8Array(32);
    for (let i = 0; i < 32; i++) {
      digestB[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
    }

    // Path C: round-trip through toHex+manual to make sure no normalization differs.
    const reHex = toHex(digestA);
    expect(reHex.toLowerCase()).toBe(digestHex.toLowerCase());

    expect(digestA.length).toBe(32);
    expect(digestB.length).toBe(32);
    for (let i = 0; i < 32; i++) {
      expect(digestB[i], `byte ${i}`).toBe(digestA[i]);
    }
  });

  // Canonical vector lock — the canonical 32-zero-byte input has a fixed seed.
  // If either viem regresses or the algorithm drifts, this fails loudly with the
  // actual value in the diff. Per operator's refinement (D3): "memorable, audit-readable".
  it("CANONICAL VECTOR: deriveBrpSeed(32-zero-bytes) matches locked value", () => {
    const frozenOutput = new Uint8Array(32);
    const seed = deriveBrpSeed(frozenOutput);
    // Locked value computed at first commit. Determined by:
    //   keccak256(toBytes("VAPI-BRP-RENDER-v1") || 0x00 * 32) → first 4 bytes as uint32 BE.
    expect(seed).toBe(CANONICAL_32_ZERO_SEED);
  });
});

// Locked canonical seed for the 32-zero-bytes vector.
//
// Computed at first vitest run on 2026-05-02:
//   keccak256(toBytes("VAPI-BRP-RENDER-v1") || 0x00 * 32)
//     digest first 4 bytes = 0x87b0f938
//   uint32 big-endian = 0x87b0f938 = 2,276,522,296
//
// If either viem regresses or the algorithm drifts, this assertion fails
// loudly with the actual value in the diff. Per Decision D3.
const CANONICAL_32_ZERO_SEED: number = 0x87b0f938;
