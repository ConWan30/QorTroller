import type { Meta, StoryObj } from "@storybook/react";
import { AccessibilityShell, MOTION_DISABLED_STORAGE_KEY } from "../AccessibilityShell";
import { LegibilityOverlay } from "../LegibilityOverlay";
import type { PitlSnapshot } from "../../telemetry/contracts";

const meta: Meta<typeof LegibilityOverlay> = {
  title: "BRP/LegibilityOverlay",
  component: LegibilityOverlay,
  parameters: {
    layout: "fullscreen",
    docs: {
      description: {
        component:
          "Plain-HTML 7-row PITL state panel, position-absolute. role=region + aria-label + data-live=false. aidThreshold gate (placeholder per Block Z).",
      },
    },
  },
};
export default meta;

type Story = StoryObj<typeof LegibilityOverlay>;

const ambientSnapshot: PitlSnapshot = {
  rows: [
    { layer: "L0", inferenceCode: 0x20, active: true, score: 0.55 },
    { layer: "L1", inferenceCode: 0x20, active: true, score: 0.5 },
    { layer: "L2", inferenceCode: 0x20, active: true, score: 0.45 },
    { layer: "L3", inferenceCode: 0x20, active: true, score: 0.4 },
    { layer: "L4", inferenceCode: 0x20, active: true, score: 0.35 },
    { layer: "L5", inferenceCode: 0x20, active: true, score: 0.3 },
    { layer: "L6", inferenceCode: 0x20, active: false, score: 0.25 },
  ],
  snapshotTsNs: 1700000000123456789n,
};

const activeSnapshot: PitlSnapshot = {
  rows: [
    { layer: "L0", inferenceCode: 0x20, active: true, score: 0.92 },
    { layer: "L1", inferenceCode: 0x20, active: true, score: 0.85 },
    { layer: "L2", inferenceCode: 0x20, active: true, score: 0.7 },
    { layer: "L3", inferenceCode: 0x20, active: true, score: 0.55 },
    { layer: "L4", inferenceCode: 0x30, active: true, score: 0.42 },
    { layer: "L5", inferenceCode: 0x20, active: true, score: 0.4 },
    { layer: "L6", inferenceCode: 0x20, active: false, score: 0.3 },
  ],
  snapshotTsNs: 1700000000123456789n,
};

const allActiveSnapshot: PitlSnapshot = {
  rows: [
    { layer: "L0", inferenceCode: 0x20, active: true, score: 0.92 },
    { layer: "L1", inferenceCode: 0x20, active: true, score: 0.91 },
    { layer: "L2", inferenceCode: 0x20, active: true, score: 0.88 },
    { layer: "L3", inferenceCode: 0x20, active: true, score: 0.85 },
    { layer: "L4", inferenceCode: 0x30, active: true, score: 0.95 },
    { layer: "L5", inferenceCode: 0x20, active: true, score: 0.82 },
    { layer: "L6", inferenceCode: 0x20, active: true, score: 0.79 },
  ],
  snapshotTsNs: 1700000000123456789n,
};

function Frame({ children }: { children: React.ReactNode }): JSX.Element {
  return (
    <div style={{ width: "100vw", height: "100vh", background: "#0a0e14" }}>
      <AccessibilityShell>
        <div style={{ position: "relative", width: "100%", height: "100%" }}>
          {children}
        </div>
      </AccessibilityShell>
    </div>
  );
}

export const AmbientMode: Story = {
  parameters: {
    docs: {
      description: {
        story:
          "All scores below aidThreshold=0.65. data-mode='ambient' on the overlay root.",
      },
    },
  },
  render: () => (
    <Frame>
      <LegibilityOverlay pitlSnapshot={ambientSnapshot} aidThreshold={0.65} />
    </Frame>
  ),
};

export const ActiveAidMode: Story = {
  parameters: {
    docs: {
      description: {
        story:
          "L0=0.92 and L1=0.85 exceed aidThreshold=0.65. data-mode='active-aid'; visual treatment shifts to the elevated palette.",
      },
    },
  },
  render: () => (
    <Frame>
      <LegibilityOverlay pitlSnapshot={activeSnapshot} aidThreshold={0.65} />
    </Frame>
  ),
};

export const AllRowsActive: Story = {
  parameters: {
    docs: {
      description: {
        story:
          "Every row exceeds aidThreshold; saturated active-aid display. Useful for visual edge-case verification.",
      },
    },
  },
  render: () => (
    <Frame>
      <LegibilityOverlay pitlSnapshot={allActiveSnapshot} aidThreshold={0.65} />
    </Frame>
  ),
};

export const WithReducedMotion: Story = {
  parameters: {
    docs: {
      description: {
        story:
          "Photosensitivity toggle pre-set so motionShouldPause=true. The overlay's transitions are disabled (transition: none); content remains fully accessible.",
      },
    },
  },
  decorators: [
    (StoryComponent) => {
      if (typeof window !== "undefined") {
        window.localStorage.setItem(MOTION_DISABLED_STORAGE_KEY, "1");
      }
      return <StoryComponent />;
    },
  ],
  render: () => (
    <Frame>
      <LegibilityOverlay pitlSnapshot={activeSnapshot} aidThreshold={0.65} />
    </Frame>
  ),
};
