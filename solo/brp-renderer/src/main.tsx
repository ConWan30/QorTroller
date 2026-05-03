// Vite dev entry — out-of-band-solo dev surface.
//
// Track classification: out-of-band-solo. This file is the local browser
// development entry point only. The integration ceremony does NOT consume
// main.tsx — the protocol monorepo's apps/gamer-portal/ build is the eventual
// production entry; this file is the renderer's standalone dev harness.
//
// 4b mounts <BrpCanvas /> inside <AccessibilityShell /> with a deterministic
// 32-zero-byte frozenOutput. The locked seed (0x87b0f938 per
// deriveBrpSeed.test.ts canonical-vector lock) is what the dev surface
// visualizes — every reload produces the same 64-instance ambient mesh,
// so the operator can verify the seed→visual chain by eye.

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AccessibilityShell } from "./components/AccessibilityShell";
import { BrpCanvas } from "./components/BrpCanvas";

const rootEl = document.getElementById("root");
if (!rootEl) {
  throw new Error("missing #root element in index.html");
}

// Canonical 32-zero-byte demo input. Locked seed per
// deriveBrpSeed.test.ts: 0x87b0f938.
const DEMO_FROZEN_OUTPUT = new Uint8Array(32);

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
        <code>0x87b0f938</code> (32-zero-byte canonical vector). See{" "}
        <code>solo/brp-renderer/README.md</code>.
      </header>
      <main style={{ flex: 1, position: "relative" }}>
        <AccessibilityShell>
          <BrpCanvas frozenOutput={DEMO_FROZEN_OUTPUT} />
        </AccessibilityShell>
      </main>
    </div>
  </StrictMode>,
);
