# BRP Solo Track — Latency Budget

> **Track classification: out-of-band-solo. NOT Phase 241. NOT in the sequential VAPI protocol chain.**
> Per-prop staleness tolerance for the `<BrpMount />` component, mapped to achievable cadences against the current backend. The renderer treats each prop as opaque; this document specifies how *fresh* each opaque value should be at the integration boundary.

---

## Per-prop staleness budget

| Prop | Type | Tolerable staleness | Achievable via REST polling | Requires streaming? |
|---|---|---|---|---|
| `frozenOutput` | `Uint8Array` | seconds — re-renders when verification finalizes a new opaque output | YES — 1-5s polling against the endpoint that exposes the chosen hash family (see `OPEN_QUESTIONS.md#OQ-1`) | NO |
| `pitlSnapshot` | `PitlSnapshot` (7 PITL row outputs) | seconds — PITL detection events are minute-bucketed at `/dash/api/v1/pitl/timeline` (`bridge/vapi_bridge/dashboard_api.py:81`) | YES — 5-10s polling matches the bucket granularity | NO |
| `enrollmentSession?` | `EnrollmentSession` (optional) | minutes — enrollment progresses on a per-NOMINAL-session basis (~10 sessions before credentialing per `transports/http.py:819` enrollment endpoint) | YES — 30-60s polling against `/enrollment/status/{device_id}` is sufficient | NO |
| `liveness` | `{ ambient: boolean; legibility: boolean; telemetry: boolean }` | seconds — manifest-derived booleans plus guardian-health hook | YES — manifest is static at runtime; telemetry liveness can poll `/operator/watchdog-status` (already consumed by `useWatchdogStatus` at `frontend/src/api/bridgeApi.js:226`) | NO |
| `aidThreshold` | `number` | static — operator-set per `INTEGRATION_CONTRACT.md` Block Z (deferred) | YES — single fetch at mount time | NO |

**Streaming verdict: NO for every prop.** REST polling at 3-5 second cadences (matching existing SPA precedents below) satisfies every entry.

---

## Polling cadence references

The BRP renderer's polling matches one of two existing patterns in the SPA — no new pattern is introduced:

| Pattern | Cadence | Existing consumer | Source |
|---|---|---|---|
| Fast loop | 3 seconds | `useCaptureHealth` → `/bridge/capture-health` | `frontend/src/api/bridgeApi.js:163` |
| Standard loop | 5 seconds | `useGrindChain` → `/bridge/grind-chain-status` | `frontend/src/api/bridgeApi.js:172` |

**Recommendation.** `frozenOutput` and `pitlSnapshot` use the standard 5-second loop. `liveness` and `enrollmentSession?` use a slower 30-60s loop. `aidThreshold` is single-fetch at mount.

---

## PoAC production rate evidence

**1 PoAC record per second** at default settings:

```
bridge/vapi_bridge/dualshock_integration.py:357
self._interval = float(getattr(cfg, "dualshock_record_interval_s", 1.0))
```

Internal biometric polling runs at ~120 Hz (per the same file's `dt_ms = 8.0` at `:1977`), but PoAC-record assembly is throttled to once per second. The legibility overlay's "active calibration aid" use case (per `INTEGRATION_CONTRACT.md` Block Z) operates on the order of seconds-to-minutes per terminal calibration session — comfortably resolvable at 1 PoAC/sec via REST polling without streaming.

---

## Streaming infrastructure (informational)

WebSocket infrastructure exists on the bridge but is **not consumed by the active SPA**:

| Endpoint | Purpose | Source |
|---|---|---|
| `/ws/records` | Broadcasts PoAC records as JSON to subscribed clients | `bridge/vapi_bridge/transports/http.py:230` |
| `/ws/frames` | Phase 44 — raw downsampled frame stream (~20 Hz, InputSnapshot batches) | `bridge/vapi_bridge/transports/http.py:248` |
| `/ws/twin/{device_id}` | Phase 59 — device-scoped fusion stream: frames + PITL overlays | `bridge/vapi_bridge/transports/http.py:797` |

The only `new WebSocket(...)` call in the active frontend tree is in `frontend/src/legacy/ControllerTwin.jsx:91`, which is not part of the active GamerView/DeveloperView/ManufacturerView path. The BRP renderer would be the first SPA traffic exercising any of these WS endpoints if it chose streaming. **It does not need to.** REST polling at the cadences above satisfies every prop's staleness budget.

---

## Cross-references

- `BACKEND_CONTRACT.md` — endpoint inventory mapping props to source endpoints.
- `OPEN_QUESTIONS.md#OQ-1` — choice of canonical `frozenOutput` hash family (open).
- `OPEN_QUESTIONS.md#OQ-2` — `/dash/api/v1/*` vs `/agent/*` lean for `pitlSnapshot` (open).
- `INTEGRATION_CONTRACT.md` Block Z — `aidThreshold` operator-set decision (deferred).
- `INTEGRATION_CONTRACT.md` "Honesty-First Invariants" — H-7 terminal-script-wins precedence governs how a degraded telemetry budget interacts with the legibility overlay's `live` flag.
