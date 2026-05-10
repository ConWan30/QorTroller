// Phase O2-DRAFT-REVIEW-FRONTEND — DraftReviewPanel
//
// Operator review surface for the drafts produced by Sentry/Guardian/Curator
// at O2 SUGGEST. Closes the disagreement_rate + false_positive_rate gates on
// the UI side. Without operator decisions on accumulated drafts those gates
// stay structurally unmeasurable -> O3 ACTING anchor blocked indefinitely.
//
// Layout:
//   [agent chips] [decision chips] [since chips]
//   ── list of drafts (most recent first) ──
//     row: agent · action · uri/hash · age · decision badge   ▶ expand
//       expanded: payload preview · reason textarea · accept/reject/overturn
//
// Decisions:
//   accept           — operator confirms agent's draft
//   reject           — disagreement_rate numerator
//   overturn_curator — Curator-only; false_positive_rate numerator (ZERO TOLERANCE)
//
// Reason MUST be >=10 chars (server-enforced; we surface 422 inline).
//
// All hooks set noMock:true — operators must never review fabricated drafts.

import { useState } from 'react'
import { FONTS, DEVELOPER } from '../shared/design/tokens'
import { useOperatorDrafts, useReviewDraft } from '../api/bridgeApi'

// FROZEN agent canonical names (mirrors bridge _AGENT_NAME_TO_ID_ATTR).
const AGENT_FILTERS = [
  { key: '',                label: 'All',      hint: 'All three agents' },
  { key: 'anchor_sentry',   label: 'Sentry',   hint: 'AnchorSentry (Q9-frozen agentId)' },
  { key: 'guardian',        label: 'Guardian', hint: 'Guardian agent' },
  { key: 'curator',         label: 'Curator',  hint: 'Curator agent' },
]

const DECISION_FILTERS = [
  { key: 'unreviewed',         label: 'Unreviewed', hint: 'operator_decision IS NULL' },
  { key: '',                   label: 'All',        hint: 'Including reviewed' },
  { key: 'accept',             label: 'Accept',     hint: 'Previously accepted' },
  { key: 'reject',             label: 'Reject',     hint: 'Previously rejected' },
  { key: 'overturn_curator',   label: 'Overturn',   hint: 'Curator overturn (false_positive_rate)' },
]

const SINCE_FILTERS = [
  { key: 60,    label: '1h' },
  { key: 1440,  label: '24h' },
  { key: 10080, label: '7d' },
  { key: 43200, label: '30d' },
]

function fmtAge(tsSec) {
  if (!tsSec) return ''
  const sec = Math.max(0, Math.floor(Date.now() / 1000 - tsSec))
  if (sec < 60) return `${sec}s`
  if (sec < 3600) return `${Math.floor(sec / 60)}m`
  if (sec < 86400) return `${Math.floor(sec / 3600)}h`
  return `${Math.floor(sec / 86400)}d`
}

function truncMid(s, head = 8, tail = 6) {
  if (!s || typeof s !== 'string') return ''
  if (s.length <= head + tail + 3) return s
  return `${s.slice(0, head)}…${s.slice(-tail)}`
}

function decisionBadge(decision) {
  if (decision === 'accept') return { txt: 'ACCEPT', c: DEVELOPER.green }
  if (decision === 'reject') return { txt: 'REJECT', c: DEVELOPER.red }
  if (decision === 'overturn_curator') return { txt: 'OVERTURN', c: DEVELOPER.amber }
  return { txt: 'PENDING', c: DEVELOPER.t2 }
}

function FilterChip({ active, label, hint, onClick }) {
  return (
    <button
      onClick={onClick}
      title={hint || ''}
      style={{
        background: active ? `${DEVELOPER.orange}33` : 'transparent',
        border: `1px solid ${active ? DEVELOPER.orange : DEVELOPER.bd}`,
        borderRadius: 3,
        padding: '3px 9px',
        color: active ? DEVELOPER.orange : DEVELOPER.t2,
        fontFamily: FONTS.mono,
        fontSize: 9,
        fontWeight: active ? 700 : 500,
        cursor: 'pointer',
        letterSpacing: '0.1em',
        textTransform: 'uppercase',
      }}
    >
      {label}
    </button>
  )
}

function DraftRow({ draft, expanded, onToggle, mutate, busyId }) {
  const [reason, setReason] = useState('')
  const [localError, setLocalError] = useState('')
  const isBusy = busyId === draft.id
  const isCurator = (draft.agent_id || '').toLowerCase().includes('curator')
                  || (draft.action_name || '').startsWith('marketplace-')
  const dec = decisionBadge(draft.operator_decision)

  const submit = (decision) => {
    setLocalError('')
    const trimmed = reason.trim()
    if (trimmed.length < 10) {
      setLocalError(`Reason must be at least 10 characters (currently ${trimmed.length}).`)
      return
    }
    mutate({ draftId: draft.id, decision, reason: trimmed }, {
      onError: (err) => {
        setLocalError(err?.message || 'Bridge offline; try again')
      },
      onSuccess: () => {
        setReason('')
        // Row will refresh via invalidation; collapse handled by parent if needed.
      },
    })
  }

  return (
    <div
      style={{
        borderBottom: `1px solid ${DEVELOPER.bd}`,
        padding: '8px 12px',
        background: expanded ? `${DEVELOPER.orange}08` : 'transparent',
        cursor: 'default',
      }}
    >
      {/* Header row — click to expand */}
      <div
        onClick={onToggle}
        style={{
          display: 'flex', alignItems: 'center', gap: 12,
          cursor: 'pointer',
        }}
      >
        <span style={{
          fontFamily: FONTS.mono, fontSize: 9, color: DEVELOPER.t2, width: 14,
        }}>{expanded ? '▼' : '▶'}</span>
        <span style={{
          fontFamily: FONTS.mono, fontSize: 9, fontWeight: 700,
          color: DEVELOPER.amber, minWidth: 72,
        }} title={draft.agent_id || ''}>{truncMid(draft.agent_id || '', 6, 4)}</span>
        <span style={{
          fontFamily: FONTS.mono, fontSize: 10, color: DEVELOPER.t1, minWidth: 180,
        }}>{draft.action_name || '?'}</span>
        <span style={{
          fontFamily: FONTS.mono, fontSize: 9, color: DEVELOPER.t2, flex: 1,
        }} title={draft.draft_uri || ''}>{truncMid(draft.draft_uri || '', 24, 12)}</span>
        <span style={{
          fontFamily: FONTS.mono, fontSize: 9, color: DEVELOPER.t3, minWidth: 36,
          textAlign: 'right',
        }}>{fmtAge(draft.created_at)}</span>
        <span style={{
          fontFamily: FONTS.mono, fontSize: 9, fontWeight: 700,
          color: dec.c, background: `${dec.c}22`,
          border: `1px solid ${dec.c}66`,
          borderRadius: 3, padding: '2px 6px',
          minWidth: 64, textAlign: 'center',
        }}>{dec.txt}</span>
      </div>

      {/* Expanded body */}
      {expanded && (
        <div style={{ padding: '10px 0 4px 26px', display: 'flex', flexDirection: 'column', gap: 8 }}>
          {/* Payload metadata */}
          <div style={{
            fontFamily: FONTS.mono, fontSize: 9, color: DEVELOPER.t2,
            display: 'grid', gridTemplateColumns: '120px 1fr', rowGap: 2,
          }}>
            <span style={{ color: DEVELOPER.t3 }}>payload_hash:</span>
            <span title={draft.payload_hash || ''}>{truncMid(draft.payload_hash || '', 16, 8)}</span>
            <span style={{ color: DEVELOPER.t3 }}>category:</span>
            <span>{draft.action_category || '?'}</span>
            <span style={{ color: DEVELOPER.t3 }}>kms_sig:</span>
            <span>{draft.kms_sig_present ? 'present' : 'absent'}</span>
            {draft.operator_decision && (
              <>
                <span style={{ color: DEVELOPER.t3 }}>prior reason:</span>
                <span style={{ color: DEVELOPER.t1 }}>{draft.operator_disagreement_reason || '—'}</span>
              </>
            )}
          </div>

          {/* Reason input */}
          <div>
            <div style={{
              fontFamily: FONTS.mono, fontSize: 8, color: DEVELOPER.t3,
              marginBottom: 4, letterSpacing: '0.1em', textTransform: 'uppercase',
            }}>
              Reason (≥10 chars; permanent audit field)
            </div>
            <textarea
              value={reason}
              onChange={(e) => { setReason(e.target.value); setLocalError('') }}
              placeholder="e.g. verdict matches on-chain anchor freshness check"
              disabled={isBusy}
              rows={2}
              style={{
                width: '100%', boxSizing: 'border-box',
                background: DEVELOPER.bg, color: DEVELOPER.t1,
                border: `1px solid ${DEVELOPER.bd}`, borderRadius: 3,
                padding: '6px 8px',
                fontFamily: FONTS.mono, fontSize: 10,
                resize: 'vertical',
              }}
            />
            {localError && (
              <div style={{
                fontFamily: FONTS.mono, fontSize: 9, color: DEVELOPER.red,
                marginTop: 4,
              }}>⚠ {localError}</div>
            )}
          </div>

          {/* Action buttons */}
          <div style={{ display: 'flex', gap: 6 }}>
            <button
              onClick={() => submit('accept')}
              disabled={isBusy}
              style={{
                background: `${DEVELOPER.green}22`,
                border: `1px solid ${DEVELOPER.green}66`,
                borderRadius: 3,
                padding: '5px 14px',
                color: DEVELOPER.green,
                fontFamily: FONTS.mono, fontSize: 9, fontWeight: 700,
                letterSpacing: '0.1em',
                cursor: isBusy ? 'wait' : 'pointer',
                opacity: isBusy ? 0.5 : 1,
              }}
            >ACCEPT</button>
            <button
              onClick={() => submit('reject')}
              disabled={isBusy}
              style={{
                background: `${DEVELOPER.red}22`,
                border: `1px solid ${DEVELOPER.red}66`,
                borderRadius: 3,
                padding: '5px 14px',
                color: DEVELOPER.red,
                fontFamily: FONTS.mono, fontSize: 9, fontWeight: 700,
                letterSpacing: '0.1em',
                cursor: isBusy ? 'wait' : 'pointer',
                opacity: isBusy ? 0.5 : 1,
              }}
            >REJECT</button>
            {isCurator && (
              <button
                onClick={() => submit('overturn_curator')}
                disabled={isBusy}
                title="ZERO TOLERANCE — overturn feeds false_positive_rate which blocks O3 anchor."
                style={{
                  background: `${DEVELOPER.amber}22`,
                  border: `1px solid ${DEVELOPER.amber}66`,
                  borderRadius: 3,
                  padding: '5px 14px',
                  color: DEVELOPER.amber,
                  fontFamily: FONTS.mono, fontSize: 9, fontWeight: 700,
                  letterSpacing: '0.1em',
                  cursor: isBusy ? 'wait' : 'pointer',
                  opacity: isBusy ? 0.5 : 1,
                }}
              >OVERTURN</button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export function DraftReviewPanel({ enabled = true }) {
  const [agentId, setAgentId] = useState('')
  const [decision, setDecision] = useState('unreviewed')
  const [sinceMinutes, setSinceMinutes] = useState(10080)
  const [expandedId, setExpandedId] = useState(null)

  const { data, isError, isLoading } = useOperatorDrafts({
    agentId, decision, sinceMinutes, limit: 100, enabled,
  })
  const reviewMutation = useReviewDraft()

  const drafts = data?.drafts || []
  const rowCount = data?.row_count ?? 0

  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      background: DEVELOPER.bg1,
      border: `1px solid ${DEVELOPER.bd}`,
      borderRadius: 4,
      minHeight: 0, height: '100%',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '8px 12px',
        borderBottom: `1px solid ${DEVELOPER.bd}`,
      }}>
        <div style={{
          fontFamily: FONTS.display, fontSize: 11, fontWeight: 700,
          color: DEVELOPER.amber, letterSpacing: '0.2em',
          textTransform: 'uppercase',
        }}>
          Draft Review · O2 SUGGEST
        </div>
        <div style={{
          fontFamily: FONTS.mono, fontSize: 9, color: DEVELOPER.t2,
        }}>
          {isLoading ? '… loading' : isError ? '⚠ bridge offline' : `${rowCount} row${rowCount === 1 ? '' : 's'}`}
        </div>
      </div>

      {/* Filter rows */}
      <div style={{ padding: '8px 12px', borderBottom: `1px solid ${DEVELOPER.bd}`, display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          <span style={{ fontFamily: FONTS.mono, fontSize: 8, color: DEVELOPER.t3, alignSelf: 'center', width: 56, letterSpacing: '0.1em' }}>AGENT</span>
          {AGENT_FILTERS.map(f => (
            <FilterChip key={f.key || 'all'} active={agentId === f.key} label={f.label} hint={f.hint} onClick={() => setAgentId(f.key)} />
          ))}
        </div>
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          <span style={{ fontFamily: FONTS.mono, fontSize: 8, color: DEVELOPER.t3, alignSelf: 'center', width: 56, letterSpacing: '0.1em' }}>DECISION</span>
          {DECISION_FILTERS.map(f => (
            <FilterChip key={f.key || 'all'} active={decision === f.key} label={f.label} hint={f.hint} onClick={() => setDecision(f.key)} />
          ))}
        </div>
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          <span style={{ fontFamily: FONTS.mono, fontSize: 8, color: DEVELOPER.t3, alignSelf: 'center', width: 56, letterSpacing: '0.1em' }}>SINCE</span>
          {SINCE_FILTERS.map(f => (
            <FilterChip key={f.key} active={sinceMinutes === f.key} label={f.label} onClick={() => setSinceMinutes(f.key)} />
          ))}
        </div>
      </div>

      {/* Draft list */}
      <div style={{ flex: 1, minHeight: 0, overflowY: 'auto' }}>
        {drafts.length === 0 ? (
          <div style={{
            padding: 24, textAlign: 'center',
            fontFamily: FONTS.mono, fontSize: 10, color: DEVELOPER.t3,
          }}>
            {isLoading ? '… loading' : isError ? '⚠ bridge offline — last known: no drafts' :
              decision === 'unreviewed'
                ? 'No unreviewed drafts in window. Polling cadence: 20s.'
                : 'No drafts match the selected filters.'}
          </div>
        ) : (
          drafts.map(draft => (
            <DraftRow
              key={draft.id}
              draft={draft}
              expanded={expandedId === draft.id}
              onToggle={() => setExpandedId(expandedId === draft.id ? null : draft.id)}
              mutate={reviewMutation.mutate}
              busyId={reviewMutation.isPending ? reviewMutation.variables?.draftId : null}
            />
          ))
        )}
      </div>
    </div>
  )
}
