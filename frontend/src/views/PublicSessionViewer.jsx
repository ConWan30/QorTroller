/**
 * Phase O5-PUBLIC-VIEWER — PublicSessionViewer
 *
 * Top-level public route at /session/:commitmentHex. Composes the
 * four public panels (CryptoReplayPanel + AlgorithmCatalog +
 * GicChainTimeline + PoacBodyHasher) into a single page anyone can
 * load to verify a QorTroller session's cryptographic claims independently.
 *
 * Zero auth. Zero operator state. Read-only from /public/* endpoints.
 */
import { useParams, Link } from 'react-router-dom'
import { usePublicSession, usePublicAgentRoots, usePublicProtocolState } from '../api/publicForensic'
import CryptoReplayPanel from '../components/public/CryptoReplayPanel'
import AlgorithmCatalog from '../components/public/AlgorithmCatalog'
import GicChainTimeline from '../components/public/GicChainTimeline'
import PoacBodyHasher from '../components/public/PoacBodyHasher'

const _MONO = 'JetBrains Mono, ui-monospace, monospace'
const _ACCENT = '#f0a868'

function HeaderBanner({ commitmentHex, found }) {
  return (
    <div style={{
      padding:      '16px 24px',
      background:   'rgba(2,4,8,0.9)',
      borderBottom: `1px solid ${_ACCENT}`,
      display:      'flex',
      alignItems:   'center',
      gap:          16,
    }}>
      <Link to="/" style={{ fontFamily: _MONO, fontSize: 11, color: _ACCENT, textDecoration: 'none' }}>
        ← QorTroller
      </Link>
      <div style={{
        fontFamily: _MONO, fontSize: 11, fontWeight: 700, color: _ACCENT,
        letterSpacing: '0.12em', textTransform: 'uppercase',
      }}>
        Forensic Replay-and-Verify
      </div>
      <div style={{ flex: 1 }} />
      <div style={{ fontFamily: _MONO, fontSize: 10, color: '#cc8855' }}>
        session: <code style={{ color: '#ffe8d4' }}>{commitmentHex?.slice(0, 16)}…</code>
      </div>
      <span data-vapi-session-found={String(found)} style={{
        padding:       '2px 8px',
        background:    found ? '#5bd6a31a' : '#d65b781a',
        color:         found ? '#5bd6a3' : '#d65b78',
        border:        `1px solid ${found ? '#5bd6a3' : '#d65b78'}`,
        borderRadius:  4,
        fontFamily:    _MONO,
        fontSize:      10,
        fontWeight:    600,
        letterSpacing: '0.06em',
        textTransform: 'uppercase',
      }}>{found ? 'FOUND' : 'NOT FOUND'}</span>
    </div>
  )
}

function ProtocolStateRow() {
  const { data } = usePublicProtocolState()
  if (!data) return null
  return (
    <div style={{
      padding: '8px 24px',
      fontFamily: _MONO, fontSize: 10, color: '#7a8a9b',
      display: 'flex', gap: 18, flexWrap: 'wrap',
      background: 'rgba(10,14,20,0.6)',
      borderBottom: `1px solid rgba(${_ACCENT}, 0.15)`,
    }}>
      <span>PV-CI: <strong style={{ color: '#ffe8d4' }}>{data.pv_ci_invariants_count}</strong></span>
      <span>VPM artifacts: <strong style={{ color: '#ffe8d4' }}>{data.total_vpm_artifacts}</strong></span>
      <span>MLGA sessions: <strong style={{ color: '#ffe8d4' }}>{data.total_mlga_sessions}</strong></span>
      <span>GIC links: <strong style={{ color: '#ffe8d4' }}>{data.total_grind_chain_links}</strong></span>
      <span>kill-switch: <strong style={{ color: data.kill_switch_paused ? '#5bd6a3' : '#d65b78' }}>{data.kill_switch_paused ? 'PAUSED' : 'LIVE'}</strong></span>
      <span style={{ flex: 1 }} />
      <span style={{ fontStyle: 'italic' }}>chain: IoTeX testnet (4690)</span>
    </div>
  )
}

function AgentRootsPanel() {
  const { data } = usePublicAgentRoots()
  if (!data) return null
  return (
    <div style={{ padding: '12px 24px', fontFamily: _MONO, fontSize: 10, background: 'rgba(2,4,8,0.4)' }}>
      <div style={{ color: _ACCENT, fontWeight: 700, letterSpacing: '0.12em', marginBottom: 6, textTransform: 'uppercase' }}>
        Operator Initiative · on-chain identity surface
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
        {data.agents.map((a, i) => (
          <div key={i} data-vapi-agent-card={a.canonical} style={{
            padding: 8,
            background: 'rgba(10,14,20,0.6)',
            border: '1px solid rgba(122,138,155,0.18)',
            borderRadius: 4,
          }}>
            <div style={{ color: '#5bd6a3', fontWeight: 700 }}>{a.canonical}</div>
            <div style={{ color: '#7a8a9b' }}>agent_id: <code style={{ color: '#ffe8d4' }}>{a.agent_id?.slice(0, 16)}…</code></div>
            <div style={{ color: '#7a8a9b' }}>phase: <code style={{ color: '#ffe8d4' }}>{a.phase}</code></div>
            <div style={{ color: '#7a8a9b' }}>cedar merkle: <code style={{ color: '#ffe8d4' }}>{a.cedar_bundle_merkle?.slice(0, 16)}…</code></div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function PublicSessionViewer() {
  const { commitmentHex } = useParams()
  const { data: session, isLoading, error } = usePublicSession(commitmentHex)

  if (isLoading) {
    return (
      <div style={{ height: '100dvh', background: '#020408', color: '#7a8a9b', fontFamily: _MONO, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        Loading session…
      </div>
    )
  }
  if (error) {
    return (
      <div style={{ height: '100dvh', background: '#020408', color: '#d65b78', fontFamily: _MONO, padding: 24 }}>
        Bridge unreachable: {String(error.message || error)}
      </div>
    )
  }

  const found = Boolean(session?.found)
  const sessionId = session?.mlga?.session_id || 'grind_phase235_v1'

  return (
    <div style={{ height: '100dvh', background: '#020408', color: '#ffe8d4', overflow: 'auto' }}>
      <HeaderBanner commitmentHex={commitmentHex} found={found} />
      <ProtocolStateRow />
      <AgentRootsPanel />

      <div style={{ padding: '16px 24px', display: 'flex', flexDirection: 'column', gap: 16 }}>
        {found ? (
          <>
            <CryptoReplayPanel session={session} />
            <GicChainTimeline grindSessionId={sessionId} />
            <PoacBodyHasher />
            <AlgorithmCatalog />
          </>
        ) : (
          <>
            <div style={{
              padding: 24,
              fontFamily: _MONO,
              fontSize: 12,
              color: '#d65b78',
              border: '1px solid #d65b78',
              borderRadius: 4,
              background: 'rgba(214,91,120,0.05)',
            }}>
              No VPM artifact with commitment_hex <code>{commitmentHex}</code>.
              Check the hash and try again. If the session was emitted by an
              earlier bridge run, the artifact may not have been autonomously
              committed yet.
            </div>
            <AlgorithmCatalog />
          </>
        )}
      </div>
    </div>
  )
}
