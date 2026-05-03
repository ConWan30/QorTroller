// TypeScript shapes for the BRP renderer's prop contract.
//
// Track classification: out-of-band-solo. NOT Phase 241. NOT in the sequential
// VAPI protocol chain.
//
// Per Decision D2 (mount-agnostic), the renderer accepts these typed shapes;
// the host page at integration ceremony time wires whichever upstream produces
// matching values. The renderer never imports a fetch URL, never calls a chain
// RPC, never validates upstream provenance — every value is treated as opaque.
//
// Per BACKEND_CONTRACT.md §2 (prop → endpoint mapping), the wiring choices are:
//   frozenOutput        — ceremony-bound to one of five hash-family candidates
//                         (see OPEN_QUESTIONS.md#OQ-1)
//   pitlSnapshot        — ceremony-bound to /dash/api/v1/pitl/timeline OR
//                         composition over /agent/* summaries
//                         (see OPEN_QUESTIONS.md#OQ-2; lean toward /agent/*)
//   enrollmentSession?  — wired to GET /enrollment/status/{device_id}
//   liveness            — manifest-derived for ambient/legibility booleans;
//                         /operator/watchdog-status drives telemetry boolean
//   aidThreshold        — operator-set static; no endpoint
//
// PDF reference: §"Component structure" + §"Telemetry consumption pattern" +
// INTEGRATION_CONTRACT.md "What the O0-integrated VAPI must expose".

// -----------------------------------------------------------------------------
// PITL stack — read-only snapshot per Block X (PITL row coexistence).
//
// The seven-layer PITL stack is canonical authority; the BRP renderer is a
// downstream consumer (per H-7 honesty-first invariant in
// INTEGRATION_CONTRACT.md). The renderer never mutates, reorders, or
// aggregates these rows in a way the verification side could mistake for a
// derived signal.
// -----------------------------------------------------------------------------

/** Layer identifier in the seven-layer PITL stack. */
export type PitlLayer = "L0" | "L1" | "L2" | "L3" | "L4" | "L5" | "L6";

/**
 * One row from the PITL snapshot.
 *
 * `inferenceCode` is an opaque byte value from the PoAC inference table
 * (e.g., 0x20 NOMINAL, 0x28 DRIVER_INJECT, 0x30 BIOMETRIC_ANOMALY). The
 * renderer does not interpret the code — it forwards it to the legibility
 * overlay which chooses presentation.
 */
export interface PitlRow {
  readonly layer: PitlLayer;
  readonly inferenceCode: number;
  readonly active: boolean;
  /** Optional confidence/score in [0, 1]. */
  readonly score?: number;
  /** Optional row-level timestamp in nanoseconds. */
  readonly tsNs?: bigint;
}

/**
 * The full read-only snapshot the renderer consumes.
 *
 * `rows` is an unmodified copy of the seven-layer state at `snapshotTsNs`.
 */
export interface PitlSnapshot {
  readonly rows: readonly PitlRow[];
  readonly snapshotTsNs: bigint;
}

// -----------------------------------------------------------------------------
// Enrollment session — optional, owner deferred per Block V.
//
// The renderer ships the calibration-legibility overlay as a passive consumer
// of this prop with a fully-typed shape, but does not bind whether the overlay
// is owned by the Twin route, the Operator-series guardian agent, or a separate
// enrollment shell. The integration ceremony picks the owner; this type is the
// contract regardless of who owns it.
// -----------------------------------------------------------------------------

export type EnrollmentStatus =
  | "pending"
  | "eligible"
  | "minting"
  | "credentialed"
  | "failed";

export interface EnrollmentSession {
  readonly deviceId: string;
  readonly sessionsNominal: number;
  readonly avgHumanity: number;
  readonly status: EnrollmentStatus;
  readonly requiredSessions: number;
  readonly requiredHumanity: number;
}

// -----------------------------------------------------------------------------
// Liveness flags — drives the data-live attribute and visible badge.
//
// Per Block W honesty-first contract: every BRP-rendered surface declares its
// `live` state truthfully. A `live: true` claim must be backed by a `live: true`
// upstream; INV-BRP-1 (draft) enforces this at the DOM level.
// -----------------------------------------------------------------------------

export interface LivenessFlags {
  readonly ambient: boolean;
  readonly legibility: boolean;
  readonly telemetry: boolean;
}

// -----------------------------------------------------------------------------
// Pulse signal (optional, commit ε).
//
// When the host page wires a live event stream (e.g., /ws/records WebSocket
// for PoAC record arrivals at gameplay frequency), it can pass a `pulse`
// prop whose `ts` field changes with each event. The renderer responds with
// a brief emissive bump on the ambient mesh — visible "alive" feedback that
// telemetry is flowing.
//
// Optional. Renderer remains mount-agnostic per D2: when omitted, the mesh
// continues its base rotation (commit δ) without pulse animation.
//
// Per WCAG 2.3.1 (G19 < 3 Hz): the pulse animation duration + emissive
// delta are bounded so the effective oscillation stays within budget. See
// sceneFlashBudget AMBIENT_LAYER_MATERIAL frequency_hz documentation for
// the worst-case rate (1 Hz at gameplay-frequency PoAC; 3× under cap).
// -----------------------------------------------------------------------------

export interface PulseSignal {
  /**
   * Monotonically advancing timestamp. The renderer triggers a pulse
   * animation when this value differs from the previous frame's
   * observed value. Suggested source: Date.now() at the time of the
   * upstream event arrival.
   */
  readonly ts: number;
  /**
   * Pulse intensity in [0, 1]. 1 = full emissive bump; 0 = no animation.
   * Allows the host page to throttle visual response by event class
   * (e.g., damp pulses for low-confidence telemetry).
   */
  readonly intensity: number;
}

// -----------------------------------------------------------------------------
// Orientation signal (optional, commit ζ).
//
// When the host page subscribes to a controller IMU stream (e.g., the bridge's
// /ws/twin/{device_id} fusion endpoint, Phase 59), it can pass an `orientation`
// prop with derived pitch + roll + yaw radians. The renderer's ambient mesh
// applies the orientation as an X/Z-axis tilt overlaid on its existing 0.1 Hz
// Y-axis spin (commit δ). The overlay is lerped per-frame so 1 Hz target
// updates produce smooth 60 fps interpolated motion.
//
// Optional. Renderer remains mount-agnostic per D2: when omitted, the mesh
// continues with rotation-only mode (commit δ).
//
// Per WCAG 2.3.1: orientation is spatial movement (no luminance change).
// flashBudget descriptor unchanged. AccessibilityShell's motionShouldPause
// halts the entire useFrame loop including orientation lerping.
// -----------------------------------------------------------------------------

export interface OrientationSignal {
  /** Pitch in radians: forward/back tilt. Positive = nose up. */
  readonly pitch: number;
  /** Roll in radians: left/right tilt. Positive = right side down. */
  readonly roll: number;
  /** Yaw in radians: rotation around vertical axis. Positive = clockwise. */
  readonly yaw: number;
  /** Monotonically advancing timestamp of the source frame, for staleness detection. */
  readonly ts: number;
}

// -----------------------------------------------------------------------------
// Host-state signal (optional, commit ι).
//
// Surfaces the bridge's PCC (Physical Capture Continuity, Phase 234.7)
// host-state inference, derived from HID poll-rate coefficient of variation.
// Drives the ambient mesh's emissive palette so the operator sees at a
// glance whether the controller<->bridge link is healthy.
//
// Per PCC: host-state values are EXCLUSIVE_USB / EXCLUSIVE_BT / CONTESTED
// / UNKNOWN / DEGRADED / DISCONNECTED. The bridge classifies these at
// /operator/bridge/capture-health (already-consumed by useCaptureHealth
// at 3s polling, no new endpoint needed).
//
// Optional. Renderer remains mount-agnostic per D2: when omitted, the mesh
// uses its base palette (commit δ/ε/ζ behavior — steel-blue #5a8fb8).
//
// Per WCAG 2.3.1: palette change is a one-shot color transition on the
// MATERIAL color (not a flashing oscillator), happens at most once per
// 3s polling cycle, well under any G19 frequency concern. The color
// values are pre-validated against the saturated-red guard.
// -----------------------------------------------------------------------------

// -----------------------------------------------------------------------------
// Trust signal (optional, commit λ).
//
// Surfaces the bridge's PHG (Player Humanity Glyph) Trust Ledger — the same
// per-device legitimacy stat that backs VHP credentialing — as a visual
// modulation. humanityProbAvg lerps the ambient mesh's resting emissive
// intensity floor: low trust dims the mesh; high trust brightens it.
// nominalRecords / totalRecords are exposed for future surface bindings
// (instance-count modulation, etc.) but the v1 commit only consumes
// humanityProbAvg.
//
// Optional. Renderer remains mount-agnostic per D2: when omitted, the mesh
// uses the static BASE_EMISSIVE_INTENSITY (commit ε behavior).
//
// Per WCAG 2.3.1: emissive floor is bounded to [0.05, 0.20] — well under the
// ΔL 0.10 luminance-delta cap relative to the dark canvas bg. Updates are
// driven by the 10s PHG profile poll, far below G19 3 Hz cap. The pulse
// animation (commit ε) still operates on top of this floor; the bump goes
// from `floor → PEAK_INTENSITY` so a high-trust mesh has a smaller bump
// magnitude (its baseline is already brighter) — preserves the ΔL
// invariant in both directions.
// -----------------------------------------------------------------------------

export interface TrustSignal {
  /** Mean humanity probability in [0, 1] over recent NOMINAL records. */
  readonly humanityProbAvg: number;
  /** PHG score (raw cumulative, monotonic). */
  readonly phgScore: number;
  /** PHG score weighted by humanity probability. */
  readonly phgScoreWeighted: number;
  /** Count of NOMINAL records in the trust ledger. */
  readonly nominalRecords: number;
  /** Total record count for the device (NOMINAL + advisory + hard). */
  readonly totalRecords: number;
}

export type HostStateKind =
  | "EXCLUSIVE_USB"
  | "EXCLUSIVE_BT"
  | "CONTESTED"
  | "DEGRADED"
  | "DISCONNECTED"
  | "UNKNOWN";

export interface HostStateSignal {
  /** Bridge-classified host-state per Phase 234.7 PCC. */
  readonly kind: HostStateKind;
  /** Capture-state classification: NOMINAL / DEGRADED / DISCONNECTED. */
  readonly captureState: "NOMINAL" | "DEGRADED" | "DISCONNECTED";
}

// -----------------------------------------------------------------------------
// The full prop contract for <BrpMount />.
//
// 4a ships the type. 4c ships the matching <BrpMount /> component. The
// integration ceremony confirms slot placement at /gamer/twin per Block T.
// -----------------------------------------------------------------------------

export interface BrpMountProps {
  readonly frozenOutput: Uint8Array;
  readonly pitlSnapshot: PitlSnapshot;
  readonly enrollmentSession?: EnrollmentSession;
  readonly aidThreshold: number;
  readonly liveness: LivenessFlags;
  /**
   * Optional. When present, a change in `pulse.ts` triggers a brief
   * emissive animation on the ambient mesh (commit ε). Omit to keep
   * the mesh in base-rotation-only mode (commit δ behavior).
   */
  readonly pulse?: PulseSignal;
  /**
   * Optional. When present, the ambient mesh applies pitch/roll/yaw as
   * an X/Z-axis tilt overlay on the base 0.1 Hz Y-spin (commit ζ).
   * Lerped per-frame for smooth interpolation when source updates at
   * 1 Hz. Omit for rotation-only mode (commit δ behavior).
   */
  readonly orientation?: OrientationSignal;
  /**
   * Optional. When present, the ambient mesh's emissive palette reflects
   * the host-state classification (commit ι). EXCLUSIVE_USB → cool steel-blue
   * (base palette); EXCLUSIVE_BT → warm amber; CONTESTED/DEGRADED →
   * desaturated grey; DISCONNECTED → dim charcoal. Omit to keep base palette.
   */
  readonly hostState?: HostStateSignal;
  /**
   * Optional. When present, humanityProbAvg lerps the ambient mesh's
   * resting emissive intensity floor between dim (low trust) and bright
   * (high trust). Pulse bumps still operate on top of this floor.
   */
  readonly trust?: TrustSignal;
}
