import type { Meta, StoryObj } from "@storybook/react";
import { BrpMount } from "../BrpMount";
import { MOTION_DISABLED_STORAGE_KEY } from "../AccessibilityShell";
import {
  getMockEnrollmentSession,
  getMockPitlSnapshot,
} from "../../mocks/loaders";
import type {
  BrpMountProps,
  PitlSnapshot,
  EnrollmentSession,
} from "../../telemetry/contracts";

const meta: Meta<typeof BrpMount> = {
  title: "BRP/BrpMount",
  component: BrpMount,
  parameters: {
    layout: "fullscreen",
    docs: {
      description: {
        component:
          "Top-level public composition. Accepts the full BrpMountProps contract. The 5 stories below cover design PDF §A1's mandated visual states: default ambient / reduced-motion / photosensitivity-toggle-on (≈WithReducedMotion) / telemetry-degraded / enrollment-overlay-active.",
      },
    },
  },
};
export default meta;

type Story = StoryObj<typeof BrpMount>;

const baseSnapshot: PitlSnapshot = getMockPitlSnapshot();
const baseEnrollment: EnrollmentSession = getMockEnrollmentSession();

const baseProps: BrpMountProps = {
  frozenOutput: new Uint8Array(32),
  pitlSnapshot: baseSnapshot,
  aidThreshold: 0.65,
  liveness: { ambient: false, legibility: false, telemetry: false },
};

// --- Variants -----------------------------------------------------------------

const activeAidSnapshot: PitlSnapshot = {
  ...baseSnapshot,
  rows: baseSnapshot.rows.map((r, i) => ({
    ...r,
    score: i === 0 ? 0.95 : r.score,
  })),
};

const degradedSnapshot: PitlSnapshot = {
  ...baseSnapshot,
  rows: baseSnapshot.rows.map((r, i) => ({
    ...r,
    active: i === 0,
    score: i === 0 ? r.score : 0.1,
  })),
};

const credentialedEnrollment: EnrollmentSession = {
  ...baseEnrollment,
  status: "credentialed",
  sessionsNominal: 10,
  avgHumanity: 0.82,
};

const eligibleEnrollment: EnrollmentSession = {
  ...baseEnrollment,
  status: "eligible",
  sessionsNominal: 10,
  avgHumanity: 0.78,
};

// --- Stories ------------------------------------------------------------------

export const DefaultDevSurface: Story = {
  parameters: {
    docs: {
      description: {
        story:
          "Matches `npm run dev` main.tsx surface. Canvas + LegibilityOverlay + EnrollmentBadge mounted under AccessibilityShell.",
      },
    },
  },
  render: () => (
    <BrpMount {...baseProps} enrollmentSession={baseEnrollment} />
  ),
};

export const EnrollmentEligible: Story = {
  parameters: {
    docs: {
      description: {
        story: "EnrollmentSession.status='eligible'. Badge shows progress 100% / status=eligible.",
      },
    },
  },
  render: () => (
    <BrpMount {...baseProps} enrollmentSession={eligibleEnrollment} />
  ),
};

export const EnrollmentCredentialed: Story = {
  parameters: {
    docs: {
      description: {
        story:
          "EnrollmentSession.status='credentialed'. Mount is fully decorated; visualization claims `data-status=credentialed` for downstream auditors.",
      },
    },
  },
  render: () => (
    <BrpMount {...baseProps} enrollmentSession={credentialedEnrollment} />
  ),
};

export const TelemetryDegraded: Story = {
  parameters: {
    docs: {
      description: {
        story:
          "PitlSnapshot with only L0 active; rest degraded. The legibility overlay shows muted rows for inactive layers per `opacity: row.active ? 1 : 0.4` rule.",
      },
    },
  },
  render: () => (
    <BrpMount
      {...baseProps}
      pitlSnapshot={degradedSnapshot}
      enrollmentSession={baseEnrollment}
    />
  ),
};

export const FullActiveAid: Story = {
  parameters: {
    docs: {
      description: {
        story:
          "Active-aid mode triggered: at least one PITL row exceeds aidThreshold. Combined with reduced-motion preset to verify that aria-label + role=region remain stable across visual treatment changes.",
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
    <BrpMount
      {...baseProps}
      pitlSnapshot={activeAidSnapshot}
      enrollmentSession={credentialedEnrollment}
    />
  ),
};
