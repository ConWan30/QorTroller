// LegibilityOverlay — calibration-aid HUD.
//
// Track classification: out-of-band-solo. NOT Phase 241. NOT in the sequential
// VAPI protocol chain.
//
// Plain HTML, position-absolute over BrpCanvas. NOT drei <Html>. Per design
// PDF §"Block X — PITL row coexistence", BRP visualization is "presented
// adjacent to (not within) the PITL row container in the DOM" — keeping the
// overlay as a DOM sibling (rather than a child of the WebGL canvas) is
// architecturally cleaner and decouples the overlay from BrpCanvas's lifecycle.
// Deliberate deviation from PDF §"Component structure" line that prescribed
// drei <Html>; documented in commit 4c plan and message.
//
// aidThreshold gate (placeholder per Block Z, deferred):
//   The threshold at which the overlay flips from "ambient aesthetic" to
//   "active calibration aid" is fundamentally an empirical question requiring
//   real PITL telemetry across a real player population. The renderer ships
//   `aidThreshold: number` as an opaque prop with default 0.65. The 0.65
//   value mirrors the protocol's Epistemic Consensus Protocol threshold
//   purely as a placeholder; it shares the numeric value by accident, NOT by
//   design. Ceremony picks the real metric.
//
// Current placeholder gate logic:
//   activeMode = pitlSnapshot.rows.some(row => (row.score ?? 0) > aidThreshold)
//
// PDF reference: §"Block X", §"Block Z", §"Block A1", §"Block W".

import { useMotionContext } from "./AccessibilityShell";
import type { PitlRow, PitlSnapshot } from "../telemetry/contracts";

export interface LegibilityOverlayProps {
  readonly pitlSnapshot: PitlSnapshot;
  readonly aidThreshold: number;
}

/**
 * Pure helper: aidThreshold gate decision. Exported so unit tests can verify
 * the semantic without rendering.
 */
export function isActiveAidMode(
  rows: readonly PitlRow[],
  aidThreshold: number,
): boolean {
  return rows.some((row) => (row.score ?? 0) > aidThreshold);
}

function inferenceCodeName(code: number): string {
  // Audit-readable lookup for the small set of codes the renderer needs to
  // surface verbally. Unknown codes render as 0xNN hex.
  switch (code) {
    case 0x20:
      return "NOMINAL";
    case 0x28:
      return "DRIVER_INJECT";
    case 0x29:
      return "WALLHACK";
    case 0x2a:
      return "AIMBOT";
    case 0x2b:
      return "TEMPORAL_BOT";
    case 0x30:
      return "BIOMETRIC_ANOMALY";
    case 0x31:
      return "IMU_PRESS_DECOUPLED";
    case 0x32:
      return "STICK_IMU_DECOUPLED";
    case 0x33:
      return "GSR_CORRELATION_ABSENT";
    default:
      return `0x${code.toString(16).padStart(2, "0")}`;
  }
}

export function LegibilityOverlay({
  pitlSnapshot,
  aidThreshold,
}: LegibilityOverlayProps): JSX.Element {
  const { motionShouldPause } = useMotionContext();
  const activeMode = isActiveAidMode(pitlSnapshot.rows, aidThreshold);

  return (
    <aside
      role="region"
      aria-label="VAPI calibration legibility overlay"
      data-brp-overlay="true"
      data-live="false"
      data-mode={activeMode ? "active-aid" : "ambient"}
      data-motion-paused={motionShouldPause ? "true" : "false"}
      style={{
        position: "absolute",
        top: "1rem",
        right: "1rem",
        minWidth: "240px",
        maxWidth: "320px",
        padding: "0.75rem 1rem",
        background: activeMode
          ? "rgba(40, 60, 80, 0.85)"
          : "rgba(15, 22, 32, 0.65)",
        color: "#dde",
        fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
        fontSize: "0.78rem",
        lineHeight: 1.5,
        borderRadius: "6px",
        border: activeMode
          ? "1px solid #5a8fb8"
          : "1px solid rgba(90, 143, 184, 0.25)",
        backdropFilter: "blur(6px)",
        transition: motionShouldPause ? "none" : "background 0.4s, border 0.4s",
        pointerEvents: "auto",
        zIndex: 10,
      }}
    >
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          marginBottom: "0.5rem",
          fontSize: "0.7rem",
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          opacity: 0.7,
        }}
      >
        <span data-testid="overlay-mode-label">
          {activeMode ? "ACTIVE AID" : "AMBIENT"}
        </span>
        <span
          data-testid="overlay-snapshot-ts"
          aria-label="snapshot timestamp"
          title={`snapshotTsNs=${pitlSnapshot.snapshotTsNs.toString()}`}
        >
          {/* Show last 9 digits for visual stability without exposing full ns */}
          {`…${pitlSnapshot.snapshotTsNs.toString().slice(-9)}`}
        </span>
      </header>
      <ol
        data-testid="overlay-row-list"
        style={{
          listStyle: "none",
          padding: 0,
          margin: 0,
          display: "grid",
          gridTemplateColumns: "auto 1fr auto",
          rowGap: "0.25rem",
          columnGap: "0.5rem",
        }}
      >
        {pitlSnapshot.rows.map((row) => (
          <li
            key={row.layer}
            data-testid={`overlay-row-${row.layer}`}
            data-active={row.active ? "true" : "false"}
            data-above-threshold={
              (row.score ?? 0) > aidThreshold ? "true" : "false"
            }
            style={{
              display: "contents",
              opacity: row.active ? 1 : 0.4,
            }}
          >
            <span style={{ fontWeight: 600 }}>{row.layer}</span>
            <span>{inferenceCodeName(row.inferenceCode)}</span>
            <span
              style={{
                fontVariantNumeric: "tabular-nums",
                color:
                  (row.score ?? 0) > aidThreshold ? "#9bc4e8" : "inherit",
              }}
            >
              {row.score !== undefined ? row.score.toFixed(2) : "—"}
            </span>
          </li>
        ))}
      </ol>
    </aside>
  );
}
