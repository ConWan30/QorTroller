// Verified Replay Card — proof-bytes-derived foil gradient.
//
// The visual IS the proof: a different proof produces a different foil.
// You cannot fake the card without faking the underlying proof bytes.
//
// We compute (deterministically) two values from the proof_token hash:
//   • angle      — gradient rotation, 0-360°
//   • shimmer_dx — center-shift on hover, derived from byte deltas
//
// CSS conic-gradient on a positioned span; transform shifts on hover.
// No canvas, no WebGL — keeps the embed lightweight enough for OBS
// browser sources at 60fps without GPU pressure.

import { useMemo } from 'react'

function bytesFromHexLike(s) {
  if (!s) return new Uint8Array(0)
  const h = s.startsWith('0x') ? s.slice(2) : s
  const clean = h.replace(/[^0-9a-fA-F]/g, '')
  if (clean.length < 2) return new Uint8Array(0)
  const out = new Uint8Array(Math.floor(clean.length / 2))
  for (let i = 0; i < out.length; i++) {
    out[i] = parseInt(clean.substr(i * 2, 2), 16)
  }
  return out
}

function paletteFromBytes(bytes) {
  // Three accent colors derived from the proof, biased toward
  // chain-green and amber so the foil stays in-brand. Hue rotation
  // pulls each color into a different segment of the wheel.
  if (bytes.length < 6) {
    return ['#5bd6a3', '#f0a868', '#00d4ff']
  }
  const h1 = (bytes[0] / 255) * 80 + 130   // 130-210 (chain green region)
  const h2 = (bytes[1] / 255) * 50 + 25    // 25-75 (amber region)
  const h3 = (bytes[2] / 255) * 60 + 170   // 170-230 (cyan region)
  return [
    `hsl(${h1.toFixed(0)}, 65%, 62%)`,
    `hsl(${h2.toFixed(0)}, 75%, 65%)`,
    `hsl(${h3.toFixed(0)}, 60%, 58%)`,
  ]
}

export function ProofFoil({ proofToken, intensity = 1.0, children }) {
  const { angle, palette, shimmerDx } = useMemo(() => {
    const bytes = bytesFromHexLike(proofToken || '')
    const angle = bytes.length > 0 ? (bytes[Math.min(3, bytes.length - 1)] / 255) * 360 : 137
    const palette = paletteFromBytes(bytes)
    const shimmerDx = bytes.length > 5 ? ((bytes[5] / 255) * 12) - 6 : 0
    return { angle, palette, shimmerDx }
  }, [proofToken])

  const opacityBase = 0.22 * intensity
  const opacityHover = 0.45 * intensity

  return (
    <div
      className="proof-foil-frame"
      style={{
        position: 'relative',
        borderRadius: 12,
        overflow: 'hidden',
        '--foil-angle': `${angle}deg`,
        '--foil-shimmer-dx': `${shimmerDx}px`,
        '--foil-c1': palette[0],
        '--foil-c2': palette[1],
        '--foil-c3': palette[2],
        '--foil-opacity-base': opacityBase,
        '--foil-opacity-hover': opacityHover,
      }}
    >
      {/* foil layer — sits BEHIND content, blends in */}
      <span
        aria-hidden="true"
        style={{
          position: 'absolute',
          inset: 0,
          background: `conic-gradient(from var(--foil-angle), var(--foil-c1), var(--foil-c2), var(--foil-c3), var(--foil-c1))`,
          opacity: opacityBase,
          mixBlendMode: 'screen',
          filter: 'blur(28px)',
          transform: `translateX(var(--foil-shimmer-dx))`,
          transition: 'opacity 0.5s cubic-bezier(.2,.6,.2,1), transform 0.7s cubic-bezier(.2,.6,.2,1)',
          pointerEvents: 'none',
        }}
        className="proof-foil-layer"
      />
      {/* shimmer overlay — finer diagonal grain on top */}
      <span
        aria-hidden="true"
        style={{
          position: 'absolute',
          inset: 0,
          background: `linear-gradient(calc(var(--foil-angle) + 60deg), transparent 0%, rgba(255,255,255,0.05) 45%, rgba(255,255,255,0.12) 50%, rgba(255,255,255,0.05) 55%, transparent 100%)`,
          mixBlendMode: 'overlay',
          opacity: 0.4,
          pointerEvents: 'none',
        }}
      />
      {/* content */}
      <div style={{ position: 'relative', zIndex: 1 }}>{children}</div>
      <style>{`
        .proof-foil-frame:hover .proof-foil-layer {
          opacity: var(--foil-opacity-hover) !important;
          transform: translateX(calc(var(--foil-shimmer-dx) * -1)) !important;
        }
      `}</style>
    </div>
  )
}
