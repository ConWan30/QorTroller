/**
 * ApopEvidenceRays — Phase 241-APOP 3D evidence visualization.
 *
 * Five cone meshes radiating from the scene origin, one per APOP scoring
 * axis. Each cone's LENGTH is proportional to its raw score (0..1) and its
 * BASE WIDTH is proportional to that axis's FROZEN INV-APOP-002 weight
 * (0.35 stick / 0.20 button / 0.20 trigger / 0.15 imu / 0.10 physiology).
 *
 * Color is the active APOP state color (cyan ACTIVE_MATCH_PLAY, green
 * COMPETITIVE_CONTROL, t2 MATCH_TRANSITION, red NON_COMPETITIVE_MENU,
 * t3 UNKNOWN_LOW_EVIDENCE). Emissive intensity scales with score so high-
 * evidence axes glow more brightly.
 *
 * The whole group rotates slowly so the prism reads as a 3D form rather
 * than a flat fan — readability without distracting motion.
 *
 * Returns null when apop is undefined or apop.state is null (no
 * fabrication; honest empty state matching the 2D EvidencePrism).
 */

import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import type { Group } from "three";

export interface ApopEvidence {
  readonly stick_score?: number;
  readonly button_score?: number;
  readonly trigger_score?: number;
  readonly imu_score?: number;
  readonly physiology_score?: number;
}

export interface ApopSignal {
  readonly state: string | null;
  readonly score: number;
  readonly confidence: number;
  readonly evidence: ApopEvidence;
}

export interface ApopEvidenceRaysProps {
  readonly apop?: ApopSignal;
}

// Mirrors GAMER palette tokens; kept inline so the BRP src has zero
// imports outside its own subtree (vendored-source discipline).
const STATE_COLOR: Record<string, string> = {
  ACTIVE_MATCH_PLAY:    "#00d4ff",
  COMPETITIVE_CONTROL:  "#00ff88",
  MATCH_TRANSITION:     "#7ab8cc",
  NON_COMPETITIVE_MENU: "#ff3b5c",
  UNKNOWN_LOW_EVIDENCE: "#3a6070",
};

// FROZEN INV-APOP-002 — five axes at fixed weights. base_radius
// scales with weight so the prism's 3D form preserves the protocol's
// classification grain (bigger base = bigger contribution to verdict).
// Angles distribute the rays evenly around the Z axis.
interface Axis {
  readonly key: keyof ApopEvidence;
  readonly weight: number;
  readonly angle: number;
}

const AXES: readonly Axis[] = [
  { key: "stick_score",      weight: 0.35, angle: (Math.PI * 2) * (0 / 5) },
  { key: "button_score",     weight: 0.20, angle: (Math.PI * 2) * (1 / 5) },
  { key: "trigger_score",    weight: 0.20, angle: (Math.PI * 2) * (2 / 5) },
  { key: "imu_score",        weight: 0.15, angle: (Math.PI * 2) * (3 / 5) },
  { key: "physiology_score", weight: 0.10, angle: (Math.PI * 2) * (4 / 5) },
];

function clamp01(x: number): number {
  if (Number.isNaN(x)) return 0;
  if (x < 0) return 0;
  if (x > 1) return 1;
  return x;
}

export function ApopEvidenceRays({
  apop,
}: ApopEvidenceRaysProps): JSX.Element | null {
  const groupRef = useRef<Group>(null);

  useFrame((_state, delta) => {
    if (groupRef.current) {
      // Slow rotation reads as 3D form without distracting motion.
      // Speed scales mildly with APOP score: more competitive = more lively.
      const baseSpeed = 0.05;
      const apopBoost = apop ? apop.score * 0.10 : 0;
      groupRef.current.rotation.z += delta * (baseSpeed + apopBoost);
    }
  });

  if (!apop || !apop.state) return null;

  const stateColor = STATE_COLOR[apop.state] ?? STATE_COLOR.UNKNOWN_LOW_EVIDENCE;

  return (
    <group ref={groupRef} renderOrder={5}>
      {AXES.map((axis) => {
        const rawScore = Number(apop.evidence?.[axis.key] ?? 0);
        const score = clamp01(rawScore);
        // Length range 0.3..1.8: even an axis with score=0 has minimal
        // presence so the prism shape is readable; score=1 reaches well
        // past the icosahedron's resting size.
        const length = 0.3 + score * 1.5;
        // Base radius scales with FROZEN INV-APOP-002 weight × 0.18 so
        // even the lightest axis (physiology, 0.10) has a visible base.
        const baseRadius = 0.018 + axis.weight * 0.18;
        // Cone position is mid-length along the angle so the base is
        // centered at origin and the tip extends outward.
        const x = Math.cos(axis.angle) * (length / 2);
        const y = Math.sin(axis.angle) * (length / 2);
        // Emissive scales with score: 0.4 floor (always visible) up to 2.0.
        const emissiveIntensity = 0.4 + score * 1.6;
        // Opacity scales with score: low evidence stays semi-transparent
        // so high-evidence rays visually dominate.
        const opacity = 0.35 + score * 0.55;
        return (
          <mesh
            key={axis.key}
            position={[x, y, 0]}
            rotation={[0, 0, axis.angle - Math.PI / 2]}
          >
            <coneGeometry args={[baseRadius, length, 16]} />
            <meshStandardMaterial
              color={stateColor}
              emissive={stateColor}
              emissiveIntensity={emissiveIntensity}
              transparent
              opacity={opacity}
              depthWrite={false}
            />
          </mesh>
        );
      })}
    </group>
  );
}
