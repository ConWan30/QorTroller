// QorTroller Gamer Dashboard — QRESCE-0001 v0.5 grant-evaluator remodel.
//
// Composition ported from the Claude-design export (bundle 5): a full-bleed
// 3D Controller Twin (the emotional hero — humanity made visible) on a
// forensic-instrument graticule stage, with capture-health, latest-GIC,
// fleet-coherence, consent and analytics floating as translucent overlay
// panels around it, and the grind-integrity chain growing along the bottom.
//
// HONESTY-PRESERVING ADAPTATIONS over the design export:
//   - The twin is the REAL iframe (/controller-twin.html?minimal=1), never a
//     placeholder — the design's ControllerTwinSlot was a prototype stand-in.
//   - The chain ribbon advances ONLY on the real polled chain_length (via
//     useChainPulse); the export's useChainAdvance simulated growth.
//   - The latest-GIC panel shows the REAL grindChain.latest_gic_hash; the
//     "settle" motion fires when that real hash actually changes. (In-browser
//     re-derivation lives in ForensicView where the real preimage exists — we
//     do NOT fake a re-derive here.)
//   - All telemetry comes from the real bridge hooks (noMock:true); a bridge
//     outage surfaces the explicit MOCK banner, never fabricated values.
//
// Load-bearing surfaces from the prior GamerView are preserved verbatim:
//   - ApopEvidencePrism (mirrors FROZEN INV-APOP-002 weights)
//   - PCCDrawer (contention episode history)
//   - the chain_length vs consecutive_clean two-metric distinction
//   - the per-category consent surface + ConsentPanel drawer

import { useEffect, useMemo, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useHeartbeatStore } from '../heartbeat/useHeartbeat'
import { useAccount } from 'wagmi'
import {
  useCaptureHealth, useGrindChain, useGrindAnalytics,
  usePCCIntelligence, useActivePlayOccupancy, useConsentStatus,
} from '../api/bridgeApi'
import { ConsentPanel } from '../components/ConsentPanel'
import { FONTS, GAMER } from '../shared/design/tokens'
import { OverlayPanel, StatusChip, HashSpecimen } from '../design/Primitives'
import { useChainPulse, useRelativeTime } from '../design/motion'
import { useQtTweaks, LevelUpBadge } from '../design/Tweaks'
import { useViewEyebrow } from '../design/Eyebrow'
import { GicChainConstellation } from '../design/GicChainConstellation'
import '../design/qortroller-kit.css'

// ---------------------------------------------------------------------------
// Tone maps (preserved from prior GamerView — GAMER palette for telemetry
// instruments; the new chrome uses the design palette via qortroller-kit.css)
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
  { key: 'stick_score',      label: 'STICK', weight: 0.35 },
  { key: 'button_score',     label: 'BTN',   weight: 0.20 },
  { key: 'trigger_score',    label: 'TRIG',  weight: 0.20 },
  { key: 'imu_score',        label: 'IMU',   weight: 0.15 },
  { key: 'physiology_score', label: 'PHYS',  weight: 0.10 },
]

// FROZEN consent categories (CLAUDE.md CONSENT FORMULA v1 — bitmask positions
// MUST match VAPIConsentRegistry.sol position-for-position).
// key MUST match the bridge consent_ledger category names + ConsentPanel.jsx
// CATEGORIES (the FROZEN CONSENT v1 bitmask positions).
const CONSENT_CATEGORIES = [
  { bit: 0, key: 'TOURNAMENT_GATE',     scope: 'TOURNAMENT · GATE' },
  { bit: 1, key: 'ANONYMIZED_RESEARCH', scope: 'ANONYMIZED · RESEARCH' },
  { bit: 2, key: 'MANUFACTURER_CERT',   scope: 'MANUFACTURER · CERT' },
  { bit: 3, key: 'MARKETPLACE',         scope: 'MARKETPLACE' },
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
// Glass — preserved translucent instrument surface (APOP prism + PCC drawer)
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
// Overlay panel header (design forensic-instrument eyebrow + meta)
// ---------------------------------------------------------------------------

function PanelHead({ eye, children }) {
  return (
    <header className="p-head">
      <span className="p-head__eye">{eye}</span>
      {children}
    </header>
  )
}

function Row({ label, value, color = 'var(--text-dim)', size = 12 }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
      <span className="label">{label}</span>
      <span className="mono" style={{ fontSize: size, color }}>{value}</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Top-left: CAPTURE HEALTH
// ---------------------------------------------------------------------------

function CaptureHealthPanel({ capture, paused, bridgeDown }) {
  const stateTone = bridgeDown ? 'blocked' : paused ? 'pending' : 'live'
  const stateText = bridgeDown ? 'BRIDGE UNREACHABLE'
    : paused ? 'COUNTING PAUSED'
      : (capture?.capture_state ?? '—')
  const sustained = capture?.sustained_duration_s ?? 0
  return (
    <OverlayPanel style={{ top: 16, left: 16, width: 264, maxHeight: 'calc(50% - 28px)', overflowY: 'auto' }}>
      <PanelHead eye="CAPTURE · HEALTH">
        <StatusChip tone={stateTone}>{stateText}</StatusChip>
      </PanelHead>
      <div className="p-body" style={{ display: 'grid', gap: 9 }}>
        <Row label="host" value={capture?.host_state ?? '—'}
          color={tone(HOST_TONE, capture?.host_state, 'var(--text)')} />
        <Row label="poll" size={14}
          value={bridgeDown ? '—' : `${capture?.poll_rate_hz ?? 0} HZ`}
          color="var(--accent-amber)" />
        <Row label="sustained"
          value={bridgeDown ? '—' : `${Math.floor(sustained / 60)}m ${Math.round(sustained % 60)}s`} />
        <Row label="ready" value={capture?.grind_ready ? 'YES' : 'NO'}
          color={capture?.grind_ready ? 'var(--chain)' : 'var(--accent-amber)'} />
      </div>
    </OverlayPanel>
  )
}

// ---------------------------------------------------------------------------
// Top-right: LATEST GIC HASH + chain status (real hash, motion on real change)
// ---------------------------------------------------------------------------

function useHashChangedAt(hash) {
  const [settledAt, setSettledAt] = useState(0)
  const [prev, setPrev] = useState(hash)
  useEffect(() => {
    if (hash && hash !== prev) {
      setSettledAt(Date.now())
      setPrev(hash)
    }
  }, [hash, prev])
  return settledAt
}

function LatestGicPanel({ grind, bridgeDown, magnitude }) {
  const hash = grind?.latest_gic_hash || ''
  const settledAt = useHashChangedAt(hash)
  const changedAgo = useRelativeTime(settledAt)
  const sessionId = grind?.grind_session_id ?? '—'
  const glow = 4 + (magnitude ?? 0) * 8
  return (
    <OverlayPanel accent style={{ top: 16, right: 16, width: 332, maxHeight: 'calc(50% - 28px)', overflowY: 'auto' }}>
      <PanelHead eye="LATEST · GIC · HASH">
        <span className="p-head__meta motion--pulse" style={{ color: bridgeDown ? 'var(--status-blocked)' : 'var(--chain)' }}>
          {bridgeDown ? '● STALE' : '● LIVE · SHA-256'}
        </span>
      </PanelHead>
      <div className="p-body">
        <div
          key={hash}
          className={hash ? 'motion--settle' : ''}
          style={{
            minHeight: 38,
            textShadow: hash ? `0 0 ${glow}px #5bd6a355` : 'none',
          }}
        >
          {hash
            ? <HashSpecimen value={hash} size="md" group={4} tone="chain" />
            : <span className="mono" style={{ fontSize: 13, color: 'var(--text-faint)' }}>— awaiting first GIC stamp —</span>}
        </div>
        <div style={{ marginTop: 10, paddingTop: 8, borderTop: '1px solid var(--border-soft)', display: 'grid', gap: 5 }}>
          <Row label="chain"
            value={
              <span>
                <span style={{ color: 'var(--accent-amber)', fontSize: 14, fontWeight: 600 }}>{grind?.chain_length ?? 0}</span>
                <span className="faint"> / {grind?.grind_target ?? 100}</span>
              </span>
            } />
          <Row label="integrity"
            value={grind?.chain_intact === false ? '⚠ BROKEN' : '● INTACT'}
            size={11}
            color={grind?.chain_intact === false ? 'var(--status-blocked)' : 'var(--chain)'} />
          <Row label="last stamp" value={hash ? changedAgo : '—'} size={11} color="var(--accent-amber)" />
          <Row label="session" value={sessionId} size={11} />
        </div>
      </div>
    </OverlayPanel>
  )
}

// ---------------------------------------------------------------------------
// Bottom-left: CONSENT MATRIX (real bitmask → frozen categories)
// ---------------------------------------------------------------------------

// Real per-category consent from /agent/gamer-consent-status (keyed by the
// gamer's wallet-derived device_id). When no wallet is connected we CANNOT
// know consent state — show an honest "—" rather than fabricating GRANTED
// (the prior bug read a non-existent curator.consent_bitmask and defaulted to
// all-GRANTED). The full grant/revoke flow lives in the ConsentPanel drawer.
function ConsentPanelOverlay({ consentStatus, connected, onOpen, ribbonMode }) {
  const known = connected && consentStatus && consentStatus.categories
  const rows = CONSENT_CATEGORIES.map((c) => ({
    ...c,
    granted: known ? Boolean(consentStatus.categories?.[c.key]?.granted) : null,
  }))
  const grantedCount = rows.filter((r) => r.granted === true).length
  return (
    <OverlayPanel style={{
      bottom: ribbonMode ? 100 : 16, left: 16, width: 264, cursor: 'pointer',
      maxHeight: ribbonMode ? 'calc(50% - 124px)' : 'calc(50% - 40px)', overflowY: 'auto',
    }}>
      <div onClick={onOpen} title="Open per-category consent panel">
        <PanelHead eye="CONSENT · MATRIX">
          <span className="p-head__meta">
            {known ? `${grantedCount} / ${rows.length}` : 'CONNECT WALLET'}
          </span>
        </PanelHead>
        <div style={{ padding: '4px 14px 12px' }}>
          {rows.map((row, i) => (
            <div key={row.bit} style={{
              display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) auto', gap: 10,
              padding: '6px 0', alignItems: 'center',
              borderBottom: i < rows.length - 1 ? '1px solid var(--border-soft)' : 0,
            }}>
              <span className="mono" style={{
                fontSize: 10, letterSpacing: '0.04em',
                color: row.granted ? 'var(--text)' : 'var(--text-faint)',
              }}>{row.scope}</span>
              {row.granted === null ? (
                <StatusChip tone="dormant">—</StatusChip>
              ) : (
                <StatusChip tone={row.granted ? 'live' : 'dormant'}>
                  {row.granted ? 'GRANTED' : 'WITHHELD'}
                </StatusChip>
              )}
            </div>
          ))}
        </div>
      </div>
    </OverlayPanel>
  )
}

// ---------------------------------------------------------------------------
// Bottom-right: ANALYTICS (real grind pipeline stats)
// ---------------------------------------------------------------------------

function AnalyticsPanel({ analytics, topBlocker, ribbonMode }) {
  const total = analytics?.total_validated
  return (
    <OverlayPanel style={{
      bottom: ribbonMode ? 100 : 16, right: 16, width: 264,
      maxHeight: ribbonMode ? 'calc(50% - 124px)' : 'calc(50% - 40px)', overflowY: 'auto',
    }}>
      <PanelHead eye="ANALYTICS · GRIND">
        <span className="p-head__meta">{total != null ? total.toLocaleString() : '—'} TOTAL</span>
      </PanelHead>
      <div className="p-body" style={{ display: 'grid', gap: 9 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
          <span className="label">success · rate</span>
          <span className="mono" style={{ fontSize: 22, color: 'var(--chain)' }}>
            {analytics?.success_rate != null ? `${(analytics.success_rate * 100).toFixed(1)}%` : '—'}
          </span>
        </div>
        <Row label="stamped" value={analytics?.stamped_count ?? '—'} />
        <Row label="~ / day"
          value={analytics?.sessions_per_day != null ? analytics.sessions_per_day.toFixed(1) : '—'} size={11} />
        <Row label="proj · gic-100" value={analytics?.projected_gic100_date ?? '—'}
          size={11} color="var(--accent-amber)" />
        {topBlocker && (
          <div style={{ marginTop: 2, fontFamily: 'var(--font-mono)', fontSize: 9.5, color: 'var(--accent-amber)', letterSpacing: '0.05em' }}>
            blocked: {topBlocker}
          </div>
        )}
      </div>
    </OverlayPanel>
  )
}

// ---------------------------------------------------------------------------
// Bottom-center: GRIND CHAIN RIBBON (real chain_length; pulse on real landing)
// ---------------------------------------------------------------------------

function GrindRibbon({ chainLen, target, intact, paused, bridgeDown, consecutiveClean, changedAgo }) {
  const { landingAt } = useChainPulse(chainLen)
  // GIC landing FX is gamer-selectable via Tweaks (pulse / bloom / shockwave /
  // off). It only ever fires on a REAL chain advance (useChainPulse observes the
  // polled chain_length; it never simulates growth) — the vibe layer never
  // fabricates an advancing chain.
  const { landingFx } = useQtTweaks()
  const showStreak = consecutiveClean != null && consecutiveClean !== chainLen
  // Cap the rendered cell count so very large targets stay performant.
  const cells = Math.min(target ?? 100, 100)
  const scale = (target ?? 100) / cells
  return (
    <div style={{
      position: 'absolute', left: 16, right: 16, bottom: 16,
      // Fixed-height container (v2 · item F) so the ribbon never grows into the
      // bottom corner panels as the chain advances; cells scale-X within it.
      height: 72, boxSizing: 'border-box', overflow: 'hidden',
      background: 'rgba(10, 14, 20, 0.92)',
      border: `1px solid ${paused ? 'var(--status-pending)' : 'var(--border)'}`,
      borderRadius: 'var(--radius)', padding: '10px 16px', zIndex: 4,
      backdropFilter: 'blur(6px)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8, alignItems: 'baseline' }}>
        <span className="eye">
          GRIND · INTEGRITY · CHAIN
          {showStreak && (
            <span style={{ color: 'var(--accent-amber)', marginLeft: 10 }}>STREAK {consecutiveClean}</span>
          )}
        </span>
        <span className="mono" style={{ fontSize: 12 }}>
          <span style={{ color: 'var(--accent-amber)', fontSize: 15, fontWeight: 600 }}>{chainLen ?? 0}</span>
          <span className="faint"> / {target ?? 100} · </span>
          {paused ? (
            <span style={{ color: 'var(--status-pending)' }}>● COUNTING PAUSED</span>
          ) : bridgeDown ? (
            <span style={{ color: 'var(--status-blocked)' }}>● BRIDGE UNREACHABLE</span>
          ) : intact === false ? (
            <span style={{ color: 'var(--status-blocked)' }}>⚠ CHAIN BROKEN</span>
          ) : (
            <span style={{ color: 'var(--chain)' }}>● INTACT · {changedAgo}</span>
          )}
        </span>
      </div>
      <div className="ribbon">
        {Array.from({ length: cells }).map((_, i) => {
          const cellThreshold = (i + 1) * scale
          const filled = (chainLen ?? 0) >= cellThreshold
          const isLatest = filled && (i + 1) * scale > (chainLen ?? 0) - scale
          const justLanded = isLatest && landingAt && (Date.now() - landingAt) < 800
          const fxClass = justLanded && landingFx && landingFx !== 'off'
            ? `ribbon__cell--fx-${landingFx}`
            : ''
          return (
            <div
              key={i}
              className={`ribbon__cell ${filled ? 'ribbon__cell--filled' : ''} ${isLatest ? 'ribbon__cell--latest' : ''} ${fxClass}`}
              title={filled ? `≈ GIC #${Math.round(cellThreshold)}` : undefined}
            />
          )
        })}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Phase 241-APOP — Evidence Prism (PRESERVED novel weighted-evidence viz)
// ---------------------------------------------------------------------------

function ApopEvidencePrism({ apop }) {
  if (!apop || !apop.latest_state) return null
  const evidence = apop.latest_evidence || {}
  const stateColor = APOP_TONE[apop.latest_state] ?? GAMER.t2
  const isCompetitive = apop.latest_state === 'ACTIVE_MATCH_PLAY' || apop.latest_state === 'COMPETITIVE_CONTROL'
  const segments = APOP_AXES.map((axis) => ({
    ...axis,
    score: Math.max(0, Math.min(1, Number(evidence[axis.key] ?? 0))),
  }))
  return (
    <div style={{
      position: 'absolute', bottom: 20, left: '50%', transform: 'translateX(-50%)',
      zIndex: 4, width: 'min(520px, calc(100vw - 600px))', minWidth: 300, pointerEvents: 'none',
    }}>
      <Glass accent={stateColor} intensity={0.7} style={{ padding: '12px 16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 9 }}>
          <span style={{ fontFamily: FONTS.mono, fontSize: 11, letterSpacing: '0.14em', textTransform: 'uppercase', color: GAMER.t3 }}>
            EVIDENCE PRISM · APOP
          </span>
          <span style={{
            fontFamily: FONTS.mono, fontSize: 13, color: stateColor, letterSpacing: '0.04em', fontWeight: 600,
            textShadow: isCompetitive ? `0 0 6px ${stateColor}66` : 'none',
          }}>
            {(apop.latest_score ?? 0).toFixed(3)} · h{(evidence.history_score ?? 0).toFixed(2)}
          </span>
        </div>
        <div style={{ display: 'flex', gap: 3, height: 16, alignItems: 'stretch' }}>
          {segments.map((seg) => (
            <div key={seg.key} style={{
              flex: seg.weight, background: '#0a1620', borderRadius: 2,
              border: `1px solid ${stateColor}26`, position: 'relative', overflow: 'hidden',
            }}>
              <div style={{
                position: 'absolute', left: 0, top: 0, bottom: 0, width: `${seg.score * 100}%`,
                background: `linear-gradient(90deg, ${stateColor}55 0%, ${stateColor}cc 100%)`,
                boxShadow: seg.score > 0.5 ? `inset 0 0 4px ${stateColor}88` : 'none',
                transition: 'width 0.6s ease, background 0.4s ease',
              }} />
            </div>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 3, marginTop: 6 }}>
          {segments.map((seg) => (
            <div key={seg.key} style={{
              flex: seg.weight, fontFamily: FONTS.mono, fontSize: 11, letterSpacing: '0.06em',
              color: seg.score > 0.4 ? GAMER.t1 : GAMER.t3, textAlign: 'center', transition: 'color 0.4s ease',
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
// Right-edge PCC drawer (PRESERVED — contention episode history)
// ---------------------------------------------------------------------------

function pccIsConcerning(captureHealth) {
  if (!captureHealth) return false
  if (captureHealth.capture_state && captureHealth.capture_state !== 'NOMINAL') return true
  if (captureHealth.host_state && !['EXCLUSIVE_USB', 'UNKNOWN'].includes(captureHealth.host_state)) return true
  if (captureHealth.session_counting_paused) return true
  return false
}

function DrawerStat({ label, value, color }) {
  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
      padding: '6px 0', borderBottom: `1px solid ${GAMER.bd2}`,
    }}>
      <span style={{ fontFamily: FONTS.mono, fontSize: 8, color: GAMER.t3, letterSpacing: '0.06em' }}>{label}</span>
      <span style={{ fontFamily: FONTS.mono, fontSize: 10, color, fontWeight: 500 }}>{value}</span>
    </div>
  )
}

function PCCDrawer({ captureHealth, pccIntelligence, manualOpen, onCloseManual }) {
  const concerning = pccIsConcerning(captureHealth)
  // Auto-open ONCE when a PCC alert begins, then the drawer is purely manual
  // so the × button (and the handle) can always dismiss it. Previously
  // open = concerning || manualOpen, which force-held the drawer open while
  // concerning and made × a no-op. The handle stays red while `concerning`
  // so the alert indicator persists even after the drawer is dismissed.
  const open = manualOpen
  const prevConcerning = useRef(false)
  useEffect(() => {
    if (concerning && !prevConcerning.current) onCloseManual(true)
    prevConcerning.current = concerning
  }, [concerning, onCloseManual])
  const state = captureHealth?.capture_state ?? '—'
  const host = captureHealth?.host_state ?? '—'
  const rate = captureHealth?.poll_rate_hz ?? 0
  const sustained = captureHealth?.sustained_duration_s ?? 0
  const ready = captureHealth?.grind_ready ?? false
  const paused = captureHealth?.session_counting_paused ?? false
  const episodes = pccIntelligence?.total_episodes ?? 0
  const meanRecov = pccIntelligence?.mean_recovery_s
  const longestEp = pccIntelligence?.longest_episode_s
  const hidRestarts = pccIntelligence?.hid_counter_restarts ?? 0
  const hasHistory = pccIntelligence != null

  return (
    <>
      <div
        onClick={() => onCloseManual(!manualOpen)}
        style={{
          position: 'absolute', top: '50%', right: open ? 320 : 0, transform: 'translateY(-50%)',
          width: 28, height: 96,
          background: concerning ? GAMER.red + 'cc' : GAMER.cyan + '26',
          border: `1px solid ${concerning ? GAMER.red : GAMER.cyan}66`, borderRight: 'none',
          borderRadius: '6px 0 0 6px', cursor: 'pointer', zIndex: 11,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          transition: 'right 0.32s ease, background 0.4s ease',
          boxShadow: concerning ? `0 0 16px ${GAMER.red}88` : 'none',
        }}
        title={concerning ? 'PCC alert — click to inspect' : 'PCC details'}
      >
        <span style={{
          fontFamily: FONTS.mono, fontSize: 8, color: concerning ? '#fff' : GAMER.cyan,
          letterSpacing: '0.16em', writingMode: 'vertical-rl', transform: 'rotate(180deg)',
        }}>
          {concerning ? '⚠ PCC' : 'PCC ▶'}
        </span>
      </div>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ x: 320 }} animate={{ x: 0 }} exit={{ x: 320 }}
            transition={{ duration: 0.32, ease: 'easeInOut' }}
            style={{ position: 'absolute', top: 0, right: 0, bottom: 0, width: 320, zIndex: 12 }}
          >
            <Glass accent={concerning ? GAMER.red : GAMER.cyan} style={{
              height: '100%', borderRadius: 0,
              borderLeft: `1px solid ${concerning ? GAMER.red : GAMER.cyan}33`,
              padding: '16px 16px', overflow: 'auto',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                <span style={{ fontFamily: FONTS.mono, fontSize: 9, letterSpacing: '0.16em', color: concerning ? GAMER.red : GAMER.cyan, fontWeight: 600 }}>
                  PHYSICAL CAPTURE CONTINUITY
                </span>
                <button onClick={() => onCloseManual(false)} style={{ background: 'transparent', border: 'none', color: GAMER.t2, cursor: 'pointer', fontFamily: FONTS.mono, fontSize: 14 }}>×</button>
              </div>

              {concerning && (
                <div style={{
                  background: GAMER.red + '14', border: `1px solid ${GAMER.red}44`, borderRadius: 4,
                  padding: '10px 12px', marginBottom: 16, fontFamily: FONTS.mono, fontSize: 9, color: GAMER.red, lineHeight: 1.5,
                }}>
                  ⚠ {paused
                    ? 'Session counting paused. Sessions will not advance toward GIC_N until protocol returns to NOMINAL + EXCLUSIVE_USB.'
                    : 'Protocol fail-closed. Verify USB cable, check Bluetooth pairing state, ensure controller is not in PS5 menu.'}
                </div>
              )}

              <DrawerStat label="capture_state" value={state} color={tone(STATE_TONE, state)} />
              <DrawerStat label="host_state" value={host} color={tone(HOST_TONE, host)} />
              <DrawerStat label="poll_rate_hz" value={rate.toFixed(1) + ' Hz'} color={GAMER.t1} />
              <DrawerStat label="sustained_duration_s" value={sustained.toFixed(1) + 's'} color={GAMER.t1} />
              <DrawerStat label="grind_ready" value={ready ? 'true' : 'false'} color={ready ? GAMER.green : GAMER.orange} />
              <DrawerStat label="session_counting_paused" value={paused ? 'true' : 'false'} color={paused ? GAMER.orange : GAMER.t2} />

              {hasHistory && (
                <>
                  <div style={{ marginTop: 20, paddingTop: 14, borderTop: `1px solid ${GAMER.bd}`, marginBottom: 10, fontFamily: FONTS.mono, fontSize: 8, color: GAMER.t2, letterSpacing: '0.12em' }}>
                    CONTENTION HISTORY
                  </div>
                  <DrawerStat label="episodes this session" value={episodes} color={episodes === 0 ? GAMER.green : episodes < 3 ? GAMER.orange : GAMER.red} />
                  {meanRecov != null && <DrawerStat label="mean recovery" value={meanRecov.toFixed(1) + 's'} color={GAMER.t1} />}
                  {longestEp != null && <DrawerStat label="longest episode" value={longestEp.toFixed(1) + 's'} color={GAMER.t1} />}
                  <DrawerStat label="hid counter restarts" value={hidRestarts} color={hidRestarts === 0 ? GAMER.green : GAMER.orange} />
                  {episodes === 0 && hidRestarts === 0 && (
                    <div style={{ marginTop: 8, fontFamily: FONTS.mono, fontSize: 7.5, color: GAMER.green }}>
                      No contention episodes — USB environment is clean
                    </div>
                  )}
                </>
              )}

              <div style={{ marginTop: 20, paddingTop: 14, borderTop: `1px solid ${GAMER.bd}`, fontFamily: FONTS.mono, fontSize: 8, color: GAMER.t3, lineHeight: 1.6 }}>
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

// ---------------------------------------------------------------------------
// Main view
// ---------------------------------------------------------------------------

export function GamerView() {
  const magnitude = useHeartbeatStore((s) => s.magnitude)

  const { data: captureHealth }   = useCaptureHealth()
  const { data: grindChain }      = useGrindChain()
  const { data: grindAnalytics }  = useGrindAnalytics()
  const { data: pccIntelligence } = usePCCIntelligence()
  const { data: apop }            = useActivePlayOccupancy()
  // Real per-category consent: device_id is the gamer's wallet (lower-cased,
  // no 0x), matching ConsentPanel.jsx + the bridge consent_ledger row key.
  const { address }               = useAccount()
  const consentDeviceId           = address ? address.toLowerCase().replace(/^0x/, '') : ''
  const { data: consentStatus }   = useConsentStatus(consentDeviceId)

  // chain_length = cumulative GIC stamps (fills the ribbon; matches check_grind.py)
  // consecutive_clean = leading streak; diverges when a session breaks the streak.
  const consecutiveClean = captureHealth?.consecutive_clean_toward_target ?? null
  const chainLen = grindChain?.chain_length ?? 0
  const target   = captureHealth?.grind_target ?? grindChain?.grind_target ?? 100
  const intact   = grindChain?.chain_intact
  const paused   = captureHealth?.session_counting_paused ?? false

  const latestHash = grindChain?.latest_gic_hash || ''
  const hashSettledAt = useHashChangedAt(latestHash)
  const changedAgo = useRelativeTime(hashSettledAt)

  const topBlocker = useMemo(() => {
    const counts = grindAnalytics?.blocking_reason_counts
    if (!counts || Object.keys(counts).length === 0) return null
    const [reason, n] = Object.entries(counts).sort((a, b) => b[1] - a[1])[0]
    const label = reason.replace('PCC_NOT_NOMINAL:', '').replace(/_/g, ' ')
    return `${label} ×${n}`
  }, [grindAnalytics])

  const [drawerManual, setDrawerManual] = useState(false)
  const [consentOpen, setConsentOpen] = useState(false)

  // Real offline signal: the grind-critical hooks are noMock, so when the
  // bridge is unreachable they hold no data (undefined) rather than fabricating.
  // This reflects actual bridge reachability — not a mock flag — and drives the
  // panels' honest "—" / STALE states.
  const bridgeOffline = !captureHealth && !grindChain

  // GIC chain display mode — orb-web constellation (default) vs classic ribbon,
  // gamer-selectable via Tweaks. Constellation frees the bottom strip, so the
  // bottom corner panels drop to the corner; ribbon mode keeps them raised.
  const { gicView } = useQtTweaks()
  const ribbonMode = gicView === 'ribbon'

  // v2 · item A — name this view + its live readouts in the persistent eyebrow.
  useViewEyebrow({
    num: '01',
    name: 'GAMER · LIVE',
    status: bridgeOffline ? 'BRIDGE UNREACHABLE' : paused ? 'COUNTING PAUSED' : 'LIVE',
    statusTone: bridgeOffline ? 'blocked' : paused ? 'pending' : 'live',
    readouts: [
      { label: 'CHAIN', value: `${chainLen}/${target}`, tone: 'chain' },
      { label: 'HOST', value: captureHealth?.host_state || '—', tone: bridgeOffline ? 'blocked' : 'amber' },
      { label: 'POLL', value: bridgeOffline ? '—' : `${captureHealth?.poll_rate_hz ?? 0}HZ`, tone: 'amber' },
    ],
  })

  return (
    <div className="qt-design-root" style={{ overflow: 'hidden' }}>
      {/* z0 — forensic-instrument graticule (shows through the transparent twin) */}
      <div className="twin-stage" style={{ position: 'absolute', inset: 0, zIndex: 0, border: 'none', borderRadius: 0 }} />

      {/* z1 — REAL 3D controller twin (full-bleed hero) */}
      <iframe
        src="/controller-twin.html?minimal=1"
        title="QorTroller 3D Controller Twin"
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', border: 'none', background: 'transparent', zIndex: 1 }}
      />

      {/* z2 — edge vignette; center stays sharp on the controller. The vignette
          respires at the Tweaks "twin breath" rate (--qt-breath) — the "alive"
          signal: a real human is on the controller. */}
      <div className="qt-twin-breath" style={{
        position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 2,
        background: 'radial-gradient(ellipse at center, transparent 52%, rgba(2,4,8,0.55) 100%)',
      }} />

      {/* z2 — GIC chain as an orb-web constellation around the controller
          (default). The lit-orb count is the REAL chain_length; the chain line
          wraps the controller as it grows. Toggle to the ribbon via Tweaks. */}
      {!ribbonMode && (
        <GicChainConstellation
          chainLen={chainLen} target={target}
          paused={paused} bridgeDown={bridgeOffline}
        />
      )}

      {/* z3+ — the design's four floating forensic-instrument corner panels.
          (FleetPanel + the top-center ChipStrip were removed — they overcrowded
          the clean 4-corner composition; fleet coherence lives in OperatorView.) */}
      <CaptureHealthPanel capture={captureHealth} paused={paused} bridgeDown={bridgeOffline} />
      <LatestGicPanel grind={grindChain} bridgeDown={bridgeOffline} magnitude={magnitude} />
      <ConsentPanelOverlay consentStatus={consentStatus} connected={Boolean(address)} onOpen={() => setConsentOpen(true)} ribbonMode={ribbonMode} />
      <AnalyticsPanel analytics={grindAnalytics} topBlocker={topBlocker} ribbonMode={ribbonMode} />

      <ApopEvidencePrism apop={apop} />

      {ribbonMode && (
        <GrindRibbon
          chainLen={chainLen} target={target} intact={intact}
          paused={paused} bridgeDown={bridgeOffline}
          consecutiveClean={consecutiveClean} changedAgo={changedAgo}
        />
      )}

      <PCCDrawer
        captureHealth={captureHealth}
        pccIntelligence={pccIntelligence}
        manualOpen={drawerManual}
        onCloseManual={setDrawerManual}
      />

      <ConsentPanel manualOpen={consentOpen} onCloseManual={setConsentOpen} />

      {/* GIC milestone flash — fires only on a real chain-length 10x crossing */}
      <LevelUpBadge chainLen={chainLen} />
    </div>
  )
}
