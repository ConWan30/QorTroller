/* GIC Chain Constellation — the grind-integrity chain rendered as a living
 * orb-web around the 3D controller.
 *
 * 100 orbs in concentric elliptical rings halo the controller (centre kept
 * clear). Orbs 1..chain_length are landed and joined in order by a continuous
 * chain line that wraps the controller; the freshest link pops when it lands;
 * pending orbs twinkle faintly. Faint nearest-neighbour cross-links weave a web.
 *
 * v2 enhancements — all driven by REAL polled state, never fabricated:
 *  1. VERDICT TEXTURE — each landed orb (and its incoming chain segment) is
 *     coloured by its real GIC verdict: CLEAR/CERTIFY → chain-green, FLAG/HOLD →
 *     amber, BLOCK → red. A CONTESTED / DEGRADED host gets a faint red rim. The
 *     chain shows what it ACTUALLY is, not a uniform green. (links[] from
 *     /gic/{sid}/links, oldest-first → orb i maps to links[i].)
 *  2. PRESENCE BREATHING — the web's motion + glow are coupled to real presence
 *     (capture NOMINAL and not MENU_DETECTED). A human on the controller → the
 *     web breathes and brightens; AFK / menu → it eases to stillness. The "alive"
 *     signal is now the protocol's real presence reading, not Math.random().
 *  3. FRACTURE ON BREAK — chain_intact=false snaps the chain at the head: the
 *     final segment severs (a visible gap) and the head orb cracks red with a
 *     one-shot snap ring. The integrity invariant becomes something you SEE.
 *
 * HONESTY: landed-orb count = real chain_length; colours = real verdicts; motion
 * = real presence; the fracture = the real chain_intact flag. Paused tints amber,
 * a bridge outage tints red (those global states dominate the verdict colours).
 * Honors reduced-motion. When links are absent it degrades to the prior uniform
 * chain-green behaviour.
 *
 * Canvas overlay (z2): above the twin iframe, below the corner panels; never
 * draws a controller — it composes around the reserved twin rectangle.
 */
import { useEffect, useMemo, useRef } from 'react'

const prefersReducedMotion = () =>
  typeof matchMedia !== 'undefined' &&
  matchMedia('(prefers-reduced-motion: reduce)').matches

const CHAIN = '#5bd6a3', AMBER = '#f0a868', RED = '#d65b78'

// verdict_code → colour (frozen mirror of grind_chain.py VERDICT_CODES)
function verdictColor(code) {
  if (code === 0x00 || code === 0x01) return CHAIN // CLEAR / CERTIFY
  if (code === 0x10 || code === 0x11) return AMBER // FLAG / HOLD
  if (code === 0x20) return RED                    // BLOCK
  return null
}
// host_state_code → contested? CONTESTED 0x20 / DEGRADED 0x30 / DISCONNECTED 0xFF
const hostContested = (code) => code === 0x20 || code === 0x30 || code === 0xFF

export function GicChainConstellation({
  chainLen = 0, target = 100, paused = false, bridgeDown = false, accent = '#5bd6a3',
  links = null, present = true, broken = false,
}) {
  const canvasRef = useRef(null)
  const rafRef = useRef(0)
  const orbsRef = useRef([])
  const stateRef = useRef({ chainLen, target, paused, bridgeDown, links, present, broken })
  const landRef = useRef({ prevFilled: 0, at: 0 })
  const presRef = useRef(present ? 1 : 0)   // smoothed presence 0..1 (the "alive" amplitude)
  const breakRef = useRef({ broken: false, at: 0 })
  const reduced = useMemo(prefersReducedMotion, [])

  useEffect(() => {
    stateRef.current = { chainLen, target, paused, bridgeDown, links, present, broken }
  }, [chainLen, target, paused, bridgeDown, links, present, broken])

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

    // Orbs laid out sequentially within 3 concentric rings so consecutive chain
    // indices are neighbours → the chain line reads as a wrapping spiral.
    orbsRef.current = Array.from({ length: N }, (_, i) => {
      const ring = Math.floor(i / PER_RING)
      const idx = i % PER_RING
      return {
        i, ring,
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
      const L = st.links

      // smoothed presence — eased toward 0/1; drives the web's "alive" amplitude
      const presTarget = st.present ? 1 : 0
      presRef.current += (presTarget - presRef.current) * Math.min(1, dt * 2.2)
      const pres = reduced ? 1 : presRef.current

      // land-pop bookkeeping
      if (filled > landRef.current.prevFilled) landRef.current.at = now
      landRef.current.prevFilled = filled
      const sinceLand = now - landRef.current.at
      const popping = sinceLand < 650

      // fracture onset (one-shot snap pulse when chain_intact flips false)
      if (st.broken && !breakRef.current.broken) breakRef.current.at = now
      breakRef.current.broken = !!st.broken
      const sinceBreak = now - breakRef.current.at

      const minWH = Math.min(w, h)
      // global tint: bridge outage (red) or paused (amber) dominates verdict colour
      const baseColor = st.bridgeDown ? RED : st.paused ? AMBER : accent
      const tinted = st.paused || st.bridgeDown

      // per-orb colour: real verdict when links present + not globally tinted
      const orbColor = (i) => {
        if (!tinted && L && i < L.length) {
          const vc = verdictColor(L[i].verdict_code)
          if (vc) return vc
        }
        return baseColor
      }

      ctx.clearRect(0, 0, w, h)

      // positions (orb order === chain order); bob amplitude scales with presence
      const P = orbsRef.current
      for (const o of P) {
        if (!reduced) o.rot += o.dir * (0.05 + o.ring * 0.015) * dt
        const bob = reduced ? 0 : Math.sin(time * 0.6 + o.bobPhase) * o.bobAmp * (0.2 + 0.8 * pres)
        const R = (o.rFrac + bob) * minWH
        const a = o.baseAngle + o.rot
        o.x = cx + Math.cos(a) * R
        o.y = cy + Math.sin(a) * R * 0.64 // ellipse — flatter halo
      }

      // ── web: faint nearest-neighbour cross-links (landed links brighten with presence) ──
      const maxD = minWH * 0.11, maxD2 = maxD * maxD
      ctx.lineWidth = 1
      for (let a = 0; a < N; a++) {
        for (let b = a + 1; b < N; b++) {
          const dx = P[a].x - P[b].x, dy = P[a].y - P[b].y
          const d2 = dx * dx + dy * dy
          if (d2 < maxD2) {
            const f = 1 - Math.sqrt(d2) / maxD
            const both = a < filled && b < filled
            const wf = both ? f * 0.22 * (0.4 + 0.6 * pres) : f * 0.06
            ctx.strokeStyle = `rgba(91,214,163,${wf.toFixed(3)})`
            ctx.beginPath(); ctx.moveTo(P[a].x, P[a].y); ctx.lineTo(P[b].x, P[b].y); ctx.stroke()
          }
        }
      }

      // ── the chain line: per-segment verdict colour through landed orbs ──
      // when broken, the final segment (into the head) is severed → a visible gap.
      const headSegSkip = st.broken && filled > 1 ? filled - 1 : -1
      if (filled > 1) {
        ctx.lineWidth = 1.5
        ctx.globalAlpha = 0.55
        for (let i = 1; i < filled; i++) {
          if (i === headSegSkip) continue // severed gap at the break
          ctx.strokeStyle = orbColor(i)
          ctx.beginPath(); ctx.moveTo(P[i - 1].x, P[i - 1].y); ctx.lineTo(P[i].x, P[i].y); ctx.stroke()
        }
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
          color = orbColor(i)
          if (isLatest) {
            const pop = popping ? 1 + (1 - sinceLand / 650) * 1.4 : 1
            const breathe = 1 + (reduced ? 0 : 0.18 * pres * Math.sin(time * 1.6))
            r = 3.2 * pop * breathe; glow = 16 * pop * (0.5 + 0.5 * pres); alpha = 1
          } else {
            r = 2.1; glow = 6; alpha = 0.55 + 0.45 * (0.3 + 0.7 * pres) * tw
          }
        } else {
          color = '#5a6675'; r = 1.5; glow = 0; alpha = (0.16 + 0.14 * tw) * (0.4 + 0.6 * pres)
        }
        ctx.globalAlpha = alpha
        ctx.shadowBlur = glow
        ctx.shadowColor = glow ? color : 'transparent'
        ctx.fillStyle = color
        ctx.beginPath(); ctx.arc(o.x, o.y, r, 0, Math.PI * 2); ctx.fill()

        // contested / degraded host → faint red rim (honest host-state texture)
        if (landed && !tinted && L && i < L.length && hostContested(L[i].host_state_code)) {
          ctx.shadowBlur = 0; ctx.globalAlpha = 0.5
          ctx.strokeStyle = RED; ctx.lineWidth = 1
          ctx.beginPath(); ctx.arc(o.x, o.y, r + 2.4, 0, Math.PI * 2); ctx.stroke()
        }

        // latest landed: shockwave on land (suppressed when fractured)
        if (isLatest && popping && !st.broken) {
          ctx.shadowBlur = 0; ctx.globalAlpha = (1 - sinceLand / 650) * 0.6
          ctx.strokeStyle = color; ctx.lineWidth = 1.2
          ctx.beginPath(); ctx.arc(o.x, o.y, r + (sinceLand / 650) * 26, 0, Math.PI * 2); ctx.stroke()
        }

        // ── FRACTURE: head orb cracks red when chain_intact === false ──
        if (isLatest && st.broken) {
          ctx.shadowBlur = 12; ctx.shadowColor = RED
          ctx.globalAlpha = 1; ctx.fillStyle = RED
          ctx.beginPath(); ctx.arc(o.x, o.y, 3.6, 0, Math.PI * 2); ctx.fill()
          ctx.shadowBlur = 0
          ctx.strokeStyle = RED; ctx.lineWidth = 1.4; ctx.globalAlpha = 0.9
          ctx.beginPath() // two short diverging crack strokes
          ctx.moveTo(o.x - 9, o.y - 5); ctx.lineTo(o.x, o.y); ctx.lineTo(o.x - 7, o.y + 8)
          ctx.moveTo(o.x, o.y); ctx.lineTo(o.x + 10, o.y + 4)
          ctx.stroke()
          if (sinceBreak < 900) { // one-shot expanding snap ring
            ctx.globalAlpha = (1 - sinceBreak / 900) * 0.7
            ctx.beginPath(); ctx.arc(o.x, o.y, 4 + (sinceBreak / 900) * 34, 0, Math.PI * 2); ctx.stroke()
          }
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
