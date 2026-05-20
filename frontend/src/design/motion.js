/* Motion — design-system animation primitives, each tied to a REAL event.
 *
 * Ported from the Claude-design export (bundle 5) Motion.jsx, converted from
 * the global-window pattern to an ES module AND hardened for honesty:
 *
 *   - useReDeriveHash : UNCHANGED — real crypto.subtle.digest over real input.
 *   - useRelativeTime : UNCHANGED — relative-time string off a real timestamp.
 *   - useTick         : UNCHANGED — a paused-aware heartbeat counter.
 *   - useChainPulse   : REPLACES the export's useChainAdvance. The export
 *                       SIMULATED chain growth client-side via setInterval —
 *                       which would render a fabricated advancing chain even
 *                       when the real bridge chain is static. That violates the
 *                       noMock honesty contract. useChainPulse instead observes
 *                       the REAL polled chain_length and fires a landing pulse
 *                       only when it actually increases.
 *
 * No decorative motion. Every animation visualizes the protocol computing.
 */
import { useEffect, useRef, useState } from 'react'

/* Heartbeat. Returns an incrementing counter (default every 5 s).
   Paused when `paused` is true. */
export function useTick(intervalMs = 5000, paused = false) {
  const [tick, setTick] = useState(0)
  useEffect(() => {
    if (paused) return undefined
    const t = setInterval(() => setTick((n) => n + 1), intervalMs)
    return () => clearInterval(t)
  }, [intervalMs, paused])
  return tick
}

/* In-browser SHA-256 over `input` (string or ArrayBuffer/TypedArray).
   Returns:
     - hex      : the computed 64-char hex
     - settledAt: timestamp when the latest digest resolved (drives settle anim)
     - state    : 'computing' | 'settled' | 'mismatch' (if compareTo given)
     - duration : ms the last computation took
   When compareTo is supplied, state becomes 'mismatch' iff hex !== compareTo —
   this is the honesty surface: a real re-derivation that visibly disagrees. */
export function useReDeriveHash(input, compareTo) {
  const [hex, setHex] = useState('')
  const [state, setState] = useState('computing')
  const [duration, setDuration] = useState(0)
  const [settledAt, setSettledAt] = useState(0)

  useEffect(() => {
    if (input == null || input === '') {
      setHex('')
      setState('computing')
      return undefined
    }
    let cancelled = false
    setState('computing')
    const started = performance.now()
    const bytes = typeof input === 'string' ? new TextEncoder().encode(input) : input
    crypto.subtle.digest('SHA-256', bytes).then((buf) => {
      if (cancelled) return
      const arr = new Uint8Array(buf)
      const h = Array.from(arr).map((b) => b.toString(16).padStart(2, '0')).join('')
      setHex(h)
      setDuration(Math.round(performance.now() - started))
      setSettledAt(Date.now())
      if (compareTo && h !== compareTo.toLowerCase()) setState('mismatch')
      else setState('settled')
    })
    return () => { cancelled = true }
  }, [typeof input === 'string' ? input : input?.byteLength, compareTo])

  return { hex, state, duration, settledAt }
}

/* Chain pulse — observe a REAL polled chain_length. Whenever it increases,
   stamp landingAt so the freshly-landed link can briefly pulse. Never
   advances the count itself; it only reacts to the bridge's real value. */
export function useChainPulse(realLength) {
  const prevRef = useRef(realLength)
  const [landingAt, setLandingAt] = useState(0)
  useEffect(() => {
    if (typeof realLength === 'number' && realLength > prevRef.current) {
      setLandingAt(Date.now())
    }
    if (typeof realLength === 'number') prevRef.current = realLength
  }, [realLength])
  return { landingAt }
}

/* A controlled relative-time string that updates every second.
   "280 MS AGO" / "4 S AGO" / "—". Tied to a real settledAt timestamp. */
export function useRelativeTime(settledAt) {
  const [, force] = useState(0)
  useEffect(() => {
    const t = setInterval(() => force((n) => n + 1), 1000)
    return () => clearInterval(t)
  }, [])
  if (!settledAt) return '—'
  const ms = Date.now() - settledAt
  if (ms < 1000) return `${Math.max(ms, 1)} MS AGO`
  if (ms < 60_000) return `${Math.floor(ms / 1000)} S AGO`
  return `${Math.floor(ms / 60_000)} M AGO`
}
