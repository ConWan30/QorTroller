import { useQuery } from '@tanstack/react-query'
import { activateMock, deactivateMock, isMockActive, MOCK } from './mockBridge'

const BASE = ''  // vite proxy handles /agent/* → localhost:8080

async function get(path, mockKey) {
  if (isMockActive()) return MOCK[mockKey]?.()
  try {
    const res = await fetch(path, { signal: AbortSignal.timeout(5000) })
    if (!res.ok) { activateMock(); return MOCK[mockKey]?.() }
    deactivateMock()
    return res.json()
  } catch {
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
