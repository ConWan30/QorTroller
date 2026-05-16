/**
 * Evidence OS — WorkspaceHeader
 *
 * Sits below the StatusStrip, inside each workspace. Renders the
 * workspace title + a one-line description + an optional right-side
 * slot for filters/actions. Semantic <header role="banner"> for
 * accessibility tree navigation.
 */
import PropTypes from 'prop-types'

export default function WorkspaceHeader({ title, description, right }) {
  return (
    <header role="banner" style={{
      display:        'flex',
      alignItems:     'baseline',
      gap:            16,
      padding:        '20px 24px',
      borderBottom:   '1px solid var(--os-border)',
      background:     'var(--os-panel-soft)',
      fontFamily:     'JetBrains Mono, ui-monospace, monospace',
    }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, flex: 1 }}>
        <h1 style={{
          margin:         0,
          fontSize:       'var(--os-text-h1)',
          fontWeight:     700,
          letterSpacing:  '0.04em',
          color:          'var(--os-text)',
        }}>{title}</h1>
        {description && (
          <div style={{
            fontSize:    'var(--os-text-base)',
            color:       'var(--os-text-dim)',
            lineHeight:  1.5,
            maxWidth:    720,
          }}>{description}</div>
        )}
      </div>
      {right && <div style={{ display: 'flex', gap: 8 }}>{right}</div>}
    </header>
  )
}

WorkspaceHeader.propTypes = {
  title:       PropTypes.string.isRequired,
  description: PropTypes.node,
  right:       PropTypes.node,
}
