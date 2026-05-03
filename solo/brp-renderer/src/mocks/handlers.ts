// MSW handlers — Storybook fixture-variation server.
//
// Track classification: out-of-band-solo. NOT Phase 241. NOT in the sequential
// VAPI protocol chain.
//
// IMPORTANT: the BRP renderer itself does NOT fetch anything in 4d. Decision D2
// (mount-agnostic) means the host page wires telemetry; the renderer accepts
// props as opaque values. So why MSW?
//
// Storybook stories need *fixture variations* that the synchronous loaders in
// `src/mocks/loaders.ts` can't supply (a single deterministic shape per loader).
// Stories that exercise "active aid mode", "telemetry degraded", "enrollment
// credentialed", etc. need different fixture variants per story. MSW addon
// intercepts simulated `fetch()` calls inside Storybook decorators / play
// functions and returns the variant that matches the story.
//
// At integration ceremony time, the host page wires real endpoints. These
// handlers are documentation-only at that point — they describe the shape the
// renderer expects from each ceremony-bound endpoint. The handlers map 1:1 to
// `BACKEND_CONTRACT.md` §"Endpoint inventory".

import { http, HttpResponse } from "msw";
import {
  getMockEnrollmentSession,
  getMockPitlSnapshot,
} from "./loaders";

// -----------------------------------------------------------------------------
// Variant builders — start from the canonical fixture, override targeted fields.
// -----------------------------------------------------------------------------

/** Active-aid variant: at least one PITL row's score exceeds typical thresholds. */
function activeAidPitlSnapshot(): Record<string, unknown> {
  const base = getMockPitlSnapshot();
  return {
    rows: base.rows.map((row, i) => ({
      ...row,
      // bigint -> string for JSON wire compat (matches loader convention).
      ...(row.tsNs !== undefined ? { tsNs: row.tsNs.toString() } : {}),
      // First two rows clearly above typical 0.65 threshold.
      score: i < 2 ? 0.95 : (row.score ?? 0.5),
    })),
    snapshotTsNs: base.snapshotTsNs.toString(),
  };
}

/** Telemetry-degraded variant: most rows inactive. */
function degradedPitlSnapshot(): Record<string, unknown> {
  const base = getMockPitlSnapshot();
  return {
    rows: base.rows.map((row, i) => ({
      ...row,
      ...(row.tsNs !== undefined ? { tsNs: row.tsNs.toString() } : {}),
      active: i === 0, // only L0 active; rest degraded
      score: i === 0 ? row.score : 0.1,
    })),
    snapshotTsNs: base.snapshotTsNs.toString(),
  };
}

/** Default canonical PITL snapshot, JSON-serialized. */
function canonicalPitlSnapshot(): Record<string, unknown> {
  const base = getMockPitlSnapshot();
  return {
    rows: base.rows.map((row) => ({
      ...row,
      ...(row.tsNs !== undefined ? { tsNs: row.tsNs.toString() } : {}),
    })),
    snapshotTsNs: base.snapshotTsNs.toString(),
  };
}

/** Enrollment status variants matching the EnrollmentStatus union. */
function enrollmentVariant(
  status: "pending" | "eligible" | "minting" | "credentialed" | "failed",
): Record<string, unknown> {
  const base = getMockEnrollmentSession();
  const sessionsByStatus: Record<typeof status, number> = {
    pending: 7,
    eligible: 10,
    minting: 10,
    credentialed: 10,
    failed: 4,
  };
  return {
    ...base,
    status,
    sessionsNominal: sessionsByStatus[status],
  };
}

// -----------------------------------------------------------------------------
// Handlers — STUB endpoints that mirror BACKEND_CONTRACT.md.
// The renderer never fetches these in 4d; Storybook stories trigger them via
// decorators when a story explicitly opts into a network-driven variant.
// -----------------------------------------------------------------------------

export const handlers = [
  // PITL snapshot — default canonical shape.
  http.get("/dash/api/v1/pitl/snapshot", () => {
    return HttpResponse.json(canonicalPitlSnapshot());
  }),

  // PITL snapshot — active-aid variant (used by ActiveAidMode story).
  http.get("/dash/api/v1/pitl/snapshot/active-aid", () => {
    return HttpResponse.json(activeAidPitlSnapshot());
  }),

  // PITL snapshot — telemetry-degraded variant.
  http.get("/dash/api/v1/pitl/snapshot/degraded", () => {
    return HttpResponse.json(degradedPitlSnapshot());
  }),

  // Enrollment session — variant by status query param.
  http.get(
    "/dash/api/v1/enrollment/:deviceId",
    ({ request }) => {
      const url = new URL(request.url);
      const status = (url.searchParams.get("status") ??
        "pending") as Parameters<typeof enrollmentVariant>[0];
      const valid = ["pending", "eligible", "minting", "credentialed", "failed"];
      if (!valid.includes(status)) {
        return HttpResponse.json(
          { error: `unknown status: ${status}` },
          { status: 400 },
        );
      }
      return HttpResponse.json(enrollmentVariant(status));
    },
  ),
];

// Re-export individual handler builders for per-story override scenarios.
export {
  activeAidPitlSnapshot,
  canonicalPitlSnapshot,
  degradedPitlSnapshot,
  enrollmentVariant,
};
