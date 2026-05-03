// INV-BRP-3 (DRAFT — NOT yet added to PV-CI gate) — hash-domain isolation.
//
// Statement: every call to keccak256() (or, in future, poseidon()) from BRP code
// must pass through deriveBrpSeed(), which prepends the domain string
// "VAPI-BRP-RENDER-v1". Direct keccak256() calls outside the helper are forbidden.
//
// At ceremony time, the production check is: AST grep for raw keccak256( and
// poseidon( outside src/hash/deriveBrpSeed.ts. This draft spec performs the
// equivalent check at workspace scope.
//
// Status: DRAFT — added_to_pv_ci_gate=false in brp.manifest.json#pv_ci_drafts.

import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve, relative, join } from "node:path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const workspaceRoot = resolve(__dirname, "..");

// Files allowed to call keccak256() directly:
//   - the helper itself: src/hash/deriveBrpSeed.ts
//   - the test files: src/hash/__tests__/*.test.ts (vector tests verify the helper)
//   - this very spec file (this draft documents the rule and includes its own grep)
const ALLOWED_DIRECT_KECCAK_FILES = [
  "src/hash/deriveBrpSeed.ts",
  "src/hash/__tests__/deriveBrpSeed.test.ts",
  "src/hash/__tests__/keccak256-vectors.test.ts",
  "pv-ci-drafts/inv-brp-3.spec.ts",
];

function walkTs(dir: string, acc: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    if (name === "node_modules" || name === "dist" || name === ".git") continue;
    const full = join(dir, name);
    const st = statSync(full);
    if (st.isDirectory()) walkTs(full, acc);
    else if (st.isFile() && (name.endsWith(".ts") || name.endsWith(".tsx"))) acc.push(full);
  }
  return acc;
}

describe("INV-BRP-3 (draft) — hash-domain isolation", () => {
  it("manifest declares this invariant is drafted, not adopted", () => {
    const raw = readFileSync(
      resolve(workspaceRoot, "src", "manifest", "brp.manifest.json"),
      "utf8",
    );
    const manifest = JSON.parse(raw) as Record<string, unknown>;
    const drafts = manifest["pv_ci_drafts"] as Record<string, Record<string, unknown>>;
    const entry = drafts["INV-BRP-3"];
    expect(entry).toBeDefined();
    expect(entry!["added_to_pv_ci_gate"]).toBe(false);
  });

  it("no .ts/.tsx file outside the helper or its tests calls keccak256( directly", () => {
    const files = walkTs(workspaceRoot);
    const violations: string[] = [];
    for (const file of files) {
      const rel = relative(workspaceRoot, file).replace(/\\/g, "/");
      if (ALLOWED_DIRECT_KECCAK_FILES.includes(rel)) continue;
      const content = readFileSync(file, "utf8");
      // Match keccak256( as an identifier call — i.e., a code call, not a string mention.
      const match = content.match(/[^"'`/]\bkeccak256\(/);
      if (match) {
        violations.push(
          `${rel}: direct keccak256( call (use deriveBrpSeed() or get added to ALLOWED list at ceremony review)`,
        );
      }
    }
    expect(violations).toEqual([]);
  });

  it("renderer-side hash domain string is reserved as 'VAPI-BRP-RENDER-v1' in the helper source", () => {
    const helperSrc = readFileSync(
      resolve(workspaceRoot, "src", "hash", "deriveBrpSeed.ts"),
      "utf8",
    );
    expect(helperSrc.includes('"VAPI-BRP-RENDER-v1"')).toBe(true);
  });

  it("the helper applies domain separation by prepending the domain bytes before hashing", () => {
    const helperSrc = readFileSync(
      resolve(workspaceRoot, "src", "hash", "deriveBrpSeed.ts"),
      "utf8",
    );
    expect(helperSrc.includes("concat([DOMAIN_BYTES, frozenOutput])")).toBe(true);
  });
});
