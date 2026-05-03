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

import { Suspense, useState } from 'react'
import { BrpMount } from '../brp/components/BrpMount'
import { FONTS } from '../shared/design/tokens'
import {
  getMockEnrollmentSession,
  getMockPitlSnapshot,
} from '../brp/mocks/loaders'
import {
  useBrpControllerOrientation,
  useBrpDeviceDiscovery,
  useBrpFrozenOutput,
  useBrpPhgProfile,
  useBrpRecentRecords,
  useBrpRecordPulse,
  useCaptureHealth,
  useEnrollmentStatus,
} from '../api/bridgeApi'

// Synthetic device_id from the vendored fixture. Used as fallback when
// useBrpDeviceDiscovery (commit η) cannot resolve a live device_id from
// the bridge — e.g., when the bridge is offline OR no controller has ever
// connected. Bridge returns 'pending' status for unknown device IDs, so
// the synthetic placeholder still produces valid EnrollmentSession shapes.
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
  // Pull-out indicator drawer; collapsed by default so the renderer
  // claims the full view (matches GamerView PCCDrawer pattern).
  const [drawerOpen, setDrawerOpen] = useState(false)

  // Commit η: device discovery first; downstream hooks consume the
  // discovered ID. When discovery returns null (bridge offline OR no
  // controller seen), fall back to PLACEHOLDER_DEVICE_ID — the bridge
  // returns synthetic-shaped data for unknown IDs, so downstream hooks
  // continue working without errors. Per-prop indicator badges show
  // whether each is on a live or fallback device_id.
  const deviceQuery = useBrpDeviceDiscovery()
  const liveDeviceId = deviceQuery.data?.deviceId ?? null
  const activeDeviceId = liveDeviceId ?? PLACEHOLDER_DEVICE_ID

  const frozen = useBrpFrozenOutput()
  const enrollmentQuery = useEnrollmentStatus(activeDeviceId)
  const recordPulse = useBrpRecordPulse()
  const controllerOrientation = useBrpControllerOrientation(activeDeviceId)
  const recentRecords = useBrpRecentRecords(activeDeviceId)
  const captureHealth = useCaptureHealth()
  const phgProfile = useBrpPhgProfile(activeDeviceId)

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

  // Pulse prop is forwarded to BrpMount only when the WebSocket has produced
  // at least one event. lastPulseTs starts at 0; sending pulse={ts:0,...} on
  // first render would trigger a no-op pulse (ts > 0 check inside AmbientLayer
  // skips it), but we omit the prop entirely to keep the wiring honest:
  // when no pulse stream exists, the renderer is in rotation-only mode.
  const pulse = recordPulse.lastPulseTs > 0
    ? { ts: recordPulse.lastPulseTs, intensity: 1 }
    : undefined
  const pulseSourceKind = recordPulse.connected
    ? 'live'
    : recordPulse.lastPulseTs > 0
      ? 'live-fallback'
      : 'synth'
  const pulseLabel = recordPulse.connected
    ? `WS connected · ${recordPulse.pulseCount} records`
    : recordPulse.lastPulseTs > 0
      ? `WS dropped · last ${recordPulse.pulseCount} records, reconnecting`
      : 'WS not connected (no /ws/records broadcast yet)'

  // Orientation prop wiring: only forward when the hook has actually
  // received frames (controllerOrientation.orientation !== null).
  // When connected but no frames yet (e.g., placeholder device_id with
  // no matching server-side _ws_twin_clients key), we leave orientation
  // unset so AmbientLayer stays in rotation-only mode (commit δ behavior).
  const orientation = controllerOrientation.orientation ?? undefined
  const orientationSourceKind = controllerOrientation.orientation
    ? 'live'
    : controllerOrientation.connected
      ? 'live-fallback'
      : 'synth'
  const orientationLabel = controllerOrientation.orientation
    ? `pitch ${controllerOrientation.orientation.pitch.toFixed(2)}rad · roll ${controllerOrientation.orientation.roll.toFixed(2)}rad · ${controllerOrientation.framesReceived} frames`
    : controllerOrientation.connected
      ? `WS connected · no twin frames yet (device ${liveDeviceId ? 'discovered' : 'placeholder'})`
      : 'WS not connected (no /ws/twin broadcast)'

  // Commit η: device discovery indicator.
  const deviceSourceKind = liveDeviceId
    ? 'live'
    : deviceQuery.error
      ? 'live-fallback'
      : 'synth'
  const deviceLabel = liveDeviceId
    ? `${liveDeviceId.slice(0, 10)}…${liveDeviceId.slice(-8)} · ${deviceQuery.data.deviceCount} device(s) seen`
    : deviceQuery.error
      ? 'bridge offline → using placeholder device_id'
      : deviceQuery.isLoading
        ? 'discovering…'
        : 'no devices in bridge → using placeholder device_id'

  // Commit θ: per-device recent-records indicator. liveDeviceId gates LIVE
  // posture; placeholder fallback reads the synthetic device's records
  // (bridge returns []) which we surface as 'no recent records'.
  const recordsData = recentRecords.data
  const sessionSourceKind = liveDeviceId && recordsData?.records?.length > 0
    ? 'live'
    : recentRecords.error
      ? 'live-fallback'
      : 'synth'
  const sessionLabel = (() => {
    if (!recordsData) return recentRecords.isLoading ? 'loading…' : 'no data'
    if (recordsData.records.length === 0) {
      return liveDeviceId ? 'no records yet for this device' : 'no records (placeholder device)'
    }
    const ageS = recordsData.lastRecordAgeMs != null
      ? Math.round(recordsData.lastRecordAgeMs / 1000)
      : null
    const ageStr = ageS != null ? `last ${ageS}s ago` : 'no timestamp'
    const rate = recordsData.recordsPerMinute > 0
      ? `~${recordsData.recordsPerMinute}/min`
      : 'no rate'
    const anomalyTag = recordsData.anomalyCount > 0
      ? ` · ${recordsData.anomalyCount} anomaly`
      : ''
    return `${recordsData.records.length} recent · ${rate} · ${ageStr}${anomalyTag}`
  })()

  // Commit ι: capture-health palette wiring. The bridge's PCC subsystem
  // (Phase 234.7) classifies host-state from HID poll-rate CV. We forward
  // the kind to BrpMount so the ambient mesh's emissive palette reflects
  // controller<->bridge link health. Omit prop when no health data exists
  // so the renderer stays on the base steel-blue palette.
  const captureData = captureHealth.data
  const hostState = captureData?.host_state
    ? {
        kind: captureData.host_state,
        captureState: captureData.capture_state || 'NOMINAL',
      }
    : undefined
  const hostStateSourceKind = captureData?.host_state
    ? 'live'
    : captureHealth.error
      ? 'live-fallback'
      : 'synth'
  const hostStateLabel = (() => {
    if (!captureData) {
      return captureHealth.isLoading ? 'loading capture-health…' : 'no capture-health data'
    }
    const host = captureData.host_state || 'UNKNOWN'
    const cap = captureData.capture_state || 'UNKNOWN'
    const rate = typeof captureData.poll_rate_hz === 'number'
      ? `${captureData.poll_rate_hz.toFixed(0)}Hz`
      : '—'
    const ready = captureData.grind_ready ? 'grind-ready' : 'not-ready'
    return `${host} · ${cap} · ${rate} · ${ready}`
  })()

  // Commit κ: PHG profile indicator. Bridge returns 404 (→ null) for the
  // placeholder device until first NOMINAL record arrives. liveDeviceId AND
  // a non-null profile gate the LIVE posture.
  const phgData = phgProfile.data
  const phgSourceKind = liveDeviceId && phgData
    ? 'live'
    : phgProfile.error
      ? 'live-fallback'
      : 'synth'
  const phgLabel = (() => {
    if (phgProfile.isLoading) return 'loading…'
    if (!phgData) {
      return liveDeviceId ? 'no profile yet (no NOMINAL records)' : 'no profile (placeholder device)'
    }
    const score = phgData.phg_score ?? 0
    const weighted = phgData.phg_score_weighted ?? 0
    const humanity = typeof phgData.humanity_prob_avg === 'number'
      ? phgData.humanity_prob_avg.toFixed(2)
      : '—'
    const nominal = phgData.nominal_records ?? 0
    const total = phgData.total_records ?? 0
    return `score ${score} (weighted ${weighted}) · humanity ${humanity} · ${nominal}/${total} nominal`
  })()

  // Commit λ: promote PHG profile from drawer-text to renderer-side trust
  // modulation. humanityProbAvg lerps the ambient mesh's resting emissive
  // floor; low-trust devices render dimmer, high-trust devices brighter.
  // Omit prop entirely when no live profile exists so the mesh stays on
  // the static BASE_EMISSIVE_INTENSITY (commit ε behavior).
  const trust = phgData
    ? {
        humanityProbAvg: typeof phgData.humanity_prob_avg === 'number' ? phgData.humanity_prob_avg : 0,
        phgScore: phgData.phg_score ?? 0,
        phgScoreWeighted: phgData.phg_score_weighted ?? 0,
        nominalRecords: phgData.nominal_records ?? 0,
        totalRecords: phgData.total_records ?? 0,
      }
    : undefined

  const indicatorRows = [
    { kind: deviceSourceKind, label: 'device', value: deviceLabel },
    { kind: frozenSourceKind, label: 'frozenOutput', value: frozenLabel },
    { kind: 'synth', label: 'pitlSnapshot', value: 'getMockPitlSnapshot · 7 rows · live composition adapter pending' },
    { kind: enrollmentSourceKind, label: 'enrollmentSession', value: enrollmentLabel },
    { kind: 'operator', label: 'aidThreshold', value: `${AID_THRESHOLD} · Block Z placeholder` },
    { kind: pulseSourceKind, label: 'pulse', value: pulseLabel },
    { kind: orientationSourceKind, label: 'orientation', value: orientationLabel },
    { kind: sessionSourceKind, label: 'session', value: sessionLabel },
    { kind: hostStateSourceKind, label: 'host-state', value: hostStateLabel },
    { kind: phgSourceKind, label: 'phg-profile', value: phgLabel },
  ]

  return (
    <div
      data-testid="brp-view-root"
      style={{
        display: 'flex',
        flexDirection: 'column',
        flex: 1,
        background: '#020408',
        overflow: 'hidden',
        position: 'relative',
      }}
    >
      {/* Renderer fills the whole view; the indicator panel is now a
          right-edge pull-out drawer (matches PCCDrawer / ConsentPanel
          pattern from GamerView). */}
      <main style={{ flex: 1, position: 'relative', minHeight: 0 }}>
        <div style={{ position: 'absolute', inset: 0 }}>
          <Suspense fallback={null}>
            <BrpMount
              frozenOutput={frozenBytes}
              pitlSnapshot={pitlSnapshot}
              enrollmentSession={enrollmentSession}
              aidThreshold={AID_THRESHOLD}
              liveness={liveness}
              {...(pulse ? { pulse } : {})}
              {...(orientation ? { orientation } : {})}
              {...(hostState ? { hostState } : {})}
              {...(trust ? { trust } : {})}
            />
          </Suspense>
        </div>

        {/* Pull-out tab — always visible, anchored to left edge */}
        <div
          onClick={() => setDrawerOpen(!drawerOpen)}
          style={{
            position: 'absolute',
            top: '50%',
            left: drawerOpen ? 320 : 0,
            transform: 'translateY(-50%)',
            width: 28,
            height: 96,
            background: 'rgba(90, 143, 184, 0.18)',
            border: '1px solid rgba(90, 143, 184, 0.4)',
            borderLeft: 'none',
            borderRadius: '0 6px 6px 0',
            cursor: 'pointer',
            zIndex: 11,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'left 0.32s ease',
          }}
          title={drawerOpen ? 'Hide BRP indicators' : 'Show BRP indicators'}
        >
          <span
            style={{
              fontFamily: FONTS.mono,
              fontSize: 8,
              color: '#5a8fb8',
              letterSpacing: '0.16em',
              writingMode: 'vertical-rl',
              transform: 'rotate(180deg)',
              fontWeight: 500,
            }}
          >
            {drawerOpen ? 'BRP ▶' : 'BRP ◀'}
          </span>
        </div>

        {/* Slide-in drawer */}
        <div
          aria-hidden={!drawerOpen}
          style={{
            position: 'absolute',
            top: 0,
            left: drawerOpen ? 0 : -320,
            bottom: 0,
            width: 320,
            zIndex: 10,
            background: '#0a0e14',
            borderRight: '1px solid rgba(90, 143, 184, 0.25)',
            color: '#cce',
            fontFamily: FONTS.mono,
            fontSize: '0.78rem',
            padding: '16px 16px',
            overflowY: 'auto',
            transition: 'left 0.32s ease',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'flex-start',
              marginBottom: '0.75rem',
              gap: '0.5rem',
            }}
          >
            <strong
              style={{
                fontSize: '0.68rem',
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
                color: '#aab',
                lineHeight: 1.4,
              }}
            >
              BRP Renderer · post-milestone (OQ-7)
            </strong>
            <button
              onClick={() => setDrawerOpen(false)}
              style={{
                background: 'transparent',
                border: 'none',
                color: '#aab',
                cursor: 'pointer',
                fontFamily: 'inherit',
                fontSize: 14,
                lineHeight: 1,
                padding: 0,
              }}
              aria-label="Close indicator drawer"
            >×</button>
          </div>

          <div style={{ marginBottom: '0.75rem' }}>
            <LiveFalseBadge />
          </div>

          {indicatorRows.map((row) => (
            <div key={row.label} style={ROW_STYLE}>
              <SourceBadge kind={row.kind} />
              <span style={{ color: '#aab' }}>{row.label}</span>
              <span style={{ color: '#dde', wordBreak: 'break-word' }}>{row.value}</span>
            </div>
          ))}
        </div>
      </main>
    </div>
  )
}
