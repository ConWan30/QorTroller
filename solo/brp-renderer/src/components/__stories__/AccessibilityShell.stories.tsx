import type { Meta, StoryObj } from "@storybook/react";
import { AccessibilityShell, MOTION_DISABLED_STORAGE_KEY } from "../AccessibilityShell";

const meta: Meta<typeof AccessibilityShell> = {
  title: "BRP/AccessibilityShell",
  component: AccessibilityShell,
  parameters: {
    layout: "centered",
    docs: {
      description: {
        component:
          "Pure-DOM accessibility primitives. Wraps every BRP surface; provides role=presentation + data-live=false root, sr-only description, prefers-reduced-motion listener, and WCAG 2.2.2 photosensitivity-safety toggle.",
      },
    },
  },
  argTypes: {
    description: {
      control: "text",
      description: "sr-only description text (overrides default)",
    },
  },
};
export default meta;

type Story = StoryObj<typeof AccessibilityShell>;

const placeholderChild = (
  <div
    style={{
      padding: "1rem",
      width: "320px",
      color: "#cce",
      fontFamily: "system-ui, sans-serif",
      fontSize: "0.85rem",
      background: "#0c1320",
      border: "1px solid rgba(90,143,184,0.25)",
      borderRadius: "4px",
    }}
  >
    Children rendered inside the shell. The shell&apos;s root carries{" "}
    <code>role=&quot;presentation&quot;</code> +{" "}
    <code>data-live=&quot;false&quot;</code>; the visible &quot;Motion: ON/OFF&quot; button is the
    WCAG 2.2.2 mechanism.
  </div>
);

export const Default: Story = {
  args: {
    children: placeholderChild,
  },
};

export const WithReducedMotionOSPref: Story = {
  args: {
    children: placeholderChild,
  },
  parameters: {
    docs: {
      description: {
        story:
          "Simulates `prefers-reduced-motion: reduce` at the OS level. The shell's `data-motion-paused` attribute should be `true`. (To exercise: open this story in a browser with the OS setting enabled, or use Chrome DevTools > Rendering > Emulate CSS media feature `prefers-reduced-motion`.)",
      },
    },
  },
};

export const WithUserMotionToggleOff: Story = {
  args: {
    children: placeholderChild,
  },
  parameters: {
    docs: {
      description: {
        story:
          "Simulates the user clicking the photosensitivity-safety toggle. Use the rendered button to flip; localStorage key `brp:motionDisabled` persists the choice across reloads.",
      },
    },
  },
  decorators: [
    (StoryComponent) => {
      // Pre-set the localStorage flag so the story renders in toggled-off state.
      if (typeof window !== "undefined") {
        window.localStorage.setItem(MOTION_DISABLED_STORAGE_KEY, "1");
      }
      return <StoryComponent />;
    },
  ],
};

export const WithBothOnAndOff: Story = {
  args: {
    children: placeholderChild,
  },
  parameters: {
    docs: {
      description: {
        story:
          "Composability matrix: motion pauses if EITHER the OS preference OR the user toggle is set. Exercise via the button + DevTools `prefers-reduced-motion` emulation.",
      },
    },
  },
};
