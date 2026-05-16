/**
 * Evidence OS — EmptyState
 *
 * Used for placeholder workspaces (Live Match, Operator Queue,
 * Forensic Replay, Protocol State) until their vertical slices ship,
 * AND for empty data states inside Evidence Graph node-detail flyouts.
 *
 * Discipline: never paint "no data" as "no problem." The message tells
 * the operator what they're waiting on, what would populate the
 * surface, and where the data WOULD come from (endpoint reference).
 */
import PropTypes from 'prop-types'

export default function EmptyState({
  title, body, source, action,
}) {
  return (
    <div
      role="region"
      aria-label={title}
      style={{
        padding:        32,
        border:         '1px dashed var(--os-border)',
        borderRadius:   'var(--os-radius)',
        background:     'var(--os-panel-soft)',
        display:        'flex',
        flexDirection:  'column',
        gap:            12,
        maxWidth:       640,
        margin:         '0 auto',
        fontFamily:     'JetBrains Mono, ui-monospace, monospace',
      }}
    >
      <div style={{
        fontSize:       'var(--os-text-h2)',
        fontWeight:     700,
        color:          'var(--os-text)',
        letterSpacing:  '0.04em',
      }}>{title}</div>
      <div style={{
        fontSize:    'var(--os-text-base)',
        color:       'var(--os-text-dim)',
        lineHeight:  1.6,
      }}>{body}</div>
      {source && (
        <div style={{
          fontSize:    'var(--os-text-min)',
          color:       'var(--os-text-faint)',
          fontStyle:   'italic',
        }}>
          source: <code style={{ color: 'var(--os-text-dim)' }}>{source}</code>
        </div>
      )}
      {action && <div style={{ marginTop: 6 }}>{action}</div>}
    </div>
  )
}

EmptyState.propTypes = {
  title:  PropTypes.string.isRequired,
  body:   PropTypes.node.isRequired,
  source: PropTypes.string,
  action: PropTypes.node,
}
