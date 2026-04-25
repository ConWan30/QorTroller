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

export function useFleetCoherenceStatus() {
  return useQuery({
    queryKey: ['fleetCoherenceStatus'],
    queryFn: () => get('/agent/fleet-coherence-status', 'fleetCoherenceStatus'),
    refetchInterval: 8000,
    staleTime: 5000,
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
