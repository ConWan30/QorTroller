// Vite dev entry — out-of-band-solo dev surface.
//
// Track classification: out-of-band-solo. This file is the local browser
// development entry point only. The integration ceremony does NOT consume
// main.tsx — the protocol monorepo's apps/gamer-portal/ build is the eventual
// production entry; this file is the renderer's standalone dev harness.
//
// 4c mounts <BrpMount /> with synthetic fixture data:
//   frozenOutput      — 32-zero-byte canonical vector (locked seed 0x87b0f938)
//   pitlSnapshot      — getMockPitlSnapshot() (7 PITL rows, deterministic)
//   enrollmentSession — getMockEnrollmentSession() (status="pending", 7/10)
//   aidThreshold      — 0.65 (placeholder per Block Z, ceremony picks)
//   liveness          — all false (default until ceremony confirms upstream)
//
// Reload the dev surface (`npm run dev`) to verify deterministic seed→visual
// chain plus the calibration-aid HUD rendering against the fixture.

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrpMount } from "./components/BrpMount";
import {
  getMockEnrollmentSession,
  getMockPitlSnapshot,
} from "./mocks/loaders";
import type { BrpMountProps } from "./telemetry/contracts";

const rootEl = document.getElementById("root");
if (!rootEl) {
  throw new Error("missing #root element in index.html");
}

// Canonical 32-zero-byte demo input. Locked seed per
// deriveBrpSeed.test.ts: 0x87b0f938.
const DEMO_FROZEN_OUTPUT = new Uint8Array(32);

const DEV_PROPS: BrpMountProps = {
  frozenOutput: DEMO_FROZEN_OUTPUT,
  pitlSnapshot: getMockPitlSnapshot(),
  enrollmentSession: getMockEnrollmentSession(),
  aidThreshold: 0.65,
  liveness: { ambient: false, legibility: false, telemetry: false },
};

createRoot(rootEl).render(
  <StrictMode>
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "#0a0e14",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <header
        style={{
          padding: "0.75rem 1rem",
          fontFamily: "system-ui, -apple-system, sans-serif",
          fontSize: "0.85rem",
          color: "#aab",
          background: "#0c1320",
          borderBottom: "1px solid #1a2030",
        }}
      >
        BRP Renderer — out-of-band-solo dev surface. live:false. seed=
        <code>0x87b0f938</code> (32-zero-byte canonical vector). Fixture data
        from <code>src/mocks/fixtures/</code>. See{" "}
        <code>solo/brp-renderer/README.md</code>.
      </header>
      <main style={{ flex: 1, position: "relative" }}>
        <BrpMount {...DEV_PROPS} />
      </main>
    </div>
  </StrictMode>,
);
