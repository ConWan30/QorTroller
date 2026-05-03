import { describe, it, expect } from "vitest";
import {
  evaluateFlashBudget,
  evaluateScene,
  G19_FREQUENCY_HZ_CAP,
  G176_AREA_CSS_PX2_CAP,
  DELTA_L_CAP,
  SATURATED_RED_DELTA_UV_CAP,
  type MaterialDescriptor,
} from "../flashBudget";

const baseMaterial: MaterialDescriptor = {
  id: "test-material",
  frequency_hz: 0,
  area_css_px2: 0,
  delta_luminance: 0,
  is_saturated_red: false,
};

describe("flashBudget — INV-BRP-4 (draft) WCAG 2.3.1 enforcement", () => {
  it("exposes the W3C-verbatim numeric constants", () => {
    expect(G19_FREQUENCY_HZ_CAP).toBe(3);
    expect(G176_AREA_CSS_PX2_CAP).toBe(87_296);
    expect(DELTA_L_CAP).toBe(0.1);
    expect(SATURATED_RED_DELTA_UV_CAP).toBe(0.2);
  });

  // G19 — frequency cap.
  it("G19: frequency 2.9 Hz passes", () => {
    const r = evaluateFlashBudget({ ...baseMaterial, frequency_hz: 2.9 });
    expect(r.ok).toBe(true);
    expect(r.pathway).toBe("G19");
  });

  it("G19: frequency exactly 3.0 Hz fails (strict-less-than cap)", () => {
    const r = evaluateFlashBudget({
      ...baseMaterial,
      frequency_hz: 3.0,
      area_css_px2: 200_000, // also too large
      delta_luminance: 0.5, // also too large
    });
    expect(r.ok).toBe(false);
    expect(r.pathway).toBeNull();
  });

  it("G19: frequency 3.1 Hz fails when no other pathway applies", () => {
    const r = evaluateFlashBudget({
      ...baseMaterial,
      frequency_hz: 3.1,
      area_css_px2: 200_000,
      delta_luminance: 0.2,
    });
    expect(r.ok).toBe(false);
  });

  // G176 — area cap.
  it("G176: 87,295 CSS px² passes", () => {
    const r = evaluateFlashBudget({
      ...baseMaterial,
      frequency_hz: 30,
      area_css_px2: 87_295,
      delta_luminance: 0.5,
    });
    expect(r.ok).toBe(true);
    expect(r.pathway).toBe("G176");
  });

  it("G176: 87,296 CSS px² fails (strict-less-than cap)", () => {
    const r = evaluateFlashBudget({
      ...baseMaterial,
      frequency_hz: 30,
      area_css_px2: 87_296,
      delta_luminance: 0.5,
    });
    expect(r.ok).toBe(false);
  });

  it("G176: 87,297 CSS px² fails", () => {
    const r = evaluateFlashBudget({
      ...baseMaterial,
      frequency_hz: 30,
      area_css_px2: 87_297,
      delta_luminance: 0.5,
    });
    expect(r.ok).toBe(false);
  });

  // ΔL — luminance clamp.
  it("ΔL: 0.09 passes", () => {
    const r = evaluateFlashBudget({
      ...baseMaterial,
      frequency_hz: 30,
      area_css_px2: 200_000,
      delta_luminance: 0.09,
    });
    expect(r.ok).toBe(true);
    expect(r.pathway).toBe("DELTA_L");
  });

  it("ΔL: 0.10 fails (strict-less-than cap)", () => {
    const r = evaluateFlashBudget({
      ...baseMaterial,
      frequency_hz: 30,
      area_css_px2: 200_000,
      delta_luminance: 0.10,
    });
    expect(r.ok).toBe(false);
  });

  it("ΔL: 0.11 fails", () => {
    const r = evaluateFlashBudget({
      ...baseMaterial,
      frequency_hz: 30,
      area_css_px2: 200_000,
      delta_luminance: 0.11,
    });
    expect(r.ok).toBe(false);
  });

  // Saturated-red guard.
  it("saturated-red guard: Δuv 0.21 fails regardless of any pathway", () => {
    const r = evaluateFlashBudget({
      ...baseMaterial,
      frequency_hz: 0.1, // would otherwise pass G19
      area_css_px2: 0,
      delta_luminance: 0,
      is_saturated_red: true,
      chromaticity_delta_uv: 0.21,
    });
    expect(r.ok).toBe(false);
    expect(r.violations.some((v) => v.includes("saturated-red"))).toBe(true);
  });

  it("saturated-red guard: Δuv 0.19 passes (still within guard)", () => {
    const r = evaluateFlashBudget({
      ...baseMaterial,
      frequency_hz: 1,
      is_saturated_red: true,
      chromaticity_delta_uv: 0.19,
    });
    expect(r.ok).toBe(true);
    expect(r.pathway).toBe("G19");
  });

  // Scene-level evaluation.
  it("scene: passes when every material satisfies at least one pathway", () => {
    const scene = evaluateScene([
      { ...baseMaterial, id: "m1", frequency_hz: 1 },
      { ...baseMaterial, id: "m2", area_css_px2: 100, delta_luminance: 0.5, frequency_hz: 60 },
      { ...baseMaterial, id: "m3", delta_luminance: 0.05, frequency_hz: 60, area_css_px2: 200_000 },
    ]);
    expect(scene.ok).toBe(true);
  });

  it("scene: any material failure fails the whole scene; violations list every failure", () => {
    const scene = evaluateScene([
      { ...baseMaterial, id: "ok-mat", frequency_hz: 1 },
      {
        ...baseMaterial,
        id: "bad-mat-1",
        frequency_hz: 10,
        area_css_px2: 200_000,
        delta_luminance: 0.5,
      },
      {
        ...baseMaterial,
        id: "bad-mat-2",
        frequency_hz: 30,
        area_css_px2: 100_000,
        delta_luminance: 0.3,
      },
    ]);
    expect(scene.ok).toBe(false);
    expect(scene.violations.length).toBe(2);
    expect(scene.violations.some((v) => v.includes("bad-mat-1"))).toBe(true);
    expect(scene.violations.some((v) => v.includes("bad-mat-2"))).toBe(true);
  });

  it("scene: empty material list passes vacuously (no animated materials, no risk)", () => {
    const scene = evaluateScene([]);
    expect(scene.ok).toBe(true);
    expect(scene.violations).toEqual([]);
  });
});
