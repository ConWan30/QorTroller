import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Link } from 'react-router-dom'
import { useHeartbeatStore } from './heartbeat/useHeartbeat'
import { FONTS, GAMER } from './shared/design/tokens'
import { RealityDot } from './design/realityHeartbeat'
import { Wordmark } from './design/Primitives'

// QRESCE-0001 v0.5 grant-evaluator remodel — slimmed 4-tab bar. Only the
// design-language, grant-facing surfaces are shown: Gamer (hero) · Forensic
// (cryptographic depth) · Operator (self-monitoring honesty) · VPM (autonomous
// HTML snapshot proofs). Developer / Manufacturer / Marketplace / BRP are
// intentionally OFF the bar (deferred — dense tooling / zero partners / zero
// listings / BRP abstract-mesh pending a legibility pass). All remain in
// App.jsx VIEW_MAP (preserved in code); Developer is still reachable via the
// drift-alert badge for operator-agent drill-down.
const VIEWS = [
  { id: 'gamer',    num: '01', label: 'Gamer',                 accent: GAMER.cyan },
  { id: 'forensic', num: '02', label: 'Forensic · Explorer',   accent: '#5bd6a3' },
  { id: 'operator', num: '03', label: 'Operator · Evidence',   accent: '#f0a868' },
  // VPM Registry — autonomous Verified Projection Media (HTML snapshot proofs).
  { id: 'vpm',      num: '04', label: 'VPM · Proofs',          accent: '#f0a868' },
  // Grant Brief — brand-locked IoTeX grant-evaluator deck (public, no auth).
  { id: 'grant',    num: '05', label: 'Grant · Brief',         accent: '#f0a868' },
  // Reference — canonical what/how/forward codex (public, no auth).
  { id: 'reference', num: '06', label: 'Reference',            accent: '#5bd6a3' },
  // Partner Brief — self-contained manufacturer/partner pitch deck (public, no auth).
  { id: 'partner',  num: '07', label: 'Partner · Brief',       accent: '#f0a868' },
]

export function ViewSelector({ activeView, onViewChange }) {
  const merkleRoot    = useHeartbeatStore((s) => s.merkleRoot)
  const onChain       = useHeartbeatStore((s) => s.onChainConfirmed)

  return (
    <div style={{
      display:        'flex',
      alignItems:     'center',
      justifyContent: 'space-between',
      gap:            12,
      padding:        '6px 16px',
      borderBottom:   '1px solid rgba(255,255,255,0.06)',
      background:     'rgba(2,4,8,0.95)',
      backdropFilter: 'blur(12px)',
      zIndex:         100,
      flexShrink:     0,
      // Bulletproof against horizontal overflow: the bar never widens the
      // window (html/body is overflow:auto for the public-viewer routes, so a
      // too-wide header would otherwise produce a side-scrollbar on the SPA).
      minWidth:       0,
      maxWidth:       '100vw',
      overflow:       'hidden',
    }}>
      {/* Left: QorTroller wordmark — V.A.P.I. reference implementation.
          Path A handoff PR 1: replaced 14 lines of inline-JSX wordmark
          with the scope-independent <Wordmark> primitive (Primitives.jsx).
          Eliminates the drift v3 audit flagged ("wordmark duplicated as
          inline JSX rather than using the shared primitive"). All sub-11px
          font sizes in this strip bumped to 11px per brand-spec floor. */}
      <div style={{
        display: 'flex', alignItems: 'baseline', gap: 10,
        minWidth: 0, flexShrink: 1, overflow: 'hidden',
      }}>
        <Wordmark size={18} />
        <span style={{
          fontFamily:    FONTS.mono,
          fontSize:      11,
          color:         'rgba(74,158,255,0.55)',
          letterSpacing: '0.12em',
          textTransform: 'uppercase',
          whiteSpace:    'nowrap',
          overflow:      'hidden',
          textOverflow:  'ellipsis',
          flexShrink:    1,
          minWidth:      0,
        }}>
          <span style={{ color: 'rgba(240,168,104,0.65)' }}>V.A.P.I.</span>
        </span>
        {/* Phase O5-EVIDENCE-OS Stage 1 — entry point to the new IA.
            Preserves existing 6 tabs; this is an additive cross-link. */}
        <Link
          to="/os/evidence"
          aria-label="Evidence OS — new proof-native IA"
          style={{
            fontFamily:    FONTS.mono,
            fontSize:      11,
            fontWeight:    700,
            color:         '#f0a868',
            background:    'rgba(240,168,104,0.10)',
            border:        '1px solid rgba(240,168,104,0.45)',
            borderRadius:  3,
            padding:       '2px 7px',
            letterSpacing: '0.08em',
            textDecoration: 'none',
            marginLeft:    4,
            textTransform: 'uppercase',
          }}
        >Evidence OS →</Link>
      </div>

      {/* Center: view tabs — priority element; never shrinks (the 01–04
          numbered sequence stays intact + on one line). */}
      <div style={{ display: 'flex', gap: 2, flexShrink: 0 }}>
        {VIEWS.map((v) => {
          const active = v.id === activeView
          return (
            <button
              key={v.id}
              onClick={() => onViewChange(v.id)}
              style={{
                background:    active ? `${v.accent}18` : 'transparent',
                border:        `1px solid ${active ? v.accent + '55' : 'rgba(255,255,255,0.06)'}`,
                borderRadius:  4,
                padding:       '4px 14px',
                fontFamily:    FONTS.body,
                fontSize:      13,
                fontWeight:    active ? 700 : 500,
                letterSpacing: '0.01em',
                color:         active ? v.accent : 'rgba(200,216,232,0.50)',
                cursor:        'pointer',
                transition:    'all 0.15s ease',
                // Stacked tab — number above label, per the design's final
                // iteration ("01 / Gamer"). Number sits on its own line in
                // amber-on-active; label below. Container stays flexShrink:0
                // so the 01–04 sequence never wraps or triggers side-scroll.
                display:        'flex',
                flexDirection:  'column',
                alignItems:     'flex-start',
                gap:            2,
                lineHeight:     1.1,
                whiteSpace:     'nowrap',
              }}
            >
              <span style={{
                fontFamily:    FONTS.mono,
                fontSize:      11,
                fontWeight:    500,
                color:         active ? v.accent : 'rgba(200,216,232,0.30)',
                letterSpacing: '0.14em',
              }}>{v.num}</span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                {v.label}
                {active && (
                  <motion.span
                    layoutId="tab-indicator"
                    style={{
                      width:        4,
                      height:       4,
                      borderRadius: '50%',
                      background:   v.accent,
                      boxShadow:    `0 0 6px ${v.accent}`,
                    }}
                  />
                )}
              </span>
            </button>
          )
        })}
      </div>

      {/* Right: live merkle / agent status — shrinks/truncates first so it
          never forces a horizontal scrollbar on narrow viewports. */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12,
        fontFamily: FONTS.mono, fontSize: 11,
        minWidth: 0, flexShrink: 1, overflow: 'hidden', whiteSpace: 'nowrap',
        justifyContent: 'flex-end',
      }}>
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
    </div>
  )
}
