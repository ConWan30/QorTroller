/**
 * Evidence OS — DataBadge
 *
 * Semantic status pill. Text + color, never color-only (a11y).
 * Status values map to Mythos-derived honest states:
 *   live      — real bridge data, fresh
 *   verified  — cryptographically confirmed (re-hashed in browser)
 *   pending   — in-flight; awaiting next anchor / next poll
 *   blocked   — failed validation or upstream gate
 *   mock      — fabricated data visibly flagged
 *   killswitch — paused-anchor honest state (CHAIN_SUBMISSION_PAUSED)
 *   dormant   — has not yet been emitted (no row exists)
 *   deferred  — operator-authorized cast-out from active gate set;
 *               distinct from pending (no work in progress) AND from
 *               blocked (not blocking anything). Mirrors the
 *               protocol-level "tremor_resting P1vP3 cast-out
 *               2026-05-09" precedent. Used for historical baselines
 *               kept visible for transparency but explicitly not
 *               part of the live-gate evaluation.
 *
 * Renders as inline span (not interactive). For interactive states
 * wrap in <button>.
 */
import PropTypes from 'prop-types'

const _LABELS = {
  live:       'LIVE',
  verified:   'VERIFIED',
  pending:    'PENDING',
  blocked:    'BLOCKED',
  mock:       'MOCK',
  killswitch: 'PAUSED',
  dormant:    'DORMANT',
  deferred:   'DEFERRED',
}

const _COLOR_VAR = {
  live:       '--os-status-live',
  verified:   '--os-status-verified',
  pending:    '--os-status-pending',
  blocked:    '--os-status-blocked',
  mock:       '--os-status-mock',
  killswitch: '--os-status-killswitch',
  dormant:    '--os-status-dormant',
  // deferred reuses the dormant colour token deliberately — visually
  // calm grey, NOT amber pending nor red blocked. Operator-authorized
  // cast-out should read as "not part of the active gate set" not as
  // "something to fix".
  deferred:   '--os-status-dormant',
}

export default function DataBadge({ status = 'dormant', label, ariaLabel, title }) {
  const text = label ?? _LABELS[status] ?? 'UNKNOWN'
  const colorVar = _COLOR_VAR[status] || '--os-status-dormant'
  return (
    <span
      data-os-badge={status}
      role="status"
      aria-label={ariaLabel || `${text} status`}
      title={title || text}
      style={{
        display:        'inline-flex',
        alignItems:     'center',
        gap:            6,
        padding:        '2px 8px',
        fontSize:       'var(--os-text-min)',
        fontWeight:     600,
        letterSpacing:  '0.06em',
        textTransform:  'uppercase',
        color:          `var(${colorVar})`,
        border:         `1px solid var(${colorVar})`,
        background:     `color-mix(in srgb, var(${colorVar}) 12%, transparent)`,
        borderRadius:   'var(--os-radius)',
        whiteSpace:     'nowrap',
        fontFamily:     'JetBrains Mono, ui-monospace, monospace',
      }}
    >
      <span aria-hidden="true" style={{
        width: 6, height: 6, borderRadius: '50%',
        background: `var(${colorVar})`, flexShrink: 0,
      }} />
      {text}
    </span>
  )
}

DataBadge.propTypes = {
  status: PropTypes.oneOf([
    'live', 'verified', 'pending', 'blocked',
    'mock', 'killswitch', 'dormant', 'deferred',
  ]),
  label:     PropTypes.string,
  ariaLabel: PropTypes.string,
  title:     PropTypes.string,
}
