// Phase O1 C5 — ShadowLogPanel
//
// Surfaces the most recent Cedar policy evaluations (operator_agent_shadow_log)
// for both Anchor Sentry + Guardian agents. Read-only operator audit panel.
// Mounted inside OperatorAgentsDrawer (bottom-edge slide-up in DeveloperView).
//
// Decision color tinting (matches Cedar v3 semantics):
//   permit*                          → green   (action allowed)
//   permit_with_shadow_constraint    → amber   (allowed but in shadow mode)
//   forbid_lane_violation            → orange  (lane prefix violated)
//   forbid_capability_inactive       → orange  (skill not in current bundle)
//   forbid_agent_not_principal       → red     (cross-agent attempt)
//   forbid_explicit_policy           → red     (policy explicitly denied)
//   forbid_default_deny              → red     (no matching policy; safest)
//
// Security:
//   - Resource strings truncated to 64 chars (defensive layout + render cost)
//   - All text rendered via React (auto-escaped); no dangerouslySetInnerHTML
//   - Decision filter values are FROZEN enum literals (no string injection risk)

import { useState } from 'react'
import { useShadowLog } from '../api/bridgeApi'
import { FONTS, DEVELOPER } from '../shared/design/tokens'

const DECISION_COLORS = {
  permit:                          DEVELOPER.green,
  permit_with_shadow_constraint:   DEVELOPER.amber,
  forbid_lane_violation:           DEVELOPER.orange,
  forbid_capability_inactive:      DEVELOPER.orange,
  forbid_agent_not_principal:      DEVELOPER.red,
  forbid_explicit_policy:          DEVELOPER.red,
  forbid_default_deny:             DEVELOPER.red,
}

const DECISION_FILTER_OPTIONS = [
  { value: '',                                label: 'ALL' },
  { value: 'permit',                          label: 'PERMIT' },
  { value: 'permit_with_shadow_constraint',   label: 'SHADOW_CONSTRAINT' },
  { value: 'forbid_lane_violation',           label: 'FORBID_LANE' },
  { value: 'forbid_capability_inactive',      label: 'FORBID_CAP' },
  { value: 'forbid_agent_not_principal',      label: 'FORBID_AGENT' },
  { value: 'forbid_explicit_policy',          label: 'FORBID_EXPLICIT' },
  { value: 'forbid_default_deny',             label: 'FORBID_DEFAULT' },
]

const SENTRY_ID   = '0xb21e1ec258d2d381c313f84944bd36fbc63badb2c9a24c2412212d3a27e3e42c'
const GUARDIAN_ID = '0xbd8c7fba08815b7ed343973c9c7300c062303b1acd19e8d9847a953ce5fa38d1'

const AGENT_FILTER_OPTIONS = [
  { value: '',          label: 'BOTH' },
  { value: SENTRY_ID,   label: 'SENTRY' },
  { value: GUARDIAN_ID, label: 'GUARDIAN' },
]

function FilterChip({ active, label, onClick }) {
  return (
    <button
      onClick={onClick}
      style={{
        background: active ? `${DEVELOPER.orange}26` : 'transparent',
        border: `1px solid ${active ? DEVELOPER.orange : DEVELOPER.bd}`,
        borderRadius: 4,
        padding: '3px 8px',
        fontFamily: FONTS.mono,
        fontSize: 8,
        letterSpacing: '0.08em',
        color: active ? DEVELOPER.orange : DEVELOPER.t2,
        cursor: 'pointer',
        textTransform: 'uppercase',
      }}
    >
      {label}
    </button>
  )
}

function DecisionDot({ decision }) {
  const color = DECISION_COLORS[decision] || DEVELOPER.t3
  return (
    <span style={{
      display: 'inline-block',
      width: 6, height: 6, borderRadius: '50%',
      background: color,
      boxShadow: `0 0 6px ${color}`,
      marginRight: 6,
    }} />
  )
}

function fmtRelativeTime(ts) {
  if (!ts) return '–'
  const s = Math.max(0, Math.floor(Date.now() / 1000 - ts))
  if (s < 60)    return `${s}s ago`
  if (s < 3600)  return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}

function truncateResource(resource, maxChars = 64) {
  if (!resource) return ''
  return resource.length > maxChars
    ? resource.slice(0, maxChars - 1) + '…'
    : resource
}

function ShadowSummaryBar({ summary, agentId }) {
  // summary is the per-agent aggregate from /operator-agent-shadow-log endpoint.
  // Shape: { total, by_decision: { permit: N, ... } }. Defensive on shape.
  if (!summary || typeof summary !== 'object') {
    return (
      <div style={{ fontFamily: FONTS.mono, fontSize: 8, color: DEVELOPER.t3 }}>
        no summary
      </div>
    )
  }
  const total = summary.total ?? 0
  const byDecision = summary.by_decision ?? {}
  if (total === 0) {
    return (
      <div style={{ fontFamily: FONTS.mono, fontSize: 8, color: DEVELOPER.t3 }}>
        0 evaluations {agentId ? `for ${agentId.slice(0, 10)}…` : 'fleet-wide'}
      </div>
    )
  }
  return (
    <div>
      <div style={{ fontFamily: FONTS.mono, fontSize: 9, color: DEVELOPER.t1, marginBottom: 4 }}>
        {total} evaluations · last hour
      </div>
      <div style={{ display: 'flex', gap: 2, height: 6, borderRadius: 3, overflow: 'hidden' }}>
        {Object.entries(byDecision).map(([decision, count]) => {
          if (!count) return null
          const pct = (count / total) * 100
          return (
            <div
              key={decision}
              title={`${decision}: ${count} (${pct.toFixed(0)}%)`}
              style={{
                width: `${pct}%`,
                background: DECISION_COLORS[decision] || DEVELOPER.t3,
              }}
            />
          )
        })}
      </div>
    </div>
  )
}

export function ShadowLogPanel({ enabled = true }) {
  const [agentFilter,    setAgentFilter]    = useState('')
  const [decisionFilter, setDecisionFilter] = useState('')

  const { data, isLoading, error } = useShadowLog({
    agentId:  agentFilter,
    decision: decisionFilter,
    limit:    50,
    enabled,
  })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, height: '100%' }}>
      {/* Header — title + summary bar */}
      <div>
        <div style={{
          fontFamily: FONTS.display, fontSize: 11, fontWeight: 600,
          letterSpacing: '0.18em', color: DEVELOPER.t1, marginBottom: 4,
          textTransform: 'uppercase',
        }}>
          Cedar Shadow Evaluations
        </div>
        <ShadowSummaryBar summary={data?.summary} agentId={agentFilter} />
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
        {AGENT_FILTER_OPTIONS.map((opt) => (
          <FilterChip
            key={opt.value || 'all'}
            active={agentFilter === opt.value}
            label={opt.label}
            onClick={() => setAgentFilter(opt.value)}
          />
        ))}
        <span style={{ width: 8 }} />
        {DECISION_FILTER_OPTIONS.slice(0, 4).map((opt) => (
          <FilterChip
            key={opt.value || 'all-d'}
            active={decisionFilter === opt.value}
            label={opt.label}
            onClick={() => setDecisionFilter(opt.value)}
          />
        ))}
      </div>

      {/* Body — scrollable evaluation list */}
      <div style={{
        flex: 1, overflow: 'auto', minHeight: 0,
        border: `1px solid ${DEVELOPER.bd}`,
        borderRadius: 4,
        background: DEVELOPER.bg1,
      }}>
        {error && (
          <div style={{ padding: 12, fontFamily: FONTS.mono, fontSize: 9, color: DEVELOPER.red }}>
            BRIDGE OFFLINE — last data shown if any
          </div>
        )}
        {isLoading && !data && (
          <div style={{ padding: 12, fontFamily: FONTS.mono, fontSize: 9, color: DEVELOPER.t3 }}>
            loading…
          </div>
        )}
        {data && data.row_count === 0 && (
          <div style={{ padding: 12, fontFamily: FONTS.mono, fontSize: 9, color: DEVELOPER.t3, textAlign: 'center' }}>
            No evaluations in shadow log.<br />
            <span style={{ color: DEVELOPER.t2 }}>
              Operator agents not active or no actions evaluated yet.
            </span>
          </div>
        )}
        {data && data.row_count > 0 && (
          <table style={{ width: '100%', fontFamily: FONTS.mono, fontSize: 9, borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: DEVELOPER.bg2, position: 'sticky', top: 0 }}>
                <th style={{ textAlign: 'left',  padding: '6px 8px', color: DEVELOPER.t3, fontWeight: 400, letterSpacing: '0.1em' }}>WHEN</th>
                <th style={{ textAlign: 'left',  padding: '6px 8px', color: DEVELOPER.t3, fontWeight: 400, letterSpacing: '0.1em' }}>AGENT</th>
                <th style={{ textAlign: 'left',  padding: '6px 8px', color: DEVELOPER.t3, fontWeight: 400, letterSpacing: '0.1em' }}>ACTION</th>
                <th style={{ textAlign: 'left',  padding: '6px 8px', color: DEVELOPER.t3, fontWeight: 400, letterSpacing: '0.1em' }}>RESOURCE</th>
                <th style={{ textAlign: 'left',  padding: '6px 8px', color: DEVELOPER.t3, fontWeight: 400, letterSpacing: '0.1em' }}>DECISION</th>
              </tr>
            </thead>
            <tbody>
              {data.evaluations.map((ev, i) => {
                const aid = (ev.agent_id || '').toLowerCase()
                const agentLabel =
                  aid === SENTRY_ID   ? 'SENTRY'   :
                  aid === GUARDIAN_ID ? 'GUARDIAN' :
                  (aid.slice(0, 10) + '…')
                return (
                  <tr key={`${ev.evaluated_at}_${i}`} style={{ borderTop: `1px solid ${DEVELOPER.bd2}` }}>
                    <td style={{ padding: '5px 8px', color: DEVELOPER.t2, whiteSpace: 'nowrap' }} title={String(ev.evaluated_at)}>
                      {fmtRelativeTime(ev.evaluated_at)}
                    </td>
                    <td style={{ padding: '5px 8px', color: DEVELOPER.t1, whiteSpace: 'nowrap' }}>
                      {agentLabel}
                    </td>
                    <td style={{ padding: '5px 8px', color: DEVELOPER.t2 }}>
                      {ev.action || '–'}
                    </td>
                    <td style={{ padding: '5px 8px', color: DEVELOPER.t2 }} title={ev.resource}>
                      {truncateResource(ev.resource)}
                    </td>
                    <td style={{ padding: '5px 8px', whiteSpace: 'nowrap' }}>
                      <DecisionDot decision={ev.decision} />
                      <span style={{ color: DECISION_COLORS[ev.decision] || DEVELOPER.t3 }}>
                        {(ev.decision || '–').replace(/^(permit|forbid)_?/, '').toUpperCase() || (ev.decision || '–').toUpperCase()}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
