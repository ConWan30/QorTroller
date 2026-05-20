import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Link } from 'react-router-dom'
import { useHeartbeatStore } from './heartbeat/useHeartbeat'
import { FONTS, GAMER } from './shared/design/tokens'

// QRESCE-0001 v0.5 grant-evaluator remodel — slimmed 4-tab bar. Only the
// design-language, grant-facing surfaces are shown: Gamer (hero) · Forensic
// (cryptographic depth) · Operator (self-monitoring honesty) · VPM (autonomous
// HTML snapshot proofs). Developer / Manufacturer / Marketplace / BRP are
// intentionally OFF the bar (deferred — dense tooling / zero partners / zero
// listings / BRP abstract-mesh pending a legibility pass). All remain in
// App.jsx VIEW_MAP (preserved in code); Developer is still reachable via the
// drift-alert badge for operator-agent drill-down.
const VIEWS = [
  { id: 'gamer',     label: 'GAMER',     accent: GAMER.cyan, icon: '◈' },
  { id: 'forensic',  label: 'FORENSIC',  accent: '#5bd6a3',  icon: '⌗' },
  { id: 'operator',  label: 'OPERATOR',  accent: '#f0a868',  icon: '◎' },
  // VPM Registry — autonomous Verified Projection Media (HTML snapshot proofs).
  { id: 'vpm',       label: 'VPM',       accent: '#f0a868',  icon: '◫' },
]

export function ViewSelector({ activeView, onViewChange }) {
  const merkleRoot    = useHeartbeatStore((s) => s.merkleRoot)
  const onChain       = useHeartbeatStore((s) => s.onChainConfirmed)
  const agentCount    = useHeartbeatStore((s) => s.agentCount)

  return (
    <div style={{
      display:        'flex',
      alignItems:     'center',
      justifyContent: 'space-between',
      padding:        '6px 16px',
      borderBottom:   '1px solid rgba(255,255,255,0.06)',
      background:     'rgba(2,4,8,0.95)',
      backdropFilter: 'blur(12px)',
      zIndex:         100,
      flexShrink:     0,
    }}>
      {/* Left: QorTroller wordmark — V.A.P.I. reference implementation.
          Typography: Syne (heavy weight, crafted curves, distinctive vs
          generic Rajdhani treatment used pre-QRESCE-0001 v0.5). Medial-T
          accent surfaces the Qor+Troller compound per brand discipline
          §6 hostile-read mitigation. V.A.P.I. category tag follows the
          2-layer reframing — brand = QorTroller, category = V.A.P.I. */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
        <span style={{
          fontFamily:    FONTS.body,
          fontSize:      19,
          fontWeight:    700,
          letterSpacing: '-0.005em',
          color:         '#d4dde8',
          display:       'inline-flex',
          alignItems:    'baseline',
        }}>
          <span>Qor</span>
          <span style={{ color: '#f0a868', fontWeight: 800 }}>T</span>
          <span>roller</span>
        </span>
        <span style={{
          fontFamily:    FONTS.mono,
          fontSize:      9,
          color:         'rgba(74,158,255,0.55)',
          letterSpacing: '0.12em',
          textTransform: 'uppercase',
        }}>
          <span style={{ color: 'rgba(240,168,104,0.65)' }}>V.A.P.I.</span>
          {' · phase 235'}
        </span>
        {/* Phase O5-EVIDENCE-OS Stage 1 — entry point to the new IA.
            Preserves existing 6 tabs; this is an additive cross-link. */}
        <Link
          to="/os/evidence"
          aria-label="Evidence OS — new proof-native IA"
          style={{
            fontFamily:    FONTS.mono,
            fontSize:      9,
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

      {/* Center: view tabs */}
      <div style={{ display: 'flex', gap: 2 }}>
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
                fontFamily:    FONTS.display,
                fontSize:      11,
                fontWeight:    600,
                letterSpacing: '0.12em',
                color:         active ? v.accent : 'rgba(200,216,232,0.45)',
                cursor:        'pointer',
                transition:    'all 0.15s ease',
                display:       'flex',
                alignItems:    'center',
                gap:           5,
              }}
            >
              <span style={{ fontSize: 9 }}>{v.icon}</span>
              {v.label}
              {v.liveFalse && (
                <span
                  title="live: false (Block W — pre-ceremony)"
                  style={{
                    width:        5,
                    height:       5,
                    borderRadius: '50%',
                    background:   '#e85a5a',
                    boxShadow:    '0 0 4px rgba(232,90,90,0.6)',
                    marginLeft:   2,
                  }}
                />
              )}
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
            </button>
          )
        })}
      </div>

      {/* Right: live merkle / agent status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontFamily: FONTS.mono, fontSize: 9 }}>
        <span style={{ color: onChain ? '#00ff88' : 'rgba(255,59,92,0.7)' }}>
          {onChain ? '● ON-CHAIN' : '○ PENDING'}
        </span>
        <span style={{ color: 'rgba(74,158,255,0.5)' }}>
          {agentCount} AGENTS
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
