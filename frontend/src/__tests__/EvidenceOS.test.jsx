/**
 * Phase O5-EVIDENCE-OS Stage 1 — vertical slice tests.
 *
 * T-OS-SHELL-1   AppShell renders the 5 workspace nav links + 3 legacy links
 * T-OS-SHELL-2   /os index redirects to /os/evidence (signature workspace)
 * T-OS-SHELL-3   StatusStrip renders bridge state + kill-switch + agent count
 * T-OS-EVID-1    EvidenceGraphWorkspace renders all 11 named DAG nodes
 * T-OS-EVID-2    Every node carries a mythology one-liner (not empty)
 * T-OS-EVID-3    Edge legend renders all 4 semantic kinds
 * T-OS-NODE-1    EvidenceNode is rendered as <article> when non-interactive
 * T-OS-NODE-2    EvidenceNode is rendered as <button> when onClickAction set
 * T-OS-BADGE-1   DataBadge has role=status and aria-label
 * T-OS-PLACE-1   LiveMatch / Queue / Replay show EmptyState with source
 */
import { describe, it, expect, vi } from 'vitest'
import { render } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route, Navigate } from 'react-router-dom'

import AppShell                 from '../os/AppShell'
import EvidenceGraphWorkspace   from '../os/workspaces/EvidenceGraphWorkspace'
import LiveMatchWorkspace       from '../os/workspaces/LiveMatchWorkspace'
import OperatorQueueWorkspace   from '../os/workspaces/OperatorQueueWorkspace'
import ForensicReplayWorkspace  from '../os/workspaces/ForensicReplayWorkspace'
import ProtocolStateWorkspace   from '../os/workspaces/ProtocolStateWorkspace'
import EvidenceNode             from '../os/components/EvidenceNode'
import DataBadge                from '../os/components/DataBadge'

// Mock all bridge + public hooks used by the workspaces. We're testing
// shell behavior + render shape, not data flow.
vi.mock('../api/publicForensic', () => ({
  usePublicProtocolState: () => ({ data: {
    pv_ci_invariants_count: 122,
    total_vpm_artifacts: 14,
    total_mlga_sessions: 11,
    total_grind_chain_links: 100,
    kill_switch_paused: true,
  }, error: null }),
  usePublicAgentRoots: () => ({ data: {
    agents: [
      { canonical: 'anchor_sentry', phase: 'O1_SHADOW', cedar_bundle_merkle: '0xabc'.repeat(11) },
      { canonical: 'guardian',      phase: 'O1_SHADOW', cedar_bundle_merkle: '0xdef'.repeat(11) },
      { canonical: 'curator',       phase: 'O1_SHADOW', cedar_bundle_merkle: '0x123'.repeat(11) },
    ],
    chain: { name: 'IoTeX', chain_id: 4690, network: 'testnet' },
  }, error: null }),
  usePublicVhp: () => ({ data: null, error: null }),
}))

vi.mock('../api/bridgeApi', () => ({
  useCaptureHealth: () => ({ data: { capture_state: 'NOMINAL', host_state: 'EXCLUSIVE_USB', poll_rate_hz: 998 } }),
  useGrindChain:    () => ({ data: { chain_length: 100, chain_intact: true, latest_gic_hash: '0e9d453d904220148d632e75802b71bdff74c7197aa8afcbfec5d36a61ab48da' } }),
  useActivePlayOccupancy: () => ({ data: { state: 'ACTIVE_MATCH_PLAY', classification: { state: 'ACTIVE_MATCH_PLAY' } } }),
  useAITSeparation:       () => ({ data: { separation_ratio: 1.199, n_sessions: 37 } }),
  useVpmList:             () => ({ data: { row_count: 14, rows: [{ zkba_class: 2 }, { zkba_class: 7 }] } }),
  useCuratorStatus:       () => ({ data: { total_reviews: 0 } }),
  useBrpRecordPulse:           () => ({ pulseCount: 0, lastPulseTs: 0, connected: false }),
  useBrpControllerOrientation: () => ({ data: null }),
  useAutoTriggerStatus:        () => ({ data: null }),
  // Stage 3 — Operator Queue dependencies
  useOperatorDrafts:           () => ({ data: { drafts: [], row_count: 0 }, isError: false }),
  useReviewDraft:              () => ({ mutate: () => {}, isPending: false, error: null }),
  useCuratorFlaggedListings:   () => ({ data: { listings: [], total: 0 }, isError: false }),
  useDriftLog:                 () => ({ data: { findings: [] }, isError: false }),
  useFleetReadinessRoot:       () => ({ data: { per_agent: [] }, isError: false }),
  useInvariantGateStatus:      () => ({ data: { gate_pass: true, total_checked: 122, last_failures: [] }, isError: false }),
  useFleetCoherenceStatus:     () => ({ data: { by_mode: { CONTRADICTION: 0, ORPHAN: 0, INVERSION: 0 } }, isError: false }),
}))

vi.mock('../api/mockBridge', () => ({
  isMockActive:  () => false,
  deactivateMock: () => {},
}))


function renderRoute(initialPath) {
  const qc = new QueryClient()
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/os" element={<AppShell />}>
            <Route index element={<Navigate to="evidence" replace />} />
            <Route path="live"     element={<LiveMatchWorkspace />} />
            <Route path="evidence" element={<EvidenceGraphWorkspace />} />
            <Route path="queue"    element={<OperatorQueueWorkspace />} />
            <Route path="replay"   element={<ForensicReplayWorkspace />} />
            <Route path="protocol" element={<ProtocolStateWorkspace />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Evidence OS AppShell', () => {
  it('T-OS-SHELL-1: renders 5 workspace nav links + 3 legacy links', () => {
    const { container } = renderRoute('/os/evidence')
    // Five workspace nav-link data attrs (scoped to nav, not workspace body)
    const navLinks = container.querySelectorAll('[data-os-nav-link]')
    expect(navLinks.length).toBe(5)
    // Each nav link includes the workspace label
    const navText = Array.from(navLinks).map(n => n.textContent).join(' | ')
    for (const label of ['Live Match', 'Evidence Graph', 'Operator Queue', 'Forensic Replay', 'Protocol State']) {
      expect(navText, `nav missing: ${label}`).toContain(label)
    }
    // Three legacy links appear in the nav region
    const nav = container.querySelector('nav[aria-label="Evidence OS workspaces"]')
    expect(nav).not.toBeNull()
    expect(nav.textContent).toContain('Classic Operator Cockpit')
    expect(nav.textContent).toContain('Public Forensic Explorer')
    expect(nav.textContent).toContain('Algorithm Catalog')
  })

  it('T-OS-SHELL-2: /os index redirects to /os/evidence', () => {
    const { container } = renderRoute('/os')
    // After redirect, the active workspace MUST be Evidence Graph
    expect(container.querySelector('[data-os-evidence-graph]')).not.toBeNull()
  })

  it('T-OS-SHELL-3: StatusStrip surfaces bridge + kill-switch + agent count', () => {
    const { getByText } = renderRoute('/os/evidence')
    expect(getByText('BRIDGE LIVE')).not.toBeNull()
    expect(getByText('KILL-SWITCH PAUSED')).not.toBeNull()
    // 3 agents from mocked usePublicAgentRoots
    expect(getByText('Agents')).not.toBeNull()
    // PV-CI metric from protocol state
    expect(getByText('PV-CI')).not.toBeNull()
  })
})

describe('EvidenceGraphWorkspace', () => {
  it('T-OS-EVID-1: renders all 11 named DAG nodes', () => {
    const { container } = renderRoute('/os/evidence')
    const layerLabels = ['HID FRAMES', 'POAC', 'APOP', 'PCC', 'AIT', 'GIC', 'VHP', 'ZKBA', 'VPM', 'CURATOR', 'ON-CHAIN ANCHOR']
    for (const label of layerLabels) {
      const node = container.querySelector(`[data-os-evidence-node="${label}"]`)
      expect(node, `node missing: ${label}`).not.toBeNull()
    }
  })

  it('T-OS-EVID-2: every node carries a mythology one-liner', () => {
    const { container } = renderRoute('/os/evidence')
    const nodes = container.querySelectorAll('[data-os-evidence-node]')
    expect(nodes.length).toBe(11)
    for (const node of nodes) {
      // Mythology line lives in the second flex child (div after header).
      // Just assert non-empty text content beyond the layer label.
      const text = node.textContent || ''
      expect(text.length).toBeGreaterThan(40)
    }
  })

  it('T-OS-EVID-3: accent key includes all 4 semantic kinds', () => {
    // Stage 5.1 (Mythos audit H1): the prior "edge legend" promised
    // line types that never rendered; replaced with node-accent
    // semantics key. Documentation must match what's rendered.
    const { getByText } = renderRoute('/os/evidence')
    expect(getByText(/cryptographic substrate/i)).not.toBeNull()
    expect(getByText(/derived \/ polled/i)).not.toBeNull()
    expect(getByText(/predicate gate/i)).not.toBeNull()
    expect(getByText(/on-chain terminus/i)).not.toBeNull()
  })
})

describe('EvidenceNode semantics', () => {
  it('T-OS-NODE-1: renders as <article> when non-interactive', () => {
    const { container } = render(
      <EvidenceNode layer="TEST" mythology="testing mythology" status="live" source="test" />,
    )
    const node = container.querySelector('[data-os-evidence-node="TEST"]')
    expect(node).not.toBeNull()
    expect(node.tagName.toLowerCase()).toBe('article')
  })

  it('T-OS-NODE-2: renders as <button> when onClickAction provided', () => {
    const { container } = render(
      <EvidenceNode layer="TEST2" mythology="m" status="live" onClickAction={() => {}} />,
    )
    const node = container.querySelector('[data-os-evidence-node="TEST2"]')
    expect(node.tagName.toLowerCase()).toBe('button')
  })
})

describe('DataBadge accessibility', () => {
  it('T-OS-BADGE-1: has role=status + aria-label', () => {
    const { container } = render(<DataBadge status="verified" />)
    const badge = container.querySelector('[data-os-badge="verified"]')
    expect(badge).not.toBeNull()
    expect(badge.getAttribute('role')).toBe('status')
    expect(badge.getAttribute('aria-label')).toMatch(/verified/i)
  })
})

describe('All 5 OS workspaces shipped', () => {
  // Stage 2: /os/live. Stage 3: /os/queue. Stage 4: /os/replay.
  // None remain placeholder. Only /os/protocol still uses the original
  // Stage 1 LIVE metrics shape (no further work pending).
  it('T-OS-WS-1: /os/live renders the live verdict (Stage 2)', () => {
    const { container } = renderRoute('/os/live')
    expect(container.querySelector('[data-os-verdict]')).not.toBeNull()
  })

  it('T-OS-WS-2: /os/queue renders the queue summary (Stage 3)', () => {
    const { container } = renderRoute('/os/queue')
    expect(container.querySelector('[aria-label="Queue summary"]')).not.toBeNull()
  })

  it('T-OS-WS-3: /os/replay renders ReplaySearch + ReplayModeTabs (Stage 4)', () => {
    const { container } = renderRoute('/os/replay')
    expect(container.querySelector('form[role="search"]')).not.toBeNull()
    expect(container.querySelector('[role="tablist"]')).not.toBeNull()
  })
})
