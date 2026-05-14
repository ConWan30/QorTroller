import { useState, useEffect, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  useCaptureHealth,
  useGrindChain,
  useGrindAnalytics,
  useTournamentPreflight,
  useFleetCoherenceStatus,
  useProtocolCoherence,
  useOperatorActivation,
  useDriftLog,
  useOperatorDrafts,
  useFleetReadinessRoot,
  useCuratorStatus,
  useCuratorFlaggedListings,
} from '../api/bridgeApi'
import { FONTS, DEVELOPER } from '../shared/design/tokens'
import { PIPELINE_NODE_CONTAINER, PIPELINE_NODE, DRAWER_SLIDE_LEFT } from '../shared/design/animations'
import { OperatorAgentsDrawer, OperatorAgentsDrawerHandle } from '../components/OperatorAgentsDrawer'
import { DraftReviewDrawer, DraftReviewDrawerHandle } from '../components/DraftReviewDrawer'
import { O3ReadinessDrawer, O3ReadinessDrawerHandle } from '../components/O3ReadinessDrawer'
import { AuditHarnessesDrawer, AuditHarnessesDrawerHandle } from '../components/AuditHarnessesDrawer'
import { useCuratorGraduationReadiness } from '../api/bridgeApi'

// ─── Design primitives ───────────────────────────────────────────────────────

function Glass({ children, style, accent = DEVELOPER.orange, intensity = 1 }) {
  return (
    <div style={{
      background: `linear-gradient(180deg, rgba(12,6,2,${0.60 * intensity}) 0%, rgba(3,5,7,${0.78 * intensity}) 100%)`,
      backdropFilter: 'blur(14px) saturate(130%)',
      border: `1px solid ${accent}26`,
      borderRadius: 8,
      boxShadow: `0 0 24px ${accent}1a, inset 0 1px 0 rgba(255,255,255,0.03)`,
      ...style,
    }}>
      {children}
    </div>
  )
}

function StatusChip({ label, value, accent = DEVELOPER.orange, onClick, active }) {
  return (
    <Glass
      accent={accent}
      style={{
        padding: '5px 10px',
        cursor: onClick ? 'pointer' : 'default',
        outline: active ? `1px solid ${accent}55` : 'none',
      }}
      onClick={onClick}
    >
      <div style={{ fontFamily: FONTS.mono, letterSpacing: '0.16em', fontSize: 6.5, color: DEVELOPER.t3, textTransform: 'uppercase', marginBottom: 2 }}>{label}</div>
      <div style={{ fontFamily: FONTS.mono, fontSize: 10, fontWeight: 600, color: accent, whiteSpace: 'nowrap' }}>{value}</div>
    </Glass>
  )
}

function DrawerStat({ label, value, accent = DEVELOPER.orange }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 0', borderBottom: `1px solid ${DEVELOPER.bd}` }}>
      <span style={{ fontFamily: FONTS.mono, fontSize: 8, color: DEVELOPER.t3 }}>{label}</span>
      <span style={{ fontFamily: FONTS.mono, fontSize: 10, fontWeight: 600, color: accent }}>{value}</span>
    </div>
  )
}

// ─── Pipeline canvas ──────────────────────────────────────────────────────────

const NODE_LABELS = ['CAPTURE', 'ADJUDICATE', 'VALIDATE', 'GIC STAMP', 'ON-CHAIN']
// x-center of each node as fraction of canvas width (for connector + particle calc)
const NODE_X = [0.09, 0.29, 0.49, 0.69, 0.89]
const NODE_Y = 0.50   // vertical center fraction

function PipelineConnector({ x0, x1, y, width, height, active, accent, particleCount = 3 }) {
  const px0 = x0 * width
  const px1 = x1 * width
  const py  = y  * height

  return (
    <g>
      {/* Connector line */}
      <line
        x1={px0} y1={py}
        x2={px1} y2={py}
        stroke={active ? `${accent}55` : `${accent}18`}
        strokeWidth={active ? 1.5 : 1}
        strokeDasharray={active ? 'none' : '4 6'}
      />
      {/* Animated particles */}
      {active && Array.from({ length: particleCount }, (_, i) => (
        <motion.circle
          key={i}
          cx={px0}
          cy={py}
          r={2}
          fill={accent}
          filter={`drop-shadow(0 0 3px ${accent})`}
          animate={{ cx: [px0, px1] }}
          transition={{
            duration: 2.4,
            delay: i * (2.4 / particleCount),
            repeat: Infinity,
            ease: 'linear',
          }}
          opacity={0.85}
        />
      ))}
    </g>
  )
}

function PipelineCanvas({ stages, width, height }) {
  const accent = DEVELOPER.orange

  return (
    <svg
      width={width}
      height={height}
      style={{ position: 'absolute', top: 0, left: 0, pointerEvents: 'none' }}
    >
      {/* Connectors between nodes */}
      {NODE_X.slice(0, -1).map((x, i) => {
        const stageActive = stages[i]?.status === 'ACTIVE' && stages[i + 1]?.status !== 'DEAD'
        return (
          <PipelineConnector
            key={i}
            x0={x + 0.063}
            x1={NODE_X[i + 1] - 0.063}
            y={NODE_Y}
            width={width}
            height={height}
            active={stageActive}
            accent={accent}
            particleCount={stageActive ? 3 : 0}
          />
        )
      })}
    </svg>
  )
}

// ─── Right drawer — isFullyEligible() gate conditions ─────────────────────────

const PREFLIGHT_LABELS = {
  separation_ok:         'Separation ratio > min',
  l4_ok:                 'L4 calibration valid',
  gate_ok:               'Dual primitive gate',
  cert_ok:               'Device cert registered',
  audit_ok:              'Ceremony audit clean',
  biometric_ttl_ok:      'Biometric TTL valid',
  all_pairs_p0_ok:       'All pairs > 1.0',
  ait_defensibility_ok:  'AIT defensibility (N≥10)',
}

function GateDrawer({ open, onClose, preflight }) {
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.35)', zIndex: 30 }}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.div
            style={{
              position: 'fixed', top: '50%', right: 16,
              transform: 'translateY(-50%)',
              width: 280, zIndex: 31,
            }}
            initial={{ x: 320, opacity: 0 }}
            animate={{ x: 0, opacity: 1, transition: { duration: 0.2, ease: 'easeOut' } }}
            exit={{ x: 320, opacity: 0, transition: { duration: 0.15 } }}
          >
            <Glass accent={DEVELOPER.orange} style={{ padding: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <span style={{ fontFamily: FONTS.display, fontSize: 13, fontWeight: 600, color: DEVELOPER.t1, letterSpacing: '0.08em' }}>isFullyEligible() GATE</span>
                <span
                  style={{ fontFamily: FONTS.mono, fontSize: 8, color: DEVELOPER.t3, cursor: 'pointer', padding: '2px 6px' }}
                  onClick={onClose}
                >✕</span>
              </div>

              {preflight ? (
                <div>
                  {Object.entries(PREFLIGHT_LABELS).map(([key, label]) => {
                    const val = preflight[key]
                    return (
                      <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '5px 0', borderBottom: `1px solid ${DEVELOPER.bd}` }}>
                        <span style={{ fontFamily: FONTS.mono, fontSize: 8, color: DEVELOPER.t2 }}>{label}</span>
                        <span style={{
                          fontFamily: FONTS.mono, fontSize: 9, fontWeight: 700,
                          color: val === true ? DEVELOPER.green : val === false ? DEVELOPER.red : DEVELOPER.t3,
                        }}>
                          {val === true ? 'PASS' : val === false ? 'FAIL' : '–'}
                        </span>
                      </div>
                    )
                  })}

                  <div style={{ marginTop: 10 }}>
                    <DrawerStat
                      label="OVERALL"
                      value={preflight.overall_pass ? 'PASS' : 'FAIL'}
                      accent={preflight.overall_pass ? DEVELOPER.green : DEVELOPER.red}
                    />
                  </div>
                </div>
              ) : (
                <div style={{ fontFamily: FONTS.mono, fontSize: 9, color: DEVELOPER.t3, textAlign: 'center', padding: 16 }}>Loading…</div>
              )}
            </Glass>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}

// ─── Left drawer — PITL signal weights ────────────────────────────────────────

const PITL_SIGNALS = [
  { label: 'L4 Mahalanobis',   weight: 0.28, key: 'l4' },
  { label: 'L5 Temporal',      weight: 0.27, key: 'l5' },
  { label: 'L2B IMU-Press',    weight: 0.15, key: 'l2b' },
  { label: 'L2C Stick-IMU',    weight: 0.10, key: 'l2c' },
  { label: 'IoSwarm (emu)',     weight: 0.35, key: 'sw', note: 'off' },
]

const VERDICT_COLORS = {
  CERTIFY: DEVELOPER.green,
  FLAG: DEVELOPER.amber,
  HOLD: DEVELOPER.orange,
  BLOCK: DEVELOPER.red,
}

function PITLDrawer({ open, onClose, analytics }) {
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.35)', zIndex: 30 }}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.div
            style={{
              position: 'fixed', top: '50%', left: 16,
              transform: 'translateY(-50%)',
              width: 260, zIndex: 31,
            }}
            variants={DRAWER_SLIDE_LEFT}
            initial="initial" animate="animate" exit="exit"
          >
            <Glass accent={DEVELOPER.amber} style={{ padding: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <span style={{ fontFamily: FONTS.display, fontSize: 13, fontWeight: 600, color: DEVELOPER.t1, letterSpacing: '0.08em' }}>PITL SIGNAL WEIGHTS</span>
                <span style={{ fontFamily: FONTS.mono, fontSize: 8, color: DEVELOPER.t3, cursor: 'pointer', padding: '2px 6px' }} onClick={onClose}>✕</span>
              </div>

              {PITL_SIGNALS.map((sig) => (
                <div key={sig.key} style={{ marginBottom: 8 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                    <span style={{ fontFamily: FONTS.mono, fontSize: 8, color: sig.note ? DEVELOPER.t3 : DEVELOPER.t2 }}>
                      {sig.label}{sig.note ? ` (${sig.note})` : ''}
                    </span>
                    <span style={{ fontFamily: FONTS.mono, fontSize: 9, fontWeight: 700, color: sig.note ? DEVELOPER.t3 : DEVELOPER.amber }}>{sig.weight.toFixed(2)}</span>
                  </div>
                  <div style={{ height: 3, background: DEVELOPER.bd, borderRadius: 2 }}>
                    <motion.div
                      style={{ height: '100%', borderRadius: 2, background: sig.note ? DEVELOPER.t3 : DEVELOPER.amber }}
                      initial={{ width: 0 }}
                      animate={{ width: `${sig.weight * 100}%` }}
                      transition={{ duration: 1.2, ease: 'easeOut', delay: 0.1 }}
                    />
                  </div>
                </div>
              ))}

              {analytics && (
                <div style={{ marginTop: 14, paddingTop: 10, borderTop: `1px solid ${DEVELOPER.bd}` }}>
                  <div style={{ fontFamily: FONTS.mono, fontSize: 7, color: DEVELOPER.t3, letterSpacing: '0.12em', marginBottom: 6 }}>BLOCKING REASONS</div>
                  {Object.entries(analytics.blocking_reason_counts ?? {}).map(([reason, count]) => (
                    <DrawerStat key={reason} label={reason} value={count} accent={DEVELOPER.red} />
                  ))}
                  {Object.keys(analytics.blocking_reason_counts ?? {}).length === 0 && (
                    <div style={{ fontFamily: FONTS.mono, fontSize: 8, color: DEVELOPER.green, textAlign: 'center', padding: 8 }}>No blockers</div>
                  )}
                </div>
              )}
            </Glass>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}

// ─── Node component ────────────────────────────────────────────────────────────

function PipelineNode({ label, count, countLabel, ageLabel, status, accent, index }) {
  const statusColor = status === 'ACTIVE' ? DEVELOPER.green : status === 'STALLED' ? DEVELOPER.amber : DEVELOPER.red

  return (
    <motion.div variants={PIPELINE_NODE} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      {/* Status indicator dot */}
      <div style={{ width: 6, height: 6, borderRadius: '50%', background: statusColor, boxShadow: `0 0 8px ${statusColor}`, marginBottom: 6 }} />

      <Glass accent={accent} style={{ width: 112, padding: '8px 10px', textAlign: 'center' }}>
        <div style={{ fontFamily: FONTS.display, fontWeight: 600, fontSize: 11, letterSpacing: '0.1em', color: DEVELOPER.t1, marginBottom: 4 }}>{label}</div>
        <div style={{ fontFamily: FONTS.mono, fontSize: 18, fontWeight: 700, color: accent, lineHeight: 1, marginBottom: 2 }}>{count ?? '–'}</div>
        <div style={{ fontFamily: FONTS.mono, fontSize: 7, color: DEVELOPER.t3, letterSpacing: '0.1em' }}>{countLabel}</div>
        {ageLabel && (
          <div style={{ fontFamily: FONTS.mono, fontSize: 7, color: ageLabel.includes('stall') || ageLabel.includes('dead') ? DEVELOPER.red : DEVELOPER.t2, marginTop: 3 }}>{ageLabel}</div>
        )}
      </Glass>
    </motion.div>
  )
}

// ─── Main view ────────────────────────────────────────────────────────────────

export function DeveloperView() {
  const [gateOpen,  setGateOpen]  = useState(false)
  const [pitlOpen,  setPitlOpen]  = useState(false)
  const [opAgentsOpen, setOpAgentsOpen] = useState(false)
  const [draftReviewOpen, setDraftReviewOpen] = useState(false)
  const [o3ReadinessOpen, setO3ReadinessOpen] = useState(false)
  const [auditDrawerOpen, setAuditDrawerOpen] = useState(false)
  const [dims,      setDims]      = useState({ w: window.innerWidth, h: window.innerHeight })

  const { data: ch } = useCaptureHealth()
  const { data: gc } = useGrindChain()
  const { data: ga } = useGrindAnalytics()
  const { data: pf } = useTournamentPreflight()
  const { data: fs } = useFleetCoherenceStatus()
  const { data: pc } = useProtocolCoherence()

  // Phase O1 C5 — Operator Agents shadow visibility.
  // Activation gate: only show drawer/handle when at least one Cedar bundle
  // has been anchored (operator_agent_activation_log row_count > 0).
  // Drift count: 24h window — only polled when an O1 agent is activated, so
  // operators on the main protocol track incur zero polling cost.
  const { data: opActivation } = useOperatorActivation()
  const o1Active = (opActivation?.row_count ?? 0) > 0
  const { data: driftSummary } = useDriftLog({
    sinceMinutes: 1440, limit: 1, enabled: o1Active,
  })
  const driftCount24h = driftSummary?.row_count ?? 0

  // Phase O4 post-backlog-closure — Curator graduation readiness drives
  // the AuditHarnesses drawer handle ★ badge tint. Gated on o1Active so
  // operators not on the Operator Initiative track incur zero polling
  // cost. Polls every 60s while o1Active=true.
  const { data: curatorGradData } = useCuratorGraduationReadiness({ enabled: o1Active })
  const curatorGradVerdict = curatorGradData?.section_5_consolidated_verdict?.verdict || ''

  // Phase O2-DRAFT-REVIEW-FRONTEND — Unreviewed-draft badge counter.
  // Polls only when O1 active. Single-row limit fetch; row_count carries
  // the unreviewed-draft total in the last 7 days. Used to drive the
  // handle's pending-count chip; full review surface lives in the drawer.
  const { data: draftSummary } = useOperatorDrafts({
    decision: 'unreviewed', sinceMinutes: 10080, limit: 1, enabled: o1Active,
  })
  const unreviewedDraftCount = draftSummary?.row_count ?? 0

  // Phase O3-READINESS-DASHBOARD — fleet alignment for handle badge.
  // Polls only when O1 active. fleet_phase_aligned=True is the strategic
  // signal that all three agents are at the same phase + ready to advance.
  const { data: frrSummary } = useFleetReadinessRoot({ enabled: o1Active })
  const fleetAligned = Boolean(frrSummary?.fleet_phase_aligned)

  // Phase 238-FRONTEND-V3 — Curator review log surface.
  // Curator is the third Operator Initiative agent (Sentry/Guardian/Curator)
  // and its review verdicts are the audit trail operators consult before
  // marketplace listings clear into the buyer-facing tab.  Surfaced in
  // DeveloperView since this is the operator drill-down view.
  const { data: curator }       = useCuratorStatus()
  const curatorEnabled          = Boolean(curator?.curator_review_enabled)
  const { data: curatorFlagged } = useCuratorFlaggedListings({
    sinceMinutes: 1440, limit: 8,
  })
  const [curatorOpen, setCuratorOpen] = useState(false)

  useEffect(() => {
    const onResize = () => setDims({ w: window.innerWidth, h: window.innerHeight })
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  // Auto-open gate drawer when preflight fails
  useEffect(() => {
    if (pf && !pf.overall_pass) setGateOpen(true)
  }, [pf?.overall_pass])

  // Auto-open PITL drawer on contradictions
  useEffect(() => {
    if (fs && fs.active_contradictions > 0) setPitlOpen(true)
  }, [fs?.active_contradictions])

  // Derive pipeline stage states
  const captureActive  = ch?.capture_state === 'NOMINAL'
  const validated      = ga?.total_validated ?? 0
  const stamped        = ga?.stamped_count   ?? 0
  const chainLen       = gc?.chain_length     ?? 0
  const chainIntact    = gc?.chain_intact     ?? true
  const successRate    = ga?.success_rate     ?? 0
  const sessPerDay     = ga?.sessions_per_day ?? 0
  const agentCount     = pc?.agent_count      ?? fs?.total_entries ?? 38
  const contradictions = fs?.active_contradictions ?? 0
  const merkleRoot     = pc?.latest_merkle_root ?? ''
  const merkleShort    = merkleRoot ? merkleRoot.slice(0, 12) : '–'
  const sessionId      = gc?.grind_session_id ?? '–'
  const grindTarget    = ch?.grind_target     ?? 100
  const consClean      = ch?.consecutive_clean_toward_target ?? 0

  // Format seconds-ago into human-readable label
  const fmtAge = (ts) => {
    if (!ts || ts === 0) return null
    const s = Math.floor(Date.now() / 1000 - ts)
    if (s < 0) return 'just now'
    if (s < 60) return `${s}s ago`
    if (s < 3600) return `${Math.floor(s / 60)}m ago`
    return `${Math.floor(s / 3600)}h ago`
  }

  const lastValidAge = fmtAge(ga?.last_validation_ts)
  const lastStampAge = fmtAge(ga?.last_stamp_ts)
  const lastGicAge   = fmtAge(gc?.latest_ts)
  const lastChainAge = fmtAge(pc?.last_anchor_ts)

  const stages = useMemo(() => [
    {
      label: 'CAPTURE',
      count: ch?.poll_rate_hz ? Math.round(ch.poll_rate_hz) : '–',
      countLabel: 'Hz POLL',
      ageLabel: captureActive ? 'NOMINAL' : (ch?.capture_state ?? 'offline'),
      status: captureActive ? 'ACTIVE' : 'STALLED',
    },
    {
      label: 'ADJUDICATE',
      count: validated,
      countLabel: 'VALIDATED',
      ageLabel: lastValidAge ?? (validated > 0 ? 'live' : 'waiting'),
      status: validated > 0 ? 'ACTIVE' : 'WAITING',
    },
    {
      label: 'VALIDATE',
      count: stamped,
      countLabel: 'STAMPED',
      ageLabel: lastStampAge ?? (stamped > 0 ? `${(successRate * 100).toFixed(0)}% rate` : 'waiting'),
      status: stamped > 0 ? 'ACTIVE' : 'WAITING',
    },
    {
      label: 'GIC STAMP',
      count: chainLen,
      countLabel: `/ ${grindTarget} CHAIN`,
      ageLabel: lastGicAge ?? (chainIntact ? 'INTACT' : 'BROKEN'),
      status: chainLen > 0 ? (chainIntact ? 'ACTIVE' : 'STALLED') : 'WAITING',
    },
    {
      label: 'ON-CHAIN',
      count: pc?.total_anchors ?? '–',
      countLabel: 'ANCHORS',
      ageLabel: lastChainAge ?? (pc?.on_chain_confirmed ? 'confirmed' : 'pending'),
      status: pc?.on_chain_confirmed ? 'ACTIVE' : 'WAITING',
    },
  // eslint-disable-next-line react-hooks/exhaustive-deps
  ], [ch, gc, ga, pc, captureActive, validated, stamped, chainLen, chainIntact, successRate, grindTarget, lastValidAge, lastStampAge, lastGicAge, lastChainAge])

  // Bottom bar chip states
  const pipelineStatus = captureActive ? 'ACTIVE' : (ch ? 'STALLED' : 'DEAD')
  const pipelineColor  = pipelineStatus === 'ACTIVE' ? DEVELOPER.green : pipelineStatus === 'STALLED' ? DEVELOPER.amber : DEVELOPER.red
  const chainStatus    = `${chainLen}/${grindTarget}`
  const chainColor     = chainIntact ? DEVELOPER.orange : DEVELOPER.red
  const gatePass       = pf?.overall_pass
  const gateColor      = gatePass ? DEVELOPER.green : DEVELOPER.red
  const fleetLabel     = `${agentCount} · ${contradictions} CONTRA`
  const fleetColor     = contradictions > 0 ? DEVELOPER.amber : DEVELOPER.green
  const successLabel   = `${(successRate * 100).toFixed(0)}% PASS`
  const velocityLabel  = sessPerDay > 0 ? `${sessPerDay.toFixed(1)}/day` : '–'

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden', background: DEVELOPER.bg }}>

      {/* Circuit board grid background */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        backgroundImage: [
          `repeating-linear-gradient(0deg, transparent, transparent 39px, ${DEVELOPER.orange}0d 39px, ${DEVELOPER.orange}0d 40px)`,
          `repeating-linear-gradient(90deg, transparent, transparent 39px, ${DEVELOPER.orange}0d 39px, ${DEVELOPER.orange}0d 40px)`,
        ].join(', '),
      }} />

      {/* Radial vignette */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: `radial-gradient(ellipse 70% 60% at 50% 50%, transparent 40%, ${DEVELOPER.bg} 100%)`,
      }} />

      {/* Pipeline SVG connectors + particles */}
      <PipelineCanvas stages={stages} width={dims.w} height={dims.h} />

      {/* Pipeline nodes — horizontally centered at 50% height */}
      <motion.div
        variants={PIPELINE_NODE_CONTAINER}
        initial="initial" animate="animate"
        style={{
          position: 'absolute',
          top: `${NODE_Y * 100}%`,
          left: 0, right: 0,
          transform: 'translateY(-50%)',
          display: 'flex',
          justifyContent: 'space-around',
          alignItems: 'center',
          padding: '0 4%',
          pointerEvents: 'none',
        }}
      >
        {stages.map((stage, i) => (
          <PipelineNode
            key={stage.label}
            index={i}
            label={stage.label}
            count={stage.count}
            countLabel={stage.countLabel}
            ageLabel={stage.ageLabel}
            status={stage.status}
            accent={i === 3 ? DEVELOPER.amber : DEVELOPER.orange}
          />
        ))}
      </motion.div>

      {/* ── TOP-LEFT: session badge ── */}
      <div style={{ position: 'absolute', top: 16, left: 16, display: 'flex', flexDirection: 'column', gap: 6 }}>
        <Glass accent={DEVELOPER.orange} style={{ padding: '8px 12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{
              width: 6, height: 6, borderRadius: '50%',
              background: ch ? DEVELOPER.green : DEVELOPER.red,
              boxShadow: `0 0 6px ${ch ? DEVELOPER.green : DEVELOPER.red}`,
            }} />
            <span style={{ fontFamily: FONTS.mono, fontSize: 9, color: DEVELOPER.t2 }}>BRIDGE</span>
          </div>
          <div style={{ fontFamily: FONTS.mono, fontSize: 9, fontWeight: 600, color: DEVELOPER.orange, marginTop: 4 }}>{sessionId}</div>
        </Glass>
      </div>

      {/* ── TOP-RIGHT: fleet badge ── */}
      <div style={{ position: 'absolute', top: 16, right: 16 }}>
        <Glass accent={DEVELOPER.amber} style={{ padding: '8px 12px', textAlign: 'right' }}>
          <div style={{ fontFamily: FONTS.mono, fontSize: 9, color: DEVELOPER.t3 }}>FLEET</div>
          <div style={{ fontFamily: FONTS.mono, fontSize: 11, fontWeight: 700, color: DEVELOPER.amber }}>
            {agentCount} <span style={{ fontWeight: 400, color: DEVELOPER.t2 }}>agents</span>
          </div>
          <div style={{ fontFamily: FONTS.mono, fontSize: 8, color: contradictions > 0 ? DEVELOPER.red : DEVELOPER.t3, marginTop: 2 }}>
            {contradictions} contra · {merkleShort}
          </div>
        </Glass>
      </div>

      {/* ── TOP-CENTER: hero number ── */}
      <div style={{ position: 'absolute', top: 16, left: '50%', transform: 'translateX(-50%)', textAlign: 'center', pointerEvents: 'none' }}>
        <div style={{ fontFamily: FONTS.display, fontSize: 36, fontWeight: 700, color: DEVELOPER.orange, lineHeight: 1, textShadow: `0 0 40px ${DEVELOPER.orange}88` }}>
          {consClean} <span style={{ fontSize: 20, color: DEVELOPER.t3 }}>/ {grindTarget}</span>
        </div>
        <div style={{
          fontFamily: FONTS.mono, fontSize: 8, letterSpacing: '0.18em',
          color: chainIntact ? DEVELOPER.green : DEVELOPER.red, marginTop: 4,
        }}>
          {chainIntact ? 'PIPELINE VERIFIED' : 'CHAIN BROKEN'}
        </div>
      </div>

      {/* ── LEFT DRAWER HANDLE ── */}
      <motion.div
        style={{
          position: 'absolute', left: 0, top: '50%', transform: 'translateY(-50%)',
          width: 20, height: 60,
          background: `${DEVELOPER.amber}22`, border: `1px solid ${DEVELOPER.amber}33`,
          borderRadius: '0 4px 4px 0', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
        whileHover={{ width: 26, background: `${DEVELOPER.amber}44` }}
        onClick={() => setPitlOpen(v => !v)}
      >
        <span style={{ fontFamily: FONTS.mono, fontSize: 7, color: DEVELOPER.amber, writingMode: 'vertical-rl', letterSpacing: '0.1em' }}>PITL</span>
      </motion.div>

      {/* ── RIGHT DRAWER HANDLE ── */}
      <motion.div
        style={{
          position: 'absolute', right: 0, top: '50%', transform: 'translateY(-50%)',
          width: 20, height: 60,
          background: gatePass ? `${DEVELOPER.green}22` : `${DEVELOPER.red}22`,
          border: `1px solid ${gatePass ? DEVELOPER.green : DEVELOPER.red}33`,
          borderRadius: '4px 0 0 4px', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
        whileHover={{ width: 26 }}
        onClick={() => setGateOpen(v => !v)}
      >
        <span style={{ fontFamily: FONTS.mono, fontSize: 7, color: gatePass ? DEVELOPER.green : DEVELOPER.red, writingMode: 'vertical-rl', letterSpacing: '0.1em' }}>GATE</span>
      </motion.div>

      {/* ── BOTTOM STATUS BAR ── */}
      <div style={{
        position: 'absolute', bottom: 16, left: '50%', transform: 'translateX(-50%)',
        display: 'flex', gap: 6, alignItems: 'center',
      }}>
        <StatusChip label="PIPELINE" value={pipelineStatus}    accent={pipelineColor} />
        <StatusChip label="SUCCESS"  value={successLabel}      accent={DEVELOPER.orange} />
        <StatusChip label="CHAIN"    value={chainStatus}       accent={chainColor} onClick={() => setGateOpen(v => !v)} active={gateOpen} />
        <StatusChip label="FLEET"    value={fleetLabel}        accent={fleetColor} onClick={() => setPitlOpen(v => !v)} active={pitlOpen} />
        <StatusChip label="GATE"     value={gatePass ? 'PASS' : 'FAIL'} accent={gateColor} onClick={() => setGateOpen(v => !v)} active={gateOpen} />
        <StatusChip label="VELOCITY" value={velocityLabel}    accent={DEVELOPER.amber} />
      </div>

      {/* Drawers */}
      <GateDrawer open={gateOpen} onClose={() => setGateOpen(false)} preflight={pf} />
      <PITLDrawer open={pitlOpen} onClose={() => setPitlOpen(false)} analytics={ga} />

      {/* Phase O1 C5 — Operator Agents shadow drawer (only when O1 active). */}
      {o1Active && (
        <>
          <OperatorAgentsDrawerHandle
            onClick={() => setOpAgentsOpen(v => !v)}
            driftCount={driftCount24h}
          />
          <OperatorAgentsDrawer
            open={opAgentsOpen}
            onClose={() => setOpAgentsOpen(false)}
            driftCount={driftCount24h}
          />
        </>
      )}

      {/* Phase O2-DRAFT-REVIEW-FRONTEND — Draft review drawer (only when O1 active).
         Handle at bottom-LEFT to avoid the OperatorAgentsDrawerHandle at bottom-right.
         Unreviewed-count badge surfaces pending-decision backlog: clearing it
         is what drives operator_disagreement_rate gate measurement. */}
      {o1Active && (
        <>
          <DraftReviewDrawerHandle
            onClick={() => setDraftReviewOpen(v => !v)}
            unreviewedCount={unreviewedDraftCount}
          />
          <DraftReviewDrawer
            open={draftReviewOpen}
            onClose={() => setDraftReviewOpen(false)}
            unreviewedCount={unreviewedDraftCount}
          />
        </>
      )}

      {/* Phase O3-READINESS-DASHBOARD — top-edge slide-down drawer (only O1 active).
         Handle at top-CENTER; drawer slides down from top. Three drawers total
         (top-center / bottom-left / bottom-right) — no collisions. ★ badge fires
         when fleet_phase_aligned=True signaling all three agents at same phase. */}
      {o1Active && (
        <>
          <O3ReadinessDrawerHandle
            onClick={() => setO3ReadinessOpen(v => !v)}
            fleetAligned={fleetAligned}
          />
          <O3ReadinessDrawer
            open={o3ReadinessOpen}
            onClose={() => setO3ReadinessOpen(false)}
            fleetAligned={fleetAligned}
          />
        </>
      )}

      {/* Phase O4 post-backlog-closure — Audit harnesses drawer (top-right).
         Surfaces G7 readiness + CFSS lane authority + Curator graduation
         readiness from the 3 bridge HTTP endpoints shipped at commit
         0f2d10fa. Drawer position TOP-RIGHT (only remaining uncluttered
         drawer slot; existing drawers occupy top-CENTER, bottom-LEFT,
         bottom-RIGHT). Activation-gated like the other drawers — only
         renders when o1Active=true. Conditional polling: panels poll
         only while drawer is open + the handle's badge query is gated
         on o1Active (zero polling cost when no O1 agent is active).
         curatorGradVerdict drives the ★ badge tint so operator sees
         from-a-glance whether graduation cleared. */}
      {o1Active && (
        <>
          <AuditHarnessesDrawerHandle
            onClick={() => setAuditDrawerOpen(v => !v)}
            readinessVerdict={curatorGradVerdict}
          />
          <AuditHarnessesDrawer
            open={auditDrawerOpen}
            onClose={() => setAuditDrawerOpen(false)}
          />
        </>
      )}

      {/* Phase 238-FRONTEND-V3 — Curator review log surface. */}
      {curatorEnabled && (
        <CuratorReviewLog
          curator={curator}
          flagged={curatorFlagged}
          open={curatorOpen}
          onToggle={() => setCuratorOpen(v => !v)}
        />
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// CuratorReviewLog — Phase 238-FRONTEND-V3
// Bottom-left collapsible panel showing recent curator reviews. Mirrors the
// OperatorAgentsDrawer interaction pattern (handle + slide-up panel).
// ---------------------------------------------------------------------------
function CuratorReviewLog({ curator, flagged, open, onToggle }) {
  const total      = Number(curator?.total_reviews || 0)
  const flagN      = Number(curator?.flagged_reviews || 0)
  const accent     = flagN > 0 ? 'var(--vapi-warn)' : 'var(--vapi-cyan)'
  const rows       = flagged?.listings ?? []

  return (
    <>
      {/* Handle */}
      <button
        onClick={onToggle}
        title={`Curator agent — ${total} reviews · ${flagN} flagged in last 24h`}
        style={{
          position:      'absolute',
          left:          16,
          bottom:        16,
          padding:       '6px 12px',
          background:    'rgba(2,4,8,0.85)',
          border:        `1px solid ${accent}`,
          borderRadius:  3,
          color:         accent,
          fontFamily:    FONTS.mono,
          fontSize:      10,
          letterSpacing: '0.08em',
          cursor:        'pointer',
          zIndex:        15,
          display:       'flex',
          alignItems:    'center',
          gap:           8,
        }}
      >
        <span style={{
          width:        6,
          height:       6,
          borderRadius: 3,
          background:   accent,
          boxShadow:    flagN > 0 ? `0 0 8px ${accent}` : 'none',
        }} />
        CURATOR · {total}/{flagN}
        <span style={{ opacity: 0.6, fontSize: 8 }}>{open ? '▼' : '▲'}</span>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            transition={{ duration: 0.18 }}
            style={{
              position:      'absolute',
              left:          16,
              bottom:        56,
              width:         360,
              maxHeight:     320,
              overflowY:     'auto',
              background:    'rgba(2,4,8,0.94)',
              border:        `1px solid ${accent}`,
              borderRadius:  3,
              padding:       12,
              backdropFilter: 'blur(8px)',
              zIndex:        14,
            }}
          >
            <div style={{
              fontFamily:    FONTS.mono,
              fontSize:      9,
              color:         'var(--vapi-tier-basic)',
              letterSpacing: '0.08em',
              marginBottom:  8,
            }}>
              CURATOR REVIEWS · LAST 24H · {rows.length} FLAGGED
            </div>
            {rows.length === 0 ? (
              <div style={{
                padding:    12,
                fontSize:   10,
                color:      'var(--vapi-cyan)',
                textAlign:  'center',
                opacity:    0.7,
              }}>
                ◌ no flagged reviews — curator pipeline quiet
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {rows.map((r, i) => (
                  <div
                    key={`${r.listing_commitment}-${i}`}
                    style={{
                      padding:    '6px 8px',
                      background: 'rgba(255,255,255,0.02)',
                      borderLeft: `3px solid ${
                        r.severity === 'CRITICAL' || r.severity === 'HIGH'
                          ? 'var(--vapi-block)'
                          : 'var(--vapi-warn)'
                      }`,
                      fontSize:   10,
                      fontFamily: FONTS.mono,
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                      <span style={{ color: 'var(--vapi-warn)', fontWeight: 600 }}>
                        {r.verdict}
                      </span>
                      <span style={{ fontSize: 8, color: 'var(--vapi-tier-basic)' }}>
                        {String(r.listing_commitment ?? '').slice(0, 12)}…
                      </span>
                    </div>
                    {r.reason_detail && (
                      <div style={{
                        fontSize:     9,
                        color:        'var(--vapi-tier-basic)',
                        marginTop:    3,
                        whiteSpace:   'nowrap',
                        overflow:     'hidden',
                        textOverflow: 'ellipsis',
                      }}>{r.reason_detail}</div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
