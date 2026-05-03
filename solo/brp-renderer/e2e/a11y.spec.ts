// axe-core smoke per Storybook story.
//
// Track classification: out-of-band-solo. NOT Phase 241. NOT in the sequential
// VAPI protocol chain.
//
// Per design PDF §A1: WCAG 2.3.1 conformance is proven by construction
// (G19/G176/ΔL static analyzer), not by tool. axe-core is defense-in-depth.
// No rules are preemptively disabled; if a real violation surfaces that
// conflicts with the design contract (e.g., Block A1's decorative-canvas
// decision), the specific axe rule name is added to DISABLED_RULES with a
// commit-message-grade justification. Empty list = trust the standard.

import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

interface StoryEntry {
  readonly id: string;
  readonly title: string;
}

// Storybook 8 exposes /index.json with story metadata at storybook-static root.
// Each entry is `${kind}--${name}` lowercased and slugified.
const STORIES: readonly StoryEntry[] = [
  // AccessibilityShell (4)
  { id: "brp-accessibilityshell--default", title: "AccessibilityShell/Default" },
  { id: "brp-accessibilityshell--with-reduced-motion-os-pref", title: "AccessibilityShell/WithReducedMotionOSPref" },
  { id: "brp-accessibilityshell--with-user-motion-toggle-off", title: "AccessibilityShell/WithUserMotionToggleOff" },
  { id: "brp-accessibilityshell--with-both-on-and-off", title: "AccessibilityShell/WithBothOnAndOff" },
  // AmbientLayer (4)
  { id: "brp-ambientlayer--default-seed", title: "AmbientLayer/DefaultSeed" },
  { id: "brp-ambientlayer--non-deterministic-seed", title: "AmbientLayer/NonDeterministicSeed" },
  { id: "brp-ambientlayer--count-16", title: "AmbientLayer/Count16" },
  { id: "brp-ambientlayer--count-256", title: "AmbientLayer/Count256" },
  // BrpCanvas (4)
  { id: "brp-brpcanvas--default", title: "BrpCanvas/Default" },
  { id: "brp-brpcanvas--frameloop-never", title: "BrpCanvas/FrameloopNever" },
  { id: "brp-brpcanvas--count-16", title: "BrpCanvas/Count16" },
  { id: "brp-brpcanvas--non-deterministic-seed", title: "BrpCanvas/NonDeterministicSeed" },
  // LegibilityOverlay (4)
  { id: "brp-legibilityoverlay--ambient-mode", title: "LegibilityOverlay/AmbientMode" },
  { id: "brp-legibilityoverlay--active-aid-mode", title: "LegibilityOverlay/ActiveAidMode" },
  { id: "brp-legibilityoverlay--all-rows-active", title: "LegibilityOverlay/AllRowsActive" },
  { id: "brp-legibilityoverlay--with-reduced-motion", title: "LegibilityOverlay/WithReducedMotion" },
  // BrpMount (5) — design PDF §A1 mandated states
  { id: "brp-brpmount--default-dev-surface", title: "BrpMount/DefaultDevSurface" },
  { id: "brp-brpmount--enrollment-eligible", title: "BrpMount/EnrollmentEligible" },
  { id: "brp-brpmount--enrollment-credentialed", title: "BrpMount/EnrollmentCredentialed" },
  { id: "brp-brpmount--telemetry-degraded", title: "BrpMount/TelemetryDegraded" },
  { id: "brp-brpmount--full-active-aid", title: "BrpMount/FullActiveAid" },
];

// Rules disabled by design contract. Currently empty — axe-core's standard
// rule set runs in full. If a violation surfaces that conflicts with a
// design-PDF decision, the specific axe rule name is added here with a
// justification comment.
const DISABLED_RULES: readonly string[] = [];

test.describe("axe-core a11y smoke per Storybook story", () => {
  test("meta: disabled-rules list is empty (no preemptive disables)", () => {
    expect(DISABLED_RULES).toEqual([]);
  });

  for (const story of STORIES) {
    test(`${story.title} — zero a11y violations on non-canvas chrome`, async ({
      page,
    }) => {
      // Storybook 8: /iframe.html?id=<story-id>&viewMode=story renders the story
      // standalone (without the Storybook UI chrome).
      await page.goto(`/iframe.html?id=${story.id}&viewMode=story`);
      // R3F-rendering stories never hit `networkidle` because the R3F frame
      // loop keeps the page busy. Wait for DOM ready + the Storybook root
      // element to be present + a brief settle for component mount.
      await page.waitForLoadState("domcontentloaded");
      await page.waitForSelector("#storybook-root", { state: "attached", timeout: 10_000 });
      // Brief settle for first-frame R3F mount + AccessibilityShell hydration.
      await page.waitForTimeout(500);

      // Scope axe to Storybook's content wrapper #storybook-root rather than
      // the whole document. The iframe chrome (html/body/etc.) belongs to
      // Storybook's host page, not the BRP renderer; rules like
      // `landmark-one-main` and `region` would otherwise fire on Storybook
      // iframe artifacts that the integration ceremony's actual host page
      // (apps/gamer-portal/) is responsible for resolving, NOT the BRP
      // renderer. Per design PDF §"Accessibility conformance approach":
      // axe-core runs on the host page chrome with the WebGL canvas
      // documented decorative; this `#storybook-root` scope is the dev-time
      // analog — axe checks the actual rendered story, not Storybook's UI.
      const builder = new AxeBuilder({ page }).include("#storybook-root");
      for (const rule of DISABLED_RULES) {
        builder.disableRules([rule]);
      }
      const results = await builder.analyze();

      if (results.violations.length > 0) {
        // Surface the violations in the failure output for honesty-first debug.
        // eslint-disable-next-line no-console
        console.error(
          `axe violations for ${story.title}:\n` +
            results.violations
              .map((v) => `  - ${v.id}: ${v.help}`)
              .join("\n"),
        );
      }
      expect(results.violations).toEqual([]);
    });
  }
});
