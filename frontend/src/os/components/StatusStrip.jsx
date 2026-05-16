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
import { useFleetCoherenceStatus } from '../../api/bridgeApi'
import DataBadge from './DataBadge'

function MetricCell({ label, value, accent, isLast }) {
  return (
    <div style={{
      display:        'flex',
      flexDirection:  'column',
      gap:            2,
      // Stage 5.3 (iPhone 15 Finding B): last cell drops paddingRight
      // + borderRight so there's no dead space after Blockers at the
      // end of horizontal scroll on phone. The right padding +
      // separator border were designed for cell-to-cell separation;
      // the trailing cell has no neighbour to separate from.
      paddingRight:   isLast ? 0 : 18,
      borderRight:    isLast ? 'none' : '1px solid var(--os-border)',
      minWidth:       100,
      flexShrink:     0,
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
  // Mythos audit C2 — real fleet-coherence aggregate replaces hardcoded 0.
  // useFleetCoherenceStatus is operator-side (api_key); when unauthenticated
  // OR mock/offline, fall through to dormant "—" instead of fake green.
  const { data: coherence, isError: coherenceErr } = useFleetCoherenceStatus()

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
  // Real fleet-coherence aggregate. When coherence data unavailable (auth
  // missing / mock / offline), the strip honestly reads "—" + dormant
  // status — NOT green 0. This is the C2 honesty fix from Mythos audit.
  const coherenceAvailable = Boolean(coherence) && !coherenceErr && !isMockActive()
  const blockerCount = coherenceAvailable
    ? (coherence.active_contradictions ?? coherence.by_mode?.CONTRADICTION ?? 0)
      + (coherence.active_orphans     ?? coherence.by_mode?.ORPHAN ?? 0)
      + (coherence.active_inversions  ?? coherence.by_mode?.INVERSION ?? 0)
    : '—'

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
        // Stage 5.3 (iPhone 15 Finding B): explicit overflow-x:auto so
        // iOS Safari gives momentum-scroll on touch instead of the
        // default panning behavior. flex-shrink:0 on MetricCell + Link
        // children keeps them from squeezing into illegibility on
        // narrow viewports.
        overflowX:      'auto',
        WebkitOverflowScrolling: 'touch',
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
          flexShrink:     0,
          whiteSpace:     'nowrap',
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

      {/* Stage 5.3 (iPhone 15 Finding B): spacer is flex-shrink:1 so
          it collapses to zero when content overflows the viewport on
          phone, instead of holding non-zero width and creating dead
          space between the badges and the metric cells. */}
      <div style={{ flex: '1 1 0', minWidth: 0 }} />

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
        isLast
        value={blockerCount}
        accent={!coherenceAvailable
          ? 'var(--os-text-faint)'
          : blockerCount > 0
            ? 'var(--os-status-blocked)'
            : 'var(--os-status-live)'}
      />
    </nav>
  )
}
