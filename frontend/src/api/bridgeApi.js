import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { activateMock, deactivateMock, isMockActive, MOCK } from './mockBridge'
import { apiGet, ApiKeyError, BridgeOfflineError } from './client'

// All status endpoints hit by the dashboard live inside the operator sub-app,
// which the bridge mounts at /operator (see bridge/vapi_bridge/main.py). The
// declared route paths are e.g. "/bridge/capture-health" — but the actual URL
// is "/operator/bridge/capture-health". Everything that flows through this
// helper needs the prefix; legacy/shared modules that hit non-operator routes
// (/health, /api/v1, /devices) use their own fetch helpers and are unaffected.
const _OP_PREFIX = '/operator'

async function get(path, mockKey, opts = {}) {
  // Always try the live bridge first. If it succeeds, deactivate any sticky
  // mock state and return live data. Only fall back to mock on network/offline
  // errors — never short-circuit before the live call, otherwise mock becomes
  // permanent until sessionStorage is manually cleared.
  //
  // opts.noMock — for grind-critical endpoints (capture-health, grind-chain
  // -status) we MUST NOT swap in mock data on transient failure. Mock has
  // hardcoded values (chain_length~12, target=100, session 'grind_phase235
  // _v1') that visually compete with the real bridge state during an active
  // grind, producing a 0/3 ↔ 11/100 flip-flop on every failed poll. Instead,
  // re-throw so react-query keeps the last successful response in `data`.
  try {
    const data = await apiGet(_OP_PREFIX + path)
    if (isMockActive()) deactivateMock()
    return data
  } catch (err) {
    if (err instanceof ApiKeyError) {
      // Key is wrong — don't activate mock, surface the error to the UI
      throw err
    }
    if (opts.noMock) {
      // Grind-critical: rethrow so react-query holds the last successful
      // value instead of swapping in mock fakes.
      throw err
    }
    activateMock()
    return MOCK[mockKey]?.()
  }
}

export function useProtocolCoherence() {
  return useQuery({
    queryKey: ['protocolCoherence'],
    queryFn: () => get('/agent/protocol-coherence-status', 'protocolCoherenceStatus'),
    refetchInterval: 3000,
    staleTime: 2000,
  })
}

export function useTournamentBlockerSummary() {
  return useQuery({
    queryKey: ['tournamentBlockerSummary'],
    queryFn: () => get('/agent/tournament-blocker-summary', 'tournamentBlockerSummary'),
    refetchInterval: 8000,
    staleTime: 5000,
  })
}

export function usePerPairGapStatus() {
  return useQuery({
    queryKey: ['perPairGapStatus'],
    queryFn: () => get('/agent/per-pair-gap-status', 'perPairGapStatus'),
    refetchInterval: 10000,
    staleTime: 8000,
  })
}

export function usePerPairGapProjection() {
  return useQuery({
    queryKey: ['perPairGapProjection'],
    queryFn: () => get('/agent/per-pair-gap-projection', 'perPairGapProjection'),
    refetchInterval: 15000,
    staleTime: 10000,
  })
}

export function useSeparationDefensibility() {
  return useQuery({
    queryKey: ['separationDefensibility'],
    queryFn: () => get('/agent/separation-defensibility-status', 'separationDefensibilityStatus'),
    refetchInterval: 10000,
    staleTime: 8000,
  })
}

export function useInvariantGateStatus() {
  return useQuery({
    queryKey: ['invariantGateStatus'],
    queryFn: () => get('/agent/invariant-gate-status', 'invariantGateStatus'),
    refetchInterval: 30000,
    staleTime: 20000,
  })
}

// Phase 235-AUDIT fix: bridge endpoint is /agent/fleet-coherence-summary
// (not -status — the -status path returns 404 and silently activates mock).
// Response shape uses `by_mode` dict; we adapt to active_* fields the chip expects.
export function useFleetCoherenceStatus() {
  return useQuery({
    queryKey: ['fleetCoherenceStatus'],
    queryFn: async () => {
      const raw = await get('/agent/fleet-coherence-summary', 'fleetCoherenceStatus', { noMock: true })
      // Adapt live shape → field names the GamerView coherence chip reads.
      // Mock already returns the adapted shape, so we only adapt live data.
      if (raw && typeof raw === 'object' && 'by_mode' in raw) {
        const m = raw.by_mode || {}
        return {
          ...raw,
          active_contradictions: m.CONTRADICTION ?? 0,
          active_orphans:        m.ORPHAN ?? 0,
          active_inversions:     m.INVERSION ?? 0,
        }
      }
      return raw
    },
    refetchInterval: 8000,
    staleTime: 5000,
    retry: 1,
  })
}

export function useCaptureVelocityOracle() {
  return useQuery({
    queryKey: ['captureVelocityOracle'],
    queryFn: () => get('/agent/capture-velocity-oracle', 'captureVelocityOracle'),
    refetchInterval: 12000,
    staleTime: 8000,
  })
}

export function useTournamentPreflight() {
  return useQuery({
    queryKey: ['tournamentPreflight'],
    queryFn: () => get('/agent/tournament-preflight-status', 'tournamentPreflight'),
    refetchInterval: 15000,
    staleTime: 10000,
  })
}

// Phase 235-DASH-UPGRADE: SessionBoundaryDetectorAgent telemetry.
// Polls every 5s; noMock so the live throttle countdown can't get
// hijacked by stale mock data during a live grind.
export function useAutoTriggerStatus() {
  return useQuery({
    queryKey: ['autoTriggerStatus'],
    queryFn: () => get('/agent/auto-trigger-status', 'autoTriggerStatus', { noMock: true }),
    refetchInterval: 5000,
    staleTime: 3000,
    retry: 1,
  })
}

// Phase 241-APOP — Active Play Occupancy Proof live status.
// noMock=true: when gate_mode != "shadow" this is grind-critical (rescues
// MENU false-positives + blocks confident NON_COMPETITIVE_MENU). Mock would
// fabricate state/score/confidence — must not land mid-grind.
export function useActivePlayOccupancy() {
  return useQuery({
    queryKey: ['activePlayOccupancy'],
    queryFn: () => get('/agent/active-play-occupancy-status', 'activePlayOccupancy', { noMock: true }),
    refetchInterval: 4000,
    staleTime: 2500,
    retry: 1,
  })
}

// Phase 235-FINAL: grind-critical live indicators.
// noMock=true: on transient failure react-query holds the last successful
// response.  Without this, a single 5s timeout under DataCuratorAgent
// contention would swap in mock data ('grind_phase235_v1' / 11 / 100) and
// produce a 0/3 ↔ 11/100 flip-flop on the GamerView during a real run.
export function useCaptureHealth() {
  return useQuery({
    queryKey: ['captureHealth'],
    queryFn: () => get('/bridge/capture-health', 'captureHealth', { noMock: true }),
    refetchInterval: 3000,
    staleTime: 2000,
    retry: 1,
  })
}

export function useGrindChain() {
  return useQuery({
    queryKey: ['grindChain'],
    queryFn: () => get('/bridge/grind-chain-status', 'grindChain', { noMock: true }),
    refetchInterval: 5000,
    staleTime: 3000,
    retry: 1,
  })
}

// Phase 229 — AIT inter-player separation analysis
// noMock=true: AIT separation is corpus state, not live telemetry.
// Mock fakes (1.199 / all_pairs_above_1=true) would mislead during a real grind.
export function useAITSeparation() {
  return useQuery({
    queryKey: ['aitSeparation'],
    queryFn: () => get('/agent/ait-separation-status', 'aitSeparationStatus', { noMock: true }),
    refetchInterval: 20000,
    staleTime: 15000,
    retry: 1,
  })
}

// Phase 235-ANALYTICS — grind pipeline success rate + projection
// noMock=true: projected_gic100_date and sessions_per_day feed the GamerView
// progress sub-strip directly. Mock fallback would show fabricated ETAs.
export function useGrindAnalytics() {
  return useQuery({
    queryKey: ['grindAnalytics'],
    queryFn: () => get('/grind/analytics', 'grindAnalytics', { noMock: true }),
    refetchInterval: 10000,
    staleTime: 8000,
    retry: 1,
  })
}

// Phase 235-CONTENTION — BT contention episode intelligence
// noMock=true: PCCDrawer surfaces hid_counter_restarts and episode counts.
// Mock fallback would hide a real CONTESTED problem behind fake "0 episodes".
export function usePCCIntelligence() {
  return useQuery({
    queryKey: ['pccIntelligence'],
    queryFn: () => get('/grind/pcc-intelligence', 'pccIntelligence', { noMock: true }),
    refetchInterval: 8000,
    staleTime: 5000,
    retry: 1,
  })
}

// Phase 236-WATCHDOG — Watchdog Event Chain (WEC) status.
// Surfaces in DeveloperView (operational tooling); not used by GamerView.
// noMock=true: WEC must reflect actual watchdog state — mock has no chain.
export function useWatchdogStatus() {
  return useQuery({
    queryKey: ['watchdogStatus'],
    queryFn: () => get('/operator/watchdog-status', 'watchdogStatus', { noMock: true }),
    refetchInterval: 15000,
    staleTime: 10000,
    retry: 1,
  })
}

// UI-side mock-active indicator for the dashboard.
// Returns true when bridge is unreachable AND we're showing fakes.
// GamerView/DeveloperView should render a banner so operators don't mistake
// fabricated values for live grind state.
export { isMockActive } from './mockBridge'

// ─── BRP renderer hooks (post-milestone incorporation per OQ-7) ─────────────
// These hooks adapt live bridge telemetry to the BrpMount prop contract
// (frontend/src/brp/telemetry/contracts.ts). They live in bridgeApi.js
// (the host page's wiring layer) NOT in src/brp/ — preserves D2
// mount-agnostic: the renderer never imports a fetch URL; the host wires.

/**
 * useBrpFrozenOutput — derives the renderer's `frozenOutput: Uint8Array`
 * from the bridge's GIC chain hash. Reuses useGrindChain's 5s polling
 * cadence (no new pattern; per LATENCY_BUDGET.md).
 *
 * Returns: { bytes, hashHex, source, isLoading, error }
 *   - bytes:   32-byte Uint8Array on success, null when chain isn't ready
 *   - hashHex: the raw hex string (audit-readable, surfaced in BrpView indicator)
 *   - source:  'live' when bridge returned a hash; 'unavailable' otherwise
 *
 * Per OQ-1 (canonical frozenOutput hash family), GIC chain hash is one of
 * five candidates the integration ceremony will pick from. Pre-ceremony
 * incorporation uses GIC for visibility; ceremony may switch.
 */
export function useBrpFrozenOutput() {
  const grind = useGrindChain()
  const hashHex = grind.data?.latest_gic_hash || null
  let bytes = null
  if (hashHex && /^[0-9a-fA-F]{64}$/.test(hashHex)) {
    bytes = new Uint8Array(32)
    for (let i = 0; i < 32; i++) {
      bytes[i] = parseInt(hashHex.slice(i * 2, i * 2 + 2), 16)
    }
  }
  return {
    bytes,
    hashHex,
    source: bytes ? 'live' : 'unavailable',
    isLoading: grind.isLoading,
    error: grind.error,
  }
}

/**
 * useEnrollmentStatus — fetches /enrollment/status/{deviceId} and adapts
 * the bridge's snake_case response to the renderer's EnrollmentSession
 * shape.
 *
 * Note on path prefix: this endpoint lives on the MAIN bridge app
 * (transports/http.py:819), NOT under the /operator sub-app. So we use
 * apiGet() directly instead of the get() helper which prepends /operator.
 * Vite proxies /enrollment → bridge:8080 (see frontend/vite.config.js).
 *
 * The bridge endpoint always returns 200 with status='pending' for
 * unknown devices, so an HTTP 404 path isn't needed — but BridgeOffline
 * is, in case the bridge is down. We let the error propagate so
 * react-query holds the last successful response.
 *
 * Polling: 30s (slower cadence per LATENCY_BUDGET.md — enrollment progresses
 * on a per-NOMINAL-session basis, ~10 sessions before credentialing).
 */
export function useEnrollmentStatus(deviceId) {
  return useQuery({
    queryKey: ['brpEnrollmentStatus', deviceId],
    queryFn: async () => {
      const res = await apiGet(`/enrollment/status/${encodeURIComponent(deviceId)}`)
      // Adapter: snake_case → camelCase to match BRP contracts.ts
      // EnrollmentSession shape. Bridge fields per
      // bridge/vapi_bridge/transports/http.py:819+.
      return {
        deviceId: res.device_id || deviceId,
        sessionsNominal: res.sessions_nominal ?? 0,
        avgHumanity: res.avg_humanity ?? 0,
        status: res.status || 'pending',
        requiredSessions: res.sessions_required ?? 10,
        requiredHumanity: res.humanity_required ?? 0.6,
      }
    },
    enabled: Boolean(deviceId),
    refetchInterval: 30000,
    staleTime: 25000,
    retry: 1,
  })
}

/**
 * useBrpRecordPulse — WebSocket subscriber to /ws/records (commit ε).
 *
 * Connects to the bridge's PoAC record broadcast channel
 * (bridge/vapi_bridge/transports/http.py:230). Each record-arrival message
 * advances `lastPulseTs` and `pulseCount`, which the BrpView passes to
 * <BrpMount pulse={...}> to drive the ambient mesh's emissive pulse.
 *
 * This is the FIRST active-SPA WebSocket consumer (per
 * Backend State Assessment §F-9 — assessment.md F-9 noted that the
 * existing 17 useQuery hooks are all REST polling; only frontend/legacy/
 * ControllerTwin.jsx had a WS reference, in inactive legacy code).
 * Documented as a deliberate scope shift; the BRP renderer matches the
 * design PDF's gameplay-frequency mental model (~1 record/sec when
 * grinding) which REST polling at 3-5s cadence cannot match.
 *
 * Direct WebSocket connection (not via Vite proxy): vite.config.js does
 * not currently configure ws:true on its proxy entries, so we connect
 * directly to ws://${hostname}:8080. Bridge accepts this without origin
 * checks (no CSP enforced on the /ws/records handler).
 *
 * Auto-reconnect: exponential backoff capped at 30s. Connection state
 * surfaced via `connected` so BrpView can show a pulse-source indicator.
 */
export function useBrpRecordPulse() {
  const [pulseCount, setPulseCount] = useState(0)
  const [lastPulseTs, setLastPulseTs] = useState(0)
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)
  const reconnectAttemptsRef = useRef(0)

  useEffect(() => {
    let cleanup = false

    function connect() {
      if (cleanup) return
      try {
        const host = window.location.hostname || 'localhost'
        const ws = new WebSocket(`ws://${host}:8080/ws/records`)
        wsRef.current = ws

        ws.onopen = () => {
          if (cleanup) {
            ws.close()
            return
          }
          setConnected(true)
          reconnectAttemptsRef.current = 0
        }

        ws.onmessage = () => {
          if (cleanup) return
          // Each broadcast = one PoAC record. Increment + stamp.
          // We don't parse the payload; the BRP renderer only needs the
          // event arrival time, not the record contents (those flow
          // through frozenOutput via the GIC chain hash separately).
          setPulseCount((c) => c + 1)
          setLastPulseTs(Date.now())
        }

        ws.onclose = () => {
          if (cleanup) return
          setConnected(false)
          // Exponential backoff: 1s, 2s, 4s, 8s, 16s, capped at 30s.
          const attempt = reconnectAttemptsRef.current++
          const delay = Math.min(1000 * Math.pow(2, attempt), 30000)
          setTimeout(connect, delay)
        }

        ws.onerror = () => {
          // close handler fires after error; backoff handles retry there.
        }
      } catch {
        if (!cleanup) setConnected(false)
      }
    }

    connect()
    return () => {
      cleanup = true
      try { wsRef.current?.close() } catch { /* fail-silent */ }
    }
  }, [])

  return { pulseCount, lastPulseTs, connected }
}

/**
 * useBrpDeviceDiscovery — resolves the active controller's device_id by
 * polling the bridge's /api/v1/devices endpoint (commit η).
 *
 * Mirrors the long-established pattern from frontend/legacy/ControllerTwin.jsx
 * `useAutoDiscover` (lines 54-76) which has been the working device-discovery
 * pattern in this repo since the initial commit. The bridge's
 * store.list_devices() returns rows sorted by last_seen DESC, so the first
 * entry is the most recently active controller. /api/v1/devices is on the
 * MAIN bridge app (NOT under /operator), so we use apiGet directly — same
 * approach as useEnrollmentStatus.
 *
 * 5s polling cadence matches LATENCY_BUDGET.md's "fast loop" pattern
 * (useCaptureHealth at 3s, useGrindChain at 5s) — devices come and go on
 * the order of seconds when a controller is plugged in or unplugged.
 *
 * Returns null when bridge is offline OR no devices have ever been seen.
 * Consumers should treat null as "fall back to placeholder/synthetic".
 */
export function useBrpDeviceDiscovery() {
  return useQuery({
    queryKey: ['brpDeviceDiscovery'],
    queryFn: async () => {
      const devices = await apiGet('/api/v1/devices')
      if (!Array.isArray(devices) || devices.length === 0) {
        return null
      }
      // First entry = most recently active per store.list_devices()
      // ORDER BY last_seen DESC.
      const first = devices[0]
      if (!first?.device_id) {
        return null
      }
      return {
        deviceId: first.device_id,
        deviceCount: devices.length,
        // Bridge schema for devices table includes:
        //   device_id (TEXT) — keccak256(pubkey) hex
        //   pubkey (TEXT)    — ECDSA-P256 pubkey hex
        //   first_seen (INTEGER, ms) | last_seen (INTEGER, ms)
        //   record_count (INTEGER)
        // Forward whatever the bridge actually returns; null for missing.
        firstSeen: first.first_seen ?? null,
        lastSeen: first.last_seen ?? null,
        recordCount: first.record_count ?? null,
      }
    },
    refetchInterval: 5000,
    staleTime: 4000,
    retry: 1,
  })
}

/**
 * useBrpRecentRecords — per-device session activity feed (commit θ).
 *
 * Polls /api/v1/records/recent?device_id=...&limit=10 (transports/http.py:318;
 * delegates to store.get_recent_records which joins records + devices and
 * returns rows ORDER BY r.created_at DESC). Each row carries the standard
 * record schema: record_hash, device_id, counter, timestamp_ms, inference,
 * action_code, confidence, plus the PITL feature columns.
 *
 * Bridge-level inference codes per CLAUDE.md FROZEN-v1:
 *   0x20 NOMINAL          (clean) — does not count as anomaly
 *   0x28 DRIVER_INJECT    (hard cheat — blocks tournament)
 *   0x29 WALLHACK         (hard cheat)
 *   0x2A AIMBOT           (hard cheat)
 *   0x2B TEMPORAL_BOT     (advisory)
 *   0x30 BIOMETRIC_ANOMALY (advisory)
 *   0x31 IMU_PRESS_DECOUPLED (advisory)
 *   0x32 STICK_IMU_DECOUPLED (advisory)
 *   0x33 GSR_CORRELATION_ABSENT (advisory L7)
 *
 * Polling cadence: 5s (matches LATENCY_BUDGET.md standard loop). Records
 * arrive at ~1 Hz when grinding so this gives ~5 fresh records per poll.
 */
export function useBrpRecentRecords(deviceId) {
  return useQuery({
    queryKey: ['brpRecentRecords', deviceId],
    queryFn: async () => {
      const params = new URLSearchParams({
        limit: '10',
        device_id: deviceId,
      })
      const records = await apiGet(`/api/v1/records/recent?${params.toString()}`)
      if (!Array.isArray(records)) {
        return { records: [], lastRecordTs: null, anomalyCount: 0, recordsPerMinute: 0 }
      }
      const now = Date.now()
      // anomaly = any non-NOMINAL inference code (0x20 = 32 decimal)
      const anomalyCount = records.filter((r) => {
        const code = r?.inference
        return typeof code === 'number' && code !== 0x20
      }).length
      // Newest record's timestamp (ORDER BY created_at DESC, so records[0] is latest)
      const newest = records[0]
      const lastRecordTs = newest?.timestamp_ms ?? null
      // Records-per-minute estimate from how recent the 10-record window is.
      // If the oldest record in the window is < 60s old, we have >10 r/m.
      const oldest = records[records.length - 1]
      let recordsPerMinute = 0
      if (records.length > 0 && oldest?.timestamp_ms && newest?.timestamp_ms) {
        const windowMs = newest.timestamp_ms - oldest.timestamp_ms
        if (windowMs > 0) {
          recordsPerMinute = Math.round((records.length / windowMs) * 60_000)
        }
      }
      return {
        records,
        lastRecordTs,
        lastRecordAgeMs: lastRecordTs ? now - lastRecordTs : null,
        anomalyCount,
        recordsPerMinute,
      }
    },
    enabled: Boolean(deviceId),
    refetchInterval: 5000,
    staleTime: 4000,
    retry: 1,
  })
}

/**
 * useBrpPhgProfile — per-device PHG Trust Score + humanity stats (commit κ).
 *
 * Polls /dash/api/v1/player/{device_id}/profile (dashboard_api.py:53-75;
 * delegates to store.get_player_profile which aggregates over the records
 * table for the device). Returns the PHG Trust Score (Σ confidence_i/255 × 10
 * over NOMINAL records) plus humanity_prob_avg, l5_rhythm_humanity_avg, and
 * confidence_mean — the per-player legitimacy ledger that backs VHP credentialing.
 *
 * The endpoint returns 404 when the device_id is unknown to the bridge — for
 * the placeholder device this is the steady state, surfaced as 'no profile yet'.
 *
 * Polling cadence: 10s. PHG score updates monotonically with each NOMINAL
 * record (~1/sec at gameplay rate), so a 10s poll gives ~10-record granularity
 * — fast enough to feel live, slow enough not to thrash the SQL aggregator.
 */
export function useBrpPhgProfile(deviceId) {
  return useQuery({
    queryKey: ['brpPhgProfile', deviceId],
    queryFn: async () => {
      try {
        const profile = await apiGet(`/dash/api/v1/player/${encodeURIComponent(deviceId)}/profile`)
        return profile
      } catch (e) {
        // 404 (device unknown) and BridgeOffline both surface as null;
        // the UI distinguishes via the query's error/isLoading flags.
        return null
      }
    },
    enabled: Boolean(deviceId),
    refetchInterval: 10000,
    staleTime: 8000,
    retry: 1,
  })
}

/**
 * useBrpControllerOrientation — WebSocket subscriber to /ws/twin/{deviceId}
 * (commit ζ). Parses ~20 Hz frame batches; derives pitch + roll from accel
 * (gravity reference). Yaw is currently 0 (not derivable from accel alone;
 * gyro integration would drift; magnetometer not exposed). The renderer
 * lerps toward the latest target at 60 fps so 1 Hz batch arrival still
 * feels smooth.
 *
 * Each /ws/twin/{deviceId} message has shape:
 *   { type: "frame", data: { type: "frames", frames: [ ... ] } }
 * with up to 20 frames per batch. Each frame includes accel_{x,y,z} and
 * gyro_{x,y,z}. We use the LAST frame in each batch as the freshest
 * orientation target.
 *
 * SECOND active-SPA WebSocket consumer (commit ε added the first via
 * /ws/records). Per BACKEND_CONTRACT.md F-9 / OQ-2: this is a deliberate
 * scope shift toward gameplay-frequency feedback. The two channels are
 * independent: /ws/records provides per-event pulses; /ws/twin/{deviceId}
 * provides continuous orientation. They can run simultaneously without
 * coordination.
 *
 * deviceId: in pre-ceremony incorporation, the bridge's actual device_id
 * (keccak256 of pubkey for the connected DualShock Edge) is unknown to
 * the frontend without a discovery endpoint. With the placeholder
 * device_id, the WS connects but receives no broadcasts (the bridge's
 * _ws_twin_clients dict has no matching key). Hook returns connected=true
 * but yields no orientation updates — visible in the indicator panel as
 * "[LIVE-FALLBACK] WS connected but no twin frames yet" while the renderer
 * stays in rotation-only mode. Discovery via a future /devices endpoint
 * is a follow-up enhancement.
 */
export function useBrpControllerOrientation(deviceId) {
  const [orientation, setOrientation] = useState(null)
  const [connected, setConnected] = useState(false)
  const [framesReceived, setFramesReceived] = useState(0)
  const wsRef = useRef(null)
  const reconnectAttemptsRef = useRef(0)

  useEffect(() => {
    if (!deviceId) return undefined
    let cleanup = false

    function deriveOrientation(frame) {
      // Gravity-derived pitch + roll. accel components are in g-units
      // (or arbitrary scaled units; sign convention from controller's
      // body frame). When the controller is at rest, the accel vector
      // points along gravity.
      //
      // Pitch: rotation around X-axis (forward/back tilt). Derived from
      // ax + sqrt(ay² + az²) projection.
      // Roll: rotation around Z-axis (left/right tilt). Derived from
      // ay vs az.
      const ax = frame.accel_x ?? 0
      const ay = frame.accel_y ?? 0
      const az = frame.accel_z ?? 0
      const pitch = Math.atan2(-ax, Math.sqrt(ay * ay + az * az))
      const roll = Math.atan2(ay, az)
      return {
        pitch,
        roll,
        yaw: 0,
        ts: typeof frame.ts_ms === 'number' ? frame.ts_ms : Date.now(),
      }
    }

    function connect() {
      if (cleanup) return
      try {
        const host = window.location.hostname || 'localhost'
        const ws = new WebSocket(`ws://${host}:8080/ws/twin/${encodeURIComponent(deviceId)}`)
        wsRef.current = ws

        ws.onopen = () => {
          if (cleanup) {
            ws.close()
            return
          }
          setConnected(true)
          reconnectAttemptsRef.current = 0
        }

        ws.onmessage = (event) => {
          if (cleanup) return
          try {
            const msg = JSON.parse(event.data)
            // Filter for frame batches; ignore record messages.
            if (msg?.type !== 'frame') return
            const frames = msg?.data?.frames
            if (!Array.isArray(frames) || frames.length === 0) return
            const latest = frames[frames.length - 1]
            setOrientation(deriveOrientation(latest))
            setFramesReceived((n) => n + frames.length)
          } catch {
            // Malformed payload; skip frame, hold last orientation.
          }
        }

        ws.onclose = () => {
          if (cleanup) return
          setConnected(false)
          const attempt = reconnectAttemptsRef.current++
          const delay = Math.min(1000 * Math.pow(2, attempt), 30000)
          setTimeout(connect, delay)
        }

        ws.onerror = () => {
          // close handler fires after error; retry handled there.
        }
      } catch {
        if (!cleanup) setConnected(false)
      }
    }

    connect()
    return () => {
      cleanup = true
      try { wsRef.current?.close() } catch { /* fail-silent */ }
    }
  }, [deviceId])

  return { orientation, connected, framesReceived }
}

// Phase 237-EXTEND — Per-category consent status (read-side).
// Pairs with useConsentSubmit() (wagmi-write side). The bridge endpoint
// reads from local consent_ledger; on-chain state is queried separately
// from the wallet via useReadContract if needed.
// noMock: consent state is real privacy data — fakes would mislead.
export function useConsentStatus(deviceId, category = '') {
  return useQuery({
    queryKey: ['consentStatus', deviceId, category],
    queryFn: () => {
      const path = category
        ? `/agent/gamer-consent-status?device_id=${encodeURIComponent(deviceId)}&category=${encodeURIComponent(category)}`
        : `/agent/gamer-consent-status?device_id=${encodeURIComponent(deviceId)}`
      return get(path, 'consentStatus', { noMock: true })
    },
    enabled: Boolean(deviceId),
    refetchInterval: 15000,
    staleTime: 10000,
    retry: 1,
  })
}

// Phase O1 C5 — Operator Agents shadow-mode visibility hooks.
//
// All three hooks set noMock: true — operator audit data must never be
// silently replaced with fabricated mock state. Empty/offline behavior:
// react-query holds last successful value or shows undefined → component
// renders explicit "BRIDGE OFFLINE" / "no findings" empty states.
//
// useOperatorActivation is the gate query. When row_count=0, the C5 drawer
// is hidden in DeveloperView and the other two hooks set enabled:false
// (zero polling cost for operators not running Phase O1 SHADOW agents).

// NOTE: bridge operator app is mounted at /operator AND its individual
// route declarations carry the "/operator/" prefix (codebase convention —
// see watchdog-status / suspension/* / gic-reset for precedent). The get()
// helper prepends _OP_PREFIX="/operator", so the path passed here must
// include the inner "/operator/" segment. Final URL becomes
// /operator/operator/operator-agent-* which matches the route definitions.
// Empirical bug caught at C9 activation 2026-05-07.
export function useOperatorActivation() {
  return useQuery({
    queryKey: ['operatorActivation'],
    queryFn: () => get('/operator/operator-agent-activation-log?limit=1', 'operatorActivation', { noMock: true }),
    refetchInterval: 60000, // 1 min — activation events are rare
    staleTime: 30000,
    retry: 1,
  })
}

export function useShadowLog({ agentId = '', decision = '', limit = 50, enabled = true } = {}) {
  const params = new URLSearchParams()
  if (agentId)  params.set('agent_id', agentId)
  if (decision) params.set('decision', decision)
  params.set('limit', String(Math.max(1, Math.min(500, limit))))
  return useQuery({
    queryKey: ['operatorAgentShadowLog', agentId, decision, limit],
    queryFn: () => get(`/operator/operator-agent-shadow-log?${params.toString()}`, 'operatorAgentShadowLog', { noMock: true }),
    enabled,
    refetchInterval: 30000, // shadow events not grind-critical; 30s is plenty
    staleTime: 15000,
    retry: 1,
  })
}

export function useDriftLog({ agentId = '', driftType = '', sinceMinutes = 1440, limit = 50, enabled = true } = {}) {
  const params = new URLSearchParams()
  if (agentId)    params.set('agent_id', agentId)
  if (driftType)  params.set('drift_type', driftType)
  // since_minutes capped at 30d (43200) by backend; mirror that here for safety
  params.set('since_minutes', String(Math.max(0, Math.min(43200, sinceMinutes))))
  params.set('limit', String(Math.max(1, Math.min(500, limit))))
  return useQuery({
    queryKey: ['operatorAgentDriftLog', agentId, driftType, sinceMinutes, limit],
    queryFn: () => get(`/operator/operator-agent-drift-log?${params.toString()}`, 'operatorAgentDriftLog', { noMock: true }),
    enabled,
    refetchInterval: 30000,
    staleTime: 15000,
    retry: 1,
  })
}
