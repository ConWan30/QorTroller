/**
 * Evidence OS Stage 5 — Protocol State
 *
 * Three-section observability surface answering the operator's
 * five questions:
 *
 *   1. What is the protocol's posture right now?
 *      → POSTURE band: kill-switch + chain + invariant gate +
 *        fleet coherence snapshot — all from public surface so
 *        no auth gates this answer.
 *
 *   2. Where does the truth chain come from?
 *      → IDENTITY band: Operator Initiative agent roots + chain
 *        id — public via /public/agent-roots.
 *
 *   3. What is the tournament-readiness empirical state?
 *      → MEASUREMENT band: separation ratios per probe type,
 *        PV-CI invariant count, persisted volume — public.
 *
 * Plus optional operator-detail expansion: when an authenticated
 * session is reachable, surface fleet coherence findings (CONTRADICTION/
 * ORPHAN/INVERSION counts) and invariant-gate failure list — these
 * use /operator/* and /agent/* endpoints that require api_key; on a
 * bridge-offline or 401/403, the workspace renders an HONEST
 * "operator detail unavailable" state instead of fabricating.
 *
 * Composition (per Stage 1 intent + brief):
 *   usePublicProtocolState   (public, no auth)
 *   usePublicAgentRoots       (public, no auth)
 *   useFleetCoherenceStatus  (operator, may be offline — honest)
 *   useInvariantGateStatus   (operator, may be offline — honest)
 *
 * Discipline:
 *   - All status labels redundant to color
 *   - Mock and offline state visibly separated from live
 *   - Public surface is the truth-floor; operator-detail is bonus
 */
import { useMemo } from 'react'
import { usePublicProtocolState, usePublicAgentRoots } from '../../api/publicForensic'
import { useFleetCoherenceStatus, useInvariantGateStatus } from '../../api/bridgeApi'
import { isMockActive } from '../../api/mockBridge'
import WorkspaceHeader from '../components/WorkspaceHeader'
import EmptyState      from '../components/EmptyState'
import DataBadge       from '../components/DataBadge'

const _MONO = 'JetBrains Mono, ui-monospace, monospace'

function _Section({ title, subtitle, children, right }) {
  return (
    <section
      role="region"
      aria-label={title}
      style={{
        display:        'flex',
        flexDirection:  'column',
        gap:            10,
        padding:        '16px 18px',
        background:     'var(--os-panel)',
        border:         '1px solid var(--os-border)',
        borderRadius:   'var(--os-radius)',
        fontFamily:     _MONO,
      }}
    >
      <header style={{
        display:        'flex',
        alignItems:     'center',
        justifyContent: 'space-between',
        gap:            12,
      }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <h3 style={{
            margin: 0,
            fontSize: 'var(--os-text-h3)',
            fontWeight: 700,
            color: 'var(--os-text)',
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
          }}>{title}</h3>
          {subtitle && (
            <div style={{
              fontSize: 'var(--os-text-min)',
              color: 'var(--os-text-faint)',
            }}>{subtitle}</div>
          )}
        </div>
        {right}
      </header>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
        {children}
      </div>
    </section>
  )
}

function _Row({ label, value, status, hint }) {
  return (
    <div style={{
      display:        'flex',
      alignItems:     'center',
      gap:            14,
      padding:        '10px 0',
      borderTop:      '1px solid var(--os-border-soft)',
      fontFamily:     _MONO,
    }}>
      <div style={{
        flex: 1,
        color: 'var(--os-text-dim)',
        fontSize: 'var(--os-text-base)',
        minWidth: 0,
      }}>
        {label}
        {hint && (
          <div style={{
            fontSize: 'var(--os-text-min)',
            color: 'var(--os-text-faint)',
            marginTop: 2,
          }}>{hint}</div>
        )}
      </div>
      <div style={{
        color: 'var(--os-text)',
        fontSize: 'var(--os-text-base)',
        fontWeight: 600,
        textAlign: 'right',
        wordBreak: 'break-all',
      }}>{value ?? '—'}</div>
      {status && <DataBadge status={status}/>}
    </div>
  )
}

// Operator-deferred probe set — cast out of the active gate evaluation
// per explicit operator authorization. Mirrors the protocol-level
// tremor_resting P1vP3 cast-out (CLAUDE.md 2026-05-09). The corpus stays
// queryable for transparency; the probe is no longer evaluated as a
// blocker. Adding to this set is a documentation-only operator decision
// — no protocol code path treats deferred probes specially.
const _DEFERRED_PROBES = new Set([
  'touchpad_corners',  // 2026-05-16: AIT (1.199) cleared and touchpad signal
                       // is structurally absent in NCAA CFB 26 gameplay
                       // (zero touchpad-active fraction). No path to >1.0
                       // through this probe; cast out as development
                       // progress blocker per operator authorization.
                       // Mainnet TGE invariant remains in force via AIT.
])

function _ProbeBar({ probe, ratio, target = 1.0 }) {
  const pct = Math.max(0, Math.min(100, (ratio / Math.max(1.0, target)) * 100))
  const cleared = ratio >= target
  const deferred = _DEFERRED_PROBES.has(probe)
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', gap: 4,
      padding: '10px 0',
      borderTop: '1px solid var(--os-border-soft)',
      opacity: deferred ? 0.75 : 1,
    }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between',
        alignItems: 'center', gap: 12,
      }}>
        <span style={{ color: 'var(--os-text-dim)' }}>{probe}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{
            color: deferred ? 'var(--os-text-dim)' : 'var(--os-text)',
            fontWeight: 600,
            fontFamily: _MONO,
            textDecoration: deferred ? 'line-through' : 'none',
          }}>{ratio?.toFixed(3) ?? '—'}</span>
          {deferred ? (
            <DataBadge
              status="deferred"
              label="DEFERRED"
              title="Operator-deferred per CLAUDE.md NOTE 2026-05-16. Not a live gate input; corpus retained for historical reference. AIT (cleared) is the active discriminator."
            />
          ) : (
            <DataBadge
              status={cleared ? 'verified' : 'pending'}
              label={cleared ? 'CLEARED' : 'BELOW 1.0'}
            />
          )}
        </div>
      </div>
      <div
        role="meter"
        aria-label={`${probe} separation ratio`}
        aria-valuenow={ratio || 0}
        aria-valuemin={0}
        aria-valuemax={target}
        style={{
          height: 6,
          background: 'var(--os-bg)',
          borderRadius: 3,
          overflow: 'hidden',
        }}
      >
        <div style={{
          height: '100%',
          width: `${pct}%`,
          background: cleared ? 'var(--os-status-live)' : 'var(--os-status-pending)',
          transition: 'width 0.3s',
        }}/>
      </div>
    </div>
  )
}

export default function ProtocolStateWorkspace() {
  const { data: state, error: stateError, isLoading: stateLoading } = usePublicProtocolState()
  const { data: roots, error: rootsError } = usePublicAgentRoots()
  const fleetCoherence = useFleetCoherenceStatus()
  const invariantGate  = useInvariantGateStatus()
  const mockActive = isMockActive()

  // Public truth-floor
  const killSwitch = state?.kill_switch_paused
  const pvCount    = state?.pv_ci_invariants_count ?? null
  const sepRatios  = state?.separation_ratios || {}
  const fleetAligned = state?.fleet_phase_aligned

  // Operator-detail (may be unavailable)
  const fleetData = fleetCoherence?.data || null
  const invData   = invariantGate?.data || null
  const operatorAvailable = Boolean(fleetData || invData)
  const operatorOfflineReason = useMemo(() => {
    if (mockActive) return 'Mock mode active — operator detail is unavailable until a real bridge is reachable.'
    if (fleetCoherence?.isError || invariantGate?.isError) return 'Operator endpoint returned an error (bridge offline OR api_key missing).'
    if (!operatorAvailable) return 'Operator detail not yet loaded.'
    return null
  }, [mockActive, fleetCoherence?.isError, invariantGate?.isError, operatorAvailable])

  if (stateLoading && !state) {
    return (
      <>
        <WorkspaceHeader
          title="Protocol State"
          description="Loading public state snapshot…"
        />
        <div style={{ padding: 24 }}>
          <EmptyState
            title="Loading protocol state…"
            body="Awaiting /public/protocol-state + /public/agent-roots."
            source="frontend/src/api/publicForensic.js"
          />
        </div>
      </>
    )
  }

  // Posture status derivation
  const postureStatus = mockActive
    ? 'mock'
    : stateError
      ? 'blocked'
      : killSwitch
        ? 'killswitch'
        : 'live'
  const postureLabel = mockActive
    ? 'MOCK'
    : stateError
      ? 'OFFLINE'
      : killSwitch
        ? 'PAUSED'
        : 'LIVE'

  const agents = roots?.agents || []
  const chainInfo = roots?.chain || {}

  return (
    <>
      <WorkspaceHeader
        title="Protocol State"
        description="Read-only protocol-wide observability. Posture, identity, and measurement — answered from the public /public/* surface so no operator API key is required. Operator-detail expansion (fleet coherence findings, invariant gate failure list) layers in when an authenticated bridge is reachable."
        right={
          <DataBadge status={postureStatus} label={postureLabel}/>
        }
      />

      <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 14 }}>

        {/* ─── SECTION 1 — POSTURE ─────────────────────────── */}
        <_Section
          title="Posture"
          subtitle="What is the protocol doing right now? Public-surface answers."
          right={<DataBadge status={postureStatus} label={postureLabel}/>}
        >
          <_Row
            label="Kill-switch (CHAIN_SUBMISSION_PAUSED)"
            value={killSwitch === undefined ? '—' : killSwitch ? 'PAUSED' : 'OPEN'}
            status={killSwitch ? 'killswitch' : 'live'}
            hint={killSwitch
              ? 'No chain writes occur in this state. Operator-side mint/anchor calls return early before sending.'
              : 'Chain writes are permitted. All operator-authorized actions reach IoTeX testnet.'}
          />
          <_Row
            label="PV-CI invariants pinned"
            value={pvCount === null ? '—' : `${pvCount}`}
            status={pvCount >= 100 ? 'verified' : pvCount > 0 ? 'pending' : 'dormant'}
            hint="Frozen-region SHA-256 hashes that fail the CI gate when changed without governance. Higher is more locked-down."
          />
          <_Row
            label="Fleet phase alignment (FRR)"
            value={fleetAligned === undefined ? '—' : fleetAligned ? 'ALIGNED' : 'NOT ALIGNED'}
            status={fleetAligned ? 'verified' : 'pending'}
            hint="Sentry + Guardian + Curator all at the same Operator Initiative phase (O1_SHADOW / O2_SUGGEST / O3_ACT)."
          />
        </_Section>

        {/* ─── SECTION 2 — MEASUREMENT (tournament readiness) ─── */}
        <_Section
          title="Measurement"
          subtitle="Empirical tournament-readiness state per probe type. Target separation ratio ≥ 1.0."
        >
          {Object.entries(sepRatios).length === 0 ? (
            <div style={{
              padding: '12px 0',
              color: 'var(--os-text-faint)',
              fontStyle: 'italic',
              textAlign: 'center',
            }}>No separation-ratio snapshots published yet.</div>
          ) : (
            Object.entries(sepRatios).map(([probe, ratio]) => (
              <_ProbeBar key={probe} probe={probe} ratio={Number(ratio)} target={1.0}/>
            ))
          )}
          <_Row
            label="VPM artifacts persisted"
            value={state?.total_vpm_artifacts}
            status="live"
            hint="Cryptographically verifiable methodology artifacts emitted by the protocol's compilers."
          />
          <_Row
            label="MLGA sessions persisted"
            value={state?.total_mlga_sessions}
            status="live"
            hint="Methodology Live-Grind Anchor sessions — every closed-out grind run."
          />
          <_Row
            label="GIC chain links"
            value={state?.total_grind_chain_links}
            status="live"
            hint="Tamper-evident hash links across the entire Grind Integrity Chain."
          />
        </_Section>

        {/* ─── SECTION 3 — IDENTITY ─────────────────────────── */}
        <_Section
          title="Identity"
          subtitle={rootsError
            ? 'Agent roots endpoint unavailable — surfacing public posture only.'
            : 'Operator Initiative agent registry + chain anchor. Identity rarely changes; cached aggressively.'}
        >
          <_Row
            label="Chain"
            value={chainInfo.name
              ? `${chainInfo.name} (chain_id ${chainInfo.chain_id})`
              : '—'}
            status={chainInfo.name ? 'live' : 'dormant'}
            hint={chainInfo.network ? `network: ${chainInfo.network}` : null}
          />
          <_Row
            label="Operator Initiative agents"
            value={agents.length > 0 ? `${agents.length} agents` : '—'}
            status={agents.length > 0 ? 'live' : 'dormant'}
            hint={agents.length > 0
              ? agents.map(a => a.canonical_name || a.name || '?').join(' · ')
              : null}
          />
          {agents.map(a => (
            <_Row
              key={a.agent_id || a.canonical_name}
              label={`agent · ${a.canonical_name || a.name || a.agent_id?.slice(0, 12)}`}
              value={a.agent_id
                ? `${String(a.agent_id).slice(0, 14)}…${String(a.agent_id).slice(-6)}`
                : '—'}
              status="verified"
              hint={`phase: ${a.current_phase || a.phase || '?'}${a.scope_root ? ` · scopeRoot: ${String(a.scope_root).slice(0, 12)}…` : ''}`}
            />
          ))}
        </_Section>

        {/* ─── SECTION 4 — OPERATOR DETAIL (graceful unavailable) ─── */}
        <_Section
          title="Operator Detail"
          subtitle="Authenticated bridge expansion — surfaces only when a reachable operator endpoint answers."
          right={
            operatorAvailable
              ? <DataBadge status="live" label="AUTHENTICATED"/>
              : <DataBadge status="dormant" label="UNAVAILABLE"/>
          }
        >
          {operatorOfflineReason ? (
            <div
              role="note"
              data-os-operator-detail="unavailable"
              style={{
                padding: '12px 14px',
                border: '1px dashed var(--os-border)',
                borderRadius: 'var(--os-radius)',
                color: 'var(--os-text-faint)',
                fontSize: 'var(--os-text-base)',
              }}
            >
              <strong style={{ color: 'var(--os-text-dim)' }}>Operator detail unavailable.</strong>{' '}
              {operatorOfflineReason}{' '}
              <span style={{ color: 'var(--os-text-faint)' }}>
                The public posture above remains the trustworthy baseline regardless.
              </span>
            </div>
          ) : (
            <div data-os-operator-detail="available" style={{
              display: 'flex', flexDirection: 'column', gap: 0,
            }}>
              {invData && (
                <>
                  <_Row
                    label="Invariant gate"
                    value={invData.gate_pass
                      ? `${invData.total_checked ?? '?'}/${invData.total_checked ?? '?'} PASS`
                      : `${(invData.last_failures || []).length} FAILING`}
                    status={invData.gate_pass ? 'verified' : 'blocked'}
                    hint={invData.gate_pass
                      ? 'All PV-CI invariants verify locally; safe to land protocol-altering work.'
                      : 'STOP protocol-altering work until every failure is resolved.'}
                  />
                  {!invData.gate_pass && (invData.last_failures || []).slice(0, 5).map((f, i) => (
                    <_Row
                      key={`fail-${i}`}
                      label={`failing invariant · ${f.id || f.name || `#${i}`}`}
                      value={String(f.reason || f.error || 'see CI log').slice(0, 80)}
                      status="blocked"
                    />
                  ))}
                </>
              )}
              {fleetData && (
                <>
                  <_Row
                    label="Fleet coherence — CONTRADICTIONS"
                    value={fleetData.active_contradictions ?? fleetData.by_mode?.CONTRADICTION ?? 0}
                    status={(fleetData.active_contradictions || fleetData.by_mode?.CONTRADICTION || 0) > 0
                      ? 'blocked' : 'verified'}
                    hint="FSCA rules currently firing for inconsistent on-chain vs off-chain state."
                  />
                  <_Row
                    label="Fleet coherence — ORPHANS"
                    value={fleetData.active_orphans ?? fleetData.by_mode?.ORPHAN ?? 0}
                    status={(fleetData.active_orphans || fleetData.by_mode?.ORPHAN || 0) > 0
                      ? 'pending' : 'verified'}
                    hint="State references that point at no parent (e.g. drift event without bundle)."
                  />
                  <_Row
                    label="Fleet coherence — INVERSIONS"
                    value={fleetData.active_inversions ?? fleetData.by_mode?.INVERSION ?? 0}
                    status={(fleetData.active_inversions || fleetData.by_mode?.INVERSION || 0) > 0
                      ? 'pending' : 'verified'}
                    hint="Provenance-DAG timestamp anomalies (child registered before parent — see classifier rubric)."
                  />
                </>
              )}
            </div>
          )}
        </_Section>

        {/* Footer */}
        <div style={{
          fontSize: 'var(--os-text-min)',
          color: 'var(--os-text-faint)',
          fontFamily: _MONO,
          padding: '4px 2px',
        }}>
          Public posture refreshes every 30s. Operator-detail follows
          its own hook cadence (FSCA 8s · invariant gate 30s).
          Source: <code>/public/protocol-state</code> ·
          <code>/public/agent-roots</code> ·
          <code>/agent/fleet-coherence-summary</code> ·
          <code>/agent/invariant-gate-status</code>.
        </div>
      </div>
    </>
  )
}
