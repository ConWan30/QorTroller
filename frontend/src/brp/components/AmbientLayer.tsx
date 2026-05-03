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

import { useMemo } from "react";
import { Instances, Instance } from "@react-three/drei";
import { deriveBrpSeed } from "../hash/deriveBrpSeed";
import { mulberry32 } from "../hash/mulberry32";

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
}

export function AmbientLayer({
  frozenOutput,
  instanceCount = DEFAULT_INSTANCE_COUNT,
}: AmbientLayerProps): JSX.Element {
  const seed = useMemo(() => deriveBrpSeed(frozenOutput), [frozenOutput]);
  const params = useMemo(
    () => seedToInstanceParams(seed, instanceCount),
    [seed, instanceCount],
  );

  return (
    <Instances limit={instanceCount} range={instanceCount}>
      {/* Low-poly icosahedron — 12 vertices, 20 faces. */}
      <icosahedronGeometry args={[0.04, 0]} />
      <meshStandardMaterial
        color="#5a8fb8"
        emissive="#1a3a5a"
        emissiveIntensity={0.15}
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
  );
}
