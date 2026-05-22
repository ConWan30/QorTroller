/* useRealityHeartbeat (v2 design pass · item D) — the "alive" signal.
 *
 * One module-level beat, fired by the data layer whenever ANY bridge query
 * succeeds (wired once in main.jsx to the react-query cache). Every surface
 * subscribes to drive a single chain-green `● LIVE` dot in the strip; when the
 * bridge drops, the dot goes amber and the eyebrow degrades to
 * `BRIDGE UNREACHABLE — last known Ns ago` with no layout shift.
 *
 * Honest by construction: the beat reflects a REAL successful response. It does
 * not distinguish mock data — consumers gate on isMockActive() so a mock feed
 * reads `MOCK`, never a fake `LIVE`. The "unreachable" degrade only shows after
 * at least one real beat (lastBeatAt > 0); before that it's just connecting.
 */
import { useEffect, useState } from 'react'
import { isMockActive } from '../api/mockBridge'

let lastBeatAt = 0
const listeners = new Set()

/** Record a successful bridge response. Called from the react-query cache
 *  subscription in main.jsx; safe to call from anywhere. */
export function markReality(ts = Date.now()) {
  lastBeatAt = typeof ts === 'number' && ts > 0 ? ts : Date.now()
  for (const l of listeners) l(lastBeatAt)
}

export function getLastBeat() {
  return lastBeatAt
}

export function subscribeReality(fn) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

/* Subscribe a component to the heartbeat. Re-renders on each beat AND once a
   second so `sinceMs` / `alive` stay current between beats. */
export function useRealityHeartbeat({ staleMs = 15000 } = {}) {
  const [, force] = useState(0)
  useEffect(() => {
    const unsub = subscribeReality(() => force((n) => n + 1))
    const t = setInterval(() => force((n) => n + 1), 1000)
    return () => { unsub(); clearInterval(t) }
  }, [])
  const last = lastBeatAt
  const sinceMs = last ? Date.now() - last : Infinity
  return {
    alive: last > 0 && sinceMs < staleMs,
    everBeat: last > 0,
    lastBeatAt: last,
    sinceMs,
  }
}

/* "14s ago" / "3m ago" from a millisecond delta. */
export function agoLabel(sinceMs) {
  if (!isFinite(sinceMs)) return '—'
  const s = Math.floor(sinceMs / 1000)
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  return `${Math.floor(s / 3600)}h ago`
}

/* RealityDot — the `● LIVE` strip indicator. Literal-hex (renders outside
   .qt-design-root). Pulses gently while live; honest MOCK / OFFLINE otherwise. */
export function RealityDot() {
  const { alive, everBeat } = useRealityHeartbeat()
  const mock = isMockActive()
  let color, label, pulse
  if (mock) { color = '#f0a868'; label = 'MOCK'; pulse = false }
  else if (alive) { color = '#5bd6a3'; label = 'LIVE'; pulse = true }
  else if (everBeat) { color = '#f0a868'; label = 'OFFLINE'; pulse = false }
  else { color = '#5a6878'; label = '···'; pulse = false }
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      fontFamily: "'JetBrains Mono', ui-monospace, monospace",
      fontSize: 9, letterSpacing: '0.08em', textTransform: 'uppercase',
      color, whiteSpace: 'nowrap',
    }}>
      <span
        className={pulse ? 'qt-live-pulse' : undefined}
        style={{ width: 6, height: 6, borderRadius: '50%', background: color, boxShadow: `0 0 6px ${color}` }}
      />
      {label}
    </span>
  )
}
