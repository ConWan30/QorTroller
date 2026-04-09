// src/shared/api/hooks/index.js
// All live-data hooks — built on TanStack Query + apiFetch
// Each hook reads apiKey from authStore; public endpoints pass ''

import { useQuery } from '@tanstack/react-query'
import { EP, apiFetch } from '../endpoints'
import { useAuthStore } from '../../store/authStore'

// ─── shared query helper ─────────────────────────────────────
const q = (key, url, apiKey, staleTime) =>
  useQuery({
    queryKey: [key, apiKey],
    queryFn:  () => apiFetch(url, apiKey),
    staleTime,
    retry:    2,
  })

// ─── AGENT HOOKS (api_key required) ─────────────────────────

export function useTournamentReadiness() {
  const key = useAuthStore(s => s.apiKey)
  return q('tournamentReadiness', EP.TOURNAMENT_READINESS, key, 60_000)
}

export function useTournamentReadinessScore() {
  const key = useAuthStore(s => s.apiKey)
  return q('tournamentReadinessScore', EP.TOURNAMENT_READINESS_SCORE, key, 60_000)
}

export function usePreflightStatus() {
  const key = useAuthStore(s => s.apiKey)
  return q('preflightStatus', EP.TOURNAMENT_PREFLIGHT, key, 60_000)
}

export function useProtocolMaturity() {
  const key = useAuthStore(s => s.apiKey)
  return q('protocolMaturity', EP.PROTOCOL_MATURITY, key, 300_000)
}

export function useProtocolIntelligence() {
  const key = useAuthStore(s => s.apiKey)
  return q('protocolIntelligence', EP.PROTOCOL_INTELLIGENCE, key, 60_000)
}

export function useSupervisorStatus() {
  const key = useAuthStore(s => s.apiKey)
  return q('supervisorStatus', EP.SUPERVISOR_STATUS, key, 30_000)
}

export function useCampaignStatus() {
  const key = useAuthStore(s => s.apiKey)
  return q('campaignStatus', EP.CAMPAIGN_STATUS, key, 30_000)
}

export function useSeparationRatio() {
  const key = useAuthStore(s => s.apiKey)
  return q('separationRatio', EP.SEPARATION_RATIO, key, 120_000)
}

export function useEdgeAIProfile() {
  const key = useAuthStore(s => s.apiKey)
  return q('edgeAIProfile', EP.EDGE_AI_PROFILE, key, 120_000)
}

export function useIoSwarmStatus() {
  const key = useAuthStore(s => s.apiKey)
  return q('ioswarmStatus', EP.IOSWARM_STATUS, key, 60_000)
}

export function useVHPDualGateLog() {
  const key = useAuthStore(s => s.apiKey)
  return q('vhpDualGateLog', EP.VHP_DUAL_GATE_LOG, key, 60_000)
}

export function useEpochWindowAnalytics() {
  const key = useAuthStore(s => s.apiKey)
  return q('epochWindowAnalytics', EP.EPOCH_WINDOW_ANALYTICS, key, 120_000)
}

export function useConfidenceMultiplier() {
  const key = useAuthStore(s => s.apiKey)
  return q('confidenceMultiplier', EP.CONFIDENCE_MULTIPLIER, key, 60_000)
}

export function useFederationPeers() {
  const key = useAuthStore(s => s.apiKey)
  return q('federationPeers', EP.FEDERATION_PEERS, key, 60_000)
}

export function useL4CalibrationStatus() {
  const key = useAuthStore(s => s.apiKey)
  return q('l4CalibrationStatus', EP.L4_CALIBRATION_STATUS, key, 120_000)
}

// ─── PER-DEVICE HOOKS ────────────────────────────────────────

export function useVHPStatus(deviceId) {
  const key = useAuthStore(s => s.apiKey)
  return useQuery({
    queryKey:  ['vhpStatus', deviceId, key],
    queryFn:   () => apiFetch(EP.VHP_STATUS(deviceId), key),
    staleTime: 30_000,
    enabled:   !!deviceId,
  })
}

// PUBLIC — no api_key — served by dashboard_api.py /api/v1/player/{id}/eligibility
export function useEnrollmentStatus(deviceId) {
  return useQuery({
    queryKey:  ['enrollmentStatus', deviceId],
    queryFn:   () => apiFetch(EP.PLAYER_ELIGIBILITY(deviceId), ''),
    staleTime: 30_000,
    enabled:   !!deviceId,
  })
}

// PUBLIC — no api_key
export function usePlayerProfile(deviceId) {
  return useQuery({
    queryKey:  ['playerProfile', deviceId],
    queryFn:   () => apiFetch(EP.PLAYER_PROFILE(deviceId), ''),
    staleTime: 30_000,
    enabled:   !!deviceId,
  })
}

export function usePlayerCredential(deviceId) {
  return useQuery({
    queryKey:  ['playerCredential', deviceId],
    queryFn:   () => apiFetch(EP.PLAYER_CREDENTIAL(deviceId), ''),
    staleTime: 30_000,
    enabled:   !!deviceId,
  })
}

export function useProof(deviceId) {
  return useQuery({
    queryKey:  ['proof', deviceId],
    queryFn:   () => apiFetch(EP.PROOF(deviceId), ''),
    staleTime: 60_000,
    enabled:   !!deviceId,
  })
}

// PUBLIC — no auth
export function useDeviceCerts() {
  return q('deviceCerts', EP.DEVICES, '', 120_000)
}

export function useDeviceCert(profileId) {
  return useQuery({
    queryKey:  ['deviceCert', profileId],
    queryFn:   () => apiFetch(EP.DEVICE_CERT(profileId), ''),
    staleTime: 120_000,
    enabled:   !!profileId,
  })
}

// Manual trigger — enabled=false until user clicks
export function useGateTester(deviceId, enabled = false) {
  const key = useAuthStore(s => s.apiKey)
  return useQuery({
    queryKey:  ['gateTester', deviceId, key],
    queryFn:   () => apiFetch(EP.GATE(deviceId), key),
    staleTime: 0,
    enabled:   !!deviceId && !!key && enabled,
  })
}

// CURATOR — api_key
export function useDataLineage(deviceId) {
  const key = useAuthStore(s => s.apiKey)
  return useQuery({
    queryKey:  ['dataLineage', deviceId, key],
    queryFn:   () => apiFetch(EP.DATA_LINEAGE(deviceId), key),
    staleTime: 120_000,
    enabled:   !!deviceId && !!key,
  })
}

export function useOracleState(oracle = 'HUMANITY') {
  const key = useAuthStore(s => s.apiKey)
  return q(`oracleState_${oracle}`, EP.ORACLE_STATE(oracle), key, 60_000)
}

// CURATOR — token eligibility + DePIN multiplier stack
export function useTokenEligibility(deviceId) {
  const key = useAuthStore(s => s.apiKey)
  return useQuery({
    queryKey:  ['tokenEligibility', deviceId, key],
    queryFn:   () => apiFetch(EP.TOKEN_ELIGIBILITY(deviceId), key),
    staleTime: 120_000,
    enabled:   !!deviceId && !!key,
  })
}
