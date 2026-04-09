import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    open: true,
    proxy: {
      '/api':        { target: 'http://localhost:8080', changeOrigin: true },
      '/agent':      { target: 'http://localhost:8080', changeOrigin: true },
      '/gate':       { target: 'http://localhost:8080', changeOrigin: true },
      '/devices':    { target: 'http://localhost:8080', changeOrigin: true },
      '/proof':      { target: 'http://localhost:8080', changeOrigin: true },
      '/enrollment': { target: 'http://localhost:8080', changeOrigin: true },
      '/curator':    { target: 'http://localhost:8080', changeOrigin: true },
      '/federation': { target: 'http://localhost:8080', changeOrigin: true },
      '/health':     { target: 'http://localhost:8080', changeOrigin: true },
      '/operator':   { target: 'http://localhost:8080', changeOrigin: true },
      '/ws':         { target: 'ws://localhost:8080',   changeOrigin: true, ws: true },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
    rollupOptions: {
      input: {
        main: "index.html",
        twin: "controller-twin.html",
      },
    },
  },
});
