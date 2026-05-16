/**
 * Evidence OS — ActionGuardBadge
 *
 * Tiny inline indicator explaining WHY a write action is disabled.
 * Always renders alongside (or instead of) an action button so the
 * operator never sees a greyed control without explanation.
 *
 * Discipline:
 *   - Reason is REQUIRED — silent disabled controls are forbidden
 *   - role='note' (not interactive) so screen readers announce it as
 *     context, not as a button
 *   - Color + label + icon-character ⊘ — never color-only
 *
 * Common reasons (operator brief):
 *   - mock-active           → mock/offline state disables writes
 *   - invariant-failing     → invariant gate fail blocks sensitive ops
 *   - killswitch-paused     → CHAIN_SUBMISSION_PAUSED held
 *   - read-only             → row is a status report, not a draft
 *   - bridge-offline        → hook returned error
 */
import PropTypes from 'prop-types'

const _LABELS = {
  'mock-active':        'mock — writes disabled',
  'invariant-failing':  'invariants failing — sensitive actions disabled',
  'killswitch-paused':  'kill-switch paused — chain writes disabled',
  'read-only':          'read-only',
  'bridge-offline':     'bridge offline',
  'no-mutation':        'no mutation wired',
}

export default function ActionGuardBadge({ reason, label, title }) {
  const text = label ?? _LABELS[reason] ?? reason ?? 'disabled'
  return (
    <span
      role="note"
      data-os-guard={reason || 'disabled'}
      aria-label={`Action disabled — ${text}`}
      title={title || text}
      style={{
        display:        'inline-flex',
        alignItems:     'center',
        gap:            4,
        padding:        '2px 6px',
        fontSize:       'var(--os-text-min)',
        fontWeight:     500,
        color:          'var(--os-text-faint)',
        border:         '1px dashed var(--os-border)',
        borderRadius:   'var(--os-radius)',
        whiteSpace:     'nowrap',
        fontFamily:     'JetBrains Mono, ui-monospace, monospace',
      }}
    >
      <span aria-hidden="true" style={{
        color: 'var(--os-status-killswitch)',
        fontWeight: 700,
      }}>⊘</span>
      {text}
    </span>
  )
}

ActionGuardBadge.propTypes = {
  reason: PropTypes.string,        // semantic key — see _LABELS
  label:  PropTypes.string,        // override label text
  title:  PropTypes.string,
}
