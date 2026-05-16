/**
 * Evidence OS Stage 3 — Operator Queue tests
 *
 * Required by operator brief:
 *   T-OS-QUEUE-1   pending draft appears with enabled review action when live
 *   T-OS-QUEUE-2   mock/offline disables write actions
 *   T-OS-QUEUE-3   invariant gate failure disables sensitive actions
 *   T-OS-QUEUE-4   curator flags render with recommended actions
 *   T-OS-QUEUE-5   empty queue is honest (no false "all clear")
 *   T-OS-QUEUE-6   drift findings render with their own severity
 *   T-OS-QUEUE-7   invariant-fail item itself surfaces as CRITICAL queue row
 *   T-OS-QUEUE-8   accessibility — semantic roles + aria-labels
 *   T-OS-QUEUE-9   destructive review needs two-click confirm
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, act, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

let _drafts          = { drafts: [], row_count: 0 }
let _draftsError     = null
let _curator         = { total_reviews: 0 }
let _flagged         = { listings: [], total: 0 }
let _drift           = { findings: [] }
let _frr             = { per_agent: [] }
let _invGate         = { gate_pass: true, total_checked: 122, last_failures: [] }
let _coherence       = { by_mode: { CONTRADICTION: 0, ORPHAN: 0, INVERSION: 0 } }
let _isMock          = false
let _reviewMutateFn  = vi.fn()
let _reviewIsPending = false
let _reviewError     = null

vi.mock('../api/bridgeApi', () => ({
  useOperatorDrafts:        () => ({ data: _drafts, isError: Boolean(_draftsError) }),
  useReviewDraft:           () => ({
    mutate: (args, opts) => { _reviewMutateFn(args); opts?.onSuccess?.() },
    isPending: _reviewIsPending,
    error: _reviewError,
  }),
  useCuratorStatus:         () => ({ data: _curator, isError: false }),
  useCuratorFlaggedListings: () => ({ data: _flagged, isError: false }),
  useDriftLog:              () => ({ data: _drift,   isError: false }),
  useFleetReadinessRoot:    () => ({ data: _frr,     isError: false }),
  useInvariantGateStatus:   () => ({ data: _invGate, isError: false }),
  useFleetCoherenceStatus:  () => ({ data: _coherence, isError: false }),
}))

vi.mock('../api/mockBridge', () => ({
  isMockActive:  () => _isMock,
  deactivateMock: () => {},
}))

import OperatorQueueWorkspace from '../os/workspaces/OperatorQueueWorkspace'

function reset() {
  _drafts = { drafts: [], row_count: 0 }
  _draftsError = null
  _curator = { total_reviews: 0 }
  _flagged = { listings: [], total: 0 }
  _drift = { findings: [] }
  _frr = { per_agent: [] }
  _invGate = { gate_pass: true, total_checked: 122, last_failures: [] }
  _coherence = { by_mode: { CONTRADICTION: 0, ORPHAN: 0, INVERSION: 0 } }
  _isMock = false
  _reviewMutateFn = vi.fn()
  _reviewIsPending = false
  _reviewError = null
}

function renderWorkspace() {
  const qc = new QueryClient()
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Routes>
          <Route path="/" element={<OperatorQueueWorkspace />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(reset)


describe('OperatorQueueWorkspace', () => {

  it('T-OS-QUEUE-1: pending draft renders with enabled Review action when live', () => {
    _drafts = {
      drafts: [{
        id: 42,
        agent_id: '0xb21e1ec2cafe',
        action_name: 'kms-sign',
        action_category: 'tool',
        payload_hash: 'abc'.repeat(20).slice(0, 64),
        created_at: new Date().toISOString(),
      }],
      row_count: 1,
    }
    const { container, getByText } = renderWorkspace()
    expect(container.querySelector('[data-os-queue-item="draft"]')).not.toBeNull()
    // The Review action button must be enabled (not an ActionGuardBadge)
    const reviewBtn = getByText('Review').closest('button')
    expect(reviewBtn).not.toBeNull()
    expect(reviewBtn.disabled).toBe(false)
    expect(container.querySelector('[data-os-guard="mock-active"]')).toBeNull()
  })

  it('T-OS-QUEUE-2: mock/offline disables write actions', () => {
    _isMock = true
    _drafts = {
      drafts: [{
        id: 99, agent_id: '0xguardian', action_name: 'audit-drafting',
        created_at: new Date().toISOString(),
      }],
      row_count: 1,
    }
    const { container, getAllByText } = renderWorkspace()
    // Review action replaced by ActionGuardBadge
    expect(container.querySelector('[data-os-guard="mock-active"]')).not.toBeNull()
    // Header warning visible (case-insensitive search)
    expect(getAllByText(/MOCK ACTIVE — WRITES DISABLED/i).length).toBeGreaterThan(0)
  })

  it('T-OS-QUEUE-3: invariant gate failure disables sensitive actions', () => {
    _invGate = {
      gate_pass: false,
      total_checked: 122,
      last_failures: [{ id: 'INV-OPERATOR-AGENT-001', reason: 'pattern not found' }],
      last_run_ts: Math.floor(Date.now() / 1000),
    }
    _drafts = {
      drafts: [{
        id: 7, agent_id: '0xsentry', action_name: 'kms-sign',
        created_at: new Date().toISOString(),
      }],
      row_count: 1,
    }
    const { container } = renderWorkspace()
    // Drafts still appear, but their action is replaced by ActionGuardBadge
    expect(container.querySelector('[data-os-queue-item="draft"]')).not.toBeNull()
    expect(container.querySelector('[data-os-guard="invariant-failing"]')).not.toBeNull()
    // The invariant-fail item itself is in the queue and CRITICAL
    expect(container.querySelector('[data-os-queue-item="invariant-fail"]')).not.toBeNull()
    expect(container.querySelector('[data-os-queue-item="invariant-fail"][data-os-severity="critical"]')).not.toBeNull()
  })

  it('T-OS-QUEUE-4: curator flags render with recommended actions', () => {
    _flagged = {
      listings: [{
        listing_commitment: 'deadbeef'.repeat(8),
        verdict: 'FLAGGED_TIER_MISMATCH',
        severity: 'HIGH',
        reason_detail: 'Listing claims tier 3 but anchor freshness < 24h',
        created_at: new Date(Date.now() - 600_000).toISOString(),
      }],
      total: 1,
    }
    const { container } = renderWorkspace()
    const row = container.querySelector('[data-os-queue-item="curator"]')
    expect(row).not.toBeNull()
    // Critical severity (HIGH → critical)
    expect(row.getAttribute('data-os-severity')).toBe('critical')
    // Recommended action text present
    expect(row.textContent).toMatch(/recommended:/i)
    expect(row.textContent).toMatch(/marketplace|review/i)
  })

  it('T-OS-QUEUE-5: empty queue is honest (no false "all clear")', () => {
    const { container } = renderWorkspace()
    // EmptyState is rendered
    expect(container.querySelector('[role="region"]')).not.toBeNull()
    // Honest copy — uses "quiet" not "all-clear"
    expect(container.textContent).toMatch(/0 items in window/i)
    expect(container.textContent).toMatch(/honest|quiet|verify/i)
    expect(container.textContent).not.toMatch(/all clear|all-clear/i)
  })

  it('T-OS-QUEUE-6: drift findings render with their own severity', () => {
    _drift = {
      findings: [{
        id: 1,
        drift_type: 'SCOPE_HASH_GOVERNANCE_DRIFT',
        agent_id: '0xsentry',
        expected_value: 'a'.repeat(64),
        actual_value:   'b'.repeat(64),
        created_at: new Date().toISOString(),
      }, {
        id: 2,
        drift_type: 'BUNDLE_HASH_DRIFT',
        agent_id: '0xguardian',
        expected_value: 'c'.repeat(64),
        actual_value:   'd'.repeat(64),
        created_at: new Date().toISOString(),
      }],
    }
    const { container } = renderWorkspace()
    const driftRows = container.querySelectorAll('[data-os-queue-item="drift"]')
    expect(driftRows.length).toBe(2)
    // Governance drift is CRITICAL; bundle drift is WARN
    const sevs = Array.from(driftRows).map(r => r.getAttribute('data-os-severity'))
    expect(sevs).toContain('critical')
    expect(sevs).toContain('warn')
  })

  it('T-OS-QUEUE-7: invariant-fail item itself surfaces as CRITICAL queue row', () => {
    _invGate = {
      gate_pass: false,
      total_checked: 122,
      last_failures: [{ id: 'INV-PV-CI-001', reason: 'allowlist drift' }],
      last_run_ts: Math.floor(Date.now() / 1000),
    }
    const { container } = renderWorkspace()
    const invRow = container.querySelector('[data-os-queue-item="invariant-fail"]')
    expect(invRow).not.toBeNull()
    expect(invRow.getAttribute('data-os-severity')).toBe('critical')
    // Recommendation surfaces the safe-action: STOP
    expect(invRow.textContent).toMatch(/STOP|vapi_invariant_gate/i)
  })

  it('T-OS-QUEUE-8: semantic roles + aria-labels present', () => {
    _drafts = { drafts: [{ id: 1, agent_id: '0xsentry', action_name: 'kms-sign', created_at: new Date().toISOString() }], row_count: 1 }
    const { container } = renderWorkspace()
    // Summary tiles use role=group
    const groups = container.querySelectorAll('[role="group"]')
    expect(groups.length).toBeGreaterThan(0)
    // Summary section is a region with aria-label
    const region = container.querySelector('[aria-label="Queue summary"]')
    expect(region).not.toBeNull()
    // Queue is a semantic list
    expect(container.querySelector('ul[role="list"]')).not.toBeNull()
    // Item button is reachable as semantic button
    const btn = container.querySelector('[data-os-queue-item="draft"]')
    expect(btn.tagName.toLowerCase()).toBe('button')
    expect(btn.getAttribute('aria-label')).toMatch(/Draft|WARN/i)
  })

  it('T-OS-QUEUE-9: destructive review needs two-click confirm', () => {
    _drafts = {
      drafts: [{
        id: 5, agent_id: '0xguardian', action_name: 'audit-drafting',
        created_at: new Date().toISOString(),
      }],
      row_count: 1,
    }
    const { container, getByText, getByPlaceholderText } = renderWorkspace()
    // Open the detail panel
    fireEvent.click(container.querySelector('[data-os-queue-item="draft"]'))
    expect(container.querySelector('[data-os-queue-detail="draft"]')).not.toBeNull()
    // Type a reason ≥10 chars
    const textarea = getByPlaceholderText(/verdict matches/i)
    fireEvent.change(textarea, { target: { value: 'verdict matches on-chain anchor freshness check' } })
    // First click arms, does NOT submit
    const acceptBtn = getByText('Accept').closest('button')
    fireEvent.click(acceptBtn)
    expect(_reviewMutateFn).not.toHaveBeenCalled()
    // Button text now reads "Confirm accept"
    expect(getByText('Confirm accept')).not.toBeNull()
    // Second click confirms
    fireEvent.click(getByText('Confirm accept').closest('button'))
    expect(_reviewMutateFn).toHaveBeenCalledTimes(1)
    expect(_reviewMutateFn.mock.calls[0][0]).toMatchObject({
      draftId: 5, decision: 'accept',
    })
  })
})
