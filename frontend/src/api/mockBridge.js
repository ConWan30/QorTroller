// Realistic mock data matching openapi.yaml schemas — auto-activates on 5xx/timeout

export const MOCK_ACTIVE_KEY = '__vapiMockActive'

export function isMockActive() {
  return sessionStorage.getItem(MOCK_ACTIVE_KEY) === 'true'
}

export function activateMock() {
  sessionStorage.setItem(MOCK_ACTIVE_KEY, 'true')
}

export function deactivateMock() {
  sessionStorage.removeItem(MOCK_ACTIVE_KEY)
}

// Simulate subtle biological drift in numeric values
let _drift = 0
function drift(base, range = 0.05) {
  _drift += (Math.random() - 0.5) * 0.01
  _drift = Math.max(-1, Math.min(1, _drift))
  return +(base + base * _drift * range).toFixed(4)
}

const now = () => new Date().toISOString()

export const MOCK = {
  protocolCoherenceStatus: () => ({
    protocol_coherence_enabled: true,
    total_anchors: 12,
    latest_merkle_root: 'a3f8e1c2b5d7' + Math.floor(Math.random() * 0xfffff).toString(16).padStart(4, '0'),
    agent_count: 38,
    on_chain_confirmed: true,
    last_anchor_ts: now(),
    timestamp: now(),
  }),

  tournamentBlockerSummary: () => ({
    tournament_blocker_summary_enabled: true,
    total_blockers: 3,
    overall_blocked: true,
    preflight_pass: false,
    capture_healthy: true,
    all_pairs_above_1: false,
    timestamp: now(),
    blockers: [
      { severity: 'P0', source: 'per_pair_gap', key: 'P1vP3', detail: 'distance=0.032 (target >1.0)' },
      { severity: 'P0', source: 'per_pair_gap', key: 'P2vP3', detail: 'distance=0.401 (target >1.0)' },
      { severity: 'P1', source: 'l4_calibration', key: 'dim_staleness', detail: 'live_dim=13 vs calib_dim=12' },
    ],
  }),

  perPairGapStatus: () => ({
    per_pair_gap_log_enabled: true,
    all_pairs_above_1: false,
    session_type: 'tremor_resting',
    pair_count: 3,
    blocker_pairs: ['P1vP3', 'P2vP3'],
    timestamp: now(),
    pairs: [
      { pair_key: 'P1vP2', player_i: 'P1', player_j: 'P2', distance: drift(0.749), above_1_0: false },
      { pair_key: 'P1vP3', player_i: 'P1', player_j: 'P3', distance: drift(0.032, 0.2), above_1_0: false },
      { pair_key: 'P2vP3', player_i: 'P2', player_j: 'P3', distance: drift(0.401), above_1_0: false },
    ],
  }),

  perPairGapProjection: () => ({
    per_pair_gap_projection_enabled: true,
    any_feasible: false,
    max_days_to_1_0: null,
    projected_tge_date: null,
    session_type: 'tremor_resting',
    timestamp: now(),
    projections: [
      { pair_key: 'P1vP2', current_dist: drift(0.749), trend: 'IMPROVING', velocity_per_day: 0.003, days_to_1_0: 84 },
      { pair_key: 'P1vP3', current_dist: drift(0.032, 0.2), trend: 'WORSENING', velocity_per_day: -0.001, days_to_1_0: null },
      { pair_key: 'P2vP3', current_dist: drift(0.401), trend: 'STABLE', velocity_per_day: 0.0001, days_to_1_0: null },
    ],
  }),

  separationDefensibilityStatus: () => ({
    defensible: false,
    ratio: drift(1.177, 0.02),
    n_per_player: { P1: 10, P2: 8, P3: 6 },
    min_n_per_player: 10,
    all_pairs_above_1: false,
    found: true,
  }),

  invariantGateStatus: () => ({
    pv_ci_enabled: true,
    gate_pass: true,
    total_checked: 26,
    failure_count: 0,
    last_failures: [],
    last_run_ts: now(),
    timestamp: now(),
  }),

  fleetCoherenceStatus: () => ({
    fleet_coherence_enabled: true,
    total_entries: 4,
    active_contradictions: 1,
    active_orphans: 1,
    active_inversions: 0,
    timestamp: now(),
    entries: [
      { coherence_id: 'coh_a3b2c1', rule_name: 'PER_PAIR_GAP_BLOCKER_UNRESOLVED', severity: 'HIGH', type: 'ORPHAN', created_at: now() },
      { coherence_id: 'coh_d4e5f6', rule_name: 'RATIO_VELOCITY_NEGATIVE', severity: 'MEDIUM', type: 'ORPHAN', created_at: now() },
    ],
  }),

  // Phase 235-DASH-UPGRADE — auto-trigger telemetry mock (off by default
  // so dev-mode renders an OFF chip without triggering false ARMED state)
  autoTriggerStatus: () => ({
    auto_trigger_enabled: false,
    agent_alive:          false,
    fires_this_run:       0,
    last_fire_age_s:      null,
    next_eligible_in_s:   0,
    min_interval_s:       300,
    quiescence_window:    60,
    activity_window:      120,
    stopped:              false,
    timestamp:            now(),
  }),

  protocolCoherenceHistory: () => ({
    entries: Array.from({ length: 8 }, (_, i) => ({
      merkle_root: Math.random().toString(16).slice(2, 18),
      agent_count: 38,
      on_chain_confirmed: true,
      created_at: new Date(Date.now() - i * 3600_000).toISOString(),
    })),
    total_entries: 8,
    chain_intact: true,
    timestamp: now(),
  }),

  captureVelocityOracle: () => ({
    capture_velocity_oracle_enabled: true,
    probe_type: 'tremor_resting',
    sessions_per_day: drift(0.8),
    sessions_stagnant: false,
    ratio_velocity: drift(0.002),
    velocity_stagnant: false,
    overall_capture_healthy: true,
    recommended_action: 'CONTINUE_CURRENT_PROTOCOL',
    timestamp: now(),
  }),

  // Phase 235-FINAL: grind-critical live indicators
  captureHealth: () => ({
    pcc_enabled: true,
    capture_state: 'NOMINAL',
    host_state: 'EXCLUSIVE_USB',
    poll_rate_hz: drift(1002.0, 0.002),
    sustained_duration_s: drift(180.0, 0.01),
    grind_mode: true,
    grind_ready: true,
    grind_target: 100,
    consecutive_clean_toward_target: Math.floor(drift(12, 0.1)),
    session_counting_paused: false,
    gameplay_context_enabled: true,
    latest_gameplay_context: 'ACTIVE_GAMEPLAY',
    timestamp: now(),
  }),

  grindChain: () => ({
    grind_session_id: 'grind_phase235_v1',
    chain_length: Math.floor(drift(12, 0.1)),
    latest_gic_hash: 'a3b2c1d4e5f6' + Math.random().toString(16).slice(2, 54),
    chain_intact: true,
    genesis_ts: Date.now() / 1000 - 3600 * 24,
    latest_ts: Date.now() / 1000 - 120,
    latest_gameplay_context: 'ACTIVE_GAMEPLAY',
    timestamp: now(),
  }),

  tournamentPreflight: () => ({
    separation_ok: false,
    l4_ok: true,
    gate_ok: true,
    cert_ok: true,
    audit_ok: true,
    overall_pass: false,
    biometric_ttl_ok: true,
    all_pairs_p0_ok: false,
    conditions_detail: { separation: 'ratio=1.177 but all_pairs_p0_ok=False: P1vP3=0.032' },
    error: null,
  }),
}

// Wrap a fetch call with mock fallback
export async function fetchWithMockFallback(url, fetchFn, mockKey) {
  if (isMockActive()) {
    return MOCK[mockKey]?.() ?? null
  }
  try {
    const res = await fetchFn(url)
    if (res.status >= 500) { activateMock(); return MOCK[mockKey]?.() ?? null }
    deactivateMock()
    return res
  } catch {
    activateMock()
    return MOCK[mockKey]?.() ?? null
  }
}
