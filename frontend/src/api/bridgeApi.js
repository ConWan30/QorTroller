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
