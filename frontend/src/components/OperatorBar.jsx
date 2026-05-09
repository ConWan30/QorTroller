/**
 * Phase 238 Frontend — OperatorBar three-pill bar.
 *
 * Always-visible top-bar showing the three Operator Initiative agents:
 *   - Sentry   — event-correlation + provenance-recording      (Phase O1 C1)
 *   - Guardian — operational-diagnostic + audit-drafting       (Phase O1 C1)
 *   - Curator  — marketplace-listing-review + tier-compliance  (Phase 238 Step I)
 *
 * Pill state colors:
 *   gray   — agent inactive (placeholder agentId / not anchored)
 *   cyan   — O1_SHADOW active
 *   gold   — O2_SUGGEST graduated
 *   orange — O3_ENFORCE active
 *
 * Visual consistency demands all three appear together — Curator alone
 * would imply Curator is the only Operator agent, breaking the ≥3-agent
 * cross-agent skill separation invariant.
 */
import { useCuratorStatus, useSentryStatus, useDriftLog } from '../api/bridgeApi'

export function OperatorBar({ onClick }) {
  const curator = useCuratorStatus()
  const sentry  = useSentryStatus()
  const drift   = useDriftLog({ sinceMinutes: 60, limit: 1 })

  // Sentry pill — shadow_log non-empty implies Sentry is anchored + producing
  const sentryActive = sentry.data?.entries?.length > 0
  // Guardian pill — drift findings recent imply Guardian is observing
  const guardianActive = (drift.data?.findings?.length || 0) > 0 || sentry.data?.entries?.length > 0
  const guardianDrift = (drift.data?.findings?.length || 0) > 0
  // Curator pill — curator_review_enabled OR placeholder still in O1_SHADOW infra
  const curatorEnabled = Boolean(curator.data?.curator_review_enabled)
  const curatorTotal   = Number(curator.data?.total_reviews || 0)
  const curatorFlagged = Number(curator.data?.flagged_reviews || 0)

  return (
    <div style={{
      display:       'flex',
      alignItems:    'center',
      gap:           8,
      padding:       '4px 12px',
      fontFamily:    "'JetBrains Mono', monospace",
      fontSize:      10,
      letterSpacing: '0.05em',
    }}>
      <span style={{ color: 'var(--vapi-tier-basic)', fontSize: 9, marginRight: 4 }}>
        OPS:
      </span>

      {/* Sentry */}
      <Pill
        label="SENTRY"
        active={sentryActive}
        accent={sentryActive ? 'var(--vapi-agent-shadow)' : 'var(--vapi-agent-inactive)'}
        detail={sentryActive ? 'O1 SHADOW' : 'INACTIVE'}
        onClick={onClick}
      />

      {/* Guardian */}
      <Pill
        label="GUARDIAN"
        active={guardianActive}
        accent={
          guardianDrift     ? 'var(--vapi-block)' :
          guardianActive    ? 'var(--vapi-agent-shadow)' :
          'var(--vapi-agent-inactive)'
        }
        detail={
          guardianDrift     ? `DRIFT ${drift.data?.findings?.length}` :
          guardianActive    ? 'O1 SHADOW' :
          'INACTIVE'
        }
        onClick={onClick}
      />

      {/* Curator */}
      <Pill
        label="CURATOR"
        active={curator.isSuccess}
        accent={
          curatorFlagged > 0 ? 'var(--vapi-warn)' :
          curatorEnabled     ? 'var(--vapi-agent-shadow)' :
          'var(--vapi-agent-inactive)'
        }
        detail={
          !curator.isSuccess  ? '—' :
          curatorFlagged > 0  ? `FLAGGED ${curatorFlagged}/${curatorTotal}` :
          curatorEnabled      ? `O1 SHADOW ${curatorTotal}` :
          'INACTIVE'
        }
        onClick={onClick}
      />
    </div>
  )
}

function Pill({ label, active, accent, detail, onClick }) {
  return (
    <button
      onClick={onClick}
      style={{
        display:        'inline-flex',
        alignItems:     'center',
        gap:            6,
        padding:        '3px 10px',
        background:     'rgba(255,255,255,0.02)',
        border:         `1px solid ${accent}`,
        borderRadius:   2,
        color:          accent,
        cursor:         onClick ? 'pointer' : 'default',
        fontFamily:     'inherit',
        fontSize:       9,
        letterSpacing:  '0.06em',
        opacity:        active ? 1 : 0.6,
        transition:     'all 0.18s',
      }}
    >
      <span style={{
        width:        6,
        height:       6,
        borderRadius: 3,
        background:   accent,
        boxShadow:    active ? `0 0 8px ${accent}` : 'none',
        flexShrink:   0,
      }} />
      <span style={{ fontWeight: 700 }}>{label}</span>
      <span style={{ opacity: 0.7, fontSize: 8 }}>{detail}</span>
    </button>
  )
}
