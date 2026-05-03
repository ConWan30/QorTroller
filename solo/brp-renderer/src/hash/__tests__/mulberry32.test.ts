import { describe, it, expect } from "vitest";
import { mulberry32 } from "../mulberry32";

describe("mulberry32 — deterministic visual PRNG", () => {
  it("same seed → identical sequence (determinism)", () => {
    const a = mulberry32(0xdeadbeef);
    const b = mulberry32(0xdeadbeef);
    for (let i = 0; i < 1000; i++) {
      expect(a()).toBe(b());
    }
  });

  it("different seeds → different sequences (high confidence over 1000 samples)", () => {
    const a = mulberry32(1);
    const b = mulberry32(2);
    let collisions = 0;
    for (let i = 0; i < 1000; i++) {
      if (a() === b()) collisions++;
    }
    // If the PRNG were broken, collisions ≈ 1000. Healthy: well below 5.
    expect(collisions).toBeLessThan(5);
  });

  it("output is always in [0, 1)", () => {
    const r = mulberry32(42);
    for (let i = 0; i < 10_000; i++) {
      const v = r();
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThan(1);
    }
  });

  it("mean over 1M samples is approximately 0.5 (Bryc PRNGs.md statistical-quality claim)", () => {
    const r = mulberry32(0xc0ffee);
    let sum = 0;
    const N = 1_000_000;
    for (let i = 0; i < N; i++) {
      sum += r();
    }
    const mean = sum / N;
    expect(mean).toBeGreaterThanOrEqual(0.49);
    expect(mean).toBeLessThanOrEqual(0.51);
  });

  it("32-bit seed coercion: out-of-range seeds normalize via uint32 truncation", () => {
    // Seed values that JS bitwise ops would normalize identically.
    const a = mulberry32(0xffffffff);
    const b = mulberry32(-1); // -1 >>> 0 === 0xffffffff
    for (let i = 0; i < 100; i++) {
      expect(a()).toBe(b());
    }
  });

  it("period sanity: distinct seeds produce distinct first-1000-sample sequences (sample of 64 seeds)", () => {
    const fingerprints = new Set<string>();
    const sampleSeeds = [
      0, 1, 2, 3, 7, 13, 31, 42, 0x100, 0xfff, 0xdead, 0xc0ffee, 0x10000000,
      0x80000000, 0xffffffff, 0xa5a5a5a5, 0x5a5a5a5a, 0x12345678, 0x87654321,
      0xcafebabe, 0xdeadbeef, 0xfeedface, 0xfacefeed, 0xb16b00b5, 0xbaadf00d,
      0xabad1dea, 0x1bad1dea, 0x10101010, 0x01010101, 0xff00ff00, 0x00ff00ff,
      ...Array.from({ length: 32 }, (_, i) => 0x10000 + i * 0x101),
    ];
    for (const seed of sampleSeeds) {
      const r = mulberry32(seed);
      let acc = "";
      for (let i = 0; i < 16; i++) acc += r().toFixed(8) + ",";
      fingerprints.add(acc);
    }
    expect(fingerprints.size).toBe(sampleSeeds.length);
  });
});
