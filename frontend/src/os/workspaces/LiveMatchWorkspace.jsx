/**
 * Evidence OS Stage 2 — Live Match workspace
 *
 * The operator's active-session decision surface. Single dominant
 * verdict ("Can this session count?") on top, live signal grid
 * underneath, only blockers that affect the verdict listed inline.
 *
 * 7 composed hooks (existing, no new endpoints):
 *   useCaptureHealth         — PCC capture_state + host_state
 *   useGrindChain            — GIC chain_length + chain_intact
 *   useActivePlayOccupancy   — APOP state
 *   useBrpRecordPulse        — WebSocket pulse + connected flag
 *   useBrpControllerOrientation — IMU/accel (optional; surfaced as
 *                              detail meter, NOT a verdict input)
 *   useAutoTriggerStatus     — next adjudication cadence
 *   useAITSeparation         — biometric separation ratio context
 *
 * Verdict logic (FROZEN at Stage 2; review for Stage 3):
 *   counting  ← ALL of:
 *      capture_state === 'NOMINAL'
 *      host_state ∈ {'EXCLUSIVE_USB', 'UNKNOWN'}
 *      apop.state ∈ {'ACTIVE_MATCH_PLAY', 'COMPETITIVE_CONTROL'}
 *      grindChain.chain_intact === true
 *      recordPulse.lastPulseTs > now - 8s  (controller live recently)
 *      NOT isMockActive
 *
 *   mock      ← isMockActive
 *   dormant   ← no recent record pulse + no controller signal
 *   blocked   ← otherwise (one or more gates failing)
 *
 * Mock visibly separated per operator brief: when mock=true the
 * verdict word reads "MOCK SESSION · not live" and live signal
 * meters render with status='mock' (red dot, not green).
 */
import { useEffect, useState, useMemo } from 'react'
import {
  useCaptureHealth,
  useGrindChain,
  useActivePlayOccupancy,
  useBrpRecordPulse,
  useBrpControllerOrientation,
  useAutoTriggerStatus,
  useAITSeparation,
} from '../../api/bridgeApi'
import { isMockActive } from '../../api/mockBridge'
import WorkspaceHeader from '../components/WorkspaceHeader'
import VerdictPanel    from '../components/VerdictPanel'
import LiveSignalPane  from '../components/LiveSignalPane'
import BlockerList     from '../components/BlockerList'
import SignalMeter     from '../components/SignalMeter'

const _PULSE_FRESH_MS = 8000   // controller live if pulse within 8s
const _USB_HZ_NOMINAL = 1000   // PCC nominal poll rate target

function _humanApop(state) {
  switch (state) {
    case 'ACTIVE_MATCH_PLAY':    return 'Actively playing'
    case 'COMPETITIVE_CONTROL':  return 'Competitive control'
    case 'MATCH_TRANSITION':     return 'Between plays'
    case 'NON_COMPETITIVE_MENU': return 'On menu / paused'
    case 'UNKNOWN_LOW_EVIDENCE': return 'Insufficient evidence'
    default:                      return 'Awaiting first sample'
  }
}

function _humanHost(state) {
  switch (state) {
    case 'EXCLUSIVE_USB':  return 'USB exclusive'
    case 'EXCLUSIVE_BT':   return 'Bluetooth exclusive'
    case 'CONTESTED':      return 'Contested (USB + BT)'
    case 'DEGRADED':       return 'Degraded'
    case 'DISCONNECTED':   return 'Disconnected'
    case 'UNKNOWN':        return 'Unknown (assumed USB)'
    default:                return 'Unknown'
  }
}

function _humanCapture(state) {
  switch (state) {
    case 'NOMINAL':        return 'Nominal'
    case 'DEGRADED':       return 'Degraded'
    case 'DISCONNECTED':   return 'Disconnected'
    default:                return state || 'Unknown'
  }
}

/* ------------------------------------------------------------------ */
/*  Verdict + blocker derivation                                       */
/* ------------------------------------------------------------------ */

function deriveLiveState({ capture, grind, apop, pulse, mock, nowMs }) {
  if (mock) {
    return {
      verdict: 'mock',
      headline: 'Bridge is unreachable — this UI is showing fabricated data',
      subline:  'Anything below is mock-generated, not live grind state. Clear the mock flag by hard-refreshing once the bridge is back online.',
      blockers: [],
    }
  }

  const captureState = capture?.capture_state
  const hostState    = capture?.host_state
  const apopState    = apop?.classification?.state || apop?.state || null
  const chainIntact  = grind?.chain_intact !== false
  const pulseFresh   = pulse?.lastPulseTs && (nowMs - pulse.lastPulseTs) <= _PULSE_FRESH_MS

  // No live controller AND no recent grind chain advance → dormant
  if (!pulseFresh && (!grind || (grind?.chain_length ?? 0) === 0)) {
    return {
      verdict: 'dormant',
      headline: 'No active controller — plug in the DualShock Edge to begin',
      subline:  'Capture monitor is waiting for HID frames. Once the controller streams, the verdict will flip in under 8 seconds.',
      blockers: [],
    }
  }

  // Build blockers list — only ones currently active
  const blockers = []

  if (!pulseFresh) {
    blockers.push({
      key: 'controller',
      severity: 'blocked',
      severityLabel: 'CONTROLLER',
      message: 'Controller signal is stale — no HID frames received recently',
      protocolTerm: 'useBrpRecordPulse.lastPulseTs older than 8s',
      source: 'WebSocket /ws/records',
    })
  }

  if (captureState && captureState !== 'NOMINAL') {
    blockers.push({
      key: 'capture',
      severity: captureState === 'DISCONNECTED' ? 'blocked' : 'pending',
      severityLabel: 'CAPTURE',
      message: captureState === 'DISCONNECTED'
        ? 'Capture channel is disconnected — Windows lost the controller'
        : `Capture quality is ${_humanCapture(captureState).toLowerCase()}`,
      protocolTerm: `capture_state = ${captureState}`,
      source: '/bridge/capture-health',
    })
  }

  if (hostState && !['EXCLUSIVE_USB', 'UNKNOWN'].includes(hostState)) {
    blockers.push({
      key: 'host',
      severity: hostState === 'CONTESTED' ? 'blocked' : 'pending',
      severityLabel: 'HOST',
      message: hostState === 'CONTESTED'
        ? 'Host arbitration contested — USB and Bluetooth fighting for the controller'
        : `Host channel is ${_humanHost(hostState).toLowerCase()}`,
      protocolTerm: `host_state = ${hostState}`,
      source: '/bridge/capture-health',
    })
  }

  if (apopState && !['ACTIVE_MATCH_PLAY', 'COMPETITIVE_CONTROL'].includes(apopState)) {
    blockers.push({
      key: 'apop',
      severity: 'pending',
      severityLabel: 'GAMEPLAY',
      message: apopState === 'NON_COMPETITIVE_MENU'
        ? 'Player is on a menu — no competitive play detected'
        : apopState === 'UNKNOWN_LOW_EVIDENCE'
          ? 'Not enough trigger / button activity to classify play yet'
          : `Active play classification is "${_humanApop(apopState)}"`,
      protocolTerm: `APOP state = ${apopState}`,
      source: '/agent/active-play-occupancy',
    })
  }

  if (!chainIntact) {
    blockers.push({
      key: 'gic',
      severity: 'blocked',
      severityLabel: 'GIC',
      message: 'Grind chain integrity check failed — investigate before resuming',
      protocolTerm: 'chain_intact = false (INV-GIC-003 violation)',
      source: '/bridge/grind-chain-status',
    })
  }

  if (blockers.length === 0) {
    return {
      verdict: 'counting',
      headline: 'Session is counting — every PoAC record advances the chain',
      subline:  `Capture nominal · host ${_humanHost(hostState).toLowerCase()} · play "${_humanApop(apopState)}" · chain link ${grind?.chain_length ?? 0}`,
      blockers,
    }
  }

  // One or more blockers — render verdict explaining the dominant one
  const dominant = blockers[0]
  return {
    verdict: 'blocked',
    headline: dominant.message,
    subline:  blockers.length === 1
      ? `1 active blocker · ${dominant.protocolTerm}`
      : `${blockers.length} active blockers · resolve them in order to resume counting`,
    blockers,
  }
}

/* ------------------------------------------------------------------ */
/*  Workspace                                                          */
/* ------------------------------------------------------------------ */

export default function LiveMatchWorkspace() {
  // 7 composed hooks
  const captureHealth  = useCaptureHealth().data
  const grindChain     = useGrindChain().data
  const apop           = useActivePlayOccupancy().data
  const pulse          = useBrpRecordPulse()
  // Mythos audit C1 — hook returns {orientation, connected, framesReceived}
  // (NOT .data) and short-circuits to no-op when deviceId === ''.  Stage 2
  // ships without device-id discovery wiring, so the IMU meter is
  // intentionally dormant in v1 — the meter renders an honest
  // "device-id wiring deferred" label instead of falsely claiming
  // a stream that never connects.
  const orientationStream = useBrpControllerOrientation('')
  const autoTrigger    = useAutoTriggerStatus().data
  const aitSeparation  = useAITSeparation().data

  // Tick state so "8s freshness" check re-evaluates without poll
  const [nowMs, setNowMs] = useState(Date.now())
  useEffect(() => {
    const id = setInterval(() => setNowMs(Date.now()), 1000)
    return () => clearInterval(id)
  }, [])

  const live = useMemo(() => deriveLiveState({
    capture: captureHealth,
    grind:   grindChain,
    apop,
    pulse,
    mock:    isMockActive(),
    nowMs,
  }), [captureHealth, grindChain, apop, pulse, nowMs])

  // Signal meter status per metric
  const captureStatus =
    live.verdict === 'mock' ? 'mock' :
    captureHealth?.capture_state === 'NOMINAL' ? 'live' :
    captureHealth?.capture_state === 'DISCONNECTED' ? 'blocked' : 'pending'

  const apopStatus =
    live.verdict === 'mock' ? 'mock' :
    ['ACTIVE_MATCH_PLAY', 'COMPETITIVE_CONTROL'].includes(apop?.classification?.state || apop?.state) ? 'live' :
    (apop?.classification?.state || apop?.state) === 'NON_COMPETITIVE_MENU' ? 'pending' : 'dormant'

  const gicStatus =
    live.verdict === 'mock' ? 'mock' :
    grindChain?.chain_intact === false ? 'blocked' :
    (grindChain?.chain_length ?? 0) > 0 ? 'live' : 'dormant'

  const pulseStatus =
    live.verdict === 'mock' ? 'mock' :
    pulse?.connected && (nowMs - (pulse?.lastPulseTs || 0)) <= _PULSE_FRESH_MS ? 'live' :
    pulse?.connected ? 'pending' : 'blocked'

  const pollRateHz = captureHealth?.poll_rate_hz ?? null

  return (
    <>
      <WorkspaceHeader
        title="Live Match"
        description="Active-session decision surface. One question: can this session count? The verdict updates the moment any gate flips. Mock and offline state are visibly separate from live."
      />

      <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: 18 }}>
        {/* Dominant verdict */}
        <VerdictPanel
          verdict={live.verdict}
          headline={live.headline}
          subline={live.subline}
        />

        {/* Blocker list — renders nothing when verdict='counting' */}
        <BlockerList blockers={live.blockers} />

        {/* Live signal grid — controller / capture / play / chain */}
        <LiveSignalPane title="Live signals">
          <SignalMeter
            label="Controller pulse"
            value={pulse?.lastPulseTs
              ? `${Math.max(0, Math.floor((nowMs - pulse.lastPulseTs) / 1000))}s`
              : '—'}
            unit="ago"
            status={pulseStatus}
            ariaLabel="Controller HID pulse last-event age"
          />
          <SignalMeter
            label="Capture poll rate"
            value={pollRateHz}
            unit="Hz"
            status={captureStatus}
            max={_USB_HZ_NOMINAL}
            ariaLabel="HID capture poll rate"
          />
          <SignalMeter
            label="Active play"
            value={_humanApop(apop?.classification?.state || apop?.state)}
            status={apopStatus}
            ariaLabel="Active play occupancy classification"
          />
          <SignalMeter
            label="Chain length"
            value={grindChain?.chain_length ?? '—'}
            unit="links"
            status={gicStatus}
            ariaLabel="GIC chain link count"
          />
        </LiveSignalPane>

        {/* Context strip — secondary signals (not verdict inputs) */}
        <LiveSignalPane title="Context">
          <SignalMeter
            label="Next adjudication"
            value={autoTrigger?.seconds_until_next ?? '—'}
            unit="s"
            status={autoTrigger ? 'live' : 'dormant'}
            ariaLabel="Seconds until next auto-adjudication"
          />
          <SignalMeter
            label="Biometric separation"
            value={aitSeparation?.separation_ratio
              ? aitSeparation.separation_ratio.toFixed(3) : '—'}
            unit={`N=${aitSeparation?.n_sessions ?? 0}`}
            status={aitSeparation
              ? (aitSeparation.separation_ratio >= 1.0 ? 'verified' : 'pending')
              : 'dormant'}
            ariaLabel="AIT inter-player separation ratio"
          />
          <SignalMeter
            label="Controller IMU"
            value={orientationStream?.connected
              ? 'streaming'
              : 'device-id wiring deferred'}
            status={orientationStream?.connected ? 'live' : 'dormant'}
            ariaLabel="Controller orientation IMU stream"
          />
          <SignalMeter
            label="Host channel"
            value={_humanHost(captureHealth?.host_state)}
            status={
              ['EXCLUSIVE_USB', 'UNKNOWN'].includes(captureHealth?.host_state) ? 'live' :
              captureHealth?.host_state === 'CONTESTED' ? 'blocked' : 'pending'
            }
            ariaLabel="Host arbitration channel"
          />
        </LiveSignalPane>
      </div>
    </>
  )
}
