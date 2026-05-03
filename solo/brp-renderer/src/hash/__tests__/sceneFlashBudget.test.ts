import { describe, it, expect } from "vitest";
import {
  evaluateBrpScene,
  AMBIENT_LAYER_MATERIAL,
  REGISTERED_SCENE_MATERIALS,
} from "../sceneFlashBudget";
import type { MaterialDescriptor } from "../flashBudget";

describe("sceneFlashBudget — INV-BRP-4 progression hook", () => {
  it("T-4b-1: empty scene passes vacuously", () => {
    const r = evaluateBrpScene([]);
    expect(r.ok).toBe(true);
    expect(r.violations).toEqual([]);
  });

  it("T-4b-2: AmbientLayer's static-material descriptor passes by construction (3 pathways)", () => {
    const r = evaluateBrpScene([AMBIENT_LAYER_MATERIAL]);
    expect(r.ok).toBe(true);
    expect(r.violations).toEqual([]);
  });

  it("T-4b-3: tampered scene (frequency >= 3 Hz, area >= 87,296, ΔL >= 0.10) fails with violations", () => {
    const tampered: MaterialDescriptor = {
      id: "tampered/material",
      frequency_hz: 5.0,
      area_css_px2: 200_000,
      delta_luminance: 0.5,
      is_saturated_red: false,
    };
    const r = evaluateBrpScene([tampered]);
    expect(r.ok).toBe(false);
    expect(r.violations.length).toBeGreaterThanOrEqual(1);
    expect(r.violations.some((v) => v.includes("tampered/material"))).toBe(true);
  });

  it("T-4b-4: REGISTERED_SCENE_MATERIALS includes AmbientLayer descriptor and passes", () => {
    expect(REGISTERED_SCENE_MATERIALS.length).toBe(1);
    expect(REGISTERED_SCENE_MATERIALS[0]?.id).toBe("AmbientLayer/ambient-mesh");
    expect(evaluateBrpScene().ok).toBe(true);
  });
});
