# Frontend Connectivity Verification — Phase O0 Pause Period

**Date**: 2026-04-29
**Session character**: Read-only static analysis. No files modified, no servers run, no state changed.
**Verification result**: 26 of 26 active frontend endpoint calls match real bridge endpoints. Zero PATH_MISMATCH, METHOD_MISMATCH, REQUEST_SHAPE_MISMATCH, RESPONSE_SHAPE_MISMATCH, or AUTH_MISMATCH detected.

This document preserves the read-only static analysis verification confirming
that frontend-backend connectivity was structurally clean as of 2026-04-29.
It serves as a reference document for future operators, future Claude Code
sessions, and external auditors examining the protocol's state.

---

## Section 1 — Frontend code inventory

| File | Role | HTTP pattern | Base URL source |
|---|---|---|---|
| `frontend/src/api/client.js` | Central API wrapper. `apiGet()` / `apiPost()` with `x-api-key` header + `api_key` query param + Phase 236-VAME sidecar validation. | native `fetch` | `import.meta.env.VITE_VAPI_API_KEY` (key only); host implicit via Vite proxy |
| `frontend/src/api/bridgeApi.js` | React-Query hooks for 17 bridge endpoints. Uses `_OP_PREFIX = '/operator'` to mount paths onto operator sub-app. | wraps `apiGet` | inherited |
| `frontend/src/api/mockBridge.js` | First-load fallback when bridge unreachable. `noMock: true` on grind-critical hooks suppresses it. | n/a | n/a |
| `frontend/src/api/vame.js` | VAME sidecar header validator. | n/a | n/a |
| `frontend/src/components/ConsentPanel.jsx` | UI for consent grant/revoke. Reads `useConsentStatus`, writes via wagmi (`useConsentSubmit`). | wagmi `useWriteContract` | `VITE_CONSENT_REGISTRY_ADDRESS` |
| `frontend/src/heartbeat/HeartbeatProvider.jsx` | Pulses heartbeat from `useProtocolCoherence`. | wraps bridgeApi | inherited |
| `frontend/src/views/{Gamer,Developer,Manufacturer}View.jsx` | The three active SPA views. Consume bridgeApi hooks only — no direct fetches. | wraps bridgeApi | inherited |
| `frontend/src/legacy/ControllerTwin.jsx` | 3D twin view rendered via iframe in GamerView (`<iframe src="/controller-twin.html?minimal=1">`). Direct `fetch` to bridge. | native `fetch` | `params.get('bridge') \|\| '127.0.0.1:8080'` (URL query param fallback to literal) |
| `frontend/controller-twin.html` | 14-line HTML shell that loads `src/legacy/ControllerTwin.jsx`. | n/a | n/a |
| `frontend/src/shared/api/endpoints.js` | "Single source of truth" `EP.*` constants + `apiFetch()` helper using **api_key as query param ONLY** (no header). | native `fetch` | n/a |
| `frontend/src/shared/api/hooks/index.js` | Wraps `apiFetch` + `EP.*` into react-query hooks. | wraps `apiFetch` | inherited |
| `frontend/src/shared/components/index.jsx` | Has a `fetch('/health')` call. | native `fetch` | Vite proxy |
| `frontend/src/hooks/useConsentSubmit.js` | wagmi-write hook for `VAPIConsentRegistry`. | n/a (wallet) | `VITE_CONSENT_REGISTRY_ADDRESS` env |
| `frontend/vite.config.js` | Vite proxy: `/api`, `/agent`, `/bridge`, `/gate`, `/devices`, `/proof`, `/enrollment`, `/curator`, `/federation`, `/health`, `/operator`, `/ws` all → `http://127.0.0.1:8080`. | n/a | hardcoded |

**Two parallel client patterns coexist**:
- **`api/client.js` + `api/bridgeApi.js`** — modern central client. Header + query param auth. Used by all 3 active views and ConsentPanel/HeartbeatProvider.
- **`shared/api/endpoints.js` + `shared/api/hooks/index.js` + `shared/components/index.jsx`** — older "single source of truth" client. Query-param-only auth. **ZERO active imports** in the SPA tree (App.jsx → ViewSelector + 3 views, none of which import these modules).

## Section 2 — Frontend endpoint usage catalog

### Active SPA paths (via `api/bridgeApi.js`)

All hooks call `get('/path', mockKey, opts)` which prepends `/operator` and dispatches to `apiGet()` with `x-api-key` header + `api_key` query param. Final URL = `/operator{path}`.

| Hook (file:line) | HTTP | Path called (after /operator prefix) | Auth |
|---|---|---|---|
| `useProtocolCoherence` (bridgeApi.js:44) | GET | `/operator/agent/protocol-coherence-status` | x-api-key + ?api_key |
| `useTournamentBlockerSummary` (:53) | GET | `/operator/agent/tournament-blocker-summary` | same |
| `usePerPairGapStatus` (:62) | GET | `/operator/agent/per-pair-gap-status` | same |
| `usePerPairGapProjection` (:71) | GET | `/operator/agent/per-pair-gap-projection` | same |
| `useSeparationDefensibility` (:80) | GET | `/operator/agent/separation-defensibility-status` | same |
| `useInvariantGateStatus` (:89) | GET | `/operator/agent/invariant-gate-status` | same |
| `useFleetCoherenceStatus` (:101) | GET | `/operator/agent/fleet-coherence-summary` | same |
| `useCaptureVelocityOracle` (:125) | GET | `/operator/agent/capture-velocity-oracle` | same |
| `useTournamentPreflight` (:134) | GET | `/operator/agent/tournament-preflight-status` | same |
| `useAutoTriggerStatus` (:146) | GET | `/operator/agent/auto-trigger-status` | same |
| `useCaptureHealth` (:161) | GET | `/operator/bridge/capture-health` | same |
| `useGrindChain` (:171) | GET | `/operator/bridge/grind-chain-status` | same |
| `useAITSeparation` (:184) | GET | `/operator/agent/ait-separation-status` | same |
| `useGrindAnalytics` (:197) | GET | `/operator/grind/analytics` | same |
| `usePCCIntelligence` (:210) | GET | `/operator/grind/pcc-intelligence` | same |
| `useWatchdogStatus` (:223) | GET | `/operator/operator/watchdog-status` | same |
| `useConsentStatus` (:244) | GET | `/operator/agent/gamer-consent-status?device_id=...&category=...` | same |

### Iframe-loaded ControllerTwin (`legacy/ControllerTwin.jsx`)

Direct `fetch(\`http://${BRIDGE_URL}{path}\`)` where `BRIDGE_URL = '127.0.0.1:8080'`. **No auth headers, no query param key**.

| Line | HTTP | Path | Auth |
|---|---|---|---|
| :59 | GET | `/api/v1/devices` | none |
| :91 | WS | `ws://.../ws/twin/{deviceId}` | none |
| :123 | GET | `/controller/twin/{deviceId}` | none |
| :125 | GET | `/controller/twin/{deviceId}/chain?limit=50` | none |
| :145 | GET | `/controller/twin/{deviceId}/checkpoints?limit=200` | none |
| :152 | GET | `/controller/twin/{deviceId}/replay?record_hash=...` | none |
| :200 | GET | `/controller/twin/{deviceId}/features?limit=50` | none |
| :245 | GET | `/agent/rulings/{deviceId}` | none |

### Isolated singleton fetches

| File:line | HTTP | Path | Auth |
|---|---|---|---|
| `shared/components/index.jsx:20` | GET | `/health` | none |

### Stale (zero active imports — dead code)

`shared/api/endpoints.js` defines 25+ `EP.*` constants and an `apiFetch()` helper. `shared/api/hooks/index.js` wraps them. **Neither is imported by any reachable file in the active SPA tree** (App.jsx → 3 views → bridgeApi.js → client.js). Listed for completeness but excluded from the cross-reference.

## Section 3 — Bridge endpoint inventory

**Total: 193 unique endpoints** in `bridge/vapi_bridge/operator_api.py` (the operator sub-app mounted at `/operator` per `main.py:444`).

Plus separate sub-apps and main-app endpoints:
- `bridge/vapi_bridge/transports/http.py`: `/api/v1/devices` (line 307), `/controller/twin/{device_id}*` (lines 739, 744, 756, 766, 772), `/agent/rulings/{device_id}` (line 847), `/ws/records`, `/ws/frames`, `/ws/twin/{device_id}` (lines 230, 248, 797). Mounted on the **main app** (root path).
- `bridge/vapi_bridge/dashboard_api.py`: 10 `/api/v1/...` paths (lines 53-223) + `/proof/{device_id}` (line 248). **Mounted at `/dash` per main.py:433** — actual paths are `/dash/api/v1/...`.
- `/health` — main app (`@app.get("/health")` in operator_api.py:281, but the operator sub-app's `/health` is at `/operator/health`; main app also has its own).

Authentication shapes:
- Operator full-key (`Depends(_check_key)` or `api_key: str = Query(...)`): writes + sensitive reads
- Operator read-key (`x_api_key: str = Header(default="")` + `_check_read_key(x_api_key)`): all `/agent/*-status` reads — fail-open when `OPERATOR_API_KEY` env unset
- Agent token (`Depends(_check_agent_token)`, Stream 4-prep Session 2): the 5 Phase O0 endpoints `/agent/agent-commit-history`, `/agent/agent-commit-status`, `/agent/physical-data-attestation-history`, `/agent/physical-data-attestation-status`, `/agent/agent-registry-status`
- Public (no auth): `/health`, `/api/v1/devices`, `/controller/twin/*`, `/agent/rulings/*`, dashboard `/dash/api/v1/*`, `/proof/*`

## Section 4 — Cross-reference matching

### CLEAN connections (26)

| # | Frontend call | Bridge endpoint (verified) |
|---|---|---|
| 1 | `useProtocolCoherence` → `/operator/agent/protocol-coherence-status` | operator_api.py `@app.get("/agent/protocol-coherence-status")` ✓ |
| 2 | `useTournamentBlockerSummary` | `@app.get("/agent/tournament-blocker-summary")` ✓ |
| 3 | `usePerPairGapStatus` | `@app.get("/agent/per-pair-gap-status")` ✓ |
| 4 | `usePerPairGapProjection` | `@app.get("/agent/per-pair-gap-projection")` ✓ |
| 5 | `useSeparationDefensibility` | `@app.get("/agent/separation-defensibility-status")` ✓ |
| 6 | `useInvariantGateStatus` | `@app.get("/agent/invariant-gate-status")` ✓ |
| 7 | `useFleetCoherenceStatus` → `/agent/fleet-coherence-summary` | `@app.get("/agent/fleet-coherence-summary")` ✓ (response shape adapted in hook) |
| 8 | `useCaptureVelocityOracle` | `@app.get("/agent/capture-velocity-oracle")` ✓ |
| 9 | `useTournamentPreflight` | `@app.get("/agent/tournament-preflight-status")` ✓ |
| 10 | `useAutoTriggerStatus` | `@app.get("/agent/auto-trigger-status")` (line 7595) ✓ |
| 11 | `useCaptureHealth` → `/operator/bridge/capture-health` | `@app.get("/bridge/capture-health")` ✓ |
| 12 | `useGrindChain` → `/operator/bridge/grind-chain-status` | `@app.get("/bridge/grind-chain-status")` ✓ |
| 13 | `useAITSeparation` | `@app.get("/agent/ait-separation-status")` ✓ |
| 14 | `useGrindAnalytics` → `/operator/grind/analytics` | `@app.get("/grind/analytics")` ✓ |
| 15 | `usePCCIntelligence` → `/operator/grind/pcc-intelligence` | `@app.get("/grind/pcc-intelligence")` ✓ |
| 16 | `useWatchdogStatus` → `/operator/operator/watchdog-status` | `@app.get("/operator/watchdog-status")` (in operator sub-app, so post-mount it is `/operator/operator/...`) ✓ |
| 17 | `useConsentStatus` → `/operator/agent/gamer-consent-status` | `@app.get("/agent/gamer-consent-status")` ✓ |
| 18 | ControllerTwin `/api/v1/devices` | transports/http.py:307 ✓ |
| 19 | ControllerTwin `/ws/twin/{id}` | transports/http.py:797 ✓ |
| 20 | ControllerTwin `/controller/twin/{id}` | transports/http.py:739 ✓ |
| 21 | ControllerTwin `/controller/twin/{id}/chain` | transports/http.py:744 ✓ |
| 22 | ControllerTwin `/controller/twin/{id}/checkpoints` | transports/http.py:766 ✓ |
| 23 | ControllerTwin `/controller/twin/{id}/replay` | transports/http.py:756 ✓ |
| 24 | ControllerTwin `/controller/twin/{id}/features` | transports/http.py:772 ✓ |
| 25 | ControllerTwin `/agent/rulings/{id}` | transports/http.py:847 ✓ |
| 26 | shared/components/index.jsx `/health` | `@app.get("/health")` (multiple, e.g. operator_api.py:281, main.py routes) ✓ |

**26 of 26 active frontend endpoint calls match a real bridge endpoint.** Zero PATH_MISMATCH, METHOD_MISMATCH, REQUEST_SHAPE_MISMATCH, RESPONSE_SHAPE_MISMATCH, or AUTH_MISMATCH detected for ACTIVE code paths.

### Notes on apparent (resolved) mismatches

- `useFleetCoherenceStatus` calls `/agent/fleet-coherence-summary` and adapts `by_mode` dict → `active_*` field names (bridgeApi.js:108-116). The hook docstring confirms this was a Phase 235-AUDIT fix from a prior `/agent/fleet-coherence-status` (404) bug. Currently CLEAN.
- `useWatchdogStatus` calls `/operator/watchdog-status` which after the `/operator` prefix becomes `/operator/operator/watchdog-status`. The double-prefix is intentional — the FastAPI route is literally `@app.get("/operator/watchdog-status")` *inside* the operator sub-app. CLEAN.

### ORPHAN_FRONTEND (0)

None.

### ORPHAN_BACKEND — Intentionally non-frontend (categories)

The bridge has 193 operator endpoints. The frontend uses 17 of them. The remaining ~176 operator endpoints + the `/api/v1/...` dashboard endpoints + several main-app routes are NOT consumed by the frontend, but most are intentionally non-frontend:

- **Agent-token-gated** (5 Phase O0 endpoints — see Section 8)
- **Operator write actions** (POST `/agent/commit-activation`, `/agent/mint-vhp`, `/operator/force-corpus-snapshot`, etc.) — meant for operator scripts/curl, not dashboard buttons
- **Internal agent triggers** (`/agent/run-tournament-preflight`, `/agent/run-invariant-gate`, etc.)
- **Long-tail audit endpoints** (`/agent/coherence-fingerprint-status`, `/agent/biometric-stationarity-status`, etc.) — visibility for protocol researchers, not the gamer/developer/manufacturer dashboards
- **Per-device queries** (`/agent/vhp-status/{device_id}`, `/curator/data-lineage/{device_id}`) — would need device-id selection UX before integration

### ORPHAN_BACKEND — Frontend coverage gaps (potential UX value)

Endpoints where the dashboards would arguably benefit from integration but currently have none:
- `/agent/auto-trigger-status` — actually IS consumed (`useAutoTriggerStatus`); listed in CLEAN.
- `/operator/watchdog-status` — IS consumed (`useWatchdogStatus`); CLEAN.
- `/agent/fleet-coherence-history` and `/agent/fleet-coherence-entries` — frontend uses summary only; history endpoints would feed a "what changed since last refresh" panel
- `/agent/data-provenance-chain` — DataCuratorAgent's hop-walk; would feed a Developer-view audit panel
- `/agent/protocol-maturity-score` — single number that would fit a top-level header chip in DeveloperView
- `/agent/biometric-credential-age` — would surface in a per-device profile drawer
- `/grind/session-history` — historical view of GIC stamps; would feed a "session log" tab in DeveloperView

These are **opportunity gaps**, not bugs. Frontend works fine without them.

## Section 5 — Authentication coverage analysis

**Active SPA path** (`api/client.js`): correctly attaches `x-api-key` header AND `api_key` query param on every request. Matches operator_api.py's `_check_key` (Query) and `_check_read_key` (Header) patterns — both auth flavors satisfied simultaneously.

**ControllerTwin.jsx** (legacy iframe): zero auth headers, zero query params. The bridge endpoints it calls (`/api/v1/devices`, `/controller/twin/*`, `/agent/rulings/*`) are public (no `_check_key` / `_check_read_key` dependency). CLEAN — the public endpoints don't require auth.

**`shared/api/endpoints.js`** (dead code): `apiFetch()` attaches `api_key` as query param only, no header. If ever revived, it would still work for endpoints that accept `api_key` Query but FAIL for endpoints that only accept `x-api-key` Header. Currently moot since dead code.

**Phase O0 agent-token endpoints** (`/agent/agent-commit-*`, `/agent/physical-data-attestation-*`, `/agent/agent-registry-status`): require `Authorization: Bearer <JWT>` + `X-Agent-KeyId` + `X-Timestamp` + `X-Nonce` + `X-Signature` (Stream 4-prep Session 2). **Frontend has zero integration with this auth scheme.** Confirmed by grep — no `Bearer`, `X-Agent-KeyId`, `X-Timestamp`, `X-Nonce`, `X-Signature` strings appear anywhere in `frontend/src/`.

This is a known coverage gap aligned with Phase O0's "agents inactive" status; Phase O1+ activation work will introduce these patterns to the frontend (likely a separate auth client distinct from operator-key client.js).

## Section 6 — Configuration drift

| Config item | Value / source | Status |
|---|---|---|
| Bridge base URL (active SPA) | implicit via Vite proxy → `http://127.0.0.1:8080` | matches main.py default bind |
| Bridge URL (ControllerTwin) | `params.get('bridge') \|\| '127.0.0.1:8080'` | matches |
| `VITE_VAPI_API_KEY` | env from `.env.local`, build-time fail if missing in PROD | secure (env-driven, not inlined) |
| `VITE_CONSENT_REGISTRY_ADDRESS` | env from `.env.local` for `useConsentSubmit` | secure |
| `VITE_VAPI_BRIDGE_URL` | declared in `.env.example` (default `http://localhost:8080`) | declared but **not actually read by client.js** — Vite proxy is the active mechanism. Slightly confusing but harmless. |

**No deprecated bridge versions referenced.** No development-branch endpoint references found.

**One minor drift**: the `_OP_PREFIX = '/operator'` comment in `bridgeApi.js:8-11` says "the actual URL is /operator/bridge/capture-health" — which is correct. But `useGrindAnalytics` calls `/grind/analytics` (a route on the operator sub-app), and similarly `useGrindChain` calls `/bridge/grind-chain-status`. The comment focuses on `/bridge/*` and doesn't clarify that `/grind/*` is also under the operator sub-app. Documentation precision issue, not a connectivity bug.

## Section 7 — Build and dependency health (brief)

`package.json` declares standard React 18 + Vite 6 + react-query 5 + viem 2 + wagmi 2 stack. Three.js and react-three-fiber for the 3D twin. Tailwind 3.4 + framer-motion 11. No known critical security advisories on the listed major versions as of mid-2026.

`vite.config.js` proxy block covers all 12 path prefixes the frontend uses. No obvious misconfigurations.

Static analysis suggests `npm install` and `npm run build` would both succeed if run (not executed per session constraints).

## Section 8 — Phase O0 agent endpoint integration

The five Phase O0 read-only `/agent/*` endpoints from Stream 4-prep Session 2 (`a32c9d48`):

| Endpoint | Frontend integration |
|---|---|
| `GET /agent/agent-commit-history` | NONE |
| `GET /agent/agent-commit-status` | NONE |
| `GET /agent/physical-data-attestation-history` | NONE |
| `GET /agent/physical-data-attestation-status` | NONE |
| `GET /agent/agent-registry-status` | NONE |

Search confirmed: zero references in `frontend/src/` to any of these paths or to any of the four required HMAC headers (`X-Agent-KeyId`, `X-Timestamp`, `X-Nonce`, `X-Signature`).

This is **expected and aligned with Phase O0's "agents inactive" status**. No frontend integration is required for Phase O0 closure.

**Natural integration points for Phase O1+ activation**:
- DeveloperView → new "Agent Activity" panel with tabs for AGENT_COMMIT history (commit hashes per agent over time) and PDA history (attestation type breakdown)
- ManufacturerView → audit panel showing AgentRegistry status (registered count, scopeRoot per agent) for hardware-cert provenance discussions
- A new GovernanceView or admin overlay surfacing agent-registry-status alongside the existing PV-CI invariant-gate-status chip in DeveloperView

These would require a new agent-token auth client (separate from `client.js` because the auth scheme differs: Bearer JWT + HMAC headers vs operator x-api-key + query param). Per Pass 2C Section 5.1, the agent token issuer (`oauth_issuer.py`) and HMAC primitives (`hmac_middleware.py`) ship as bridge-side infrastructure; the frontend would need a corresponding browser-side signing helper that holds the agent's HMAC secret and issues the per-request signature. Holding that secret in browser memory introduces a new threat model that Phase O0 deferred; Phase O1+ will need to address it.

---

## Summary table

| Metric | Count |
|---|---|
| **Total active frontend endpoint calls** | **26** (17 bridgeApi hooks + 8 ControllerTwin direct + 1 shared `/health`) |
| CLEAN | **26** |
| PATH_MISMATCH | 0 |
| METHOD_MISMATCH | 0 |
| REQUEST_SHAPE_MISMATCH | 0 |
| RESPONSE_SHAPE_MISMATCH | 0 (one apparent — `useFleetCoherenceStatus` `by_mode` adaptation — already handled in the hook itself) |
| AUTH_MISMATCH | 0 |
| ORPHAN_FRONTEND | 0 |
| ORPHAN_BACKEND (intentional) | ~176 operator endpoints + most of dashboard `/api/v1/*` — by design (operator scripts, write actions, agent-only, audit endpoints) |
| ORPHAN_BACKEND (coverage gap) | ~6 endpoints (`fleet-coherence-history`, `fleet-coherence-entries`, `data-provenance-chain`, `protocol-maturity-score`, `biometric-credential-age`, `grind/session-history`) — opportunity, not bug |
| Phase O0 agent endpoints with frontend integration | **0 of 5** — expected per "agents inactive" Phase O0 posture |

**Connectivity is structurally clean.** No mismatches in active code paths require fixing for Phase O0 closure. The `shared/api/endpoints.js` + `shared/api/hooks/index.js` modules are dead-code carrying a parallel-but-stale auth pattern (query-param-only); cleanup is purely cosmetic. ControllerTwin.jsx hits public endpoints without auth and that's correct because those endpoints are public. The five Phase O0 agent-token endpoints are zero-integration in the frontend — by design, with natural integration points identified for future Phase O1+ work.
