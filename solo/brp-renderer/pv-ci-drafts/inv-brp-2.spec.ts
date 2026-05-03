// INV-BRP-2 (DRAFT — NOT yet added to PV-CI gate) — verification-downstream
// import boundary.
//
// Statement: no module under src/brp/** (or, in this solo workspace, no module
// under src/**) may import from any verification-side module group:
//   - poac/**
//   - vhp/**
//   - consensus/**
//   - zk/**
//   - any sibling VAPI workspace (frontend/, bridge/, contracts/, sdk/, scripts/, agents/)
//
// Enforcement layers:
//   1. ESLint no-restricted-imports rule in .eslintrc.json (already shipped).
//   2. AST grep at CI time (drafted here as a manual-grep placeholder until ceremony).
//
// Status: DRAFT — added_to_pv_ci_gate=false in brp.manifest.json#pv_ci_drafts.

import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve, relative, join } from "node:path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const workspaceRoot = resolve(__dirname, "..");

const FORBIDDEN_PATTERNS: RegExp[] = [
  /from\s+["'][^"']*\/poac\//,
  /from\s+["'][^"']*\/vhp\//,
  /from\s+["'][^"']*\/consensus\//,
  /from\s+["'][^"']*\/zk\//,
  /from\s+["'][^"']*\/frontend\/src\//,
  /from\s+["'][^"']*\/bridge\//,
  /from\s+["'][^"']*\/contracts\//,
  /from\s+["'][^"']*\/sdk\//,
  /from\s+["'][^"']*\/agents\//,
  /from\s+["']ethers["']/,
  /from\s+["']ethers\//,
  /from\s+["']hardhat["']/,
  /from\s+["']@nomicfoundation\//,
];

function walkTs(dir: string, acc: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    if (name === "node_modules" || name === "dist" || name === ".git") continue;
    const full = join(dir, name);
    const st = statSync(full);
    if (st.isDirectory()) {
      walkTs(full, acc);
    } else if (st.isFile() && (name.endsWith(".ts") || name.endsWith(".tsx"))) {
      acc.push(full);
    }
  }
  return acc;
}

describe("INV-BRP-2 (draft) — verification-downstream import boundary", () => {
  const raw = readFileSync(
    resolve(workspaceRoot, "src", "manifest", "brp.manifest.json"),
    "utf8",
  );
  const manifest = JSON.parse(raw) as Record<string, unknown>;

  it("manifest declares this invariant is drafted, not adopted", () => {
    const drafts = manifest["pv_ci_drafts"] as Record<string, Record<string, unknown>>;
    const entry = drafts["INV-BRP-2"];
    expect(entry).toBeDefined();
    expect(entry!["added_to_pv_ci_gate"]).toBe(false);
  });

  it("no .ts/.tsx file in this workspace imports from any forbidden group", () => {
    const files = walkTs(workspaceRoot);
    expect(files.length).toBeGreaterThan(0);
    const violations: string[] = [];
    for (const file of files) {
      const content = readFileSync(file, "utf8");
      for (const pattern of FORBIDDEN_PATTERNS) {
        const match = content.match(pattern);
        if (match) {
          // Allow patterns that appear inside a string literal documenting the rule
          // (this very file). Whitelist rule: the match is inside a JS regex literal.
          const idx = content.indexOf(match[0]);
          const surrounding = content.slice(Math.max(0, idx - 4), idx);
          if (surrounding.includes("/")) continue; // inside a regex literal
          violations.push(
            `${relative(workspaceRoot, file)}: forbidden import matching ${pattern}`,
          );
        }
      }
    }
    expect(violations).toEqual([]);
  });

  it("eslint config declares the no-restricted-imports rule for the same patterns", () => {
    const eslintPath = resolve(workspaceRoot, ".eslintrc.json");
    const eslint = JSON.parse(readFileSync(eslintPath, "utf8")) as Record<string, unknown>;
    const rules = eslint["rules"] as Record<string, unknown>;
    expect(rules["no-restricted-imports"]).toBeDefined();
    const ruleConfig = JSON.stringify(rules["no-restricted-imports"]);
    for (const required of ["poac", "vhp", "consensus", "zk", "frontend/src", "ethers"]) {
      expect(ruleConfig.includes(required), `eslint rule mentions ${required}`).toBe(true);
    }
  });
});
