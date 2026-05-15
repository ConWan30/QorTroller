/**
 * Phase O4-VPM-INT Stream C.1 — VpmRegistryView
 *
 * Two-pane layout per Phase O4 plan section 3 Stream C.1:
 *   Left  pane (~360px wide): filter chips + scrollable list of VPM
 *                             artifacts; each row clickable to select.
 *   Right pane (flex):        sandboxed iframe rendering the selected
 *                             artifact + manifest panel + grammar
 *                             verifier badge.
 *
 * Audit-critical: useVpmList + useVpmManifest are noMock:true (per
 * bridgeApi.js comments) — fabricated entries would corrupt operator
 * audit posture. On bridge offline, the panel shows "Bridge offline /
 * no recorded artifacts" with no fake rows.
 */
import { useState, useRef } from 'react'
import { useVpmList, useVpmManifest } from '../api/bridgeApi'
import { FONTS } from '../shared/design/tokens'
import { VpmFilterChips, VISUAL_STATE_OPTIONS } from '../components/VpmFilterChips'
import { VpmIframe } from '../components/VpmIframe'
import { VpmManifestPanel } from '../components/VpmManifestPanel'
import { VpmGrammarVerifier } from '../components/VpmGrammarVerifier'


// VPM accent (matches the tab accent in ViewSelector.jsx)
const VPM_ACCENT = '#f0a868'

// Build URL for /operator/vpm-artifact/{commit} that the iframe loads via
// src (when srcdoc not used / large artifact). Includes the read-key
// query param so the iframe's HTTP GET passes auth.
function vpmArtifactUrl(commit, readKey) {
  const params = new URLSearchParams()
  if (readKey) params.set('api_key', readKey)
  const qs = params.toString()
  // Doubled-prefix convention per Phase O1 C9 codebase: operator endpoints
  // live under /operator/<inner> at the live URL.
  return `/operator/operator/vpm-artifact/${commit}${qs ? '?' + qs : ''}`
}


function StateBadge({ state }) {
  const opt = VISUAL_STATE_OPTIONS.find((o) => o.value === state) || VISUAL_STATE_OPTIONS[0]
  return (
    <span style={{
      background:    `${opt.color}1a`,
      color:         opt.color,
      border:        `1px solid ${opt.color}40`,
      borderRadius:  3,
      padding:       '1px 5px',
      fontFamily:    FONTS.mono,
      fontSize:      9,
      letterSpacing: '0.05em',
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
        display:        'block',
        width:          '100%',
        textAlign:      'left',
        padding:        '8px 10px',
        background:     selected ? `${VPM_ACCENT}14` : 'transparent',
        border:         selected ? `1px solid ${VPM_ACCENT}50` : '1px solid rgba(255,255,255,0.04)',
        borderRadius:   4,
        cursor:         'pointer',
        marginBottom:   3,
        transition:     'all 0.12s ease',
      }}
    >
      <div style={{
        display:        'flex',
        justifyContent: 'space-between',
        alignItems:     'center',
        gap:            6,
      }}>
        <span style={{
          fontFamily: FONTS.mono,
          fontSize:   11,
          color:      VPM_ACCENT,
          fontWeight: selected ? 600 : 500,
        }}>{row.vpm_id}</span>
        <StateBadge state={row.visual_state} />
      </div>
      <div style={{
        fontFamily: FONTS.mono,
        fontSize:   9,
        color:      'rgba(200,216,232,0.55)',
        marginTop:  3,
        wordBreak:  'break-all',
      }}>
        {row.commitment_hex.slice(0, 32)}…
      </div>
      <div style={{
        fontFamily: FONTS.mono,
        fontSize:   9,
        color:      'rgba(122,138,155,0.65)',
        marginTop:  2,
      }}>
        capture: {row.capture_mode} · zkba_class: {row.zkba_class} · pw: {row.proof_weight}
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

  // The read-key for iframe URL — apiGet() in client.js already appends
  // VITE_VAPI_API_KEY to operator URLs. For srcdoc the auth isn't needed
  // because the HTML is fetched by react-query (auth-injected) + passed
  // into srcdoc. For src= mode we'd need explicit auth in URL; we use
  // src= only as fallback. Today we always use srcdoc.

  return (
    <div data-vpm-registry-view style={{
      flex:           1,
      display:        'flex',
      flexDirection:  'column',
      overflow:       'hidden',
      background:     '#020408',
    }}>
      {/* Header */}
      <div style={{
        padding:       '10px 16px',
        borderBottom:  `1px solid ${VPM_ACCENT}26`,
        background:    'rgba(2,4,8,0.85)',
        display:       'flex',
        alignItems:    'center',
        justifyContent: 'space-between',
      }}>
        <div>
          <span style={{
            fontFamily:    FONTS.display,
            fontSize:      14,
            fontWeight:    600,
            letterSpacing: '0.10em',
            color:         VPM_ACCENT,
          }}>
            VPM REGISTRY
          </span>
          <span style={{
            fontFamily: FONTS.mono,
            fontSize:   9,
            color:      'rgba(200,216,232,0.45)',
            marginLeft: 10,
            letterSpacing: '0.06em',
          }}>
            PHASE O4 · {rows.length} ARTIFACT{rows.length === 1 ? '' : 'S'}
          </span>
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          {selectedRow && (
            <VpmGrammarVerifier
              iframeRef={iframeRef}
              declaredState={selectedRow.visual_state}
            />
          )}
          {listQ.isError && (
            <span data-vpm-bridge-status="offline" style={{
              fontFamily: FONTS.mono,
              fontSize:   10,
              color:      '#d65b78',
              border:     '1px solid #d65b78',
              padding:    '2px 8px',
              borderRadius: 4,
            }}>BRIDGE OFFLINE</span>
          )}
        </div>
      </div>

      {/* Two-pane body */}
      <div style={{
        flex:    1,
        display: 'flex',
        overflow: 'hidden',
      }}>
        {/* LEFT pane: filter chips + list */}
        <div style={{
          width:         360,
          minWidth:      360,
          display:       'flex',
          flexDirection: 'column',
          borderRight:   `1px solid ${VPM_ACCENT}1a`,
          background:    'rgba(2,4,8,0.5)',
        }}>
          <VpmFilterChips
            vpmId={vpmId}
            visualState={visualState}
            onVpmIdChange={setVpmId}
            onVisualStateChange={setVisualState}
          />
          <div style={{
            flex:      1,
            overflowY: 'auto',
            padding:   '8px 10px',
          }}>
            {listQ.isLoading && (
              <div style={{
                fontFamily: FONTS.mono,
                fontSize:   10,
                color:      'rgba(200,216,232,0.4)',
                padding:    '8px',
              }}>loading…</div>
            )}
            {!listQ.isLoading && rows.length === 0 && (
              <div data-vpm-list-empty style={{
                fontFamily: FONTS.mono,
                fontSize:   10,
                color:      'rgba(200,216,232,0.5)',
                padding:    '8px',
              }}>
                No artifacts recorded.<br/>
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

        {/* RIGHT pane: iframe + manifest panel */}
        <div style={{
          flex:          1,
          display:       'flex',
          flexDirection: 'column',
          overflow:      'hidden',
        }}>
          {!selectedRow && (
            <div data-vpm-view-empty style={{
              flex:          1,
              display:       'flex',
              alignItems:    'center',
              justifyContent: 'center',
              fontFamily:    FONTS.mono,
              fontSize:      11,
              color:         'rgba(200,216,232,0.4)',
              letterSpacing: '0.08em',
            }}>
              SELECT AN ARTIFACT
            </div>
          )}
          {selectedRow && (
            <>
              {/* Integrity Nutrition Label panel on TOP — the operator's
                  primary cryptographic-honesty surface. The 9-field
                  FROZEN integrity contract is what makes this protocol
                  defensible, so it deserves the prime above-the-fold
                  position. Fixed height (no scroll bar) since the 9
                  fields + audit-fingerprint footer fit in ~340px;
                  if a future class needs more rows, lift this and
                  re-balance. */}
              <div style={{
                flex:       '0 0 auto',
                padding:    '12px',
                background: 'rgba(10,14,20,0.85)',
                borderBottom: `1px solid ${VPM_ACCENT}1a`,
              }}>
                <VpmManifestPanel
                  manifest={manifestQ.data?.manifest}
                  commitmentHex={selectedCommit}
                />
              </div>
              {/* Iframe takes the remaining space. Iframe loads via src=
                  since the manifest doesn't embed the HTML; the bridge
                  serves it under /operator/operator/vpm-artifact/{commit}.
                  NOTE: in operator-console-internal deployment the
                  iframe inherits the parent origin so the FROZEN
                  sandbox flags allow-scripts+allow-same-origin work.
                  The read-key MUST be passed in the URL because an
                  iframe with src= cannot set custom headers
                  (bridge's _check_read_key requires x-api-key OR
                  query api_key). The earlier null-readKey form
                  surfaced as 403 'Invalid x-api-key header' in the
                  iframe body. Read-key in URL is acceptable here
                  because (a) operator console is internal-only
                  deployment, (b) the same key already appears in
                  every apiGet wrapper's query string. */}
              <div style={{ flex: 1, position: 'relative', minHeight: 0 }}>
                <VpmIframe
                  artifactUrl={vpmArtifactUrl(
                    selectedCommit,
                    import.meta.env.VITE_VAPI_API_KEY,
                  )}
                  onIframeReady={(el) => { iframeRef.current = el }}
                  title={`VPM Artifact ${selectedCommit.slice(0, 12)}`}
                />
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
