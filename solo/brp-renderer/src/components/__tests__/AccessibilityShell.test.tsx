import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, renderHook, act } from "@testing-library/react";
import {
  AccessibilityShell,
  useMotionContext,
  MOTION_DISABLED_STORAGE_KEY,
} from "../AccessibilityShell";

// Helper: install a controllable matchMedia stub on window.
function installMatchMediaStub(initialMatches: boolean): {
  setMatches: (next: boolean) => void;
  listeners: Set<(ev: { matches: boolean }) => void>;
} {
  const listeners = new Set<(ev: { matches: boolean }) => void>();
  let matches = initialMatches;
  const stub = (query: string): MediaQueryList => {
    void query;
    return {
      matches,
      media: "(prefers-reduced-motion: reduce)",
      onchange: null,
      addEventListener: (_evt: string, cb: (ev: { matches: boolean }) => void) => {
        listeners.add(cb);
      },
      removeEventListener: (_evt: string, cb: (ev: { matches: boolean }) => void) => {
        listeners.delete(cb);
      },
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => true,
    } as unknown as MediaQueryList;
  };
  window.matchMedia = stub as unknown as typeof window.matchMedia;
  return {
    setMatches: (next: boolean) => {
      matches = next;
      for (const cb of listeners) cb({ matches });
    },
    listeners,
  };
}

beforeEach(() => {
  window.localStorage.clear();
  // Default to no OS preference unless a test overrides.
  installMatchMediaStub(false);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("AccessibilityShell — DOM accessibility primitives", () => {
  it("T-4a-1: renders children + sr-only description; root carries role=presentation + data-live=false", () => {
    const { container } = render(
      <AccessibilityShell>
        <span data-testid="child">child content</span>
      </AccessibilityShell>,
    );
    // Children present.
    expect(screen.getByTestId("child")).toHaveTextContent("child content");
    // Root attributes (INV-BRP-1 + INV-BRP-5 draft contracts).
    const root = container.querySelector("[data-brp-shell]");
    expect(root).not.toBeNull();
    expect(root).toHaveAttribute("role", "presentation");
    expect(root).toHaveAttribute("data-live", "false");
    // Default description text present and AT-visible.
    expect(screen.getByTestId("brp-shell-description")).toHaveTextContent(
      /Decorative ambient visualization/,
    );
  });

  it("T-4a-2: description prop overrides the default text", () => {
    render(
      <AccessibilityShell description="Custom audit description.">
        <span />
      </AccessibilityShell>,
    );
    expect(screen.getByTestId("brp-shell-description")).toHaveTextContent(
      "Custom audit description.",
    );
  });

  it("T-4a-3: photosensitivity toggle persists to localStorage and toggles back", () => {
    render(
      <AccessibilityShell>
        <span />
      </AccessibilityShell>,
    );
    const btn = screen.getByTestId("brp-photosensitivity-toggle");
    expect(btn).toHaveAttribute("data-toggled", "false");
    expect(window.localStorage.getItem(MOTION_DISABLED_STORAGE_KEY)).toBeNull();

    fireEvent.click(btn);
    expect(btn).toHaveAttribute("data-toggled", "true");
    expect(window.localStorage.getItem(MOTION_DISABLED_STORAGE_KEY)).toBe("1");

    fireEvent.click(btn);
    expect(btn).toHaveAttribute("data-toggled", "false");
    expect(window.localStorage.getItem(MOTION_DISABLED_STORAGE_KEY)).toBe("0");
  });

  it("T-4a-4: localStorage initial value 1 hydrates the toggle as user-toggled-off on mount", () => {
    window.localStorage.setItem(MOTION_DISABLED_STORAGE_KEY, "1");
    render(
      <AccessibilityShell>
        <span />
      </AccessibilityShell>,
    );
    const btn = screen.getByTestId("brp-photosensitivity-toggle");
    expect(btn).toHaveAttribute("data-toggled", "true");
    expect(btn).toHaveTextContent("Motion: OFF");
  });

  it("T-4a-5: localStorage failure is fail-silent — write throws, in-memory state still updates", () => {
    const setItemSpy = vi
      .spyOn(window.localStorage.__proto__ as Storage, "setItem")
      .mockImplementation(() => {
        throw new Error("QuotaExceededError simulated");
      });

    render(
      <AccessibilityShell>
        <span />
      </AccessibilityShell>,
    );
    const btn = screen.getByTestId("brp-photosensitivity-toggle");
    // Click should NOT throw despite storage failure.
    expect(() => fireEvent.click(btn)).not.toThrow();
    // In-memory state still flipped.
    expect(btn).toHaveAttribute("data-toggled", "true");
    expect(setItemSpy).toHaveBeenCalled();
    setItemSpy.mockRestore();
  });

  it("T-4a-6: matchMedia listener fires on OS preference change and updates motion-paused state", () => {
    const mq = installMatchMediaStub(false);
    const { container } = render(
      <AccessibilityShell>
        <span />
      </AccessibilityShell>,
    );
    const root = container.querySelector("[data-brp-shell]")!;
    expect(root).toHaveAttribute("data-motion-paused", "false");
    // OS now signals reduce. Wrap in act() so React 18 flushes the state
    // update from the matchMedia listener before the assertion.
    act(() => {
      mq.setMatches(true);
    });
    expect(root).toHaveAttribute("data-motion-paused", "true");
  });

  it("T-4a-7: useMotionContext throws when called outside the shell", () => {
    // Renders the hook in isolation, no provider ancestor.
    const callsite = (): unknown => renderHook(() => useMotionContext());
    expect(callsite).toThrow(/AccessibilityShell/);
  });

  it("T-4a-8: motionShouldPause is OS pref OR user toggle (composability)", () => {
    let captured: ReturnType<typeof useMotionContext> | null = null;
    function Probe(): null {
      captured = useMotionContext();
      return null;
    }

    const mq = installMatchMediaStub(false);
    const { rerender, container } = render(
      <AccessibilityShell>
        <Probe />
      </AccessibilityShell>,
    );
    expect(captured!.motionShouldPause).toBe(false);

    // User-only path.
    fireEvent.click(screen.getByTestId("brp-photosensitivity-toggle"));
    expect(captured!.motionShouldPause).toBe(true);
    expect(captured!.userToggledOff).toBe(true);
    expect(captured!.osPrefersReducedMotion).toBe(false);

    // Reset user toggle, then OS-only path.
    fireEvent.click(screen.getByTestId("brp-photosensitivity-toggle"));
    expect(captured!.motionShouldPause).toBe(false);
    act(() => {
      mq.setMatches(true);
    });
    expect(captured!.motionShouldPause).toBe(true);
    expect(captured!.osPrefersReducedMotion).toBe(true);
    expect(captured!.userToggledOff).toBe(false);

    // Both ON.
    fireEvent.click(screen.getByTestId("brp-photosensitivity-toggle"));
    expect(captured!.motionShouldPause).toBe(true);

    void rerender;
    void container;
  });
});
