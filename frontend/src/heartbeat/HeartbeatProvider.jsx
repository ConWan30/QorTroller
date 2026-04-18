import { useEffect } from 'react'
import { useProtocolCoherence } from '../api/bridgeApi'
import { useHeartbeatStore } from './useHeartbeat'
import { isMockActive } from '../api/mockBridge'

export function HeartbeatProvider({ children }) {
  const { data } = useProtocolCoherence()
  const recordBeat = useHeartbeatStore((s) => s.recordBeat)

  useEffect(() => {
    if (data) recordBeat(data, isMockActive())
  }, [data, recordBeat])

  return children
}
