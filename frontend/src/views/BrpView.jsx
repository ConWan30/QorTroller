// BrpView — additive 5th view, post-milestone incorporation per OQ-7.
//
// Track classification: out-of-band-solo. Pre-ceremony incorporation;
// `live: false` posture preserved per Block W.
//
// Phase 238-FRONTEND-V4 (BRP CROWN-JEWEL REVAMP) 2026-05-09:
//   The BRP is the gamer's CRYPTOGRAPHIC PORTRAIT — every polygon of the
//   ambient mesh is derived from PoAC frozenOutput bytes via keccak256.
//   This view is the most QorTroller-distinctive surface because it visualizes
//   the protocol's data as art.
//
// V4 changes vs V3:
//   - All inline hex colors replaced with vapi-theme.css CSS variables
//   - Side drawer moved from left-edge to right-edge (matches PCCDrawer +
//     ConsentPanel pattern from GamerView; left becomes the focal-mesh
//     real estate)
//   - Pull-out handle restyled to match V3 theme (cyan-on-void, JetBrains
//     Mono 11px, 0.08em letterSpacing, glowing dot when active)
//   - Drawer header uses Rajdhani display font + cyan accent matching V3
//   - Cinematic radial vignette toward void at edges
//   - Provenance HUD strip at bottom: device_id[:16] · chain_length=N ·
//     latest_hash[:24] · APOP state (gives the visual its meaning — "this
//     mesh IS your last N PoAC links, hash-projected into 3D space")
//   - SSE event imprinting expanded from gic+curator (V3) to all 5 event
//     types: poac_chain_link / gic_verdict / pcc_state_change /
//     curator_verdict / anchor_confirmed.  Pulses are ADDITIVE on the
//     existing ambient rotation, matching the legacy/ControllerTwin.jsx
//     pattern from V3 C1+C2.
//   - Camera framing fix moved into BrpCanvas (z=4.5, fov=55) so the mesh
//     doesn't kiss viewport edges + drift particle trails up to 50 active
//     particles fade toward void
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

import { Suspense, useEffect, useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { BrpMount } from '../brp/components/BrpMount'
import { FONTS } from '../shared/design/tokens'
import { useTwinStream } from '../api/twinStream'
import {
  getMockEnrollmentSession,
  getMockPitlSnapshot,
} from '../brp/mocks/loaders'
import {
  useActivePlayOccupancy,
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
  padding: '0.3rem 0',
  borderBottom: '1px solid rgba(34, 211, 238, 0.06)',
}

// Phase 238 V4 — SourceBadge using V3 theme tokens (severity palette).
function SourceBadge({ kind }) {
  // kind: 'live' | 'synth' | 'live-fallback' | 'operator'
  const palette = {
    live:           { color: 'var(--vapi-cyan)',         bg: 'rgba(34,211,238,0.10)',  label: 'LIVE' },
    'live-fallback':{ color: 'var(--vapi-warn)',         bg: 'rgba(251,146,60,0.10)',  label: 'LIVE→SYNTH' },
    synth:          { color: 'var(--vapi-tier-basic)',   bg: 'rgba(125,133,144,0.10)', label: 'SYNTH' },
    operator:       { color: 'var(--vapi-orange)',       bg: 'rgba(255,107,0,0.10)',   label: 'OPERATOR' },
  }
  const p = palette[kind] || palette.synth
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '0.15rem 0.45rem',
        background: p.bg,
        color: p.color,
        fontFamily: FONTS.mono,
        fontSize: '9px',
        fontWeight: 700,
        letterSpacing: '0.08em',
        borderRadius: 2,
        minWidth: '5em',
        textAlign: 'center',
        border: `1px solid ${p.color}`,
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
        gap: '0.5rem',
        padding: '0.4rem 0.7rem',
        background: 'rgba(239, 68, 68, 0.10)',
        border: '1px solid var(--vapi-block)',
        color: 'var(--vapi-block)',
        fontFamily: FONTS.mono,
        fontSize: 10,
        fontWeight: 600,
        letterSpacing: '0.05em',
        borderRadius: 3,
      }}
    >
      <motion.span
        animate={{ opacity: [0.4, 1, 0.4] }}
        transition={{ duration: 1.8, repeat: Infinity }}
        style={{
          width: 7,
          height: 7,
          borderRadius: '50%',
          background: 'var(--vapi-block)',
          boxShadow: 'var(--vapi-glow-block)',
          display: 'inline-block',
        }}
      />
      live: false
      <span style={{ opacity: 0.7, fontWeight: 400, fontSize: 9 }}>
        Block W — pre-ceremony, no audit
      </span>
    </div>
  )
}

// Phase 238 V4 — Provenance HUD strip at bottom of view.
// Surfaces device_id, GIC chain length, latest hash, APOP state — gives
// the focal mesh its meaning ("this is your protocol-derived self").
function ProvenanceHUD({ deviceId, frozenHashHex, chainLength, apopState, apopScore, ssePulseTs }) {
  const shortDevice = deviceId
    ? `${deviceId.slice(0, 10)}…${deviceId.slice(-6)}`
    : 'placeholder'
  const shortHash = frozenHashHex
    ? `${frozenHashHex.slice(0, 6)}…${frozenHashHex.slice(-12)}`
    : '—'
  const apopLabel = apopState
    ? `${apopState}${apopScore != null ? ` ${apopScore.toFixed(2)}` : ''}`
    : 'no APOP'

  return (
    <div
      style={{
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        padding: '8px 16px',
        background: 'linear-gradient(180deg, transparent 0%, rgba(10,10,15,0.92) 60%)',
        borderTop: '1px solid rgba(34,211,238,0.10)',
        fontFamily: FONTS.mono,
        fontSize: 10,
        color: 'var(--vapi-tier-basic)',
        letterSpacing: '0.06em',
        zIndex: 5,
        pointerEvents: 'none',
      }}
    >
      <span style={{ color: 'var(--vapi-orange)', fontWeight: 600 }}>BRP</span>
      <span style={{ color: 'var(--vapi-tier-basic)' }}>·</span>
      <span>device <span style={{ color: 'var(--vapi-cyan)' }}>{shortDevice}</span></span>
      <span style={{ color: 'var(--vapi-tier-basic)' }}>·</span>
      <span>chain_len <span style={{ color: 'var(--vapi-cyan)' }}>{chainLength ?? 0}</span></span>
      <span style={{ color: 'var(--vapi-tier-basic)' }}>·</span>
      <span>latest <span style={{ color: 'var(--vapi-cyan)', fontFamily: FONTS.mono }}>{shortHash}</span></span>
      <span style={{ color: 'var(--vapi-tier-basic)' }}>·</span>
      <span>{apopLabel}</span>
      <span style={{ flex: 1 }} />
      {/* SSE pulse indicator — flashes cyan when an event fires */}
      <SsePulseIndicator pulseTs={ssePulseTs} />
      <span style={{ color: 'var(--vapi-tier-basic)', opacity: 0.6, fontSize: 9 }}>
        keccak256(frozenOutput) → mesh
      </span>
    </div>
  )
}

function SsePulseIndicator({ pulseTs }) {
  const [glow, setGlow] = useState(false)
  useEffect(() => {
    if (!pulseTs) return
    setGlow(true)
    const t = setTimeout(() => setGlow(false), 600)
    return () => clearTimeout(t)
  }, [pulseTs])
  return (
    <span
      title={pulseTs ? `last SSE event ${new Date(pulseTs).toLocaleTimeString()}` : 'no SSE event yet'}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        fontSize: 9,
        color: glow ? 'var(--vapi-cyan)' : 'var(--vapi-tier-basic)',
        transition: 'color 0.4s',
      }}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: 3,
          background: glow ? 'var(--vapi-cyan)' : 'var(--vapi-tier-basic)',
          boxShadow: glow ? 'var(--vapi-cyan-glow)' : 'none',
          transition: 'all 0.3s',
        }}
      />
      SSE
    </span>
  )
}

export function BrpView() {
  // Drawer collapsed by default so the renderer claims the full viewport.
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
  const apopQuery = useActivePlayOccupancy()

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

  // Phase 238-FRONTEND-V4 — SSE-driven imprinting layer expanded to all 5
  // event types.  Each event type imprints differently on the ambient mesh:
  //   poac_chain_link  → small cyan pulse  (~120ms, low intensity 0.6)
  //   gic_verdict      → CERTIFY=orange aurora 800ms / FLAG=amber / BLOCK=red+freeze
  //   curator_verdict  → APPROVED=cyan halo / FLAGGED=amber / REJECTED=red
  //   anchor_confirmed → orange-cyan shimmer 1200ms (one-time, high impact)
  //   pcc_state_change → rim color update (sticky until next event)
  //
  // The SSE pulse is forwarded to BrpMount's `pulse` prop, which AmbientLayer
  // treats as an additive intensity boost on the existing rotation/emissive
  // base.  This matches the V3 ControllerTwin pattern: ADDITIVE layering
  // never overrides the existing animations.
  const { lastEvent: sseEvent } = useTwinStream({
    filter: ['poac_chain_link', 'gic_verdict', 'pcc_state_change', 'curator_verdict', 'anchor_confirmed'],
  })
  const [ssePulse, setSsePulse] = useState({ ts: 0, intensity: 0, kind: null, label: null })
  useEffect(() => {
    if (!sseEvent) return
    const { type, data } = sseEvent
    let intensity = 1.0
    let label = type
    if (type === 'poac_chain_link') {
      intensity = 0.6
      label = 'POAC'
    } else if (type === 'gic_verdict') {
      const v = data?.verdict
      intensity = v === 'BLOCK' ? 2.0 : v === 'CERTIFY' ? 1.6 : 1.2
      label = `GIC ${v || ''}`
    } else if (type === 'curator_verdict') {
      const v = data?.verdict
      intensity = v?.startsWith('REJECTED_') ? 1.8 : v?.startsWith('FLAGGED_') ? 1.3 : 1.0
      label = `CUR ${v || ''}`
    } else if (type === 'anchor_confirmed') {
      intensity = 2.4
      label = `ANCHOR ${data?.primitive_type || ''}`
    } else if (type === 'pcc_state_change') {
      intensity = 0.9
      label = `PCC ${data?.host_state || ''}`
    }
    setSsePulse({ ts: Date.now(), intensity, kind: type, label })
  }, [sseEvent])

  // Pulse merge — when SSE event ts is newer than WS pulse ts, use the SSE
  // (with its event-tuned intensity); otherwise prefer the WS pulse stream
  // (1000 Hz cadence; keeps the mesh alive between rare cryptographic events).
  const wsTs   = recordPulse.lastPulseTs
  const useSse = ssePulse.ts > wsTs
  const pulse  = (wsTs > 0 || ssePulse.ts > 0)
    ? { ts: useSse ? ssePulse.ts : wsTs, intensity: useSse ? ssePulse.intensity : 1 }
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

  // Provenance HUD inputs
  const chainLength = recordsData?.records?.length ?? 0
  const apopState = apopQuery.data?.latest_state ?? null
  const apopScore = apopQuery.data?.latest_score ?? null

  return (
    <div
      data-testid="brp-view-root"
      style={{
        display: 'flex',
        flexDirection: 'column',
        flex: 1,
        background: 'var(--vapi-void)',
        overflow: 'hidden',
        position: 'relative',
      }}
    >
      {/* Renderer + cinematic vignette + provenance HUD strip */}
      <main style={{ flex: 1, position: 'relative', minHeight: 0 }}>
        {/* The Canvas itself — fills the entire main */}
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
              {...(apopQuery.data && apopQuery.data.latest_state
                ? {
                    apop: {
                      state: apopQuery.data.latest_state,
                      score: apopQuery.data.latest_score ?? 0,
                      confidence: apopQuery.data.latest_confidence ?? 0,
                      evidence: apopQuery.data.latest_evidence ?? {},
                    },
                  }
                : {})}
            />
          </Suspense>
        </div>

        {/* Cinematic radial vignette — focal mesh draws the eye, edges fade
            to void.  Pointer-events:none so the canvas remains interactive. */}
        <div
          aria-hidden="true"
          style={{
            position: 'absolute',
            inset: 0,
            pointerEvents: 'none',
            background:
              'radial-gradient(ellipse at center, transparent 35%, rgba(10,10,15,0.55) 75%, rgba(10,10,15,0.95) 100%)',
            zIndex: 2,
          }}
        />

        {/* Title chip — top-left, anchored above vignette */}
        <div
          style={{
            position: 'absolute',
            top: 16,
            left: 16,
            zIndex: 3,
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
          }}
        >
          <div style={{
            fontFamily: "'Rajdhani', sans-serif",
            fontSize: 22,
            fontWeight: 700,
            letterSpacing: '0.10em',
            color: 'var(--vapi-cyan)',
            textShadow: '0 0 14px rgba(34,211,238,0.45)',
          }}>
            BRP
          </div>
          <div style={{
            fontFamily: FONTS.mono,
            fontSize: 9,
            color: 'var(--vapi-tier-basic)',
            letterSpacing: '0.08em',
          }}>
            BIOMETRIC RENDERER · cryptographic portrait
          </div>
        </div>

        {/* SSE event toast — top-center, slides in when an event fires */}
        <SseEventToast pulse={ssePulse} />

        {/* Pull-out handle — RIGHT EDGE, V4 theme tokens, matches V3
            CuratorReviewLog handle pattern (bottom-left) but mirrored to
            right-edge to keep focal mesh undisturbed when drawer closed. */}
        <button
          onClick={() => setDrawerOpen(!drawerOpen)}
          style={{
            position: 'absolute',
            top: '50%',
            right: drawerOpen ? 380 : 0,
            transform: 'translateY(-50%)',
            width: 32,
            height: 110,
            background: 'rgba(34, 211, 238, 0.08)',
            border: `1px solid ${drawerOpen ? 'var(--vapi-cyan)' : 'rgba(34, 211, 238, 0.35)'}`,
            borderRight: 'none',
            borderRadius: '6px 0 0 6px',
            cursor: 'pointer',
            zIndex: 11,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 6,
            transition: 'right 0.32s ease, background 0.2s, border-color 0.2s',
            color: 'var(--vapi-cyan)',
            fontFamily: 'inherit',
            padding: 0,
          }}
          title={drawerOpen ? 'Hide BRP indicators' : 'Show BRP indicators'}
          aria-label={drawerOpen ? 'Hide BRP indicators' : 'Show BRP indicators'}
        >
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: 3.5,
              background: 'var(--vapi-cyan)',
              boxShadow: drawerOpen ? 'var(--vapi-cyan-glow)' : 'none',
              transition: 'box-shadow 0.3s',
            }}
          />
          <span
            style={{
              fontFamily: FONTS.mono,
              fontSize: 10,
              color: 'var(--vapi-cyan)',
              letterSpacing: '0.18em',
              writingMode: 'vertical-rl',
              transform: 'rotate(180deg)',
              fontWeight: 600,
            }}
          >
            INDICATORS
          </span>
        </button>

        {/* Slide-in drawer — RIGHT EDGE, V4 theme tokens */}
        <AnimatePresence>
          {drawerOpen && (
            <motion.div
              key="brp-drawer"
              initial={{ x: 380, opacity: 0 }}
              animate={{ x: 0,   opacity: 1 }}
              exit={{    x: 380, opacity: 0 }}
              transition={{ duration: 0.28, ease: 'easeOut' }}
              aria-hidden={!drawerOpen}
              style={{
                position: 'absolute',
                top: 0,
                right: 0,
                bottom: 36, // leave room for provenance HUD strip
                width: 380,
                zIndex: 10,
                background: 'rgba(8, 10, 14, 0.97)',
                backdropFilter: 'blur(14px)',
                borderLeft: '1px solid var(--vapi-cyan)',
                color: 'var(--vapi-tier-verified)',
                fontFamily: FONTS.mono,
                fontSize: 11,
                padding: '20px 18px',
                overflowY: 'auto',
                boxShadow: '0 0 28px rgba(34,211,238,0.10)',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  marginBottom: 14,
                  gap: 8,
                }}
              >
                <div>
                  <div
                    style={{
                      fontFamily: "'Rajdhani', sans-serif",
                      fontSize: 16,
                      fontWeight: 700,
                      letterSpacing: '0.10em',
                      color: 'var(--vapi-cyan)',
                      lineHeight: 1.1,
                    }}
                  >
                    BRP INDICATORS
                  </div>
                  <div
                    style={{
                      fontSize: 9,
                      letterSpacing: '0.06em',
                      color: 'var(--vapi-tier-basic)',
                      marginTop: 3,
                    }}
                  >
                    post-milestone (OQ-7) · per-prop honesty
                  </div>
                </div>
                <button
                  onClick={() => setDrawerOpen(false)}
                  style={{
                    background: 'transparent',
                    border: '1px solid rgba(34, 211, 238, 0.25)',
                    borderRadius: 3,
                    color: 'var(--vapi-cyan)',
                    cursor: 'pointer',
                    fontFamily: 'inherit',
                    fontSize: 12,
                    lineHeight: 1,
                    padding: '4px 8px',
                  }}
                  aria-label="Close indicator drawer"
                >×</button>
              </div>

              <div style={{ marginBottom: 14 }}>
                <LiveFalseBadge />
              </div>

              <div style={{
                fontSize: 9,
                color: 'var(--vapi-tier-basic)',
                letterSpacing: '0.06em',
                marginBottom: 6,
                textTransform: 'uppercase',
              }}>
                Per-Prop Indicators
              </div>

              {indicatorRows.map((row) => (
                <div key={row.label} style={ROW_STYLE}>
                  <SourceBadge kind={row.kind} />
                  <span style={{ color: 'var(--vapi-tier-basic)' }}>{row.label}</span>
                  <span style={{
                    color: 'var(--vapi-tier-verified)',
                    wordBreak: 'break-word',
                    fontSize: 10,
                  }}>{row.value}</span>
                </div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Provenance HUD bottom strip — gives the visual its meaning */}
        <ProvenanceHUD
          deviceId={activeDeviceId}
          frozenHashHex={frozen.hashHex}
          chainLength={chainLength}
          apopState={apopState}
          apopScore={apopScore}
          ssePulseTs={ssePulse.ts}
        />
      </main>
    </div>
  )
}

// SSE event toast — slides down from top-center, fades after 1.6s
function SseEventToast({ pulse }) {
  const [visible, setVisible] = useState(false)
  const [latest, setLatest] = useState(null)
  useEffect(() => {
    if (!pulse?.ts || pulse.ts === 0) return
    setLatest(pulse)
    setVisible(true)
    const t = setTimeout(() => setVisible(false), 1600)
    return () => clearTimeout(t)
  }, [pulse?.ts])

  if (!latest) return null
  const color =
    latest.kind === 'gic_verdict' ? 'var(--vapi-orange)' :
    latest.kind === 'curator_verdict' ? 'var(--vapi-cyan)' :
    latest.kind === 'anchor_confirmed' ? 'var(--vapi-tier-premium)' :
    latest.kind === 'pcc_state_change' ? 'var(--vapi-amber)' :
    'var(--vapi-cyan)'

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          key={latest.ts}
          initial={{ y: -30, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: -30, opacity: 0 }}
          transition={{ duration: 0.24 }}
          style={{
            position: 'absolute',
            top: 18,
            left: '50%',
            transform: 'translateX(-50%)',
            zIndex: 4,
            padding: '6px 14px',
            background: 'rgba(8,10,14,0.85)',
            backdropFilter: 'blur(8px)',
            border: `1px solid ${color}`,
            borderRadius: 4,
            color: color,
            fontFamily: FONTS.mono,
            fontSize: 10,
            letterSpacing: '0.08em',
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: 3,
              background: color,
              boxShadow: `0 0 10px ${color}`,
            }}
          />
          {latest.label}
        </motion.div>
      )}
    </AnimatePresence>
  )
}
