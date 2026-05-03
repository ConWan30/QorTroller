import type { Meta, StoryObj } from "@storybook/react";
import { AccessibilityShell, MOTION_DISABLED_STORAGE_KEY } from "../AccessibilityShell";
import { BrpCanvas } from "../BrpCanvas";

const meta: Meta<typeof BrpCanvas> = {
  title: "BRP/BrpCanvas",
  component: BrpCanvas,
  parameters: {
    layout: "fullscreen",
    docs: {
      description: {
        component:
          "R3F Canvas wrapper. Consumes motionShouldPause from AccessibilityShell context: frameloop='demand' by default, frameloop='never' when paused. role=presentation + aria-hidden=true on the Canvas root per Block A1.",
      },
    },
  },
};
export default meta;

type Story = StoryObj<typeof BrpCanvas>;

function CanvasFrame({ children }: { children: React.ReactNode }): JSX.Element {
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

export const Default: Story = {
  parameters: {
    docs: {
      description: {
        story:
          "Default mount: frameloop='demand' (renders on telemetry change only). Locked seed `0x87b0f938` from 32-zero-byte canonical vector.",
      },
    },
  },
  render: () => (
    <CanvasFrame>
      <BrpCanvas frozenOutput={new Uint8Array(32)} />
    </CanvasFrame>
  ),
};

export const FrameloopNever: Story = {
  parameters: {
    docs: {
      description: {
        story:
          "Photosensitivity toggle pre-set in localStorage so frameloop initializes to 'never'. The Canvas renders zero frames; the static visual is whatever the first commit produced.",
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
    <CanvasFrame>
      <BrpCanvas frozenOutput={new Uint8Array(32)} />
    </CanvasFrame>
  ),
};

export const Count16: Story = {
  parameters: {
    docs: {
      description: {
        story: "16-instance ambient mesh. Sparse visual; same deterministic seed.",
      },
    },
  },
  render: () => (
    <CanvasFrame>
      <BrpCanvas frozenOutput={new Uint8Array(32)} instanceCount={16} />
    </CanvasFrame>
  ),
};

export const NonDeterministicSeed: Story = {
  parameters: {
    docs: {
      description: {
        story:
          "Different seed bytes. Visual must differ from Default; proves the canvas wrapper passes frozenOutput through to AmbientLayer correctly.",
      },
    },
  },
  render: () => {
    const bytes = new Uint8Array(32);
    for (let i = 0; i < 32; i++) bytes[i] = (i * 7 + 13) & 0xff;
    return (
      <CanvasFrame>
        <BrpCanvas frozenOutput={bytes} />
      </CanvasFrame>
    );
  },
};
