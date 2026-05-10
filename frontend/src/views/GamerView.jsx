// VAPI Gamer Dashboard — Phase 235-GAMER-REDESIGN
// Phase 235-DASH-UPGRADE-3: consecutive_clean (true grind metric),
// GrindAnalytics velocity strip, PCCIntelligence episode history, AIT chip.
//
// Design invariant: the 3D controller twin is the entire canvas.
// Every overlay is anchored to a screen edge. Vertical center is clear.
//   top strip   — SessionBadge (left), LiveStatusBadge (right), GrindProgressBar (center)
//   bottom strip — 7 compact StatusChips
//   right edge   — PCCDrawer (off-screen until stress or click)

import { useEffect, useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useHeartbeatStore } from '../heartbeat/useHeartbeat'
import {
  useCaptureHealth, useGrindChain, useFleetCoherenceStatus,
  useAutoTriggerStatus, useGrindAnalytics, useAITSeparation, usePCCIntelligence,
  useActivePlayOccupancy,
  useCuratorStatus,
  isMockActive,
} from '../api/bridgeApi'
import { ConsentPanel } from '../components/ConsentPanel'
import { ConsentMatrix } from '../components/ConsentMatrix'
import { PoacChainRibbon } from '../components/PoacChainRibbon'
import { FONTS, GAMER } from '../shared/design/tokens'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const HOST_TONE = {
  EXCLUSIVE_USB: GAMER.green,
  UNKNOWN:       GAMER.t2,
  EXCLUSIVE_BT:  GAMER.orange,
  CONTESTED:     GAMER.red,
  DEGRADED:      GAMER.orange,
  DISCONNECTED:  GAMER.red,
}
const STATE_TONE = {
  NOMINAL:      GAMER.green,
  DEGRADED:     GAMER.orange,
  DISCONNECTED: GAMER.red,
}
const GCTX_TONE = {
  ACTIVE_GAMEPLAY: GAMER.green,
  MENU_DETECTED:   GAMER.red,
}

// Phase 241-APOP — 5-state taxonomy color mapping (mirror INV-APOP-001).
const APOP_TONE = {
  ACTIVE_MATCH_PLAY:    GAMER.cyan,
  COMPETITIVE_CONTROL:  GAMER.green,
  MATCH_TRANSITION:     GAMER.t2,
  NON_COMPETITIVE_MENU: GAMER.red,
  UNKNOWN_LOW_EVIDENCE: GAMER.t3,
}
const APOP_GATE_TONE = {
  shadow: GAMER.t3,
  hybrid: GAMER.cyan,
  strict: GAMER.orange,
}
// Frozen weights mirror INV-APOP-002 — keep prism segment widths in sync
// with the bridge classifier's scoring formula.
const APOP_AXES = [
  { key: 'stick_score',     label: 'STICK',   weight: 0.35 },
  { key: 'button_score',    label: 'BTN',     weight: 0.20 },
  { key: 'trigger_score',   label: 'TRIG',    weight: 0.20 },
  { key: 'imu_score',       label: 'IMU',     weight: 0.15 },
  { key: 'physiology_score', label: 'PHYS',   weight: 0.10 },
]

function tone(map, value, fallback = GAMER.t3) {
  if (value == null) return fallback
  return map[value] ?? fallback
}

function fmtAge(ts) {
  if (!ts || ts === 0) return null
  const s = Math.floor(Date.now() / 1000 - ts)
  if (s < 0)    return 'just now'
  if (s < 60)   return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  return `${Math.floor(s / 3600)}h ago`
}

// ---------------------------------------------------------------------------
// Glass card — shared translucent surface
// ---------------------------------------------------------------------------

function Glass({ children, style, accent = GAMER.cyan, intensity = 1 }) {
  return (
    <div style={{
      background:           `linear-gradient(180deg, rgba(8,18,24,${0.55 * intensity}) 0%, rgba(5,10,15,${0.72 * intensity}) 100%)`,
      backdropFilter:       'blur(14px) saturate(140%)',
      WebkitBackdropFilter: 'blur(14px) saturate(140%)',
      border:               `1px solid ${accent}26`,
      borderRadius:         8,
      boxShadow:            `0 0 24px ${accent}1a, inset 0 1px 0 rgba(255,255,255,0.04)`,
      ...style,
    }}>
      {children}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Top-left: session badge
// ---------------------------------------------------------------------------

function SessionBadge({ sessionId, magnitude }) {
  return (
    <Glass style={{ position: 'absolute', top: 62, left: 16, padding: '6px 12px', zIndex: 10 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <span style={{ fontFamily: FONTS.mono, fontSize: 7, letterSpacing: '0.18em', color: GAMER.t3 }}>
          GRIND SESSION
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{
            display: 'inline-block', width: 5, height: 5, borderRadius: '50%',
            background: GAMER.cyan,
            boxShadow: `0 0 ${4 + magnitude * 8}px ${GAMER.cyan}`,
            transition: 'box-shadow 0.4s ease',
          }} />
          <span style={{ fontFamily: FONTS.mono, fontSize: 11, color: GAMER.t1, letterSpacing: '0.04em' }}>
            {sessionId}
          </span>
        </div>
      </div>
    </Glass>
  )
}

// ---------------------------------------------------------------------------
// Top-right: live chain + fleet badge
// ---------------------------------------------------------------------------

function LiveStatusBadge({ intact, onChain, agentCount, merkleRoot }) {
  return (
    <Glass
      style={{ position: 'absolute', top: 62, right: 16, padding: '6px 12px', zIndex: 10 }}
      accent={intact ? GAMER.green : GAMER.red}
    >
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 2 }}>
        <span style={{
          fontFamily:    FONTS.mono,
          fontSize:      9,
          fontWeight:    600,
          color:         intact ? GAMER.green : GAMER.red,
          letterSpacing: '0.12em',
        }}>
          {intact ? '● CHAIN INTACT' : '⚠ CHAIN BROKEN'}
        </span>
        <span style={{ fontFamily: FONTS.mono, fontSize: 7, color: GAMER.t3, letterSpacing: '0.08em' }}>
          {agentCount} AGENTS · {onChain ? 'ON-CHAIN' : 'PENDING'}
          {merkleRoot && ` · ${merkleRoot.slice(-8)}`}
        </span>
      </div>
    </Glass>
  )
}

// ---------------------------------------------------------------------------
// Top-center: GRIND PROGRESS
//
// Primary metric: chain_length (cumulative GIC-stamped sessions).
// This is the number that fills the bar and matches check_grind.py output.
// consecutive_clean_toward_target (the running streak) is shown as a small
// secondary line — the two diverge whenever a session breaks the streak.
//
// Sub-strip (one line, dim): velocity · projected date · success rate ·
// last-validated age · top blocking reason.
// The entire card stays inside the top-edge safe zone.
// ---------------------------------------------------------------------------

function GrindProgressBar({
  consecutiveClean, chainLen, target,
  intact, magnitude, paused,
  successRate, sessionsPerDay, projectedDate, lastValidAge, topBlocker,
}) {
  const primary   = chainLen            // cumulative GIC stamps — the progress number
  const pct       = Math.min(1, primary / Math.max(1, target))
  const completed = primary >= target
  const barColor  = completed ? GAMER.green : paused ? GAMER.orange : GAMER.cyan
  const glow      = 4 + magnitude * 12

  // Show "STREAK: N" when streak differs from total (i.e. after any break)
  const showStreak = consecutiveClean !== primary

  return (
    <div style={{
      position:  'absolute',
      top:       106,
      left:      '50%',
      transform: 'translateX(-50%)',
      width:     500,
      maxWidth:  'calc(100vw - 360px)',
      zIndex:    9,
    }}>
      <Glass accent={barColor} intensity={1.0} style={{ padding: '8px 14px' }}>

        {/* Header: label (left) + count (right) */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, marginBottom: 6 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <span style={{
              fontFamily:    FONTS.mono,
              fontSize:      7,
              color:         GAMER.t3,
              letterSpacing: '0.18em',
              whiteSpace:    'nowrap',
            }}>
              GRIND INTEGRITY CHAIN
            </span>
            {showStreak && (
              <span style={{ fontFamily: FONTS.mono, fontSize: 6.5, color: GAMER.orange, letterSpacing: '0.06em' }}>
                STREAK: {consecutiveClean}
              </span>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
            <span style={{
              fontFamily:    FONTS.display,
              fontSize:      32,
              fontWeight:    700,
              lineHeight:    1,
              color:         barColor,
              letterSpacing: '-0.02em',
              textShadow:    `0 0 ${glow}px ${barColor}aa`,
              transition:    'color 0.4s ease, text-shadow 0.4s ease',
            }}>
              {primary}
            </span>
            <span style={{ fontFamily: FONTS.display, fontSize: 16, fontWeight: 500, color: GAMER.t2 }}>
              / {target}
            </span>
          </div>
        </div>

        {/* Progress bar */}
        <div style={{ height: 4, background: 'rgba(255,255,255,0.05)', borderRadius: 2, overflow: 'hidden', marginBottom: 7 }}>
          <motion.div
            initial={false}
            animate={{ width: `${pct * 100}%` }}
            transition={{ duration: 0.8, ease: 'easeInOut' }}
            style={{
              height:     '100%',
              background: completed
                ? `linear-gradient(90deg, ${GAMER.green}, ${GAMER.cyan})`
                : `linear-gradient(90deg, ${barColor}, ${GAMER.cyan})`,
              boxShadow:  pct > 0 ? `0 0 ${4 + magnitude * 6}px ${barColor}` : 'none',
            }}
          />
        </div>

        {/* Velocity sub-strip — never taller than one line */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
            {sessionsPerDay != null && sessionsPerDay > 0 && (
              <span style={{ fontFamily: FONTS.mono, fontSize: 7, color: GAMER.t2, letterSpacing: '0.04em' }}>
                ~{sessionsPerDay.toFixed(1)}/day
              </span>
            )}
            {projectedDate && (
              <span style={{ fontFamily: FONTS.mono, fontSize: 7, color: GAMER.t3, letterSpacing: '0.04em' }}>
                est. {projectedDate}
              </span>
            )}
            {successRate != null && (
              <span style={{ fontFamily: FONTS.mono, fontSize: 7, color: GAMER.t3, letterSpacing: '0.04em' }}>
                {Math.round(successRate * 100)}% valid
              </span>
            )}
          </div>
          {lastValidAge && (
            <span style={{ fontFamily: FONTS.mono, fontSize: 7, color: GAMER.t3, letterSpacing: '0.04em' }}>
              last {lastValidAge}
            </span>
          )}
        </div>

        {/* Top blocker — amber, only shown when a reason exists */}
        {topBlocker && (
          <div style={{ marginTop: 5, fontFamily: FONTS.mono, fontSize: 7, color: GAMER.orange, letterSpacing: '0.06em' }}>
            blocked: {topBlocker}
          </div>
        )}

        {/* Paused warning — only when no blocker text (avoids double line) */}
        {paused && !topBlocker && (
          <div style={{ marginTop: 5, fontFamily: FONTS.mono, fontSize: 7.5, color: GAMER.orange, textAlign: 'center', letterSpacing: '0.08em' }}>
            ⚠ PAUSED — needs NOMINAL + EXCLUSIVE_USB
          </div>
        )}
      </Glass>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Bottom edge: 7 compact status chips
// All sit on the bottom strip — no contact with the controller twin body.
// ---------------------------------------------------------------------------

function StatusChip({ label, value, color }) {
  return (
    <Glass accent={color} style={{ padding: '6px 12px', minWidth: 90 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
        <span style={{ fontFamily: FONTS.mono, fontSize: 6.5, letterSpacing: '0.16em', color: GAMER.t3 }}>
          {label}
        </span>
        <span style={{ fontFamily: FONTS.mono, fontSize: 10, fontWeight: 600, color, letterSpacing: '0.04em', whiteSpace: 'nowrap' }}>
          {value}
        </span>
      </div>
    </Glass>
  )
}

function StatusBar({ host, state, gctx, ready, coherence, autoTrigger, ait, apop, curator }) {
  // GAMEPLAY chip
  const gctxValue = gctx ?? 'WAITING'
  const gctxColor = gctx ? tone(GCTX_TONE, gctx) : GAMER.t2
  const gctxTitle = gctx ? undefined : 'No rulings validated yet — populates after first GIC stamp'

  // COHERENCE chip — FleetSignalCoherenceAgent
  const cohC     = coherence?.active_contradictions ?? 0
  const cohH     = coherence?.active_orphans ?? 0
  const cohI     = coherence?.active_inversions ?? 0
  const cohValue = cohC === 0 && cohH === 0 && cohI === 0 ? 'CLEAN' : `${cohC}C·${cohH}H·${cohI}I`
  const cohColor = cohC > 0 ? GAMER.red : cohH > 0 ? GAMER.orange : GAMER.green

  // AUTO-TRIGGER chip — SessionBoundaryDetectorAgent
  let atValue, atColor
  if (!autoTrigger || autoTrigger.agent_alive === false) {
    atValue = 'OFF';   atColor = GAMER.t3
  } else if (autoTrigger.stopped) {
    atValue = 'DONE';  atColor = GAMER.green
  } else if (autoTrigger.next_eligible_in_s > 0) {
    atValue = `NEXT ~${Math.round(autoTrigger.next_eligible_in_s)}s`; atColor = GAMER.cyan
  } else {
    atValue = 'ARMED'; atColor = GAMER.green
  }
  const atTitle = autoTrigger
    ? `fires_this_run=${autoTrigger.fires_this_run} · min_interval=${autoTrigger.min_interval_s}s · quiescence=${autoTrigger.quiescence_window} records`
    : undefined

  // AIT chip — biometric inter-player separation certification
  const aitAbove = ait?.all_pairs_above_1 ?? false
  const aitRatio = ait?.separation_ratio
  const aitValue = aitAbove
    ? (aitRatio != null ? `${aitRatio.toFixed(3)} ✓` : 'CLEAR')
    : ait == null ? '—' : 'PENDING'
  const aitColor = aitAbove ? GAMER.green : ait == null ? GAMER.t3 : GAMER.orange
  const aitTitle = ait
    ? `AIT separation ratio=${aitRatio?.toFixed(3)} all_pairs_above_1=${aitAbove}`
    : 'AIT data not yet available'

  return (
    <div style={{
      position:       'absolute',
      bottom:         16,
      left:           '50%',
      transform:      'translateX(-50%)',
      display:        'flex',
      gap:            8,
      zIndex:         9,
      flexWrap:       'wrap',
      maxWidth:       'calc(100vw - 64px)',
      justifyContent: 'center',
    }}>
      <StatusChip label="HOST"         value={host  ?? '—'} color={tone(HOST_TONE, host)} />
      <StatusChip label="PCC"          value={state ?? '—'} color={tone(STATE_TONE, state)} />
      {/* Phase 241-APOP: GAMEPLAY chip is only authoritative in shadow mode.
          In hybrid/strict, APOP is the actual gate — hiding GAMEPLAY here
          prevents misleading red MENU_DETECTED when consecutive_clean is
          actually advancing via APOP rescue. Legacy GAD data still in DB
          for audit; surfaced in DeveloperView. */}
      {(!apop || apop.gate_mode === 'shadow') && (
        <span title={gctxTitle}>
          <StatusChip label="GAMEPLAY"   value={gctxValue}         color={gctxColor} />
        </span>
      )}
      <StatusChip label="READY"        value={ready ? 'YES' : 'NO'} color={ready ? GAMER.green : GAMER.orange} />
      <StatusChip label="COHERENCE"    value={cohValue}          color={cohColor} />
      <span title={atTitle}>
        <StatusChip label="AUTO-TRIGGER" value={atValue}         color={atColor} />
      </span>
      <span title={aitTitle}>
        <StatusChip label="AIT"        value={aitValue}          color={aitColor} />
      </span>
      {/* Phase 238-FRONTEND-V3 — Curator review surface in HUD.
          Hidden when the bridge has not exposed curator status (e.g. read-key
          missing or curator agent not deployed) so the chip strip stays
          quiet for non-Operator-tier deployments. */}
      {curator?.curator_review_enabled && (() => {
        const flagged = Number(curator.flagged_reviews || 0)
        const total   = Number(curator.total_reviews || 0)
        const value   = flagged > 0 ? `${flagged}/${total}` : (total > 0 ? `${total}` : 'IDLE')
        const color   = flagged > 0 ? GAMER.orange : total > 0 ? GAMER.cyan : GAMER.t2
        const title   = `Curator agent (Operator Initiative #3) — ${total} reviews · ${flagged} flagged · click DeveloperView for review log`
        return (
          <span title={title}>
            <StatusChip label="CURATOR" value={value} color={color} />
          </span>
        )
      })()}
      {(() => {
        // Phase 241-APOP — Active Play Occupancy chip.
        // Compact: state value (or WAITING) + gate_mode pill.
        if (!apop) {
          return <StatusChip label="APOP" value="—" color={GAMER.t3} />
        }
        const apopState = apop.latest_state ?? 'WAITING'
        const apopColor = apop.latest_state ? (APOP_TONE[apop.latest_state] ?? GAMER.t3) : GAMER.t2
        const apopMode  = apop.gate_mode ?? 'shadow'
        const apopGateColor = APOP_GATE_TONE[apopMode] ?? GAMER.t3
        const apopConf  = (apop.latest_confidence ?? 0) > 0
          ? ` · ${(apop.latest_confidence * 100).toFixed(0)}%` : ''
        const apopTitle = apop.latest_state
          ? `gate=${apopMode} · score=${(apop.latest_score ?? 0).toFixed(3)} · conf=${(apop.latest_confidence ?? 0).toFixed(3)} · total_logs=${apop.total_logs ?? 0}`
          : `gate=${apopMode} · awaiting first ruling validation`
        return (
          <span title={apopTitle} style={{ position: 'relative' }}>
            <StatusChip label="APOP" value={`${apopState}${apopConf}`} color={apopColor} />
            <span style={{
              position: 'absolute', top: -6, right: -6,
              padding: '1px 5px', borderRadius: 3,
              background: apopGateColor + 'd0', color: '#02060a',
              fontFamily: FONTS.mono, fontSize: 6, fontWeight: 700,
              letterSpacing: '0.12em', textTransform: 'uppercase',
              boxShadow: `0 0 8px ${apopGateColor}66`,
            }}>{apopMode}</span>
          </span>
        )
      })()}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Phase 241-APOP — Evidence Prism
// Novel multi-evidence visualization. Five horizontal segments — one per
// scoring axis (stick/button/trigger/imu/physiology) — with widths exactly
// matching the FROZEN INV-APOP-002 weights (0.35/0.20/0.20/0.15/0.10).
// Each segment fills proportionally to its raw score; tinted by the active
// APOP state color. Centered below StatusBar; transparent + low-profile so
// it never visually competes with the GIC chain bar above.
// ---------------------------------------------------------------------------

function ApopEvidencePrism({ apop }) {
  if (!apop || !apop.latest_state) return null
  const evidence = apop.latest_evidence || {}
  const stateColor = APOP_TONE[apop.latest_state] ?? GAMER.t2
  const isCompetitive = apop.latest_state === 'ACTIVE_MATCH_PLAY' || apop.latest_state === 'COMPETITIVE_CONTROL'

  // Each axis: {label, weight, score 0..1}
  const segments = APOP_AXES.map(axis => ({
    ...axis,
    score: Math.max(0, Math.min(1, Number(evidence[axis.key] ?? 0))),
  }))

  return (
    <div style={{
      position:  'absolute',
      bottom:    72,             // sits above StatusBar (which is bottom: 32)
      left:      '50%',
      transform: 'translateX(-50%)',
      zIndex:    8,
      width:     420,
      pointerEvents: 'none',     // transparent to clicks; visual only
    }}>
      <Glass accent={stateColor} intensity={0.7} style={{ padding: '6px 10px' }}>
        {/* Top label row: state + score + history */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 5 }}>
          <span style={{
            fontFamily: FONTS.mono, fontSize: 6.5, letterSpacing: '0.18em', color: GAMER.t3,
          }}>
            EVIDENCE PRISM · APOP
          </span>
          <span style={{
            fontFamily: FONTS.mono, fontSize: 8, color: stateColor, letterSpacing: '0.04em',
            fontWeight: 600,
            textShadow: isCompetitive ? `0 0 6px ${stateColor}66` : 'none',
          }}>
            {(apop.latest_score ?? 0).toFixed(3)} · h{(evidence.history_score ?? 0).toFixed(2)}
          </span>
        </div>

        {/* Prism: five horizontal segments, widths = FROZEN weights */}
        <div style={{ display: 'flex', gap: 2, height: 8, alignItems: 'stretch' }}>
          {segments.map(seg => (
            <div key={seg.key} style={{
              flex:           seg.weight,
              background:     '#0a1620',
              borderRadius:   2,
              border:         `1px solid ${stateColor}26`,
              position:       'relative',
              overflow:       'hidden',
            }}>
              {/* Inner fill — proportional to score, tinted by state */}
              <div style={{
                position:   'absolute',
                left:       0, top: 0, bottom: 0,
                width:      `${seg.score * 100}%`,
                background: `linear-gradient(90deg, ${stateColor}55 0%, ${stateColor}cc 100%)`,
                boxShadow:  seg.score > 0.5 ? `inset 0 0 4px ${stateColor}88` : 'none',
                transition: 'width 0.6s ease, background 0.4s ease',
              }} />
            </div>
          ))}
        </div>

        {/* Axis labels — perfectly aligned with segments above */}
        <div style={{ display: 'flex', gap: 2, marginTop: 3 }}>
          {segments.map(seg => (
            <div key={seg.key} style={{
              flex: seg.weight,
              fontFamily: FONTS.mono,
              fontSize:   5.5,
              letterSpacing: '0.14em',
              color:      seg.score > 0.4 ? GAMER.t1 : GAMER.t3,
              textAlign:  'center',
              transition: 'color 0.4s ease',
            }}>
              {seg.label}
            </div>
          ))}
        </div>
      </Glass>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Right-edge PCC drawer
// Collapsed handle is always visible at the right edge (28px).
// Drawer slides in on PCC stress or manual click.
// Includes live snapshot + contention episode history from /grind/pcc-intelligence.
// ---------------------------------------------------------------------------

function pccIsConcerning(captureHealth) {
  if (!captureHealth) return false
  if (captureHealth.capture_state && captureHealth.capture_state !== 'NOMINAL') return true
  if (captureHealth.host_state && !['EXCLUSIVE_USB', 'UNKNOWN'].includes(captureHealth.host_state)) return true
  if (captureHealth.session_counting_paused) return true
  return false
}

function PCCDrawer({ captureHealth, pccIntelligence, manualOpen, onCloseManual }) {
  const concerning = pccIsConcerning(captureHealth)
  const open       = concerning || manualOpen

  const state     = captureHealth?.capture_state ?? '—'
  const host      = captureHealth?.host_state ?? '—'
  const rate      = captureHealth?.poll_rate_hz ?? 0
  const sustained = captureHealth?.sustained_duration_s ?? 0
  const ready     = captureHealth?.grind_ready ?? false
  const paused    = captureHealth?.session_counting_paused ?? false

  // PCCIntelligence — contention episode history
  const episodes    = pccIntelligence?.total_episodes ?? 0
  const meanRecov   = pccIntelligence?.mean_recovery_s
  const longestEp   = pccIntelligence?.longest_episode_s
  const hidRestarts = pccIntelligence?.hid_counter_restarts ?? 0
  const hasHistory  = pccIntelligence != null

  return (
    <>
      {/* Collapsed handle — always anchored to the right viewport edge */}
      <div
        onClick={() => onCloseManual(!manualOpen)}
        style={{
          position:     'absolute',
          top:          '50%',
          right:        open ? 320 : 0,
          transform:    'translateY(-50%)',
          width:        28,
          height:       96,
          background:   concerning ? GAMER.red + 'cc' : GAMER.cyan + '26',
          border:       `1px solid ${concerning ? GAMER.red : GAMER.cyan}66`,
          borderRight:  'none',
          borderRadius: '6px 0 0 6px',
          cursor:       'pointer',
          zIndex:       11,
          display:      'flex',
          alignItems:   'center',
          justifyContent: 'center',
          transition:   'right 0.32s ease, background 0.4s ease',
          boxShadow:    concerning ? `0 0 16px ${GAMER.red}88` : 'none',
        }}
        title={concerning ? 'PCC alert — click to inspect' : 'PCC details'}
      >
        <span style={{
          fontFamily:    FONTS.mono,
          fontSize:      8,
          color:         concerning ? '#fff' : GAMER.cyan,
          letterSpacing: '0.16em',
          writingMode:   'vertical-rl',
          transform:     'rotate(180deg)',
        }}>
          {concerning ? '⚠ PCC' : 'PCC ▶'}
        </span>
      </div>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ x: 320 }} animate={{ x: 0 }} exit={{ x: 320 }}
            transition={{ duration: 0.32, ease: 'easeInOut' }}
            style={{ position: 'absolute', top: 0, right: 0, bottom: 0, width: 320, zIndex: 10 }}
          >
            <Glass
              accent={concerning ? GAMER.red : GAMER.cyan}
              style={{
                height:       '100%',
                borderRadius: 0,
                borderLeft:   `1px solid ${concerning ? GAMER.red : GAMER.cyan}33`,
                padding:      '16px 16px',
                overflow:     'auto',
              }}
            >
              {/* Drawer header */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                <span style={{
                  fontFamily:    FONTS.mono,
                  fontSize:      9,
                  letterSpacing: '0.16em',
                  color:         concerning ? GAMER.red : GAMER.cyan,
                  fontWeight:    600,
                }}>
                  PHYSICAL CAPTURE CONTINUITY
                </span>
                <button
                  onClick={() => onCloseManual(false)}
                  style={{ background: 'transparent', border: 'none', color: GAMER.t2, cursor: 'pointer', fontFamily: FONTS.mono, fontSize: 14 }}
                >×</button>
              </div>

              {/* Alert banner */}
              {concerning && (
                <div style={{
                  background:   GAMER.red + '14',
                  border:       `1px solid ${GAMER.red}44`,
                  borderRadius: 4,
                  padding:      '10px 12px',
                  marginBottom: 16,
                  fontFamily:   FONTS.mono,
                  fontSize:     9,
                  color:        GAMER.red,
                  lineHeight:   1.5,
                }}>
                  ⚠ {paused
                    ? 'Session counting paused. Sessions will not advance toward GIC_N until protocol returns to NOMINAL + EXCLUSIVE_USB.'
                    : 'Protocol fail-closed. Verify USB cable, check Bluetooth pairing state, ensure controller is not in PS5 menu.'}
                </div>
              )}

              {/* Live snapshot */}
              <DrawerStat label="capture_state"           value={state}                      color={tone(STATE_TONE, state)} />
              <DrawerStat label="host_state"              value={host}                       color={tone(HOST_TONE, host)} />
              <DrawerStat label="poll_rate_hz"            value={rate.toFixed(1) + ' Hz'}    color={GAMER.t1} />
              <DrawerStat label="sustained_duration_s"    value={sustained.toFixed(1) + 's'} color={GAMER.t1} />
              <DrawerStat label="grind_ready"             value={ready ? 'true' : 'false'}   color={ready ? GAMER.green : GAMER.orange} />
              <DrawerStat label="session_counting_paused" value={paused ? 'true' : 'false'}  color={paused ? GAMER.orange : GAMER.t2} />

              {/* Contention episode history from /grind/pcc-intelligence */}
              {hasHistory && (
                <>
                  <div style={{
                    marginTop:     20,
                    paddingTop:    14,
                    borderTop:     `1px solid ${GAMER.bd}`,
                    marginBottom:  10,
                    fontFamily:    FONTS.mono,
                    fontSize:      8,
                    color:         GAMER.t2,
                    letterSpacing: '0.12em',
                  }}>
                    CONTENTION HISTORY
                  </div>

                  <DrawerStat
                    label="episodes this session"
                    value={episodes}
                    color={episodes === 0 ? GAMER.green : episodes < 3 ? GAMER.orange : GAMER.red}
                  />
                  {meanRecov != null && (
                    <DrawerStat label="mean recovery" value={meanRecov.toFixed(1) + 's'} color={GAMER.t1} />
                  )}
                  {longestEp != null && (
                    <DrawerStat label="longest episode" value={longestEp.toFixed(1) + 's'} color={GAMER.t1} />
                  )}
                  <DrawerStat
                    label="hid counter restarts"
                    value={hidRestarts}
                    color={hidRestarts === 0 ? GAMER.green : GAMER.orange}
                  />

                  {episodes === 0 && hidRestarts === 0 && (
                    <div style={{
                      marginTop:  8,
                      fontFamily: FONTS.mono,
                      fontSize:   7.5,
                      color:      GAMER.green,
                    }}>
                      No contention episodes — USB environment is clean
                    </div>
                  )}
                </>
              )}

              {/* Host state legend */}
              <div style={{
                marginTop:  20,
                paddingTop: 14,
                borderTop:  `1px solid ${GAMER.bd}`,
                fontFamily: FONTS.mono,
                fontSize:   8,
                color:      GAMER.t3,
                lineHeight: 1.6,
              }}>
                <div style={{ marginBottom: 4, color: GAMER.t2 }}>HOST STATE LEGEND</div>
                <div><span style={{ color: GAMER.green }}>EXCLUSIVE_USB</span> — USB poll ≥900 Hz, CV &lt;0.20</div>
                <div><span style={{ color: GAMER.t2 }}>UNKNOWN</span> — bootstrap window or sample-starved</div>
                <div><span style={{ color: GAMER.orange }}>EXCLUSIVE_BT</span> — BT host (200–350 Hz)</div>
                <div><span style={{ color: GAMER.red }}>CONTESTED</span> — CV ≥0.40, host arbitration race</div>
              </div>
            </Glass>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}

function DrawerStat({ label, value, color }) {
  return (
    <div style={{
      display:        'flex',
      justifyContent: 'space-between',
      alignItems:     'baseline',
      padding:        '6px 0',
      borderBottom:   `1px solid ${GAMER.bd2}`,
    }}>
      <span style={{ fontFamily: FONTS.mono, fontSize: 8, color: GAMER.t3, letterSpacing: '0.06em' }}>
        {label}
      </span>
      <span style={{ fontFamily: FONTS.mono, fontSize: 10, color, fontWeight: 500 }}>
        {value}
      </span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main view
// ---------------------------------------------------------------------------

export function GamerView() {
  const magnitude  = useHeartbeatStore((s) => s.magnitude)
  const merkleRoot = useHeartbeatStore((s) => s.merkleRoot)
  const onChain    = useHeartbeatStore((s) => s.onChainConfirmed)
  const agentCount = useHeartbeatStore((s) => s.agentCount)

  const { data: captureHealth }   = useCaptureHealth()
  const { data: grindChain }      = useGrindChain()
  const { data: coherence }       = useFleetCoherenceStatus()
  const { data: autoTrigger }     = useAutoTriggerStatus()
  const { data: grindAnalytics }  = useGrindAnalytics()
  const { data: ait }             = useAITSeparation()
  const { data: pccIntelligence } = usePCCIntelligence()
  const { data: apop }            = useActivePlayOccupancy()
  // Phase 238-FRONTEND-V3 — Curator status for HUD chip + ConsentMatrix
  // mini-pill render gating.  noMock surfaced via the hook; if the bridge is
  // unreachable the value is undefined and the chip is hidden.
  const { data: curator }         = useCuratorStatus()

  // Two complementary grind metrics, both surfaced in the progress card:
  //   chain_length            — cumulative GIC stamps (Phase 235-A); monotonically grows.
  //                             This is what fills the progress bar (matches check_grind.py).
  //   consecutive_clean_toward_target — leading streak of non-divergent + PCC-attested +
  //                             gameplay-confirmed rulings; resets when a session breaks the
  //                             streak. Determines gate_passed (>= 100). Shown as a small
  //                             secondary line "STREAK: N" only when it diverges from chain_length.
  // The two diverge whenever a recent ruling is divergent / PCC-not-NOMINAL / MENU_DETECTED.
  // Audit 2026-04-26 confirmed correct: e.g. chain_length=20 with consecutive_clean=0 means
  // 20 GIC stamps exist but the most recent ruling broke the streak.
  const consecutiveClean = captureHealth?.consecutive_clean_toward_target ?? 0
  const chainLen         = grindChain?.chain_length ?? 0
  const target           = captureHealth?.grind_target ?? grindChain?.grind_target ?? 100
  const intact           = grindChain?.chain_intact ?? true
  const sessionId        = grindChain?.grind_session_id ?? '—'
  const host             = captureHealth?.host_state
  const state            = captureHealth?.capture_state
  const gctx             = captureHealth?.latest_gameplay_context
  const ready            = captureHealth?.grind_ready ?? false
  const paused           = captureHealth?.session_counting_paused ?? false

  // GrindAnalytics-derived sub-strip values
  const successRate    = grindAnalytics?.success_rate
  const sessionsPerDay = grindAnalytics?.sessions_per_day
  const projectedDate  = grindAnalytics?.projected_gic100_date
  const lastValidAge   = fmtAge(grindAnalytics?.last_validation_ts)

  // Top blocking reason — highest count entry from blocking_reason_counts
  const topBlocker = useMemo(() => {
    const counts = grindAnalytics?.blocking_reason_counts
    if (!counts || Object.keys(counts).length === 0) return null
    const [reason, n] = Object.entries(counts).sort((a, b) => b[1] - a[1])[0]
    const label = reason.replace('PCC_NOT_NOMINAL:', '').replace(/_/g, ' ')
    return `${label} ×${n}`
  }, [grindAnalytics])

  const [drawerManual, setDrawerManual] = useState(false)
  const [consentOpen, setConsentOpen] = useState(false)

  // Audit fix: surface a banner when sessionStorage flag indicates the bridge
  // is unreachable and we're rendering mock data. Without this, fabricated
  // values (sessions_per_day, projected ETAs, AIT ratios) read as live state.
  const [mockShown, setMockShown] = useState(isMockActive())
  useEffect(() => {
    const id = setInterval(() => setMockShown(isMockActive()), 2000)
    return () => clearInterval(id)
  }, [])

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', background: GAMER.bg, overflow: 'hidden' }}>

      {/* 3D controller twin — full-bleed canvas, the hero visual */}
      <iframe
        src="/controller-twin.html?minimal=1"
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', border: 'none', background: 'transparent', zIndex: 1 }}
        title="VAPI 3D Controller Twin"
      />

      {/* Edge vignette — center fully transparent, controller stays sharp */}
      <div style={{
        position:      'absolute',
        inset:         0,
        pointerEvents: 'none',
        background:    'radial-gradient(ellipse at center, transparent 55%, rgba(2,4,8,0.45) 100%)',
        zIndex:        2,
      }} />

      {/* Phase 238-FRONTEND-V4 — PoAC Chain accretion ribbon at top edge.
          Visualizes the GIC chain primitive (Phase 235-A) growing in real
          time. Subscribes to twin-stream SSE for poac_chain_link + gic_verdict
          to pulse the rightmost dot. Pointer-events:none → does not block
          the badges that overlay below. */}
      <PoacChainRibbon
        chainLen={chainLen}
        target={target}
        intact={intact}
        latestHash={grindChain?.latest_gic_hash}
        sessionId={sessionId}
      />

      {/* HUD overlays — all confined to screen edges */}
      <SessionBadge sessionId={sessionId} magnitude={magnitude} />

      <LiveStatusBadge
        intact={intact}
        onChain={onChain}
        agentCount={agentCount}
        merkleRoot={merkleRoot}
      />

      <GrindProgressBar
        consecutiveClean={consecutiveClean}
        chainLen={chainLen}
        target={target}
        intact={intact}
        magnitude={magnitude}
        paused={paused}
        successRate={successRate}
        sessionsPerDay={sessionsPerDay}
        projectedDate={projectedDate}
        lastValidAge={lastValidAge}
        topBlocker={topBlocker}
      />

      <StatusBar
        host={host}
        state={state}
        gctx={gctx}
        ready={ready}
        coherence={coherence}
        autoTrigger={autoTrigger}
        ait={ait}
        apop={apop}
        curator={curator}
      />

      {/* Phase 238-FRONTEND-V3 — ConsentMatrix HUD mini.
          Compact 4-bit consent indicator in the top-right area, anchored
          below LiveStatusBadge. Displays cleared/granted bits for the four
          frozen categories (TOURNAMENT_GATE / ANONYMIZED_RESEARCH /
          MANUFACTURER_CERT / MARKETPLACE).  Read-only here — gamer changes
          their bitmask via the existing right-edge ConsentPanel. */}
      <div style={{
        position:      'absolute',
        top:           126,
        right:         16,
        zIndex:        9,
        padding:       '6px 10px',
        background:    'rgba(2,4,8,0.72)',
        border:        '1px solid var(--vapi-cyan)',
        borderRadius:  3,
        backdropFilter: 'blur(6px)',
        display:       'flex',
        alignItems:    'center',
        gap:           8,
        cursor:        'pointer',
      }}
        onClick={() => setConsentOpen(true)}
        title="Click to open per-category consent panel"
      >
        <span style={{
          fontFamily:    FONTS.mono,
          fontSize:      8,
          color:         'var(--vapi-tier-basic)',
          letterSpacing: '0.08em',
        }}>CONSENT</span>
        <ConsentMatrix bitmask={curator?.consent_bitmask ?? 0b1111} mode="compact" />
      </div>

      {/* Phase 241-APOP — Evidence Prism (novel weighted-evidence visualization). */}
      <ApopEvidencePrism apop={apop} />

      <PCCDrawer
        captureHealth={captureHealth}
        pccIntelligence={pccIntelligence}
        manualOpen={drawerManual}
        onCloseManual={setDrawerManual}
      />

      {/* Phase 237-EXTEND — per-category consent panel; right-edge drawer. */}
      <ConsentPanel
        manualOpen={consentOpen}
        onCloseManual={setConsentOpen}
      />

      {mockShown && (
        <div style={{
          position:     'absolute',
          top:          0,
          left:         0,
          right:        0,
          padding:      '4px 12px',
          background:   GAMER.orange + 'cc',
          color:        '#0c0500',
          fontFamily:   FONTS.mono,
          fontSize:     9,
          letterSpacing: '0.16em',
          textAlign:    'center',
          fontWeight:   700,
          zIndex:       50,
        }}>
          ⚠ MOCK DATA — BRIDGE OFFLINE — values are fabricated, not live grind state
        </div>
      )}
    </div>
  )
}
