/**
 * Evidence OS — VerdictPanel
 *
 * The dominant surface on /os/live. Single binary verdict answering
 * the operator's 3-second question: "Can this session count?"
 *
 * Verdicts (FROZEN at v1):
 *   counting  → SESSION COUNTS · all gates clear
 *   blocked   → SESSION BLOCKED · one or more blockers
 *   dormant   → NO ACTIVE SESSION · controller not engaged
 *   mock      → MOCK SESSION · bridge unreachable, this is fabricated
 *
 * Discipline:
 *   - The verdict word is large + the explanation is one human sentence
 *   - Mock state visually separated from live — never paint mock as live
 *   - aria-live='polite' so screen readers announce verdict changes
 *   - Status text is REDUNDANT to color — never color-only
 */
import PropTypes from 'prop-types'

const _COLOR_VAR = {
  counting: '--os-status-live',
  blocked:  '--os-status-blocked',
  dormant:  '--os-status-dormant',
  mock:     '--os-status-mock',
}

const _LABELS = {
  counting: 'SESSION COUNTS',
  blocked:  'SESSION BLOCKED',
  dormant:  'NO ACTIVE SESSION',
  mock:     'MOCK SESSION · not live',
}

const _MONO = 'JetBrains Mono, ui-monospace, monospace'

export default function VerdictPanel({ verdict = 'dormant', headline, subline }) {
  const colorVar = _COLOR_VAR[verdict] || _COLOR_VAR.dormant
  const verdictLabel = _LABELS[verdict] || 'UNKNOWN'
  return (
    <section
      role="status"
      aria-live="polite"
      aria-label={`Session verdict: ${verdictLabel}`}
      data-os-verdict={verdict}
      style={{
        display:        'flex',
        flexDirection:  'column',
        gap:            10,
        padding:        '24px 28px',
        background:     `color-mix(in srgb, var(${colorVar}) 8%, var(--os-panel))`,
        border:         `1px solid var(${colorVar})`,
        borderLeft:     `4px solid var(${colorVar})`,
        borderRadius:   'var(--os-radius)',
        fontFamily:     _MONO,
      }}
    >
      {/* Verdict label — text+color, never color-only */}
      <div style={{
        display:    'flex',
        alignItems: 'center',
        gap:        12,
      }}>
        <span
          aria-hidden="true"
          style={{
            width: 12, height: 12, borderRadius: '50%',
            background: `var(${colorVar})`,
            boxShadow: verdict === 'counting'
              ? `0 0 12px var(${colorVar})` : 'none',
            flexShrink: 0,
          }}
        />
        <span style={{
          fontSize:       18,
          fontWeight:     700,
          color:          `var(${colorVar})`,
          letterSpacing:  '0.06em',
        }}>{verdictLabel}</span>
      </div>

      {/* Headline — operator's 3-second answer in plain English */}
      {headline && (
        <div style={{
          fontSize:    'var(--os-text-h2)',
          color:       'var(--os-text)',
          lineHeight:  1.4,
        }}>{headline}</div>
      )}

      {/* Subline — protocol term + reason */}
      {subline && (
        <div style={{
          fontSize:    'var(--os-text-base)',
          color:       'var(--os-text-dim)',
          lineHeight:  1.5,
        }}>{subline}</div>
      )}
    </section>
  )
}

VerdictPanel.propTypes = {
  verdict: PropTypes.oneOf(['counting', 'blocked', 'dormant', 'mock']),
  headline: PropTypes.node,
  subline:  PropTypes.node,
}
