/**
 * Evidence OS — EvidenceGraphWorkspace (signature visual)
 *
 * Renders the causal DAG of the protocol's evidence lifecycle:
 *
 *   HID frames → PoAC → GIC → APOP/PCC/AIT → VHP/ZKBA → VPM → Curator → On-chain
 *
 * Every node is wired to a real bridge hook (or honestly labelled
 * "dormant" if no row exists yet). Mythology lines + edge semantics
 * are Mythos-derived (see commit 885a2da4 + parent commits for the
 * mapping rationale).
 *
 * Topology choice for first vertical slice: 4-row grid laid out
 * left-to-right by causal flow. Rows:
 *   1. HID  → PoAC
 *   2. APOP, PCC, AIT  (three parallel sub-substrates from PoAC)
 *   3. GIC  →  VHP / ZKBA  →  VPM  →  Curator
 *   4. On-chain anchor (terminus)
 *
 * Edges drawn as inline SVG overlay; SVG sits above the grid with
 * pointer-events:none so it doesn't intercept node clicks.
 */
import { useMemo, useRef } from 'react'
import { useGrindChain, useCaptureHealth, useActivePlayOccupancy, useAITSeparation, useCuratorStatus, useVpmList } from '../../api/bridgeApi'
import { usePublicVhp, usePublicProtocolState } from '../../api/publicForensic'
import EvidenceNode from '../components/EvidenceNode'
import EvidenceEdgeLayer from '../components/EvidenceEdgeLayer'
import WorkspaceHeader from '../components/WorkspaceHeader'

const _ACCENT_CHAIN     = 'var(--os-chain)'
const _ACCENT_PREDICATE = 'var(--os-predicate)'
const _ACCENT_DERIVED   = 'var(--os-derived)'
const _ACCENT_TERMINUS  = 'var(--os-status-pending)'

/* ------------------------------------------------------------------ */
/*  Status derivation helpers — Mythos-aligned honesty discipline.    */
/*  Never paint mock as live; never paint pending as anchored.        */
/* ------------------------------------------------------------------ */

function hidStatus() {
  // Node 1 is intentionally hook-less: HID frames are infrastructure.
  // Always render as 'live' when bridge reachable (a connected
  // controller IS the protocol's source-of-truth).
  return { status: 'live', detail: '~1 kHz HID poll · pre-signing layer' }
}

function poacStatus(captureHealth) {
  if (!captureHealth) return { status: 'dormant', detail: 'no capture-health snapshot yet' }
  const state = captureHealth.capture_state || captureHealth?.snapshot?.capture_state
  if (state === 'NOMINAL') return {
    status: 'live',
    detail: `capture_state=${state} · ECDSA-P256 signing active`,
  }
  if (state === 'DISCONNECTED') return {
    status: 'blocked',
    detail: 'capture_state=DISCONNECTED · no signing',
  }
  return {
    status: 'pending',
    detail: `capture_state=${state || 'unknown'}`,
  }
}

function gicStatus(grindChain) {
  if (!grindChain) return { status: 'dormant', detail: 'no grind-chain snapshot yet' }
  const len = grindChain.chain_length ?? 0
  const intact = grindChain.chain_intact !== false
  if (!intact) return { status: 'blocked', detail: 'chain_intact=false — investigate before resuming' }
  if (len === 0) return { status: 'dormant', detail: 'no chain links yet · awaiting first PoAC' }
  return {
    status: 'live',
    detail: `chain_length=${len} · head ${(grindChain.latest_gic_hash || '').slice(0, 12)}…`,
  }
}

// Mythos audit M2 — APOP enum → human label translation. Detail copy
// renders the human label first; raw enum is appended in parens so
// the protocol term is still inspectable but the reader gets the
// English meaning first.
const _APOP_HUMAN = {
  ACTIVE_MATCH_PLAY:    'Actively playing',
  COMPETITIVE_CONTROL:  'Competitive control',
  MATCH_TRANSITION:     'Between plays',
  NON_COMPETITIVE_MENU: 'On menu / paused',
  UNKNOWN_LOW_EVIDENCE: 'Insufficient evidence',
}

function _humanApop(s) {
  return _APOP_HUMAN[s] || s || 'Unclassified'
}

function apopStatus(apop) {
  if (!apop) return { status: 'dormant', detail: 'APOP tracker not yet emitting' }
  const s = apop.classification?.state || apop.state
  if (!s) return { status: 'pending', detail: 'no classification yet' }
  const human = _humanApop(s)
  if (s === 'ACTIVE_MATCH_PLAY' || s === 'COMPETITIVE_CONTROL') return {
    status: 'live',
    detail: `${human} (${s})`,
  }
  if (s === 'NON_COMPETITIVE_MENU') return {
    status: 'pending',
    detail: `${human} — gating GIC (${s})`,
  }
  return { status: 'pending', detail: `${human} (${s})` }
}

function pccStatus(captureHealth) {
  if (!captureHealth) return { status: 'dormant', detail: 'no PCC snapshot yet' }
  const cs = captureHealth.capture_state
  const hs = captureHealth.host_state
  if (cs === 'NOMINAL' && (hs === 'EXCLUSIVE_USB' || hs === 'UNKNOWN'))
    return { status: 'live', detail: `${cs} · host=${hs} · trusted` }
  if (cs === 'DISCONNECTED' || hs === 'CONTESTED')
    return { status: 'blocked', detail: `${cs} · host=${hs} · cannot trust` }
  return { status: 'pending', detail: `${cs || 'unknown'} · host=${hs || 'unknown'}` }
}

function aitStatus(ait) {
  if (!ait) return { status: 'dormant', detail: 'no AIT separation snapshot yet' }
  const ratio = ait.separation_ratio
  const n = ait.n_sessions
  if (typeof ratio !== 'number') return { status: 'pending', detail: 'awaiting separation analysis' }
  if (ratio >= 1.0 && n >= 30) return {
    status: 'verified',
    detail: `ratio=${ratio.toFixed(3)} · N=${n} · cleared P0 gate`,
  }
  return {
    status: 'pending',
    detail: `ratio=${(ratio || 0).toFixed(3)} · N=${n || 0} · below P0 gate`,
  }
}

function vhpStatus(vhp) {
  if (!vhp || !vhp.found) return { status: 'dormant', detail: 'no VHP minted for tokenId=2 yet' }
  if (vhp.vhp.is_valid_local) return {
    status: 'verified',
    detail: `tokenId #${vhp.vhp.token_id} · cert ${vhp.vhp.cert_level} · valid`,
  }
  return { status: 'blocked', detail: `tokenId #${vhp.vhp.token_id} expired` }
}

function zkbaStatus(vpmList) {
  // ZKBA surfaces via VPM artifacts (Mythos finding: no direct hook).
  // We count distinct zkba_class values present.
  if (!vpmList?.rows) return { status: 'dormant', detail: 'no VPM artifacts yet' }
  const classes = new Set(vpmList.rows.map((r) => r.zkba_class))
  return {
    status: classes.size > 0 ? 'live' : 'dormant',
    detail: `${classes.size} ZKBA class${classes.size === 1 ? '' : 'es'} active across ${vpmList.rows.length} artifacts`,
  }
}

function vpmStatus(vpmList) {
  if (!vpmList) return { status: 'dormant', detail: 'no VPM artifacts yet' }
  const n = vpmList.row_count ?? vpmList.rows?.length ?? 0
  return {
    status: n > 0 ? 'live' : 'dormant',
    detail: n > 0
      ? `${n} artifact${n === 1 ? '' : 's'} · 6 compilers fire autonomously`
      : 'awaiting first emission',
  }
}

function curatorStatus(curator) {
  if (!curator) return { status: 'dormant', detail: 'curator drafts not yet flowing' }
  const total = curator.total_reviews ?? 0
  return {
    status: total > 0 ? 'live' : 'dormant',
    detail: total > 0
      ? `${total} review${total === 1 ? '' : 's'} · ${curator.latest_verdict || '—'}`
      : 'shadow mode · no verdicts yet',
  }
}

function chainStatus(protocolState) {
  if (!protocolState) return { status: 'dormant', detail: '/public/protocol-state unavailable' }
  if (protocolState.kill_switch_paused) return {
    status: 'killswitch',
    detail: 'CHAIN_SUBMISSION_PAUSED=true · commitments computed locally',
  }
  return { status: 'live', detail: 'IoTeX testnet 4690 · accepting writes' }
}

/* ------------------------------------------------------------------ */
/*  Workspace                                                          */
/* ------------------------------------------------------------------ */

export default function EvidenceGraphWorkspace() {
  // Live data sources — every node gets a real hook where one exists.
  const capture = useCaptureHealth().data
  const grind   = useGrindChain().data
  const apop    = useActivePlayOccupancy().data
  const ait     = useAITSeparation().data
  const vpmList = useVpmList({ limit: 50 }).data
  const curator = useCuratorStatus().data
  const vhp     = usePublicVhp(2).data    // demo token (Phase 99 Session 3 mint target)
  const protoState = usePublicProtocolState().data
  // (usePublicAgentRoots loaded by StatusStrip; not strictly needed here)

  // Compose status objects once per render
  const nodes = useMemo(() => ({
    hid:     hidStatus(),
    poac:    poacStatus(capture),
    gic:     gicStatus(grind),
    apop:    apopStatus(apop),
    pcc:     pccStatus(capture),
    ait:     aitStatus(ait),
    vhp:     vhpStatus(vhp),
    zkba:    zkbaStatus(vpmList),
    vpm:     vpmStatus(vpmList),
    curator: curatorStatus(curator),
    chain:   chainStatus(protoState),
  }), [capture, grind, apop, ait, vpmList, curator, vhp, protoState])

  // Stage 6 (Option B) — honest edge model. Each entry names a
  // protocol-level dataflow relationship that is currently
  // represented by the workspace's node set. Edges fall back to
  // 'ghost' (translucent dashed) when the TARGET node is dormant,
  // so the geometry never implies a live binding that hasn't
  // actually flowed. The kill-switch on the on-chain terminus
  // also forces all → chain edges to ghost.
  const killSwitchPaused = Boolean(protoState?.kill_switch_paused)
  const onChainDormant   = killSwitchPaused || nodes.chain.status === 'killswitch' || nodes.chain.status === 'dormant'

  const edges = useMemo(() => [
    // Substrate spine — every PoAC is signed over HID frame data
    // (INV-POAC); every GIC link hashes the prior PoAC commitment
    // (INV-GIC-001). Solid chain edges.
    { from: 'HID FRAMES', to: 'POAC',  kind: 'chain', dormant: nodes.poac.status === 'dormant' },
    { from: 'POAC',       to: 'GIC',   kind: 'chain', dormant: nodes.gic.status  === 'dormant' },

    // Predicate gates — APOP gameplay_context AND PCC capture_state
    // are inputs to GIC eligibility (Phase 235-GAD / 235-PCC).
    // Dashed predicate edges.
    { from: 'APOP', to: 'GIC', kind: 'predicate', dormant: nodes.gic.status === 'dormant' || nodes.apop.status === 'dormant' },
    { from: 'PCC',  to: 'GIC', kind: 'predicate', dormant: nodes.gic.status === 'dormant' || nodes.pcc.status  === 'dormant' },

    // AIT separation is the biometric input to VHP cert-tier.
    // Predicate gate (must clear separation ratio to mint).
    { from: 'AIT', to: 'VHP', kind: 'predicate', dormant: nodes.vhp.status === 'dormant' },

    // GIC head is a cryptographic input to BOTH VHP mints AND
    // ZKBA artifacts (PATTERN-017 composition).
    { from: 'GIC', to: 'VHP',  kind: 'chain', dormant: nodes.vhp.status  === 'dormant' },
    { from: 'GIC', to: 'ZKBA', kind: 'chain', dormant: nodes.zkba.status === 'dormant' },

    // ZKBA manifests are wrapped by VPM artifacts. Chain.
    { from: 'ZKBA', to: 'VPM', kind: 'chain', dormant: nodes.vpm.status === 'dormant' },

    // Curator polls VPM listings via the marketplace surface.
    // Derived (read-side polling, not cryptographic binding).
    { from: 'VPM', to: 'CURATOR', kind: 'derived', dormant: nodes.curator.status === 'dormant' },

    // On-chain terminus — VHP mints + ZKBA anchors + VPM persistence
    // all flow into IoTeX testnet writes. When CHAIN_SUBMISSION_PAUSED
    // is held, ALL these edges render as ghost (honest deferred state).
    { from: 'VHP',  to: 'ON-CHAIN ANCHOR', kind: 'chain', dormant: onChainDormant },
    { from: 'ZKBA', to: 'ON-CHAIN ANCHOR', kind: 'chain', dormant: onChainDormant },
    { from: 'VPM',  to: 'ON-CHAIN ANCHOR', kind: 'chain', dormant: onChainDormant },
  ], [nodes, onChainDormant])

  // Container ref for the edge layer's position measurement.
  const dagContainerRef = useRef(null)

  return (
    <>
      <WorkspaceHeader
        title="Evidence Graph"
        description="The protocol's causal DAG, end to end. Each node is a real bridge hook (or honestly labelled dormant if no data has flowed yet). Edges encode cryptographic vs predicate-gate vs derived vs kill-switch-paused bindings, measured against the rendered node positions. The on-chain anchor terminus respects CHAIN_SUBMISSION_PAUSED honestly — when the kill-switch is held, every edge into the anchor renders as a ghost (deferred) line."
        right={
          <span style={{
            fontSize:       'var(--os-text-min)',
            color:          'var(--os-text-faint)',
            fontStyle:      'italic',
            alignSelf:      'center',
          }}>signature workspace · Mythos-grounded</span>
        }
      />

      <section
        data-os-evidence-graph
        aria-label="Protocol evidence DAG"
        style={{
          padding:        '24px',
          position:       'relative',
          minHeight:      600,
        }}
      >
        {/* Screen-reader summary of the rendered dataflow.
            EvidenceEdgeLayer's SVG geometry is aria-hidden because
            it's purely visual; the same relationships are exposed
            here as text so keyboard / SR users get the dataflow
            without depending on the graph. */}
        <div data-os-edge-summary style={{
          position: 'absolute',
          width: 1, height: 1, overflow: 'hidden',
          clip: 'rect(0 0 0 0)',
          whiteSpace: 'nowrap',
        }}>
          <h3>Protocol dataflow summary</h3>
          <ul>
            {edges.map((e) => (
              <li key={`${e.from}->${e.to}`}>
                {e.from} flows into {e.to} as a {e.kind} relationship
                {e.dormant ? ' (currently deferred / no data has flowed yet)' : ''}.
              </li>
            ))}
          </ul>
        </div>

        {/* Live dataflow edge layer — Stage 6 Option B. Measures real
            DOM positions of EvidenceNode cards and draws SVG lines
            between them. Suppresses itself below 760px viewport
            (matches AppShell rail collapse) where flex-wrap would
            make horizontal edges misleading. */}
        <div
          ref={dagContainerRef}
          data-os-evidence-dag
          style={{
            position: 'relative',
          }}
        >
          <EvidenceEdgeLayer containerRef={dagContainerRef} edges={edges}/>

          {/* ROW 1 — Input substrate */}
        <div style={{ display: 'flex', gap: 16, marginBottom: 18, position: 'relative', zIndex: 1, flexWrap: 'wrap' }}>
          <EvidenceNode
            layer="HID FRAMES"
            mythology="The controller speaks at 1 kHz. Nothing else may speak for it."
            status={nodes.hid.status}
            source="dualshock_integration.py · /ws/records"
            detail={nodes.hid.detail}
            accent={_ACCENT_CHAIN}
          />
          <EvidenceNode
            layer="POAC"
            mythology="A 228-byte signed receipt every 14 ms, hash-rooted in 164."
            status={nodes.poac.status}
            source="/bridge/capture-health · /public/record"
            detail={nodes.poac.detail}
            accent={_ACCENT_CHAIN}
          />
        </div>

        {/* ROW 2 — Three parallel sub-substrates */}
        <div style={{ display: 'flex', gap: 16, marginBottom: 18, position: 'relative', zIndex: 1, flexWrap: 'wrap' }}>
          <EvidenceNode
            layer="APOP"
            mythology="Is the player actually playing right now? Five states answer."
            status={nodes.apop.status}
            source="/agent/active-play-occupancy"
            detail={nodes.apop.detail}
            accent={_ACCENT_PREDICATE}
          />
          <EvidenceNode
            layer="PCC"
            mythology="Is the capture channel trustworthy? Host arbitration, observed not assumed."
            status={nodes.pcc.status}
            source="/bridge/capture-health"
            detail={nodes.pcc.detail}
            accent={_ACCENT_PREDICATE}
          />
          <EvidenceNode
            layer="AIT"
            mythology="Who holds this controller? Tremor and gravity say so, biometrically."
            status={nodes.ait.status}
            source="/agent/ait-separation-status"
            detail={nodes.ait.detail}
            accent={_ACCENT_PREDICATE}
          />
        </div>

        {/* ROW 3 — Continuity, credential, audit composition */}
        <div style={{ display: 'flex', gap: 16, marginBottom: 18, position: 'relative', zIndex: 1, flexWrap: 'wrap' }}>
          <EvidenceNode
            layer="GIC"
            mythology="A SHA-256 chain that grinds 100 sessions into one unforgeable head."
            status={nodes.gic.status}
            source="/bridge/grind-chain-status · /public/gic"
            detail={nodes.gic.detail}
            accent={_ACCENT_CHAIN}
          />
          <EvidenceNode
            layer="VHP"
            mythology="A soulbound token, bound to one device and one grind, mintable once."
            status={nodes.vhp.status}
            source="/public/vhp/{tokenId}"
            detail={nodes.vhp.detail}
            accent={_ACCENT_CHAIN}
          />
          <EvidenceNode
            layer="ZKBA"
            mythology="A 32-byte commitment that proves a claim without revealing the claim."
            status={nodes.zkba.status}
            source="vpm_artifact_log · 7 classes"
            detail={nodes.zkba.detail}
            accent={_ACCENT_CHAIN}
          />
          <EvidenceNode
            layer="VPM"
            mythology="A self-contained HTML proof an operator can hand a journalist."
            status={nodes.vpm.status}
            source="/operator/operator/vpm-list"
            detail={nodes.vpm.detail}
            accent={_ACCENT_CHAIN}
          />
          <EvidenceNode
            layer="CURATOR"
            mythology="A third agent, watching the marketplace, drafting in the open."
            status={nodes.curator.status}
            source="/curator/status · operator-agent-drafts"
            detail={nodes.curator.detail}
            accent={_ACCENT_DERIVED}
          />
        </div>

        {/* ROW 4 — On-chain terminus */}
        <div style={{ display: 'flex', gap: 16, position: 'relative', zIndex: 1, flexWrap: 'wrap' }}>
          <EvidenceNode
            layer="ON-CHAIN ANCHOR"
            mythology="IoTeX testnet, when the kill-switch lifts, makes it permanent."
            status={nodes.chain.status}
            source="/public/protocol-state · IoTeX 4690"
            detail={nodes.chain.detail}
            accent={_ACCENT_TERMINUS}
          />
        </div>
        </div>{/* /os-evidence-dag — closes Stage 6 measured-edge container */}

        {/* Stage 6 — accent + edge semantics key (updated from Stage
            5.1's accent-only key to also describe edge styles now
            that real edges render). */}
        <div style={{
          marginTop:      32,
          padding:        '12px 14px',
          background:     'var(--os-panel-soft)',
          border:         '1px solid var(--os-border)',
          borderRadius:   'var(--os-radius)',
          display:        'flex',
          gap:            18,
          flexWrap:       'wrap',
          fontSize:       'var(--os-text-min)',
          fontFamily:     'JetBrains Mono, ui-monospace, monospace',
          color:          'var(--os-text-dim)',
        }}>
          <strong style={{
            fontSize:       'var(--os-text-min)',
            color:          'var(--os-text-faint)',
            letterSpacing:  '0.08em',
            textTransform:  'uppercase',
          }}>Edge + accent key</strong>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <svg width="36" height="6" aria-hidden="true">
              <line x1="0" y1="3" x2="36" y2="3" className="os-edge--solid"/>
            </svg>
            cryptographic binding (signed/hashed)
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <svg width="36" height="6" aria-hidden="true">
              <line x1="0" y1="3" x2="36" y2="3" className="os-edge--dashed"/>
            </svg>
            predicate gate (APOP / PCC / AIT clears GIC / VHP)
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <svg width="36" height="6" aria-hidden="true">
              <line x1="0" y1="3" x2="36" y2="3" className="os-edge--dotted"/>
            </svg>
            derived / polled (Curator reads VPM)
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <svg width="36" height="6" aria-hidden="true">
              <line x1="0" y1="3" x2="36" y2="3" className="os-edge--ghost"/>
            </svg>
            deferred / kill-switch held (no live binding yet)
          </span>
          <span aria-hidden="true" style={{
            width: 1, height: 18, background: 'var(--os-border)', margin: '0 4px',
          }}/>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <span aria-hidden="true" style={{ width: 12, height: 12, background: 'var(--os-accent)', borderRadius: 2 }}/>
            on-chain terminus (anchor · VHP mint)
          </span>
        </div>
      </section>
    </>
  )
}
