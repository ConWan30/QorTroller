/**
 * Phase O5-PUBLIC-VIEWER Stage 4 — VHP Credential Card
 *
 * Public route at /vhp/:tokenId. Renders a soulbound Verified Human
 * Proof credential as a card embedding cert_level + expires_at
 * countdown + linked device_id + consecutive_clean grind streak. The
 * strategic target is streamer/sponsor embed: a streamer can link to
 * /vhp/<tokenId> to demonstrate VAPI-verified human gameplay history.
 */
import { Link, useParams } from 'react-router-dom'
import { usePublicVhp } from '../api/publicForensic'

const _MONO = 'JetBrains Mono, ui-monospace, monospace'
const _ACCENT = '#f0a868'

function StatBlock({ label, value, accent = '#ffe8d4' }) {
  return (
    <div style={{ padding: 12, background: 'rgba(10,14,20,0.6)', border: '1px solid rgba(122,138,155,0.18)', borderRadius: 4 }}>
      <div style={{ fontFamily: _MONO, fontSize: 9, color: '#7a8a9b', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 4 }}>
        {label}
      </div>
      <div style={{ fontFamily: _MONO, fontSize: 14, fontWeight: 700, color: accent }}>
        {value}
      </div>
    </div>
  )
}

function formatDuration(seconds) {
  if (!seconds || seconds <= 0) return 'expired'
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  return d > 0 ? `${d}d ${h}h` : `${h}h ${Math.floor((seconds % 3600) / 60)}m`
}

export default function VhpCredentialView() {
  const { tokenId } = useParams()
  const { data, isLoading, error } = usePublicVhp(parseInt(tokenId, 10))

  return (
    <div style={{ minHeight: '100dvh', background: '#020408', color: '#ffe8d4', overflow: 'auto' }}>
      <div style={{
        padding: '16px 24px', background: 'rgba(2,4,8,0.9)',
        borderBottom: `1px solid ${_ACCENT}`, display: 'flex', gap: 16, alignItems: 'center',
      }}>
        <Link to="/" style={{ fontFamily: _MONO, fontSize: 11, color: _ACCENT, textDecoration: 'none' }}>← VAPI</Link>
        <div style={{ fontFamily: _MONO, fontSize: 11, fontWeight: 700, color: _ACCENT, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
          Verified Human Proof
        </div>
        <div style={{ flex: 1 }} />
        <div style={{ fontFamily: _MONO, fontSize: 10, color: '#cc8855' }}>
          tokenId: <strong style={{ color: '#ffe8d4' }}>#{tokenId}</strong>
        </div>
      </div>

      <div style={{ padding: '24px' }}>
        {isLoading && <div style={{ fontFamily: _MONO, color: '#7a8a9b' }}>Loading credential…</div>}
        {error && <div style={{ fontFamily: _MONO, color: '#d65b78' }}>{String(error.message || error)}</div>}
        {data && !data.found && (
          <div style={{ padding: 24, border: '1px solid #d65b78', borderRadius: 4, fontFamily: _MONO, color: '#d65b78', background: 'rgba(214,91,120,0.05)' }}>
            No VHP credential exists for tokenId #{tokenId}. Try tokenId #2 (Phase 99 demo
            mint to the bridge wallet binding DualShock Edge CFI-ZCP1).
          </div>
        )}
        {data?.found && (
          <>
            {/* Credential card */}
            <div data-vapi-vhp-card style={{
              padding: 24,
              background: 'linear-gradient(135deg, rgba(91,214,163,0.08) 0%, rgba(240,168,104,0.05) 100%)',
              border: `2px solid ${data.vhp.is_valid_local ? '#5bd6a3' : '#d65b78'}`,
              borderRadius: 8,
              marginBottom: 18,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
                <div>
                  <div style={{ fontFamily: _MONO, fontSize: 9, color: '#7a8a9b', letterSpacing: '0.16em' }}>
                    VAPI · VERIFIED HUMAN PROOF
                  </div>
                  <div style={{ fontFamily: _MONO, fontSize: 22, fontWeight: 700, color: '#ffe8d4', marginTop: 6 }}>
                    #{data.vhp.token_id}
                  </div>
                  <div style={{ fontFamily: _MONO, fontSize: 11, color: '#cc8855', marginTop: 4 }}>
                    Soulbound · ERC-4671 · cert_level {data.vhp.cert_level}
                  </div>
                </div>
                <span style={{
                  padding: '6px 14px',
                  background:    data.vhp.is_valid_local ? '#5bd6a31a' : '#d65b781a',
                  color:         data.vhp.is_valid_local ? '#5bd6a3' : '#d65b78',
                  border:        `1px solid ${data.vhp.is_valid_local ? '#5bd6a3' : '#d65b78'}`,
                  borderRadius:  4,
                  fontFamily:    _MONO,
                  fontSize:      12,
                  fontWeight:    700,
                  letterSpacing: '0.12em',
                  textTransform: 'uppercase',
                }}>{data.vhp.is_valid_local ? 'Valid' : 'Expired'}</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10 }}>
                <StatBlock label="Cert Level" value={data.vhp.cert_level === 1 ? 'TIER 1 — CONTROLLER' : data.vhp.cert_level === 2 ? 'TIER 2 — + GSR' : `level ${data.vhp.cert_level}`} accent="#5bd6a3" />
                <StatBlock label="Consecutive Clean" value={data.vhp.consecutive_clean} accent="#f0a868" />
                <StatBlock label="Time to Expiry" value={formatDuration(data.vhp.seconds_until_expiry)} />
                <StatBlock label="Device" value={String(data.vhp.device_id).slice(0, 18) + '…'} accent="#cc8855" />
              </div>
              <div style={{ marginTop: 14, padding: 10, background: 'rgba(2,4,8,0.5)', borderRadius: 4, fontFamily: _MONO, fontSize: 10, color: '#7a8a9b' }}>
                <div>tx_hash:    <code style={{ color: '#ffe8d4' }}>{data.vhp.tx_hash || '(no on-chain record)'}</code></div>
                <div>to_address: <code style={{ color: '#ffe8d4' }}>{data.vhp.to_address || '—'}</code></div>
                <div>expires_at: <code style={{ color: '#ffe8d4' }}>{new Date((data.vhp.expires_at || 0) * 1000).toISOString()}</code></div>
              </div>
            </div>

            {/* Chain metadata */}
            <div style={{ padding: 14, background: 'rgba(10,14,20,0.85)', border: '1px solid rgba(240,168,104,0.25)', borderRadius: 4, marginBottom: 18 }}>
              <div style={{ fontFamily: _MONO, fontSize: 10, fontWeight: 700, color: _ACCENT, letterSpacing: '0.12em', marginBottom: 6, textTransform: 'uppercase' }}>
                On-Chain Identity
              </div>
              <div style={{ fontFamily: _MONO, fontSize: 10, color: '#cc8855' }}>
                chain: <strong style={{ color: '#ffe8d4' }}>{data.chain.name}</strong> · chain_id <strong style={{ color: '#ffe8d4' }}>{data.chain.chain_id}</strong> · network <strong style={{ color: '#ffe8d4' }}>{data.chain.network}</strong>
              </div>
              <div style={{ fontFamily: _MONO, fontSize: 10, color: '#cc8855', marginTop: 4 }}>
                contract: <code style={{ color: '#ffe8d4' }}>{data.chain.contract || '(not configured)'}</code>
              </div>
            </div>

            {/* Discipline footer */}
            <div style={{ padding: 14, background: 'rgba(2,4,8,0.6)', border: '1px solid rgba(122,138,155,0.12)', borderRadius: 4, fontFamily: _MONO, fontSize: 10, color: '#7a8a9b', lineHeight: 1.6, fontStyle: 'italic' }}>
              {data.discipline}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
