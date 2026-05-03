// Storybook preview config — global decorators + parameters.
//
// Track classification: out-of-band-solo.

import type { Preview } from "@storybook/react";
import { initialize, mswLoader } from "msw-storybook-addon";
import { handlers } from "../src/mocks/handlers";

// Initialize MSW once at preview load. Handlers can be overridden per-story
// via parameters.msw.handlers.
initialize({
  serviceWorker: {
    // Storybook serves /public at root; the SW file lives at /mockServiceWorker.js
    url: "/mockServiceWorker.js",
  },
});

const preview: Preview = {
  parameters: {
    actions: { argTypesRegex: "^on[A-Z].*" },
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/,
      },
    },
    backgrounds: {
      default: "brp-dark",
      values: [
        { name: "brp-dark", value: "#0a0e14" },
        { name: "brp-darker", value: "#020408" },
      ],
    },
    a11y: {
      // Per Block A1 design contract: WebGL canvas is decorative
      // (role=presentation + aria-hidden=true). axe-core's
      // canvas-aria-hidden rule warns about this by default; disable
      // it so the test doesn't flag a deliberate design property.
      // The disable list is asserted in e2e/a11y.spec.ts as a meta-test.
      config: {
        rules: [
          {
            id: "canvas-aria-hidden",
            enabled: false,
          },
        ],
      },
      options: {},
      manual: false,
    },
    msw: {
      handlers,
    },
  },
  loaders: [mswLoader],
};

export default preview;
