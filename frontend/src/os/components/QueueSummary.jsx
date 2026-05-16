/**
 * Evidence OS — QueueSummary
 *
 * Top strip on /os/queue. Answers operator's first question
 * ("what needs attention?") at a glance — total pending +
 * critical blockers + curator flags + drift findings + invariant
 * gate state. Each tile is a role='group' with explicit label.
 *
 * Discipline:
 *   - Each tile carries a status word AND a count — never numeric-only
 *   - Invariant gate FAIL is structurally separated (red border + word)
 *     because it is the strongest "do not proceed" signal in the surface
 *   - "—" rendered honestly when a hook is loading or offline
 */
import PropTypes from 'prop-types'

const _MONO = 'JetBrains Mono, ui-monospace, monospace'

function _Tile({ label, count, status, hint }) {
  const colorVar = `--os-status-${status || 'dormant'}`
  return (
    <div
      role="group"
      aria-label={`${label}: ${count ?? '—'} (${status || 'unknown'})`}
      style={{
        // Stage 5.3 (iPhone 15 walk-through Finding A) — tile no longer
        // self-flexes inside the parent; parent is now a CSS grid that
        // gives each tile a 140px minimum. Tile only constrains its
        // own minWidth:0 to allow inner text to wrap when needed.
        minWidth:       0,
        padding:        '12px 14px',
        background:     'var(--os-panel)',
        border:         `1px solid var(${colorVar})`,
        borderLeft:     `3px solid var(${colorVar})`,
        borderRadius:   'var(--os-radius)',
        display:        'flex',
        flexDirection:  'column',
        gap:            4,
        fontFamily:     _MONO,
      }}
    >
      <div style={{
        fontSize:       'var(--os-text-min)',
        letterSpacing:  '0.08em',
        textTransform:  'uppercase',
        color:          'var(--os-text-faint)',
      }}>{label}</div>
      <div style={{
        display:        'flex',
        alignItems:     'baseline',
        gap:            8,
      }}>
        <span style={{
          fontSize: 'var(--os-text-h1)',
          fontWeight: 700,
          color: `var(${colorVar})`,
        }}>{count ?? '—'}</span>
        <span style={{
          fontSize: 'var(--os-text-min)',
          color: `var(${colorVar})`,
          letterSpacing: '0.06em',
        }}>{status?.toUpperCase() || 'UNKNOWN'}</span>
      </div>
      {hint && (
        <div style={{
          fontSize: 'var(--os-text-min)',
          color: 'var(--os-text-faint)',
        }}>{hint}</div>
      )}
    </div>
  )
}

_Tile.propTypes = {
  label:  PropTypes.string.isRequired,
  count:  PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  status: PropTypes.string,
  hint:   PropTypes.string,
}

export default function QueueSummary({ tiles }) {
  return (
    <section
      role="region"
      aria-label="Queue summary"
      style={{
        // Stage 5.3 (iPhone 15 Finding A): swap from flex+wrap to CSS
        // grid with auto-fit minmax. Each tile gets a hard 140px
        // minimum width; below that, the row wraps to fewer columns.
        // At 393px iPhone 15 width: ~2 columns × 3 rows (clean).
        // At 768px tablet: ~5 columns. At 1280px+ desktop: all 6 in
        // one row. The prior flex:1 1 0 caused tiles to compress to
        // ~50px before flex-wrap kicked in, making content overflow
        // the rectangle bounds.
        display:               'grid',
        gridTemplateColumns:   'repeat(auto-fit, minmax(140px, 1fr))',
        gap:                   10,
      }}
    >
      {tiles.map(t => <_Tile key={t.label} {...t} />)}
    </section>
  )
}

QueueSummary.propTypes = {
  tiles: PropTypes.arrayOf(PropTypes.shape({
    label:  PropTypes.string.isRequired,
    count:  PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
    status: PropTypes.string,
    hint:   PropTypes.string,
  })).isRequired,
}
