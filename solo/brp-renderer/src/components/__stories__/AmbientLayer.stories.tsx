import type { Meta, StoryObj } from "@storybook/react";
import { Canvas } from "@react-three/fiber";
import { AmbientLayer } from "../AmbientLayer";

const meta: Meta<typeof AmbientLayer> = {
  title: "BRP/AmbientLayer",
  component: AmbientLayer,
  parameters: {
    layout: "centered",
    docs: {
      description: {
        component:
          "Hash-seeded ambient mesh (drei <Instances>). Pure deterministic seedToInstanceParams generates 64 instances from Mulberry32. Bounds: position ∈ [-1,1]³, rotation ∈ [0,2π)³, scale ∈ [0.5,1.5]. Single draw call regardless of count. Story renders inside a real R3F Canvas; visual differences across stories prove the seed→visual chain.",
      },
    },
  },
};
export default meta;

type Story = StoryObj<typeof AmbientLayer>;

function CanvasFrame({ children }: { children: React.ReactNode }): JSX.Element {
  return (
    <div
      style={{
        width: "480px",
        height: "320px",
        background: "#0a0e14",
        borderRadius: "4px",
        overflow: "hidden",
      }}
    >
      <Canvas
        camera={{ position: [0, 0, 3], fov: 45 }}
        role="presentation"
        aria-hidden="true"
      >
        <ambientLight intensity={0.5} />
        <directionalLight position={[2, 2, 2]} intensity={0.8} />
        {children}
      </Canvas>
    </div>
  );
}

export const DefaultSeed: Story = {
  parameters: {
    docs: {
      description: {
        story:
          "Canonical 32-zero-byte input. Locked seed `0x87b0f938` per `deriveBrpSeed.test.ts` canonical-vector test. This visual is the deterministic baseline — every reload should produce the same 64-instance mesh.",
      },
    },
  },
  render: () => (
    <CanvasFrame>
      <AmbientLayer frozenOutput={new Uint8Array(32)} />
    </CanvasFrame>
  ),
};

export const NonDeterministicSeed: Story = {
  parameters: {
    docs: {
      description: {
        story:
          "Seed derived from a different fixed input (deviceId-shaped 32-byte vector). Should look obviously different from DefaultSeed — proves the hash-domain → visual binding.",
      },
    },
  },
  render: () => {
    const bytes = new Uint8Array(32);
    for (let i = 0; i < 32; i++) bytes[i] = (i * 7 + 13) & 0xff;
    return (
      <CanvasFrame>
        <AmbientLayer frozenOutput={bytes} />
      </CanvasFrame>
    );
  },
};

export const Count16: Story = {
  parameters: {
    docs: {
      description: {
        story: "16 instances. Sparse mesh; tests that the count parameter is respected.",
      },
    },
  },
  render: () => (
    <CanvasFrame>
      <AmbientLayer frozenOutput={new Uint8Array(32)} instanceCount={16} />
    </CanvasFrame>
  ),
};

export const Count256: Story = {
  parameters: {
    docs: {
      description: {
        story:
          "256 instances. Dense mesh; still single draw call. Stays well below the < 80 mesh/draw-call budget per PDF §Performance budget because Instances is one mesh.",
      },
    },
  },
  render: () => (
    <CanvasFrame>
      <AmbientLayer frozenOutput={new Uint8Array(32)} instanceCount={256} />
    </CanvasFrame>
  ),
};
