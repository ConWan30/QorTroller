/**
 * Evidence OS — SignalMeter
 *
 * Small inline meter for one numeric signal (poll rate Hz, chain
 * length, records-per-min, etc.). Bar fill or sparkline at operator
 * resolution — NOT 6-8px nano-text.
 *
 * Discipline:
 *   - Label is the human translation first; technical units secondary
 *   - Status comes from the same 7-state palette as DataBadge
 *   - When status='dormant' or value is null, renders "—" honestly
 */
import PropTypes from 'prop-types'

const _COLOR_VAR = {
  live:       '--os-status-live',
  verified:   '--os-status-verified',
  pending:    '--os-status-pending',
  blocked:    '--os-status-blocked',
  mock:       '--os-status-mock',
  killswitch: '--os-status-killswitch',
  dormant:    '--os-status-dormant',
}

export default function SignalMeter({
  label, value, unit, status = 'dormant',
  max, ariaLabel,
}) {
  const colorVar = _COLOR_VAR[status] || _COLOR_VAR.dormant
  const v = (value === null || value === undefined) ? null : Number(value)
  const m = max ? Number(max) : null
  const pct = (v !== null && m) ? Math.max(0, Math.min(100, (v / m) * 100)) : null
  const display = v === null ? '—' : (
    typeof value === 'number' && !Number.isInteger(value) ? value.toFixed(1) : String(value)
  )
  return (
    <div
      role="group"
      aria-label={ariaLabel || label}
      style={{
        display:        'flex',
        flexDirection:  'column',
        gap:            6,
        padding:        '12px 14px',
        background:     'var(--os-panel)',
        border:         '1px solid var(--os-border)',
        borderRadius:   'var(--os-radius)',
        fontFamily:     'JetBrains Mono, ui-monospace, monospace',
        minWidth:       180,
      }}
    >
      <div style={{
        fontSize:       'var(--os-text-min)',
        color:          'var(--os-text-faint)',
        letterSpacing:  '0.08em',
        textTransform:  'uppercase',
      }}>{label}</div>
      <div style={{
        display:    'flex',
        alignItems: 'baseline',
        gap:        6,
      }}>
        <span style={{
          fontSize:    'var(--os-text-h1)',
          fontWeight:  700,
          color:       `var(${colorVar})`,
        }}>{display}</span>
        {unit && v !== null && (
          <span style={{
            fontSize:   'var(--os-text-base)',
            color:      'var(--os-text-dim)',
          }}>{unit}</span>
        )}
      </div>
      {pct !== null && (
        <div
          aria-hidden="true"
          style={{
            position:     'relative',
            height:       4,
            background:   'var(--os-border-soft)',
            borderRadius: 2,
            overflow:     'hidden',
          }}
        >
          <div style={{
            position:    'absolute',
            inset:       0,
            width:       `${pct}%`,
            background:  `var(${colorVar})`,
            transition:  'width 0.3s',
          }} />
        </div>
      )}
    </div>
  )
}

SignalMeter.propTypes = {
  label:    PropTypes.string.isRequired,
  value:    PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  unit:     PropTypes.string,
  status:   PropTypes.string,
  max:      PropTypes.number,
  ariaLabel: PropTypes.string,
}
