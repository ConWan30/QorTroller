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
}
