/**
 * StreamView — gamer witness HUD (PKG-UI-01..03 React SPA).
 *
 * Reads ONLY local CLI snapshots via /stream-ui/* (Vite middleware →
 * ~/.qortroller/ui). Never bridge /agent, never mockBridge liveness.
 * URL-reachable: /?view=stream
 *
 * Named exports. Brand tokens from stream/streamTokens.
 */
import React, { useMemo } from 'react'
import { useViewEyebrow } from '../design/Eyebrow'
import {
  WitnessRespiration,
  ReceiptReveal,
  BirthCeremonyMap,
  useStreamSnapshots,
  STREAM_PAL,
  STREAM_FONTS,
  DEFAULT_STREAM_UI_BASE,
} from '../stream'

/**
 * Resolve stream UI base:
 *   ?streamBase=...  overrides
 *   VITE_STREAM_UI_BASE env
 *   default /stream-ui
 */
function resolveBaseUrl() {
  if (typeof window !== 'undefined') {
    const q = new URLSearchParams(window.location.search).get('streamBase')
    if (q) return q
  }
  try {
    const env = import.meta?.env?.VITE_STREAM_UI_BASE
    if (env) return env
  } catch { /* ignore */ }
  return DEFAULT_STREAM_UI_BASE
}

export function StreamView(props = {}) {
  const baseUrl = props.baseUrl || resolveBaseUrl()
  const snap = useStreamSnapshots({
    baseUrl,
    pollMs: props.pollMs ?? 3000,
    initial: props.initial ?? null,
    fetchImpl: props.fetchImpl,
    enabled: props.enabled !== false,
  })

  const on = snap.stream?.on_screen || {}
  const freshness = on.freshness_class || 'UNKNOWN'
  const eyebrowStatus = useMemo(() => {
    if (freshness === 'LIVE') return { label: 'WITNESS LIVE', tone: 'live' }
    if (freshness === 'FRESH') return { label: 'WITNESS FRESH', tone: 'pending' }
    if (freshness === 'STALE') return { label: 'WITNESS QUIET', tone: 'dim' }
    if (freshness === 'EMPTY') return { label: 'NO CAPTURE', tone: 'dim' }
    return { label: 'UNKNOWN', tone: 'dim' }
  }, [freshness])

  useViewEyebrow({
    num: 'SV',
    name: 'STREAM · WITNESS',
    status: eyebrowStatus.label,
    statusTone: eyebrowStatus.tone,
    readouts: [
      { k: 'NODE', v: on.node_state || '—', tone: 'dim' },
      { k: 'FRESH', v: freshness, tone: freshness === 'LIVE' ? 'live' : 'dim' },
      { k: 'MODE', v: snap.mode || 'EMPTY', tone: 'dim' },
    ],
  })

  return (
    <div
      data-testid="stream-view"
      data-mode={snap.mode}
      data-mock="false"
      data-fabricated-liveness="false"
      data-signing-material="false"
      style={{
        flex: 1,
        overflow: 'auto',
        background: STREAM_PAL.void0,
        color: STREAM_PAL.ink,
        fontFamily: STREAM_FONTS.mono,
        padding: '28px 24px 48px',
      }}
    >
      <div style={{ maxWidth: 760, margin: '0 auto' }}>
        <header style={{ marginBottom: 28 }}>
          <div style={{
            color: STREAM_PAL.amber,
            fontSize: 11,
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
            marginBottom: 8,
          }}>
            QorTroller · Stream
          </div>
          <div style={{ color: STREAM_PAL.dim, fontSize: 11, lineHeight: 1.6 }}>
            Observes CLI JSON only (<code>{baseUrl}</code>). No keys. No consent authority.
            noMock: missing snapshot → UNKNOWN, never fabricated LIVE.
          </div>
        </header>

        {snap.loading ? (
          <div data-testid="stream-loading" style={{ color: STREAM_PAL.dim, fontSize: 12 }}>
            loading local witness state…
          </div>
        ) : null}

        {/* Primary HUD — always show respiration (UNKNOWN when empty) */}
        <section style={{ marginBottom: 32 }} data-testid="stream-hud">
          <WitnessRespiration
            presenceLine={on.presence_line}
            presenceTone={on.presence_tone}
            nodeState={on.node_state}
            freshnessClass={on.freshness_class}
            sessionIdDisplay={on.session_id_display}
            pack={on.pack}
          />
        </section>

        {/* Mode panels */}
        {snap.mode === 'CEREMONY' || (snap.ceremony?._present && !snap.ceremony.ceremony_complete) ? (
          <section style={{ marginBottom: 32 }} data-testid="stream-ceremony-section">
            <BirthCeremonyMap model={snap.ceremony} />
          </section>
        ) : null}

        {snap.mode === 'RECEIPT' || snap.receipt?._present ? (
          <section style={{ marginBottom: 32 }} data-testid="stream-receipt-section">
            <ReceiptReveal
              model={snap.receipt}
              forceComplete={props.forceReceiptComplete === true}
            />
          </section>
        ) : null}

        {snap.mode === 'EMPTY' && !snap.loading ? (
          <section data-testid="stream-empty-help" style={{
            border: `1px solid ${STREAM_PAL.bd}`,
            borderRadius: 6,
            padding: 14,
            color: STREAM_PAL.dim,
            fontSize: 12,
            lineHeight: 1.7,
          }}>
            <div style={{ color: STREAM_PAL.ink, marginBottom: 8 }}>No local stream snapshot yet.</div>
            <div>1. <code>qortroller status --write-ui</code> or <code>qortroller ui</code></div>
            <div>2. Open <code>/?view=stream</code> (this surface) or the offline shell</div>
            <div>3. After a match: <code>qortroller stop</code> then <code>qortroller receipt --write-ui</code></div>
          </section>
        ) : null}

        {/* Rails footer */}
        <footer style={{
          marginTop: 40,
          paddingTop: 16,
          borderTop: `1px solid ${STREAM_PAL.bd}`,
          color: STREAM_PAL.dim,
          fontSize: 10,
          lineHeight: 1.7,
        }}>
          <div>novelty: witness_respiration · deliberately absent: crop counts, FPS, biometrics, grind bars, green-check theater</div>
          <div>F-T66B-1 disclosed on receipt surfaces · PKG-D-06: UI observes CLI, never a second control plane</div>
          {snap.error ? <div data-testid="stream-error">load note: {snap.error}</div> : null}
        </footer>
      </div>
    </div>
  )
}

export default StreamView
