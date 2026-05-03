import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { validateManifest } from "../validate";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const manifestPath = resolve(__dirname, "..", "brp.manifest.json");

const raw = readFileSync(manifestPath, "utf8");
const manifest: unknown = JSON.parse(raw);

describe("brp.manifest.json — schema and honesty-first posture", () => {
  it("parses as JSON and is a plain object", () => {
    expect(typeof manifest).toBe("object");
    expect(Array.isArray(manifest)).toBe(false);
  });

  it("validates against schema (validateManifest returns ok)", () => {
    const result = validateManifest(manifest);
    if (!result.ok) {
      // Surface every violation in the failure output for honesty-first debugging.
      // eslint-disable-next-line no-console
      console.error("Manifest violations:\n" + result.violations.join("\n"));
    }
    expect(result.violations).toEqual([]);
    expect(result.ok).toBe(true);
  });

  it("track_classification is exactly 'out-of-band-solo'", () => {
    const m = manifest as Record<string, unknown>;
    expect(m["track_classification"]).toBe("out-of-band-solo");
  });

  it("phase_number is exactly null (not 241, not any number)", () => {
    const m = manifest as Record<string, unknown>;
    expect(m["phase_number"]).toBeNull();
  });

  it("every component entry has live: false (honesty-first default)", () => {
    const m = manifest as Record<string, unknown>;
    const components = m["components"] as Record<string, { live: boolean }>;
    for (const [key, entry] of Object.entries(components)) {
      expect(typeof entry.live, `components.${key}.live`).toBe("boolean");
      expect(entry.live, `components.${key}.live`).toBe(false);
    }
  });

  it("every module entry has live: false (no live telemetry source yet)", () => {
    const m = manifest as Record<string, unknown>;
    const modules = m["modules"] as Record<string, { live: boolean }>;
    for (const [key, entry] of Object.entries(modules)) {
      expect(typeof entry.live, `modules.${key}.live`).toBe("boolean");
      expect(entry.live, `modules.${key}.live`).toBe(false);
    }
  });

  it("hash_library records the viem-for-ethers substitution per Decision D3", () => {
    const m = manifest as Record<string, unknown>;
    const hash = m["hash_library"] as Record<string, unknown>;
    expect(hash["name"]).toBe("viem");
    expect(hash["substituted_from"]).toBe("ethers@6");
    expect(typeof hash["substitution_reason"]).toBe("string");
    expect((hash["substitution_reason"] as string).length).toBeGreaterThan(20);
  });

  it("hash_domain string is exactly 'VAPI-BRP-RENDER-v1'", () => {
    const m = manifest as Record<string, unknown>;
    const dom = m["hash_domain"] as Record<string, unknown>;
    expect(dom["string"]).toBe("VAPI-BRP-RENDER-v1");
  });

  it("hash_domain does not collide with any FROZEN-v1 protocol prefix", () => {
    const m = manifest as Record<string, unknown>;
    const dom = m["hash_domain"] as Record<string, unknown>;
    const reserved = dom["collision_check_against_existing_v1_tags"] as readonly string[];
    const renderDomain = dom["string"] as string;
    for (const tag of reserved) {
      // Neither a prefix of the other.
      expect(renderDomain.startsWith(tag), `${renderDomain} starts with ${tag}`).toBe(false);
      expect(tag.startsWith(renderDomain), `${tag} starts with ${renderDomain}`).toBe(false);
    }
  });

  it("every PV-CI draft has added_to_pv_ci_gate: false (gate not modified by this commit)", () => {
    const m = manifest as Record<string, unknown>;
    const drafts = m["pv_ci_drafts"] as Record<string, Record<string, unknown>>;
    for (const [key, entry] of Object.entries(drafts)) {
      expect(entry["added_to_pv_ci_gate"], `pv_ci_drafts.${key}`).toBe(false);
    }
  });

  it("INV-BRP-1 through INV-BRP-5 are all present in pv_ci_drafts", () => {
    const m = manifest as Record<string, unknown>;
    const drafts = m["pv_ci_drafts"] as Record<string, unknown>;
    expect(drafts["INV-BRP-1"]).toBeDefined();
    expect(drafts["INV-BRP-2"]).toBeDefined();
    expect(drafts["INV-BRP-3"]).toBeDefined();
    expect(drafts["INV-BRP-4"]).toBeDefined();
    expect(drafts["INV-BRP-5"]).toBeDefined();
  });

  it("rejects a tampered manifest (track_classification flipped)", () => {
    const tampered = { ...(manifest as Record<string, unknown>), track_classification: "phase" };
    const result = validateManifest(tampered);
    expect(result.ok).toBe(false);
    expect(result.violations.some((v) => v.includes("track_classification"))).toBe(true);
  });

  it("rejects a tampered manifest (a component flipped to live: true without ceremony)", () => {
    const m = manifest as Record<string, unknown>;
    const components = m["components"] as Record<string, Record<string, unknown>>;
    const firstKey = Object.keys(components)[0]!;
    const tampered = {
      ...m,
      components: {
        ...components,
        [firstKey]: { ...components[firstKey], live: "true" }, // wrong type
      },
    };
    const result = validateManifest(tampered);
    expect(result.ok).toBe(false);
  });

  // --- Commit 3 additions: docs bucket ---

  it("every docs entry has live: false (Commit 3 honesty-first default)", () => {
    const m = manifest as Record<string, unknown>;
    const docs = m["docs"] as Record<string, { live: boolean }>;
    expect(Object.keys(docs).length).toBeGreaterThan(0);
    for (const [key, entry] of Object.entries(docs)) {
      expect(typeof entry.live, `docs.${key}.live`).toBe("boolean");
      expect(entry.live, `docs.${key}.live`).toBe(false);
    }
  });

  it("rejects a manifest missing the 'docs' bucket", () => {
    const m = { ...(manifest as Record<string, unknown>) };
    delete m["docs"];
    const result = validateManifest(m);
    expect(result.ok).toBe(false);
    expect(result.violations.some((v) => v.includes("docs"))).toBe(true);
  });

  it("Commit 3 docs entries cover BACKEND_CONTRACT, LATENCY_BUDGET, OPEN_QUESTIONS", () => {
    const m = manifest as Record<string, unknown>;
    const docs = m["docs"] as Record<string, Record<string, unknown>>;
    for (const required of ["BACKEND_CONTRACT", "LATENCY_BUDGET", "OPEN_QUESTIONS"]) {
      expect(docs[required], `docs.${required}`).toBeDefined();
      expect(docs[required]!["live"], `docs.${required}.live`).toBe(false);
      expect(typeof docs[required]!["path"], `docs.${required}.path`).toBe("string");
      expect((docs[required]!["path"] as string).endsWith(".md")).toBe(true);
    }
  });

  // --- Commit 4a addition: implementation-progression assertion ---

  it("Commit 4a — AccessibilityShell.implemented flips to true; live stays false", () => {
    const m = manifest as Record<string, unknown>;
    const components = m["components"] as Record<string, Record<string, unknown>>;
    const shell = components["AccessibilityShell"]!;
    expect(shell["implemented"]).toBe(true);
    expect(shell["live"]).toBe(false);
    expect(typeof shell["path"]).toBe("string");
    expect(shell["path"]).toBe("src/components/AccessibilityShell.tsx");
  });

  // --- Commit 4b addition: BrpCanvas + AmbientLayer + sceneFlashBudget ---

  it("Commit 4b — BrpCanvas + AmbientLayer flip to implemented:true; live stays false", () => {
    const m = manifest as Record<string, unknown>;
    const components = m["components"] as Record<string, Record<string, unknown>>;

    const canvas = components["BrpCanvas"]!;
    expect(canvas["implemented"]).toBe(true);
    expect(canvas["live"]).toBe(false);
    expect(canvas["path"]).toBe("src/components/BrpCanvas.tsx");

    const layer = components["AmbientLayer"]!;
    expect(layer["implemented"]).toBe(true);
    expect(layer["live"]).toBe(false);
    expect(layer["path"]).toBe("src/components/AmbientLayer.tsx");
  });

  it("Commit 4b — modules.sceneFlashBudget added (implemented:true, live:false)", () => {
    const m = manifest as Record<string, unknown>;
    const modules = m["modules"] as Record<string, Record<string, unknown>>;
    const scene = modules["sceneFlashBudget"]!;
    expect(scene).toBeDefined();
    expect(scene["implemented"]).toBe(true);
    expect(scene["live"]).toBe(false);
    expect(scene["path"]).toBe("src/hash/sceneFlashBudget.ts");
  });

  // --- Commit 4c: LegibilityOverlay + BrpMount + fixtures + mockLoaders ---

  it("Commit 4c — LegibilityOverlay + BrpMount flip implemented:true; live stays false", () => {
    const m = manifest as Record<string, unknown>;
    const components = m["components"] as Record<string, Record<string, unknown>>;

    const overlay = components["LegibilityOverlay"]!;
    expect(overlay["implemented"]).toBe(true);
    expect(overlay["live"]).toBe(false);
    expect(overlay["path"]).toBe("src/components/LegibilityOverlay.tsx");

    const mount = components["BrpMount"]!;
    expect(mount["implemented"]).toBe(true);
    expect(mount["live"]).toBe(false);
    expect(mount["path"]).toBe("src/components/BrpMount.tsx");
  });

  it("Commit 4c — fixtures bucket has pitlSnapshot + enrollmentSession (live:false)", () => {
    const m = manifest as Record<string, unknown>;
    const fixtures = m["fixtures"] as Record<string, Record<string, unknown>>;

    const pitl = fixtures["pitlSnapshot"]!;
    expect(pitl).toBeDefined();
    expect(pitl["live"]).toBe(false);
    expect(pitl["path"]).toBe("src/mocks/fixtures/pitl.snapshot.json");

    const enrollment = fixtures["enrollmentSession"]!;
    expect(enrollment).toBeDefined();
    expect(enrollment["live"]).toBe(false);
    expect(enrollment["path"]).toBe("src/mocks/fixtures/enrollment.session.json");
  });

  it("Commit 4c — modules.mockLoaders added (implemented:true, live:false)", () => {
    const m = manifest as Record<string, unknown>;
    const modules = m["modules"] as Record<string, Record<string, unknown>>;
    const loaders = modules["mockLoaders"]!;
    expect(loaders).toBeDefined();
    expect(loaders["implemented"]).toBe(true);
    expect(loaders["live"]).toBe(false);
    expect(loaders["path"]).toBe("src/mocks/loaders.ts");
  });

  // --- Commit 4d: PerfOverlay flip + tooling bucket + stories bucket ---

  it("Commit 4d — PerfOverlay.implemented flips to true; live stays false", () => {
    const m = manifest as Record<string, unknown>;
    const components = m["components"] as Record<string, Record<string, unknown>>;
    const perf = components["PerfOverlay"]!;
    expect(perf["implemented"]).toBe(true);
    expect(perf["live"]).toBe(false);
    expect(perf["path"]).toBe("src/components/PerfOverlay.tsx");
  });

  it("Commit 4d — tooling bucket has storybook + playwright + mswHandlers + captureScript", () => {
    const m = manifest as Record<string, unknown>;
    const tooling = m["tooling"] as Record<string, Record<string, unknown>>;
    for (const key of ["storybook", "playwright", "mswHandlers", "captureScript"]) {
      expect(tooling[key], `tooling.${key}`).toBeDefined();
      expect(tooling[key]!["live"], `tooling.${key}.live`).toBe(false);
      expect(typeof tooling[key]!["path"]).toBe("string");
    }
  });

  it("Commit 4d — stories bucket covers all 5 public components", () => {
    const m = manifest as Record<string, unknown>;
    const stories = m["stories"] as Record<string, Record<string, unknown>>;
    for (const key of [
      "AccessibilityShell",
      "AmbientLayer",
      "BrpCanvas",
      "LegibilityOverlay",
      "BrpMount",
    ]) {
      expect(stories[key], `stories.${key}`).toBeDefined();
      expect(stories[key]!["live"], `stories.${key}.live`).toBe(false);
      expect(stories[key]!["implemented"]).toBe(true);
      expect((stories[key]!["path"] as string).endsWith(".stories.tsx")).toBe(true);
    }
  });

  it("Commit 4d — every tooling and stories entry has live: false (honesty-first default)", () => {
    const m = manifest as Record<string, unknown>;
    for (const bucket of ["tooling", "stories"] as const) {
      const entries = m[bucket] as Record<string, { live: boolean }>;
      expect(Object.keys(entries).length).toBeGreaterThan(0);
      for (const [key, entry] of Object.entries(entries)) {
        expect(typeof entry.live, `${bucket}.${key}.live`).toBe("boolean");
        expect(entry.live, `${bucket}.${key}.live`).toBe(false);
      }
    }
  });
});
