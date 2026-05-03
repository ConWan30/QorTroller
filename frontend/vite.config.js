import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    open: true,
    // Use 127.0.0.1 explicitly — Node on Windows resolves "localhost" to IPv6
    // ::1 first, but the bridge binds IPv4 only (0.0.0.0:8080). Using the
    // IPv4 literal sidesteps that resolution path and the silent 500s it causes.
    proxy: {
      '/api':        { target: 'http://127.0.0.1:8080', changeOrigin: true },
      '/agent':      { target: 'http://127.0.0.1:8080', changeOrigin: true },
      '/bridge':     { target: 'http://127.0.0.1:8080', changeOrigin: true },
      '/gate':       { target: 'http://127.0.0.1:8080', changeOrigin: true },
      '/devices':    { target: 'http://127.0.0.1:8080', changeOrigin: true },
      '/proof':      { target: 'http://127.0.0.1:8080', changeOrigin: true },
      '/enrollment': { target: 'http://127.0.0.1:8080', changeOrigin: true },
      '/curator':    { target: 'http://127.0.0.1:8080', changeOrigin: true },
      '/dash':       { target: 'http://127.0.0.1:8080', changeOrigin: true },
      '/federation': { target: 'http://127.0.0.1:8080', changeOrigin: true },
      '/health':     { target: 'http://127.0.0.1:8080', changeOrigin: true },
      '/operator':   { target: 'http://127.0.0.1:8080', changeOrigin: true },
      '/ws':         { target: 'ws://127.0.0.1:8080',   changeOrigin: true, ws: true },
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
