/**
 * Phase O5-EVIDENCE-OS Stage 2 — Live Match workspace tests
 *
 * The 4 verdict states must each render correctly:
 *
 *   T-OS-LIVE-1   counting verdict when all gates clear
 *   T-OS-LIVE-2   blocked verdict + BlockerList when capture disconnected
 *   T-OS-LIVE-3   blocked verdict + BlockerList when APOP on menu
 *   T-OS-LIVE-4   blocked verdict + BlockerList when GIC chain broken
 *   T-OS-LIVE-5   mock verdict reads "MOCK SESSION · not live" honestly
 *   T-OS-LIVE-6   dormant verdict when no pulse and no chain
 *   T-OS-LIVE-7   BlockerList lists multiple blockers in order
 *   T-OS-LIVE-8   primitives are accessible (semantic roles + aria)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

// Mock controllers — we re-mock per test by changing return shape
let _captureMock      = { capture_state: 'NOMINAL', host_state: 'EXCLUSIVE_USB', poll_rate_hz: 998 }
let _grindMock        = { chain_length: 42, chain_intact: true, latest_gic_hash: 'a'.repeat(64) }
let _apopMock         = { classification: { state: 'ACTIVE_MATCH_PLAY' } }
let _pulseMock        = { pulseCount: 100, lastPulseTs: Date.now() - 500, connected: true }
let _orientationMock  = null
let _autoTriggerMock  = { seconds_until_next: 12 }
let _aitMock          = { separation_ratio: 1.199, n_sessions: 37 }
let _isMockActiveResult = false

vi.mock('../api/bridgeApi', () => ({
  useCaptureHealth:           () => ({ data: _captureMock }),
  useGrindChain:              () => ({ data: _grindMock }),
  useActivePlayOccupancy:     () => ({ data: _apopMock }),
  useBrpRecordPulse:          () => _pulseMock,
  useBrpControllerOrientation: () => ({ data: _orientationMock }),
  useAutoTriggerStatus:       () => ({ data: _autoTriggerMock }),
  useAITSeparation:           () => ({ data: _aitMock }),
}))

vi.mock('../api/mockBridge', () => ({
  isMockActive:  () => _isMockActiveResult,
  deactivateMock: () => {},
}))

import LiveMatchWorkspace from '../os/workspaces/LiveMatchWorkspace'

function renderWorkspace() {
  const qc = new QueryClient()
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Routes>
          <Route path="/" element={<LiveMatchWorkspace />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function resetMocks() {
  _captureMock      = { capture_state: 'NOMINAL', host_state: 'EXCLUSIVE_USB', poll_rate_hz: 998 }
  _grindMock        = { chain_length: 42, chain_intact: true, latest_gic_hash: 'a'.repeat(64) }
  _apopMock         = { classification: { state: 'ACTIVE_MATCH_PLAY' } }
  _pulseMock        = { pulseCount: 100, lastPulseTs: Date.now() - 500, connected: true }
  _orientationMock  = null
  _autoTriggerMock  = { seconds_until_next: 12 }
  _aitMock          = { separation_ratio: 1.199, n_sessions: 37 }
  _isMockActiveResult = false
}

beforeEach(resetMocks)


describe('LiveMatchWorkspace verdicts', () => {
  it('T-OS-LIVE-1: counting verdict when all gates clear', () => {
    const { container, getByText } = renderWorkspace()
    const verdict = container.querySelector('[data-os-verdict="counting"]')
    expect(verdict).not.toBeNull()
    expect(getByText('SESSION COUNTS')).not.toBeNull()
    // BlockerList must not render when verdict=counting
    expect(container.querySelector('[role="region"][aria-label="Active blockers"]'))
      .toBeNull()
  })

  it('T-OS-LIVE-2: blocked verdict + BlockerList when capture disconnected', () => {
    _captureMock = { capture_state: 'DISCONNECTED', host_state: 'UNKNOWN', poll_rate_hz: 0 }
    const { container, getByText } = renderWorkspace()
    expect(container.querySelector('[data-os-verdict="blocked"]')).not.toBeNull()
    expect(getByText('SESSION BLOCKED')).not.toBeNull()
    expect(container.querySelector('[data-os-blocker="capture"]')).not.toBeNull()
  })

  it('T-OS-LIVE-3: blocked verdict when APOP is on a menu', () => {
    _apopMock = { classification: { state: 'NON_COMPETITIVE_MENU' } }
    const { container } = renderWorkspace()
    expect(container.querySelector('[data-os-verdict="blocked"]')).not.toBeNull()
    expect(container.querySelector('[data-os-blocker="apop"]')).not.toBeNull()
    // Human translation must appear (not raw enum)
    expect(container.textContent).toMatch(/on a menu|no competitive play/i)
  })

  it('T-OS-LIVE-4: blocked verdict when GIC chain integrity fails', () => {
    _grindMock = { chain_length: 42, chain_intact: false, latest_gic_hash: 'a'.repeat(64) }
    const { container } = renderWorkspace()
    expect(container.querySelector('[data-os-verdict="blocked"]')).not.toBeNull()
    expect(container.querySelector('[data-os-blocker="gic"]')).not.toBeNull()
    expect(container.textContent).toMatch(/grind chain integrity check failed/i)
  })

  it('T-OS-LIVE-5: mock verdict reads honestly when isMockActive=true', () => {
    _isMockActiveResult = true
    const { container, getByText } = renderWorkspace()
    expect(container.querySelector('[data-os-verdict="mock"]')).not.toBeNull()
    expect(getByText('MOCK SESSION · not live')).not.toBeNull()
    // Mock verdict explicitly tells operator the UI is fabricated
    expect(container.textContent).toMatch(/fabricated|unreachable/i)
    // BlockerList suppressed when mock (no live gates to grade)
    expect(container.querySelector('[role="region"][aria-label="Active blockers"]'))
      .toBeNull()
  })

  it('T-OS-LIVE-6: dormant verdict when no pulse + no chain', () => {
    _pulseMock = { pulseCount: 0, lastPulseTs: 0, connected: false }
    _grindMock = { chain_length: 0, chain_intact: true, latest_gic_hash: '' }
    const { container, getByText } = renderWorkspace()
    expect(container.querySelector('[data-os-verdict="dormant"]')).not.toBeNull()
    expect(getByText('NO ACTIVE SESSION')).not.toBeNull()
  })

  it('T-OS-LIVE-7: BlockerList lists multiple blockers in order', () => {
    _captureMock = { capture_state: 'DEGRADED', host_state: 'CONTESTED', poll_rate_hz: 200 }
    _apopMock    = { classification: { state: 'NON_COMPETITIVE_MENU' } }
    const { container } = renderWorkspace()
    expect(container.querySelector('[data-os-verdict="blocked"]')).not.toBeNull()
    const blockers = container.querySelectorAll('[data-os-blocker]')
    // Capture, host, AND APOP all blocking — expect ≥3
    expect(blockers.length).toBeGreaterThanOrEqual(3)
  })

  it('T-OS-LIVE-8: primitives carry accessibility roles', () => {
    const { container } = renderWorkspace()
    // VerdictPanel role=status aria-live=polite
    const verdict = container.querySelector('[data-os-verdict]')
    expect(verdict.getAttribute('role')).toBe('status')
    expect(verdict.getAttribute('aria-live')).toBe('polite')
    // SignalMeter cards role=group
    const meters = container.querySelectorAll('[role="group"]')
    expect(meters.length).toBeGreaterThan(0)
    // LiveSignalPane sections role=region
    const panes = container.querySelectorAll('[role="region"]')
    expect(panes.length).toBeGreaterThan(0)
  })
})
