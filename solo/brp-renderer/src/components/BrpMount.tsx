// BrpMount — top-level public composition.
//
// Track classification: out-of-band-solo. NOT Phase 241. NOT in the sequential
// VAPI protocol chain.
//
// This is the slot the integration ceremony mounts at /gamer/twin per Block T.
// Accepts the full BrpMountProps contract from src/telemetry/contracts.ts;
// every value is opaque to the renderer per Decision D2 (mount-agnostic).
//
// Composition (top-down):
//   <AccessibilityShell>          // role/aria/reduced-motion/photosensitivity
//     <div data-brp-mount>        // layout root
//       <BrpCanvas />              // R3F canvas + AmbientLayer (4b)
//       <LegibilityOverlay />      // calibration-aid HUD (4c)
//       <EnrollmentBadge? />       // enrollment status (4c, optional)
//     </div>
//   </AccessibilityShell>
//
// PDF reference: §"Block T", §"Block W", §"Integration Contract for Downstream
// Merge".

import { AccessibilityShell } from "./AccessibilityShell";
import { BrpCanvas } from "./BrpCanvas";
import { LegibilityOverlay } from "./LegibilityOverlay";
import type {
  BrpMountProps,
  EnrollmentSession,
} from "../telemetry/contracts";

interface EnrollmentBadgeProps {
  readonly session: EnrollmentSession;
}

/**
 * Optional enrollment status display. Rendered only when the host passes
 * `enrollmentSession`. Plain HTML; not load-bearing for the ambient mesh.
 */
function EnrollmentBadge({ session }: EnrollmentBadgeProps): JSX.Element {
  const progress = session.requiredSessions > 0
    ? Math.min(1, session.sessionsNominal / session.requiredSessions)
    : 0;
  return (
    <div
      data-testid="brp-enrollment-badge"
      data-brp-enrollment="true"
      data-live="false"
      data-status={session.status}
      style={{
        position: "absolute",
        bottom: "1rem",
        right: "1rem",
        padding: "0.5rem 0.75rem",
        background: "rgba(15, 22, 32, 0.7)",
        color: "#cce",
        fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
        fontSize: "0.72rem",
        borderRadius: "4px",
        border: "1px solid rgba(90, 143, 184, 0.25)",
        zIndex: 10,
      }}
    >
      <div style={{ opacity: 0.7, fontSize: "0.65rem", letterSpacing: "0.08em", textTransform: "uppercase" }}>
        Enrollment
      </div>
      <div data-testid="enrollment-status">{session.status}</div>
      <div data-testid="enrollment-progress" style={{ opacity: 0.7 }}>
        {session.sessionsNominal} / {session.requiredSessions} nominal
        {" · "}
        {(progress * 100).toFixed(0)}%
      </div>
    </div>
  );
}

export function BrpMount(props: BrpMountProps): JSX.Element {
  const {
    frozenOutput,
    pitlSnapshot,
    enrollmentSession,
    aidThreshold,
    liveness,
    pulse,
    orientation,
    hostState,
  } = props;

  return (
    <AccessibilityShell>
      <div
        data-testid="brp-mount-root"
        data-brp-mount="true"
        data-live={liveness.ambient || liveness.legibility || liveness.telemetry ? "true" : "false"}
        data-liveness-ambient={liveness.ambient ? "true" : "false"}
        data-liveness-legibility={liveness.legibility ? "true" : "false"}
        data-liveness-telemetry={liveness.telemetry ? "true" : "false"}
        style={{
          position: "relative",
          width: "100%",
          height: "100%",
          minHeight: "320px",
        }}
      >
        <BrpCanvas
          frozenOutput={frozenOutput}
          {...(pulse ? { pulse } : {})}
          {...(orientation ? { orientation } : {})}
          {...(hostState ? { hostState } : {})}
        />
        <LegibilityOverlay
          pitlSnapshot={pitlSnapshot}
          aidThreshold={aidThreshold}
        />
        {enrollmentSession ? (
          <EnrollmentBadge session={enrollmentSession} />
        ) : null}
      </div>
    </AccessibilityShell>
  );
}
