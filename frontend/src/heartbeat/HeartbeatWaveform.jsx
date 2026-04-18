import { useRef, useLayoutEffect } from 'react'
import { useHeartbeatStore } from './useHeartbeat'

// 228-byte PoAC biological rhythm waveform
// Scrolling ECG-style: P-wave → QRS complex → T-wave, one beat per merkle anchor
// accent color reflects current view theme

export function HeartbeatWaveform({ accent = '#00d4ff', height = 40, className = '' }) {
  const canvasRef = useRef(null)
  const rafRef    = useRef(null)
  const phaseRef  = useRef(0)
  const beatMs    = useHeartbeatStore((s) => s.lastBeatMs)
  const magnitude = useHeartbeatStore((s) => s.magnitude)

  useLayoutEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')

    // Build one ECG cycle (normalized 0→1 x-axis)
    function ecgY(t) {
      // P-wave: gentle bump 0.05–0.15
      const p = t > 0.05 && t < 0.15
        ? 0.3 * Math.sin(Math.PI * (t - 0.05) / 0.10)
        : 0
      // QRS: sharp spike 0.30–0.42
      let qrs = 0
      if (t > 0.30 && t < 0.34) qrs = -0.2 * (t - 0.30) / 0.04            // Q dip
      else if (t >= 0.34 && t < 0.38) qrs = 1.0 * (t - 0.34) / 0.04       // R rise
      else if (t >= 0.38 && t < 0.42) qrs = 1.0 - 1.2 * (t - 0.38) / 0.04 // R→S fall
      // T-wave: broad bump 0.55–0.75
      const tw = t > 0.55 && t < 0.75
        ? 0.35 * Math.sin(Math.PI * (t - 0.55) / 0.20)
        : 0
      return p + qrs + tw
    }

    const W = canvas.width
    const H = canvas.height
    const SCROLL_SPEED = 1.2 // px per frame

    // Pre-render one full cycle into a lookup table
    const LUT_W = 512
    const lut = new Float32Array(LUT_W)
    for (let i = 0; i < LUT_W; i++) lut[i] = ecgY(i / LUT_W)

    // Scrolling buffer: stores rendered Y values
    const buf = new Float32Array(W).fill(0)
    let lutPos = 0
    let framesSinceBeat = 0

    function draw() {
      framesSinceBeat++

      // Advance scrolling buffer
      buf.copyWithin(0, 1)
      const lutIdx = Math.floor(lutPos % LUT_W)
      buf[W - 1] = lut[lutIdx] * magnitude
      lutPos = (lutPos + LUT_W / (W * 0.8)) % LUT_W

      ctx.clearRect(0, 0, W, H)

      // Dark background
      ctx.fillStyle = 'rgba(2,4,8,0.92)'
      ctx.fillRect(0, 0, W, H)

      // Faint grid lines
      ctx.strokeStyle = 'rgba(255,255,255,0.04)'
      ctx.lineWidth = 0.5
      for (let x = 0; x < W; x += 40) {
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke()
      }
      ctx.beginPath(); ctx.moveTo(0, H / 2); ctx.lineTo(W, H / 2); ctx.stroke()

      // Waveform glow pass (wide)
      ctx.save()
      ctx.shadowColor = accent
      ctx.shadowBlur  = 8
      ctx.strokeStyle = accent + '55'
      ctx.lineWidth   = 2
      ctx.beginPath()
      for (let x = 0; x < W; x++) {
        const y = H / 2 - buf[x] * H * 0.38
        x === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
      }
      ctx.stroke()
      ctx.restore()

      // Waveform sharp pass (narrow)
      ctx.save()
      ctx.shadowColor = accent
      ctx.shadowBlur  = 4
      ctx.strokeStyle = accent
      ctx.lineWidth   = 1.2
      ctx.beginPath()
      for (let x = 0; x < W; x++) {
        const y = H / 2 - buf[x] * H * 0.38
        x === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
      }
      ctx.stroke()
      ctx.restore()

      // Trailing head highlight
      const headX = W - 4
      const headY = H / 2 - buf[W - 1] * H * 0.38
      ctx.save()
      ctx.shadowColor = '#ffffff'
      ctx.shadowBlur  = 6
      ctx.fillStyle   = '#ffffff'
      ctx.beginPath()
      ctx.arc(headX, headY, 1.5, 0, Math.PI * 2)
      ctx.fill()
      ctx.restore()

      rafRef.current = requestAnimationFrame(draw)
    }

    rafRef.current = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(rafRef.current)
  }, [accent, magnitude])

  return (
    <canvas
      ref={canvasRef}
      width={600}
      height={height}
      className={className}
      style={{ width: '100%', height, display: 'block' }}
    />
  )
}
