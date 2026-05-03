import { describe, it, expect } from "vitest";
import {
  seedToInstanceParams,
  DEFAULT_INSTANCE_COUNT,
} from "../AmbientLayer";
import { evaluateBrpScene, AMBIENT_LAYER_MATERIAL } from "../../hash/sceneFlashBudget";

describe("AmbientLayer — seed→instance-params pure logic", () => {
  it("T-4b-5: seedToInstanceParams is deterministic (same seed → same params)", () => {
    const a = seedToInstanceParams(0x87b0f938, 8);
    const b = seedToInstanceParams(0x87b0f938, 8);
    expect(a).toEqual(b);
  });

  it("T-4b-6: different seeds → different params (high confidence over 64 instances)", () => {
    const a = seedToInstanceParams(1, 64);
    const b = seedToInstanceParams(2, 64);
    let identical = 0;
    for (let i = 0; i < 64; i++) {
      const aP = a[i]!;
      const bP = b[i]!;
      if (
        aP.position[0] === bP.position[0] &&
        aP.position[1] === bP.position[1] &&
        aP.position[2] === bP.position[2]
      ) {
        identical++;
      }
    }
    expect(identical).toBeLessThan(2);
  });

  it("T-4b-7: param ranges respected — positions ∈ [-1,1], rotations ∈ [0,2π), scale ∈ [0.5,1.5]", () => {
    const params = seedToInstanceParams(0xdeadbeef, 256);
    for (const p of params) {
      for (const v of p.position) {
        expect(v).toBeGreaterThanOrEqual(-1);
        expect(v).toBeLessThan(1);
      }
      for (const v of p.rotation) {
        expect(v).toBeGreaterThanOrEqual(0);
        expect(v).toBeLessThan(Math.PI * 2);
      }
      expect(p.scale).toBeGreaterThanOrEqual(0.5);
      expect(p.scale).toBeLessThan(1.5);
    }
  });

  it("T-4b-8: count parameter respected; default DEFAULT_INSTANCE_COUNT", () => {
    expect(seedToInstanceParams(42, 8).length).toBe(8);
    expect(seedToInstanceParams(42, 64).length).toBe(64);
    expect(seedToInstanceParams(42).length).toBe(DEFAULT_INSTANCE_COUNT);
    expect(DEFAULT_INSTANCE_COUNT).toBe(64);
  });

  it("T-4b-9: AmbientLayer's static-material descriptor passes flashBudget by construction", () => {
    const r = evaluateBrpScene([AMBIENT_LAYER_MATERIAL]);
    expect(r.ok).toBe(true);
    expect(r.violations).toEqual([]);
  });
});
