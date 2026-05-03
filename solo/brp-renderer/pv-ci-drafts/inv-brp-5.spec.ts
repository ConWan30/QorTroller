// INV-BRP-5 (DRAFT — NOT yet added to PV-CI gate) — accessibility surface.
//
// Statement: every BRP canvas root must carry role="presentation" (or an explicit
// role="img" with aria-label) and have a sibling DOM description block; axe-core
// run on the host page chrome must report zero violations on the non-canvas DOM.
//
// In commit 1, no canvas exists yet. This draft asserts (a) the manifest declares
// this invariant drafted-not-adopted, and (b) reserves the contract that the
// R3F surface in commit 2+ must honor.
//
// Status: DRAFT — added_to_pv_ci_gate=false in brp.manifest.json#pv_ci_drafts.

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const workspaceRoot = resolve(__dirname, "..");

describe("INV-BRP-5 (draft) — accessibility surface", () => {
  it("manifest declares this invariant is drafted, not adopted", () => {
    const raw = readFileSync(
      resolve(workspaceRoot, "src", "manifest", "brp.manifest.json"),
      "utf8",
    );
    const manifest = JSON.parse(raw) as Record<string, unknown>;
    const drafts = manifest["pv_ci_drafts"] as Record<string, Record<string, unknown>>;
    const entry = drafts["INV-BRP-5"];
    expect(entry).toBeDefined();
    expect(entry!["added_to_pv_ci_gate"]).toBe(false);
  });

  it("manifest pre-registers AccessibilityShell as live: false (default-off until ceremony)", () => {
    const raw = readFileSync(
      resolve(workspaceRoot, "src", "manifest", "brp.manifest.json"),
      "utf8",
    );
    const manifest = JSON.parse(raw) as Record<string, unknown>;
    const components = manifest["components"] as Record<string, { live: boolean }>;
    expect(components["AccessibilityShell"]).toBeDefined();
    expect(components["AccessibilityShell"]!.live).toBe(false);
  });

  it("ceremony-time canvas-a11y hook (placeholder until commit 2+ R3F surface)", () => {
    // When the R3F surface lands, this assertion expands to:
    //   const html = render(<BrpMount {...integrationContract} />);
    //   const canvases = html.querySelectorAll("canvas");
    //   for (const canvas of canvases) {
    //     const role = canvas.getAttribute("role");
    //     expect(["presentation", "img"]).toContain(role);
    //     if (role === "presentation") {
    //       expect(canvas.getAttribute("aria-hidden")).toBe("true");
    //     } else {
    //       expect(canvas.getAttribute("aria-label")).toBeTruthy();
    //     }
    //   }
    //   const axeReport = await axe(html, { rules: { "canvas-aria-hidden": { enabled: true } } });
    //   expect(axeReport.violations).toEqual([]);
    expect(true).toBe(true);
  });

  it("ceremony-time prefers-reduced-motion hook (placeholder until commit 2+ R3F surface)", () => {
    // Per Block A1 of the design PDF: prefers-reduced-motion must (a) pause the
    // R3F frameloop ("never") and (b) replace the ambient layer with a static
    // gradient. The R3F integration in commit 2+ will assert this via a
    // matchMedia mock.
    expect(true).toBe(true);
  });
});
