/**
 * Evidence OS — LiveSignalPane
 *
 * Full-bleed signal area for the Live Match workspace. Hosts a grid
 * of SignalMeter cards across the operator-readable signals that
 * decide whether the session counts. Layout responsive — 2-col on
 * narrow viewports, 4-col wide.
 *
 * Discipline:
 *   - Children should be SignalMeter (or any role='group' card)
 *   - Title slot uses semantic <h2> for screen-reader navigability
 *   - Section wrapper has role='region' + aria-label
 */
import PropTypes from 'prop-types'

export default function LiveSignalPane({ title, children }) {
  return (
    <section
      role="region"
      aria-label={title || 'Live signals'}
      style={{
        display:        'flex',
        flexDirection:  'column',
        gap:            12,
        padding:        '16px 0 0',
        fontFamily:     'JetBrains Mono, ui-monospace, monospace',
      }}
    >
      {title && (
        <h2 style={{
          margin:         0,
          fontSize:       'var(--os-text-h3)',
          fontWeight:     700,
          color:          'var(--os-text)',
          letterSpacing:  '0.06em',
          textTransform:  'uppercase',
        }}>{title}</h2>
      )}
      <div style={{
        display:        'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
        gap:            12,
      }}>
        {children}
      </div>
    </section>
  )
}

LiveSignalPane.propTypes = {
  title:    PropTypes.string,
  children: PropTypes.node,
}
