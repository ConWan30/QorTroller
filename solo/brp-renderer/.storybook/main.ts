// Storybook 8 config — out-of-band-solo dev surface visual validation.
//
// Track classification: out-of-band-solo. NOT Phase 241. NOT in the sequential
// VAPI protocol chain.
//
// Framework: @storybook/react-vite (Vite 6 compatible).
// Stories live alongside their components in src/components/__stories__/.

import type { StorybookConfig } from "@storybook/react-vite";

const config: StorybookConfig = {
  stories: ["../src/**/*.stories.@(ts|tsx|mdx)"],
  addons: [
    "@storybook/addon-essentials",
    "@storybook/addon-a11y",
    "msw-storybook-addon",
  ],
  framework: {
    name: "@storybook/react-vite",
    options: {},
  },
  staticDirs: ["../public"],
  typescript: {
    check: false, // tsc runs separately via `npm run test`
    reactDocgen: "react-docgen-typescript",
  },
  docs: {
    autodocs: false,
  },
};

export default config;
