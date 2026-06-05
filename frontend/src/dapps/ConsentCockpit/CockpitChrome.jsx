// Consent Cockpit dApp — minimal top header.
//
// Distinct from the operator dashboard's <ViewSelector> and EvidenceOS
// <AppShell>: the Cockpit is its own standalone surface (`/consent`)
// and wears the lightest chrome possible. Wordmark + back-link + live
// status only. No view tabs, no eyebrow row.
//
// Honesty rails: bridge / kill-switch / on-chain dots come from the
// same heartbeat store the dashboard uses, so the Cockpit shows the
// SAME live state — not a wrapper "always green" indicator.

import { Link } from 'react-router-dom'
import { useHeartbeatStore } from '../../heartbeat/useHeartbeat'
import { FONTS, GAMER } from '../../shared/design/tokens'
import { RealityDot } from '../../design/realityHeartbeat'
import { Wordmark } from '../../design/Primitives'

export function CockpitChrome() {
  const merkleRoot  = useHeartbeatStore((s) => s.merkleRoot)
  const onChain     = useHeartbeatStore((s) => s.onChainConfirmed)

  return (
    <header
      style={{
        display:        'flex',
        alignItems:     'center',
        justifyContent: 'space-between',
        gap:            12,
        padding:        '8px 20px',
        borderBottom:   '1px solid rgba(255,255,255,0.06)',
        background:     'rgba(2,4,8,0.95)',
        backdropFilter: 'blur(12px)',
        minWidth:       0,
        maxWidth:       '100vw',
        overflow:       'hidden',
      }}
    >
      {/* Left — wordmark + dApp name + back-link to dashboard */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, minWidth: 0 }}>
        <Wordmark size={18} />
        <span style={{
          fontFamily:    FONTS.mono,
          fontSize:      11,
          letterSpacing: '0.16em',
          textTransform: 'uppercase',
          color:         GAMER.cyan + 'cc',
          whiteSpace:    'nowrap',
        }}>
          Consent Cockpit
        </span>
        <Link
          to="/"
          aria-label="Return to operator dashboard"
          style={{
            fontFamily:     FONTS.mono,
            fontSize:       10,
            letterSpacing:  '0.08em',
            color:          'rgba(200,216,232,0.45)',
            textDecoration: 'none',
            whiteSpace:     'nowrap',
            textTransform:  'uppercase',
            marginLeft:     6,
          }}
        >
          ← Dashboard
        </Link>
      </div>

      {/* Right — honest live status (same primitives as ViewSelector) */}
      <div
        style={{
          display:        'flex',
          alignItems:     'center',
          gap:            12,
          fontFamily:     FONTS.mono,
          fontSize:       11,
          minWidth:       0,
          flexShrink:     1,
          overflow:       'hidden',
          whiteSpace:     'nowrap',
          justifyContent: 'flex-end',
        }}
      >
        <RealityDot />
        <span style={{ color: onChain ? '#00ff88' : 'rgba(255,59,92,0.7)' }}>
          {onChain ? '● ON-CHAIN' : '○ PENDING'}
        </span>
        {merkleRoot && (
          <span style={{ color: 'rgba(74,158,255,0.35)', letterSpacing: '0.04em' }}>
            {merkleRoot.slice(-12)}
          </span>
        )}
      </div>
    </header>
  )
}
