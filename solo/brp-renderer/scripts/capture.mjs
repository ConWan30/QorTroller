#!/usr/bin/env node
// capture.mjs — headless Storybook story capture for offline a11y audit.
//
// Track classification: out-of-band-solo. NOT Phase 241. NOT in the sequential
// VAPI protocol chain.
//
// Usage:
//   npm run build-storybook              # produce storybook-static/
//   npm run capture                      # capture all stories (default 30s each)
//   npm run capture -- --story <id>      # capture one story
//   npm run capture -- --duration 10     # 10-second clips
//
// Output:
//   dist/captures/<story-id>.webm
//
// PEAT (Photosensitive Epilepsy Analysis Tool) requires 25fps uncompressed
// AVI input. ffmpeg conversion is operator-driven (not part of this script):
//   ffmpeg -i dist/captures/<story>.webm -an -vcodec rawvideo -y -r 25 output.avi
// Per design PDF §"No-deploy testing"; documented in README.

import { chromium } from "@playwright/test";
import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const WORKSPACE_ROOT = dirname(__dirname);
const CAPTURE_DIR = join(WORKSPACE_ROOT, "dist", "captures");

// Story ids mirror e2e/a11y.spec.ts. Keep in sync — could be extracted to
// a shared module in a future refactor.
const STORIES = [
  "brp-accessibilityshell--default",
  "brp-accessibilityshell--with-reduced-motion-os-pref",
  "brp-accessibilityshell--with-user-motion-toggle-off",
  "brp-accessibilityshell--with-both-on-and-off",
  "brp-ambientlayer--default-seed",
  "brp-ambientlayer--non-deterministic-seed",
  "brp-ambientlayer--count-16",
  "brp-ambientlayer--count-256",
  "brp-brpcanvas--default",
  "brp-brpcanvas--frameloop-never",
  "brp-brpcanvas--count-16",
  "brp-brpcanvas--non-deterministic-seed",
  "brp-legibilityoverlay--ambient-mode",
  "brp-legibilityoverlay--active-aid-mode",
  "brp-legibilityoverlay--all-rows-active",
  "brp-legibilityoverlay--with-reduced-motion",
  "brp-brpmount--default-dev-surface",
  "brp-brpmount--enrollment-eligible",
  "brp-brpmount--enrollment-credentialed",
  "brp-brpmount--telemetry-degraded",
  "brp-brpmount--full-active-aid",
];

function parseArgs(argv) {
  const out = { duration: 30, story: null, baseUrl: "http://localhost:6006" };
  for (let i = 2; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === "--duration") {
      out.duration = Number(argv[++i] ?? "30");
    } else if (arg === "--story") {
      out.story = argv[++i] ?? null;
    } else if (arg === "--base-url") {
      out.baseUrl = argv[++i] ?? out.baseUrl;
    } else if (arg === "--help" || arg === "-h") {
      console.log("Usage: npm run capture -- [--story <id>] [--duration <seconds>] [--base-url <url>]");
      process.exit(0);
    }
  }
  return out;
}

async function captureStory(browser, baseUrl, storyId, durationSeconds) {
  const context = await browser.newContext({
    viewport: { width: 1280, height: 720 },
  });
  const page = await context.newPage();
  const url = `${baseUrl}/iframe.html?id=${storyId}&viewMode=story`;
  await page.goto(url);
  await page.waitForLoadState("domcontentloaded");
  await page.waitForSelector("#storybook-root", { state: "attached" });
  // Settle: AccessibilityShell hydration + first R3F frame.
  await page.waitForTimeout(750);

  // Drive canvas.captureStream + MediaRecorder in the page context.
  //
  // Serialization detail: Playwright's page.evaluate bridges return values
  // as JSON-equivalent. ArrayBuffer / Blob / TypedArray do NOT survive — they
  // arrive on the Node side as `{}`. Convert to a plain number array inside
  // the page context; reconstruct as Buffer on the Node side.
  // (Bug found at first real capture run after b3b7f39d; fix landed in this
  // commit before the milestone-anchored capture archive was produced.)
  const byteArray = await page.evaluate(async (durMs) => {
    return await new Promise((resolve, reject) => {
      try {
        const canvas = document.querySelector("canvas");
        if (!canvas || typeof canvas.captureStream !== "function") {
          // No canvas (story is plain DOM). Resolve to an empty array so the
          // output file still exists for completeness.
          resolve([]);
          return;
        }
        const stream = canvas.captureStream(60);
        const chunks = [];
        const rec = new MediaRecorder(stream, {
          mimeType: "video/webm; codecs=vp9",
        });
        rec.ondataavailable = (e) => {
          if (e.data && e.data.size > 0) chunks.push(e.data);
        };
        rec.onstop = async () => {
          const blob = new Blob(chunks, { type: "video/webm" });
          const ab = await blob.arrayBuffer();
          // Number-array serializes across Playwright's bridge cleanly;
          // Buffer.from(numberArray) reconstructs on the Node side.
          resolve(Array.from(new Uint8Array(ab)));
        };
        rec.onerror = (e) => reject(e);
        rec.start();
        setTimeout(() => rec.stop(), durMs);
      } catch (err) {
        reject(err);
      }
    });
  }, durationSeconds * 1000);

  await context.close();
  return Buffer.from(byteArray);
}

async function main() {
  const args = parseArgs(process.argv);
  const stories = args.story ? [args.story] : STORIES;
  await mkdir(CAPTURE_DIR, { recursive: true });
  console.log(`capture.mjs — capturing ${stories.length} stor${stories.length === 1 ? "y" : "ies"}, ${args.duration}s each`);
  console.log(`base url: ${args.baseUrl}`);
  console.log(`output:   ${CAPTURE_DIR}`);

  // Headless Chromium needs explicit software GL for canvas.captureStream
  // to yield frames. Without these flags, WebGL contexts initialize but
  // never produce captureable frames; output WebM ends up as a zero-frame
  // container header (~110 B) regardless of duration. swiftshader is
  // bundled with Chromium and works without GPU drivers.
  const browser = await chromium.launch({
    headless: true,
    args: [
      "--use-gl=swiftshader",
      "--use-angle=swiftshader",
      "--enable-unsafe-swiftshader",
    ],
  });
  try {
    for (const story of stories) {
      const start = Date.now();
      const buf = await captureStory(browser, args.baseUrl, story, args.duration);
      const outPath = join(CAPTURE_DIR, `${story}.webm`);
      await writeFile(outPath, buf);
      const sec = ((Date.now() - start) / 1000).toFixed(1);
      console.log(`  ${story}: ${(buf.length / 1024).toFixed(1)} KB (${sec}s)`);
    }
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
