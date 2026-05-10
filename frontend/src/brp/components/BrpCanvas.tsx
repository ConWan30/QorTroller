// BrpCanvas — R3F Canvas wrapper.
//
// Track classification: out-of-band-solo. NOT Phase 241. NOT in the sequential
// VAPI protocol chain.
//
// Wraps @react-three/fiber's Canvas with three pieces of contract:
//
//   1. role="presentation" + aria-hidden="true" on the Canvas root per Block X
//      (PITL row coexistence) and Block A1 (accessibility surface). The mesh
//      is decorative; AccessibilityShell's sr-only sibling provides the
//      AT-readable description. INV-BRP-5 (draft) enforces this at ceremony.
//
//   2. frameloop bound to AccessibilityShell's motion-context:
//        motionShouldPause === true  → frameloop="never"
//        motionShouldPause === false → frameloop="always"
//      Originally "demand" (PDF §"Performance budget" — on-demand "saves
//      battery and keeps noisy fans in check"). Switched to "always" in
//      commit δ to support AmbientLayer's continuous useFrame rotation
//      (0.1 Hz, well under G19 3 Hz cap). Battery cost is opt-out via
//      the WCAG 2.2.2 photosensitivity toggle, which remains the user's
//      mechanism for halting render entirely (frameloop=never).
//
//   3. data-live="false" on the Canvas wrapper. Block W contract.
//
// Per design Decision D2 (mount-agnostic), the host page wires frozenOutput
// in and the renderer treats it as opaque.
//
// PDF reference: §"Block W", §"Block A1", §"Block X", §"Performance budget".

import { Canvas } from "@react-three/fiber";
import { useMotionContext } from "./AccessibilityShell";
import { AmbientLayer } from "./AmbientLayer";
import { ApopEvidenceRays } from "./ApopEvidenceRays";
import type { ApopSignal } from "./ApopEvidenceRays";
import type {
  HostStateSignal,
  OrientationSignal,
  PulseSignal,
  TrustSignal,
} from "../telemetry/contracts";

/**
 * Pure helper: mode mapping. Extracted as a named export so unit tests can
 * verify the semantic contract without rendering R3F.
 *
 * Returns "always" when motion is enabled — required by AmbientLayer's
 * useFrame rotation hook (commit δ). Returns "never" when paused —
 * deterministically stops all rendering, including the rotation.
 */
export function computeFrameloop(motionShouldPause: boolean): "always" | "never" {
  return motionShouldPause ? "never" : "always";
}

export interface BrpCanvasProps {
  readonly frozenOutput: Uint8Array;
  readonly instanceCount?: number;
  /** Optional commit-ε pulse signal threaded through to AmbientLayer. */
  readonly pulse?: PulseSignal;
  /** Optional commit-ζ orientation signal threaded through to AmbientLayer. */
  readonly orientation?: OrientationSignal;
  /** Optional commit-ι host-state signal threaded through to AmbientLayer. */
  readonly hostState?: HostStateSignal;
  /** Optional commit-λ trust signal threaded through to AmbientLayer. */
  readonly trust?: TrustSignal;
  /** Phase 241-APOP active play occupancy signal — drives Evidence Rays. */
  readonly apop?: ApopSignal;
}

export function BrpCanvas({
  frozenOutput,
  instanceCount,
  pulse,
  orientation,
  hostState,
  trust,
  apop,
}: BrpCanvasProps): JSX.Element {
  const { motionShouldPause } = useMotionContext();
  const frameloop = computeFrameloop(motionShouldPause);

  return (
    <div
      data-testid="brp-canvas-wrapper"
      data-brp-canvas="true"
      data-live="false"
      data-frameloop={frameloop}
      style={{ width: "100%", height: "100%" }}
    >
      <Canvas
        frameloop={frameloop}
        role="presentation"
        aria-hidden="true"
        camera={{ position: [0, 0, 4.5], fov: 55 }}
        gl={{ antialias: true, alpha: true }}
      >
        <ambientLight intensity={0.5} />
        <directionalLight position={[2, 2, 2]} intensity={0.8} />
        <AmbientLayer
          frozenOutput={frozenOutput}
          {...(instanceCount !== undefined ? { instanceCount } : {})}
          {...(pulse ? { pulse } : {})}
          {...(orientation ? { orientation } : {})}
          {...(hostState ? { hostState } : {})}
          {...(trust ? { trust } : {})}
        />
        {/* Phase 241-APOP — 3D Evidence Rays.  Hidden when no apop or no
            state yet (renders null). When live, five cones radiate from
            origin, lengths driven by per-axis scores, color by APOP state. */}
        <ApopEvidenceRays {...(apop ? { apop } : {})} />
      </Canvas>
    </div>
  );
}
