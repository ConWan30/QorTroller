// INV-BRP-1 (DRAFT — NOT yet added to PV-CI gate) — live-flag honesty.
//
// Statement: every BRP-namespaced React component must render a `data-live`
// attribute matching its manifest entry; CI fails if a `data-live="true"`
// element exists for which the manifest entry is `live: false` or the upstream
// telemetry is `live: false`.
//
// This commit ships the math + manifest + contract layer ONLY. The React
// component surface arrives in commit 2+. Therefore this draft spec asserts:
//   (a) the manifest exists and has a `live` field per entry (already covered
//       by manifest.test.ts); and
//   (b) when the React surface is added, the data-live wiring contract is
//       documented here as a hard requirement (this spec is the binding
//       documentation, ready for ceremony adoption).
//
// At ceremony time, this file is moved into PV-CI's invariants/ directory and
// expanded with DOM-traversal assertions against the integrated mount.
//
// Status: DRAFT — added_to_pv_ci_gate=false in brp.manifest.json#pv_ci_drafts.

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const manifestPath = resolve(
  __dirname,
  "..",
  "src",
  "manifest",
  "brp.manifest.json",
);

describe("INV-BRP-1 (draft) — live-flag honesty", () => {
  const raw = readFileSync(manifestPath, "utf8");
  const manifest = JSON.parse(raw) as Record<string, unknown>;

  it("manifest declares this invariant is drafted, not adopted", () => {
    const drafts = manifest["pv_ci_drafts"] as Record<string, Record<string, unknown>>;
    const entry = drafts["INV-BRP-1"];
    expect(entry).toBeDefined();
    expect(entry!["added_to_pv_ci_gate"]).toBe(false);
  });

  it("every component pre-registered in the manifest carries a live: false default", () => {
    const components = manifest["components"] as Record<string, { live: boolean }>;
    expect(Object.keys(components).length).toBeGreaterThan(0);
    for (const [key, entry] of Object.entries(components)) {
      expect(entry.live, `components.${key}`).toBe(false);
    }
  });

  it("ceremony-time DOM-traversal hook (placeholder until commit 2+ React surface)", () => {
    // When the React components land:
    //   - render <BrpMount {...integrationContract} />
    //   - assert: every element with [data-live] resolves to a manifest entry
    //   - assert: no element carries data-live="true" while manifest says live:false
    //   - assert: no element carries data-live="true" while upstream liveness=false
    // For commit 1, this hook is reserved.
    expect(true).toBe(true);
  });
});
