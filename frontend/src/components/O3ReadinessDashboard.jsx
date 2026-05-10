// Phase O3-READINESS-DASHBOARD — single-panel countdown surface
//
// Visualizes per-agent progress toward O3 ACTING anchor across all gates:
//   shadow_age clock (504h)        — time-based, external
//   cedar_eval count (100)         — accrues with agent activity
//   bundle/scope drift (0/30d)     — fail-closed on detected drift
//   o2_age clock (504h)            — time-based, external (only at O2_SUGGEST)
//   draft_payload count (50)       — accrues via polling-loop triggers
//   disagreement_rate (≤0.05)      — operator decisions in DraftReviewDrawer
//   false_positive_rate (==0.0)    — Curator ZERO TOLERANCE
//   operator_dual_key_present       — operator flag
//   kms_hsm_production_ready        — operator flag (Sentry+Guardian)
//   github_app_oauth_tokens_valid   — operator flag (Guardian-only)
//   marketplace_curator_role        — operator flag (Curator-only)
//
// Reads GET /operator/fleet-readiness-root (Phase O1-FRR-ENDPOINT). The
// endpoint returns o2_blockers + o3_blockers as human-readable strings; we
// parse them where useful for progress visualization, otherwise display
// raw. Activation gate handled by parent (only mounts when o1Active).

import { FONTS, DEVELOPER } from '../shared/design/tokens'
import { useFleetReadinessRoot } from '../api/bridgeApi'

// Frozen gate constants (must mirror bridge/operator_initiative_advancement.py)
const GATES = {
  PHASE_O2_SHADOW_MIN_HOURS:       504,    // 3 weeks
  PHASE_O2_EVAL_MIN_COUNT:         100,
  PHASE_O2_DRIFT_MAX_30D:          0,
  PHASE_O3_SUGGEST_MIN_HOURS:      504,
  PHASE_O3_DRAFT_PAYLOAD_MIN:      50,
  PHASE_O3_DISAGREEMENT_RATE_MAX:  0.05,
  PHASE_O3_FALSE_POSITIVE_RATE_MAX: 0.0,
}

const AGENT_DISPLAY = {
  anchor_sentry: { label: 'SENTRY',   tier: ['kms_hsm'] },
  guardian:      { label: 'GUARDIAN', tier: ['kms_hsm', 'github_app'] },
  curator:       { label: 'CURATOR',  tier: ['curator_role', 'false_positive'] },
}

function ProgressBar({ value, target, label, unit = '', highBetter = true, danger = false }) {
  const ratio = target > 0 ? Math.min(1.0, value / target) : 1.0
  const reached = highBetter ? ratio >= 1.0 : value <= target
  const color = reached ? DEVELOPER.green : (danger ? DEVELOPER.red : DEVELOPER.amber)
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between',
        fontFamily: FONTS.mono, fontSize: 8, color: DEVELOPER.t3,
        letterSpacing: '0.1em', textTransform: 'uppercase',
      }}>
        <span>{label}</span>
        <span style={{ color }}>{value}{unit} / {target}{unit}</span>
      </div>
      <div style={{
        height: 4, background: DEVELOPER.bg, borderRadius: 2,
        border: `1px solid ${DEVELOPER.bd}`, overflow: 'hidden',
      }}>
        <div style={{
          width: `${ratio * 100}%`, height: '100%',
          background: color, transition: 'width 0.3s ease',
        }} />
      </div>
    </div>
  )
}

function FlagPill({ label, ok, hint = '' }) {
  const color = ok ? DEVELOPER.green : DEVELOPER.red
  return (
    <div
      title={hint}
      style={{
        display: 'flex', alignItems: 'center', gap: 4,
        fontFamily: FONTS.mono, fontSize: 8, fontWeight: 600,
        color,
        background: `${color}1a`,
        border: `1px solid ${color}55`,
        borderRadius: 3,
        padding: '2px 6px',
        letterSpacing: '0.1em',
      }}
    >
      <span>{ok ? '✓' : '✗'}</span>
      <span style={{ textTransform: 'uppercase' }}>{label}</span>
    </div>
  )
}

// Parse a blocker string like "shadow_age_152.1h_under_min_504h" into
// {kind, value, target}. Returns null if no useful structure found.
function parseShadowAge(blockers) {
  for (const b of blockers || []) {
    const m = b.match(/shadow_age_([\d.]+)h_under_min_([\d.]+)h/)
    if (m) return { value: parseFloat(m[1]), target: parseFloat(m[2]) }
  }
  return null
}

function parseO2Age(blockers) {
  for (const b of blockers || []) {
    const m = b.match(/o2_age_([\d.]+)h_under_min_([\d.]+)h/)
    if (m) return { value: parseFloat(m[1]), target: parseFloat(m[2]) }
  }
  return null
}

function parseDraftCount(blockers) {
  for (const b of blockers || []) {
    const m = b.match(/draft_payload_count_(\d+)_under_min_(\d+)/)
    if (m) return { value: parseInt(m[1]), target: parseInt(m[2]) }
  }
  return null
}

function parseDisagreement(blockers) {
  for (const b of blockers || []) {
    const m = b.match(/disagreement_rate_([\d.]+)_over_max_([\d.]+)/)
    if (m) return { value: parseFloat(m[1]), target: parseFloat(m[2]) }
  }
  return null
}

function parseFalsePositive(blockers) {
  for (const b of blockers || []) {
    const m = b.match(/false_positive_rate_([\d.]+)_over_max_([\d.]+)/)
    if (m) return { value: parseFloat(m[1]), target: parseFloat(m[2]) }
  }
  return null
}

function hasBlocker(blockers, substring) {
  return (blockers || []).some(b => b.includes(substring))
}

function AgentCard({ agent }) {
  const display = AGENT_DISPLAY[agent.agent_id] || { label: agent.agent_id.toUpperCase(), tier: [] }
  const phase = agent.current_phase || 'UNKNOWN'
  const phaseColor = phase === 'O3_ACT' ? DEVELOPER.green
                   : phase === 'O2_SUGGEST' ? DEVELOPER.amber
                   : phase === 'O1_SHADOW' ? DEVELOPER.orange
                   : DEVELOPER.t3
  const isCurator = agent.agent_id === 'curator'
  const isGuardian = agent.agent_id === 'guardian'

  // Pick the relevant gate set: if currently at O1_SHADOW, show O2 gates;
  // if at O2_SUGGEST, show O3 gates (the meaningful target). If at O3_ACT,
  // show nothing — anchor is done.
  const showingO2 = phase === 'O1_SHADOW'
  const showingO3 = phase === 'O2_SUGGEST'

  // Shadow-age & eval-count for O2 gate
  const shadowAge = showingO2 ? (
    parseShadowAge(agent.o2_blockers) || {
      value: agent.shadow_age_hours, target: GATES.PHASE_O2_SHADOW_MIN_HOURS,
    }
  ) : null
  const evalCount = showingO2 ? {
    value: agent.cedar_eval_count, target: GATES.PHASE_O2_EVAL_MIN_COUNT,
  } : null

  // O3 progress reads
  const o2Age = showingO3 ? (
    parseO2Age(agent.o3_blockers) || { value: 0, target: GATES.PHASE_O3_SUGGEST_MIN_HOURS }
  ) : null
  const draftCount = showingO3 ? (
    parseDraftCount(agent.o3_blockers) || { value: 0, target: GATES.PHASE_O3_DRAFT_PAYLOAD_MIN }
  ) : null
  const disagreement = showingO3 ? (
    parseDisagreement(agent.o3_blockers) || { value: 0, target: GATES.PHASE_O3_DISAGREEMENT_RATE_MAX }
  ) : null
  const falsePositive = (showingO3 && isCurator) ? (
    parseFalsePositive(agent.o3_blockers) || { value: 0, target: GATES.PHASE_O3_FALSE_POSITIVE_RATE_MAX }
  ) : null

  // Operator flags (only meaningful at O2_SUGGEST → O3 transition)
  const dualKeyOK = showingO3 && !hasBlocker(agent.o3_blockers, 'operator_dual_key_not_present')
  const kmsOK = showingO3 && !hasBlocker(agent.o3_blockers, 'kms_hsm_production_not_provisioned')
  const githubOK = showingO3 && !hasBlocker(agent.o3_blockers, 'github_app_oauth_tokens_not_valid')
  const curatorRoleOK = showingO3 && !hasBlocker(agent.o3_blockers, 'marketplace_setCurator_role_not_assigned')

  // Drift counts (always visible — fail-closed if any drift in 30d)
  const driftBundle = agent.bundle_hash_drift_count_30d || 0
  const driftScope = agent.scope_hash_governance_drift_count_30d || 0

  return (
    <div style={{
      background: DEVELOPER.bg2,
      border: `1px solid ${phaseColor}55`,
      borderRadius: 4,
      padding: 10,
      display: 'flex', flexDirection: 'column', gap: 8,
      minWidth: 0,
    }}>
      {/* Header: name + phase chip */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{
          fontFamily: FONTS.display, fontSize: 11, fontWeight: 700,
          color: DEVELOPER.t1, letterSpacing: '0.2em',
        }}>{display.label}</div>
        <div style={{
          fontFamily: FONTS.mono, fontSize: 8, fontWeight: 700,
          color: phaseColor, background: `${phaseColor}1a`,
          border: `1px solid ${phaseColor}66`, borderRadius: 3,
          padding: '2px 6px', letterSpacing: '0.1em',
        }}>{phase}</div>
      </div>

      {/* O2 gate section (when at O1_SHADOW) */}
      {showingO2 && shadowAge && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <div style={{
            fontFamily: FONTS.mono, fontSize: 8, color: DEVELOPER.amber,
            letterSpacing: '0.16em', textTransform: 'uppercase',
          }}>→ O2 Suggest</div>
          <ProgressBar value={shadowAge.value.toFixed(1)} target={shadowAge.target} label="Shadow Age" unit="h" />
          <ProgressBar value={evalCount.value} target={evalCount.target} label="Cedar Evals" />
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginTop: 2 }}>
            <FlagPill label="Bundle Drift" ok={driftBundle === 0}
              hint={`${driftBundle} bundle-hash drift events in 30d (max ${GATES.PHASE_O2_DRIFT_MAX_30D})`} />
            <FlagPill label="Scope Drift" ok={driftScope === 0}
              hint={`${driftScope} scope-governance drift events in 30d (max ${GATES.PHASE_O2_DRIFT_MAX_30D})`} />
          </div>
        </div>
      )}

      {/* O3 gate section (when at O2_SUGGEST) */}
      {showingO3 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <div style={{
            fontFamily: FONTS.mono, fontSize: 8, color: DEVELOPER.green,
            letterSpacing: '0.16em', textTransform: 'uppercase',
          }}>→ O3 Acting</div>
          <ProgressBar value={o2Age.value.toFixed(1)} target={o2Age.target} label="O2 Age" unit="h" />
          <ProgressBar value={draftCount.value} target={draftCount.target} label="Drafts" />
          <ProgressBar
            value={disagreement.value.toFixed(4)} target={disagreement.target}
            label="Disagreement" highBetter={false}
            danger={disagreement.value > disagreement.target}
          />
          {falsePositive && (
            <ProgressBar
              value={falsePositive.value.toFixed(4)} target={falsePositive.target}
              label="False Positive" highBetter={false}
              danger={falsePositive.value > falsePositive.target}
            />
          )}
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginTop: 4 }}>
            <FlagPill label="Dual Key" ok={dualKeyOK} hint="operator_dual_key_present cfg flag" />
            {(agent.agent_id === 'anchor_sentry' || isGuardian) && (
              <FlagPill label="KMS HSM" ok={kmsOK} hint="kms_hsm_production_ready cfg flag" />
            )}
            {isGuardian && (
              <FlagPill label="GitHub App" ok={githubOK} hint="github_app_oauth_tokens_valid cfg flag" />
            )}
            {isCurator && (
              <FlagPill label="setCurator" ok={curatorRoleOK} hint="marketplace_curator_role_assigned cfg flag" />
            )}
          </div>
        </div>
      )}

      {/* O3_ACT terminal — anchor is done */}
      {phase === 'O3_ACT' && (
        <div style={{
          fontFamily: FONTS.mono, fontSize: 9, color: DEVELOPER.green,
          textAlign: 'center', padding: '8px 0',
          letterSpacing: '0.1em',
        }}>✓ ANCHORED — LIVE WRITE AUTHORITY</div>
      )}

      {/* UNKNOWN / error fallback */}
      {phase !== 'O1_SHADOW' && phase !== 'O2_SUGGEST' && phase !== 'O3_ACT' && (
        <div style={{
          fontFamily: FONTS.mono, fontSize: 9, color: DEVELOPER.t3,
          textAlign: 'center', padding: '8px 0',
        }}>{agent.error || 'phase unknown — bridge has not anchored this agent'}</div>
      )}
    </div>
  )
}

export function O3ReadinessDashboard({ enabled = true }) {
  const { data, isError, isLoading } = useFleetReadinessRoot({ enabled })
  const perAgent = data?.per_agent || []
  const aligned = data?.fleet_phase_aligned
  const target = data?.next_alignment_target || '—'
  const frr = data?.frr_hex || ''
  const o2Count = data?.fleet_at_o2_ready_count ?? 0
  const o3Count = data?.fleet_at_o3_ready_count ?? 0

  // Order: Sentry → Guardian → Curator (matches parallel_o2/o3_anchor.py order)
  const ORDER = ['anchor_sentry', 'guardian', 'curator']
  const orderedAgents = ORDER
    .map(id => perAgent.find(a => a.agent_id === id))
    .filter(Boolean)
  // Append any other agents that came back (forward-compat)
  for (const a of perAgent) {
    if (!ORDER.includes(a.agent_id)) orderedAgents.push(a)
  }

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0,
      background: DEVELOPER.bg1,
      border: `1px solid ${DEVELOPER.bd}`,
      borderRadius: 4,
    }}>
      {/* Fleet summary band */}
      <div style={{
        padding: '8px 12px',
        borderBottom: `1px solid ${DEVELOPER.bd}`,
        display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap',
      }}>
        <div style={{
          fontFamily: FONTS.mono, fontSize: 8, color: DEVELOPER.t3,
          letterSpacing: '0.1em', textTransform: 'uppercase',
        }}>FRR
          <span style={{
            color: DEVELOPER.amber, marginLeft: 6, fontWeight: 700,
          }} title={frr}>{frr.slice(0, 12)}…{frr.slice(-6)}</span>
        </div>
        <div style={{
          fontFamily: FONTS.mono, fontSize: 8, color: DEVELOPER.t3,
          letterSpacing: '0.1em', textTransform: 'uppercase',
        }}>ALIGNED
          <span style={{
            color: aligned ? DEVELOPER.green : DEVELOPER.amber,
            marginLeft: 6, fontWeight: 700,
          }}>{aligned ? 'YES' : 'NO'}</span>
        </div>
        <div style={{
          fontFamily: FONTS.mono, fontSize: 8, color: DEVELOPER.t3,
          letterSpacing: '0.1em', textTransform: 'uppercase',
        }}>NEXT
          <span style={{
            color: DEVELOPER.t1, marginLeft: 6, fontWeight: 700,
          }}>{target}</span>
        </div>
        <div style={{ flex: 1 }} />
        <div style={{
          fontFamily: FONTS.mono, fontSize: 8, color: DEVELOPER.t3,
        }}>{isLoading ? '… loading' : isError ? '⚠ bridge offline' : `${o2Count} O2 ready · ${o3Count} O3 ready`}</div>
      </div>

      {/* Per-agent cards */}
      <div style={{
        flex: 1, minHeight: 0, overflowY: 'auto',
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
        gap: 10,
        padding: 12,
      }}>
        {orderedAgents.length === 0 ? (
          <div style={{
            fontFamily: FONTS.mono, fontSize: 10, color: DEVELOPER.t3,
            textAlign: 'center', padding: 24, gridColumn: '1 / -1',
          }}>
            {isLoading ? '… loading fleet readiness' : isError ? '⚠ FRR endpoint offline' : 'No agents in fleet'}
          </div>
        ) : orderedAgents.map(a => <AgentCard key={a.agent_id} agent={a} />)}
      </div>

      {/* Footnote */}
      <div style={{
        padding: '6px 12px',
        borderTop: `1px solid ${DEVELOPER.bd}`,
        fontFamily: FONTS.mono, fontSize: 8, color: DEVELOPER.t3,
        letterSpacing: '0.05em',
      }}>
        ↑ gates frozen by operator_initiative_advancement.py · 30s refetch · FRR v1 SHA-256
      </div>
    </div>
  )
}
