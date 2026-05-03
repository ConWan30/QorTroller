// Playwright config — runs axe-core smoke against built Storybook.
//
// Track classification: out-of-band-solo. NOT Phase 241. NOT in the sequential
// VAPI protocol chain.
//
// Strategy: build Storybook to storybook-static/, serve via http-server on
// port 6006, run Chromium-only Playwright tests against it. CI deferred to
// integration ceremony per OQ-5; this config is local-only.

import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  fullyParallel: true,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://localhost:6006",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "npx http-server storybook-static -p 6006 -s",
    url: "http://localhost:6006",
    reuseExistingServer: !process.env["CI"],
    timeout: 30_000,
  },
});
