import { defineConfig } from "vitest/config";

// JSX transform for .tsx test files is handled by esbuild via tsconfig
// "jsx": "react-jsx". The @vitejs/plugin-react plugin is intentionally
// NOT loaded here because vite and vitest's bundled vite ship distinct
// (incompatible) Plugin<any> types — using the plugin under vitest's
// defineConfig produces a TS2769 error. The plugin lives in vite.config.ts
// for dev-server HMR; tests don't need HMR.

export default defineConfig({
  test: {
    globals: true,
    environment: "jsdom",
    include: [
      "src/**/__tests__/**/*.test.ts",
      "src/**/__tests__/**/*.test.tsx",
      "pv-ci-drafts/**/*.spec.ts",
    ],
    setupFiles: ["src/test-setup.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "json"],
      include: ["src/**/*.ts", "src/**/*.tsx"],
      exclude: ["src/**/__tests__/**", "src/main.tsx", "src/test-setup.ts"],
    },
  },
});
