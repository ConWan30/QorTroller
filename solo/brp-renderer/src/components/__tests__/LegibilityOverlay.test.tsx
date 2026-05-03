import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  LegibilityOverlay,
  isActiveAidMode,
} from "../LegibilityOverlay";
import { AccessibilityShell } from "../AccessibilityShell";
import type { PitlRow, PitlSnapshot } from "../../telemetry/contracts";

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

function makeRow(
  layer: PitlRow["layer"],
  inferenceCode: number,
  score: number,
  active = true,
): PitlRow {
  return { layer, inferenceCode, active, score };
}

function makeSnapshot(rows: readonly PitlRow[]): PitlSnapshot {
  return { rows, snapshotTsNs: 1700000000123456789n };
}

describe("LegibilityOverlay — calibration-aid HUD", () => {
  it("T-4c-overlay-1: renders one entry per PITL row", () => {
    const snap = makeSnapshot([
      makeRow("L0", 0x20, 0.9),
      makeRow("L1", 0x20, 0.85),
      makeRow("L2", 0x20, 0.7),
      makeRow("L3", 0x20, 0.6),
      makeRow("L4", 0x30, 0.4),
      makeRow("L5", 0x20, 0.55),
      makeRow("L6", 0x20, 0.5, false),
    ]);
    render(
      <AccessibilityShell>
        <LegibilityOverlay pitlSnapshot={snap} aidThreshold={0.65} />
      </AccessibilityShell>,
    );
    for (const layer of ["L0", "L1", "L2", "L3", "L4", "L5", "L6"]) {
      expect(screen.getByTestId(`overlay-row-${layer}`)).toBeInTheDocument();
    }
  });

  it("T-4c-overlay-2: aria-label, role=region, data-live=false on the overlay root", () => {
    const snap = makeSnapshot([makeRow("L0", 0x20, 0.5)]);
    render(
      <AccessibilityShell>
        <LegibilityOverlay pitlSnapshot={snap} aidThreshold={0.65} />
      </AccessibilityShell>,
    );
    const region = screen.getByRole("region", {
      name: /calibration legibility overlay/i,
    });
    expect(region).toHaveAttribute("data-live", "false");
    expect(region).toHaveAttribute("data-brp-overlay", "true");
  });

  it("T-4c-overlay-3: ambient mode when no row exceeds aidThreshold", () => {
    const snap = makeSnapshot([
      makeRow("L0", 0x20, 0.5),
      makeRow("L1", 0x20, 0.4),
    ]);
    render(
      <AccessibilityShell>
        <LegibilityOverlay pitlSnapshot={snap} aidThreshold={0.65} />
      </AccessibilityShell>,
    );
    const region = screen.getByRole("region", {
      name: /calibration legibility overlay/i,
    });
    expect(region).toHaveAttribute("data-mode", "ambient");
    expect(screen.getByTestId("overlay-mode-label")).toHaveTextContent("AMBIENT");
  });

  it("T-4c-overlay-4: active-aid mode when at least one row exceeds aidThreshold", () => {
    const snap = makeSnapshot([
      makeRow("L0", 0x20, 0.5),
      makeRow("L4", 0x30, 0.92), // exceeds 0.65
    ]);
    render(
      <AccessibilityShell>
        <LegibilityOverlay pitlSnapshot={snap} aidThreshold={0.65} />
      </AccessibilityShell>,
    );
    const region = screen.getByRole("region", {
      name: /calibration legibility overlay/i,
    });
    expect(region).toHaveAttribute("data-mode", "active-aid");
    expect(screen.getByTestId("overlay-mode-label")).toHaveTextContent(/ACTIVE AID/);
    expect(screen.getByTestId("overlay-row-L4")).toHaveAttribute(
      "data-above-threshold",
      "true",
    );
    expect(screen.getByTestId("overlay-row-L0")).toHaveAttribute(
      "data-above-threshold",
      "false",
    );
  });

  it("T-4c-overlay-5: snapshot timestamp last-9-digits surfaced; full value in title", () => {
    const snap = makeSnapshot([makeRow("L0", 0x20, 0.5)]);
    render(
      <AccessibilityShell>
        <LegibilityOverlay pitlSnapshot={snap} aidThreshold={0.65} />
      </AccessibilityShell>,
    );
    const ts = screen.getByTestId("overlay-snapshot-ts");
    // Last 9 digits of 1700000000123456789 = "123456789"
    expect(ts).toHaveTextContent("…123456789");
    expect(ts).toHaveAttribute("title", "snapshotTsNs=1700000000123456789");
  });

  it("T-4c-overlay-6: pure helper isActiveAidMode handles missing scores as 0", () => {
    expect(isActiveAidMode([], 0.5)).toBe(false);
    expect(
      isActiveAidMode([{ layer: "L0", inferenceCode: 0x20, active: true }], 0.5),
    ).toBe(false);
    expect(
      isActiveAidMode(
        [{ layer: "L0", inferenceCode: 0x20, active: true, score: 0.51 }],
        0.5,
      ),
    ).toBe(true);
    expect(
      isActiveAidMode(
        [{ layer: "L0", inferenceCode: 0x20, active: true, score: 0.5 }],
        0.5,
      ),
    ).toBe(false); // strictly greater
  });
});
