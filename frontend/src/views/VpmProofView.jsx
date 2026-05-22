// QorTroller VPM Proof page — Verified Projection Media gallery + forensic
// inspector. Ported from the Claude-Design export (qortroller-frontend/
// VpmProofView.jsx) and wired to real bridge data.
//
// The protocol autonomously compiles ~14 artifact classes (MLGA / CDRR /
// GIC-LEDGER / HONESTY-BOARD / …) into self-contained, independently-verifiable
// HTML documents. This view browses them, renders the selected proof full-bleed
// via the FROZEN render rule, and surfaces a live in-browser SHA-256 integrity
// verdict + a real visual-grammar verdict + provenance.
//
// HONESTY-PRESERVING INTEGRATION (vs the design prototype which synthesised the
// proof HTML client-side against a Blob URL):
//   - The proof is FETCHED from the real bridge artifact endpoint with
//     cache:'no-store' and rendered via srcDoc — never iframe src= (which caches
//     stale proofs). This is the defining render rule.
//   - The integrity verdict is a REAL sha256 of the fetched bytes compared to
//     the row's compiler_output_hash_hex (the file hash). FLIP-A-BYTE tampers
//     the LOCAL fetched copy → a genuine mismatch (the server file is immutable).
//   - The grammar verdict runs the real verifyVpmGrammar() against the fetched
//     HTML — the FROZEN 6-state VISUAL_STATE_SIGNATURES contract, not the
//     prototype's data-grammar stub anchors.
//   - useVpmList is noMock:true; honest empty states; no fabricated rows.

import { useState, useEffect, useMemo, useRef } from 'react'
import { useVpmList } from '../api/bridgeApi'
import { verifyVpmGrammar } from '../components/VpmGrammarVerifier'
import { Panel, StatusChip, HashSpecimen } from '../design/Primitives'
import { useReDeriveHash } from '../design/motion'
import { useViewEyebrow } from '../design/Eyebrow'
import '../design/qortroller-kit.css'

// ── Visual-state vocabulary (the 6 FROZEN states) ────────────────────────
const VPM_STATES = {
  'live':            { tone: 'live',     label: 'LIVE' },
  'dry-run':         { tone: 'pending',  label: 'DRY-RUN' },
  'emulated':        { tone: 'verified', label: 'EMULATED' },
  'frozen-disabled': { tone: 'dormant',  label: 'FROZEN-DISABLED' },
  'revoked':         { tone: 'blocked',  label: 'REVOKED' },
  'unverified':      { tone: 'dormant',  label: 'UNVERIFIED' },
}
// Known artifact classes (filter chips). Selecting one with no rows shows the
// honest "no matching artifacts" state — never fabricated.
const VPM_IDS = [
  'MLGA-SESSION-v1', 'CDRR-DAG-v1', 'GIC-LEDGER-BETA-v1',
  'HONESTY-BOARD-v1', 'CONSENT-COMMIT-v1', 'VHP-ZKBA-v1',
]

const _API_KEY = import.meta.env.VITE_VAPI_API_KEY

// Real artifact URL. Content-version (&v) so the URL changes when the proof
// changes; cache:'no-store' on the fetch is the real cache defeat.
function vpmArtifactUrl(commit, version) {
  const p = new URLSearchParams()
  if (_API_KEY) p.set('api_key', _API_KEY)
  if (version) p.set('v', version)
  const qs = p.toString()
  return `/operator/operator/vpm-artifact/${commit}${qs ? '?' + qs : ''}`
}

// ── Compact gallery card ─────────────────────────────────────────────────
function GalleryCard({ row, selected, onClick }) {
  const state = VPM_STATES[row.visual_state] || { tone: 'dormant', label: row.visual_state || '—' }
  const weight = typeof row.proof_weight === 'number' ? row.proof_weight : Number(row.proof_weight || 0)
  return (
    <button
      onClick={onClick}
      style={{
        textAlign: 'left',
        background: selected ? 'var(--panel-raised)' : 'var(--panel)',
        border: `1px solid ${selected ? 'var(--accent-amber)' : 'var(--border)'}`,
        borderRadius: 'var(--radius)', padding: '10px 12px', cursor: 'pointer',
        display: 'grid', gap: 6, minWidth: 240, flexShrink: 0,
        color: 'inherit', fontFamily: 'inherit',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 8 }}>
        <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-faint)', letterSpacing: '0.06em' }}>
          {row.commitment_hex.slice(0, 8)}…{row.commitment_hex.slice(-4)}
        </span>
        <StatusChip tone={state.tone}>{state.label}</StatusChip>
      </div>
      <div className="mono" style={{ fontSize: 12.5, color: 'var(--text)', letterSpacing: '0.02em' }}>
        {row.vpm_id}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
        <span className="label" style={{ fontSize: 10 }}>{row.capture_mode}</span>
        <span className="mono" style={{ fontSize: 10.5, color: 'var(--accent-amber)' }}>
          ZKBA · {row.zkba_class} · w {weight.toFixed(2)}
        </span>
      </div>
    </button>
  )
}

// ── Filter chips ─────────────────────────────────────────────────────────
function FilterChip({ active, onClick, children, tone }) {
  return (
    <button
      onClick={onClick}
      style={{
        fontFamily: 'var(--font-mono)', fontSize: 10.5, letterSpacing: '0.08em',
        textTransform: 'uppercase', padding: '4px 10px', borderRadius: 2,
        background: active ? 'var(--accent-amber)' : 'transparent',
        color: active ? '#04060a' : tone ? `var(--status-${tone})` : 'var(--text-dim)',
        border: `1px solid ${active ? 'var(--accent-amber)' : tone ? `var(--status-${tone})` : 'var(--border-strong)'}`,
        cursor: 'pointer', lineHeight: 1,
      }}
    >
      {children}
    </button>
  )
}

// ── The framed proof stage — fetch + srcDoc + no-store ───────────────────
function VpmProofStage({ row, tamperByte, onText }) {
  const [srcDoc, setSrcDoc] = useState('')
  const [fetchTime, setFetchTime] = useState(0)
  const [err, setErr] = useState(null)
  // Auto-size the iframe to the certificate's full content height so the WHOLE
  // card is visible by scrolling the page — never trapped behind the iframe's
  // own short scrollbar. (The design preview rendered the proof in a tall
  // viewport so the card fit; on a laptop viewport the fixed-height stage
  // clipped it. Measuring scrollHeight reproduces the design's full-card view.)
  const iframeRef = useRef(null)
  const [frameH, setFrameH] = useState(640)

  const measure = () => {
    try {
      const d = iframeRef.current?.contentDocument
      if (!d) return
      const read = () => Math.max(
        d.documentElement?.scrollHeight || 0,
        d.body?.scrollHeight || 0,
      )
      const h = read()
      if (h) setFrameH(h)
      // Re-measure after webfonts (Syne/JBM) load + reflow the certificate.
      setTimeout(() => { const h2 = read(); if (h2) setFrameH(h2) }, 450)
    } catch { /* cross-origin guard — same-origin srcDoc, should not throw */ }
  }

  useEffect(() => {
    let cancelled = false
    setSrcDoc(''); setErr(null); onText('')
    const url = vpmArtifactUrl(row.commitment_hex, row.compiler_output_hash_hex)
    const started = performance.now()
    // *** THE RENDER RULE: fetch(no-store) → text() → srcDoc ***
    fetch(url, { headers: _API_KEY ? { 'x-api-key': _API_KEY } : {}, cache: 'no-store' })
      .then((r) => r.text())
      .then((text) => {
        if (cancelled) return
        // The endpoint returns JSON on not-found; only HTML is a real proof.
        if (!text || !text.trimStart().startsWith('<')) {
          setErr('artifact not found on disk'); return
        }
        // FLIP-A-BYTE demo: tamper the LOCAL copy (server file is immutable).
        const out = tamperByte != null ? `${text}\n<!-- TAMPER ${tamperByte} -->\n` : text
        setSrcDoc(out)
        setFetchTime(Math.round(performance.now() - started))
        onText(out)
      })
      .catch((e) => { if (!cancelled) setErr(String(e.message || e)) })
    return () => { cancelled = true }
  }, [row.commitment_hex, row.compiler_output_hash_hex, tamperByte])

  return (
    <div className="qt-specimen" style={{
      position: 'relative', background: 'var(--panel)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius)', overflow: 'hidden', display: 'flex',
      flexDirection: 'column', alignSelf: 'start',
    }}>
      <header className="p-head">
        <span className="p-head__eye">FRAMED · PROOF · STAGE</span>
        <span className="p-head__meta">
          <span style={{ color: 'var(--accent-amber)' }}>fetch</span>(artifact,{' '}
          {'{'}<span style={{ color: 'var(--chain)' }}>cache: 'no-store'</span>{'}'}) → srcDoc · {fetchTime} MS
        </span>
      </header>
      <div style={{ position: 'relative', background: 'var(--bg)' }}>
        {srcDoc ? (
          <iframe
            ref={iframeRef}
            srcDoc={srcDoc}
            sandbox="allow-scripts allow-same-origin"
            title={`VPM Proof · ${row.vpm_id} · ${row.commitment_hex.slice(0, 8)}`}
            onLoad={measure}
            // height = measured certificate height → the whole card renders; the
            // page (not the iframe) scrolls to reveal it all.
            style={{ display: 'block', width: '100%', height: frameH, border: 'none', background: 'transparent' }}
          />
        ) : (
          <div style={{
            minHeight: 360, display: 'grid', placeItems: 'center',
            fontFamily: 'var(--font-mono)', fontSize: 11, color: err ? 'var(--status-blocked)' : 'var(--text-faint)',
            letterSpacing: '0.14em', textTransform: 'uppercase', textAlign: 'center', padding: 16,
          }}>
            {err ? `⚠ ${err}` : '… FETCHING · NO-STORE'}
          </div>
        )}
      </div>
    </div>
  )
}

// ── The forensic inspector ───────────────────────────────────────────────
function VpmInspector({ row, srcText, tamperByte, onTamper, onReset }) {
  const claimedHash = row.compiler_output_hash_hex || ''
  // REAL sha256 over the fetched (possibly tampered) proof bytes.
  const { hex: computedHash, state: hashState, duration } = useReDeriveHash(srcText || '')
  const hashOk = !!computedHash && !!claimedHash && computedHash === claimedHash.toLowerCase()

  // REAL grammar check against the FROZEN signatures over the fetched HTML.
  const grammar = useMemo(
    () => (srcText ? verifyVpmGrammar(srcText, row.visual_state) : null),
    [srcText, row.visual_state],
  )

  // template_version parsed from the real proof's <meta> tag.
  const templateVersion = useMemo(() => {
    const m = srcText && srcText.match(/vpm-template-version"\s+content="([^"]+)"/)
    return m ? m[1] : '—'
  }, [srcText])

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', gap: 16,
      // Sticky beside the (now full-height) proof card so the verdict stays in
      // view while the page scrolls the whole certificate. Scrolls internally
      // only in the rare case it exceeds the viewport.
      position: 'sticky', top: 0, alignSelf: 'start',
      maxHeight: 'calc(100dvh - 96px)', overflowY: 'auto',
    }}>
      {/* INTEGRITY VERDICT */}
      <Panel padding={false}>
        <header className="p-head">
          <span className="p-head__eye">INTEGRITY · VERDICT</span>
          <span className="p-head__meta">SHA-256 · WEB CRYPTO</span>
        </header>
        <div style={{ padding: 16 }}>
          <div style={{
            display: 'grid', gap: 10, padding: '14px 16px',
            // computing → amber (it's working right now), then settle green / red.
            border: `1px solid ${hashState === 'computing' ? 'var(--accent-amber)' : hashOk ? 'var(--chain)' : 'var(--status-blocked)'}`,
            borderRadius: 'var(--radius)',
            background: hashState === 'computing' ? 'var(--accent-amber-trace)' : hashOk ? '#5bd6a30a' : '#d65b7811',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="eye">verdict</span>
              <span
                key={`${hashState}-${hashOk}-${computedHash}`}
                className={hashState === 'computing' ? 'motion--pulse' : hashOk ? 'motion--settle' : 'motion--mismatch'}
                style={{
                  fontFamily: 'var(--font-mono)', fontWeight: 600, fontSize: 22, letterSpacing: '0.08em',
                  color: hashState === 'computing' ? 'var(--accent-amber)' : hashOk ? 'var(--chain)' : 'var(--status-blocked)',
                  lineHeight: 1,
                }}
              >
                {hashState === 'computing' ? '● COMPUTING' : hashOk ? '● HASH OK' : '● MISMATCH'}
              </span>
            </div>
            <div style={{ display: 'grid', gap: 4 }}>
              <span className="label">computed (in-browser, {duration} ms)</span>
              <HashSpecimen value={computedHash} size="sm" tone={hashOk ? 'chain' : 'err'} truncate ends={16} />
            </div>
            <div style={{ display: 'grid', gap: 4 }}>
              <span className="label">claimed (compiler_output_hash)</span>
              <HashSpecimen value={claimedHash} size="sm" tone="chain" truncate ends={16} />
            </div>
          </div>
          <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
            <button className="btn btn--danger btn--sm" onClick={onTamper}>FLIP A BYTE</button>
            <button
              className="btn btn--secondary btn--sm"
              onClick={onReset}
              disabled={tamperByte == null}
              style={tamperByte == null ? { opacity: 0.4, cursor: 'not-allowed' } : {}}
            >
              RE-FETCH · NO-STORE
            </button>
          </div>
        </div>
      </Panel>

      {/* VISUAL-GRAMMAR VERDICT */}
      <Panel
        eyebrow="VISUAL · GRAMMAR · VERDICT"
        meta={`verifyVpmGrammar · ${row.visual_state}`}
      >
        <div style={{ display: 'grid', gap: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="label">DOM signature</span>
            <StatusChip tone={grammar?.ok ? 'live' : grammar ? 'blocked' : 'dormant'}>
              {grammar ? (grammar.ok ? 'OK' : 'VIOLATION') : '—'}
            </StatusChip>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span className="label">declared state</span>
            <span className="mono" style={{ fontSize: 11.5, color: 'var(--accent-amber)' }}>{row.visual_state}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span className="label">meta + aria</span>
            <span className="mono" style={{
              fontSize: 11.5,
              color: grammar && !grammar.missing_meta && !grammar.missing_aria ? 'var(--chain)' : 'var(--status-blocked)',
            }}>
              {grammar ? (!grammar.missing_meta && !grammar.missing_aria ? 'present' : 'missing') : '—'}
            </span>
          </div>
          {grammar && grammar.missing_signatures.length > 0 && (
            <div style={{ marginTop: 4 }}>
              <span className="label">missing signatures</span>
              <div className="mono" style={{ fontSize: 10.5, color: 'var(--status-blocked)', marginTop: 4, wordBreak: 'break-all' }}>
                {grammar.missing_signatures.join(' · ')}
              </div>
            </div>
          )}
        </div>
      </Panel>

      {/* PROVENANCE */}
      <Panel eyebrow="PROVENANCE" meta={templateVersion}>
        <div style={{ display: 'grid', gap: 8 }}>
          {[
            ['vpm_id', row.vpm_id],
            ['commitment_hex', `${row.commitment_hex.slice(0, 16)}…${row.commitment_hex.slice(-8)}`],
            ['output_hash', `${(row.compiler_output_hash_hex || '').slice(0, 16)}…`],
            ['schema', row.wrapper_schema || '—'],
            ['template_version', templateVersion],
            ['manifest_uri', row.manifest_uri || '—'],
            ['ts_ns', String(row.ts_ns)],
          ].map(([k, v]) => (
            <div key={k} style={{ display: 'grid', gridTemplateColumns: 'auto minmax(0, 1fr)', gap: 10 }}>
              <span className="label">{k}</span>
              <span className="mono" style={{ fontSize: 11, color: 'var(--text)', wordBreak: 'break-all', textAlign: 'right' }}>{v}</span>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  )
}

// ── Top-level view ───────────────────────────────────────────────────────
export function VpmProofView() {
  const [vpmId, setVpmId] = useState(null)
  const [visualState, setVisualState] = useState(null)
  const [selectedHex, setSelectedHex] = useState(null)
  const [tamperByte, setTamperByte] = useState(null)
  const [srcText, setSrcText] = useState('')

  const { data: list, isError } = useVpmList({
    vpmId: vpmId || '', visualState: visualState || '', limit: 100,
  })
  const rows = list?.rows || []

  // Keep selection valid as filters change.
  useEffect(() => {
    if (!rows.length) { if (selectedHex !== null) setSelectedHex(null); return }
    if (!rows.find((r) => r.commitment_hex === selectedHex)) {
      setSelectedHex(rows[0].commitment_hex)
    }
  }, [rows, selectedHex])

  // Reset tamper + text when switching artifacts.
  useEffect(() => { setTamperByte(null); setSrcText('') }, [selectedHex])

  const selected = rows.find((r) => r.commitment_hex === selectedHex) || rows[0] || null

  // v2 · item A — eyebrow: registry size + selected proof state.
  useViewEyebrow({
    num: '04',
    name: 'VPM · PROOFS',
    status: isError ? 'BRIDGE OFFLINE' : selected ? (selected.visual_state || '').toUpperCase() : 'NO ARTIFACTS',
    statusTone: isError ? 'blocked' : selected?.visual_state === 'live' ? 'live' : selected ? 'pending' : 'dormant',
    readouts: [
      { label: 'ARTIFACTS', value: isError ? '—' : String(rows.length), tone: 'chain' },
      { label: 'RENDER', value: 'NO-STORE', tone: 'amber' },
    ],
  })

  return (
    <div className="qt-design-root" style={{
      // Page-scrolls vertically: the gallery + the full-height proof card + the
      // inspector flow as one scrollable page so the WHOLE card is viewable
      // (was a fixed-height grid that clipped tall certificates into the
      // iframe's own scrollbar).
      display: 'grid', gridTemplateRows: 'auto auto', gap: 16, padding: 16,
      height: '100%', minHeight: 0, overflowY: 'auto', overflowX: 'hidden',
    }}>
      {/* TOP — filter chips + gallery rail */}
      <Panel padding={false}>
        <header className="p-head">
          <span className="p-head__eye">VPM · PROOF · GALLERY</span>
          <span className="p-head__meta">
            {isError ? 'BRIDGE OFFLINE' : `${rows.length} ARTIFACT${rows.length === 1 ? '' : 'S'}`}
          </span>
        </header>
        <div style={{
          padding: '10px 16px', display: 'flex', gap: 8, alignItems: 'center',
          flexWrap: 'wrap', borderBottom: '1px solid var(--border-soft)',
        }}>
          <span className="label" style={{ marginRight: 4 }}>vpm_id</span>
          <FilterChip active={vpmId === null} onClick={() => setVpmId(null)}>ALL</FilterChip>
          {VPM_IDS.map((id) => (
            <FilterChip key={id} active={vpmId === id} onClick={() => setVpmId(id)}>{id}</FilterChip>
          ))}
          <span className="label" style={{ marginLeft: 14, marginRight: 4 }}>state</span>
          <FilterChip active={visualState === null} onClick={() => setVisualState(null)}>ALL</FilterChip>
          {Object.entries(VPM_STATES).map(([k, v]) => (
            <FilterChip key={k} active={visualState === k} onClick={() => setVisualState(k)} tone={v.tone}>
              {v.label}
            </FilterChip>
          ))}
        </div>
        <div style={{ padding: 12, display: 'flex', gap: 10, overflowX: 'auto' }}>
          {isError ? (
            <div style={{ padding: '12px 6px', display: 'grid', gap: 8 }}>
              <StatusChip tone="blocked">BRIDGE OFFLINE · NO RECORDED ARTIFACTS</StatusChip>
              <span className="label">honest empty state · noMock · no fabricated rows</span>
            </div>
          ) : rows.length === 0 ? (
            <div style={{ padding: '12px 6px' }}>
              <StatusChip tone="dormant">NO MATCHING ARTIFACTS · ADJUST FILTERS</StatusChip>
            </div>
          ) : rows.map((r) => (
            <GalleryCard
              key={r.commitment_hex}
              row={r}
              selected={r.commitment_hex === selectedHex}
              onClick={() => setSelectedHex(r.commitment_hex)}
            />
          ))}
        </div>
      </Panel>

      {/* BOTTOM — proof stage + inspector (top-aligned; each sizes to content
          so the proof card renders full-height and the page scrolls to it) */}
      {selected ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 360px', gap: 16, alignItems: 'start' }}>
          <VpmProofStage row={selected} tamperByte={tamperByte} onText={setSrcText} />
          <VpmInspector
            row={selected}
            srcText={srcText}
            tamperByte={tamperByte}
            onTamper={() => setTamperByte(Math.floor(Math.random() * 256))}
            onReset={() => setTamperByte(null)}
          />
        </div>
      ) : (
        <div style={{ display: 'grid', placeItems: 'center', minHeight: 360 }}>
          <span className="eye" style={{ fontSize: 12, letterSpacing: '0.14em' }}>
            {isError ? 'BRIDGE OFFLINE' : 'SELECT AN ARTIFACT'}
          </span>
        </div>
      )}
    </div>
  )
}
