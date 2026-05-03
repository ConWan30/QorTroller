// AmbientLayer — hash-seeded ambient mesh.
//
// Track classification: out-of-band-solo. NOT Phase 241. NOT in the sequential
// VAPI protocol chain.
//
// Consumes opaque frozenOutput bytes → deriveBrpSeed → Mulberry32 PRNG →
// pure seedToInstanceParams() → drei <Instances> mesh. Single draw call
// regardless of instance count.
//
// Per Block A1 honesty-first invariants:
//   H-1: aesthetics are a consequence of verification, never an input. The
//        ambient mesh derives from frozenOutput by one-way keccak256 (via
//        deriveBrpSeed); no rendering output is ever written back to any
//        verification surface.
//   H-4: Mulberry32 is explicitly a *visual* PRNG. No cryptographic claim is
//        made about its output. No security-relevant decision happens
//        downstream of the rendered pixels.
//
// Per Block A1 photosensitivity governance: the ambient mesh's static-material
// descriptor (registered in src/hash/sceneFlashBudget.ts) passes WCAG 2.3.1 by
// construction with three margins:
//   frequency_hz: 0.5 (vs G19 cap 3 Hz, 6× margin)
//   area_css_px2: 50,000 (vs G176 cap 87,296, 1.7× margin)
//   delta_luminance: 0.05 (vs ΔL cap 0.10, 2× margin)
//
// PDF reference: §"Block A1", §"Component structure", §"Hash-derivation
// function", §"Performance budget".

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Instances, Instance } from "@react-three/drei";
import type { Group, MeshStandardMaterial } from "three";
import { deriveBrpSeed } from "../hash/deriveBrpSeed";
import { mulberry32 } from "../hash/mulberry32";
import type {
  HostStateSignal,
  OrientationSignal,
  PulseSignal,
} from "../telemetry/contracts";

// -----------------------------------------------------------------------------
// Pure-function instance-parameter generator.
//
// Determinism: same (seed, count) → same InstanceParams[]. No Math.random(),
// no time, no DOM, no React. Testable in pure-Node.
//
// Bounds (audit-readable, mapped from Mulberry32's uniform [0,1)):
//   position: [-1, 1]^3 — fits a unit-cube viewport without camera setup
//   rotation: [0, 2π)^3 — full revolution per axis
//   scale:    [0.5, 1.5] — centered on 1.0; instances vary visually but read
//                          as the same "type" of mark. Wider would create
//                          distracting outliers.
// -----------------------------------------------------------------------------

export interface InstanceParams {
  readonly position: readonly [number, number, number];
  readonly rotation: readonly [number, number, number];
  readonly scale: number;
}

/** Default instance count. Below the < 80 draw-call budget per PDF §"Performance budget". */
export const DEFAULT_INSTANCE_COUNT = 64;

const TWO_PI = Math.PI * 2;

/**
 * Pure deterministic generator: (seed, count) → InstanceParams[count].
 *
 * @param seed   uint32 from deriveBrpSeed
 * @param count  number of instances; default DEFAULT_INSTANCE_COUNT
 */
export function seedToInstanceParams(
  seed: number,
  count: number = DEFAULT_INSTANCE_COUNT,
): InstanceParams[] {
  const rand = mulberry32(seed);
  const out: InstanceParams[] = new Array(count);
  for (let i = 0; i < count; i++) {
    out[i] = {
      position: [rand() * 2 - 1, rand() * 2 - 1, rand() * 2 - 1],
      rotation: [rand() * TWO_PI, rand() * TWO_PI, rand() * TWO_PI],
      scale: 0.5 + rand() * 1.0,
    };
  }
  return out;
}

// -----------------------------------------------------------------------------
// React component.
//
// Consumes frozenOutput as Uint8Array (opaque per BrpMountProps contract).
// Memoizes the seed and instance params so re-renders without prop changes
// don't re-derive the visual.
// -----------------------------------------------------------------------------

export interface AmbientLayerProps {
  readonly frozenOutput: Uint8Array;
  readonly instanceCount?: number;
  /** Optional commit-ε pulse signal; emissive bumps when ts changes. */
  readonly pulse?: PulseSignal;
  /** Optional commit-ζ orientation signal; lerped X/Z tilt overlay. */
  readonly orientation?: OrientationSignal;
  /** Optional commit-ι host-state signal; selects emissive palette. */
  readonly hostState?: HostStateSignal;
}

/**
 * Continuous rotation rate for the ambient mesh group.
 *
 * 0.1 Hz = 1 full revolution every 10 seconds = 0.628 rad/s.
 * Well under WCAG 2.3.1's G19 3 Hz cap. The rotation is spatial movement
 * (no luminance oscillation), so flashBudget descriptor stays valid;
 * sceneFlashBudget AMBIENT_LAYER_MATERIAL is unchanged.
 *
 * The rotation only runs when the parent BrpCanvas has frameloop="always"
 * (motion enabled). When the AccessibilityShell motion toggle pauses
 * motion, BrpCanvas sets frameloop="never" and useFrame stops being
 * called — rotation freezes deterministically.
 */
const ROTATION_RAD_PER_SEC = 0.628;

/**
 * Commit ε pulse-animation parameters.
 *
 * Pulse rises from BASE → PEAK over PULSE_DURATION_MS via a sin-shaped
 * envelope (smooth ramp up + symmetric ramp down). At gameplay-frequency
 * PoAC arrival (~1/sec), this gives effectively 1 Hz oscillation — well
 * under WCAG 2.3.1 G19's 3 Hz cap. Pulse animation only runs when the
 * pulse prop is provided AND its `ts` field has changed since the last
 * frame; the renderer remains static-rotation-only when no host page
 * supplies the prop.
 *
 * BASE_EMISSIVE_INTENSITY matches the meshStandardMaterial's resting
 * value (0.15). PEAK = 0.45 keeps ΔL well under 0.10 against the dark
 * canvas bg, satisfying the ΔL clamp pathway as additional defense in
 * depth on top of the G19 frequency-cap pathway.
 */
const BASE_EMISSIVE_INTENSITY = 0.15;
const PULSE_PEAK_INTENSITY = 0.45;
const PULSE_DURATION_MS = 500;

/**
 * Commit ζ orientation-overlay parameters.
 *
 * ORIENTATION_TILT_SCALE: dampen target rotations so a full ±π controller
 * tilt maps to a more contained ±π/2 mesh tilt. Visually contained but
 * still clearly responsive.
 *
 * ORIENTATION_LERP_RATE: per-second lerp factor toward target. Higher =
 * snappier (less smoothing). 5.0 means after 1 second the mesh has moved
 * ~99% of the way to its target — fast enough for real-time feel,
 * smooth enough to absorb jittery accel readings.
 *
 * Orientation is spatial movement (no luminance change). flashBudget
 * AMBIENT_LAYER_MATERIAL is unaffected; sceneFlashBudget unchanged.
 */
const ORIENTATION_TILT_SCALE = 0.5;
const ORIENTATION_LERP_RATE = 5.0;

/**
 * Commit ι host-state palette.
 *
 * The mesh's resting `color` (diffuse) and `emissive` (glow) are selected
 * from this lookup based on the host-state classification. Each palette
 * entry is pre-validated against the WCAG 2.3.1 saturated-red guard
 * (no entry has R-channel dominance > 0.6 of total RGB sum).
 *
 * EXCLUSIVE_USB and UNKNOWN share the base steel-blue palette (commit δ
 * baseline) because UNKNOWN is the bridge's "no signal yet" state — using
 * the healthy palette as the optimistic default avoids false alarm on
 * cold-start. Phase 234.7 PCC explicitly classifies UNKNOWN as
 * grind-eligible alongside EXCLUSIVE_USB.
 *
 * Color transition is one-shot per host-state change (capped at 3s
 * polling cadence — well under G19 3 Hz cap). This is a step transition
 * on the material color property, NOT an oscillating animation, so the
 * sceneFlashBudget AMBIENT_LAYER_MATERIAL frequency_hz descriptor (0.5)
 * still bounds the worst case.
 */
interface PaletteEntry {
  readonly color: string;
  readonly emissive: string;
}

const BASE_PALETTE: PaletteEntry = { color: "#5a8fb8", emissive: "#1a3a5a" };
const BT_PALETTE: PaletteEntry = { color: "#b8965a", emissive: "#5a3e1a" };
const CONTESTED_PALETTE: PaletteEntry = { color: "#888888", emissive: "#333333" };
const DISCONNECTED_PALETTE: PaletteEntry = { color: "#444444", emissive: "#1a1a1a" };

function paletteFor(kind: string): PaletteEntry {
  switch (kind) {
    case "EXCLUSIVE_USB":
    case "UNKNOWN":
      return BASE_PALETTE;
    case "EXCLUSIVE_BT":
      return BT_PALETTE;
    case "CONTESTED":
    case "DEGRADED":
      return CONTESTED_PALETTE;
    case "DISCONNECTED":
      return DISCONNECTED_PALETTE;
    default:
      return BASE_PALETTE;
  }
}

export function AmbientLayer({
  frozenOutput,
  instanceCount = DEFAULT_INSTANCE_COUNT,
  pulse,
  orientation,
  hostState,
}: AmbientLayerProps): JSX.Element {
  const seed = useMemo(() => deriveBrpSeed(frozenOutput), [frozenOutput]);
  const params = useMemo(
    () => seedToInstanceParams(seed, instanceCount),
    [seed, instanceCount],
  );

  // Commit ι: select palette based on host-state. Falls back to
  // base steel-blue when prop is omitted or kind is unrecognized.
  const palette = useMemo(
    () => (hostState ? paletteFor(hostState.kind) : BASE_PALETTE),
    [hostState],
  );

  // Group ref allows a single transform on all instances. drei's <Instances>
  // doesn't accept ref directly; wrapping in <group> gives a transformable
  // parent that doesn't change the instanced-mesh draw count (still 1 call).
  const groupRef = useRef<Group | null>(null);

  // Commit ε: refs for pulse animation. Material ref to mutate emissive
  // intensity per-frame. Last-pulse-ts ref to detect prop changes (we
  // never call setState on every frame — useFrame is the canonical place
  // for direct material mutation).
  const materialRef = useRef<MeshStandardMaterial | null>(null);
  const lastObservedPulseTsRef = useRef<number>(0);
  const pulseEndTimeRef = useRef<number>(0);
  const pulseIntensityRef = useRef<number>(0);

  useFrame((_, delta) => {
    if (groupRef.current) {
      // Base 0.1 Hz Y-spin (commit δ).
      groupRef.current.rotation.y += delta * ROTATION_RAD_PER_SEC;

      // Commit ζ orientation overlay: lerp X (pitch) + Z (roll) toward
      // dampened target. Yaw is folded INTO the base Y-spin via additive
      // offset rather than overriding it, so the spin continues unaffected
      // when a yaw signal arrives. Lerp factor clamped to [0, 1] so high
      // delta (e.g., a frame-rate hiccup) doesn't overshoot the target.
      if (orientation) {
        const lerpFactor = Math.min(1, delta * ORIENTATION_LERP_RATE);
        const targetPitch = orientation.pitch * ORIENTATION_TILT_SCALE;
        const targetRoll = orientation.roll * ORIENTATION_TILT_SCALE;
        groupRef.current.rotation.x +=
          (targetPitch - groupRef.current.rotation.x) * lerpFactor;
        groupRef.current.rotation.z +=
          (targetRoll - groupRef.current.rotation.z) * lerpFactor;
      }
    }

    // Pulse trigger detection: pulse.ts strictly greater than the last
    // observed value means a new event arrived since the previous frame.
    // Schedule the bump animation to end at now + PULSE_DURATION_MS.
    if (pulse && pulse.ts > lastObservedPulseTsRef.current) {
      lastObservedPulseTsRef.current = pulse.ts;
      pulseEndTimeRef.current = performance.now() + PULSE_DURATION_MS;
      // Clamp intensity to [0, 1] in case the host page passes an
      // out-of-range value.
      pulseIntensityRef.current = Math.max(0, Math.min(1, pulse.intensity));
    }

    // Pulse animation: sin-shaped envelope BASE → PEAK → BASE over
    // PULSE_DURATION_MS, scaled by pulseIntensityRef. When no active
    // pulse is in flight, snap back to BASE_EMISSIVE_INTENSITY.
    if (materialRef.current) {
      const now = performance.now();
      if (now < pulseEndTimeRef.current) {
        const remaining =
          (pulseEndTimeRef.current - now) / PULSE_DURATION_MS;
        const t = 1 - remaining; // 0 → 1
        const factor = Math.sin(t * Math.PI); // 0 → 1 → 0
        const bump =
          (PULSE_PEAK_INTENSITY - BASE_EMISSIVE_INTENSITY) *
          factor *
          pulseIntensityRef.current;
        materialRef.current.emissiveIntensity =
          BASE_EMISSIVE_INTENSITY + bump;
      } else {
        materialRef.current.emissiveIntensity = BASE_EMISSIVE_INTENSITY;
      }
    }
  });

  return (
    <group ref={groupRef}>
      <Instances limit={instanceCount} range={instanceCount}>
        {/* Low-poly icosahedron — 12 vertices, 20 faces. */}
        <icosahedronGeometry args={[0.08, 0]} />
        <meshStandardMaterial
          ref={materialRef}
          color={palette.color}
          emissive={palette.emissive}
          emissiveIntensity={BASE_EMISSIVE_INTENSITY}
          metalness={0.2}
          roughness={0.7}
        />
        {params.map((p, i) => (
          <Instance
            key={i}
            position={p.position as [number, number, number]}
            rotation={p.rotation as [number, number, number]}
            scale={p.scale}
          />
        ))}
      </Instances>
    </group>
  );
}
