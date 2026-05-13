import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useHeartbeatStore } from './heartbeat/useHeartbeat'
import { FONTS, GAMER, DEVELOPER, MANUFACTURER } from './shared/design/tokens'

const VIEWS = [
  { id: 'gamer',        label: 'GAMER',        accent: GAMER.cyan,          icon: '◈' },
  { id: 'developer',   label: 'DEVELOPER',    accent: DEVELOPER.orange,    icon: '◇' },
  { id: 'manufacturer',label: 'MANUFACTURER', accent: MANUFACTURER.blue,   icon: '⬡' },
  // 4th tab: BRP renderer post-milestone incorporation (OQ-7).
  // Pre-ceremony, live: false. Distinct accent + small live:false dot
  // surfaced in the tab so the operator can identify the audit-state at a glance.
  { id: 'brp',         label: 'BRP',          accent: '#9bc4e8',           icon: '◉', liveFalse: true },
  // 5th tab: Phase 238 PALL Marketplace — sellers + buyers + auditors.
  // Cyan accent (verified-data theme) per VAPI tier palette LOCKED.
  { id: 'marketplace', label: 'MARKETPLACE',  accent: '#22d3ee',           icon: '⬢' },
  // 6th tab: Phase O4-VPM-INT Stream C — VPM Registry. Read-only
  // inspection surface for Verified Projection Media artifacts. Amber
  // accent (operator-audit theme; distinct from DEVELOPER orange so the
  // two operator-facing tabs remain visually distinguishable).
  { id: 'vpm',         label: 'VPM',          accent: '#f0a868',           icon: '◫' },
]

export function ViewSelector({ activeView, onViewChange }) {
  const isMock        = useHeartbeatStore((s) => s.isMock)
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
      {/* Left: VAPI wordmark */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{
          fontFamily:    FONTS.display,
          fontSize:      18,
          fontWeight:    700,
          letterSpacing: '0.12em',
          color:         '#c8d8e8',
        }}>VAPI</span>
        <span style={{
          fontFamily: FONTS.mono,
          fontSize:   9,
          color:      'rgba(74,158,255,0.5)',
          letterSpacing: '0.08em',
        }}>PHASE 235</span>
        {isMock && (
          <span style={{
            fontFamily:  FONTS.mono,
            fontSize:    8,
            color:       '#ff9500',
            background:  'rgba(255,149,0,0.12)',
            border:      '1px solid rgba(255,149,0,0.3)',
            borderRadius: 2,
            padding:     '1px 5px',
            letterSpacing: '0.05em',
          }}>MOCK DATA — bridge offline</span>
        )}
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
