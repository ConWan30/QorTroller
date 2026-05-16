/**
 * Evidence OS — Protocol State (placeholder vertical slice)
 *
 * Future: protocol-wide observability — PV-CI invariant count,
 * agent fleet phase alignment, kill-switch state, separation ratio
 * per probe type, fleet coherence findings, wallet balance posture.
 * Reuses useProtocolCoherence + useInvariantGateStatus +
 * useFleetCoherenceStatus + usePublicProtocolState +
 * usePublicAgentRoots.
 */
import WorkspaceHeader from '../components/WorkspaceHeader'
import EmptyState from '../components/EmptyState'
import {
  usePublicProtocolState,
  usePublicAgentRoots,
} from '../../api/publicForensic'
import DataBadge from '../components/DataBadge'

function MetricRow({ label, value, status }) {
  return (
    <div style={{
      display:        'flex',
      gap:            16,
      padding:        '10px 14px',
      borderBottom:   '1px solid var(--os-border-soft)',
      alignItems:     'center',
      fontFamily:     'JetBrains Mono, ui-monospace, monospace',
    }}>
      <div style={{ flex: 1, color: 'var(--os-text-dim)', fontSize: 'var(--os-text-base)' }}>
        {label}
      </div>
      <div style={{ color: 'var(--os-text)', fontSize: 'var(--os-text-base)', fontWeight: 600 }}>
        {value}
      </div>
      {status && <DataBadge status={status} />}
    </div>
  )
}

export default function ProtocolStateWorkspace() {
  const { data: state } = usePublicProtocolState()
  const { data: roots } = usePublicAgentRoots()

  if (!state || !roots) {
    return (
      <>
        <WorkspaceHeader
          title="Protocol State"
          description="Protocol-wide observability — PV-CI invariants, agent fleet phase alignment, kill-switch state, separation ratios."
        />
        <div style={{ padding: 32 }}>
          <EmptyState
            title="Loading protocol state…"
            body="Awaiting /public/protocol-state + /public/agent-roots."
            source="frontend/src/api/publicForensic.js"
          />
        </div>
      </>
    )
  }

  return (
    <>
      <WorkspaceHeader
        title="Protocol State"
        description="Live protocol observables — PV-CI invariants, agent fleet, kill-switch posture. Read-only public surface; the operator queue is where state-changing decisions land."
      />
      <div style={{ padding: 32, maxWidth: 900 }}>
        <div style={{
          background:     'var(--os-panel)',
          border:         '1px solid var(--os-border)',
          borderRadius:   'var(--os-radius)',
          overflow:       'hidden',
        }}>
          <MetricRow
            label="PV-CI invariants pinned"
            value={state.pv_ci_invariants_count}
            status={state.pv_ci_invariants_count >= 100 ? 'verified' : 'pending'}
          />
          <MetricRow
            label="VPM artifacts persisted"
            value={state.total_vpm_artifacts}
            status="live"
          />
          <MetricRow
            label="MLGA sessions persisted"
            value={state.total_mlga_sessions}
            status="live"
          />
          <MetricRow
            label="GIC chain links"
            value={state.total_grind_chain_links}
            status="live"
          />
          <MetricRow
            label="Kill-switch"
            value={state.kill_switch_paused ? 'PAUSED (CHAIN_SUBMISSION_PAUSED=true)' : 'LIVE'}
            status={state.kill_switch_paused ? 'killswitch' : 'live'}
          />
          <MetricRow
            label="Operator Initiative agents"
            value={`${roots.agents.length} agents`}
            status="live"
          />
          <MetricRow
            label="Chain"
            value={`${roots.chain.name} (chain_id ${roots.chain.chain_id})`}
            status="live"
          />
        </div>
      </div>
    </>
  )
}
