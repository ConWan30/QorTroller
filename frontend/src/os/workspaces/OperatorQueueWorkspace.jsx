/**
 * Evidence OS Stage 3 — Operator Queue
 *
 * Unified decision queue across the protocol's human-reviewed surfaces.
 *
 * Composed hooks (operator brief — these EXACT 7):
 *   useOperatorDrafts          — Sentry/Guardian/Curator drafts (writable)
 *   useReviewDraft             — POST mutation (already shipped)
 *   useCuratorStatus           — Curator agent status (read-only)
 *   useCuratorFlaggedListings  — recently flagged marketplace listings
 *   useDriftLog                — bundle / scope-hash drift findings
 *   useFleetReadinessRoot      — O3 readiness blockers per agent
 *   useInvariantGateStatus     — PV-CI gate state (gates write actions)
 *   useFleetCoherenceStatus    — FSCA contradictions / orphans / inversions
 *
 * Queue item kinds:
 *   - draft           (writable via useReviewDraft)
 *   - curator         (recommend operator review on marketplace bench)
 *   - drift           (recommend investigation; read-only here)
 *   - o3-blocker      (recommend wait / operator-flag-flip; read-only)
 *   - invariant-fail  (CRITICAL; recommend invariant gate audit; read-only)
 *
 * Safety contract (operator brief):
 *   - mock-active                → all write actions disabled with guard
 *   - invariant gate FAIL        → write actions disabled with guard
 *   - destructive (accept/reject/overturn) → explicit two-click confirm
 *   - empty queue                → honest message ("0 items in window")
 *                                  never "all clear" without invariant cross-check
 */
import { useState, useMemo, useCallback } from 'react'
import {
  useOperatorDrafts,
  useReviewDraft,
  useCuratorStatus,
  useCuratorFlaggedListings,
  useDriftLog,
  useFleetReadinessRoot,
  useInvariantGateStatus,
  useFleetCoherenceStatus,
} from '../../api/bridgeApi'
import { isMockActive } from '../../api/mockBridge'
import WorkspaceHeader from '../components/WorkspaceHeader'
import QueueSummary    from '../components/QueueSummary'
import QueueItem       from '../components/QueueItem'
import QueueDetailPanel from '../components/QueueDetailPanel'
import EmptyState      from '../components/EmptyState'

/* ------------------------------------------------------------------ */
/*  Utilities                                                          */
/* ------------------------------------------------------------------ */

function _ageLabel(tsLike) {
  if (!tsLike) return '—'
  let ms = null
  if (typeof tsLike === 'number') {
    ms = tsLike > 1e12 ? tsLike : tsLike * 1000
  } else if (typeof tsLike === 'string') {
    const parsed = Date.parse(tsLike)
    if (!Number.isNaN(parsed)) ms = parsed
  }
  if (ms === null) return '—'
  const dt = Math.max(0, Date.now() - ms) / 1000
  if (dt < 60)        return `${Math.round(dt)}s ago`
  if (dt < 3600)      return `${Math.round(dt / 60)}m ago`
  if (dt < 86400)     return `${Math.round(dt / 3600)}h ago`
  return `${Math.round(dt / 86400)}d ago`
}

const _SEVERITY_RANK = { critical: 0, warn: 1, info: 2 }

function _bySeverityThenAge(a, b) {
  const sa = _SEVERITY_RANK[a.severity] ?? 9
  const sb = _SEVERITY_RANK[b.severity] ?? 9
  if (sa !== sb) return sa - sb
  // Most recent first
  return (b.ageMs || 0) - (a.ageMs || 0)
}

function _msFromTs(tsLike) {
  if (!tsLike) return 0
  if (typeof tsLike === 'number') return tsLike > 1e12 ? tsLike : tsLike * 1000
  if (typeof tsLike === 'string') {
    const parsed = Date.parse(tsLike); return Number.isNaN(parsed) ? 0 : parsed
  }
  return 0
}

/* ------------------------------------------------------------------ */
/*  Item builders — one per hook                                       */
/* ------------------------------------------------------------------ */

function _draftToItem(draft, { writeGuard } = {}) {
  const actionName = draft.action_name || '?'
  const agentId = String(draft.agent_id || '').slice(0, 12)
  return {
    id:             `draft-${draft.id}`,
    kind:           'draft',
    title:          `Draft awaiting review — ${actionName}`,
    protocolTerm:   `agent=${agentId}… action=${actionName}`,
    source:         '/operator/operator-agent-drafts',
    severity:       'warn',
    ageLabel:       _ageLabel(draft.created_at),
    ageMs:          _msFromTs(draft.created_at),
    recommendation: 'Inspect payload, write a reason ≥10 chars, then accept / reject / overturn',
    actionLabel:    'Review',
    actionGuardReason: writeGuard || undefined,
    openable:       true,
    raw:            draft,
  }
}

function _curatorFlaggedToItem(row) {
  const sev = (row.severity === 'CRITICAL' || row.severity === 'HIGH') ? 'critical' : 'warn'
  return {
    id:             `curator-${row.listing_commitment || row.review_id || Math.random().toString(36).slice(2)}`,
    kind:           'curator',
    title:          `Curator flagged listing — ${row.verdict || 'verdict pending'}`,
    protocolTerm:   `commitment=${String(row.listing_commitment || '').slice(0, 12)}… severity=${row.severity || '?'}`,
    source:         '/agent/curator-flagged-listings',
    severity:       sev,
    ageLabel:       _ageLabel(row.created_at || row.reviewed_at),
    ageMs:          _msFromTs(row.created_at || row.reviewed_at),
    recommendation: row.reason_detail
      ? `Review on marketplace bench — Curator notes: ${row.reason_detail.slice(0, 120)}`
      : 'Review on marketplace bench; cross-check anchor freshness + consent state',
    openable:       true,
    raw:            row,
  }
}

function _driftToItem(row) {
  const t = row.drift_type || 'DRIFT'
  return {
    id:             `drift-${row.id || `${t}-${row.created_at}`}`,
    kind:           'drift',
    title:          t === 'BUNDLE_HASH_DRIFT'
      ? 'Cedar bundle drift — file mutated after anchor'
      : t === 'SCOPE_HASH_GOVERNANCE_DRIFT'
        ? 'AgentScope drift — governance hash mismatch'
        : `Drift finding — ${t}`,
    protocolTerm:   `type=${t} agent=${String(row.agent_id || '').slice(0, 12)}…`,
    source:         '/operator/operator-agent-drift-log',
    severity:       t === 'SCOPE_HASH_GOVERNANCE_DRIFT' ? 'critical' : 'warn',
    ageLabel:       _ageLabel(row.created_at),
    ageMs:          _msFromTs(row.created_at),
    recommendation: t === 'BUNDLE_HASH_DRIFT'
      ? 'Audit bundle file vs anchored Merkle; re-anchor only after governance review'
      : 'Audit AgentScope.scopeRoot vs AgentRegistry.scopeHash; investigate governance event chain',
    openable:       true,
    raw:            row,
  }
}

function _o3BlockerToItems(per_agent = []) {
  const items = []
  per_agent.forEach(agent => {
    const blockers = agent.o3_blockers || []
    blockers.forEach((b, i) => {
      items.push({
        id:             `o3-${agent.agent_id}-${i}`,
        kind:           'o3-blocker',
        title:          `O3 readiness blocker (${agent.agent_id || 'agent'})`,
        protocolTerm:   `blocker=${String(b).slice(0, 60)}`,
        source:         '/operator/fleet-readiness-root',
        severity:       'info',
        ageLabel:       '—',
        ageMs:          0,
        recommendation: 'Watcher-derived blocker; resolve via shadow time / draft accumulation / operator flag',
        openable:       true,
        raw:            { agent_id: agent.agent_id, blocker: b, agent },
      })
    })
  })
  return items
}

function _invariantFailToItem(inv) {
  const failures = inv?.last_failures || []
  if (!failures.length) return null
  return {
    id:             'inv-gate',
    kind:           'invariant-fail',
    title:          `Invariant gate FAILING — ${failures.length} invariant${failures.length === 1 ? '' : 's'}`,
    protocolTerm:   `total_checked=${inv.total_checked} failed=${failures.length}`,
    source:         '/agent/invariant-gate-status',
    severity:       'critical',
    ageLabel:       _ageLabel(inv.last_run_ts),
    ageMs:          _msFromTs(inv.last_run_ts),
    recommendation: 'STOP protocol-altering work. Run vapi_invariant_gate.py --report; resolve every failure before any write.',
    openable:       true,
    raw:            inv,
  }
}

/* ------------------------------------------------------------------ */
/*  Workspace                                                          */
/* ------------------------------------------------------------------ */

export default function OperatorQueueWorkspace() {
  const drafts       = useOperatorDrafts({ decision: 'unreviewed', sinceMinutes: 10080, limit: 100 })
  const reviewMutate = useReviewDraft()
  const curator      = useCuratorStatus()
  const flagged      = useCuratorFlaggedListings({ sinceMinutes: 1440, limit: 50 })
  const drift        = useDriftLog({ sinceMinutes: 1440, limit: 50 })
  const frr          = useFleetReadinessRoot()
  const invGate      = useInvariantGateStatus()
  const coherence    = useFleetCoherenceStatus()

  const mockActive = isMockActive()
  const invariantFailing = invGate?.data && invGate.data.gate_pass === false
  const [selectedId, setSelectedId] = useState(null)
  const [lastSuccessId, setLastSuccessId] = useState(null)

  // Compute the write-guard once so every action surface routes through
  // the same reason — operator can never see "disabled" without a label.
  const writeGuard = mockActive
    ? 'mock-active'
    : invariantFailing
      ? 'invariant-failing'
      : null

  // onAction handler — opens the detail panel for the item. Wired on
  // draft items so the inline "Review" button is a keyboard shortcut
  // for the row-click open. Without this, QueueItem renders an
  // ActionGuardBadge for "no mutation wired" — undesirable when the
  // detail panel IS the mutation surface.
  const openItem = useCallback((item) => {
    setSelectedId(item.id)
  }, [])

  // Build unified item list (memoised)
  const items = useMemo(() => {
    const acc = []
    const draftRows = drafts?.data?.drafts || []
    draftRows.forEach(d => {
      const it = _draftToItem(d, { writeGuard })
      if (!writeGuard) it.onAction = openItem    // route Review → open detail
      acc.push(it)
    })

    const flaggedRows = flagged?.data?.listings || []
    flaggedRows.forEach(r => acc.push(_curatorFlaggedToItem(r)))

    const driftRows = drift?.data?.findings || drift?.data?.entries || drift?.data?.rows || []
    driftRows.forEach(r => acc.push(_driftToItem(r)))

    const perAgent = frr?.data?.per_agent || []
    _o3BlockerToItems(perAgent).forEach(i => acc.push(i))

    const invItem = _invariantFailToItem(invGate?.data)
    if (invItem) acc.push(invItem)

    return acc.sort(_bySeverityThenAge)
  }, [drafts?.data, flagged?.data, drift?.data, frr?.data, invGate?.data, writeGuard, openItem])

  // Summary tile counts
  const tiles = useMemo(() => {
    const draftCount = (drafts?.data?.drafts || []).length
    const flaggedCount = (flagged?.data?.listings || flagged?.data?.entries || []).length
    const driftCount = (drift?.data?.findings || drift?.data?.entries || drift?.data?.rows || []).length
    const critical = items.filter(i => i.severity === 'critical').length
    const invFails = invGate?.data?.last_failures?.length ?? 0

    return [
      {
        label: 'Total pending',
        count: items.length,
        status: items.length === 0 ? 'live' : 'pending',
        hint:   items.length === 0 ? '0 items in last 24h–7d window' : 'attention required',
      },
      {
        label: 'Critical blockers',
        count: critical,
        status: critical > 0 ? 'blocked' : 'live',
        hint:   critical > 0 ? 'investigate before any write' : 'no critical findings',
      },
      {
        label: 'Drafts',
        count: draftCount,
        status: draftCount > 0 ? 'pending' : 'live',
        hint:   draftCount > 0 ? 'awaiting your decision' : 'queue empty',
      },
      {
        label: 'Curator flags',
        count: flaggedCount,
        status: flaggedCount > 0 ? 'pending' : 'live',
        hint:   'last 24h',
      },
      {
        label: 'Drift findings',
        count: driftCount,
        status: driftCount > 0 ? 'pending' : 'live',
        hint:   'bundle + scope-hash drift, last 24h',
      },
      {
        label: 'Invariant gate',
        count: invariantFailing ? `${invFails} fail` : 'pass',
        status: invariantFailing ? 'blocked' : 'verified',
        hint:   invariantFailing
          ? 'sensitive write actions disabled'
          : `${invGate?.data?.total_checked ?? '—'} invariants verified`,
      },
    ]
  }, [items, drafts, flagged, drift, invGate, invariantFailing])

  const selected = items.find(i => i.id === selectedId) || null

  // Open from row click
  const handleOpen = useCallback((item) => {
    setSelectedId(prev => prev === item.id ? null : item.id)
  }, [])

  // Submit review (only enabled for drafts)
  const handleReviewDraft = useCallback(({ draftId, decision, reason }) => {
    reviewMutate.mutate(
      { draftId, decision, reason },
      {
        onSuccess: () => {
          setLastSuccessId(draftId)
          // Auto-close detail after a successful review so the operator
          // sees the row vanish from the queue list.
          setTimeout(() => {
            setSelectedId(null)
            setLastSuccessId(null)
          }, 1500)
        },
      },
    )
  }, [reviewMutate])

  // Errors / status surfaces
  const anyBridgeOffline =
    drafts.isError || curator.isError || flagged.isError ||
    drift.isError  || frr.isError      || invGate.isError ||
    coherence.isError
  const reviewError = reviewMutate.error
    ? (reviewMutate.error.message || String(reviewMutate.error))
    : ''

  return (
    <>
      <WorkspaceHeader
        title="Operator Queue"
        description="Every protocol surface that needs operator judgement, in one place. Drafts, Curator flags, Cedar drift, O3-readiness blockers, and invariant-gate failures — sorted by severity, never numeric-only."
        right={mockActive
          ? <span style={{
              padding: '4px 10px', borderRadius: 'var(--os-radius)',
              border: '1px solid var(--os-status-mock)',
              color: 'var(--os-status-mock)',
              fontSize: 'var(--os-text-min)',
              letterSpacing: '0.08em', textTransform: 'uppercase',
            }}>MOCK ACTIVE — WRITES DISABLED</span>
          : invariantFailing
            ? <span style={{
                padding: '4px 10px', borderRadius: 'var(--os-radius)',
                border: '1px solid var(--os-status-blocked)',
                color: 'var(--os-status-blocked)',
                fontSize: 'var(--os-text-min)',
                letterSpacing: '0.08em', textTransform: 'uppercase',
              }}>INVARIANT GATE FAILING — SENSITIVE WRITES DISABLED</span>
            : null}
      />

      <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 18 }}>
        <QueueSummary tiles={tiles}/>

        {anyBridgeOffline && (
          <div role="status" aria-live="polite" style={{
            padding: '10px 14px',
            border: '1px solid var(--os-status-pending)',
            borderLeft: '3px solid var(--os-status-pending)',
            borderRadius: 'var(--os-radius)',
            color: 'var(--os-status-pending)',
            fontSize: 'var(--os-text-base)',
            background: 'var(--os-panel)',
          }}>
            At least one bridge source is offline — queue is partial. Read the
            tile statuses; LIVE means the hook responded.
          </div>
        )}

        {items.length === 0 ? (
          <EmptyState
            title="0 items in window"
            body={
              invariantFailing
                ? <>The queue is empty, but the <strong>invariant gate is FAILING</strong> — that is itself the dominant blocker. Run <code>vapi_invariant_gate.py --report</code>.</>
                : mockActive
                  ? <>Mock data is active — the queue may be empty because the bridge isn't reachable, not because there's nothing to do.</>
                  : <>No drafts, no Curator flags, no drift findings, no O3 blockers, no invariant failures in the last 24h–7d window. This is honest <em>quiet</em> — verify any underlying surface on demand with the Evidence Graph or Live Match workspaces before relying on it.</>
            }
            source="useOperatorDrafts · useCuratorFlaggedListings · useDriftLog · useFleetReadinessRoot · useInvariantGateStatus"
          />
        ) : (
          <ul role="list" style={{
            listStyle: 'none', padding: 0, margin: 0,
            display: 'flex', flexDirection: 'column', gap: 10,
          }}>
            {items.map(item => (
              <li key={item.id} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <QueueItem
                  item={item}
                  onOpen={handleOpen}
                  isSelected={selectedId === item.id}
                />
                {selectedId === item.id && (
                  <QueueDetailPanel
                    item={item}
                    onClose={() => setSelectedId(null)}
                    onReviewDraft={item.kind === 'draft' ? handleReviewDraft : undefined}
                    mockActive={mockActive}
                    invariantFailing={invariantFailing}
                    reviewInFlight={reviewMutate.isPending}
                    reviewError={reviewError}
                    reviewSucceededFor={lastSuccessId}
                  />
                )}
              </li>
            ))}
          </ul>
        )}

        {/* Footer hint */}
        <div style={{
          fontSize: 'var(--os-text-min)',
          color: 'var(--os-text-faint)',
          fontFamily: 'JetBrains Mono, ui-monospace, monospace',
          padding: '4px 2px',
        }}>
          Sort: severity (critical → warn → info), then most-recent first.
          Window: drafts last 7d · flags + drift last 24h · O3 + invariants live.
        </div>
      </div>
    </>
  )
}
