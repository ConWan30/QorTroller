/**
 * Poll CLI-written ~/.qortroller/ui JSON via Vite /stream-ui middleware.
 * noMock: missing → UNKNOWN empties; never fabricates LIVE.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  DEFAULT_STREAM_UI_BASE,
  loadStreamSnapshots,
  emptyStreamModel,
  emptyStatusSnapshot,
  emptyCeremonyMap,
  emptyReceiptReveal,
  classifyStreamSurfaceMode,
} from './loadLocalSnapshot'

const POLL_MS = 3000

export function useStreamSnapshots({
  baseUrl = DEFAULT_STREAM_UI_BASE,
  pollMs = POLL_MS,
  /** Injected snapshots for tests (skips network). */
  initial = null,
  fetchImpl = undefined,
  enabled = true,
} = {}) {
  const [data, setData] = useState(() => initial || {
    stream: emptyStreamModel('boot'),
    status: emptyStatusSnapshot('boot'),
    ceremony: emptyCeremonyMap('boot'),
    receipt: emptyReceiptReveal('boot'),
  })
  const [loading, setLoading] = useState(!initial)
  const [error, setError] = useState(null)
  const alive = useRef(true)

  const refresh = useCallback(async () => {
    if (!enabled) return
    try {
      const next = await loadStreamSnapshots(baseUrl, fetchImpl ?? globalThis.fetch)
      if (!alive.current) return
      setData(next)
      setError(null)
    } catch (e) {
      if (!alive.current) return
      // Fail-open to UNKNOWN — never LIVE
      setData({
        stream: emptyStreamModel('error'),
        status: emptyStatusSnapshot('error'),
        ceremony: emptyCeremonyMap('error'),
        receipt: emptyReceiptReveal('error'),
      })
      setError(e?.message || 'load failed')
    } finally {
      if (alive.current) setLoading(false)
    }
  }, [baseUrl, enabled, fetchImpl])

  useEffect(() => {
    alive.current = true
    if (initial) {
      setLoading(false)
      return undefined
    }
    refresh()
    if (!pollMs || pollMs <= 0) return () => { alive.current = false }
    const id = setInterval(refresh, pollMs)
    return () => {
      alive.current = false
      clearInterval(id)
    }
  }, [refresh, pollMs, initial])

  const mode = classifyStreamSurfaceMode(data)

  return {
    ...data,
    mode,
    loading,
    error,
    refresh,
    mock: false,
    fabricated_liveness: false,
  }
}

export default useStreamSnapshots
