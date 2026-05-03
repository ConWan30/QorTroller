import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { BrpMount } from "../BrpMount";
import type { BrpMountProps, PitlSnapshot } from "../../telemetry/contracts";

// Mock R3F + drei: jsdom has no WebGL.
vi.mock("@react-three/fiber", () => ({
  Canvas: ({
    children,
    role,
    "aria-hidden": ariaHidden,
  }: {
    children: React.ReactNode;
    role?: string;
    "aria-hidden"?: boolean | "true" | "false";
  }) => (
    <div data-testid="r3f-canvas" data-role={role} data-aria-hidden={String(ariaHidden ?? "")}>
      {children}
    </div>
  ),
}));

vi.mock("@react-three/drei", () => ({
  Instances: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="drei-instances">{children}</div>
  ),
  Instance: () => <div data-testid="drei-instance" />,
}));

beforeEach(() => {
  window.localStorage.clear();
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

const SNAPSHOT: PitlSnapshot = {
  rows: [
    { layer: "L0", inferenceCode: 0x20, active: true, score: 0.9 },
    { layer: "L1", inferenceCode: 0x20, active: true, score: 0.8 },
    { layer: "L2", inferenceCode: 0x20, active: true, score: 0.7 },
    { layer: "L3", inferenceCode: 0x20, active: true, score: 0.6 },
    { layer: "L4", inferenceCode: 0x30, active: true, score: 0.5 },
    { layer: "L5", inferenceCode: 0x20, active: true, score: 0.4 },
    { layer: "L6", inferenceCode: 0x20, active: false, score: 0.3 },
  ],
  snapshotTsNs: 1700000000000000000n,
};

const BASE_PROPS: BrpMountProps = {
  frozenOutput: new Uint8Array(32),
  pitlSnapshot: SNAPSHOT,
  aidThreshold: 0.65,
  liveness: { ambient: false, legibility: false, telemetry: false },
};

describe("BrpMount — top-level public composition", () => {
  it("T-4c-mount-1: renders all required children (shell + canvas + overlay)", () => {
    render(<BrpMount {...BASE_PROPS} />);
    // AccessibilityShell renders the photosensitivity toggle.
    expect(screen.getByTestId("brp-photosensitivity-toggle")).toBeInTheDocument();
    // BrpCanvas wrapper.
    expect(screen.getByTestId("brp-canvas-wrapper")).toBeInTheDocument();
    // R3F mocked canvas.
    expect(screen.getByTestId("r3f-canvas")).toBeInTheDocument();
    // LegibilityOverlay.
    expect(
      screen.getByRole("region", { name: /calibration legibility overlay/i }),
    ).toBeInTheDocument();
    // BrpMount root carries data-live=false and explicit liveness attrs.
    const root = screen.getByTestId("brp-mount-root");
    expect(root).toHaveAttribute("data-live", "false");
    expect(root).toHaveAttribute("data-liveness-ambient", "false");
    expect(root).toHaveAttribute("data-liveness-legibility", "false");
    expect(root).toHaveAttribute("data-liveness-telemetry", "false");
  });

  it("T-4c-mount-2: enrollmentSession optional — when omitted, no enrollment badge", () => {
    render(<BrpMount {...BASE_PROPS} />);
    expect(screen.queryByTestId("brp-enrollment-badge")).toBeNull();
  });

  it("T-4c-mount-3: enrollmentSession provided — enrollment badge rendered with status + progress", () => {
    render(
      <BrpMount
        {...BASE_PROPS}
        enrollmentSession={{
          deviceId: "0xabc",
          sessionsNominal: 7,
          avgHumanity: 0.74,
          status: "pending",
          requiredSessions: 10,
          requiredHumanity: 0.6,
        }}
      />,
    );
    expect(screen.getByTestId("brp-enrollment-badge")).toBeInTheDocument();
    expect(screen.getByTestId("enrollment-status")).toHaveTextContent("pending");
    expect(screen.getByTestId("enrollment-progress")).toHaveTextContent(
      "7 / 10 nominal · 70%",
    );
  });

  it("T-4c-mount-4: aidThreshold passes through to LegibilityOverlay (active mode at low threshold)", () => {
    // With aidThreshold=0.5, three rows in SNAPSHOT exceed it (L0=0.9, L1=0.8, L2=0.7, L3=0.6).
    // Wait — L3=0.6 > 0.5 too. So active-aid mode.
    render(<BrpMount {...BASE_PROPS} aidThreshold={0.5} />);
    expect(
      screen.getByRole("region", { name: /calibration legibility overlay/i }),
    ).toHaveAttribute("data-mode", "active-aid");

    // Cleanup: re-render with high threshold → ambient.
  });

  it("T-4c-mount-5: liveness flags propagate to data-* attributes (any-true → data-live=true)", () => {
    render(
      <BrpMount
        {...BASE_PROPS}
        liveness={{ ambient: true, legibility: false, telemetry: false }}
      />,
    );
    const root = screen.getByTestId("brp-mount-root");
    expect(root).toHaveAttribute("data-live", "true");
    expect(root).toHaveAttribute("data-liveness-ambient", "true");
    expect(root).toHaveAttribute("data-liveness-legibility", "false");
    expect(root).toHaveAttribute("data-liveness-telemetry", "false");
  });
});
