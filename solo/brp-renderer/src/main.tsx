// Vite dev entry — out-of-band-solo dev surface.
//
// Track classification: out-of-band-solo. This file is the local browser
// development entry point only. The integration ceremony does NOT consume
// main.tsx — the protocol monorepo's apps/gamer-portal/ build is the eventual
// production entry; this file is the renderer's standalone dev harness.
//
// 4a ships the AccessibilityShell wrapping a placeholder text block so the
// shell wiring, prop contract, and tsx build pipeline are end-to-end testable
// in a real browser via `npm run dev`. The R3F canvas surface arrives in 4b.

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AccessibilityShell } from "./components/AccessibilityShell";

const rootEl = document.getElementById("root");
if (!rootEl) {
  throw new Error("missing #root element in index.html");
}

createRoot(rootEl).render(
  <StrictMode>
    <AccessibilityShell>
      <div
        style={{
          padding: "1rem",
          fontFamily: "system-ui, -apple-system, sans-serif",
          maxWidth: "60ch",
          lineHeight: 1.5,
        }}
      >
        <h1 style={{ fontSize: "1.25rem", marginBottom: "0.5rem" }}>
          BRP Renderer — dev surface
        </h1>
        <p>
          Track classification: <strong>out-of-band-solo</strong>. This is the
          standalone dev harness for the BRP renderer. No R3F canvas mounts at
          this commit (4a); the canvas surface arrives in 4b. See{" "}
          <code>solo/brp-renderer/README.md</code> for per-commit scope.
        </p>
        <p>
          The visible "Motion: ON / OFF" button above is the WCAG 2.2.2
          photosensitivity-safety mechanism. The shell&apos;s root carries{" "}
          <code>role=&quot;presentation&quot;</code> +{" "}
          <code>data-live=&quot;false&quot;</code>. Both invariants are
          asserted by{" "}
          <code>src/components/__tests__/AccessibilityShell.test.tsx</code>.
        </p>
      </div>
    </AccessibilityShell>
  </StrictMode>,
);
