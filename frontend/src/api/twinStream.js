/**
 * Phase 238 Step I-AUTOLOOP-3 — useTwinStream() SSE consumer hook.
 *
 * Subscribes to GET /operator/agent/twin-stream EventSource emitted from
 * ProtocolStateCache.  Frontend consumers use this to drive Twin
 * controller animations + tier badge pulses + Operator-bar status
 * updates with real backend events (not animation theater).
 *
 * Wire contract LOCKED — event types match
 * bridge/vapi_bridge/protocol_state_cache.py FROZEN_EVENT_TYPES exactly.
 *
 * Event types delivered:
 *   poac_chain_link    { hash16, ts_ns }
 *   gic_verdict        { verdict, severity, ts_ns }
 *   pcc_state_change   { capture_state, host_state, ts_ns }
 *   curator_verdict    { commitment16, verdict, severity, ts_ns }
 *   anchor_confirmed   { tx_hash, primitive_type, ts_ns }
 *   heartbeat          { ts_ns }
 *
 * Usage:
 *   const lastEvent = useTwinStream({ filter: ['curator_verdict'] })
 *   useEffect(() => {
 *     if (lastEvent?.type === 'curator_verdict' &&
 *         lastEvent.data.verdict === 'APPROVED') {
 *       // trigger cyan pulse on Twin
 *     }
 *   }, [lastEvent])
 *
 * noMock invariant: SSE never falls back to fabricated events. If the
 * bridge is unreachable, the hook returns connected=false; UI must
 * render a "stream offline" indicator rather than fake events.
 */
import { useEffect, useState, useRef } from 'react'

const BASE_URL = import.meta.env.VITE_BRIDGE_URL || 'http://localhost:8765'
const API_KEY  = import.meta.env.VITE_VAPI_API_KEY || ''

const FROZEN_EVENT_TYPES = new Set([
  'poac_chain_link',
  'gic_verdict',
  'pcc_state_change',
  'curator_verdict',
  'anchor_confirmed',
  'heartbeat',
])

export function useTwinStream({ filter = null, backfill = 0 } = {}) {
  const [lastEvent, setLastEvent] = useState(null)
  const [connected, setConnected] = useState(false)
  const [eventCounts, setEventCounts] = useState({})
  const esRef = useRef(null)

  useEffect(() => {
    // EventSource doesn't support custom headers — pass api_key via query string.
    // Bridge SSE endpoint accepts x-api-key header; we work around by hitting
    // a wrapper or accepting that local dev uses no auth. For now, rely on
    // BRIDGE_URL with cookie or trust local-loopback.
    const url = new URL(`${BASE_URL}/operator/agent/twin-stream`)
    if (backfill > 0) url.searchParams.set('backfill', String(backfill))
    if (API_KEY) url.searchParams.set('api_key', API_KEY)

    let es
    try {
      es = new EventSource(url.toString())
      esRef.current = es
    } catch (err) {
      setConnected(false)
      return () => {}
    }

    es.onopen = () => setConnected(true)
    es.onerror = () => setConnected(false)

    const onEvent = (eventType) => (msg) => {
      if (!FROZEN_EVENT_TYPES.has(eventType)) return  // defensive
      if (filter && !filter.includes(eventType)) return
      try {
        const data = JSON.parse(msg.data)
        setLastEvent({ type: eventType, data, t: Date.now() })
        setEventCounts((counts) => ({
          ...counts,
          [eventType]: (counts[eventType] || 0) + 1,
        }))
      } catch (_) {
        // malformed — ignore (never fake events)
      }
    }

    // Register listeners for each FROZEN event type
    for (const et of FROZEN_EVENT_TYPES) {
      es.addEventListener(et, onEvent(et))
    }

    return () => {
      try { es.close() } catch (_) {}
      esRef.current = null
      setConnected(false)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [backfill, filter ? filter.join(',') : ''])

  return { lastEvent, connected, eventCounts }
}
