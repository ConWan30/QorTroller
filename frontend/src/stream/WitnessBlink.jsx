/**
 * STREAM-2 Q4 — WitnessBlink
 * Ambient "your witness just blinked" from kills_seen (OCR sink rows).
 * Deliberate absence discipline: no FPS, no scoreboard, no mid-match clutter.
 * fresh_fires stays ABSENT until HARD-1 daemon persists the counter.
 */
import React, { useEffect, useRef, useState } from 'react'
import { STREAM_PAL, STREAM_FONTS } from './streamTokens'

export function WitnessBlink({ blink = null, reducedMotion = false }) {
  const seen = blink?.kills_seen
  const hasSeen = typeof seen === 'number' && seen >= 0
  const prev = useRef(null)
  const [pulse, setPulse] = useState(false)

  useEffect(() => {
    if (!hasSeen) return undefined
    if (prev.current !== null && seen > prev.current && !reducedMotion) {
      setPulse(true)
      const t = setTimeout(() => setPulse(false), 900)
      prev.current = seen
      return () => clearTimeout(t)
    }
    prev.current = seen
    return undefined
  }, [seen, hasSeen, reducedMotion])

  return (
    <div
      data-testid="witness-blink"
      data-kills-seen={hasSeen ? String(seen) : 'absent'}
      data-fresh-fires={blink?.fresh_fires_status || 'ABSENT'}
      data-pulsing={pulse ? 'true' : 'false'}
      style={{
        fontFamily: STREAM_FONTS.mono,
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        color: STREAM_PAL.dim,
        fontSize: 11,
        lineHeight: 1.5,
      }}
    >
      <span
        data-testid="witness-blink-dot"
        aria-hidden
        style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: pulse ? STREAM_PAL.cyan : (hasSeen ? STREAM_PAL.amber : STREAM_PAL.dim),
          boxShadow: pulse ? `0 0 10px ${STREAM_PAL.cyan}` : 'none',
          flexShrink: 0,
          transition: reducedMotion ? 'none' : 'background 0.2s, box-shadow 0.2s',
        }}
      />
      <span data-testid="witness-blink-line">
        {hasSeen
          ? `witness saw ${seen} killfeed row${seen === 1 ? '' : 's'} (not your score)`
          : (blink?.line || 'killfeed activity unknown')}
      </span>
      <span
        data-testid="fresh-fires-absent"
        style={{ color: STREAM_PAL.dim, opacity: 0.7 }}
        title={blink?.fresh_fires_note || 'fresh_fires ABSENT'}
      >
        · fresh-fires ABSENT
      </span>
    </div>
  )
}

export default WitnessBlink
