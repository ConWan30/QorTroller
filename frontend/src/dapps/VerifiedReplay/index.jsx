// Verified Replay Card — Arc 5 VHR proof, public, shareable.
//
// The first gaming replay artifact with cryptographic provenance.
// A Twitch clip has zero authenticity guarantees; this card carries the
// VHR Groth16 proof's hash specimen, the sanitizedTraceRoot binding,
// the IoTeX block anchoring, and an explorer deep-link. The visual IS
// the proof: a different proof → a different foil → a visually distinct
// card. You cannot fake the card without faking the underlying proof.
//
// Routes (wired in main.jsx):
//   /replay/:hash         — chrome variant for share / standalone view
//   /replay/embed/:hash   — no chrome, transparent bg, designed to sit
//                           over OBS browser sources (streamers can drop
//                           the card on top of their gameplay during a
//                           PROOF_BUILT moment without re-styling)
//
// Honesty rails:
//   • noMock on the data hook — a fabricated proof outcome would
//     impersonate a cryptographic claim that never fired (sovereignty
//     + audit-trail violation)
//   • Bridge offline → honest "bridge unreachable" state, never a
//     placeholder proof
//   • No matching hash → honest "no such proof recorded" state, never
//     a fabricated card
//   • DEMO badge clearly shown when ?demo=1 query param sends the
//     fixture sample card (so a streamer can preview what the card
//     will look like before their first real proof lands)

import { useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useLatestVhrProof } from '../../api/bridgeApi'
import { ProofFoil } from './ProofFoil'

const IOTEX_TX_PREFIX = 'https://testnet.iotexscan.io/tx/'

// ── color tokens (in-line — this dApp is standalone, not theme-bound) ──
const VOID = '#04060a'
const VOID_SOFT = '#0a0e14'
const CHAIN = '#5bd6a3'
const AMBER = '#f0a868'
const TEXT = '#d4dde8'
const TEXT_DIM = '#8a96a5'
const TEXT_FAINT = '#5a6675'
const BORDER = '#1a2230'

function classifyOutcome(outcome) {
  if (outcome === 'vhr_proof_built') {
    return { tone: CHAIN, label: 'PROOF BUILT', sub: 'cryptographic proof generated' }
  }
  if (outcome === 'vhr_proof_built_no_verifier') {
    return { tone: CHAIN, label: 'PROOF BUILT', sub: 'verifier address not wired' }
  }
  if (outcome === 'vhr_proof_deferred') {
    return { tone: AMBER, label: 'DEFERRED', sub: 'no prover (ceremony pending)' }
  }
  if (outcome === 'vhr_deferred_no_consent') {
    return { tone: AMBER, label: 'NO CONSENT', sub: 'Arc 4 manifest gate closed' }
  }
  return { tone: TEXT_FAINT, label: outcome?.toUpperCase() || '—', sub: '' }
}

function shorten(hash, head = 8, tail = 6) {
  if (!hash) return '—'
  const h = String(hash)
  if (h.length <= head + tail + 1) return h
  return `${h.slice(0, head)}…${h.slice(-tail)}`
}

function fmtTimestamp(tsNs) {
  if (!tsNs) return '—'
  try {
    const sec = Math.floor(Number(tsNs) / 1e9)
    const d = new Date(sec * 1000)
    if (Number.isNaN(d.getTime())) return '—'
    return d.toISOString().replace('T', ' ').slice(0, 19) + ' UTC'
  } catch {
    return '—'
  }
}

// Fixture sample for ?demo=1 — a STREAMER PREVIEW so they can see what
// the card will look like before their first real PROOF_BUILT lands.
// The DEMO badge is loud — this is NOT confusable with a real proof.
const DEMO_FIXTURE = {
  outcome: 'vhr_proof_built',
  session_id: 'grind_phase235_v1',
  ts_ns: 1780703825000000000,
  // 64-char hex — produces a stable-looking foil for the demo
  extra: JSON.stringify({
    replay_proof_token: '0x4f6d2c8a93e1b5d770a9c41fbe25a8d617e4cbf4a39d8e215b9c47a832e76c5d',
    poac_chain_root: '0x0e9d453d904220148d632e75802b71bdff74c7197aa8afcbfec5d36a61ab48da',
    block_number: 44355513,
  }),
}

function pickProof(rows, hashParam) {
  if (!rows || rows.length === 0) return null
  if (!hashParam) return rows[0]  // most recent
  // Try to match by replay_proof_token in the extra JSON
  for (const r of rows) {
    try {
      const ex = typeof r.extra === 'string' ? JSON.parse(r.extra) : r.extra
      const token = ex?.replay_proof_token || ''
      if (token === hashParam) return r
      if (token === '0x' + hashParam.replace(/^0x/, '')) return r
      // Also accept prefix match for short URLs
      if (token.startsWith(hashParam)) return r
    } catch { /* fail-open on malformed extra */ }
  }
  return null
}

function CardSurface({ proofRow, isDemo, embed }) {
  // Parse the extra JSON for proof-specific fields. The curator_packaging_log
  // schema is generic; the WMP/VHR proof payload lives in extra.
  const extra = useMemo(() => {
    if (!proofRow?.extra) return {}
    try {
      return typeof proofRow.extra === 'string' ? JSON.parse(proofRow.extra) : proofRow.extra
    } catch {
      return {}
    }
  }, [proofRow])

  const c = classifyOutcome(proofRow?.outcome)
  const proofToken = extra.replay_proof_token || extra.replay_proof_hash || ''
  const poacChainRoot = extra.poac_chain_root || ''
  const blockNumber = extra.block_number || extra.block || null
  const txHash = extra.tx_hash || ''

  return (
    <div
      className="vapi-replay-card"
      style={{
        // Vertical 9:16 card (max-width sized; scales via CSS scale on
        // small screens). Aspect-ratio property keeps it phone-friendly.
        width: '100%',
        maxWidth: 360,
        aspectRatio: '9 / 16',
        background: `linear-gradient(180deg, ${VOID_SOFT} 0%, ${VOID} 100%)`,
        border: `1px solid ${BORDER}`,
        borderRadius: 12,
        position: 'relative',
        overflow: 'hidden',
        fontFamily: "'Syne', system-ui, sans-serif",
        boxShadow: embed ? 'none' : `0 8px 36px -10px rgba(0,0,0,0.6)`,
      }}
    >
      <ProofFoil proofToken={proofToken} intensity={isDemo ? 0.6 : 1.0}>
        <div
          style={{
            padding: '22px 22px 18px',
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            gap: 14,
            // aspect-ratio = 9:16 means height is auto from width;
            // but inner content should fill — use absolute positioning trick
            position: 'absolute',
            inset: 0,
            boxSizing: 'border-box',
          }}
        >
          {/* ── TOP CHROME ─────────────────────────────────── */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'baseline',
          }}>
            <span style={{
              fontFamily: "'Syne', system-ui, sans-serif",
              fontWeight: 700,
              fontSize: 18,
              letterSpacing: '-0.02em',
              color: TEXT,
            }}>
              Qor<span style={{ color: AMBER, fontWeight: 800 }}>T</span>roller
            </span>
            {isDemo && (
              <span style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 9,
                color: AMBER,
                letterSpacing: '0.18em',
                background: `${AMBER}22`,
                border: `1px solid ${AMBER}66`,
                padding: '3px 8px',
                borderRadius: 3,
              }}>DEMO</span>
            )}
          </div>

          <div style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 9,
            letterSpacing: '0.18em',
            color: TEXT_FAINT,
            textTransform: 'uppercase',
          }}>
            Verified · Human · Replay
          </div>

          {/* ── HEADLINE VERDICT ───────────────────────────── */}
          <div>
            <div style={{
              fontFamily: "'Syne', system-ui, sans-serif",
              fontSize: 26,
              fontWeight: 700,
              letterSpacing: '-0.02em',
              color: c.tone,
              lineHeight: 1.1,
            }}>
              {c.label}
            </div>
            {c.sub && (
              <div style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 10,
                color: TEXT_DIM,
                marginTop: 4,
                lineHeight: 1.4,
              }}>
                {c.sub}
              </div>
            )}
          </div>

          {/* ── CRYPTOGRAPHIC SPECIMEN ─────────────────────── */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 10 }}>
            <Field label="Proof token" mono>
              <span style={{ color: CHAIN }}>{shorten(proofToken, 12, 8)}</span>
            </Field>
            <Field label="PoAC chain root" mono>
              <span style={{ color: TEXT_DIM, fontSize: 10 }}>{shorten(poacChainRoot, 10, 8)}</span>
            </Field>
            <Field label="Session" mono>
              <span style={{ color: TEXT_DIM }}>{shorten(proofRow?.session_id || '', 12, 4)}</span>
            </Field>
            {blockNumber && (
              <Field label="IoTeX block" mono>
                <span style={{ color: AMBER }}>#{blockNumber}</span>
              </Field>
            )}
            <Field label="When" mono>
              <span style={{ color: TEXT_DIM, fontSize: 10 }}>{fmtTimestamp(proofRow?.ts_ns)}</span>
            </Field>
          </div>

          {/* ── FOOTER ─────────────────────────────────────── */}
          <div style={{
            borderTop: `1px solid ${BORDER}`,
            paddingTop: 10,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 8,
          }}>
            <span style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 8,
              color: TEXT_FAINT,
              letterSpacing: '0.14em',
              textTransform: 'uppercase',
            }}>
              IoTeX · Testnet · 4690
            </span>
            {txHash ? (
              <a
                href={IOTEX_TX_PREFIX + txHash}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 9,
                  color: CHAIN,
                  textDecoration: 'none',
                  letterSpacing: '0.04em',
                }}
              >
                explorer ↗
              </a>
            ) : (
              <span style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 9,
                color: TEXT_FAINT,
                letterSpacing: '0.04em',
              }}>
                local-attested
              </span>
            )}
          </div>
        </div>
      </ProofFoil>
    </div>
  )
}

function Field({ label, mono, children }) {
  return (
    <div style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'baseline',
      gap: 8,
    }}>
      <span style={{
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 8.5,
        color: TEXT_FAINT,
        letterSpacing: '0.16em',
        textTransform: 'uppercase',
        flexShrink: 0,
      }}>
        {label}
      </span>
      <span style={{
        fontFamily: mono ? "'JetBrains Mono', monospace" : "'Syne', system-ui, sans-serif",
        fontSize: 11,
        textAlign: 'right',
        wordBreak: 'break-all',
      }}>
        {children}
      </span>
    </div>
  )
}

export default function VerifiedReplayCardDapp() {
  const { hash } = useParams()
  const [searchParams] = useSearchParams()
  const isDemoQuery = searchParams.get('demo') === '1'
  // Detect /replay/embed/:hash route via URL inspection (vs the /replay/:hash route)
  const isEmbed = typeof window !== 'undefined'
    && window.location.pathname.startsWith('/replay/embed')

  const { data: vhrLatest, isLoading, isError } = useLatestVhrProof(20)
  const rows = useMemo(() => {
    return Array.isArray(vhrLatest?.pending_replay_proofs)
      ? vhrLatest.pending_replay_proofs
      : []
  }, [vhrLatest])

  // Decide what to render:
  //   • ?demo=1 → DEMO_FIXTURE (always honest about being a preview)
  //   • have rows + hash matches one → matched row
  //   • have rows, no hash → most recent
  //   • have no rows / error → honest empty state
  const proofRow = isDemoQuery
    ? DEMO_FIXTURE
    : pickProof(rows, hash)

  // Page container — different chrome based on embed mode
  const pageBg = isEmbed ? 'transparent' : VOID
  const pageStyle = isEmbed
    ? {
        background: pageBg,
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 20,
      }
    : {
        background: pageBg,
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: '32px 20px',
        gap: 24,
      }

  return (
    <div style={pageStyle}>
      {/* Standalone chrome — wordmark + back to dashboard. Omitted in embed mode. */}
      {!isEmbed && (
        <div style={{
          width: '100%',
          maxWidth: 720,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'baseline',
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 11,
          color: TEXT_FAINT,
        }}>
          <Link to="/" style={{
            color: TEXT_DIM,
            textDecoration: 'none',
            letterSpacing: '0.12em',
            textTransform: 'uppercase',
          }}>
            ← Dashboard
          </Link>
          <span style={{ letterSpacing: '0.14em', textTransform: 'uppercase' }}>
            Verified · Replay · Card
          </span>
        </div>
      )}

      {/* main card area */}
      {isLoading && !isDemoQuery ? (
        <EmptyState>Loading…</EmptyState>
      ) : isError && !isDemoQuery ? (
        <EmptyState>Bridge unreachable. The card will resume when the bridge is back.</EmptyState>
      ) : !proofRow ? (
        <NoProofYet hashParam={hash} />
      ) : (
        <CardSurface proofRow={proofRow} isDemo={isDemoQuery} embed={isEmbed} />
      )}

      {/* Standalone meta — copy URL helper. Omitted in embed mode. */}
      {!isEmbed && proofRow && (
        <ShareStrip isDemo={isDemoQuery} />
      )}
    </div>
  )
}

function EmptyState({ children }) {
  return (
    <div style={{
      maxWidth: 360,
      padding: '40px 20px',
      textAlign: 'center',
      fontFamily: "'JetBrains Mono', monospace",
      fontSize: 11,
      color: TEXT_FAINT,
      lineHeight: 1.6,
    }}>
      {children}
    </div>
  )
}

function NoProofYet({ hashParam }) {
  return (
    <div style={{
      maxWidth: 360,
      padding: '32px 24px',
      textAlign: 'center',
      fontFamily: "'Syne', system-ui, sans-serif",
      color: TEXT_DIM,
      lineHeight: 1.6,
      border: `1px dashed ${BORDER}`,
      borderRadius: 12,
    }}>
      <div style={{
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 10,
        color: AMBER,
        letterSpacing: '0.18em',
        marginBottom: 14,
      }}>
        NO MATCHING PROOF
      </div>
      <div style={{ fontSize: 14, marginBottom: 16 }}>
        {hashParam
          ? `No replay proof recorded for this hash yet.`
          : `No VHR proofs have been produced yet on this bridge.`}
      </div>
      <div style={{
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 10,
        color: TEXT_FAINT,
        lineHeight: 1.55,
      }}>
        Want to see what a card looks like? Append <code style={{ color: CHAIN }}>?demo=1</code> to the URL for a fixture preview.
      </div>
    </div>
  )
}

function ShareStrip({ isDemo }) {
  const [copied, setCopied] = useState(false)
  useEffect(() => {
    if (!copied) return
    const t = setTimeout(() => setCopied(false), 1600)
    return () => clearTimeout(t)
  }, [copied])

  async function copy() {
    try {
      await navigator.clipboard.writeText(window.location.href)
      setCopied(true)
    } catch { /* clipboard refused — no-op */ }
  }

  return (
    <div style={{
      maxWidth: 360,
      width: '100%',
      display: 'flex',
      flexDirection: 'column',
      gap: 10,
      fontFamily: "'JetBrains Mono', monospace",
    }}>
      <button
        onClick={copy}
        style={{
          padding: '10px 14px',
          background: 'transparent',
          border: `1px solid ${BORDER}`,
          borderRadius: 4,
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 11,
          color: copied ? CHAIN : TEXT_DIM,
          letterSpacing: '0.14em',
          textTransform: 'uppercase',
          cursor: 'pointer',
        }}
      >
        {copied ? '✓ url copied' : 'copy share url'}
      </button>
      <div style={{
        fontSize: 9,
        color: TEXT_FAINT,
        lineHeight: 1.55,
        textAlign: 'center',
        letterSpacing: '0.06em',
      }}>
        {isDemo ? (
          'this is a demo card from a fixture — not a real proof'
        ) : (
          <>
            for stream overlays use <code style={{ color: CHAIN }}>/replay/embed/{'<hash>'}</code> — same card, no chrome, transparent background
          </>
        )}
      </div>
    </div>
  )
}
