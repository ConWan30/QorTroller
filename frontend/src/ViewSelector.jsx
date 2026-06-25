import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useHeartbeatStore } from './heartbeat/useHeartbeat'
import { FONTS, GAMER } from './shared/design/tokens'
import { RealityDot } from './design/realityHeartbeat'
import { Wordmark } from './design/Primitives'

// Tab bar curated 2026-06-24 to the 4 external-facing surfaces only (was 8 — too crowded):
// the product (Gamer) + the three outreach/reference decks (IoTeX grant, partner pitch,
// reference). Operator + AI-Chat removed from the app; Forensic + VPM de-listed but kept
// URL-reachable (`/?view=forensic`, `/?view=vpm`) as the "verify it yourself" proof surfaces
// to link from the decks. The Evidence-OS header link is removed.
const VIEWS = [
  { id: 'gamer',     num: '01', label: 'Gamer',           accent: GAMER.cyan },
  { id: 'grant',     num: '02', label: 'IoTeX · Grant',   accent: '#f0a868' },
  { id: 'partner',   num: '03', label: 'Partner · Pitch', accent: '#f0a868' },
  { id: 'reference', num: '04', label: 'Reference',       accent: '#5bd6a3' },
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
