// PerfOverlay — dev-only drei <PerformanceMonitor> wrapper.
//
// Track classification: out-of-band-solo. NOT Phase 241. NOT in the sequential
// VAPI protocol chain.
//
// Renders only when `import.meta.env.DEV === true`. In production builds, Vite
// statically tree-shakes the body and this component returns null. Per design
// PDF §"Performance budget" the renderer's adaptive DPR scaling target is
// 1.0–1.75 with onIncline / onDecline thresholds.
//
// 4d ships PerfOverlay as the named tooling component for Storybook stories
// (BrpCanvas.stories.tsx WithPerfOverlay variant + future dev-mode debugging).
// Component testability via jsdom is via mocking @react-three/drei's
// PerformanceMonitor; the live drei behavior (onIncline/onDecline callbacks
// firing on real frame budget breaches) is observable only in real-browser
// Storybook.

import { useState } from "react";
import { PerformanceMonitor } from "@react-three/drei";

export interface PerfOverlayProps {
  readonly children?: React.ReactNode;
  /** Lower bound for adaptive DPR scaling. Default 1.0. */
  readonly minFactor?: number;
  /** Upper bound for adaptive DPR scaling. Default 1.75 per PDF. */
  readonly maxFactor?: number;
}

export function PerfOverlay({
  children,
  minFactor = 1.0,
  maxFactor = 1.75,
}: PerfOverlayProps): JSX.Element | null {
  // Production builds short-circuit. Vite tree-shakes the body when DEV=false.
  if (!import.meta.env.DEV) {
    return null;
  }

  // eslint-disable-next-line react-hooks/rules-of-hooks
  const [factor, setFactor] = useState<number>(1.0);

  return (
    <PerformanceMonitor
      bounds={() => [minFactor, maxFactor]}
      onIncline={(api) => {
        setFactor(Math.min(maxFactor, api.factor));
      }}
      onDecline={(api) => {
        setFactor(Math.max(minFactor, api.factor));
      }}
    >
      <span
        // DOM-attribute carrier for tests. data-perf-factor is what the
        // component-test asserts on. R3F ignores DOM elements inside
        // PerformanceMonitor (the inner content is the scene), so the
        // span has no visual effect when used inside an R3F tree; in
        // mocked test contexts the span renders normally.
        style={{ display: "none" }}
        data-perf-factor={factor.toFixed(3)}
        data-brp-perf-overlay="true"
      />
      {children}
    </PerformanceMonitor>
  );
}
