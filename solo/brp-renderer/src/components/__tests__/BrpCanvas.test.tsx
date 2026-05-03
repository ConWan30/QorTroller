import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import {
  BrpCanvas,
  computeFrameloop,
} from "../BrpCanvas";
import {
  AccessibilityShell,
  MOTION_DISABLED_STORAGE_KEY,
} from "../AccessibilityShell";

// jsdom does not provide WebGL. Mock @react-three/fiber's Canvas so we can
// assert React surface (frameloop, role, aria-hidden) without a real WebGL
// context. Visual validation of the actual Canvas is 4d's Storybook +
// Playwright work.
vi.mock("@react-three/fiber", () => ({
  Canvas: ({
    children,
    frameloop,
    role,
    "aria-hidden": ariaHidden,
  }: {
    children: React.ReactNode;
    frameloop?: string;
    role?: string;
    "aria-hidden"?: boolean | "true" | "false";
  }) => (
    <div
      data-testid="r3f-canvas"
      data-frameloop={frameloop ?? ""}
      data-role={role ?? ""}
      data-aria-hidden={String(ariaHidden ?? "")}
    >
      {children}
    </div>
  ),
}));

// drei's Instances + Instance also need WebGL; mock them as plain divs so the
// AmbientLayer mount in BrpCanvas doesn't blow up.
vi.mock("@react-three/drei", () => ({
  Instances: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="drei-instances">{children}</div>
  ),
  Instance: () => <div data-testid="drei-instance" />,
}));

beforeEach(() => {
  window.localStorage.clear();
  // Default: no OS reduce-motion preference.
  window.matchMedia = ((q: string) => {
    void q;
    return {
      matches: false,
      media: "(prefers-reduced-motion: reduce)",
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => true,
    } as unknown as MediaQueryList;
  }) as typeof window.matchMedia;
});

describe("BrpCanvas — R3F Canvas wrapper React surface", () => {
  const demoBytes = new Uint8Array(32);

  it("T-4b-10: computeFrameloop returns 'demand' when motion is on, 'never' when paused", () => {
    expect(computeFrameloop(false)).toBe("demand");
    expect(computeFrameloop(true)).toBe("never");
  });

  it("T-4b-11: mounts under AccessibilityShell with role='presentation' + aria-hidden='true' on Canvas root", () => {
    render(
      <AccessibilityShell>
        <BrpCanvas frozenOutput={demoBytes} />
      </AccessibilityShell>,
    );
    const canvas = screen.getByTestId("r3f-canvas");
    expect(canvas).toHaveAttribute("data-role", "presentation");
    expect(canvas).toHaveAttribute("data-aria-hidden", "true");
  });

  it("T-4b-12: frameloop='demand' by default; frameloop='never' when motion toggle on", () => {
    const { container } = render(
      <AccessibilityShell>
        <BrpCanvas frozenOutput={demoBytes} />
      </AccessibilityShell>,
    );

    // Default: motion on, frameloop demand.
    expect(screen.getByTestId("r3f-canvas")).toHaveAttribute(
      "data-frameloop",
      "demand",
    );
    expect(
      container.querySelector("[data-brp-canvas]"),
    ).toHaveAttribute("data-frameloop", "demand");
    expect(
      container.querySelector("[data-brp-canvas]"),
    ).toHaveAttribute("data-live", "false");

    // Click photosensitivity toggle; frameloop should flip to "never".
    fireEvent.click(screen.getByTestId("brp-photosensitivity-toggle"));
    expect(screen.getByTestId("r3f-canvas")).toHaveAttribute(
      "data-frameloop",
      "never",
    );
    expect(window.localStorage.getItem(MOTION_DISABLED_STORAGE_KEY)).toBe("1");
  });

  it("T-4b-13: AmbientLayer mounts as a child of Canvas (drei Instances rendered)", () => {
    render(
      <AccessibilityShell>
        <BrpCanvas frozenOutput={demoBytes} />
      </AccessibilityShell>,
    );
    expect(screen.getByTestId("drei-instances")).toBeInTheDocument();
    // 64 instances by default.
    expect(screen.getAllByTestId("drei-instance").length).toBe(64);
  });
});
