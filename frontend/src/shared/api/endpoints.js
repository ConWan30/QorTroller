// src/shared/api/endpoints.js
// Single source of truth for all VAPI bridge API endpoints
// All paths proxied by Vite: /agent → http://localhost:8080/agent
//
// AUTH: VAPI backend reads api_key as a QUERY PARAMETER (?api_key=...)
// NOT as a header. All operator endpoints use Query(api_key) in FastAPI.

export const EP = {
  // Health (no auth)
  HEALTH:                     '/health',

  // Agent endpoints (require api_key query param)
  TOURNAMENT_READINESS:       '/agent/tournament-readiness',
  TOURNAMENT_READINESS_SCORE: '/agent/tournament-readiness-score',
  TOURNAMENT_PREFLIGHT:       '/agent/tournament-preflight-status',
  PROTOCOL_MATURITY:          '/agent/protocol-maturity',
  PROTOCOL_INTELLIGENCE:      '/agent/protocol-intelligence',
  SUPERVISOR_STATUS:          '/agent/supervisor-status',
  CAMPAIGN_STATUS:            '/agent/campaign-status',
  SEPARATION_RATIO:           '/agent/separation-ratio-status',
  SEPARATION_BREAKTHROUGH:    '/agent/separation-ratio-breakthrough',
  L4_CALIBRATION_STATUS:      '/agent/l4-calibration-status',
  EDGE_AI_PROFILE:            '/agent/edge-ai-profile',
  IOSWARM_STATUS:             '/agent/ioswarm-status',
  POAD_ANCHOR_STATUS:         '/agent/poad-anchor-status',
  DUAL_PRIMITIVE_STATUS:      '/agent/dual-primitive-status',
  EPOCH_WINDOW_ANALYTICS:     '/agent/epoch-window-analytics',
  VHP_DUAL_GATE_LOG:          '/agent/vhp-dual-gate-log',
  CONFIDENCE_MULTIPLIER:      '/agent/confidence-score-multiplier-status',
  PREFLIGHT_RUN:              '/agent/run-tournament-preflight',
  PROTOCOL_MATURITY:          '/agent/protocol-maturity',

  // VHP per device (api_key)
  VHP_STATUS:    (deviceId) => `/agent/vhp-status/${deviceId}`,

  // Gate (api_key)
  GATE:          (deviceId) => `/gate/${deviceId}`,

  // Devices (public — no auth)
  DEVICES:                    '/devices',
  DEVICE_CERT:   (profileId) => `/devices/${profileId}/certification`,

  // Dashboard API (public — no auth, mounted at /api/v1 by dashboard_api.py)
  PLAYER_ELIGIBILITY: (deviceId) => `/api/v1/player/${deviceId}/eligibility`,
  PLAYER_CREDENTIAL:  (deviceId) => `/api/v1/player/${deviceId}/credential`,
  PLAYER_PROFILE:     (deviceId) => `/api/v1/player/${deviceId}/profile`,

  // Proof page (public — returns HTML)
  PROOF:         (deviceId) => `/proof/${deviceId}`,

  // Curator (api_key)
  DATA_LINEAGE:       (deviceId) => `/curator/data-lineage/${deviceId}`,
  ORACLE_STATE:       (oracle)   => `/curator/oracle-state/${oracle}`,
  TOKEN_ELIGIBILITY:  (deviceId) => `/curator/token-eligibility/${deviceId}`,

  // Federation (api_key)
  FEDERATION_PEERS:           '/federation/peers',

  // WebSocket endpoints (not fetched, used by useWebSocket hooks directly)
  WS_RECORDS:                 'ws://localhost:8080/ws/records',
  WS_TWIN:       (deviceId) => `ws://localhost:8080/ws/twin/${deviceId}`,
}

/**
 * apiFetch — fetch a VAPI bridge endpoint with optional api_key.
 *
 * The VAPI backend authenticates via ?api_key= query parameter (not a header).
 * FastAPI: `api_key: str = Query(...)` — see operator_api.py _check_key().
 *
 * Public endpoints (devices, dashboard /api/v1/*) pass apiKey = ''.
 */
export const apiFetch = async (url, apiKey = '') => {
  const sep     = url.includes('?') ? '&' : '?'
  const fullUrl = apiKey
    ? `${url}${sep}api_key=${encodeURIComponent(apiKey)}`
    : url
  const response = await fetch(fullUrl)
  if (!response.ok) {
    const text = await response.text().catch(() => response.statusText)
    throw new Error(`HTTP ${response.status}: ${text}`)
  }
  return response.json()
}
