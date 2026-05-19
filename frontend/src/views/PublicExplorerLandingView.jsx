/**
 * Phase O5-PUBLIC-VIEWER Stage 6 — Public Explorer Landing
 *
 * Public route at /explorer. Front door for the public viewer family.
 * Links to:
 *   /session/<hash>          — VPM artifact + 16-tag crypto replay
 *   /gic/<grindSessionId>    — full GIC chain explorer
 *   /record/<device>/<ctr>   — 228-byte PoAC byte explorer
 *   /vhp/<tokenId>           — VHP credential card
 *   /algorithms              — FROZEN-v1 algorithm catalog
 *
 * Plus a live stats panel pulled from /public/protocol-state +
 * /public/agent-roots and a hash-lookup search box.
 */
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { usePublicProtocolState, usePublicAgentRoots } from '../api/publicForensic'

const _MONO = 'JetBrains Mono, ui-monospace, monospace'
const _ACCENT = '#f0a868'

const _ROUTES = [
  { path: '/session/<commitment_hex>',   label: 'VPM Artifact Viewer',
    desc:  'Per-session VPM artifact with FROZEN-v1 verifier replay panel; ' +
           'every cryptographic claim browser-recomputed via SHA-256.' },
  { path: '/gic/<grind_session_id>',     label: 'GIC Chain Explorer',
    desc:  'Full Grind Integrity Chain timeline; every link recomputed in ' +
           'browser; on-chain GIC_100 anchor surfaceable via genesis check.' },
  { path: '/record/<device>/<counter>',  label: 'PoAC Byte Explorer',
    desc:  'Single 228-byte PoAC record with field-level byte-offset layout; ' +
           'SHA-256(raw[:164]) body-only hash demonstrated visually.' },
  { path: '/vhp/<tokenId>',              label: 'VHP Credential Card',
    desc:  'Soulbound Verified Human Proof credential view; cert_level + ' +
           'expires_at + consecutive_clean. Streamer / sponsor embed target.' },
  { path: '/algorithms',                 label: 'Algorithm Catalog',
    desc:  '14 FROZEN-v1 cryptographic primitives as a browsable reference. ' +
           'Domain tags + byte layouts + Python file:line + JS verifier names.' },
]

function StatCard({ label, value, accent = '#ffe8d4' }) {
  return (
    <div style={{ padding: 14, background: 'rgba(10,14,20,0.6)', border: '1px solid rgba(122,138,155,0.18)', borderRadius: 4 }}>
      <div style={{ fontFamily: _MONO, fontSize: 9, color: '#7a8a9b', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 4 }}>
        {label}
      </div>
      <div style={{ fontFamily: _MONO, fontSize: 18, fontWeight: 700, color: accent }}>
        {value}
      </div>
    </div>
  )
}

function HashLookup() {
  const [hash, setHash] = useState('')
  const navigate = useNavigate()

  function onSubmit(e) {
    e.preventDefault()
    const h = (hash || '').trim().toLowerCase().replace(/^0x/, '')
    if (h.length === 64) {
      navigate(`/session/${h}`)
    }
  }

  return (
    <form onSubmit={onSubmit} style={{ display: 'flex', gap: 8 }}>
      <input
        type="text"
        placeholder="paste a session commitment_hex (64 chars) and press Enter…"
        value={hash}
        onChange={e => setHash(e.target.value)}
        style={{
          flex: 1, padding: '10px 14px',
          fontFamily: _MONO, fontSize: 11,
          background: '#0a0e14', color: '#ffe8d4',
          border: `1px solid ${_ACCENT}`, borderRadius: 4,
        }}
      />
      <button type="submit" style={{
        padding: '10px 20px', fontFamily: _MONO, fontSize: 11,
        background: `${_ACCENT}33`, color: _ACCENT,
        border: `1px solid ${_ACCENT}`, borderRadius: 4,
        cursor: 'pointer', fontWeight: 700,
        letterSpacing: '0.08em', textTransform: 'uppercase',
      }}>Explore</button>
    </form>
  )
}

export default function PublicExplorerLandingView() {
  const { data: state } = usePublicProtocolState()
  const { data: agents } = usePublicAgentRoots()

  return (
    <div style={{ minHeight: '100dvh', background: '#020408', color: '#ffe8d4', overflow: 'auto' }}>
      <div style={{
        padding: '16px 24px', background: 'rgba(2,4,8,0.9)',
        borderBottom: `1px solid ${_ACCENT}`, display: 'flex', gap: 16, alignItems: 'center',
      }}>
        <div style={{ fontFamily: _MONO, fontSize: 11, fontWeight: 700, color: _ACCENT, letterSpacing: '0.16em', textTransform: 'uppercase' }}>
          QorTroller · Public Forensic Explorer
        </div>
        <div style={{ flex: 1 }} />
        <Link to="/" style={{ fontFamily: _MONO, fontSize: 11, color: '#7a8a9b', textDecoration: 'none' }}>operator dashboard →</Link>
      </div>

      <div style={{ padding: '24px', maxWidth: 1100, margin: '0 auto' }}>
        {/* Thesis */}
        <div style={{ marginBottom: 24, padding: 20, background: 'linear-gradient(135deg, rgba(91,214,163,0.08) 0%, rgba(240,168,104,0.05) 100%)', border: `1px solid ${_ACCENT}33`, borderRadius: 6 }}>
          <div style={{ fontFamily: _MONO, fontSize: 11, color: _ACCENT, fontWeight: 700, letterSpacing: '0.12em', marginBottom: 8, textTransform: 'uppercase' }}>
            Every claim · Verifiable in your browser
          </div>
          <div style={{ fontFamily: _MONO, fontSize: 11, color: '#ffe8d4', lineHeight: 1.7 }}>
            QorTroller (the reference implementation of <strong style={{ color: '#5bd6a3' }}>Verifiable Autonomous Physical Intelligence — V.A.P.I.</strong>, a coined DePIN sub-category) is the first anti-cheat protocol where any external party — tournament organizer, sponsor, manufacturer, journalist, opposing team, regulator — can verify cryptographic claims <strong style={{ color: '#5bd6a3' }}>without trusting the operator</strong>. Paste a session hash below or browse the routes. Each viewer re-executes the protocol's SHA-256 algorithms in your browser via Web Crypto API and displays OK / MISMATCH per primitive.
          </div>
        </div>

        {/* Search */}
        <div style={{ marginBottom: 24 }}>
          <HashLookup />
        </div>

        {/* Live stats */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 10, marginBottom: 24 }}>
          <StatCard label="PV-CI Invariants"     value={state?.pv_ci_invariants_count   ?? '—'} accent="#5bd6a3" />
          <StatCard label="VPM Artifacts"        value={state?.total_vpm_artifacts      ?? '—'} accent="#f0a868" />
          <StatCard label="MLGA Sessions"        value={state?.total_mlga_sessions      ?? '—'} accent="#cc8855" />
          <StatCard label="GIC Chain Links"      value={state?.total_grind_chain_links  ?? '—'} accent="#cc8855" />
          <StatCard label="Kill-Switch"          value={state?.kill_switch_paused ? 'PAUSED' : 'LIVE'} accent={state?.kill_switch_paused ? '#5bd6a3' : '#d65b78'} />
          <StatCard label="Chain"                value={agents?.chain?.name || 'IoTeX'} accent="#cc8855" />
        </div>

        {/* Route directory */}
        <div style={{ marginBottom: 18, fontFamily: _MONO, fontSize: 11, fontWeight: 700, color: _ACCENT, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
          5 Public Viewer Routes
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 12, marginBottom: 24 }}>
          {_ROUTES.map((r, i) => {
            // Build a sample link for the directory tile
            const sampleLink =
              r.path === '/session/<commitment_hex>'  ? '/session/4e5a99b1db47619e8be7cf0725c39f0440cdef95262ca7937a67c5c34984a3d8' :
              r.path === '/gic/<grind_session_id>'    ? '/gic/grind_phase235_v1' :
              r.path === '/record/<device>/<counter>' ? '/record/581a836c98b3a1b6/42' :
              r.path === '/vhp/<tokenId>'             ? '/vhp/2' :
              r.path === '/algorithms'                ? '/algorithms' :
              '/'
            return (
              <Link key={i} to={sampleLink} style={{
                display: 'flex', flexDirection: 'column', gap: 6,
                padding: 14, background: 'rgba(10,14,20,0.6)',
                border: '1px solid rgba(122,138,155,0.18)', borderRadius: 4,
                fontFamily: _MONO, textDecoration: 'none',
                transition: 'border-color 0.15s',
              }}
              onMouseEnter={e => e.currentTarget.style.borderColor = _ACCENT}
              onMouseLeave={e => e.currentTarget.style.borderColor = 'rgba(122,138,155,0.18)'}
              >
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
                  <code style={{ fontSize: 11, color: '#5bd6a3', fontWeight: 700 }}>{r.path}</code>
                  <span style={{ fontSize: 11, color: '#ffe8d4', fontWeight: 600 }}>{r.label}</span>
                </div>
                <div style={{ fontSize: 10, color: '#7a8a9b', lineHeight: 1.5 }}>
                  {r.desc}
                </div>
                <div style={{ fontSize: 9, color: '#cc8855', fontStyle: 'italic' }}>
                  example: <code>{sampleLink}</code>
                </div>
              </Link>
            )
          })}
        </div>

        {/* Operator Initiative card */}
        {agents?.agents && (
          <div style={{ padding: 14, background: 'rgba(10,14,20,0.85)', border: '1px solid rgba(240,168,104,0.25)', borderRadius: 4 }}>
            <div style={{ fontFamily: _MONO, fontSize: 11, fontWeight: 700, color: _ACCENT, letterSpacing: '0.12em', marginBottom: 8, textTransform: 'uppercase' }}>
              On-Chain Operator Initiative · {agents.agents.length} agents
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 8, fontFamily: _MONO, fontSize: 10 }}>
              {agents.agents.map((a, i) => (
                <div key={i} style={{ padding: 10, background: 'rgba(2,4,8,0.5)', borderRadius: 4 }}>
                  <div style={{ color: '#5bd6a3', fontWeight: 700 }}>{a.canonical}</div>
                  <div style={{ color: '#7a8a9b' }}>phase: <code style={{ color: '#ffe8d4' }}>{a.phase}</code></div>
                  <div style={{ color: '#7a8a9b' }}>cedar merkle: <code style={{ color: '#ffe8d4' }}>{String(a.cedar_bundle_merkle || '').slice(0, 20)}…</code></div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div style={{ marginTop: 30, padding: 18, fontFamily: _MONO, fontSize: 10, color: '#7a8a9b', lineHeight: 1.7, fontStyle: 'italic', borderTop: '1px solid rgba(122,138,155,0.18)' }}>
          QorTroller's defensibility flows from cryptographic guarantees, not closed-source obscurity. The catalog of 14 FROZEN-v1 V.A.P.I. primitives — PoAC, GIC, MLGA, ZKBA, VHP, Cedar bundle Merkle, and the rest — is published in code, executable in browser, verifiable end-to-end. No other anti-cheat surfaces its hashing scheme this way. Riot Vanguard / Easy Anti-Cheat / BattlEye / kernel-level competitors all remain opaque; QorTroller's commitment to verifiability is the moat.
        </div>
      </div>
    </div>
  )
}
