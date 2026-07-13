/**
 * PKG-UI-01 — WitnessRespiration
 * Single presence indicator from freshness-class (not FPS, not crop counts).
 * Named export. Animates ONLY the cyan breath pulse when tone===live;
 * prefers-reduced-motion disables the pulse animation.
 */
import React, { useEffect, useState } from 'react'
import { STREAM_PAL, STREAM_FONTS, PRESENCE_TONE_COLOR } from './streamTokens'

export function WitnessRespiration({
  presenceLine = 'witness state unknown',
  presenceTone = 'unknown',
  nodeState = '—',
  freshnessClass = 'UNKNOWN',
  sessionIdDisplay = null,
  pack = null,
}) {
  const [reduced, setReduced] = useState(false)
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    setReduced(mq.matches)
    const fn = () => setReduced(mq.matches)
    mq.addEventListener?.('change', fn)
    return () => mq.removeEventListener?.('change', fn)
  }, [])

  const color = PRESENCE_TONE_COLOR[presenceTone] || STREAM_PAL.dim
  const isLive = presenceTone === 'live' && freshnessClass === 'LIVE'

  return (
    <div
      data-testid="witness-respiration"
      data-presence-tone={presenceTone}
      data-freshness={freshnessClass}
      data-fabricated-liveness="false"
      style={{
        fontFamily: STREAM_FONTS.mono,
        color: STREAM_PAL.ink,
        maxWidth: 520,
      }}
    >
      <style>{`
        @keyframes qortroller-witness-breath {
          0%, 100% { opacity: 0.55; box-shadow: 0 0 8px ${STREAM_PAL.cyan}; }
          50% { opacity: 1; box-shadow: 0 0 16px ${STREAM_PAL.cyan}; }
        }
      `}</style>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <span
          data-testid="witness-pulse"
          aria-hidden="true"
          style={{
            width: 14,
            height: 14,
            borderRadius: '50%',
            marginTop: 6,
            flexShrink: 0,
            background: color,
            boxShadow: isLive ? `0 0 12px ${STREAM_PAL.cyan}` : 'none',
            animation: isLive && !reduced ? 'qortroller-witness-breath 2s ease-in-out infinite' : 'none',
          }}
        />
        <div>
          <div
            data-testid="presence-line"
            style={{
              fontSize: '1.2rem',
              lineHeight: 1.4,
              color: isLive ? STREAM_PAL.cyan : STREAM_PAL.ink,
              marginBottom: 12,
            }}
          >
            {presenceLine}
          </div>
          <div style={{ color: STREAM_PAL.dim, fontSize: 12, lineHeight: 1.7 }}>
            <div>node <b style={{ color: STREAM_PAL.ink, fontWeight: 500 }}>{nodeState || '—'}</b>
              {' · '}freshness <b style={{ color: STREAM_PAL.ink, fontWeight: 500 }}>{freshnessClass || 'UNKNOWN'}</b>
            </div>
            {sessionIdDisplay ? (
              <div>session <b style={{ color: STREAM_PAL.ink, fontWeight: 500 }}>{sessionIdDisplay}</b></div>
            ) : null}
            {pack ? (
              <div>pack <b style={{ color: STREAM_PAL.ink, fontWeight: 500 }}>{pack}</b></div>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  )
}

export default WitnessRespiration
