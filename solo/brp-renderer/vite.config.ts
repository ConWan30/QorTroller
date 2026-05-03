import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite build config for the BRP renderer dev surface.
// Track classification: out-of-band-solo. Build output is the dev artifact only;
// integration ceremony will rewire to the protocol monorepo's apps/gamer-portal/
// build pipeline.
export default defineConfig({
  plugins: [react()],
  build: {
    target: "es2022",
    sourcemap: true,
  },
});
