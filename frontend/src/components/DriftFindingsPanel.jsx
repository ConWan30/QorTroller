// Phase O1 C5 — DriftFindingsPanel
//
// Surfaces the operator_agent_drift_log table — findings from the C4 sweeper.
// Drift types (FROZEN per INV-OPERATOR-AGENT-007):
//   BUNDLE_HASH_DRIFT          — anchored bundle file mutated post-anchor
//   SCOPE_HASH_GOVERNANCE_DRIFT — AgentScope.scopeRoot != AgentRegistry.scopeHash
//
// Both are CRITICAL severity. BUNDLE_HASH_DRIFT may indicate developer
// edited a bundle without re-anchoring. SCOPE_HASH_GOVERNANCE_DRIFT may
// indicate on-chain state divergence (typically: someone called
// updateAgentScope on one contract but not the other, or a partial deploy
// failed mid-sequence). Either way: investigate before approving any
// action that depends on bundle policy state.
//
// Security: hex hash strings rendered as plain text (React auto-escaped),
// monospace font, truncated display with full value in title attribute.

import { useState } from 'react'
import { useDriftLog } from '../api/bridgeApi'
import { FONTS, DEVELOPER } from '../shared/design/tokens'

const SINCE_OPTIONS = [
  { value: 60,    label: '1H' },
  { value: 1440,  label: '24H' },
  { value: 10080, label: '7D' },
  { value: 43200, label: '30D' },
]

const TYPE_OPTIONS = [
  { value: '',                            label: 'ALL' },
  { value: 'BUNDLE_HASH_DRIFT',           label: 'BUNDLE' },
  { value: 'SCOPE_HASH_GOVERNANCE_DRIFT', label: 'SCOPE' },
]

const TYPE_COLORS = {
  BUNDLE_HASH_DRIFT:           DEVELOPER.amber,
  SCOPE_HASH_GOVERNANCE_DRIFT: DEVELOPER.red,
}

const SENTRY_ID   = '0xb21e1ec258d2d381c313f84944bd36fbc63badb2c9a24c2412212d3a27e3e42c'
const GUARDIAN_ID = '0xbd8c7fba08815b7ed343973c9c7300c062303b1acd19e8d9847a953ce5fa38d1'

function FilterChip({ active, label, onClick, accent = DEVELOPER.orange }) {
  return (
    <button
      onClick={onClick}
      style={{
        background: active ? `${accent}26` : 'transparent',
        border: `1px solid ${active ? accent : DEVELOPER.bd}`,
        borderRadius: 4,
        padding: '3px 8px',
        fontFamily: FONTS.mono,
        fontSize: 8,
        letterSpacing: '0.08em',
        color: active ? accent : DEVELOPER.t2,
        cursor: 'pointer',
        textTransform: 'uppercase',
      }}
    >
      {label}
    </button>
  )
}

function fmtRelativeTime(ts) {
  if (!ts) return '–'
  const s = Math.max(0, Math.floor(Date.now() / 1000 - Number(ts)))
  if (s < 60)    return `${s}s ago`
  if (s < 3600)  return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}

function truncateHash(hex, head = 16, tail = 8) {
  if (!hex) return '–'
  const s = String(hex).replace(/^0x/, '')
  if (s.length <= head + tail + 1) return s
  return `${s.slice(0, head)}…${s.slice(-tail)}`
}

function agentLabel(aid) {
  const a = (aid || '').toLowerCase()
  if (a === SENTRY_ID)   return 'SENTRY'
  if (a === GUARDIAN_ID) return 'GUARDIAN'
  return a.slice(0, 10) + '…'
}

function DriftRow({ finding }) {
  const color = TYPE_COLORS[finding.drift_type] || DEVELOPER.amber
  const typeShort = finding.drift_type === 'BUNDLE_HASH_DRIFT' ? 'BUNDLE' : 'SCOPE'

  return (
    <div style={{
      padding: '8px 10px',
      borderBottom: `1px solid ${DEVELOPER.bd2}`,
      borderLeft: `3px solid ${color}`,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
        <div>
          <span style={{
            fontFamily: FONTS.mono, fontSize: 8, fontWeight: 700,
            color, letterSpacing: '0.1em', marginRight: 8,
          }}>
            {typeShort}
          </span>
          <span style={{ fontFamily: FONTS.mono, fontSize: 9, color: DEVELOPER.t1 }}>
            {agentLabel(finding.agent_id)}
          </span>
        </div>
        <span style={{ fontFamily: FONTS.mono, fontSize: 8, color: DEVELOPER.t2 }} title={String(finding.detected_at)}>
          {fmtRelativeTime(finding.detected_at)}
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '60px 1fr', gap: 4, fontFamily: FONTS.mono, fontSize: 8 }}>
        <span style={{ color: DEVELOPER.t3 }}>EXPECT</span>
        <span style={{ color: DEVELOPER.green }} title={finding.expected_value || ''}>
          {truncateHash(finding.expected_value)}
        </span>
        <span style={{ color: DEVELOPER.t3 }}>ACTUAL</span>
        <span style={{ color: DEVELOPER.red }} title={finding.actual_value || ''}>
          {truncateHash(finding.actual_value)}
        </span>
      </div>

      {finding.evidence_json && (
        <details style={{ marginTop: 4 }}>
          <summary style={{ fontFamily: FONTS.mono, fontSize: 8, color: DEVELOPER.t2, cursor: 'pointer' }}>
            evidence
          </summary>
          <pre style={{
            fontFamily: FONTS.mono, fontSize: 8, color: DEVELOPER.t2,
            margin: '4px 0 0 0', padding: 6,
            background: DEVELOPER.bg2,
            borderRadius: 3,
            overflow: 'auto',
            maxHeight: 80,
          }}>
            {finding.evidence_json}
          </pre>
        </details>
      )}
    </div>
  )
}

export function DriftFindingsPanel({ enabled = true }) {
  const [sinceMinutes, setSinceMinutes] = useState(1440)
  const [typeFilter,   setTypeFilter]   = useState('')

  const { data, isLoading, error } = useDriftLog({
    sinceMinutes,
    driftType: typeFilter,
    limit:     50,
    enabled,
  })

  const findings = data?.findings || []
  const cleanState = !isLoading && !error && findings.length === 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, height: '100%' }}>
      {/* Header */}
      <div>
        <div style={{
          fontFamily: FONTS.display, fontSize: 11, fontWeight: 600,
          letterSpacing: '0.18em', color: DEVELOPER.t1, marginBottom: 4,
          textTransform: 'uppercase',
        }}>
          Drift Findings
        </div>
        <div style={{ fontFamily: FONTS.mono, fontSize: 9, color: cleanState ? DEVELOPER.green : DEVELOPER.amber }}>
          {cleanState
            ? '✓ CLEAN — no drift detected'
            : `${findings.length} finding${findings.length === 1 ? '' : 's'}`}
        </div>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
        {SINCE_OPTIONS.map((opt) => (
          <FilterChip
            key={`since_${opt.value}`}
            active={sinceMinutes === opt.value}
            label={opt.label}
            onClick={() => setSinceMinutes(opt.value)}
          />
        ))}
        <span style={{ width: 8 }} />
        {TYPE_OPTIONS.map((opt) => (
          <FilterChip
            key={`type_${opt.value || 'all'}`}
            active={typeFilter === opt.value}
            label={opt.label}
            accent={DEVELOPER.amber}
            onClick={() => setTypeFilter(opt.value)}
          />
        ))}
      </div>

      {/* Body */}
      <div style={{
        flex: 1, overflow: 'auto', minHeight: 0,
        border: `1px solid ${DEVELOPER.bd}`,
        borderRadius: 4,
        background: DEVELOPER.bg1,
      }}>
        {error && (
          <div style={{ padding: 12, fontFamily: FONTS.mono, fontSize: 9, color: DEVELOPER.red }}>
            BRIDGE OFFLINE — drift findings unavailable
          </div>
        )}
        {isLoading && !data && (
          <div style={{ padding: 12, fontFamily: FONTS.mono, fontSize: 9, color: DEVELOPER.t3 }}>
            loading…
          </div>
        )}
        {cleanState && (
          <div style={{ padding: 16, fontFamily: FONTS.mono, fontSize: 9, color: DEVELOPER.t3, textAlign: 'center' }}>
            No drift findings in the selected window.<br />
            <span style={{ color: DEVELOPER.green }}>
              Bundles + scopes match anchored truth.
            </span>
          </div>
        )}
        {findings.map((f) => (
          <DriftRow key={f.id || `${f.agent_id}_${f.detected_at}`} finding={f} />
        ))}
      </div>
    </div>
  )
}
