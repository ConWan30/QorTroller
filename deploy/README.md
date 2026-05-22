# QorTroller — production deployment wiring

In **development**, `frontend/vite.config.js` proxies the bridge prefixes
(`/operator /public /api /agent /bridge /gate /devices /proof /enrollment
/curator /dash /federation /health /ws`) to the bridge at `127.0.0.1:8080`, so
the frontend's **relative** API paths "just work".

In **production** there's no Vite dev server. The built frontend still issues
relative paths (e.g. `apiGet('/operator/bridge/capture-health')`), so those
paths must reach the bridge **same-origin**. Two supported ways:

## Option A — reverse proxy (recommended)

A single front door serves the built frontend and forwards the bridge prefixes
to `:8080`. Configs provided:

- **`Caddyfile`** — simplest; automatic HTTPS. `caddy run --config deploy/Caddyfile`
- **`nginx.conf`** — drop-in `server {}` block.

Steps:

```bash
cd frontend && npm run build          # → frontend/dist
# point the config's root at frontend/dist (edit /srv/qortroller/... )
python -m bridge.vapi_bridge.main     # bridge binds 0.0.0.0:8080
caddy run --config deploy/Caddyfile   # or: nginx -c .../deploy/nginx.conf
```

Both proxy the **exact prefix set** the frontend uses (kept in sync with
`vite.config.js`) and upgrade `/ws` for the 3D-twin WebSocket stream. Everything
else is served from `dist/` with SPA fallback to `index.html` (so client routes
like `/os/evidence` and `/session/:hash` resolve), while the self-contained
pages — `controller-twin.html`, `grant-brief.html`, `qortroller-reference.html`,
`/assets/*`, `/fonts/*`, `/deck-stage.js` — are served directly.

## Option B — bridge serves the built `dist/` (single process)

If you'd rather not run a separate proxy, the bridge can mount the built
frontend itself (everything from one process, relative paths same-origin). This
is **not yet wired** — it needs a `StaticFiles` mount registered **after** all
API routes/mounts in `bridge/vapi_bridge/main.py`, plus an SPA fallback to
`index.html`, gated behind a config flag (e.g. `SERVE_FRONTEND_DIST`). Ask and
it'll be added + verified against the bridge test suite. Lower-infra, but it
couples the bridge to the frontend build and needs careful mount ordering so it
never shadows `/operator`, `/public`, `/api`, etc.

## ⚠ Security — the operator API key is baked into the build

`client.js` reads `VITE_VAPI_API_KEY` at **build time** and attaches it as
`x-api-key` on every request, so it ends up in the shipped JS bundle. The
operator/agent endpoints require that key.

- For a **public / grant-evaluator** deploy, do **not** ship the operator key:
  the `/public/*` routes (Public Forensic Explorer, the public viewers) need no
  key, and the **Grant Brief** + **Reference** tabs are self-contained — those
  work key-less. Operator/Gamer/Forensic/VPM live data needs the bridge + key.
- For an **operator** deploy, build with the key but put it behind its own auth
  (VPN / SSO / a separate host) — never on a public origin.

A cleaner long-term fix is a tiny server-side token-exchange (the proxy injects
`x-api-key` from a server-held secret so the key never reaches the browser);
note this for a future hardening pass.
