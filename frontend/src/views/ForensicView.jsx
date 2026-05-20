// QorTroller Forensic Explorer — QRESCE-0001 v0.5 grant-evaluator remodel.
//
// The workbench. For a grant evaluator, hidden depth is depth not credited —
// so the in-browser cryptographic re-derivation surfaces are shown
// simultaneously, not buried behind tabs:
//
//   TOP ROW    — PoacBodyHasher (THE BYTES: fetch a real 228-byte PoAC record,
//                re-hash body[0:164] live) + CryptoReplayPanel (THE MATH:
//                re-execute FROZEN-v1 verifiers against protocol values,
//                OK/MISMATCH per primitive).
//   BOTTOM ROW — GicChainTimeline (the live grind session's GIC chain) +
//                the FROZEN-v1 verifier registry (the 15 verifiers actually
//                loaded in the browser, from vapi_verifier.js).
//
// Everything here is REAL re-derivation against REAL protocol data via the
// public (unauthenticated) /public/* endpoints + Web Crypto. The design
// export's prototype props (recordId="…", session="GS-…" string, STUB.chainLinks)
// are replaced with the real component contracts:
//   - PoacBodyHasher  : self-contained (its own device_id + counter inputs)
//   - CryptoReplayPanel: session object from usePublicSession(commitment_hex)
//   - GicChainTimeline : grindSessionId (defaults to the LIVE grind session)

import { useState } from 'react'
import { useGrindChain } from '../api/bridgeApi'
import { usePublicSession } from '../api/publicForensic'
import { VERIFIERS, VERIFIER_COUNT } from '../crypto/vapi_verifier'
import PoacBodyHasher from '../components/public/PoacBodyHasher'
import CryptoReplayPanel from '../components/public/CryptoReplayPanel'
import GicChainTimeline from '../components/public/GicChainTimeline'
import { Panel } from '../design/Primitives'
import '../design/qortroller-kit.css'

function CommitmentInput({ value, onChange, onSubmit }) {
  return (
    <div style={{ display: 'flex', gap: 8, padding: '0 0 12px', alignItems: 'center' }}>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value.trim())}
        placeholder="session commitment_hex (64-char) — paste to replay verifiers"
        spellCheck={false}
        style={{
          flex: 1, padding: '7px 10px', fontFamily: 'var(--font-mono)', fontSize: 10,
          background: 'var(--bg)', color: 'var(--text)', border: '1px solid var(--border-strong)',
          borderRadius: 4, letterSpacing: '0.02em',
        }}
      />
      <button
        className="btn btn--secondary btn--sm"
        onClick={onSubmit}
        disabled={!(value && value.length === 64)}
        style={(value && value.length === 64) ? {} : { opacity: 0.4, cursor: 'not-allowed' }}
      >
        REPLAY
      </button>
    </div>
  )
}

export function ForensicView() {
  const { data: grind } = useGrindChain()
  const liveSessionId = grind?.grind_session_id || ''

  const [commitInput, setCommitInput] = useState('')
  const [commitHex, setCommitHex] = useState('')
  const { data: session } = usePublicSession(commitHex, { enabled: Boolean(commitHex) })

  const verifierNames = Object.keys(VERIFIERS)

  return (
    <div className="qt-design-root" style={{ overflow: 'auto' }}>
      {/* Header strip */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
        padding: '14px 16px 0',
      }}>
        <span className="eye" style={{ fontSize: 12, letterSpacing: '0.18em' }}>
          FORENSIC · EXPLORER · IN-BROWSER RE-DERIVATION
        </span>
        <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-faint)' }}>
          SHA-256 · WEB CRYPTO · NO EXTERNAL DEPS · {VERIFIER_COUNT} FROZEN-v1 VERIFIERS
        </span>
      </div>

      <div style={{ display: 'grid', gap: 16, padding: 16 }}>
        {/* ═══ TOP ROW — the workbench (bytes · math) ═══ */}
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.05fr) minmax(0, 1fr)', gap: 16, alignItems: 'start' }}>
          <Panel padding={false}>
            <header className="p-head">
              <span className="p-head__eye">LEFT · THE BYTES</span>
              <span className="p-head__meta">POAC · 228-BYTE RECORD</span>
            </header>
            <div style={{ padding: 16 }}>
              <PoacBodyHasher />
            </div>
          </Panel>

          <Panel padding={false}>
            <header className="p-head">
              <span className="p-head__eye">RIGHT · THE MATH</span>
              <span className="p-head__meta">SHA-256 · WEB CRYPTO · LIVE</span>
            </header>
            <div style={{ padding: 16 }}>
              <CommitmentInput
                value={commitInput}
                onChange={setCommitInput}
                onSubmit={() => setCommitHex(commitInput)}
              />
              {commitHex
                ? <CryptoReplayPanel session={session} />
                : (
                  <div className="mono" style={{
                    padding: 14, fontSize: 10.5, color: 'var(--text-faint)', lineHeight: 1.6,
                    border: '1px dashed var(--border-strong)', borderRadius: 4, textAlign: 'center',
                  }}>
                    Paste a session commitment_hex above and REPLAY to re-execute the
                    FROZEN-v1 verifiers in your browser against the protocol's claimed values.
                    OK = the protocol told the truth; MISMATCH appears immediately on any tampering.
                  </div>
                )}
            </div>
          </Panel>
        </div>

        {/* ═══ BOTTOM ROW — chain + verifier registry ═══ */}
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)', gap: 16, alignItems: 'start' }}>
          <Panel padding={false}>
            <header className="p-head">
              <span className="p-head__eye">GIC · CHAIN · TIMELINE</span>
              <span className="p-head__meta">{liveSessionId ? 'LIVE SESSION' : 'NO LIVE SESSION'}</span>
            </header>
            <div style={{ padding: 16 }}>
              {liveSessionId
                ? <GicChainTimeline grindSessionId={liveSessionId} />
                : (
                  <div className="mono" style={{ fontSize: 10.5, color: 'var(--text-faint)', padding: 8 }}>
                    No live grind session — start the bridge + a grind to populate the GIC chain.
                  </div>
                )}
            </div>
          </Panel>

          <Panel eyebrow="VERIFIERS · REGISTRY" meta="FROZEN · V.A.P.I. v1">
            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8,
              fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-dim)',
            }}>
              {verifierNames.map((name) => (
                <div key={name} style={{
                  padding: '6px 8px', background: 'var(--panel-soft)', borderRadius: 2,
                  border: '1px solid var(--border-soft)', letterSpacing: '0.02em',
                }}>
                  <span style={{ color: 'var(--chain)' }}>●</span>{' '}
                  <span style={{ color: 'var(--text)' }}>{name}</span>
                </div>
              ))}
            </div>
            <div className="label" style={{ marginTop: 12, color: 'var(--text-faint)', lineHeight: 1.5 }}>
              SHA-256 · WEB CRYPTO API · NO EXTERNAL DEPS · ALL ASYNC<br />
              64-CHAR HEX OUTPUT · RE-DERIVED IN-BROWSER · {VERIFIER_COUNT} VERIFIERS LOADED
            </div>
          </Panel>
        </div>
      </div>
    </div>
  )
}
