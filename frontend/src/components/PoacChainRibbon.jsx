// PoacChainRibbon — top-edge GIC chain accretion ticker for GamerView.
//
// Phase 238-FRONTEND-V4 — gives the gamer a real-time, cryptographically
// honest view of their grind chain growing. Each dot represents one GIC
// stamp.  When a `poac_chain_link` SSE event fires, the rightmost dot
// pulses cyan; older dots drift left and fade.  When chain_length grows,
// the dot sequence extends (capped at 24 visible).
//
// Why novel for VAPI:
//   1. Visualizes the VAPI-exclusive GIC chain primitive (Phase 235-A
//      FROZEN-v1) as living art — the protocol's headline artifact.
//   2. Uses the SAME 5-event SSE stream that drives the BRP/Twin
//      imprint layer; consistent visual language across views.
//   3. Tier-color discipline preserved: cyan = chain healthy, orange =
//      most-recent verdict was FLAG, block-red = chain broken.
//   4. Honest data: chainLen + intact come from /bridge/grind-chain-status
//      (live, noMock=true); SSE pulses come from twin-stream.

import { useEffect, useRef, useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { FONTS } from '../shared/design/tokens'
import { useTwinStream } from '../api/twinStream'

const VISIBLE_LINKS = 24

export function PoacChainRibbon({ chainLen, target, intact, latestHash, sessionId }) {
  // Keep an in-memory ledger of the last N chain links + a per-link
  // pulse state.  Initialize from chainLen so older links exist as dots
  // even before any SSE event fires.
  const [pulseTs, setPulseTs] = useState(0)
  const [linkBuffer, setLinkBuffer] = useState(() => {
    return Array.from({ length: Math.min(chainLen, VISIBLE_LINKS) }, (_, i) => ({
      n: chainLen - VISIBLE_LINKS + i + 1,
      verdict: 'CERTIFY', // assume historical CERTIFY; real verdict comes via SSE on new events
      ts: 0,
    })).filter(l => l.n > 0)
  })

  const lastChainLenRef = useRef(chainLen)

  // Watch for chainLen growth from polling — append synthetic CERTIFY
  // entries (older history is approximated; new entries come via SSE).
  useEffect(() => {
    if (chainLen > lastChainLenRef.current) {
      const delta = chainLen - lastChainLenRef.current
      setLinkBuffer(prev => {
        const next = [...prev]
        for (let i = 0; i < delta; i++) {
          next.push({ n: lastChainLenRef.current + i + 1, verdict: 'CERTIFY', ts: Date.now() })
        }
        return next.slice(-VISIBLE_LINKS)
      })
      lastChainLenRef.current = chainLen
    }
  }, [chainLen])

  // Listen for SSE poac_chain_link + gic_verdict events to pulse the rightmost dot.
  const { lastEvent: sseEvent } = useTwinStream({
    filter: ['poac_chain_link', 'gic_verdict'],
  })
  useEffect(() => {
    if (!sseEvent) return
    setPulseTs(Date.now())
    if (sseEvent.type === 'gic_verdict' && sseEvent.data?.verdict) {
      // Tag the most-recent link with the verdict
      setLinkBuffer(prev => {
        if (prev.length === 0) return prev
        const next = [...prev]
        next[next.length - 1] = { ...next[next.length - 1], verdict: sseEvent.data.verdict }
        return next
      })
    }
  }, [sseEvent])

  const progressPct = target > 0 ? Math.min(100, (chainLen / target) * 100) : 0
  const ribbonColor = !intact
    ? 'var(--vapi-block)'
    : progressPct >= 100
      ? 'var(--vapi-tier-premium)'
      : 'var(--vapi-cyan)'

  return (
    <div
      data-testid="poac-chain-ribbon"
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        zIndex: 8,
        padding: '10px 16px 12px',
        background: 'linear-gradient(180deg, rgba(2,4,8,0.78) 0%, rgba(2,4,8,0.48) 60%, transparent 100%)',
        backdropFilter: 'blur(4px)',
        pointerEvents: 'none',
      }}
    >
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 14,
      }}>
        {/* Label + chain length */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 110 }}>
          <span style={{
            fontFamily: "'Rajdhani', sans-serif",
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: '0.15em',
            color: ribbonColor,
            textShadow: `0 0 6px ${ribbonColor}`,
          }}>
            POAC CHAIN
          </span>
          <span style={{
            fontFamily: FONTS.mono,
            fontSize: 9,
            color: 'var(--vapi-tier-basic)',
            letterSpacing: '0.06em',
          }}>
            <span style={{ color: ribbonColor, fontWeight: 600 }}>{chainLen}</span>
            <span style={{ opacity: 0.4 }}> / {target}</span>
            {!intact && (
              <span style={{ color: 'var(--vapi-block)', marginLeft: 6, fontWeight: 700 }}>
                CHAIN_BROKEN
              </span>
            )}
          </span>
        </div>

        {/* Dot strip */}
        <div style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          gap: 4,
          justifyContent: 'flex-end',
          height: 18,
        }}>
          <AnimatePresence initial={false}>
            {linkBuffer.map((link, idx) => {
              const isLatest = idx === linkBuffer.length - 1
              const verdictColor =
                link.verdict === 'BLOCK' ? 'var(--vapi-block)' :
                link.verdict === 'FLAG' ? 'var(--vapi-orange)' :
                link.verdict === 'HOLD' ? 'var(--vapi-amber)' :
                'var(--vapi-cyan)'
              return (
                <motion.span
                  key={link.n}
                  initial={{ scale: 0.4, opacity: 0, y: -6 }}
                  animate={{
                    scale: isLatest && Date.now() - pulseTs < 600 ? 1.45 : 1.0,
                    opacity: 0.4 + (idx / linkBuffer.length) * 0.6,
                    y: 0,
                  }}
                  exit={{ opacity: 0, x: -10, scale: 0.6 }}
                  transition={{ duration: 0.32, ease: 'easeOut' }}
                  title={`GIC #${link.n} · ${link.verdict}`}
                  style={{
                    display: 'inline-block',
                    width: 8,
                    height: 8,
                    borderRadius: 4,
                    background: verdictColor,
                    boxShadow: isLatest && Date.now() - pulseTs < 600
                      ? `0 0 14px ${verdictColor}, 0 0 6px ${verdictColor}`
                      : `0 0 4px ${verdictColor}80`,
                  }}
                />
              )
            })}
          </AnimatePresence>
        </div>

        {/* Latest hash + SSE pulse indicator */}
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'flex-end',
          gap: 2,
          minWidth: 180,
        }}>
          <span style={{
            fontFamily: FONTS.mono,
            fontSize: 8,
            letterSpacing: '0.06em',
            color: 'var(--vapi-tier-basic)',
            opacity: 0.6,
          }}>
            HEAD HASH
          </span>
          <span style={{
            fontFamily: FONTS.mono,
            fontSize: 9,
            color: ribbonColor,
            letterSpacing: '0.04em',
          }}>
            {latestHash ? `${latestHash.slice(0, 6)}…${latestHash.slice(-10)}` : '—'}
          </span>
        </div>
      </div>

      {/* Thin progress bar below the dots */}
      <div style={{
        marginTop: 8,
        height: 2,
        background: 'rgba(34,211,238,0.10)',
        borderRadius: 1,
        overflow: 'hidden',
      }}>
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${progressPct}%` }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
          style={{
            height: '100%',
            background: `linear-gradient(90deg, ${ribbonColor} 0%, ${ribbonColor}aa 100%)`,
            boxShadow: `0 0 6px ${ribbonColor}`,
          }}
        />
      </div>
    </div>
  )
}
