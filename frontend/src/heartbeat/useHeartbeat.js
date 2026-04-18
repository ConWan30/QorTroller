import { create } from 'zustand'

// 228-byte PoAC heartbeat shared across all three views
// Filled by HeartbeatProvider from /agent/protocol-coherence-status (3000ms poll)
export const useHeartbeatStore = create((set) => ({
  // latest merkle root (last 8 hex chars = "byte signature")
  merkleRoot:       null,
  // agent count driving the root
  agentCount:       38,
  // whether last anchor was confirmed on-chain
  onChainConfirmed: false,
  // unix ms timestamp of last heartbeat
  lastBeatMs:       null,
  // ring buffer of recent beat timestamps (for waveform)
  beatHistory:      [],
  // pulse magnitude: 0–1 scaled from anchor freshness
  magnitude:        0.5,
  // is mock data active?
  isMock:           false,

  recordBeat: (data, isMock) => set((s) => {
    const now = Date.now()
    const history = [...s.beatHistory, now].slice(-64)
    const fresh = data?.last_anchor_ts
      ? Math.max(0, 1 - (now - new Date(data.last_anchor_ts).getTime()) / 30000)
      : 0.5
    return {
      merkleRoot:       data?.latest_merkle_root ?? s.merkleRoot,
      agentCount:       data?.agent_count ?? s.agentCount,
      onChainConfirmed: data?.on_chain_confirmed ?? s.onChainConfirmed,
      lastBeatMs:       now,
      beatHistory:      history,
      magnitude:        fresh,
      isMock,
    }
  }),
}))
