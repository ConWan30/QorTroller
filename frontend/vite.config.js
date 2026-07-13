import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";

/**
 * PKG-UI-04 dogfood path: serve CLI-written ~/.qortroller/ui/* at /stream-ui/*
 * so StreamView can fetch status/stream/ceremony/receipt JSON without a second
 * control plane and without copying files into the repo.
 * Read-only; no auth; never invents LIVE if files are missing (404).
 */
function qortrollerUiStaticPlugin() {
  const uiRoot = path.join(os.homedir(), ".qortroller", "ui");
  const MIME = {
    ".json": "application/json; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".png": "image/png",
    ".md": "text/markdown; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
  };
  return {
    name: "qortroller-ui-static",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = req.url || "";
        if (!url.startsWith("/stream-ui")) return next();
        // Strip querystring; prevent path traversal.
        const rel = decodeURIComponent(url.replace(/^\/stream-ui\/?/, "").split("?")[0]);
        if (!rel || rel.includes("..") || path.isAbsolute(rel)) {
          res.statusCode = 400;
          res.end("bad path");
          return;
        }
        const filePath = path.join(uiRoot, rel);
        if (!filePath.startsWith(uiRoot) || !fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
          res.statusCode = 404;
          res.setHeader("Content-Type", "application/json");
          res.end(JSON.stringify({ error: "missing", path: rel, note: "run qortroller status --write-ui or qortroller ui" }));
          return;
        }
        const ext = path.extname(filePath).toLowerCase();
        res.statusCode = 200;
        res.setHeader("Content-Type", MIME[ext] || "application/octet-stream");
        res.setHeader("Cache-Control", "no-store");
        fs.createReadStream(filePath).pipe(res);
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), qortrollerUiStaticPlugin()],
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
      // Phase O5-PUBLIC-VIEWER — public Forensic Replay-and-Verify
      // sub-app mounted at /public on the bridge. NO auth required;
      // any browser can hit these URLs to verify protocol claims.
      '/public':     { target: 'http://127.0.0.1:8080', changeOrigin: true },
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
