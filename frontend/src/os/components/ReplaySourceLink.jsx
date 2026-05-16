/**
 * Evidence OS — ReplaySourceLink
 *
 * Small "View underlying endpoint / artifact" affordance shown on
 * forensic replay surfaces. Operator can click to inspect the
 * raw JSON / binary / contract state behind the rendered claim.
 *
 * Renders as a semantic <a> with an explicit external-link icon
 * character (↗) so it's distinguishable from internal nav. Honest
 * about destination — title attribute shows the full URL on hover.
 *
 * Discipline:
 *   - role implicit via <a>; explicit aria-label including the
 *     destination so screen readers announce "View raw protocol
 *     row at /public/session/..."
 *   - rel='noopener noreferrer' on external targets
 */
import PropTypes from 'prop-types'

const _MONO = 'JetBrains Mono, ui-monospace, monospace'

export default function ReplaySourceLink({
  href,
  label = 'View raw row',
  external = false,
  ariaLabel,
}) {
  if (!href) {
    return (
      <span
        role="note"
        aria-label="No source link available"
        style={{
          fontFamily: _MONO,
          fontSize:   'var(--os-text-min)',
          color:      'var(--os-text-faint)',
          fontStyle:  'italic',
        }}
      >no source endpoint published</span>
    )
  }

  return (
    <a
      href={href}
      target={external ? '_blank' : undefined}
      rel={external ? 'noopener noreferrer' : undefined}
      aria-label={ariaLabel || `${label}${external ? ' (opens new tab)' : ''} — ${href}`}
      title={href}
      data-os-source-link
      style={{
        fontFamily:    _MONO,
        fontSize:      'var(--os-text-min)',
        fontWeight:    600,
        letterSpacing: '0.04em',
        padding:       '4px 10px',
        color:         'var(--os-accent)',
        background:    'transparent',
        border:        '1px solid var(--os-accent-soft)',
        borderRadius:  'var(--os-radius)',
        textDecoration: 'none',
        display:       'inline-flex',
        alignItems:    'center',
        gap:           6,
        whiteSpace:    'nowrap',
      }}
    >
      {label}
      <span aria-hidden="true">{external ? '↗' : '→'}</span>
    </a>
  )
}

ReplaySourceLink.propTypes = {
  href:      PropTypes.string,
  label:     PropTypes.string,
  external:  PropTypes.bool,
  ariaLabel: PropTypes.string,
}
