import { useRef, useEffect } from 'react'

// PROVING GROUND tab strip — ported faithfully from the Claude Design "PG Tab Strip.dc.html"
// (round 1). Forge palette + Archivo wordmark (ember medial-T) + Martian Mono tabs + the steel
// Struck Seal chip (window.PGSeal, loaded globally via index.html). Four destinations; ALL live in
// production — the design's SOON badges on Grant/Partner are a design-preview state (those tabs
// render their not-yet-reskinned bodies until their reskin rounds). Reference is relabelled About.
const PAL = {
  void1: '#0A1120', void2: '#111B2E',
  steel: '#6E8CA8', ember: '#E0743A', ash: '#4A5260', bone: '#E9E2D2',
}
const DISP = "'Archivo', system-ui, sans-serif"
const MONO = "'Martian Mono', ui-monospace, monospace"

// Same four destinations + ids as App.jsx VIEW_MAP. Reference id retained ('reference'); label = About.
const VIEWS = [
  { id: 'gamer',     label: 'Gamer' },
  { id: 'grant',     label: 'IoTeX · Grant' },
  { id: 'partner',   label: 'Partner · Pitch' },
  { id: 'reference', label: 'About' },
]

// The shared Struck Seal, rendered small + resting-steel in the strip (one source of truth:
// window.PGSeal from /pg-seal.js). Mirrors PG Tab Strip's drawChip.
function SealChip() {
  const ref = useRef(null)
  useEffect(() => {
    let raf
    const reduced = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches)
    const loop = (t) => {
      const c = ref.current
      if (c && window.PGSeal) {
        const dpr = window.devicePixelRatio || 1, w = c.clientWidth, h = c.clientHeight
        if (w && h) {
          if (c.width !== Math.round(w * dpr)) { c.width = Math.round(w * dpr); c.height = Math.round(h * dpr) }
          const ctx = c.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, w, h)
          window.PGSeal.drawStruckSeal(ctx, { cx: w / 2, cy: h / 2, R: Math.min(w, h) * 0.34, color: PAL.steel, now: t, motion: !reduced, seed: 0x9f3c2ba3 })
        }
      }
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => { if (raf) cancelAnimationFrame(raf) }
  }, [])
  return <canvas ref={ref} style={{ width: 26, height: 26, display: 'block' }} />
}

export function ViewSelector({ activeView, onViewChange }) {
  return (
    <header style={{
      display: 'flex', alignItems: 'center', gap: 26, height: 56, padding: '0 28px',
      background: 'rgba(6,9,16,.92)', borderBottom: `1px solid ${PAL.void2}`,
      backdropFilter: 'blur(12px)', zIndex: 100, flexShrink: 0,
      minWidth: 0, maxWidth: '100vw', overflow: 'hidden',
    }}>
      {/* wordmark — Archivo (expanded), ember medial-T */}
      <span style={{ fontFamily: DISP, fontStretch: '125%', fontWeight: 800, fontSize: 19, letterSpacing: '-0.01em', color: PAL.bone, whiteSpace: 'nowrap', flexShrink: 0 }}>
        Qor<span style={{ color: PAL.ember }}>T</span>roller
      </span>

      {/* tabs — Martian Mono; active = bone + ember underline, inactive = steel */}
      <nav style={{ display: 'flex', alignItems: 'center', gap: 2, minWidth: 0, overflow: 'hidden' }}>
        {VIEWS.map((v) => {
          const active = v.id === activeView
          return (
            <button
              key={v.id}
              onClick={() => onViewChange(v.id)}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 6,
                fontFamily: MONO, fontSize: 11, fontWeight: 500, letterSpacing: '0.1em',
                textTransform: 'uppercase', color: active ? PAL.bone : PAL.steel,
                background: 'transparent', border: 0,
                borderBottom: `2px solid ${active ? PAL.ember : 'transparent'}`,
                padding: '6px 11px', cursor: 'pointer', whiteSpace: 'nowrap',
                transition: 'color 0.15s ease',
              }}
            >{v.label}</button>
          )
        })}
      </nav>

      {/* right — V.A.P.I. · PROVING GROUND + the resting-steel seal chip */}
      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10, minWidth: 0, flexShrink: 1 }}>
        <span style={{ fontFamily: MONO, fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase', color: PAL.ash, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>V.A.P.I.&nbsp;· PROVING&nbsp;GROUND</span>
        <SealChip />
      </div>
    </header>
  )
}
