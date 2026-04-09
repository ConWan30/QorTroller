// src/shared/api/hooks/useWebSocket.js
// WebSocket connection to bridge /ws/records with exponential backoff
// Phase 54 reconnect pattern — never throws, always degrades gracefully

import { useEffect, useRef, useState, useCallback } from 'react'

const WS_URL      = 'ws://localhost:8080/ws/records'
const MAX_RETRIES = 8
const BASE_DELAY  = 500   // ms

export function useWebSocket({ onMessage, enabled = true } = {}) {
  const [status, setStatus]   = useState('disconnected') // connecting | live | disconnected | error
  const [lastMsg, setLastMsg] = useState(null)
  const wsRef       = useRef(null)
  const retries     = useRef(0)
  const timerRef    = useRef(null)
  const enabledRef  = useRef(enabled)
  const onMsgRef    = useRef(onMessage)

  // Keep refs in sync without triggering reconnects
  useEffect(() => { enabledRef.current = enabled },  [enabled])
  useEffect(() => { onMsgRef.current  = onMessage }, [onMessage])

  const connect = useCallback(() => {
    if (!enabledRef.current) return
    setStatus('connecting')

    try {
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => {
        retries.current = 0
        setStatus('live')
      }

      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data)
          setLastMsg(data)
          onMsgRef.current?.(data)
        } catch (_) {}
      }

      ws.onerror = () => {
        setStatus('error')
      }

      ws.onclose = () => {
        setStatus('disconnected')
        // Exponential backoff — Phase 54 pattern
        if (retries.current < MAX_RETRIES && enabledRef.current) {
          const delay = Math.min(BASE_DELAY * 2 ** retries.current, 30_000)
          retries.current += 1
          timerRef.current = setTimeout(connect, delay)
        }
      }
    } catch (_) {
      setStatus('error')
    }
  }, [])  // stable — reads enabled/onMessage via refs

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(timerRef.current)
      wsRef.current?.close()
    }
  }, [connect])

  const reconnect = useCallback(() => {
    clearTimeout(timerRef.current)
    retries.current = 0
    wsRef.current?.close()
    connect()
  }, [connect])

  return { status, lastMsg, reconnect }
}
