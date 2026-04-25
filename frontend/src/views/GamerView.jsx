// VAPI Gamer Dashboard — Phase 235-GAMER-REDESIGN
//
// Design intent (per operator request, 2026-04-24):
//   - The 3D controller twin is the entire canvas. No split screen.
//   - Glass-morphism HUD overlays float ABOVE the twin, never compete with it.
//   - Critical-during-grind data is dominant: chain_length, chain_intact,
//     host_state, latest_gameplay_context.
//   - PCC details collapse off-screen when state is healthy; auto-reveal
//     drawer slides in only when the protocol fails closed
//     (capture_state != NOMINAL OR host_state ∉ {EXCLUSIVE_USB, UNKNOWN}
//     OR session_counting_paused == true).
//   - Removed: VHP red diamond, TouchpadHeatmap, TremorGlowRing, separation
//     ratio row, merkle root row, eligibility gate row, heartbeat waveform
//     (heartbeat moved into the diagnostic drawer).

import { useEffect, useMemo, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useHeartbeatStore } from '../heartbeat/useHeartbeat'
import {
  useCaptureHealth, useGrindChain, useTournamentPreflight,
  useFleetCoherenceStatus, useAutoTriggerStatus,
} from '../api/bridgeApi'
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

function tone(map, value, fallback = GAMER.t3) {
  if (value == null) return fallback
  return map[value] ?? fallback
}

// ---------------------------------------------------------------------------
// Glass card — translucent, blurred, used for every overlay
// ---------------------------------------------------------------------------

function Glass({ children, style, accent = GAMER.cyan, intensity = 1 }) {
  return (
    <div style={{
      background:      `linear-gradient(180deg, rgba(8,18,24,${0.55 * intensity}) 0%, rgba(5,10,15,${0.72 * intensity}) 100%)`,
      backdropFilter:  'blur(14px) saturate(140%)',
      WebkitBackdropFilter: 'blur(14px) saturate(140%)',
      border:          `1px solid ${accent}26`,
      borderRadius:    8,
      boxShadow:       `0 0 24px ${accent}1a, inset 0 1px 0 rgba(255,255,255,0.04)`,
      ...style,
    }}>
      {children}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Top-left: session badge — small, never blocks anything
// ---------------------------------------------------------------------------

function SessionBadge({ sessionId, magnitude }) {
  return (
    <Glass style={{
      position:  'absolute',
      top:       16,
      left:      16,
      padding:   '6px 12px',
      zIndex:    10,
    }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <span style={{
          fontFamily:    FONTS.mono,
          fontSize:      7,
          letterSpacing: '0.18em',
          color:         GAMER.t3,
        }}>
          GRIND SESSION
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{
            display:        'inline-block',
            width:          5,
            height:         5,
            borderRadius:   '50%',
            background:     GAMER.cyan,
            boxShadow:      `0 0 ${4 + magnitude * 8}px ${GAMER.cyan}`,
            transition:     'box-shadow 0.4s ease',
          }} />
          <span style={{
            fontFamily:    FONTS.mono,
            fontSize:      11,
            color:         GAMER.t1,
            letterSpacing: '0.04em',
          }}>
            {sessionId}
          </span>
        </div>
      </div>
    </Glass>
  )
}

// ---------------------------------------------------------------------------
// Top-right: live status — chain integrity badge + agent count
// ---------------------------------------------------------------------------

function LiveStatusBadge({ intact, onChain, agentCount, merkleRoot }) {
  return (
    <Glass style={{
      position:  'absolute',
      top:       16,
      right:     16,
      padding:   '6px 12px',
      zIndex:    10,
    }} accent={intact ? GAMER.green : GAMER.red}>
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
// Top-center: GRIND PROGRESS — compact horizontal bar at the top edge.
//
// Design note: the previous version put a ~520×170px box in the bottom
// center and physically covered the lower half of the controller twin.
// The redesign moves it to the top edge as a slim full-width strip; the
// big chain number lives there in 36px display font (still dominant, but
// only ~64px tall total).  The entire vertical center of the screen is
// now empty for the 3D twin.
// ---------------------------------------------------------------------------

function GrindProgressBar({ chainLen, target, intact, magnitude, paused }) {
  const pct = Math.min(1, chainLen / Math.max(1, target))
  const completed = chainLen >= target
  const barColor = completed
    ? GAMER.green
    : paused
      ? GAMER.orange
      : GAMER.cyan

  const glow = 4 + magnitude * 12

  return (
    <div style={{
      position:  'absolute',
      top:       60,
      left:      '50%',
      transform: 'translateX(-50%)',
      width:     440,
      maxWidth:  'calc(100vw - 360px)', // leave room for top-left & top-right badges
      zIndex:    9,
    }}>
      <Glass accent={barColor} intensity={1.0} style={{ padding: '8px 14px' }}>
        <div style={{
          display:        'flex',
          alignItems:     'center',
          justifyContent: 'space-between',
          gap:            16,
          marginBottom:   6,
        }}>
          <span style={{
            fontFamily:    FONTS.mono,
            fontSize:      7,
            color:         GAMER.t3,
            letterSpacing: '0.18em',
            whiteSpace:    'nowrap',
          }}>
            GRIND INTEGRITY CHAIN
          </span>
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
              {chainLen}
            </span>
            <span style={{
              fontFamily: FONTS.display,
              fontSize:   16,
              fontWeight: 500,
              color:      GAMER.t2,
            }}>
              / {target}
            </span>
          </div>
        </div>

        {/* Progress bar (slim) */}
        <div style={{
          height:       4,
          background:   'rgba(255,255,255,0.05)',
          borderRadius: 2,
          overflow:     'hidden',
        }}>
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

        {paused && (
          <div style={{
            marginTop:     5,
            fontFamily:    FONTS.mono,
            fontSize:      7.5,
            color:         GAMER.orange,
            textAlign:     'center',
            letterSpacing: '0.08em',
          }}>
            ⚠ PAUSED — needs NOMINAL + EXCLUSIVE_USB
          </div>
        )}
      </Glass>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Bottom edge: 4 status chips — host_state / pcc / gameplay / ready
// ---------------------------------------------------------------------------

function StatusChip({ label, value, color }) {
  return (
    <Glass accent={color} style={{ padding: '6px 12px', minWidth: 100 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
        <span style={{
          fontFamily:    FONTS.mono,
          fontSize:      6.5,
          letterSpacing: '0.16em',
          color:         GAMER.t3,
        }}>
          {label}
        </span>
        <span style={{
          fontFamily:    FONTS.mono,
          fontSize:      10,
          fontWeight:    600,
          color:         color,
          letterSpacing: '0.04em',
          whiteSpace:    'nowrap',
        }}>
          {value}
        </span>
      </div>
    </Glass>
  )
}

function StatusBar({ host, state, gctx, ready, coherence, autoTrigger }) {
  // Phase 235-DASH-UPGRADE: GAMEPLAY chip — `WAITING` instead of ambiguous
  // `NULL`.  Pre-first-stamp shows muted t2; once a ruling lands, color
  // flips to green (ACTIVE_GAMEPLAY) or red (MENU_DETECTED) per GCTX_TONE.
  const gctxValue = gctx ?? 'WAITING'
  const gctxColor = gctx ? tone(GCTX_TONE, gctx) : GAMER.t2
  const gctxTitle = gctx
    ? undefined
    : 'No rulings validated yet — chip populates after the first GIC stamp lands'

  // Phase 235-DASH-UPGRADE: COHERENCE chip surfaces FleetSignalCoherenceAgent
  // contradiction / orphan / inversion state.  Critical signals here include
  // the new AUTO_TRIGGER_RATE_LIMIT_VIOLATION rule (>12 events/hour from the
  // SessionBoundaryDetectorAgent → CRITICAL halt-state).
  const cohC = coherence?.active_contradictions ?? coherence?.critical_count ?? 0
  const cohH = coherence?.active_orphans ?? coherence?.high_count ?? 0
  const cohI = coherence?.active_inversions ?? 0
  const cohValue = (cohC === 0 && cohH === 0 && cohI === 0)
    ? 'CLEAN'
    : `${cohC}C·${cohH}H·${cohI}I`
  const cohColor =
    cohC > 0 ? GAMER.red
    : cohH > 0 ? GAMER.orange
    : GAMER.green

  // Phase 235-DASH-UPGRADE: AUTO-TRIGGER chip surfaces SessionBoundary
  // DetectorAgent live state.  Resolves the 5–15 min "static dashboard"
  // window between gameplay-end and chain_length advance — operator can
  // see ARMED / NEXT ~Ns / queued count without waiting for a stamp.
  let atValue, atColor
  if (!autoTrigger || autoTrigger.agent_alive === false) {
    atValue = 'OFF';   atColor = GAMER.t3
  } else if (autoTrigger.stopped) {
    atValue = 'DONE';  atColor = GAMER.green
  } else if (autoTrigger.next_eligible_in_s > 0) {
    atValue = `NEXT ~${Math.round(autoTrigger.next_eligible_in_s)}s`
    atColor = GAMER.cyan
  } else {
    atValue = 'ARMED'; atColor = GAMER.green
  }
  const atTitle = autoTrigger
    ? `fires_this_run=${autoTrigger.fires_this_run} · `
      + `min_interval=${autoTrigger.min_interval_s}s · `
      + `quiescence_window=${autoTrigger.quiescence_window} records`
    : undefined

  return (
    <div style={{
      position:  'absolute',
      bottom:    16,
      left:      '50%',
      transform: 'translateX(-50%)',
      display:   'flex',
      gap:       8,
      zIndex:    9,
      flexWrap:  'wrap',
      maxWidth:  'calc(100vw - 64px)',
      justifyContent: 'center',
    }}>
      <StatusChip label="HOST"         value={host  ?? '—'}    color={tone(HOST_TONE,  host)} />
      <StatusChip label="PCC"          value={state ?? '—'}    color={tone(STATE_TONE, state)} />
      <span title={gctxTitle}>
        <StatusChip label="GAMEPLAY"   value={gctxValue}       color={gctxColor} />
      </span>
      <StatusChip label="READY"        value={ready ? 'YES' : 'NO'}
                                       color={ready ? GAMER.green : GAMER.orange} />
      <StatusChip label="COHERENCE"    value={cohValue}        color={cohColor} />
      <span title={atTitle}>
        <StatusChip label="AUTO-TRIGGER" value={atValue}       color={atColor} />
      </span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// PCC drawer — auto-reveals on protocol stress, slides from right
// ---------------------------------------------------------------------------

function pccIsConcerning(captureHealth) {
  if (!captureHealth) return false
  const state = captureHealth.capture_state
  const host  = captureHealth.host_state
  if (state && state !== 'NOMINAL') return true
  if (host && !['EXCLUSIVE_USB', 'UNKNOWN'].includes(host)) return true
  if (captureHealth.session_counting_paused) return true
  return false
}

function PCCDrawer({ captureHealth, manualOpen, onCloseManual }) {
  const concerning = pccIsConcerning(captureHealth)
  const open = concerning || manualOpen

  const state = captureHealth?.capture_state ?? '—'
  const host  = captureHealth?.host_state ?? '—'
  const rate  = captureHealth?.poll_rate_hz ?? 0
  const sustained = captureHealth?.sustained_duration_s ?? 0
  const ready = captureHealth?.grind_ready ?? false
  const paused = captureHealth?.session_counting_paused ?? false

  return (
    <>
      {/* Collapsed handle on the right edge — always visible, click to manual-open */}
      <div
        onClick={() => onCloseManual(false === manualOpen ? true : !manualOpen)}
        style={{
          position:    'absolute',
          top:         '50%',
          right:       open ? 320 : 0,
          transform:   'translateY(-50%)',
          width:       28,
          height:      96,
          background:  concerning ? GAMER.red + 'cc' : GAMER.cyan + '26',
          border:      `1px solid ${concerning ? GAMER.red : GAMER.cyan}66`,
          borderRight: 'none',
          borderRadius: '6px 0 0 6px',
          cursor:      'pointer',
          zIndex:      11,
          display:     'flex',
          alignItems:  'center',
          justifyContent: 'center',
          transition:  'right 0.32s ease, background 0.4s ease',
          boxShadow:   concerning ? `0 0 16px ${GAMER.red}88` : 'none',
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

      {/* The drawer itself */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ x: 320 }}
            animate={{ x: 0 }}
            exit={{ x: 320 }}
            transition={{ duration: 0.32, ease: 'easeInOut' }}
            style={{
              position: 'absolute',
              top:      0,
              right:    0,
              bottom:   0,
              width:    320,
              zIndex:   10,
            }}
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
              <div style={{
                display:        'flex',
                alignItems:     'center',
                justifyContent: 'space-between',
                marginBottom:   16,
              }}>
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
                  style={{
                    background:  'transparent',
                    border:      'none',
                    color:       GAMER.t2,
                    cursor:      'pointer',
                    fontFamily:  FONTS.mono,
                    fontSize:    14,
                  }}
                >
                  ×
                </button>
              </div>

              {concerning && (
                <div style={{
                  background:    GAMER.red + '14',
                  border:        `1px solid ${GAMER.red}44`,
                  borderRadius:  4,
                  padding:       '10px 12px',
                  marginBottom:  16,
                  fontFamily:    FONTS.mono,
                  fontSize:      9,
                  color:         GAMER.red,
                  lineHeight:    1.5,
                }}>
                  ⚠ {paused
                      ? 'Session counting paused. Sessions will not advance toward GIC_N until protocol returns to NOMINAL + EXCLUSIVE_USB.'
                      : 'Protocol fail-closed. Verify USB cable, check Bluetooth pairing state, ensure controller is not in PS5 menu.'}
                </div>
              )}

              <DrawerStat label="capture_state"        value={state} color={tone(STATE_TONE, state)} />
              <DrawerStat label="host_state"           value={host}  color={tone(HOST_TONE,  host)} />
              <DrawerStat label="poll_rate_hz"         value={rate.toFixed(1) + ' Hz'} color={GAMER.t1} />
              <DrawerStat label="sustained_duration_s" value={sustained.toFixed(1) + 's'} color={GAMER.t1} />
              <DrawerStat label="grind_ready"          value={ready ? 'true' : 'false'} color={ready ? GAMER.green : GAMER.orange} />
              <DrawerStat label="session_counting_paused" value={paused ? 'true' : 'false'} color={paused ? GAMER.orange : GAMER.t2} />

              <div style={{
                marginTop:     20,
                paddingTop:    14,
                borderTop:     `1px solid ${GAMER.bd}`,
                fontFamily:    FONTS.mono,
                fontSize:      8,
                color:         GAMER.t3,
                lineHeight:    1.6,
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
      <span style={{ fontFamily: FONTS.mono, fontSize: 10, color: color, fontWeight: 500 }}>
        {value}
      </span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main view
// ---------------------------------------------------------------------------

export function GamerView() {
  const magnitude     = useHeartbeatStore((s) => s.magnitude)
  const merkleRoot    = useHeartbeatStore((s) => s.merkleRoot)
  const onChain       = useHeartbeatStore((s) => s.onChainConfirmed)
  const agentCount    = useHeartbeatStore((s) => s.agentCount)

  const { data: captureHealth } = useCaptureHealth()
  const { data: grindChain }    = useGrindChain()
  const { data: preflight }     = useTournamentPreflight()
  // Phase 235-DASH-UPGRADE: surface FSCA contradiction count + auto-trigger
  // agent telemetry on the bottom status strip.
  const { data: coherence }     = useFleetCoherenceStatus()
  const { data: autoTrigger }   = useAutoTriggerStatus()

  const chainLen  = grindChain?.chain_length ?? 0
  const target    = captureHealth?.grind_target ?? grindChain?.grind_target ?? 100
  const intact    = grindChain?.chain_intact ?? true
  const sessionId = grindChain?.grind_session_id ?? '—'
  const host      = captureHealth?.host_state
  const state     = captureHealth?.capture_state
  const gctx      = captureHealth?.latest_gameplay_context
  const ready     = captureHealth?.grind_ready ?? false
  const paused    = captureHealth?.session_counting_paused ?? false

  // Manual override for the PCC drawer — null = follow auto-reveal logic,
  // true/false = operator opened/closed it explicitly.
  const [drawerManual, setDrawerManual] = useState(false)

  return (
    <div style={{
      position: 'relative',
      width:    '100%',
      height:   '100%',
      background: GAMER.bg,
      overflow: 'hidden',
    }}>
      {/* The 3D controller twin — full-bleed, MINIMAL mode (no header, no
          side panels, no footer; just the Three.js Canvas) so the entire
          viewport belongs to the floating pulsing controller. */}
      <iframe
        src="/controller-twin.html?minimal=1"
        style={{
          position: 'absolute',
          inset:    0,
          width:    '100%',
          height:   '100%',
          border:   'none',
          background: 'transparent',
          zIndex:   1,
        }}
        title="VAPI 3D Controller Twin"
      />

      {/* Subtle edge vignette so HUD overlays read against bright twin
          renders.  Center is fully transparent — controller stays sharp. */}
      <div style={{
        position:      'absolute',
        inset:         0,
        pointerEvents: 'none',
        background:    'radial-gradient(ellipse at center, transparent 55%, rgba(2,4,8,0.45) 100%)',
        zIndex:        2,
      }} />

      {/* HUD overlays — all confined to screen edges (top strip + bottom
          strip + right edge drawer).  Vertical center is reserved for the
          controller twin. */}
      <SessionBadge sessionId={sessionId} magnitude={magnitude} />
      <LiveStatusBadge
        intact={intact}
        onChain={onChain}
        agentCount={agentCount}
        merkleRoot={merkleRoot}
      />
      <GrindProgressBar
        chainLen={chainLen}
        target={target}
        intact={intact}
        magnitude={magnitude}
        paused={paused}
      />
      <StatusBar
        host={host}
        state={state}
        gctx={gctx}
        ready={ready}
        coherence={coherence}
        autoTrigger={autoTrigger}
      />
      <PCCDrawer
        captureHealth={captureHealth}
        manualOpen={drawerManual}
        onCloseManual={setDrawerManual}
      />
    </div>
  )
}
