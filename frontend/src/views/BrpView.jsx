// BrpView — additive 4th view, post-milestone incorporation per OQ-7.
//
// Track classification: out-of-band-solo. Pre-ceremony incorporation;
// `live: false` posture preserved per Block W.
//
// This view consumes:
//   - frozenOutput     <- LIVE      useBrpFrozenOutput (GIC chain hash)
//   - pitlSnapshot     <- SYNTHETIC getMockPitlSnapshot (live composition
//                                    adapter is a follow-up commit)
//   - enrollmentSession<- LIVE      useEnrollmentStatus (with synth fallback)
//   - aidThreshold     <- OPERATOR  0.65 placeholder (Block Z deferred)
//   - liveness         <- all false (Block W: pre-ceremony, no audit)
//
// Per-prop honesty-first indicator: the visible indicator panel labels
// each prop's data source distinctly from Block W's audit-state badge.
// Two distinct claims, both surfaced visibly.

import { Suspense } from 'react'
import { BrpMount } from '../brp/components/BrpMount'
import {
  getMockEnrollmentSession,
  getMockPitlSnapshot,
} from '../brp/mocks/loaders'
import { useBrpFrozenOutput, useEnrollmentStatus } from '../api/bridgeApi'

// Synthetic device_id from the vendored fixture. Bridge will return
// 'pending' status for unknown device — the hook's adapter shapes
// that into a valid EnrollmentSession either way.
const PLACEHOLDER_DEVICE_ID =
  '0x0000000000000000000000000000000000000000000000000000000000000001'

// Locked seed fallback — 32-zero-byte canonical vector from
// solo/brp-renderer/src/hash/__tests__/deriveBrpSeed.test.ts: 0x87b0f938.
const FALLBACK_FROZEN_OUTPUT = new Uint8Array(32)

// Block Z placeholder (operator-set; ceremony picks the real metric).
const AID_THRESHOLD = 0.65

const ROW_STYLE = {
  display: 'grid',
  gridTemplateColumns: 'auto 7em 1fr',
  alignItems: 'baseline',
  gap: '0.5rem',
  padding: '0.25rem 0',
}

function SourceBadge({ kind }) {
  // kind: 'live' | 'synth' | 'live-fallback' | 'operator'
  const palette = {
    live:           { bg: '#0e3a2c', fg: '#9be8c4', label: 'LIVE' },
    'live-fallback':{ bg: '#3a2e0e', fg: '#e8d49b', label: 'LIVE→SYNTH' },
    synth:          { bg: '#2a2a3a', fg: '#bcc4d4', label: 'SYNTH' },
    operator:       { bg: '#1f2a3a', fg: '#9bc4e8', label: 'OPERATOR' },
  }
  const p = palette[kind] || palette.synth
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '0.1rem 0.4rem',
        background: p.bg,
        color: p.fg,
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
        fontSize: '0.65rem',
        fontWeight: 700,
        letterSpacing: '0.06em',
        borderRadius: '3px',
        minWidth: '5em',
        textAlign: 'center',
      }}
    >
      {p.label}
    </span>
  )
}

function LiveFalseBadge() {
  return (
    <div
      data-testid="brp-view-live-false-banner"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.4rem',
        padding: '0.3rem 0.6rem',
        background: 'rgba(180, 60, 60, 0.18)',
        border: '1px solid rgba(220, 100, 100, 0.4)',
        color: '#e8a8a8',
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
        fontSize: '0.72rem',
        fontWeight: 600,
        letterSpacing: '0.04em',
        borderRadius: '4px',
      }}
    >
      <span
        style={{
          width: '0.5rem',
          height: '0.5rem',
          borderRadius: '50%',
          background: '#e85a5a',
          display: 'inline-block',
        }}
      />
      live: false &nbsp;
      <span style={{ opacity: 0.7, fontWeight: 400 }}>
        Block W — pre-ceremony, no audit
      </span>
    </div>
  )
}

export function BrpView() {
  const frozen = useBrpFrozenOutput()
  const enrollmentQuery = useEnrollmentStatus(PLACEHOLDER_DEVICE_ID)

  // Resolve frozenOutput: live bytes when chain has a hash; locked-seed
  // canonical fallback otherwise.
  const frozenBytes = frozen.bytes ?? FALLBACK_FROZEN_OUTPUT
  const frozenSourceKind = frozen.bytes ? 'live' : 'synth'
  const frozenLabel = frozen.hashHex
    ? `GIC · …${frozen.hashHex.slice(-12)}`
    : '32-zero-byte canonical (seed 0x87b0f938)'

  // Resolve enrollmentSession: live data when bridge responds OK; synthetic
  // fixture fallback when bridge is offline.
  const liveEnrollment = enrollmentQuery.data
  const enrollmentSession = liveEnrollment ?? getMockEnrollmentSession()
  const enrollmentSourceKind = liveEnrollment
    ? 'live'
    : enrollmentQuery.error
      ? 'live-fallback'
      : 'synth'
  const enrollmentLabel = liveEnrollment
    ? `${liveEnrollment.status} · ${liveEnrollment.sessionsNominal}/${liveEnrollment.requiredSessions}`
    : enrollmentQuery.error
      ? 'bridge offline → synthetic fixture'
      : 'loading…'

  // pitlSnapshot is synthetic in this incorporation — live composition
  // adapter is deferred to a follow-up commit.
  const pitlSnapshot = getMockPitlSnapshot()

  // Per Block W: liveness flags all false until ceremony audit.
  const liveness = { ambient: false, legibility: false, telemetry: false }

  return (
    <div
      data-testid="brp-view-root"
      style={{
        display: 'flex',
        flexDirection: 'column',
        flex: 1,
        background: '#020408',
        overflow: 'hidden',
      }}
    >
      {/* Honesty-first indicator panel — shown at top, separate from BrpMount */}
      <header
        style={{
          padding: '0.75rem 1rem',
          background: '#0a0e14',
          borderBottom: '1px solid rgba(90, 143, 184, 0.18)',
          color: '#cce',
          fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
          fontSize: '0.78rem',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '0.5rem',
          }}
        >
          <strong style={{ fontSize: '0.72rem', letterSpacing: '0.08em', textTransform: 'uppercase', color: '#aab' }}>
            BRP Renderer · post-milestone incorporation (OQ-7)
          </strong>
          <LiveFalseBadge />
        </div>

        <div style={ROW_STYLE}>
          <SourceBadge kind={frozenSourceKind} />
          <span style={{ color: '#aab' }}>frozenOutput</span>
          <span style={{ color: '#dde' }}>{frozenLabel}</span>
        </div>
        <div style={ROW_STYLE}>
          <SourceBadge kind="synth" />
          <span style={{ color: '#aab' }}>pitlSnapshot</span>
          <span style={{ color: '#dde' }}>
            getMockPitlSnapshot · 7 rows · live composition adapter pending
          </span>
        </div>
        <div style={ROW_STYLE}>
          <SourceBadge kind={enrollmentSourceKind} />
          <span style={{ color: '#aab' }}>enrollmentSession</span>
          <span style={{ color: '#dde' }}>{enrollmentLabel}</span>
        </div>
        <div style={ROW_STYLE}>
          <SourceBadge kind="operator" />
          <span style={{ color: '#aab' }}>aidThreshold</span>
          <span style={{ color: '#dde' }}>{AID_THRESHOLD} · Block Z placeholder</span>
        </div>
      </header>

      {/* The actual renderer */}
      <main style={{ flex: 1, position: 'relative' }}>
        <Suspense fallback={null}>
          <BrpMount
            frozenOutput={frozenBytes}
            pitlSnapshot={pitlSnapshot}
            enrollmentSession={enrollmentSession}
            aidThreshold={AID_THRESHOLD}
            liveness={liveness}
          />
        </Suspense>
      </main>
    </div>
  )
}
