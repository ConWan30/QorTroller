/**
 * DEPRECATED Phase 238-FRONTEND-V3 — superseded by the unified 3D Twin at
 * frontend/src/legacy/ControllerTwin.jsx, which now consumes the same SSE
 * cryptographic-event stream and infuses the 5 frozen event types
 * (poac_chain_link / gic_verdict / pcc_state_change / curator_verdict /
 * anchor_confirmed) as additive layered effects on top of the existing R3F
 * humanity / breathing / trigger-orbit / anomaly-halo animations.
 *
 * Single-Twin invariant: the dashboard MUST render exactly ONE controller
 * visualization.  This simplified SVG silhouette is kept for git history
 * only; do NOT import.  See /root/.claude/plans/here-is-a-draft-shimmying-quasar.md
 * for the full V3 design.
 */
import { useEffect, useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useTwinStream } from '../api/twinStream'
import { ConsentMatrix } from './ConsentMatrix'

const PULSE_DURATION_MS = 800

export function TwinControllerStream({ consentBitmask = 0, height = 320 }) {
  const { lastEvent, connected, eventCounts } = useTwinStream({ backfill: 0 })
  const [activePulse, setActivePulse] = useState(null)
  const [pccColor, setPccColor]       = useState('var(--vapi-tier-basic)')

  // Map incoming events to active animation state
  useEffect(() => {
    if (!lastEvent) return
    const { type, data } = lastEvent

    if (type === 'poac_chain_link') {
      setActivePulse({ kind: 'poac', color: 'var(--vapi-cyan)', anim: 'vapi-pulse-cyan' })
    } else if (type === 'gic_verdict') {
      const v = data.verdict
      const c = v === 'CERTIFY' ? 'var(--vapi-orange)' :
                v === 'FLAG'    ? 'var(--vapi-warn)'   :
                v === 'BLOCK'   ? 'var(--vapi-block)'  :
                'var(--vapi-cyan)'
      const anim = v === 'CERTIFY' ? 'vapi-pulse-orange' :
                   v === 'FLAG'    ? 'vapi-pulse-amber'  :
                   v === 'BLOCK'   ? 'vapi-pulse-block'  :
                   'vapi-pulse-cyan'
      setActivePulse({ kind: 'gic', color: c, anim, label: v })
    } else if (type === 'pcc_state_change') {
      const host = data.host_state
      const next =
        host === 'EXCLUSIVE_USB' ? 'var(--vapi-pcc-nominal)' :
        host === 'CONTESTED'     ? 'var(--vapi-pcc-contested)' :
        host === 'DEGRADED'      ? 'var(--vapi-pcc-degraded)' :
        'var(--vapi-pcc-disconnect)'
      setPccColor(next)
    } else if (type === 'curator_verdict') {
      const v = data.verdict
      const c =
        v === 'APPROVED'                         ? 'var(--vapi-cyan)'  :
        v?.startsWith('FLAGGED_')                ? 'var(--vapi-warn)'  :
        v?.startsWith('REJECTED_')               ? 'var(--vapi-block)' :
        'var(--vapi-cyan)'
      const anim =
        v === 'APPROVED'                         ? 'vapi-pulse-cyan'  :
        v?.startsWith('FLAGGED_')                ? 'vapi-pulse-amber' :
        v?.startsWith('REJECTED_')               ? 'vapi-pulse-block' :
        'vapi-pulse-cyan'
      setActivePulse({ kind: 'curator', color: c, anim, label: v })
    } else if (type === 'anchor_confirmed') {
      setActivePulse({ kind: 'anchor', color: 'var(--vapi-orange)', anim: 'vapi-aurora-shimmer', label: data.primitive_type })
    }

    // Auto-clear pulse after duration
    const timer = setTimeout(() => setActivePulse(null), PULSE_DURATION_MS)
    return () => clearTimeout(timer)
  }, [lastEvent])

  return (
    <div style={{
      position:        'relative',
      width:           '100%',
      height,
      background:      'var(--vapi-void)',
      border:          `1px solid ${pccColor}`,
      borderRadius:    4,
      overflow:        'hidden',
      boxShadow:       activePulse ? `var(--vapi-glow-info)` : 'none',
      transition:      'box-shadow 0.4s ease, border-color 0.6s ease',
      animation:       activePulse ? `${activePulse.anim} ${PULSE_DURATION_MS}ms ease-out 1` : 'none',
    }}>
      {/* Stream-status indicator */}
      <div style={{
        position:    'absolute',
        top:         8,
        right:       8,
        display:     'flex',
        alignItems:  'center',
        gap:         6,
        fontFamily:  "'JetBrains Mono', monospace",
        fontSize:    9,
        letterSpacing: '0.05em',
        color:       connected ? 'var(--vapi-cyan)' : 'var(--vapi-tier-basic)',
        zIndex:      10,
      }}>
        <span style={{
          width:        6,
          height:       6,
          borderRadius: 3,
          background:   connected ? 'var(--vapi-cyan)' : 'var(--vapi-tier-basic)',
          boxShadow:    connected ? 'var(--vapi-cyan-glow)' : 'none',
        }} />
        {connected ? 'TWIN STREAM LIVE' : 'STREAM OFFLINE'}
      </div>

      {/* Static twin SVG silhouette — pulses applied via box-shadow on container */}
      <div style={{
        position:   'absolute',
        inset:      0,
        display:    'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap:        16,
      }}>
        {/* DualShock Edge silhouette (simplified) */}
        <svg
          width="200" height="120" viewBox="0 0 200 120"
          style={{ filter: activePulse ? `drop-shadow(0 0 12px ${activePulse.color})` : 'none' }}
        >
          {/* Body */}
          <rect x="20" y="30" width="160" height="55" rx="22" ry="22"
                fill="none" stroke={pccColor} strokeWidth="2" />
          {/* Grips */}
          <rect x="14" y="45" width="22" height="50" rx="11"
                fill="none" stroke={pccColor} strokeWidth="2" />
          <rect x="164" y="45" width="22" height="50" rx="11"
                fill="none" stroke={pccColor} strokeWidth="2" />
          {/* L2 / R2 triggers */}
          <rect x="34" y="20" width="28" height="10" rx="4"
                fill="none" stroke={activePulse?.kind === 'gic' ? activePulse.color : pccColor} strokeWidth="2" />
          <rect x="138" y="20" width="28" height="10" rx="4"
                fill="none" stroke={activePulse?.kind === 'gic' ? activePulse.color : pccColor} strokeWidth="2" />
          {/* Touchpad */}
          <rect x="80" y="48" width="40" height="20" rx="4"
                fill={activePulse?.kind === 'curator' ? activePulse.color : 'none'}
                fillOpacity="0.2"
                stroke={activePulse?.kind === 'curator' ? activePulse.color : pccColor} strokeWidth="2" />
          {/* D-pad — pulses on poac_chain_link */}
          <circle cx="50" cy="60" r="9"
                  fill={activePulse?.kind === 'poac' ? activePulse.color : 'none'}
                  fillOpacity="0.4"
                  stroke={pccColor} strokeWidth="2" />
          {/* Buttons cluster */}
          <circle cx="150" cy="60" r="9" fill="none" stroke={pccColor} strokeWidth="2" />
        </svg>

        {/* Active event readout */}
        <div style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize:   10,
          color:      activePulse ? activePulse.color : 'var(--vapi-tier-basic)',
          letterSpacing: '0.08em',
          minHeight:  14,
          textAlign:  'center',
        }}>
          <AnimatePresence mode="wait">
            {activePulse ? (
              <motion.div
                key={activePulse.label || activePulse.kind}
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 4 }}
                transition={{ duration: 0.18 }}
              >
                ● {activePulse.kind.toUpperCase()}{activePulse.label ? ` ${activePulse.label}` : ''}
              </motion.div>
            ) : (
              <motion.div
                key="idle"
                initial={{ opacity: 0 }}
                animate={{ opacity: 0.5 }}
                exit={{ opacity: 0 }}
              >
                ○ awaiting cryptographic event
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Consent HUD bottom-left */}
      <div style={{
        position:   'absolute',
        bottom:     8,
        left:       12,
        display:    'flex',
        alignItems: 'center',
        gap:        8,
      }}>
        <span style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize:   8,
          color:      'var(--vapi-tier-basic)',
          letterSpacing: '0.06em',
        }}>CONSENT:</span>
        <ConsentMatrix bitmask={consentBitmask} mode="compact" />
      </div>

      {/* Event counter bottom-right */}
      <div style={{
        position:   'absolute',
        bottom:     8,
        right:      12,
        fontFamily: "'JetBrains Mono', monospace",
        fontSize:   8,
        color:      'var(--vapi-tier-basic)',
        letterSpacing: '0.05em',
      }}>
        {Object.entries(eventCounts).slice(0, 3).map(([k, v]) => (
          <span key={k} style={{ marginLeft: 8 }}>{k}={v}</span>
        ))}
      </div>
    </div>
  )
}
