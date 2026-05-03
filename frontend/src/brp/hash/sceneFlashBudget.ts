// sceneFlashBudget — INV-BRP-4 progression hook.
//
// Track classification: out-of-band-solo. NOT Phase 241. NOT in the sequential
// VAPI protocol chain.
//
// Bridges the renderer's scene-graph descriptors (R3F components in 4b+) to the
// pure-function flashBudget analyzer shipped in commit 8da89b59. This module
// is the integration hook that INV-BRP-4 (draft) names: every animated material
// declared by BRP code passes through here at compile/test time, and the
// existing G19 / G176 / ΔL static analyzer enforces WCAG 2.3.1 by construction.
//
// 4b ships AmbientLayer's static-material descriptor as the only registered
// scene material. 4c will add LegibilityOverlay's overlay-text material. 4d
// will run this analyzer in CI against every Storybook story's declared scene
// material list.
//
// This module imports ONLY from src/hash/flashBudget.ts. It does NOT import any
// React, R3F, or DOM dependency — it must be testable in pure-Node, and its
// output must be auditable from the source tree alone.

import {
  evaluateScene,
  type FlashBudgetResult,
  type MaterialDescriptor,
} from "./flashBudget";

/**
 * AmbientLayer's static-material descriptor. Registered here (not inline in
 * AmbientLayer.tsx) so the analyzer can reference it without importing React.
 *
 * Conservative values — three WCAG 2.3.1 pathways pass simultaneously, providing
 * defense-in-depth against future tweaks:
 *   - frequency_hz=0.5 vs G19 cap 3 Hz   (6× margin)
 *   - area_css_px2=50_000 vs G176 cap 87,296 (1.7× margin)
 *   - delta_luminance=0.05 vs ΔL cap 0.10 (2× margin)
 *
 * The mesh itself is a low-poly icosahedron (12 vertices, 20 faces) instanced
 * via drei's <Instances>; the material is a non-saturated cool-palette color
 * with a low-amplitude breathing oscillator at 0.5 Hz when motion is enabled.
 */
export const AMBIENT_LAYER_MATERIAL: MaterialDescriptor = {
  id: "AmbientLayer/ambient-mesh",
  frequency_hz: 0.5,
  area_css_px2: 50_000,
  delta_luminance: 0.05,
  is_saturated_red: false,
};

/**
 * Default registered scene materials. The renderer's animated material set as
 * of this commit. New materials are appended as commits 4c/4d add components.
 */
export const REGISTERED_SCENE_MATERIALS: readonly MaterialDescriptor[] = [
  AMBIENT_LAYER_MATERIAL,
];

/**
 * Run the flashBudget analyzer over a list of scene materials. Thin adapter
 * around evaluateScene; the wrapper exists so tests and CI hooks can call this
 * function by a stable name without re-importing the lower-level analyzer.
 */
export function evaluateBrpScene(
  materials: readonly MaterialDescriptor[] = REGISTERED_SCENE_MATERIALS,
): FlashBudgetResult {
  return evaluateScene(materials);
}
