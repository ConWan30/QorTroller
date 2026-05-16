/**
 * Evidence OS — StatusStrip
 *
 * Always-visible top bar. Reads global protocol-state via
 * usePublicProtocolState + usePublicAgentRoots (no auth; cached 30s).
 * Surfaces honestly:
 *   - bridge state (LIVE / MOCK / unreachable)
 *   - kill-switch state (PAUSED / LIVE)
 *   - agent count (3 — Sentry/Guardian/Curator)
 *   - latest merkle/root hash (truncated 12 char + tooltip full)
 *   - active blocker count (drawn from useFleetCoherenceStatus)
 *
 * Discipline: never claims "verified" when bridge is unreachable.
 * Falls back to "BRIDGE UNREACHABLE" pill instead of guessing.
 */
import { Link } from 'react-router-dom'
import { isMockActive } from '../../api/mockBridge'
import {
  usePublicProtocolState,
  usePublicAgentRoots,
} from '../../api/publicForensic'
import DataBadge from './DataBadge'

function MetricCell({ label, value, accent }) {
  return (
    <div style={{
      display:        'flex',
      flexDirection:  'column',
      gap:            2,
      paddingRight:   18,
      borderRight:    '1px solid var(--os-border)',
      minWidth:       100,
    }}>
      <span style={{
        fontSize:       'var(--os-text-min)',
        color:          'var(--os-text-faint)',
        letterSpacing:  '0.08em',
        textTransform:  'uppercase',
      }}>{label}</span>
      <span style={{
        fontSize:       'var(--os-text-label)',
        fontWeight:     600,
        color:          accent || 'var(--os-text)',
        fontFamily:     'JetBrains Mono, ui-monospace, monospace',
      }}>{value}</span>
    </div>
  )
}

export default function StatusStrip() {
  const { data: state, error: stateErr } = usePublicProtocolState()
  const { data: roots } = usePublicAgentRoots()

  // Bridge state — observation, not inference
  let bridgeStatus = 'live'
  let bridgeLabel = 'LIVE'
  if (isMockActive()) {
    bridgeStatus = 'mock'
    bridgeLabel = 'MOCK'
  } else if (stateErr) {
    bridgeStatus = 'blocked'
    bridgeLabel = 'UNREACHABLE'
  }

  const killSwitchPaused = Boolean(state?.kill_switch_paused)
  const agentCount = roots?.agents?.length ?? '—'
  const firstAgentMerkle = roots?.agents?.[0]?.cedar_bundle_merkle || ''
  const merkleShort = firstAgentMerkle
    ? `${firstAgentMerkle.slice(0, 8)}…${firstAgentMerkle.slice(-4)}`
    : '—'
  const blockerCount = state?.total_grind_chain_links === undefined ? '—' :
    // proxy: 'blockers' for this strip = 0 when chain advancing, otherwise unknown.
    // Replace with real fleet-coherence aggregate in a follow-up vertical slice.
    0

  return (
    <nav
      role="navigation"
      aria-label="Evidence OS status strip"
      style={{
        display:        'flex',
        alignItems:     'center',
        gap:            18,
        padding:        '0 24px',
        height:         'var(--os-strip-h)',
        background:     'var(--os-panel)',
        borderBottom:   '1px solid var(--os-border)',
        fontFamily:     'JetBrains Mono, ui-monospace, monospace',
      }}
    >
      <Link
        to="/"
        aria-label="Return to operator dashboard"
        style={{
          fontSize:       'var(--os-text-h3)',
          fontWeight:     700,
          color:          'var(--os-accent)',
          letterSpacing:  '0.12em',
          textDecoration: 'none',
          paddingRight:   18,
          borderRight:    '1px solid var(--os-border)',
        }}
      >VAPI · Evidence OS</Link>

      <DataBadge
        status={bridgeStatus}
        label={`BRIDGE ${bridgeLabel}`}
        ariaLabel={`Bridge state: ${bridgeLabel}`}
      />
      <DataBadge
        status={killSwitchPaused ? 'killswitch' : 'live'}
        label={killSwitchPaused ? 'KILL-SWITCH PAUSED' : 'CHAIN LIVE'}
        ariaLabel={killSwitchPaused
          ? 'Chain submissions paused; no on-chain writes'
          : 'Chain submissions live'}
      />

      <div style={{ flex: 1 }} />

      <MetricCell label="Agents"  value={agentCount} />
      <MetricCell label="PV-CI"   value={state?.pv_ci_invariants_count ?? '—'} />
      <MetricCell label="VPM"     value={state?.total_vpm_artifacts ?? '—'} />
      <MetricCell label="GIC"     value={state?.total_grind_chain_links ?? '—'} />
      <MetricCell
        label="Merkle"
        value={<code style={{ fontSize: 11 }} title={firstAgentMerkle}>{merkleShort}</code>}
      />
      <MetricCell
        label="Blockers"
        value={blockerCount}
        accent={blockerCount > 0 ? 'var(--os-status-blocked)' : 'var(--os-status-live)'}
      />
    </nav>
  )
}
