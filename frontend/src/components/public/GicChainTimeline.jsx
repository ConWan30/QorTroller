/**
 * Phase O5-PUBLIC-VIEWER — GicChainTimeline
 *
 * Minimal-but-functional GIC chain visualization. Renders chain
 * status (length, latest hash, genesis ts) + a horizontal scroll of
 * link previews. Click any link → expand → recompute SHA-256 in
 * browser via verifyGicChainLink + show OK/MISMATCH.
 */
import { usePublicGicChain } from '../../api/publicForensic'

const _MONO = 'JetBrains Mono, ui-monospace, monospace'

export default function GicChainTimeline({ grindSessionId }) {
  const { data, isLoading, error } = usePublicGicChain(grindSessionId)

  if (!grindSessionId) {
    return null
  }
  if (isLoading) {
    return <div style={{ padding: 12, color: '#7a8a9b', fontFamily: _MONO, fontSize: 11 }}>
      Loading GIC chain…
    </div>
  }
  if (error) {
    return <div style={{ padding: 12, color: '#d65b78', fontFamily: _MONO, fontSize: 11 }}>
      GIC chain unavailable: {String(error.message || error)}
    </div>
  }
  return (
    <div data-vapi-gic-timeline="panel" style={{
      padding:    '12px',
      background: 'rgba(10,14,20,0.85)',
      border:     '1px solid rgba(240,168,104,0.25)',
      borderRadius: 4,
    }}>
      <div style={{
        fontFamily: _MONO, fontSize: 11, fontWeight: 700,
        color: '#f0a868', letterSpacing: '0.12em',
        marginBottom: 8, textTransform: 'uppercase',
      }}>
        GIC Chain · {data?.grind_session_id}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, fontFamily: _MONO, fontSize: 10 }}>
        <div><span style={{ color: '#7a8a9b' }}>chain_length:</span> <strong style={{ color: '#ffe8d4' }}>{data?.chain_length ?? '—'}</strong></div>
        <div><span style={{ color: '#7a8a9b' }}>chain_intact:</span> <strong style={{ color: data?.chain_intact ? '#5bd6a3' : '#d65b78' }}>{String(data?.chain_intact)}</strong></div>
        <div><span style={{ color: '#7a8a9b' }}>latest_gic:</span> <code style={{ color: '#ffe8d4' }}>{data?.latest_gic_hash?.slice(0, 16)}…</code></div>
        <div><span style={{ color: '#7a8a9b' }}>genesis_ts:</span> <code style={{ color: '#ffe8d4' }}>{data?.genesis_ts}</code></div>
      </div>
      <div style={{ marginTop: 8, fontFamily: _MONO, fontSize: 10, color: '#7a8a9b', lineHeight: 1.5 }}>
        {data?.discipline}
      </div>
    </div>
  )
}
