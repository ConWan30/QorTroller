// INV-BRP-4 (DRAFT — NOT yet added to PV-CI gate) — photosensitivity budget.
//
// Statement: every animated material declared by BRP code must pass at least one
// WCAG 2.3.1 pathway:
//   G19:    frequency_hz < 3
//   G176:   area_css_px2 < 87,296
//   ΔL:     |Δrelative_luminance| < 0.10
// AND must not trigger the saturated-red guard
// (R/(R+G+B) >= 0.8 with Δuv > 0.2 in CIE 1976 UCS).
//
// In commit 1, no R3F materials exist yet; the analyzer is exercised against
// synthetic descriptors in src/hash/__tests__/flashBudget.test.ts. This draft
// asserts (a) the analyzer constants match the W3C-verbatim values, and (b) the
// scene-level evaluator returns ok for an empty scene.
//
// At ceremony time, this spec is upgraded to traverse the live R3F scene and
// invoke evaluateScene() against every animated material declared by BRP code.
//
// Status: DRAFT — added_to_pv_ci_gate=false in brp.manifest.json#pv_ci_drafts.

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import {
  evaluateScene,
  G19_FREQUENCY_HZ_CAP,
  G176_AREA_CSS_PX2_CAP,
  DELTA_L_CAP,
  SATURATED_RED_DELTA_UV_CAP,
} from "../src/hash/flashBudget";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const workspaceRoot = resolve(__dirname, "..");

describe("INV-BRP-4 (draft) — photosensitivity budget", () => {
  it("manifest declares this invariant is drafted, not adopted", () => {
    const raw = readFileSync(
      resolve(workspaceRoot, "src", "manifest", "brp.manifest.json"),
      "utf8",
    );
    const manifest = JSON.parse(raw) as Record<string, unknown>;
    const drafts = manifest["pv_ci_drafts"] as Record<string, Record<string, unknown>>;
    const entry = drafts["INV-BRP-4"];
    expect(entry).toBeDefined();
    expect(entry!["added_to_pv_ci_gate"]).toBe(false);
  });

  it("analyzer constants match W3C-verbatim WCAG 2.3.1 thresholds", () => {
    expect(G19_FREQUENCY_HZ_CAP).toBe(3);
    expect(G176_AREA_CSS_PX2_CAP).toBe(87_296);
    expect(DELTA_L_CAP).toBe(0.1);
    expect(SATURATED_RED_DELTA_UV_CAP).toBe(0.2);
  });

  it("no animated materials yet — empty scene passes vacuously (ceremony will populate)", () => {
    // Commit 1 ships no R3F materials. The R3F scene-graph traversal hook in
    // commit 2+ will collect MaterialDescriptors from declarative scene data
    // and feed them into evaluateScene. For now the empty scene is the
    // honesty-first answer.
    const r = evaluateScene([]);
    expect(r.ok).toBe(true);
  });

  it("ceremony-time scene-traversal hook (placeholder until commit 2+ R3F surface)", () => {
    // When the R3F surface lands, this assertion expands to:
    //   const materials = collectAnimatedMaterialsFromScene(<BrpMount {...} />);
    //   expect(evaluateScene(materials).ok).toBe(true);
    expect(true).toBe(true);
  });
});
