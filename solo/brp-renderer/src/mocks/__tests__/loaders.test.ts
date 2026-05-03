import { describe, it, expect } from "vitest";
import {
  getMockPitlSnapshot,
  getMockEnrollmentSession,
} from "../loaders";

describe("mock fixture loaders — shape validation", () => {
  it("T-4c-loaders-1: getMockPitlSnapshot returns 7 PITL rows with bigint ts fields", () => {
    const snap = getMockPitlSnapshot();
    expect(snap.rows.length).toBe(7);
    expect(typeof snap.snapshotTsNs).toBe("bigint");
    expect(snap.snapshotTsNs).toBe(1700000000123456789n);

    const layers = snap.rows.map((r) => r.layer);
    expect(layers).toEqual(["L0", "L1", "L2", "L3", "L4", "L5", "L6"]);

    for (const row of snap.rows) {
      expect(typeof row.inferenceCode).toBe("number");
      expect(Number.isInteger(row.inferenceCode)).toBe(true);
      expect(typeof row.active).toBe("boolean");
      if (row.tsNs !== undefined) {
        expect(typeof row.tsNs).toBe("bigint");
      }
      if (row.score !== undefined) {
        expect(row.score).toBeGreaterThanOrEqual(0);
        expect(row.score).toBeLessThanOrEqual(1);
      }
    }
  });

  it("T-4c-loaders-2: getMockEnrollmentSession returns valid EnrollmentSession shape", () => {
    const sess = getMockEnrollmentSession();
    expect(typeof sess.deviceId).toBe("string");
    expect(sess.deviceId.length).toBeGreaterThan(0);
    expect(Number.isInteger(sess.sessionsNominal)).toBe(true);
    expect(sess.sessionsNominal).toBeGreaterThanOrEqual(0);
    expect(typeof sess.avgHumanity).toBe("number");
    expect(["pending", "eligible", "minting", "credentialed", "failed"]).toContain(
      sess.status,
    );
    expect(Number.isInteger(sess.requiredSessions)).toBe(true);
    expect(typeof sess.requiredHumanity).toBe("number");
  });

  it("T-4c-loaders-3: same call returns same frozen reference (deterministic dev surface)", () => {
    const a = getMockPitlSnapshot();
    const b = getMockPitlSnapshot();
    expect(a).toBe(b);
    expect(Object.isFrozen(a)).toBe(true);

    const e1 = getMockEnrollmentSession();
    const e2 = getMockEnrollmentSession();
    expect(e1).toBe(e2);
    expect(Object.isFrozen(e1)).toBe(true);
  });
});
