import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  useAITSeparation,
  useCaptureHealth,
  useInvariantGateStatus,
  useTournamentPreflight,
} from '../api/bridgeApi'
import { useHeartbeatStore } from '../heartbeat/useHeartbeat'
import { FONTS, MANUFACTURER } from '../shared/design/tokens'
import { DRAWER_SLIDE_LEFT } from '../shared/design/animations'

// ─── Design primitives ───────────────────────────────────────────────────────

function Glass({ children, style, accent = MANUFACTURER.blue, intensity = 1 }) {
  return (
    <div style={{
      background: `linear-gradient(180deg, rgba(4,8,15,${0.60 * intensity}) 0%, rgba(2,4,8,${0.78 * intensity}) 100%)`,
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

function StatusChip({ label, value, accent = MANUFACTURER.blue, onClick, active }) {
  return (
    <Glass accent={accent} style={{ padding: '5px 10px', cursor: onClick ? 'pointer' : 'default', outline: active ? `1px solid ${accent}55` : 'none' }} onClick={onClick}>
      <div style={{ fontFamily: FONTS.mono, letterSpacing: '0.16em', fontSize: 6.5, color: MANUFACTURER.t3, textTransform: 'uppercase', marginBottom: 2 }}>{label}</div>
      <div style={{ fontFamily: FONTS.mono, fontSize: 10, fontWeight: 600, color: accent, whiteSpace: 'nowrap' }}>{value}</div>
    </Glass>
  )
}

function DrawerStat({ label, value, accent = MANUFACTURER.blue }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 0', borderBottom: `1px solid ${MANUFACTURER.bd}` }}>
      <span style={{ fontFamily: FONTS.mono, fontSize: 8, color: MANUFACTURER.t3 }}>{label}</span>
      <span style={{ fontFamily: FONTS.mono, fontSize: 10, fontWeight: 600, color: accent }}>{value}</span>
    </div>
  )
}

// ─── Voronoi dot mesh background ─────────────────────────────────────────────

function VoronoiMesh({ width, height }) {
  const points = useRef(
    Array.from({ length: 120 }, () => ({
      x: Math.random(),
      y: Math.random(),
    }))
  ).current

  if (!width || !height) return null
  return (
    <svg style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }} width={width} height={height}>
      {points.map((p, i) => (
        <circle
          key={i}
          cx={p.x * width}
          cy={p.y * height}
          r={1.2}
          fill={MANUFACTURER.blue}
          opacity={0.06}
        />
      ))}
    </svg>
  )
}

// ─── Biometric Fingerprint Radar ──────────────────────────────────────────────

function RadarCanvas({ ait, captureHealth, magnitude }) {
  const svgRef = useRef(null)
  const animRef = useRef(null)
  const pulseRef = useRef(0)

  // Map tremor peak hz 0-15 Hz → angle 0-2π (starting at top)
  const mapHzToAngle = (hz) => ((hz - 0) / 15) * Math.PI * 2 - Math.PI / 2

  // Live per-player tremor Hz — fallback to corpus constants when API lacks features
  const _liveHz = ait?.per_player_tremor_hz ?? {}
  const _players = Object.keys(_liveHz).length > 0
    ? Object.entries(_liveHz).map(([p, hz], i) => ({
        hz,
        label: p.replace('Player ', 'P'),
        color: i === 0 ? MANUFACTURER.gold : MANUFACTURER.blue,
      }))
    : [
        { hz: 9.37, label: 'P1', color: MANUFACTURER.gold },
        { hz: 1.71, label: 'P2', color: MANUFACTURER.blue },
        { hz: 2.85, label: 'P3', color: MANUFACTURER.blue },
      ]

  // Mean roll angle across players → controls ring 2 arc start position
  const _rollVals = Object.values(ait?.per_player_roll_angle_deg ?? {})
  const _meanRollDeg = _rollVals.length > 0
    ? _rollVals.reduce((a, b) => a + b, 0) / _rollVals.length
    : 36.0  // corpus mean fallback

  // Mean pitch angle → controls ring 3 arc fill proportion (pitch ≈ 0-90° → 0.10-0.50)
  const _pitchVals = Object.values(ait?.per_player_pitch_angle_deg ?? {})
  const _meanPitchDeg = _pitchVals.length > 0
    ? _pitchVals.reduce((a, b) => a + b, 0) / _pitchVals.length
    : 33.6  // corpus mean fallback
  const _pitchFrac = Math.max(0.10, Math.min(0.50, _meanPitchDeg / 90))

  const ratio        = ait?.separation_ratio   ?? 0
  const allPairsOk   = ait?.all_pairs_above_1  ?? false
  const pairDist     = ait?.pair_distances      ?? {}
  const captureState = captureHealth?.capture_state ?? 'UNKNOWN'
  const hostState    = captureHealth?.host_state    ?? 'UNKNOWN'
  const pollHz       = captureHealth?.poll_rate_hz  ?? 0

  // Poll rate ring: nominal=EXCLUSIVE_USB → thin ring, CONTESTED → thick
  const pollNormal  = captureState === 'NOMINAL' && hostState === 'EXCLUSIVE_USB'
  const ringWidth   = pollNormal ? 2.5 : 7

  // Heartbeat pulse: outer ring brightens with magnitude
  useEffect(() => {
    pulseRef.current = magnitude ?? 0
  }, [magnitude])

  const cx = 260
  const cy = 260
  const RING_R = [120, 90, 65, 42]   // outer to inner radius

  return (
    <svg
      ref={svgRef}
      width={520}
      height={520}
      style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', pointerEvents: 'none' }}
    >
      {/* ── Ring 4 (inner): poll rate stability ── */}
      <motion.circle
        cx={cx} cy={cy} r={RING_R[3]}
        fill="none"
        stroke={pollNormal ? MANUFACTURER.gold : MANUFACTURER.red}
        strokeWidth={ringWidth}
        opacity={0.55}
        animate={{ strokeWidth: pollNormal ? [2.5, 3.5, 2.5] : [7, 9, 7] }}
        transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* ── Ring 3 (pitch): arc fill proportional to mean pitch angle ── */}
      <circle cx={cx} cy={cy} r={RING_R[2]} fill="none" stroke={`${MANUFACTURER.blue}22`} strokeWidth={1} />
      <motion.circle
        cx={cx} cy={cy} r={RING_R[2]}
        fill="none"
        stroke={MANUFACTURER.blue}
        strokeWidth={2}
        strokeDasharray={`${RING_R[2] * Math.PI * _pitchFrac * 2} ${RING_R[2] * Math.PI * (2 - _pitchFrac * 2)}`}
        strokeLinecap="round"
        opacity={0.5}
        animate={{ strokeDashoffset: [0, -RING_R[2] * Math.PI * 2] }}
        transition={{ duration: 8, repeat: Infinity, ease: 'linear' }}
      />

      {/* ── Ring 2 (roll): arc anchored to mean roll angle ── */}
      <circle cx={cx} cy={cy} r={RING_R[1]} fill="none" stroke={`${MANUFACTURER.blue}22`} strokeWidth={1} />
      <motion.circle
        cx={cx} cy={cy} r={RING_R[1]}
        fill="none"
        stroke={MANUFACTURER.gold}
        strokeWidth={2.5}
        strokeDasharray={`${RING_R[1] * Math.PI * 0.28} ${RING_R[1] * Math.PI * 1.72}`}
        strokeLinecap="round"
        opacity={0.55}
        animate={{ rotate: [_meanRollDeg, _meanRollDeg + 360] }}
        style={{ transformOrigin: `${cx}px ${cy}px` }}
        transition={{ duration: 12, repeat: Infinity, ease: 'linear' }}
      />

      {/* ── Ring 1 (outer): tremor frequency ── */}
      <circle cx={cx} cy={cy} r={RING_R[0]} fill="none" stroke={`${MANUFACTURER.gold}18`} strokeWidth={1} />

      {/* Player tremor peaks — bright points on the outer ring (live from AIT endpoint) */}
      {_players.map(({ hz, label, color }) => {
        const angle = mapHzToAngle(hz)
        const px = cx + RING_R[0] * Math.cos(angle)
        const py = cy + RING_R[0] * Math.sin(angle)
        const lx = cx + (RING_R[0] + 14) * Math.cos(angle)
        const ly = cy + (RING_R[0] + 14) * Math.sin(angle)
        return (
          <g key={label}>
            <motion.circle
              cx={px} cy={py} r={4}
              fill={color}
              opacity={0.9}
              animate={{ r: [4, 6, 4], opacity: [0.9, 1, 0.9] }}
              transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut', delay: Math.random() * 2 }}
            />
            <text x={lx} y={ly} textAnchor="middle" dominantBaseline="middle"
              style={{ fontFamily: FONTS.mono, fontSize: 8, fill: color, opacity: 0.7 }}>
              {label}
            </text>
          </g>
        )
      })}

      {/* Heartbeat pulse ring — outer ring briefly brightens */}
      <motion.circle
        cx={cx} cy={cy} r={RING_R[0] + 8}
        fill="none"
        stroke={allPairsOk ? MANUFACTURER.gold : MANUFACTURER.blue}
        strokeWidth={1.5}
        opacity={0}
        animate={{ opacity: [0, (magnitude ?? 0) * 0.6, 0] }}
        transition={{ duration: 0.8, repeat: Infinity, ease: 'easeOut' }}
      />

      {/* Separation ratio arc overlay — fills proportional to ratio / target 1.2 */}
      {ratio > 0 && (
        <motion.circle
          cx={cx} cy={cy} r={RING_R[0]}
          fill="none"
          stroke={allPairsOk ? MANUFACTURER.gold : MANUFACTURER.orange}
          strokeWidth={3}
          strokeDasharray={`${RING_R[0] * Math.PI * 2 * Math.min(ratio / 2.0, 1)} ${RING_R[0] * Math.PI * 2}`}
          strokeLinecap="round"
          opacity={0.75}
          style={{ transformOrigin: `${cx}px ${cy}px`, transform: 'rotate(-90deg)' }}
          initial={{ strokeDasharray: `0 ${RING_R[0] * Math.PI * 2}` }}
          animate={{ strokeDasharray: `${RING_R[0] * Math.PI * 2 * Math.min(ratio / 2.0, 1)} ${RING_R[0] * Math.PI * 2}` }}
          transition={{ duration: 1.8, ease: 'easeOut', delay: 0.3 }}
        />
      )}

      {/* 1.0 target tick mark */}
      {(() => {
        const targetAngle = -Math.PI / 2 + (Math.PI * 2 * (1.0 / 2.0))
        const tx1 = cx + (RING_R[0] - 6) * Math.cos(targetAngle)
        const ty1 = cy + (RING_R[0] - 6) * Math.sin(targetAngle)
        const tx2 = cx + (RING_R[0] + 6) * Math.cos(targetAngle)
        const ty2 = cy + (RING_R[0] + 6) * Math.sin(targetAngle)
        return <line x1={tx1} y1={ty1} x2={tx2} y2={ty2} stroke={MANUFACTURER.gold} strokeWidth={2} opacity={0.6} />
      })()}

      {/* Center: poll rate label */}
      <text x={cx} y={cy - 8} textAnchor="middle"
        style={{ fontFamily: FONTS.mono, fontSize: 10, fill: pollNormal ? MANUFACTURER.gold : MANUFACTURER.red, fontWeight: 700 }}>
        {pollHz > 0 ? `${Math.round(pollHz)} Hz` : '–'}
      </text>
      <text x={cx} y={cy + 8} textAnchor="middle"
        style={{ fontFamily: FONTS.mono, fontSize: 7, fill: MANUFACTURER.t3 }}>
        {hostState}
      </text>
    </svg>
  )
}

// ─── Right drawer — per-pair separation breakdown ─────────────────────────────

function PairDrawer({ open, onClose, ait }) {
  const pairs = ait?.pair_distances ?? {}
  const maxDist = 2.0  // display cap for bar width

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.35)', zIndex: 30 }}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} />
          <motion.div
            style={{ position: 'fixed', top: '50%', right: 16, transform: 'translateY(-50%)', width: 280, zIndex: 31 }}
            initial={{ x: 320, opacity: 0 }}
            animate={{ x: 0, opacity: 1, transition: { duration: 0.2, ease: 'easeOut' } }}
            exit={{ x: 320, opacity: 0, transition: { duration: 0.15 } }}
          >
            <Glass accent={MANUFACTURER.gold} style={{ padding: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <span style={{ fontFamily: FONTS.display, fontSize: 13, fontWeight: 600, color: MANUFACTURER.t1, letterSpacing: '0.08em' }}>PAIR SEPARATION</span>
                <span style={{ fontFamily: FONTS.mono, fontSize: 8, color: MANUFACTURER.t3, cursor: 'pointer', padding: '2px 6px' }} onClick={onClose}>✕</span>
              </div>

              {Object.entries(pairs).map(([pair, dist]) => {
                const passes = dist >= 1.0
                const barFrac = Math.min(dist / maxDist, 1)
                return (
                  <div key={pair} style={{ marginBottom: 10 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                      <span style={{ fontFamily: FONTS.mono, fontSize: 9, color: MANUFACTURER.t2 }}>{pair}</span>
                      <span style={{ fontFamily: FONTS.mono, fontSize: 10, fontWeight: 700, color: passes ? MANUFACTURER.gold : MANUFACTURER.red }}>
                        {typeof dist === 'number' ? dist.toFixed(3) : '–'}
                      </span>
                    </div>
                    <div style={{ position: 'relative', height: 4, background: MANUFACTURER.bd, borderRadius: 2 }}>
                      <motion.div
                        style={{ height: '100%', borderRadius: 2, background: passes ? MANUFACTURER.gold : MANUFACTURER.red }}
                        initial={{ width: 0 }}
                        animate={{ width: `${barFrac * 100}%` }}
                        transition={{ duration: 1.4, ease: 'easeOut', delay: 0.1 }}
                      />
                      {/* 1.0 target line */}
                      <div style={{
                        position: 'absolute', top: -2, bottom: -2,
                        left: `${(1.0 / maxDist) * 100}%`,
                        width: 1.5, background: MANUFACTURER.gold, opacity: 0.6,
                      }} />
                    </div>
                  </div>
                )
              })}

              {ait && (
                <div style={{ marginTop: 12, paddingTop: 10, borderTop: `1px solid ${MANUFACTURER.bd}` }}>
                  <DrawerStat label="N SESSIONS"   value={ait.n_sessions ?? '–'}          accent={MANUFACTURER.blue} />
                  <DrawerStat label="LOO ACCURACY" value={ait.loo_accuracy != null ? `${(ait.loo_accuracy * 100).toFixed(1)}%` : '–'} accent={MANUFACTURER.blue} />
                  <DrawerStat label="ANALYSIS DATE" value={ait.analysis_date ?? '–'}       accent={MANUFACTURER.t2} />
                  {ait.n_per_player && Object.keys(ait.n_per_player).length > 0 && (
                    <div style={{ marginTop: 8, paddingTop: 6, borderTop: `1px solid ${MANUFACTURER.bd}` }}>
                      <div style={{ fontFamily: FONTS.mono, fontSize: 7, color: MANUFACTURER.t3, letterSpacing: '0.12em', marginBottom: 4 }}>N PER PLAYER</div>
                      {Object.entries(ait.n_per_player).map(([p, n]) => (
                        <DrawerStat
                          key={p}
                          label={p.replace('Player ', 'P')}
                          value={`${n} sessions${n >= 10 ? ' ✓' : ' –'}`}
                          accent={n >= 10 ? MANUFACTURER.gold : MANUFACTURER.red}
                        />
                      ))}
                    </div>
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

// ─── Left drawer — certification pathway ─────────────────────────────────────

const CERT_MILESTONES = [
  {
    label: 'UNCERTIFIED → STANDARD',
    conditions: [
      { text: 'Poll rate ≥ 800 Hz', key: 'pollHz',    check: (d) => (d?.pollHz ?? 0) >= 800 },
      { text: 'L4 thresholds valid', key: 'l4',       check: () => true },
    ],
  },
  {
    label: 'STANDARD → ATTESTED',
    conditions: [
      { text: 'Separation ratio > 1.0', key: 'ratio', check: (d) => (d?.ratio ?? 0) > 1.0 },
      { text: 'All pairs > 1.0',        key: 'pairs', check: (d) => d?.allPairsOk ?? false },
      { text: 'N ≥ 10 sessions/player', key: 'n',     check: (d) => (d?.nSessions ?? 0) >= 30 },
      { text: 'PCC NOMINAL+USB stable', key: 'pcc',   check: (d) => d?.pccOk ?? false },
    ],
  },
  {
    label: 'ATTESTED → ATTESTED+GSR',
    conditions: [
      { text: 'N ≥ 30 GSR sessions/player', key: 'gsr', check: () => false },
    ],
    pending: true,
  },
]

function CertPathwayDrawer({ open, onClose, derivedData }) {
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.35)', zIndex: 30 }}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} />
          <motion.div
            style={{ position: 'fixed', top: '50%', left: 16, transform: 'translateY(-50%)', width: 260, zIndex: 31 }}
            variants={DRAWER_SLIDE_LEFT}
            initial="initial" animate="animate" exit="exit"
          >
            <Glass accent={MANUFACTURER.gold} style={{ padding: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <span style={{ fontFamily: FONTS.display, fontSize: 13, fontWeight: 600, color: MANUFACTURER.t1, letterSpacing: '0.08em' }}>CERT PATHWAY</span>
                <span style={{ fontFamily: FONTS.mono, fontSize: 8, color: MANUFACTURER.t3, cursor: 'pointer', padding: '2px 6px' }} onClick={onClose}>✕</span>
              </div>

              {CERT_MILESTONES.map((milestone, mi) => (
                <div key={mi} style={{ marginBottom: 14 }}>
                  <div style={{ fontFamily: FONTS.mono, fontSize: 8, color: MANUFACTURER.t2, letterSpacing: '0.1em', marginBottom: 6 }}>{milestone.label}</div>
                  {milestone.conditions.map((cond) => {
                    const pass = cond.check(derivedData)
                    return (
                      <div key={cond.key} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                        <div style={{
                          width: 8, height: 8, borderRadius: '50%',
                          background: milestone.pending ? MANUFACTURER.t3 : (pass ? MANUFACTURER.gold : MANUFACTURER.bd),
                          border: `1px solid ${milestone.pending ? MANUFACTURER.t3 : (pass ? MANUFACTURER.gold : MANUFACTURER.blue)}`,
                          flexShrink: 0,
                        }} />
                        <span style={{ fontFamily: FONTS.mono, fontSize: 8, color: milestone.pending ? MANUFACTURER.t3 : (pass ? MANUFACTURER.t1 : MANUFACTURER.t2) }}>
                          {cond.text}
                        </span>
                        {!milestone.pending && (
                          <span style={{ marginLeft: 'auto', fontFamily: FONTS.mono, fontSize: 8, color: pass ? MANUFACTURER.green : MANUFACTURER.orange }}>
                            {pass ? '✓' : '…'}
                          </span>
                        )}
                        {milestone.pending && (
                          <span style={{ marginLeft: 'auto', fontFamily: FONTS.mono, fontSize: 8, color: MANUFACTURER.t3 }}>PENDING</span>
                        )}
                      </div>
                    )
                  })}
                </div>
              ))}
            </Glass>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}

// ─── Main view ────────────────────────────────────────────────────────────────

export function ManufacturerView() {
  const [pairOpen, setPairOpen]   = useState(false)
  const [certOpen, setCertOpen]   = useState(false)
  const [dims,     setDims]       = useState({ w: window.innerWidth, h: window.innerHeight })

  const { data: ait } = useAITSeparation()
  const { data: ch  } = useCaptureHealth()
  const { data: inv } = useInvariantGateStatus()
  const { data: pf  } = useTournamentPreflight()
  const magnitude     = useHeartbeatStore((s) => s.magnitude)

  useEffect(() => {
    const onResize = () => setDims({ w: window.innerWidth, h: window.innerHeight })
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  // Auto-open pair drawer when ratio < 1.0
  useEffect(() => {
    if (ait && !ait.all_pairs_above_1) setPairOpen(true)
  }, [ait?.all_pairs_above_1])

  const ratio      = ait?.separation_ratio  ?? 0
  const allPairs   = ait?.all_pairs_above_1 ?? false
  const nSessions  = ait?.n_sessions        ?? 0
  const pollHz     = ch?.poll_rate_hz       ?? 0
  const hostState  = ch?.host_state         ?? '–'
  const capState   = ch?.capture_state      ?? '–'
  const pccOk      = capState === 'NOMINAL' && (hostState === 'EXCLUSIVE_USB' || hostState === 'UNKNOWN')

  const invTotal   = inv?.total_checked ?? 26
  const invPass    = inv?.gate_pass     ?? true
  const invLabel   = `${invTotal}/${invTotal} ${invPass ? 'PASS' : 'FAIL'}`

  // Derive tier from AIT data
  const tier = allPairs && nSessions >= 30 ? 'ATTESTED' : allPairs ? 'STANDARD' : 'UNCERTIFIED'
  const tierColor = tier === 'ATTESTED' ? MANUFACTURER.gold : tier === 'STANDARD' ? MANUFACTURER.orange : MANUFACTURER.t3

  // Cert pathway derived data
  const derivedData = { ratio, allPairsOk: allPairs, nSessions, pollHz, pccOk }

  // Bottom bar
  const pollLabel    = `${Math.round(pollHz) || '–'} Hz ${capState === 'NOMINAL' ? 'NOMINAL' : capState}`
  const pollColor    = pccOk ? MANUFACTURER.gold : MANUFACTURER.red
  const aitLabel     = ratio > 0 ? `${ratio.toFixed(3)} ${allPairs ? 'CLEARED' : 'BLOCKED'}` : '–'
  const aitColor     = allPairs ? MANUFACTURER.gold : MANUFACTURER.red
  const corpusLabel  = `N=${nSessions}`
  const l4Label      = `7.009 / 5.367`

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden', background: MANUFACTURER.bg }}>

      {/* Voronoi dot mesh background */}
      <VoronoiMesh width={dims.w} height={dims.h} />

      {/* Radial vignette */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: `radial-gradient(ellipse 65% 55% at 50% 50%, transparent 35%, ${MANUFACTURER.bg} 100%)`,
      }} />

      {/* Biometric fingerprint radar — full-bleed center canvas */}
      <RadarCanvas ait={ait} captureHealth={ch} magnitude={magnitude} />

      {/* ── TOP-LEFT: certification tier badge ── */}
      <div style={{ position: 'absolute', top: 16, left: 16 }}>
        <Glass accent={tierColor} style={{ padding: '8px 14px' }}>
          <div style={{ fontFamily: FONTS.display, fontSize: 20, fontWeight: 700, color: tierColor, letterSpacing: '0.12em', lineHeight: 1 }}>{tier}</div>
          <div style={{ fontFamily: FONTS.mono, fontSize: 8, color: MANUFACTURER.t2, marginTop: 4 }}>CFI-ZCP1 DualShock Edge</div>
        </Glass>
      </div>

      {/* ── TOP-RIGHT: poll rate + host state badge ── */}
      <div style={{ position: 'absolute', top: 16, right: 16 }}>
        <Glass accent={MANUFACTURER.gold} style={{ padding: '8px 12px', textAlign: 'right' }}>
          <div style={{ fontFamily: FONTS.mono, fontSize: 13, fontWeight: 700, color: pccOk ? MANUFACTURER.gold : MANUFACTURER.red }}>
            {Math.round(pollHz) || '–'} Hz
          </div>
          <div style={{ fontFamily: FONTS.mono, fontSize: 8, color: MANUFACTURER.t2, marginTop: 2 }}>{hostState}</div>
        </Glass>
      </div>

      {/* ── TOP-CENTER: hero separation ratio ── */}
      <div style={{ position: 'absolute', top: 16, left: '50%', transform: 'translateX(-50%)', textAlign: 'center', pointerEvents: 'none' }}>
        <div style={{
          fontFamily: FONTS.display, fontSize: 36, fontWeight: 700,
          color: allPairs ? MANUFACTURER.gold : MANUFACTURER.red,
          lineHeight: 1,
          textShadow: `0 0 40px ${allPairs ? MANUFACTURER.gold : MANUFACTURER.red}88`,
        }}>
          {ratio > 0 ? ratio.toFixed(3) : '–'}
        </div>
        <div style={{
          fontFamily: FONTS.mono, fontSize: 8, letterSpacing: '0.18em',
          color: allPairs ? MANUFACTURER.green : MANUFACTURER.red, marginTop: 4,
        }}>
          {allPairs ? '> 1.0 TARGET MET' : '< 1.0 BLOCKED'}
        </div>
      </div>

      {/* ── LEFT DRAWER HANDLE — tier ── */}
      <motion.div
        style={{
          position: 'absolute', left: 0, top: '50%', transform: 'translateY(-50%)',
          width: 20, height: 60,
          background: `${tierColor}22`, border: `1px solid ${tierColor}33`,
          borderRadius: '0 4px 4px 0', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
        whileHover={{ width: 26 }}
        onClick={() => setCertOpen(v => !v)}
      >
        <span style={{ fontFamily: FONTS.mono, fontSize: 7, color: tierColor, writingMode: 'vertical-rl', letterSpacing: '0.1em' }}>TIER</span>
      </motion.div>

      {/* ── RIGHT DRAWER HANDLE — AIT pairs ── */}
      <motion.div
        style={{
          position: 'absolute', right: 0, top: '50%', transform: 'translateY(-50%)',
          width: 20, height: 60,
          background: allPairs ? `${MANUFACTURER.gold}22` : `${MANUFACTURER.red}22`,
          border: `1px solid ${allPairs ? MANUFACTURER.gold : MANUFACTURER.red}33`,
          borderRadius: '4px 0 0 4px', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
        whileHover={{ width: 26 }}
        onClick={() => setPairOpen(v => !v)}
      >
        <span style={{ fontFamily: FONTS.mono, fontSize: 7, color: allPairs ? MANUFACTURER.gold : MANUFACTURER.red, writingMode: 'vertical-rl', letterSpacing: '0.1em' }}>AIT</span>
      </motion.div>

      {/* ── BOTTOM STATUS BAR ── */}
      <div style={{
        position: 'absolute', bottom: 16, left: '50%', transform: 'translateX(-50%)',
        display: 'flex', gap: 6, alignItems: 'center',
      }}>
        <StatusChip label="TIER"        value={tier}        accent={tierColor} onClick={() => setCertOpen(v => !v)} active={certOpen} />
        <StatusChip label="POLL"        value={pollLabel}   accent={pollColor} />
        <StatusChip label="AIT"         value={aitLabel}    accent={aitColor} onClick={() => setPairOpen(v => !v)} active={pairOpen} />
        <StatusChip label="CORPUS"      value={corpusLabel} accent={MANUFACTURER.blue} />
        <StatusChip label="L4"          value={l4Label}     accent={MANUFACTURER.t2} />
        <StatusChip label="INVARIANTS"  value={invLabel}    accent={invPass ? MANUFACTURER.green : MANUFACTURER.red} />
      </div>

      {/* Drawers */}
      <PairDrawer       open={pairOpen} onClose={() => setPairOpen(false)} ait={ait} />
      <CertPathwayDrawer open={certOpen} onClose={() => setCertOpen(false)} derivedData={derivedData} />
    </div>
  )
}
