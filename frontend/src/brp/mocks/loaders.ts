// Mock fixture loaders — typed JSON-to-runtime conversion.
//
// Track classification: out-of-band-solo. NOT Phase 241. NOT in the sequential
// VAPI protocol chain.
//
// JSON cannot represent BigInt natively. The fixtures encode ts_ns fields as
// decimal strings; these loaders convert to bigint at load time. This is the
// shape-validation boundary: if a fixture is malformed, the loader throws
// loudly (rather than silently returning malformed data downstream).
//
// MSW (Mock Service Worker) is intentionally NOT used at this commit. It will
// be added in Step 4d when Storybook stories need network-level mocking. For
// 4c, fixtures are imported synchronously and consumed as static props.

import pitlRaw from "./fixtures/pitl.snapshot.json";
import enrollmentRaw from "./fixtures/enrollment.session.json";
import type {
  EnrollmentSession,
  EnrollmentStatus,
  PitlLayer,
  PitlRow,
  PitlSnapshot,
} from "../telemetry/contracts";

const VALID_LAYERS: readonly PitlLayer[] = [
  "L0",
  "L1",
  "L2",
  "L3",
  "L4",
  "L5",
  "L6",
];

const VALID_STATUS: readonly EnrollmentStatus[] = [
  "pending",
  "eligible",
  "minting",
  "credentialed",
  "failed",
];

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function asBigInt(value: unknown, ctx: string): bigint {
  if (typeof value === "string" && /^\d+$/.test(value)) {
    return BigInt(value);
  }
  if (typeof value === "number" && Number.isFinite(value) && Number.isInteger(value)) {
    return BigInt(value);
  }
  throw new Error(`mock fixture: ${ctx} must be a non-negative integer string, got ${JSON.stringify(value)}`);
}

function parsePitlRow(raw: unknown, idx: number): PitlRow {
  if (!isPlainObject(raw)) {
    throw new Error(`mock fixture pitl row[${idx}]: must be an object`);
  }
  const layer = raw["layer"];
  if (typeof layer !== "string" || !VALID_LAYERS.includes(layer as PitlLayer)) {
    throw new Error(
      `mock fixture pitl row[${idx}].layer: must be one of ${VALID_LAYERS.join(", ")}; got ${JSON.stringify(layer)}`,
    );
  }
  const inferenceCode = raw["inferenceCode"];
  if (typeof inferenceCode !== "number" || !Number.isInteger(inferenceCode)) {
    throw new Error(`mock fixture pitl row[${idx}].inferenceCode: must be an integer`);
  }
  const active = raw["active"];
  if (typeof active !== "boolean") {
    throw new Error(`mock fixture pitl row[${idx}].active: must be boolean`);
  }
  const score = raw["score"];
  const tsNs = raw["tsNs"];
  return {
    layer: layer as PitlLayer,
    inferenceCode,
    active,
    ...(typeof score === "number" ? { score } : {}),
    ...(tsNs !== undefined ? { tsNs: asBigInt(tsNs, `pitl row[${idx}].tsNs`) } : {}),
  };
}

function parsePitlSnapshot(raw: unknown): PitlSnapshot {
  if (!isPlainObject(raw)) {
    throw new Error("mock fixture pitl snapshot: root must be an object");
  }
  const rowsRaw = raw["rows"];
  if (!Array.isArray(rowsRaw)) {
    throw new Error("mock fixture pitl snapshot: rows must be an array");
  }
  const rows = rowsRaw.map((row, i) => parsePitlRow(row, i));
  const snapshotTsNs = asBigInt(raw["snapshotTsNs"], "pitl snapshot.snapshotTsNs");
  return Object.freeze({ rows: Object.freeze(rows), snapshotTsNs });
}

function parseEnrollmentSession(raw: unknown): EnrollmentSession {
  if (!isPlainObject(raw)) {
    throw new Error("mock fixture enrollment session: root must be an object");
  }
  const deviceId = raw["deviceId"];
  if (typeof deviceId !== "string" || deviceId.length === 0) {
    throw new Error("mock fixture enrollment session.deviceId: must be a non-empty string");
  }
  const sessionsNominal = raw["sessionsNominal"];
  if (typeof sessionsNominal !== "number" || !Number.isInteger(sessionsNominal)) {
    throw new Error("mock fixture enrollment session.sessionsNominal: must be an integer");
  }
  const avgHumanity = raw["avgHumanity"];
  if (typeof avgHumanity !== "number") {
    throw new Error("mock fixture enrollment session.avgHumanity: must be a number");
  }
  const status = raw["status"];
  if (typeof status !== "string" || !VALID_STATUS.includes(status as EnrollmentStatus)) {
    throw new Error(
      `mock fixture enrollment session.status: must be one of ${VALID_STATUS.join(", ")}`,
    );
  }
  const requiredSessions = raw["requiredSessions"];
  if (typeof requiredSessions !== "number" || !Number.isInteger(requiredSessions)) {
    throw new Error("mock fixture enrollment session.requiredSessions: must be an integer");
  }
  const requiredHumanity = raw["requiredHumanity"];
  if (typeof requiredHumanity !== "number") {
    throw new Error("mock fixture enrollment session.requiredHumanity: must be a number");
  }
  return Object.freeze({
    deviceId,
    sessionsNominal,
    avgHumanity,
    status: status as EnrollmentStatus,
    requiredSessions,
    requiredHumanity,
  });
}

// Validate at module load — catch malformed fixtures at first import,
// not at first consumer call.
const _PITL_SNAPSHOT: PitlSnapshot = parsePitlSnapshot(pitlRaw);
const _ENROLLMENT_SESSION: EnrollmentSession = parseEnrollmentSession(enrollmentRaw);

/**
 * Returns a frozen mock PitlSnapshot suitable for dev-surface mounting and
 * Storybook stories (4d). Same object reference returned on every call.
 */
export function getMockPitlSnapshot(): PitlSnapshot {
  return _PITL_SNAPSHOT;
}

/**
 * Returns a frozen mock EnrollmentSession. Same object reference returned on
 * every call.
 */
export function getMockEnrollmentSession(): EnrollmentSession {
  return _ENROLLMENT_SESSION;
}
