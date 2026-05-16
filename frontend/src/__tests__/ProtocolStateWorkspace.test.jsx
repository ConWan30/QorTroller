/**
 * Phase O5-EVIDENCE-OS Stage 5 — Protocol State workspace tests
 *
 *   T-OS-PROT-1  posture LIVE when kill-switch open + no errors
 *   T-OS-PROT-2  posture PAUSED when kill_switch_paused=true
 *   T-OS-PROT-3  posture MOCK when isMockActive=true
 *   T-OS-PROT-4  posture OFFLINE when public state errors
 *   T-OS-PROT-5  separation-ratio probes render CLEARED when ≥1.0
 *                AND BELOW 1.0 otherwise
 *   T-OS-PROT-6  operator detail surfaces invariant gate failures
 *                when authenticated
 *   T-OS-PROT-7  operator detail HONEST unavailable state when
 *                bridge offline (no fabrication)
 *   T-OS-PROT-8  fleet coherence rows surface contradictions /
 *                orphans / inversions counts
 *   T-OS-PROT-9  accessibility — semantic roles + aria-labels
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

let _state           = null
let _stateError      = null
let _stateLoading    = false
let _roots           = null
let _rootsError      = null
let _fleetData       = null
let _fleetError      = false
let _invData         = null
let _invError        = false
let _isMock          = false

vi.mock('../api/publicForensic', () => ({
  usePublicProtocolState: () => ({
    data: _state, error: _stateError, isLoading: _stateLoading,
  }),
  usePublicAgentRoots:    () => ({ data: _roots, error: _rootsError }),
}))

vi.mock('../api/bridgeApi', () => ({
  useFleetCoherenceStatus: () => ({ data: _fleetData, isError: _fleetError }),
  useInvariantGateStatus:  () => ({ data: _invData,   isError: _invError }),
}))

vi.mock('../api/mockBridge', () => ({
  isMockActive:  () => _isMock,
  deactivateMock: () => {},
}))

import ProtocolStateWorkspace from '../os/workspaces/ProtocolStateWorkspace'

function reset() {
  _state = {
    kill_switch_paused: true,
    pv_ci_invariants_count: 122,
    fleet_phase_aligned: false,
    separation_ratios: {
      touchpad_corners: 0.728,
      tremor_resting:   1.177,
      ait:              1.199,
    },
    total_vpm_artifacts:     14,
    total_mlga_sessions:     2,
    total_grind_chain_links: 100,
    timestamp: Date.now() / 1000,
  }
  _stateError   = null
  _stateLoading = false
  _roots = {
    chain: { name: 'IoTeX', chain_id: 4690, network: 'testnet' },
    agents: [
      { canonical_name: 'sentry',   agent_id: '0xb21e1ec2cafef00d11', current_phase: 'O1_SHADOW', scope_root: '0xebe899279b' },
      { canonical_name: 'guardian', agent_id: '0xbd8c7fba00112233',   current_phase: 'O1_SHADOW' },
      { canonical_name: 'curator',  agent_id: '0xed6a2df5deadbeef',   current_phase: 'O1_SHADOW' },
    ],
  }
  _rootsError = null
  _fleetData  = null
  _fleetError = false
  _invData    = null
  _invError   = false
  _isMock     = false
}

function renderWorkspace() {
  const qc = new QueryClient()
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Routes>
          <Route path="/" element={<ProtocolStateWorkspace />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(reset)

describe('ProtocolStateWorkspace', () => {

  it('T-OS-PROT-1: posture LIVE when kill-switch open + no errors', () => {
    _state.kill_switch_paused = false
    const { container } = renderWorkspace()
    // Posture badge label uses the LIVE token (DataBadge data attr)
    const badges = container.querySelectorAll('[data-os-badge="live"]')
    expect(badges.length).toBeGreaterThan(0)
    // Kill-switch row reads OPEN (semantic state — surface text)
    expect(container.textContent).toMatch(/OPEN/)
  })

  it('T-OS-PROT-2: posture PAUSED when kill_switch_paused=true', () => {
    const { container } = renderWorkspace()
    // killswitch-status badge present (DataBadge contract)
    expect(container.querySelector('[data-os-badge="killswitch"]')).not.toBeNull()
    // Kill-switch hint surfaces "No chain writes occur"
    expect(container.textContent).toMatch(/No chain writes occur/i)
  })

  it('T-OS-PROT-3: posture MOCK when isMockActive', () => {
    _isMock = true
    const { container } = renderWorkspace()
    // mock-status badge present
    expect(container.querySelector('[data-os-badge="mock"]')).not.toBeNull()
    // Operator detail explicitly unavailable when mock
    expect(container.querySelector('[data-os-operator-detail="unavailable"]')).not.toBeNull()
    expect(container.textContent).toMatch(/mock mode active/i)
  })

  it('T-OS-PROT-4: posture OFFLINE when public state errors', () => {
    _state = null
    _stateError = new Error('bridge unreachable')
    _stateLoading = false
    const { container } = renderWorkspace()
    // blocked status badge present (DataBadge OFFLINE label maps to blocked status)
    expect(container.querySelector('[data-os-badge="blocked"]')).not.toBeNull()
    // OFFLINE label text appears somewhere in DOM
    expect(container.textContent.includes('OFFLINE')).toBe(true)
  })

  it('T-OS-PROT-5: separation-ratio probes render CLEARED ≥1.0 and BELOW 1.0 otherwise', () => {
    const { container, getAllByText } = renderWorkspace()
    // tremor_resting (1.177) AND ait (1.199) both ≥ 1.0 → CLEARED
    const cleared = getAllByText('CLEARED')
    expect(cleared.length).toBeGreaterThanOrEqual(2)
    // touchpad_corners (0.728) < 1.0 → BELOW 1.0
    const below = getAllByText('BELOW 1.0')
    expect(below.length).toBeGreaterThanOrEqual(1)
    // Each probe has a role=meter for screen readers
    const meters = container.querySelectorAll('[role="meter"]')
    expect(meters.length).toBe(3)
  })

  it('T-OS-PROT-6: operator detail surfaces invariant gate failures', () => {
    _invData = {
      gate_pass: false,
      total_checked: 122,
      last_failures: [
        { id: 'INV-PV-CI-001', reason: 'allowlist sha drift' },
        { id: 'INV-VPM-001',   reason: 'compiler region mutated' },
      ],
      last_run_ts: Math.floor(Date.now() / 1000),
    }
    const { container } = renderWorkspace()
    expect(container.querySelector('[data-os-operator-detail="available"]')).not.toBeNull()
    expect(container.textContent).toMatch(/FAILING/)
    expect(container.textContent).toMatch(/INV-PV-CI-001/)
    expect(container.textContent).toMatch(/INV-VPM-001/)
    expect(container.textContent).toMatch(/STOP protocol-altering work/i)
  })

  it('T-OS-PROT-7: operator detail HONEST unavailable when bridge offline', () => {
    _fleetError = true
    _invError   = true
    const { container } = renderWorkspace()
    const unavailable = container.querySelector('[data-os-operator-detail="unavailable"]')
    expect(unavailable).not.toBeNull()
    expect(container.textContent).toMatch(/Operator endpoint returned an error/i)
    // Public posture remains trustworthy
    expect(container.textContent).toMatch(/public posture above remains the trustworthy baseline/i)
    // No fabricated coherence numbers
    expect(container.querySelector('[data-os-operator-detail="available"]')).toBeNull()
  })

  it('T-OS-PROT-8: fleet coherence rows surface contradictions / orphans / inversions', () => {
    _fleetData = {
      active_contradictions: 1,
      active_orphans: 2,
      active_inversions: 0,
    }
    _invData = { gate_pass: true, total_checked: 122, last_failures: [] }
    const { container } = renderWorkspace()
    expect(container.querySelector('[data-os-operator-detail="available"]')).not.toBeNull()
    // Each axis surfaced as its own row with a label
    expect(container.textContent).toMatch(/CONTRADICTIONS/)
    expect(container.textContent).toMatch(/ORPHANS/)
    expect(container.textContent).toMatch(/INVERSIONS/)
  })

  it('T-OS-PROT-9: semantic roles + aria-labels present', () => {
    const { container } = renderWorkspace()
    // Four regions: Posture, Measurement, Identity, Operator Detail
    const regions = container.querySelectorAll('[role="region"]')
    expect(regions.length).toBeGreaterThanOrEqual(4)
    // Each separation-ratio probe is a role=meter with aria-label
    const meters = container.querySelectorAll('[role="meter"]')
    meters.forEach(m => {
      expect(m.getAttribute('aria-label')).toMatch(/separation ratio/i)
    })
    // Status badges carry role=status (DataBadge contract)
    const badges = container.querySelectorAll('[data-os-badge]')
    expect(badges.length).toBeGreaterThan(0)
  })
})
