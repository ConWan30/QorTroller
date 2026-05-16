/**
 * Evidence OS — BlockerList
 *
 * Renders ONLY the blockers currently affecting the dominant verdict.
 * Each blocker is a human-translation-first line + the protocol term
 * + the source hook reference, so the operator knows what's gating
 * AND how to inspect deeper.
 *
 * Discipline:
 *   - If no blockers → render nothing (the verdict is "session counts";
 *     the list is the absence-proof, not noise)
 *   - Each entry is an <li> with role; the list itself is <ul role="list">
 *     for screen-reader navigability
 *   - No color-only signalling — every entry has a status label word
 */
import PropTypes from 'prop-types'
import DataBadge from './DataBadge'

const _MONO = 'JetBrains Mono, ui-monospace, monospace'

export default function BlockerList({ blockers }) {
  if (!blockers || blockers.length === 0) return null
  return (
    <section
      aria-label="Active blockers"
      style={{
        display:        'flex',
        flexDirection:  'column',
        gap:            8,
        padding:        '14px 16px',
        background:     'var(--os-panel)',
        border:         '1px solid var(--os-status-blocked)',
        borderLeft:     '3px solid var(--os-status-blocked)',
        borderRadius:   'var(--os-radius)',
        fontFamily:     _MONO,
      }}
    >
      <div style={{
        fontSize:       'var(--os-text-min)',
        color:          'var(--os-text-faint)',
        letterSpacing:  '0.08em',
        textTransform:  'uppercase',
        marginBottom:   2,
      }}>
        {blockers.length === 1 ? '1 blocker · session cannot count' : `${blockers.length} blockers · session cannot count`}
      </div>
      <ul role="list" style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 10 }}>
        {blockers.map((b, i) => (
          <li
            key={b.key || i}
            data-os-blocker={b.key || i}
            style={{
              display:        'flex',
              alignItems:     'flex-start',
              gap:            12,
              paddingTop:     i === 0 ? 0 : 8,
              borderTop:      i === 0 ? 'none' : '1px solid var(--os-border-soft)',
            }}
          >
            <DataBadge status={b.severity || 'blocked'} label={b.severityLabel} />
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
              <div style={{
                fontSize:    'var(--os-text-label)',
                fontWeight:  600,
                color:       'var(--os-text)',
                lineHeight:  1.5,
              }}>{b.message}</div>
              {b.protocolTerm && (
                <div style={{
                  fontSize:    'var(--os-text-min)',
                  color:       'var(--os-text-faint)',
                }}>
                  protocol: <code style={{ color: 'var(--os-text-dim)' }}>{b.protocolTerm}</code>
                </div>
              )}
              {b.source && (
                <div style={{
                  fontSize:    'var(--os-text-min)',
                  color:       'var(--os-text-faint)',
                }}>
                  source: <code style={{ color: 'var(--os-text-dim)' }}>{b.source}</code>
                </div>
              )}
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

BlockerList.propTypes = {
  blockers: PropTypes.arrayOf(PropTypes.shape({
    key:           PropTypes.string,
    message:       PropTypes.node.isRequired,   // human translation first
    protocolTerm:  PropTypes.string,             // optional protocol term
    source:        PropTypes.string,             // hook / endpoint
    severity:      PropTypes.string,             // DataBadge status
    severityLabel: PropTypes.string,             // override label text
  })),
}
