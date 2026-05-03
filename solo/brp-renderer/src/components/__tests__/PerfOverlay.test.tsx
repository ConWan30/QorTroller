import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render } from "@testing-library/react";

// Mock @react-three/drei PerformanceMonitor so jsdom doesn't try to use WebGL.
// The mock renders children + the marker so DOM assertions can verify
// data-perf-factor + data-brp-perf-overlay propagate.
vi.mock("@react-three/drei", () => ({
  PerformanceMonitor: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="perf-monitor-mock">{children}</div>
  ),
}));

beforeEach(() => {
  // vi.stubEnv is vitest's canonical way to mock import.meta.env.
  // Force DEV=true so the component body executes for tests that need it.
  vi.stubEnv("DEV", true);
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("PerfOverlay — dev-only PerformanceMonitor wrapper", () => {
  it("T-4d-perf-1: renders nothing when DEV is false (prod tree-shake guard)", async () => {
    vi.stubEnv("DEV", false);
    const { PerfOverlay } = await import("../PerfOverlay");
    const { container } = render(<PerfOverlay />);
    expect(container.firstChild).toBeNull();
  });

  it("T-4d-perf-2: renders the data-brp-perf-overlay marker when DEV is true", async () => {
    const { PerfOverlay } = await import("../PerfOverlay");
    const { container } = render(<PerfOverlay />);
    // PerformanceMonitor mock wraps children; marker is inside.
    const marker = container.querySelector("[data-brp-perf-overlay]");
    expect(marker).not.toBeNull();
    expect(marker).toHaveAttribute("data-perf-factor");
    // Initial factor is 1.000 per the component.
    expect(marker?.getAttribute("data-perf-factor")).toBe("1.000");
  });

  it("T-4d-perf-3: forwards children alongside the marker", async () => {
    const { PerfOverlay } = await import("../PerfOverlay");
    const { container, getByTestId } = render(
      <PerfOverlay>
        <div data-testid="perf-child">child content</div>
      </PerfOverlay>,
    );
    expect(getByTestId("perf-child")).toBeInTheDocument();
    expect(container.querySelector("[data-brp-perf-overlay]")).not.toBeNull();
  });
});
