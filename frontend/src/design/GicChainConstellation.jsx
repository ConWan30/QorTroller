/* GIC Chain Constellation — the grind-integrity chain rendered as a living
 * orb-web around the 3D controller, instead of the bottom ribbon.
 *
 * 100 orbs sit in concentric rings (a halo around the controller, center kept
 * clear). Orbs 1..chain_length glow chain-green and are joined in order by a
 * continuous chain line — the GIC chain literally wrapping the gamer's
 * controller; the freshest link pulses + pops when a new link lands. Pending
 * orbs (not yet stamped) twinkle faintly — "disappearing and reappearing".
 * Faint nearest-neighbour cross-links weave the web.
 *
 * HONESTY: the count of lit orbs is the REAL polled chain_length (never
 * simulated — same data the eyebrow + Latest-GIC panel show). Paused tints the
 * chain amber; a bridge outage tints it red. The twinkle is the "alive" signal,
 * decoration of real state — not fabricated progress. Honors reduced-motion.
 *
 * Canvas overlay (z2): above the twin iframe, below the corner panels. It never
 * draws a controller — it composes around the reserved twin rectangle.
 */
import { useEffect, useMemo, useRef } from 'react'

const prefersReducedMotion = () =>
  typeof matchMedia !== 'undefined' &&
  matchMedia('(prefers-reduced-motion: reduce)').matches

export function GicChainConstellation({ chainLen = 0, target = 100, paused = false, bridgeDown = false, accent = '#5bd6a3' }) {
  const canvasRef = useRef(null)
  const rafRef = useRef(0)
  const orbsRef = useRef([])
  const stateRef = useRef({ chainLen, target, paused, bridgeDown })
  const landRef = useRef({ prevFilled: 0, at: 0 })
  const reduced = useMemo(prefersReducedMotion, [])

  useEffect(() => { stateRef.current = { chainLen, target, paused, bridgeDown } },
    [chainLen, target, paused, bridgeDown])

  useEffect(() => {
    const c = canvasRef.current
    if (!c) return undefined
    const ctx = c.getContext('2d')
    const N = 100
    const PER_RING = 34
    let w = 0, h = 0, cx = 0, cy = 0, dpr = 1

    const resize = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 2)
      const r = c.getBoundingClientRect()
      w = r.width; h = r.height
      c.width = Math.max(1, Math.round(w * dpr))
      c.height = Math.max(1, Math.round(h * dpr))
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      cx = w / 2
      cy = h * 0.46 // centred on the controller (a touch above middle)
    }
    resize()
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(resize) : null
    if (ro) ro.observe(c); else window.addEventListener('resize', resize)

    // Orbs laid out sequentially within 3 concentric rings so consecutive
    // chain indices are neighbours → the chain line reads as a wrapping spiral.
    orbsRef.current = Array.from({ length: N }, (_, i) => {
      const ring = Math.floor(i / PER_RING)
      const idx = i % PER_RING
      return {
        i,
        ring,
        baseAngle: (idx / PER_RING) * Math.PI * 2 + ring * 0.5,
        dir: ring % 2 === 0 ? 1 : -1,
        rFrac: 0.30 + ring * 0.072,
        bobPhase: Math.random() * Math.PI * 2,
        bobAmp: 0.010 + Math.random() * 0.016,
        twPhase: Math.random() * Math.PI * 2,
        twSpeed: 0.5 + Math.random() * 0.9,
        rot: 0,
      }
    })

    let t0 = performance.now()

    const draw = (now) => {
      const dt = Math.min(0.05, (now - t0) / 1000); t0 = now
      const time = now / 1000
      const st = stateRef.current
      const tgt = st.target || 100
      const filled = Math.max(0, Math.min(N, Math.round((st.chainLen / (tgt || 100)) * N)))

      // land-pop bookkeeping
      if (filled > landRef.current.prevFilled) landRef.current.at = now
      landRef.current.prevFilled = filled
      const sinceLand = now - landRef.current.at
      const popping = sinceLand < 650

      const minWH = Math.min(w, h)
      const chainColor = st.bridgeDown ? '#d65b78' : st.paused ? '#f0a868' : accent

      ctx.clearRect(0, 0, w, h)

      // positions (orb order === chain order)
      const P = orbsRef.current
      for (const o of P) {
        if (!reduced) o.rot += o.dir * (0.05 + o.ring * 0.015) * dt
        const bob = reduced ? 0 : Math.sin(time * 0.6 + o.bobPhase) * o.bobAmp
        const R = (o.rFrac + bob) * minWH
        const a = o.baseAngle + o.rot
        o.x = cx + Math.cos(a) * R
        o.y = cy + Math.sin(a) * R * 0.64 // ellipse — flatter halo
      }

      // ── web: faint nearest-neighbour cross-links ──
      const maxD = minWH * 0.11
      const maxD2 = maxD * maxD
      ctx.lineWidth = 1
      for (let a = 0; a < N; a++) {
        for (let b = a + 1; b < N; b++) {
          const dx = P[a].x - P[b].x, dy = P[a].y - P[b].y
          const d2 = dx * dx + dy * dy
          if (d2 < maxD2) {
            const f = 1 - Math.sqrt(d2) / maxD
            const both = a < filled && b < filled
            ctx.strokeStyle = both
              ? `rgba(91,214,163,${(f * 0.22).toFixed(3)})`
              : `rgba(91,214,163,${(f * 0.06).toFixed(3)})`
            ctx.beginPath(); ctx.moveTo(P[a].x, P[a].y); ctx.lineTo(P[b].x, P[b].y); ctx.stroke()
          }
        }
      }

      // ── the chain itself: continuous line through landed orbs in order ──
      if (filled > 1) {
        ctx.lineWidth = 1.5
        ctx.strokeStyle = chainColor
        ctx.globalAlpha = 0.55
        ctx.beginPath()
        ctx.moveTo(P[0].x, P[0].y)
        for (let i = 1; i < filled; i++) ctx.lineTo(P[i].x, P[i].y)
        ctx.stroke()
        ctx.globalAlpha = 1
      }

      // ── orbs ──
      for (let i = 0; i < N; i++) {
        const o = P[i]
        const landed = i < filled
        const isLatest = i === filled - 1
        const tw = reduced ? 1 : 0.55 + 0.45 * Math.sin(time * o.twSpeed + o.twPhase)
        let color, r, glow, alpha
        if (landed) {
          color = chainColor
          if (isLatest) {
            const pop = popping ? 1 + (1 - sinceLand / 650) * 1.4 : 1
            r = 3.2 * pop; glow = 16 * pop; alpha = 1
          } else {
            r = 2.1; glow = 6; alpha = 0.6 + 0.4 * tw
          }
        } else {
          color = '#5a6675'; r = 1.5; glow = 0; alpha = 0.16 + 0.14 * tw
        }
        ctx.globalAlpha = alpha
        ctx.shadowBlur = glow
        ctx.shadowColor = glow ? color : 'transparent'
        ctx.fillStyle = color
        ctx.beginPath(); ctx.arc(o.x, o.y, r, 0, Math.PI * 2); ctx.fill()
        // latest gets an expanding shockwave ring on land
        if (isLatest && popping) {
          ctx.shadowBlur = 0
          ctx.globalAlpha = (1 - sinceLand / 650) * 0.6
          ctx.strokeStyle = color
          ctx.lineWidth = 1.2
          ctx.beginPath(); ctx.arc(o.x, o.y, r + (sinceLand / 650) * 26, 0, Math.PI * 2); ctx.stroke()
        }
      }
      ctx.globalAlpha = 1; ctx.shadowBlur = 0

      rafRef.current = requestAnimationFrame(draw)
    }
    rafRef.current = requestAnimationFrame(draw)

    return () => {
      cancelAnimationFrame(rafRef.current)
      if (ro) ro.disconnect(); else window.removeEventListener('resize', resize)
    }
  }, [accent, reduced])

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', zIndex: 2, pointerEvents: 'none' }}
    />
  )
}
