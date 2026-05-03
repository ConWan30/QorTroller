# BRP Solo Track — Backend Contract

> **Track classification: out-of-band-solo. NOT Phase 241. NOT in the sequential VAPI protocol chain.**
> Verified-as-of-commit handoff data contract. Every claim carries a file:line citation. Items flagged `[verified]` were resolved by inspection of the active server file at commit time; items flagged `[unverified]` could not be located by the searches performed and are flagged for ceremony resolution. The integration ceremony **must verify current state** before binding any of this; the document's value is auditable evidence at commit time, not eternal truth.

---

## 1. Endpoint inventory (verified against `sdk/openapi.yaml v3.0.0-phase237`)

### 1.1 PoAC record family

| Endpoint | openapi.yaml | Live server file | Status |
|---|---:|---|---|
| `POST /records` | `:129` | `bridge/vapi_bridge/transports/http.py:266` exposes the same logic at `POST /api/v1/records` (prefix mismatch) | `[verified]` — implementation exists at a different path than the spec |
| `GET /records/{record_hash}` | `:167` | none located | `[verified]` documentation-only — see §4 Upstream spec drift |
| `POST /records/batch` | `:184` | `bridge/vapi_bridge/transports/http.py:280` exposes the same logic at `POST /api/v1/records/batch` (prefix mismatch) | `[verified]` — implementation exists at a different path |

### 1.2 Chain integrity family

| Endpoint | openapi.yaml | Live server file | Status |
|---|---:|---|---|
| `POST /chain/verify` | `:220` | none located in `bridge/`; `app/vapi-dualshock-companion.py:1137` exposes `GET /api/chain/verify` (different application, different method) | `[verified]` — see §4 Upstream spec drift |
| `POST /chain/integrity` | `:247` | none located | `[verified]` documentation-only — see §4 Upstream spec drift |

### 1.3 Dashboard family `/dash/api/v1/*`

All routes declared in `bridge/vapi_bridge/dashboard_api.py`, mounted at `/dash` per `bridge/vapi_bridge/main.py:433`. The `app.get("/api/v1/...")` paths inside `dashboard_api.py` become `/dash/api/v1/...` once the FastAPI sub-app is mounted.

| Endpoint | openapi.yaml | Live source | Status |
|---|---:|---:|---|
| `GET /dash/api/v1/player/{device_id}/profile` | `:597` | `dashboard_api.py:53` | `[verified]` |
| `GET /dash/api/v1/pitl/timeline` | `:616` | `dashboard_api.py:81` | `[verified]` |
| `GET /dash/api/v1/sdk/attestation` | (not in current openapi grep) | `dashboard_api.py:320` | `[verified]` — exists in code but spec coverage is `[unverified]` |
| `GET /dash/api/v1/player/{device_id}/checkpoint-chain` | `:641` | `dashboard_api.py:96` | `[verified]` |
| `GET /dash/api/v1/player/{device_id}/continuity-chain` | `:660` | `dashboard_api.py:111` | `[verified]` |
| `GET /dash/api/v1/player/{device_id}/behavioral-report` | `:679` | `dashboard_api.py:130` | `[verified]` (returns 503 when `BehavioralArchaeologist` not initialized) |
| `GET /dash/api/v1/player/{device_id}/pitl-proof` | `:701` | `dashboard_api.py:157` | `[verified]` |
| `GET /dash/api/v1/network/farm-detection` | `:721` | `dashboard_api.py:173` | `[verified]` (returns 503 when `NetworkCorrelationDetector` not initialized) |
| `GET /dash/api/v1/player/{device_id}/credential` | `:745` | `dashboard_api.py:200` | `[verified]` |
| `GET /dash/api/v1/leaderboard` | `:765` | `dashboard_api.py:214` | `[verified]` |
| `GET /dash/api/v1/player/{device_id}/eligibility` | `:791` | `dashboard_api.py:223` | `[verified]` |
| `GET /proof/{device_id}` | `:809` | `dashboard_api.py:248` (HTML response, not JSON) | `[verified]` |
| `GET /enrollment/status/{device_id}` | `:827` | `bridge/vapi_bridge/transports/http.py:819` | `[verified]` |

**Stability.** `dashboard_api.py` has 1 commit total since initial commit (`4805d7b9`). The 13 routes above are API-stable from a version-control perspective. **Caveat:** stable does not mean *exercised by the live SPA*. The active frontend (`frontend/src/api/bridgeApi.js`, 17 active hooks) consumes zero `/dash/api/v1/*` endpoints. Whatever stability they have is observed by the spec, not by traffic.

### 1.4 Active frontend → backend wiring (live truth)

For context, the 17 hooks currently consumed by the active SPA. Sourced from `frontend/src/api/bridgeApi.js`. `_OP_PREFIX = '/operator'` at `bridgeApi.js:11` — the bridge wraps these under `/operator` per `main.py:444` (`app.mount("/operator", _op_app)`).

| Hook | Path | bridgeApi.js line |
|---|---|---:|
| `useProtocolCoherence` | `/agent/protocol-coherence-status` | `:47` |
| `useTournamentBlockerSummary` | `/agent/tournament-blocker-summary` | `:56` |
| `usePerPairGapStatus` | `/agent/per-pair-gap-status` | `:65` |
| `usePerPairGapProjection` | `/agent/per-pair-gap-projection` | `:74` |
| `useSeparationDefensibility` | `/agent/separation-defensibility-status` | `:83` |
| `useInvariantGate` | `/agent/invariant-gate-status` | `:92` |
| `useFleetCoherenceStatus` | `/agent/fleet-coherence-summary` | `:105` |
| `useCaptureVelocityOracle` | `/agent/capture-velocity-oracle` | `:128` |
| `useTournamentPreflight` | `/agent/tournament-preflight-status` | `:137` |
| `useAutoTriggerStatus` | `/agent/auto-trigger-status` | `:149` |
| `useCaptureHealth` | `/bridge/capture-health` | `:164` |
| `useGrindChain` | `/bridge/grind-chain-status` | `:174` |
| `useAITSeparation` | `/agent/ait-separation-status` | `:187` |
| `useGrindAnalytics` | `/grind/analytics` | `:200` |
| `usePCCIntelligence` | `/grind/pcc-intelligence` | `:213` |
| `useWatchdogStatus` | `/operator/watchdog-status` | `:226` |
| `useConsentStatus` | `/agent/gamer-consent-status?device_id=...` | `:250` |

---

## 2. Prop → endpoint mapping for `<BrpMount />`

The renderer's prop contract per `INTEGRATION_CONTRACT.md` "What the O0-integrated VAPI must expose":

| Prop | Type | Likely upstream | Citation | Status |
|---|---|---|---|---|
| `frozenOutput` | `Uint8Array` | Bound to one of five hash candidates (see `OPEN_QUESTIONS.md#OQ-1`); host page hex-decodes to bytes | (deferred to ceremony) | `[unverified]` — open question, ceremony-bound |
| `pitlSnapshot` | `PitlSnapshot` (read-only) | Either `/dash/api/v1/pitl/timeline` (semantic match, but unconsumed by active SPA — see F-9) or composition over `/agent/*` summaries (see `OPEN_QUESTIONS.md#OQ-2`) | `dashboard_api.py:81` (if `/dash`), or one of `/agent/*` hooks above (if composed) | `[unverified]` — open question, ceremony-bound, with a recommendation toward `/agent/*` |
| `enrollmentSession?` | `EnrollmentSession` (optional) | `GET /enrollment/status/{device_id}` | `bridge/vapi_bridge/transports/http.py:819` | `[verified]` |
| `aidThreshold` | `number` | Operator-set per `INTEGRATION_CONTRACT.md` Block Z (deferred) | (operator config, no endpoint) | `[verified]` — single-fetch at mount; not bound to a backend route |
| `liveness` | `{ ambient: boolean; legibility: boolean; telemetry: boolean }` | (a) manifest-derived statics for `ambient` and `legibility`; (b) `/operator/watchdog-status` for `telemetry` (already consumed by `useWatchdogStatus`) | `frontend/src/api/bridgeApi.js:226` for telemetry | `[verified]` for the wiring template; the per-bucket ownership at integration time is ceremony-bound |

The renderer's prop contract is **namespace-agnostic** by design (D2 = 2-C). The host page wires the props from whichever upstream produces the matching TypeScript shape; the renderer never imports a fetch URL.

---

## 3. Q-3 resolution — `interperson-separation-data{,-v2}.json` selection

**Resolution.** **v1 (`docs/interperson-separation-data.json`) is canonical.** v2 (`docs/interperson-separation-data-v2.json`) is stale historical artifact, kept for diff/comparison purposes; not the renderer's source of truth.

**Evidence.**

| File | Size | Last modified | Top-level keys | `analysis_version` (internal) | `separation_ratio` (internal) |
|---|---:|---|---:|---|---|
| `docs/interperson-separation-data.json` (v1) | 234,928 bytes | 2026-05-01 20:03 | **35** | `2.0` | `0.07872058693528046` |
| `docs/interperson-separation-data-v2.json` (v2) | 47,882 bytes | 2026-03-11 14:38 | **25** | `2.0` | `0.36165614861754947` |

**v2 is older despite the suffix.** Last modified ~7 weeks before the unsuffixed file. Both report `analysis_version: "2.0"` internally — the "v2" in the filename is **not** the analysis version. v2 is a strict subset of v1's keys (v2 has zero keys that v1 lacks; v1 has 10 keys that v2 lacks).

**v1-only fields** (the 10 the renderer's legibility overlay would actually want):

`age_weight_halflife`, `age_weighted`, `battery_stratified_results`, `cov_auto_fallback_triggered`, `cov_mode`, `cov_np_ratio`, `cov_regime_status`, `n_sessions_before_type_filter`, `players`, `session_type_filter`

These align with the SeparationRatioMonitorAgent fields per CLAUDE.md (which mentions `cov_regime_status`, `cov_np_ratio`, etc. as part of Phase 195+ analytics). The `cov_regime_status` field is directly load-bearing for "is the displayed ratio defensible or plateau-regime" — exactly the sort of cell the legibility overlay would render.

**Implication.**

- The renderer's prop contract types against v1's schema.
- v2 is documented here for ceremony auditors so its existence is not a surprise; it is **not** part of the renderer's data wiring.
- The `separation_ratio` numerical disagreement (`0.0787` v1 vs `0.362` v2) is honest — both are correct values for *different corpus snapshots*. The host page passing this through to the renderer must label which corpus/regime the displayed value came from. The renderer treats it as opaque.

---

## 4. Upstream spec drift (separate from BRP renderer's own concerns)

This section flags spec-vs-implementation drift discovered during the assessment that is **not a BRP renderer concern** but is relevant to ceremony auditors as repository-wide notes. The renderer's prop contract does not consume any of these routes; the drift is informational.

### 4.1 `GET /records/{record_hash}` — documentation-only

| Where | What |
|---|---|
| `sdk/openapi.yaml:167` | Declared as `GET /records/{record_hash}` returning `RecordDetail` schema |
| `frontend/public/openapi.yaml:167` | Distributed copy of the same spec |
| Any active server file | **No handler exists.** Targeted searches in `bridge/vapi_bridge/{transports/http.py, operator_api.py, dashboard_api.py}` and repo-wide grep returned zero matches. |

**Status.** Documentation-only at commit time. If the integration ceremony picks PoAC `record_hash` as the canonical `frozenOutput` source (`OPEN_QUESTIONS.md#OQ-1`), the bridge currently has no public endpoint to retrieve a *specific* record's bytes by hash. Closest existing surface is `/ws/records` broadcast (`bridge/vapi_bridge/transports/http.py:230`) for live records.

### 4.2 `POST /chain/verify` — split status across applications

| Where | What |
|---|---|
| `sdk/openapi.yaml:220` | Declared as `POST /chain/verify` requiring BearerAuth |
| `bridge/vapi_bridge/transports/http.py` | **No `POST /chain/verify` handler.** |
| `app/vapi-dualshock-companion.py:1137` | `GET /api/chain/verify` exists in a **different application** (the DualShock Companion app per its module docstring at `:1-25`). Different prefix (`/api/chain/verify` vs `/chain/verify`), different method (GET vs POST). |

**Status.** Split across applications and methods. Not a single endpoint despite shared name fragments.

### 4.3 `POST /chain/integrity` — documentation-only

| Where | What |
|---|---|
| `sdk/openapi.yaml:247` | Declared as `POST /chain/integrity` |
| Any active server file | **No handler exists** anywhere in the repo. |

**Status.** Documentation-only at commit time.

### 4.4 Recommendation for ceremony auditors

These three findings are **upstream of the BRP renderer's own concerns.** Owner: whoever maintains `sdk/openapi.yaml`. The BRP renderer's prop contract does not depend on `/records/{record_hash}`, `/chain/verify`, or `/chain/integrity` being live; it depends on whichever endpoint the host page uses for `frozenOutput` and `pitlSnapshot`, which are ceremony-bound choices documented in `OPEN_QUESTIONS.md`.

The drift is logged here so ceremony auditors do not re-derive it independently and so the BRP solo-track audit trail acknowledges that the spec it was written against has known soft-spots.

---

## Cross-references

- `OPEN_QUESTIONS.md` — OQ-1 (frozenOutput hash family), OQ-2 (PITL-snapshot consumption pattern), OQ-3 (namespace agnosticism resolved-by-design), OQ-4 (Phase 13X re-read deferred).
- `LATENCY_BUDGET.md` — per-prop staleness tolerance and the REST polling cadence pattern citing `useCaptureHealth` and `useGrindChain` precedents.
- `INTEGRATION_CONTRACT.md` — the renderer's prop contract, ceremony steps, decision-block resolutions, honesty-first invariants. The spec drift in §4 above is **not** within the BRP renderer's contract surface; that doc remains the binding handoff specification.
- `README.md` — workspace overview and per-commit scope summary.
- `src/manifest/brp.manifest.json` — three new `docs:` entries added in this commit, all `live: false`.
