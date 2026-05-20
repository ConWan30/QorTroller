// QorTroller Operator · O3 Evidence — QRESCE-0001 v0.5 grant-evaluator remodel.
//
// The honesty-discipline dashboard. Top strip leads with the two surfaces that
// tell an evaluator "the protocol monitors itself + tells the truth" before
// anything else: the chain-submission KILL-SWITCH and FLEET COHERENCE. Then
// tournament pre-flight gates, the AIT biometric separation matrix, PCC
// intelligence, protocol-coherence anchor, and grind blocking reasons.
//
// HONESTY-PRESERVING ADAPTATION over the design export: the kill-switch is
// READ-ONLY here. The export prototyped interactive FORCE PAUSE / RE-ARM
// buttons, but chain-submission state is operator-env-controlled
// (CHAIN_SUBMISSION_PAUSED) and the BRIDGE-NEVER-GRANTS invariant forbids the
// frontend from toggling chain state. We display the REAL state from
// usePublicProtocolState().kill_switch_paused and nothing more.
//
// All other panels read the real bridge hooks (noMock:true). With a real
// separation ratio of 1.199 (AIT) — not the export stub's 3.47 — the matrix
// shows the truth, blockers in red, cleared pairs in green.

import {
  useTournamentPreflight, useFleetCoherenceStatus, useAITSeparation,
  usePCCIntelligence, useProtocolCoherence, useGrindAnalytics,
} from '../api/bridgeApi'
import { usePublicProtocolState } from '../api/publicForensic'
import { Panel, StatusChip } from '../design/Primitives'
import '../design/qortroller-kit.css'

function PreflightGate({ label, passed }) {
  const known = passed != null
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '1fr auto', gap: 10, padding: '10px 12px',
      background: 'var(--panel-soft)',
      border: `1px solid ${known ? (passed ? 'var(--chain)' : 'var(--status-blocked)') : 'var(--border)'}`,
      borderRadius: 4, alignItems: 'center',
    }}>
      <span className="mono" style={{ fontSize: 11, color: 'var(--text)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>{label}</span>
      <StatusChip tone={known ? (passed ? 'live' : 'blocked') : 'dormant'}>
        {known ? (passed ? 'PASS' : 'FAIL') : '—'}
      </StatusChip>
    </div>
  )
}

function MetricRow({ label, value, unit, tone }) {
  const color = tone === 'amber' ? 'var(--accent-amber)'
    : tone === 'chain' ? 'var(--chain)'
      : tone === 'err' ? 'var(--status-blocked)'
        : 'var(--text)'
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', padding: '6px 0', borderBottom: '1px solid var(--border-soft)' }}>
      <span className="label">{label}</span>
      <span className="mono" style={{ fontSize: 14, color }}>
        {value}{unit && <span className="faint" style={{ fontSize: 10, marginLeft: 4 }}>{unit}</span>}
      </span>
    </div>
  )
}

function PairDistanceMatrix({ pairs }) {
  const players = ['P1', 'P2', 'P3']
  const get = (a, b) => {
    if (a === b) return null
    const p = pairs || {}
    return p[`${a}v${b}`] ?? p[`${b}v${a}`]
  }
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '40px repeat(3, 1fr)', gap: 4 }}>
      <span></span>
      {players.map((p) => <span key={p} className="label" style={{ textAlign: 'center' }}>{p}</span>)}
      {players.map((a) => (
        <Fragment3 key={a} a={a} players={players} get={get} />
      ))}
    </div>
  )
}

function Fragment3({ a, players, get }) {
  return (
    <>
      <span className="label" style={{ alignSelf: 'center' }}>{a}</span>
      {players.map((b) => {
        const d = get(a, b)
        if (d == null) {
          return (
            <div key={b} style={{
              aspectRatio: '1', background: 'var(--bg)', border: '1px solid var(--border-soft)',
              display: 'grid', placeItems: 'center', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-faint)',
            }}>—</div>
          )
        }
        const passed = d > 1
        return (
          <div key={b} style={{
            aspectRatio: '1', background: 'var(--panel-soft)',
            border: `1px solid ${passed ? 'var(--chain)' : 'var(--status-blocked)'}`,
            display: 'grid', placeItems: 'center', fontFamily: 'var(--font-mono)', fontSize: 13,
            color: passed ? 'var(--chain)' : 'var(--status-blocked)', letterSpacing: '0.02em',
          }}>{d.toFixed(2)}</div>
        )
      })}
    </>
  )
}

function CoherenceBucket({ label, count }) {
  const known = count != null
  const ok = count === 0
  const color = !known ? 'var(--text-faint)' : ok ? 'var(--chain)' : 'var(--accent-amber)'
  return (
    <div style={{
      padding: '10px 12px', background: 'var(--panel-soft)',
      border: `1px solid ${!known ? 'var(--border)' : ok ? 'var(--chain)' : 'var(--accent-amber)'}`,
      borderRadius: 4, display: 'grid', gap: 4,
    }}>
      <span className="mono" style={{ fontSize: 22, color }}>{known ? count : '—'}</span>
      <span className="label" style={{ color: 'var(--text-dim)' }}>{label}</span>
    </div>
  )
}

export function OperatorView() {
  const { data: preflight } = useTournamentPreflight()
  const { data: fleet }     = useFleetCoherenceStatus()
  const { data: ait }       = useAITSeparation()
  const { data: pcc }       = usePCCIntelligence()
  const { data: proto }     = useProtocolCoherence()
  const { data: analytics } = useGrindAnalytics()
  const { data: pub }       = usePublicProtocolState()

  // Kill-switch — READ-ONLY (operator-env-controlled; frontend never toggles).
  const killPaused = pub?.kill_switch_paused
  const killKnown = killPaused != null

  const totalOpen = fleet?.total_open
  const sev = fleet?.by_severity || {}
  const blocking = analytics?.blocking_reason_counts || {}

  return (
    <div className="qt-design-root" style={{ overflow: 'auto' }}>
      <div style={{ display: 'grid', gridAutoRows: 'min-content', gap: 16, padding: 16 }}>

        {/* ═══ ROW 1 — HONESTY HEROES: KILL-SWITCH + FLEET COHERENCE ═══ */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <Panel padding={false}>
            <header className="p-head">
              <span className="p-head__eye">KILL · SWITCH · OPERATOR</span>
              <span className="p-head__meta">CHAIN-SUBMISSION GATE · READ-ONLY</span>
            </header>
            <div style={{ padding: '16px 18px', display: 'grid', gap: 10 }}>
              <StatusChip tone={!killKnown ? 'dormant' : killPaused ? 'pending' : 'live'}>
                {!killKnown ? 'STATE UNAVAILABLE'
                  : killPaused ? 'PAUSED · NO SUBMISSIONS'
                    : 'ARMED · ACCEPTING SUBMISSIONS'}
              </StatusChip>
              <span className="mono" style={{ fontSize: 11, color: 'var(--text-dim)', lineHeight: 1.5 }}>
                {!killKnown
                  ? 'Bridge /public/protocol-state did not report a kill-switch state.'
                  : killPaused
                    ? 'Chain submissions held. Sessions still validate + GIC-chain locally; no on-chain anchoring fires. No fabrication.'
                    : 'Chain submissions live. GIC chain advancing; public anchor active.'}
              </span>
              <span className="label faint" style={{ lineHeight: 1.5 }}>
                Controlled operator-side via CHAIN_SUBMISSION_PAUSED. Per the
                bridge-never-grants invariant, this surface observes — it cannot toggle.
              </span>
            </div>
          </Panel>

          <Panel padding={false}>
            <header className="p-head">
              <span className="p-head__eye">FLEET · COHERENCE · MONITOR</span>
              <StatusChip tone={totalOpen == null ? 'dormant' : totalOpen === 0 ? 'live' : 'pending'}>
                {totalOpen == null ? '—' : totalOpen === 0 ? 'COHERENT · 0 OPEN' : `${totalOpen} OPEN`}
              </StatusChip>
            </header>
            <div style={{ padding: '14px 18px', display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
              <CoherenceBucket label="contradiction" count={fleet?.active_contradictions} />
              <CoherenceBucket label="orphan"        count={fleet?.active_orphans} />
              <CoherenceBucket label="inversion"     count={fleet?.active_inversions} />
            </div>
            <div style={{ padding: '8px 18px 14px', borderTop: '1px solid var(--border-soft)', display: 'flex', justifyContent: 'space-between' }}>
              <span className="label">severity</span>
              <span className="mono" style={{ fontSize: 11 }}>
                <span style={{ color: (sev.P0 ?? 0) > 0 ? 'var(--status-blocked)' : 'var(--chain)' }}>P0 · {sev.P0 ?? 0}</span>{' '}
                <span style={{ color: (sev.P1 ?? 0) > 0 ? 'var(--accent-amber)' : 'var(--chain)' }}>· P1 · {sev.P1 ?? 0}</span>{' '}
                <span style={{ color: 'var(--text-dim)' }}>· P2 · {sev.P2 ?? 0}</span>
              </span>
            </div>
          </Panel>
        </div>

        {/* ═══ ROW 2 — TOURNAMENT PRE-FLIGHT ═══ */}
        <Panel
          eyebrow="TOURNAMENT · PRE-FLIGHT · GATES"
          meta={preflight == null ? 'AWAITING BRIDGE' : preflight.overall_pass ? 'CLEARED' : 'BLOCKED'}
        >
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10 }}>
            <PreflightGate label="separation"  passed={preflight?.separation_ok} />
            <PreflightGate label="l4 · stamps" passed={preflight?.l4_ok} />
            <PreflightGate label="gate"        passed={preflight?.gate_ok} />
            <PreflightGate label="cert"        passed={preflight?.cert_ok} />
            <PreflightGate label="audit"       passed={preflight?.audit_ok} />
          </div>
          <div style={{ marginTop: 12, paddingTop: 10, borderTop: '1px solid var(--border-soft)', display: 'flex', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
            <span className="label">biometric · ttl</span>
            <span className="mono" style={{ fontSize: 12, color: preflight?.biometric_ttl_ok ? 'var(--chain)' : 'var(--status-blocked)' }}>
              ● {preflight == null ? '—' : preflight.biometric_ttl_ok ? 'OK' : 'EXPIRED'}
            </span>
            <span className="label">all · pairs · &gt; 1.0</span>
            <span className="mono" style={{ fontSize: 12, color: preflight?.all_pairs_p0_ok ? 'var(--chain)' : 'var(--accent-amber)' }}>
              ● {preflight == null ? '—' : preflight.all_pairs_p0_ok ? 'OK' : 'PENDING'}
            </span>
          </div>
        </Panel>

        {/* ═══ ROW 3 — AIT + PCC + PROTOCOL COHERENCE ═══ */}
        <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 0.8fr 1.2fr', gap: 16 }}>
          <Panel
            eyebrow="A.I.T. · BIOMETRIC · SEPARATION"
            meta={ait == null ? '—' : `RATIO ${ait.separation_ratio?.toFixed?.(3) ?? '—'}${ait.loo_accuracy != null ? ` · LOO ${(ait.loo_accuracy * 100).toFixed(1)}%` : ''}`}
          >
            <PairDistanceMatrix pairs={ait?.pair_distances} />
            <div style={{ marginTop: 12, display: 'grid', gap: 4 }}>
              <MetricRow label="inter · player mean" value={ait?.inter_player_mean != null ? ait.inter_player_mean.toFixed(3) : '—'} tone="chain" />
              <MetricRow label="intra · player mean" value={ait?.intra_player_mean != null ? ait.intra_player_mean.toFixed(3) : '—'} tone="amber" />
              <MetricRow label="all · pairs · > 1.0" value={ait == null ? '—' : ait.all_pairs_above_1 ? 'YES' : 'NO'} tone={ait?.all_pairs_above_1 ? 'chain' : 'err'} />
            </div>
          </Panel>

          <Panel eyebrow="P.C.C. · INTELLIGENCE" meta={pcc == null ? '—' : `${pcc.total_episodes ?? 0} EPISODES`}>
            <div style={{ display: 'grid', gap: 4 }}>
              <MetricRow label="mean · recovery" value={pcc?.mean_recovery_s != null ? pcc.mean_recovery_s.toFixed(1) : '—'} unit="s" tone="chain" />
              <MetricRow label="longest" value={pcc?.longest_episode_s != null ? pcc.longest_episode_s.toFixed(1) : '—'} unit="s" tone="amber" />
              <MetricRow label="hid · restarts" value={pcc?.hid_counter_restarts ?? '—'} tone="amber" />
              <MetricRow
                label="usb · exclusive"
                value={pcc?.host_state_distribution?.EXCLUSIVE_USB != null ? `${(pcc.host_state_distribution.EXCLUSIVE_USB * 100).toFixed(0)}%` : '—'}
                tone="chain"
              />
            </div>
          </Panel>

          <Panel eyebrow="PROTOCOL · COHERENCE" meta={proto?.on_chain_confirmed ? 'ANCHORED · IoTeX' : proto == null ? '—' : 'PENDING'}>
            <div style={{ display: 'grid', gap: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span className="label">latest · merkle · root</span>
                <StatusChip tone={proto?.on_chain_confirmed ? 'live' : 'dormant'}>
                  {proto?.on_chain_confirmed ? 'ANCHORED' : '—'}
                </StatusChip>
              </div>
              {proto?.latest_merkle_root
                ? (
                  <span className="hash" style={{ fontSize: 11.5 }}>
                    {proto.latest_merkle_root.match(/.{1,8}/g).slice(0, 4).join(' ')}<br />
                    {proto.latest_merkle_root.match(/.{1,8}/g).slice(4).join(' ')}
                  </span>
                )
                : <span className="mono faint" style={{ fontSize: 11 }}>no merkle root yet</span>}
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span className="label">agents · anchored</span>
                <span className="mono" style={{ fontSize: 12, color: 'var(--accent-amber)' }}>{proto?.agent_count ?? '—'} · CEDAR-BUNDLE</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span className="label">total · anchors</span>
                <span className="mono" style={{ fontSize: 12 }}>{proto?.total_anchors != null ? proto.total_anchors.toLocaleString() : '—'}</span>
              </div>
            </div>
          </Panel>
        </div>

        {/* ═══ ROW 4 — BLOCKING REASONS ═══ */}
        <Panel
          eyebrow="BLOCKING · REASON · COUNTS"
          meta={analytics == null ? '—' : `${analytics.total_validated?.toLocaleString?.() ?? 0} TOTAL · ${analytics.success_rate != null ? (analytics.success_rate * 100).toFixed(1) : '—'}% SUCCESS`}
        >
          {Object.keys(blocking).length === 0 ? (
            <div className="mono faint" style={{ fontSize: 11, padding: 8 }}>
              No blocking reasons recorded — pipeline clean (or no grind data yet).
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
              {Object.entries(blocking).map(([k, v]) => (
                <div key={k} style={{
                  padding: '12px 14px', background: 'var(--panel-soft)', border: '1px solid var(--border)',
                  borderRadius: 4, display: 'grid', gap: 6,
                }}>
                  <span className="mono" style={{ fontSize: 26, color: 'var(--accent-amber)' }}>{v}</span>
                  <span className="label" style={{ color: 'var(--text-dim)' }}>{k}</span>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>
    </div>
  )
}
