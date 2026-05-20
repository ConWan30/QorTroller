/**
 * VPM Registry — QRESCE-0001 v0.5 grant-evaluator remodel.
 *
 * Verified Projection Media: the protocol AUTONOMOUSLY compiles HTML snapshot
 * proofs (one per ZKBA artifact / MLGA gameplay session) and records each in a
 * registry with a 9-field FROZEN Integrity Nutrition Label + a client-side
 * tamper-detect hash. This view makes that autonomous output legible:
 *
 *   LEFT  — filter chips + scrollable list of compiled artifacts.
 *   RIGHT — for the selected artifact:
 *             • the Integrity Label (real in-browser HASH OK/MISMATCH check)
 *             • a clearly-framed "AUTONOMOUS HTML SNAPSHOT PROOF" — the
 *               compiled artifact rendered in a sandboxed iframe, with the
 *               visual-grammar verifier confirming the rendered DOM matches
 *               the declared visual state.
 *
 * Chrome ported to the .qt-design-root design language (Syne + Panel + void)
 * to match Gamer/Forensic/Operator. All wiring preserved: useVpmList +
 * useVpmManifest (noMock:true), vpmArtifactUrl, VpmFilterChips, VpmIframe,
 * VpmManifestPanel, VpmGrammarVerifier, and every data-testid.
 */
import { useState, useRef } from 'react'
import { useVpmList, useVpmManifest } from '../api/bridgeApi'
import { VpmFilterChips, VISUAL_STATE_OPTIONS } from '../components/VpmFilterChips'
import { VpmIframe } from '../components/VpmIframe'
import { VpmManifestPanel } from '../components/VpmManifestPanel'
import { VpmGrammarVerifier } from '../components/VpmGrammarVerifier'
import { Panel, StatusChip } from '../design/Primitives'
import '../design/qortroller-kit.css'

// Build URL for /operator/vpm-artifact/{commit} the iframe loads via src.
// Includes the read-key query param so the iframe's HTTP GET passes auth.
function vpmArtifactUrl(commit, readKey) {
  const params = new URLSearchParams()
  if (readKey) params.set('api_key', readKey)
  const qs = params.toString()
  // Doubled-prefix convention per Phase O1 C9: operator endpoints live under
  // /operator/<inner> at the live URL.
  return `/operator/operator/vpm-artifact/${commit}${qs ? '?' + qs : ''}`
}

function StateBadge({ state }) {
  const opt = VISUAL_STATE_OPTIONS.find((o) => o.value === state) || VISUAL_STATE_OPTIONS[0]
  return (
    <span style={{
      background: `${opt.color}1a`,
      color: opt.color,
      border: `1px solid ${opt.color}40`,
      borderRadius: 3,
      padding: '1px 6px',
      fontFamily: 'var(--font-mono)',
      fontSize: 9,
      letterSpacing: '0.05em',
      whiteSpace: 'nowrap',
    }}>
      {opt.label}
    </span>
  )
}

function VpmListRow({ row, selected, onSelect }) {
  return (
    <button
      data-vpm-list-row={row.commitment_hex}
      onClick={() => onSelect(row.commitment_hex)}
      style={{
        display: 'block',
        width: '100%',
        textAlign: 'left',
        padding: '9px 11px',
        background: selected ? 'var(--accent-amber-trace)' : 'transparent',
        border: `1px solid ${selected ? 'var(--accent-amber)' : 'var(--border-soft)'}`,
        borderRadius: 4,
        cursor: 'pointer',
        marginBottom: 4,
        transition: 'all 0.12s ease',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6 }}>
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 11,
          color: 'var(--accent-amber)',
          fontWeight: selected ? 600 : 500,
        }}>{row.vpm_id}</span>
        <StateBadge state={row.visual_state} />
      </div>
      <div style={{
        fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-dim)',
        marginTop: 4, wordBreak: 'break-all',
      }}>
        {row.commitment_hex.slice(0, 32)}…
      </div>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-faint)', marginTop: 2 }}>
        capture: {row.capture_mode} · zkba: {row.zkba_class} · pw: {row.proof_weight}
      </div>
    </button>
  )
}

export function VpmRegistryView() {
  const [vpmId, setVpmId] = useState('')
  const [visualState, setVisualState] = useState('')
  const [selectedCommit, setSelectedCommit] = useState(null)
  const iframeRef = useRef(null)

  const listQ = useVpmList({ vpmId, visualState, limit: 100 })
  const manifestQ = useVpmManifest(selectedCommit, { enabled: Boolean(selectedCommit) })

  const rows = listQ.data?.rows || []
  const selectedRow = rows.find((r) => r.commitment_hex === selectedCommit) || null

  return (
    <div data-vpm-registry-view className="qt-design-root" style={{
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
    }}>
      {/* Header strip */}
      <div className="p-head" style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
          <span style={{
            fontFamily: 'var(--font-display)', fontSize: 16, fontWeight: 700,
            letterSpacing: '0.04em', color: 'var(--accent-amber)',
          }}>VPM REGISTRY</span>
          <span className="p-head__eye">AUTONOMOUS · HTML · SNAPSHOT · PROOFS</span>
          <span className="p-head__meta">{rows.length} ARTIFACT{rows.length === 1 ? '' : 'S'}</span>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {selectedRow && (
            <VpmGrammarVerifier iframeRef={iframeRef} declaredState={selectedRow.visual_state} />
          )}
          {listQ.isError && (
            <span data-vpm-bridge-status="offline">
              <StatusChip tone="blocked">BRIDGE OFFLINE</StatusChip>
            </span>
          )}
        </div>
      </div>

      {/* Two-pane body */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* LEFT — filters + list */}
        <div style={{
          width: 360, minWidth: 360, display: 'flex', flexDirection: 'column',
          borderRight: '1px solid var(--border)', background: 'var(--panel-soft)',
        }}>
          <VpmFilterChips
            vpmId={vpmId}
            visualState={visualState}
            onVpmIdChange={setVpmId}
            onVisualStateChange={setVisualState}
          />
          <div style={{ flex: 1, overflowY: 'auto', padding: '8px 10px' }}>
            {listQ.isLoading && (
              <div className="mono" style={{ fontSize: 10, color: 'var(--text-faint)', padding: 8 }}>loading…</div>
            )}
            {!listQ.isLoading && rows.length === 0 && (
              <div data-vpm-list-empty className="mono" style={{ fontSize: 10, color: 'var(--text-faint)', padding: 8, lineHeight: 1.6 }}>
                No artifacts recorded.<br />
                The compiler emits one VPM proof per ZKBA artifact / MLGA session.<br />
                POST /operator/vpm-compile to populate the registry.
              </div>
            )}
            {rows.map((row) => (
              <VpmListRow
                key={row.commitment_hex}
                row={row}
                selected={row.commitment_hex === selectedCommit}
                onSelect={setSelectedCommit}
              />
            ))}
          </div>
        </div>

        {/* RIGHT — integrity label + framed HTML snapshot proof */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', background: 'var(--bg)' }}>
          {!selectedRow && (
            <div data-vpm-view-empty style={{
              flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center',
              justifyContent: 'center', gap: 8,
            }}>
              <span className="eye" style={{ fontSize: 12, letterSpacing: '0.18em' }}>SELECT AN ARTIFACT</span>
              <span className="mono" style={{ fontSize: 10, color: 'var(--text-faint)' }}>
                each row is an autonomously-compiled, independently-verifiable HTML proof
              </span>
            </div>
          )}
          {selectedRow && (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', padding: 16, gap: 12 }}>
              {/* Integrity Nutrition Label — the cryptographic-honesty surface
                  (real in-browser HASH OK/MISMATCH). Prime above-the-fold. */}
              <div style={{ flex: '0 0 auto' }}>
                <VpmManifestPanel manifest={manifestQ.data?.manifest} commitmentHex={selectedCommit} />
              </div>

              {/* The autonomous HTML snapshot proof, explicitly framed. */}
              <Panel padding={false} style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                <header className="p-head">
                  <span className="p-head__eye">AUTONOMOUS · HTML · SNAPSHOT · PROOF</span>
                  <span className="p-head__meta">
                    {selectedRow.vpm_id} · <StateBadge state={selectedRow.visual_state} />
                  </span>
                </header>
                <div className="mono" style={{
                  padding: '6px 14px', fontSize: 9.5, color: 'var(--text-faint)',
                  borderBottom: '1px solid var(--border-soft)', letterSpacing: '0.04em',
                }}>
                  rendered in a sandboxed iframe · DOM re-verified against declared visual state · keccak/SHA-256 anchored
                </div>
                <div style={{ flex: 1, position: 'relative', minHeight: 0 }}>
                  <VpmIframe
                    artifactUrl={vpmArtifactUrl(selectedCommit, import.meta.env.VITE_VAPI_API_KEY)}
                    onIframeReady={(el) => { iframeRef.current = el }}
                    title={`VPM Artifact ${selectedCommit.slice(0, 12)}`}
                  />
                </div>
              </Panel>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
