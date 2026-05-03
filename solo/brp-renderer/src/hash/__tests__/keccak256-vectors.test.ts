import { describe, it, expect } from "vitest";
import { keccak256, toBytes } from "viem";

// INV-BRP-3 BY VERIFICATION (not assertion): if viem's keccak256 ever regresses,
// this test fails loudly. The vectors are well-known Ethereum/Keccak-256 reference
// values and can be re-confirmed against any independent Keccak-256 implementation.
//
// Note: these are KECCAK-256 (Ethereum-style, the pre-NIST-finalization variant),
// NOT NIST SHA3-256. Ethereum kept the pre-finalization padding; viem's keccak256
// follows the same convention. Vectors below are verified against go-ethereum and
// pyethereum reference implementations.

interface Vector {
  readonly name: string;
  readonly inputUtf8: string | null;
  readonly inputHex: string | null;
  readonly expectedHex: `0x${string}`;
}

const VECTORS: readonly Vector[] = [
  {
    name: "empty string",
    inputUtf8: "",
    inputHex: null,
    expectedHex:
      "0xc5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470",
  },
  {
    name: "the ASCII string 'abc'",
    inputUtf8: "abc",
    inputHex: null,
    expectedHex:
      "0x4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45",
  },
  {
    name: "the ASCII string 'The quick brown fox jumps over the lazy dog'",
    inputUtf8: "The quick brown fox jumps over the lazy dog",
    inputHex: null,
    expectedHex:
      "0x4d741b6f1eb29cb2a9b9911c82f56fa8d73b04959d3d9d222895df6c0b28aa15",
  },
  {
    name: "single byte 0x00",
    inputUtf8: null,
    inputHex: "00",
    expectedHex:
      "0xbc36789e7a1e281436464229828f817d6612f7b477d66591ff96a9e064bcc98a",
  },
];

function hexToBytes(hex: string): Uint8Array {
  const clean = hex.startsWith("0x") ? hex.slice(2) : hex;
  if (clean.length % 2 !== 0) {
    throw new Error(`hex length must be even, got ${clean.length}`);
  }
  const out = new Uint8Array(clean.length / 2);
  for (let i = 0; i < out.length; i++) {
    out[i] = parseInt(clean.slice(i * 2, i * 2 + 2), 16);
  }
  return out;
}

describe("keccak256 reference vectors — INV-BRP-3 by verification", () => {
  for (const v of VECTORS) {
    it(`viem.keccak256 matches ${v.name}`, () => {
      const input: Uint8Array =
        v.inputUtf8 !== null ? toBytes(v.inputUtf8) : hexToBytes(v.inputHex!);
      const result = keccak256(input, "hex");
      expect(result.toLowerCase()).toBe(v.expectedHex.toLowerCase());
    });
  }

  it("output length is exactly 32 bytes for any input", () => {
    const inputs = [new Uint8Array(0), new Uint8Array(1), new Uint8Array(64), new Uint8Array(1024)];
    for (const input of inputs) {
      const out = keccak256(input, "bytes");
      expect(out.length).toBe(32);
    }
  });

  it("byte form and hex form agree on byte content", () => {
    const input = toBytes("VAPI-BRP-RENDER-v1");
    const asBytes = keccak256(input, "bytes");
    const asHex = keccak256(input, "hex");
    const reHex =
      "0x" +
      Array.from(asBytes)
        .map((b) => b.toString(16).padStart(2, "0"))
        .join("");
    expect(reHex.toLowerCase()).toBe(asHex.toLowerCase());
  });
});
