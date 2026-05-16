/**
 * Evidence OS — QueueDetailPanel
 *
 * Accessible inline detail panel for the queue. Implemented as a
 * semantic <dialog>-like region with role='region' + aria-labelledby
 * (NOT a custom clickable div per operator brief). For reviewable
 * drafts it embeds the review form: reason ≥10 chars + accept /
 * reject / overturn-curator buttons (overturn surfaced only for
 * Curator drafts). All destructive ops require an explicit confirm
 * step (two-click pattern via internal state).
 *
 * Discipline:
 *   - Closes via explicit close button (Esc handler delegated to parent)
 *   - Mutation guard: when mockActive=true OR invariantFailing=true,
 *     accept/reject/overturn are visibly disabled with an
 *     ActionGuardBadge explaining why
 *   - reason textarea has aria-describedby pointing at the char-count
 *     hint so screen readers announce "10 chars required"
 *   - "raw payload" rendered as <pre> with role='code' for forensic copy
 */
import { useState, useEffect } from 'react'
import PropTypes from 'prop-types'
import DataBadge from './DataBadge'
import ActionGuardBadge from './ActionGuardBadge'

// Mythos audit M4 — armed destructive decisions auto-cancel after
// 8s of inactivity so an operator who walks away mid-decision
// doesn't return to a primed "Confirm reject" they don't remember.
const _ARM_TIMEOUT_MS = 8000

const _MONO = 'JetBrains Mono, ui-monospace, monospace'
const _REASON_MIN = 10

const _BUTTON_BASE = {
  fontFamily:     _MONO,
  fontSize:       'var(--os-text-min)',
  fontWeight:     600,
  letterSpacing:  '0.06em',
  textTransform:  'uppercase',
  padding:        '8px 14px',
  borderRadius:   'var(--os-radius)',
  cursor:         'pointer',
  background:     'transparent',
}

function _accept(disabled) {
  return {
    ..._BUTTON_BASE,
    color:  disabled ? 'var(--os-text-faint)' : 'var(--os-status-live)',
    border: `1px solid ${disabled ? 'var(--os-border)' : 'var(--os-status-live)'}`,
    cursor: disabled ? 'not-allowed' : 'pointer',
  }
}

function _reject(disabled) {
  return {
    ..._BUTTON_BASE,
    color:  disabled ? 'var(--os-text-faint)' : 'var(--os-status-blocked)',
    border: `1px solid ${disabled ? 'var(--os-border)' : 'var(--os-status-blocked)'}`,
    cursor: disabled ? 'not-allowed' : 'pointer',
  }
}

function _overturn(disabled) {
  return {
    ..._BUTTON_BASE,
    color:  disabled ? 'var(--os-text-faint)' : 'var(--os-accent)',
    border: `1px solid ${disabled ? 'var(--os-border)' : 'var(--os-accent)'}`,
    cursor: disabled ? 'not-allowed' : 'pointer',
  }
}

export default function QueueDetailPanel({
  item,
  onClose,
  onReviewDraft,
  mockActive = false,
  invariantFailing = false,
  reviewInFlight = false,
  reviewError,
  reviewSucceededFor,
}) {
  const [reason, setReason]   = useState('')
  const [pending, setPending] = useState(null)   // 'accept'|'reject'|'overturn'|null
  const titleId = `queue-detail-title-${item.id}`

  // Mythos audit M4 — auto-clear pending arm after 8s. Decisions
  // are destructive (operator_decision is non-revisable in v1 wire);
  // a primed button with no recent click cannot be trusted.
  useEffect(() => {
    if (!pending) return undefined
    const id = setTimeout(() => setPending(null), _ARM_TIMEOUT_MS)
    return () => clearTimeout(id)
  }, [pending])

  const isDraft = item.kind === 'draft'
  const isCuratorDraft = isDraft && (
    String(item.raw?.agent_id || '').toLowerCase().includes('curator')
    || String(item.raw?.action_name || '').startsWith('marketplace-')
  )

  // Guard reason — first applicable wins
  let writeGuard = null
  if (mockActive)               writeGuard = 'mock-active'
  else if (invariantFailing)    writeGuard = 'invariant-failing'
  else if (!isDraft)             writeGuard = 'read-only'
  else if (!onReviewDraft)       writeGuard = 'no-mutation'

  const writeDisabled = Boolean(writeGuard)
  const reasonShort   = reason.trim().length < _REASON_MIN
  const submitDisabled = writeDisabled || reasonShort || reviewInFlight

  const submit = (decision) => {
    if (submitDisabled) return
    if (pending !== decision) {
      // First click: arm; second click confirms (two-click discipline
      // for destructive / governance-sensitive operations)
      setPending(decision)
      return
    }
    if (!onReviewDraft) return
    onReviewDraft({ draftId: item.raw.id, decision, reason: reason.trim() })
    setPending(null)
  }

  return (
    <section
      // Mythos audit H4 — id matches QueueItem's aria-controls so
      // the disclosure pattern is programmatically wired end-to-end.
      id={`queue-detail-${item.id}`}
      role="region"
      aria-labelledby={titleId}
      data-os-queue-detail={item.kind}
      style={{
        display:        'flex',
        flexDirection:  'column',
        gap:            12,
        padding:        '16px 18px',
        background:     'var(--os-panel-soft)',
        border:         '1px solid var(--os-accent-soft)',
        borderLeft:     '3px solid var(--os-accent)',
        borderRadius:   'var(--os-radius)',
        fontFamily:     _MONO,
      }}
    >
      {/* Header */}
      <div style={{
        display:        'flex',
        alignItems:     'flex-start',
        justifyContent: 'space-between',
        gap:            16,
      }}>
        <div style={{ minWidth: 0, flex: 1 }}>
          <h3 id={titleId} style={{
            margin:     0,
            fontSize:   'var(--os-text-h3)',
            fontWeight: 700,
            color:      'var(--os-text)',
            letterSpacing: '0.04em',
          }}>{item.title}</h3>
          <div style={{
            marginTop: 6,
            display: 'flex', gap: 14, flexWrap: 'wrap',
            fontSize: 'var(--os-text-min)',
            color: 'var(--os-text-faint)',
          }}>
            <span>kind: <code style={{ color: 'var(--os-text-dim)' }}>{item.kind}</code></span>
            <span>protocol: <code style={{ color: 'var(--os-text-dim)' }}>{item.protocolTerm}</code></span>
            <span>source: <code style={{ color: 'var(--os-text-dim)' }}>{item.source}</code></span>
            <span>age: <code style={{ color: 'var(--os-text-dim)' }}>{item.ageLabel || '—'}</code></span>
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close detail panel"
          style={{
            ..._BUTTON_BASE,
            color: 'var(--os-text-dim)',
            border: '1px solid var(--os-border)',
            padding: '6px 10px',
          }}
        >Close</button>
      </div>

      {/* Recommendation block */}
      <div style={{
        padding: '10px 12px',
        background: 'var(--os-panel)',
        border: '1px solid var(--os-border)',
        borderRadius: 'var(--os-radius)',
        fontSize: 'var(--os-text-base)',
        color: 'var(--os-text)',
      }}>
        <div style={{
          fontSize: 'var(--os-text-min)',
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          color: 'var(--os-text-faint)',
          marginBottom: 4,
        }}>Recommended action</div>
        {item.recommendation}
      </div>

      {/* Raw payload — forensic copy */}
      {item.raw && (
        <details>
          <summary style={{
            cursor: 'pointer',
            fontSize: 'var(--os-text-min)',
            color: 'var(--os-text-dim)',
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
          }}>Raw row</summary>
          <pre
            // Mythos audit L3 — role="code" isn't a valid ARIA role;
            // native <pre> is sufficient for screen readers.
            aria-label="Raw protocol row"
            style={{
              marginTop: 8,
              padding: '10px 12px',
              background: 'var(--os-bg)',
              border: '1px solid var(--os-border)',
              borderRadius: 'var(--os-radius)',
              fontSize: 'var(--os-text-min)',
              color: 'var(--os-text-dim)',
              overflowX: 'auto',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-all',
            }}
          >{JSON.stringify(item.raw, null, 2)}</pre>
        </details>
      )}

      {/* Draft review form — only for reviewable drafts */}
      {isDraft && (
        <div style={{
          display: 'flex', flexDirection: 'column', gap: 8,
          paddingTop: 4, borderTop: '1px solid var(--os-border-soft)',
        }}>
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          }}>
            <span style={{
              fontSize: 'var(--os-text-min)',
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color: 'var(--os-text-faint)',
            }}>Operator decision</span>
            {writeGuard && <ActionGuardBadge reason={writeGuard}/>}
          </div>

          <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span style={{
              fontSize: 'var(--os-text-min)',
              color: 'var(--os-text-dim)',
            }}>
              Reason (≥{_REASON_MIN} chars, becomes audit field)
            </span>
            <textarea
              value={reason}
              onChange={(e) => { setReason(e.target.value); setPending(null) }}
              aria-describedby={`${titleId}-reason-hint`}
              disabled={writeDisabled}
              rows={3}
              placeholder="e.g. verdict matches on-chain anchor freshness check"
              style={{
                fontFamily: _MONO,
                fontSize: 'var(--os-text-base)',
                color: 'var(--os-text)',
                background: 'var(--os-bg)',
                border: '1px solid var(--os-border)',
                borderRadius: 'var(--os-radius)',
                padding: '8px 10px',
                resize: 'vertical',
              }}
            />
            <span id={`${titleId}-reason-hint`} style={{
              fontSize: 'var(--os-text-min)',
              color: reasonShort ? 'var(--os-status-pending)' : 'var(--os-text-faint)',
            }}>
              {reason.trim().length}/{_REASON_MIN} chars
              {reasonShort && ' — operator review requires a written justification'}
            </span>
          </label>

          {reviewSucceededFor === item.raw?.id && (
            <DataBadge status="verified" label="DECISION RECORDED"/>
          )}
          {reviewError && (
            <DataBadge status="blocked" label={`ERROR — ${String(reviewError).slice(0, 80)}`}/>
          )}

          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button
              type="button"
              onClick={() => submit('accept')}
              disabled={submitDisabled}
              style={_accept(submitDisabled)}
              aria-label="Accept draft"
            >
              {pending === 'accept' ? 'Confirm accept' : 'Accept'}
            </button>
            <button
              type="button"
              onClick={() => submit('reject')}
              disabled={submitDisabled}
              style={_reject(submitDisabled)}
              aria-label="Reject draft"
            >
              {pending === 'reject' ? 'Confirm reject' : 'Reject'}
            </button>
            {isCuratorDraft && (
              <button
                type="button"
                onClick={() => submit('overturn_curator')}
                disabled={submitDisabled}
                style={_overturn(submitDisabled)}
                aria-label="Overturn Curator draft"
                title="Overturn ⇒ false_positive_rate += 1. Use only when Curator misread."
              >
                {pending === 'overturn_curator' ? 'Confirm overturn' : 'Overturn curator'}
              </button>
            )}
            {pending && (
              <span style={{
                fontSize: 'var(--os-text-min)',
                color: 'var(--os-status-pending)',
                alignSelf: 'center',
              }}>Click again to confirm — or change reason to cancel</span>
            )}
          </div>
        </div>
      )}

      {!isDraft && (
        <ActionGuardBadge reason="read-only" label="this row is a status report — no operator action wired in v1"/>
      )}
    </section>
  )
}

QueueDetailPanel.propTypes = {
  item: PropTypes.shape({
    id:             PropTypes.string.isRequired,
    kind:           PropTypes.string.isRequired,
    title:          PropTypes.string.isRequired,
    protocolTerm:   PropTypes.string,
    source:         PropTypes.string,
    ageLabel:       PropTypes.string,
    recommendation: PropTypes.string,
    raw:            PropTypes.object,
  }).isRequired,
  onClose:           PropTypes.func.isRequired,
  onReviewDraft:     PropTypes.func,
  mockActive:        PropTypes.bool,
  invariantFailing:  PropTypes.bool,
  reviewInFlight:    PropTypes.bool,
  reviewError:       PropTypes.string,
  reviewSucceededFor: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
}
