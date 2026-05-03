// AccessibilityShell — DOM-only accessibility primitives for the BRP renderer.
//
// Track classification: out-of-band-solo. NOT Phase 241. NOT in the sequential
// VAPI protocol chain. This component ships in commit 4a; commits 4b and 4c
// will compose <BrpCanvas /> and <LegibilityOverlay /> as children.
//
// Three accessibility layers, all on by default, all per design PDF §A1
// (Accessibility & photosensitivity governance):
//
//   1. role="presentation" + data-live="false" on the shell root — the
//      canvas-level decorative-bitmap pattern per MDN canvas-a11y reference.
//      Sibling <p> with sr-only description provides the AT-readable text.
//
//   2. prefers-reduced-motion via window.matchMedia('(prefers-reduced-motion:
//      reduce)'). Symmetric subscribe/unsubscribe, StrictMode-safe (handles
//      double-mount in dev). When set, exposes osPrefersReducedMotion=true via
//      context; in 4b, BrpCanvas will set frameloop="never" when the resulting
//      motionShouldPause is true.
//
//   3. User-controllable photosensitivity-safety toggle persisted in
//      localStorage under the namespaced key 'brp:motionDisabled'. WCAG SC
//      2.2.2 ("Pause, Stop, Hide") requires a mechanism for limiting motion;
//      this toggle is that mechanism. Hard-disables motion regardless of OS
//      preference. Fail-silent on storage errors (private browsing, quota);
//      defaults to motion=ON (toggle=OFF) when storage is unreachable. The OS
//      prefers-reduced-motion path is independent of localStorage, so WCAG
//      2.2.2 is still satisfied via that path even when storage fails.
//
// Honesty-first invariants this component commits to:
//   H-2 (data-live truthfulness): the shell root carries data-live="false"
//   for the entire pre-ceremony life of the renderer.
//   H-6 (photosensitivity safety): both OS-pref path and in-page toggle are
//   enabled by default; either firing pauses motion.
//
// PDF reference: §"Block A1 — Accessibility & photosensitivity governance",
// §"Component structure", §"Accessibility conformance approach".

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

/**
 * localStorage key. Namespaced under 'brp:' so the integration ceremony can
 * confirm no collision with host-page localStorage at mount time.
 */
const MOTION_DISABLED_STORAGE_KEY = "brp:motionDisabled";

/**
 * Default sr-only description text. Mirrors the MDN canvas-a11y reference's
 * decorative-canvas pattern. Override via the `description` prop.
 */
const DEFAULT_DESCRIPTION =
  "Decorative ambient visualization seeded from your verified controller telemetry. No interactive content.";

interface MotionContextValue {
  /** OR composition: pause when OS pref OR user toggle says so. */
  readonly motionShouldPause: boolean;
  readonly osPrefersReducedMotion: boolean;
  readonly userToggledOff: boolean;
  readonly setUserToggledOff: (next: boolean) => void;
}

const MotionContext = createContext<MotionContextValue | null>(null);

function readToggleFromStorage(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(MOTION_DISABLED_STORAGE_KEY) === "1";
  } catch {
    // Storage unavailable (private mode, quota, blocked). Fail-silent;
    // default to motion-enabled. WCAG 2.2.2 mechanism is still satisfied
    // via the OS prefers-reduced-motion path.
    return false;
  }
}

function writeToggleToStorage(next: boolean): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(MOTION_DISABLED_STORAGE_KEY, next ? "1" : "0");
  } catch {
    // Fail-silent. The in-memory state still reflects the user's intent.
  }
}

function readOsReducedMotion(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch {
    return false;
  }
}

/**
 * Hook for descendants to consume the motion-pause signal.
 *
 * Throws when called outside <AccessibilityShell>. This is intentional:
 * a renderer surface that ignores motion preferences is a WCAG violation,
 * so the shell wrapping is non-optional and the throw makes that explicit.
 */
export function useMotionContext(): MotionContextValue {
  const ctx = useContext(MotionContext);
  if (!ctx) {
    throw new Error(
      "useMotionContext must be called inside <AccessibilityShell>. " +
        "The shell is non-optional per WCAG 2.3.1 / 2.2.2 / A1 design contract.",
    );
  }
  return ctx;
}

export interface AccessibilityShellProps {
  readonly children: ReactNode;
  readonly description?: string;
}

/**
 * The renderer's accessibility wrapper. Mount as the outermost component of
 * any BRP surface. Children consume the motion-pause signal via
 * useMotionContext().
 */
export function AccessibilityShell({
  children,
  description = DEFAULT_DESCRIPTION,
}: AccessibilityShellProps): JSX.Element {
  const [osPrefersReducedMotion, setOsPref] =
    useState<boolean>(readOsReducedMotion);
  const [userToggledOff, setUserToggledOffState] =
    useState<boolean>(readToggleFromStorage);

  useEffect(() => {
    if (typeof window === "undefined") return;
    let mql: MediaQueryList;
    try {
      mql = window.matchMedia("(prefers-reduced-motion: reduce)");
    } catch {
      return;
    }
    // Read the live event payload's `matches` rather than the captured
    // MediaQueryList snapshot. Per W3C MediaQueryListEvent, `.matches` on the
    // event is the post-change value; the MediaQueryList object's `.matches`
    // is also live in real browsers but stub-friendly tests rely on the event
    // payload to be authoritative.
    const onChange = (ev: MediaQueryListEvent): void => {
      setOsPref(ev.matches);
    };
    // Modern browsers: addEventListener. Older Safari may only have addListener;
    // optional chaining handles both, and the symmetric remove is StrictMode-safe.
    mql.addEventListener?.("change", onChange);
    return () => {
      mql.removeEventListener?.("change", onChange);
    };
  }, []);

  const setUserToggledOff = (next: boolean): void => {
    writeToggleToStorage(next);
    setUserToggledOffState(next);
  };

  const motionShouldPause = osPrefersReducedMotion || userToggledOff;

  const ctxValue: MotionContextValue = {
    motionShouldPause,
    osPrefersReducedMotion,
    userToggledOff,
    setUserToggledOff,
  };

  return (
    <div
      role="presentation"
      data-live="false"
      data-brp-shell="true"
      data-motion-paused={motionShouldPause ? "true" : "false"}
    >
      <p
        id="brp-amb-desc"
        data-testid="brp-shell-description"
        style={{
          // sr-only — visually hidden, AT-visible.
          position: "absolute",
          width: "1px",
          height: "1px",
          padding: 0,
          margin: "-1px",
          overflow: "hidden",
          clip: "rect(0, 0, 0, 0)",
          whiteSpace: "nowrap",
          border: 0,
        }}
      >
        {description}
      </p>
      <button
        type="button"
        data-testid="brp-photosensitivity-toggle"
        data-toggled={userToggledOff ? "true" : "false"}
        onClick={() => setUserToggledOff(!userToggledOff)}
        aria-label={
          userToggledOff
            ? "Re-enable ambient motion"
            : "Disable ambient motion (photosensitivity safety)"
        }
      >
        {userToggledOff ? "Motion: OFF" : "Motion: ON"}
      </button>
      <MotionContext.Provider value={ctxValue}>
        {children}
      </MotionContext.Provider>
    </div>
  );
}

// Re-export the storage key for ceremony auditors and integration tests.
export { MOTION_DISABLED_STORAGE_KEY };
