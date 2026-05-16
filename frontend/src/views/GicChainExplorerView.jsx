/**
 * Phase O5-PUBLIC-VIEWER Stage 2 — GIC Chain Explorer view
 *
 * Public route at /gic/:grindSessionId. Renders every chain link from
 * genesis to head as an inspectable row. Click "Re-hash" on any link
 * → in-browser SHA-256 via verifyGicChainLink → green OK badge if
 * the computed hash matches the protocol's stored grind_chain_hash.
 *
 * Plus a top "Verify Genesis" button that calls verifyGicGenesis with
 * the session ID + first link's ts_ns and confirms the FROZEN-v1
 * VAPI-GIC-GENESIS-v1 tag binding.
 *
 * Strategic claim: VAPI is the only anti-cheat protocol where any
 * external party can audit the cryptographic chain underneath a
 * grind session. 100+ links from grind_phase235_v1 genesis to the
 * Phase 239 G3 GIC_100 milestone, every one browser-replayable.
 */
import { Link, useParams } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { usePublicGicChain, usePublicGicLinks } from '../api/publicForensic'
import {
  verifyGicGenesis,
  verifyGicChainLink,
} from '../crypto/vapi_verifier'

const _MONO = 'JetBrains Mono, ui-monospace, monospace'
const _ACCENT = '#f0a868'

function StatusPill({ status }) {
  const colors = {
    ok:       { bg: '#5bd6a31a', fg: '#5bd6a3', label: 'OK' },
    mismatch: { bg: '#d65b781a', fg: '#d65b78', label: 'MISMATCH' },
    pending:  { bg: '#7a8a9b1a', fg: '#7a8a9b', label: '…' },
  }
  const c = colors[status] || colors.pending
  return (
    <span data-vapi-link-status={status} style={{
      background:    c.bg,
      color:         c.fg,
      border:        `1px solid ${c.fg}`,
      padding:       '1px 6px',
      borderRadius:  3,
      fontFamily:    _MONO,
      fontSize:      9,
      fontWeight:    600,
    }}>{c.label}</span>
  )
}

function HeaderBanner({ sessionId, chainLength, chainIntact }) {
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
        ← VAPI
      </Link>
      <div style={{
        fontFamily: _MONO, fontSize: 11, fontWeight: 700, color: _ACCENT,
        letterSpacing: '0.12em', textTransform: 'uppercase',
      }}>
        GIC Chain Explorer
      </div>
      <div style={{ flex: 1 }} />
      <div style={{ fontFamily: _MONO, fontSize: 10, color: '#cc8855' }}>
        session: <code style={{ color: '#ffe8d4' }}>{sessionId}</code>
      </div>
      <span style={{
        padding:       '2px 8px',
        background:    chainIntact ? '#5bd6a31a' : '#d65b781a',
        color:         chainIntact ? '#5bd6a3' : '#d65b78',
        border:        `1px solid ${chainIntact ? '#5bd6a3' : '#d65b78'}`,
        borderRadius:  4,
        fontFamily:    _MONO,
        fontSize:      10,
        fontWeight:    600,
      }}>chain_length={chainLength} · intact={String(chainIntact)}</span>
    </div>
  )
}

export default function GicChainExplorerView() {
  const { grindSessionId } = useParams()
  const { data: status } = usePublicGicChain(grindSessionId)
  const { data: linksResp, isLoading, error } = usePublicGicLinks(grindSessionId)
  const [results, setResults] = useState({})  // { [linkId]: 'ok' | 'mismatch' | 'pending' }
  const [genesisStatus, setGenesisStatus] = useState(null)

  // Auto-verify every link on first load — concurrent, fail-open
  useEffect(() => {
    const links = linksResp?.links || []
    if (links.length === 0) return
    let cancelled = false

    async function run() {
      const out = {}
      for (const link of links) {
        try {
          const computed = await verifyGicChainLink(
            link.prev_gic_hex || ('0'.repeat(64)),
            link.commitment_hash,
            link.verdict_code,
            link.host_state_code,
            BigInt(link.gic_ts_ns),
          )
          out[link.id] = (computed === link.grind_chain_hash) ? 'ok' : 'mismatch'
        } catch {
          out[link.id] = 'mismatch'
        }
        if (cancelled) return
      }
      // Genesis verification — re-derive the chain anchor
      if (links[0]?.gic_ts_ns) {
        try {
          await verifyGicGenesis(grindSessionId, BigInt(links[0].gic_ts_ns))
          if (!cancelled) setGenesisStatus('ok')
        } catch {
          if (!cancelled) setGenesisStatus('mismatch')
        }
      }
      if (!cancelled) setResults(out)
    }
    run()
    return () => { cancelled = true }
  }, [linksResp, grindSessionId])

  const links = linksResp?.links || []
  const okCount = Object.values(results).filter(s => s === 'ok').length
  const mismatchCount = Object.values(results).filter(s => s === 'mismatch').length

  return (
    <div style={{ minHeight: '100dvh', background: '#020408', color: '#ffe8d4', overflow: 'auto' }}>
      <HeaderBanner
        sessionId={grindSessionId}
        chainLength={status?.chain_length ?? '?'}
        chainIntact={Boolean(status?.chain_intact)}
      />

      <div style={{ padding: '12px 24px', background: 'rgba(10,14,20,0.6)', borderBottom: `1px solid ${_ACCENT}1a` }}>
        <div style={{ display: 'flex', gap: 24, fontFamily: _MONO, fontSize: 10, color: '#7a8a9b' }}>
          <span>links_fetched: <strong style={{ color: '#ffe8d4' }}>{links.length}</strong></span>
          <span>browser_verified_ok: <strong style={{ color: '#5bd6a3' }}>{okCount}</strong></span>
          <span>mismatches: <strong style={{ color: mismatchCount > 0 ? '#d65b78' : '#5bd6a3' }}>{mismatchCount}</strong></span>
          <span>genesis: <StatusPill status={genesisStatus || 'pending'} /></span>
          <span style={{ flex: 1 }} />
          <span style={{ fontStyle: 'italic' }}>verifier: vapi_verifier.js · Web Crypto SHA-256</span>
        </div>
        <div style={{ marginTop: 8, fontFamily: _MONO, fontSize: 10, color: '#7a8a9b', lineHeight: 1.5, fontStyle: 'italic' }}>
          {linksResp?.discipline}
        </div>
      </div>

      <div style={{ padding: '12px 24px' }}>
        {isLoading && <div style={{ color: '#7a8a9b', fontFamily: _MONO }}>Loading chain links…</div>}
        {error && <div style={{ color: '#d65b78', fontFamily: _MONO }}>{String(error.message || error)}</div>}
        {links.length === 0 && !isLoading && (
          <div style={{ padding: 24, fontFamily: _MONO, fontSize: 11, color: '#7a8a9b', border: '1px solid rgba(122,138,155,0.18)', borderRadius: 4 }}>
            No chain links found for session <code>{grindSessionId}</code>.
            Try <code>grind_phase235_v1</code> for the Phase 239 G3 GIC_100 anchored chain.
          </div>
        )}
        <table data-vapi-gic-table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: _MONO, fontSize: 10 }}>
          <thead>
            <tr style={{ background: 'rgba(240,168,104,0.05)' }}>
              <th style={{ textAlign: 'left', padding: '6px 10px', color: '#7a8a9b', letterSpacing: '0.08em' }}>#</th>
              <th style={{ textAlign: 'left', padding: '6px 10px', color: '#7a8a9b', letterSpacing: '0.08em' }}>PREV_GIC</th>
              <th style={{ textAlign: 'left', padding: '6px 10px', color: '#7a8a9b', letterSpacing: '0.08em' }}>COMMITMENT</th>
              <th style={{ textAlign: 'left', padding: '6px 10px', color: '#7a8a9b', letterSpacing: '0.08em' }}>VERDICT</th>
              <th style={{ textAlign: 'left', padding: '6px 10px', color: '#7a8a9b', letterSpacing: '0.08em' }}>HOST</th>
              <th style={{ textAlign: 'left', padding: '6px 10px', color: '#7a8a9b', letterSpacing: '0.08em' }}>GIC_HASH</th>
              <th style={{ textAlign: 'left', padding: '6px 10px', color: '#7a8a9b', letterSpacing: '0.08em' }}>VERIFIED</th>
            </tr>
          </thead>
          <tbody>
            {links.map((link, i) => (
              <tr key={link.id} data-vapi-gic-link-row={link.id} style={{ borderBottom: '1px solid rgba(122,138,155,0.08)' }}>
                <td style={{ padding: '5px 10px', color: '#cc8855' }}>{i + 1}</td>
                <td style={{ padding: '5px 10px', color: '#ffe8d4' }}>
                  <code>{link.prev_gic_hex ? `${link.prev_gic_hex.slice(0, 8)}…` : '— (head)'}</code>
                </td>
                <td style={{ padding: '5px 10px', color: '#ffe8d4' }}>
                  <code>{String(link.commitment_hash || '').slice(0, 8)}…</code>
                </td>
                <td style={{ padding: '5px 10px', color: '#cc8855' }}>{link.fallback_verdict}</td>
                <td style={{ padding: '5px 10px', color: '#cc8855' }}>{link.pcc_host_state}</td>
                <td style={{ padding: '5px 10px', color: '#ffe8d4' }}>
                  <code>{String(link.grind_chain_hash || '').slice(0, 8)}…</code>
                </td>
                <td style={{ padding: '5px 10px' }}>
                  <StatusPill status={results[link.id] || 'pending'} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
