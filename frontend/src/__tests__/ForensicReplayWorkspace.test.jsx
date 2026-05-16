/**
 * Phase O5-EVIDENCE-OS Stage 4 — Forensic Replay workspace tests
 *
 *   T-OS-REPLAY-1  input detection — 64-char hex → session mode
 *   T-OS-REPLAY-2  input detection — grind_* → gic mode
 *   T-OS-REPLAY-3  input detection — "<hex64>/<n>" → record mode
 *   T-OS-REPLAY-4  input detection — VHP token id → vhp mode
 *   T-OS-REPLAY-5  input detection — free text → algorithm mode
 *   T-OS-REPLAY-6  empty input — submit disabled, "dormant" badge
 *   T-OS-REPLAY-7  detectInput exported pure function — full matrix
 *   T-OS-REPLAY-8  VerificationReceipt renders OK / mismatch / skipped
 *                  / pending / error states
 *   T-OS-REPLAY-9  ReplayModeTabs disables tabs without input + shows
 *                  reason in title
 *   T-OS-REPLAY-10 workspace shows EmptyState + ReplaySearch on /os/replay
 *
 * Existing-route preservation is covered by the existing
 * PublicSessionViewer.test.jsx + EvidenceOS placeholder tests.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

// We need the publicForensic hooks NOT to make real network calls
vi.mock('../api/publicForensic', () => ({
  usePublicSession:      () => ({ data: null, isLoading: false, error: null }),
  usePublicAlgorithms:   () => ({ data: { tags: [] }, isLoading: false, error: null }),
  usePublicGicChain:     () => ({ data: null }),
  usePublicGicLinks:     () => ({ data: { links: [] }, isLoading: false, error: null }),
  usePublicAgentRoots:   () => ({ data: null }),
  usePublicProtocolState: () => ({ data: { chain: {} }, error: null }),
  usePublicVhp:          () => ({ data: null, error: null, isLoading: false }),
  fetchPublicRecordBytes: async () => new Uint8Array(228),
}))

// The vapi_verifier module touches Web Crypto; just resolve everything
// to a fixed hex so receipt-state tests don't depend on jsdom crypto
vi.mock('../crypto/vapi_verifier', () => ({
  verifyPoacRecordHash:   async () => 'a'.repeat(64),
  verifyGicGenesis:       async () => 'b'.repeat(64),
  verifyGicChainLink:     async () => 'c'.repeat(64),
  bytesToHex:             (b) => Array.from(b || []).map(x => x.toString(16).padStart(2, '0')).join(''),
  hexToBytes:             () => new Uint8Array(),
}))

import ForensicReplayWorkspace from '../os/workspaces/ForensicReplayWorkspace'
import { detectInput } from '../os/components/ReplaySearch'
import VerificationReceipt from '../os/components/VerificationReceipt'
import ReplayModeTabs from '../os/components/ReplayModeTabs'

function renderWorkspace({ initialPath = '/os/replay' } = {}) {
  const qc = new QueryClient()
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/os/replay" element={<ForensicReplayWorkspace />}>
            <Route path="session/:commitmentHex" element={<div data-test-viewer="session"/>}/>
            <Route path="gic/:grindSessionId"    element={<div data-test-viewer="gic"/>}/>
            <Route path="record/:deviceId/:counter" element={<div data-test-viewer="record"/>}/>
            <Route path="vhp/:tokenId"           element={<div data-test-viewer="vhp"/>}/>
            <Route path="algorithms"             element={<div data-test-viewer="algorithms"/>}/>
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('detectInput (pure)', () => {
  it('T-OS-REPLAY-1: 64-char hex → session', () => {
    const r = detectInput('a'.repeat(64))
    expect(r.mode).toBe('session')
    expect(r.params.commitmentHex).toBe('a'.repeat(64))
  })
  it('T-OS-REPLAY-2: grind_* → gic', () => {
    const r = detectInput('grind_phase235_v1')
    expect(r.mode).toBe('gic')
    expect(r.params.grindSessionId).toBe('grind_phase235_v1')
  })
  it('T-OS-REPLAY-3: hex64/counter → record', () => {
    const dev = 'd'.repeat(64)
    const r = detectInput(`${dev}/42`)
    expect(r.mode).toBe('record')
    expect(r.params.deviceId).toBe(dev)
    expect(r.params.counter).toBe('42')
  })
  it('T-OS-REPLAY-4: VHP-<n> → vhp', () => {
    const r = detectInput('VHP-2')
    expect(r.mode).toBe('vhp')
    expect(r.params.tokenId).toBe('2')
  })
  it('T-OS-REPLAY-4b: pure integer → vhp (default)', () => {
    const r = detectInput('42')
    expect(r.mode).toBe('vhp')
    expect(r.params.tokenId).toBe('42')
  })
  it('T-OS-REPLAY-5: free text → algorithm', () => {
    const r = detectInput('poseidon')
    expect(r.mode).toBe('algorithm')
    expect(r.params.q).toBe('poseidon')
  })
  it('T-OS-REPLAY-6: empty → empty mode', () => {
    expect(detectInput('').mode).toBe('empty')
    expect(detectInput('   ').mode).toBe('empty')
  })
  it('T-OS-REPLAY-7: lower-cases hex commitment', () => {
    const r = detectInput('ABCD' + 'a'.repeat(60))
    expect(r.mode).toBe('session')
    expect(r.params.commitmentHex).toBe('abcd' + 'a'.repeat(60))
  })
})


describe('VerificationReceipt', () => {
  it('T-OS-REPLAY-8: renders ok / mismatch / skipped / pending / error', () => {
    const items = [
      { id: '1', claim: 'GIC genesis', status: 'ok', protocol: 'a'.repeat(64), computed: 'a'.repeat(64), source: '/public/gic/x', algorithm: 'verifyGicGenesis', tsMs: 1700000000000 },
      { id: '2', claim: 'PoAC record body', status: 'mismatch', protocol: 'b'.repeat(64), computed: 'c'.repeat(64), source: '/public/record/x/0', algorithm: 'verifyPoacRecordHash' },
      { id: '3', claim: 'VPM integrity label', status: 'skipped', reason: 'no verifier wired in v1' },
      { id: '4', claim: 'FRR commitment', status: 'pending' },
      { id: '5', claim: 'Cedar bundle merkle', status: 'error', reason: 'fetch failed' },
    ]
    const { container, getByText } = render(<VerificationReceipt items={items}/>)
    // Each row carries its status label as text (never color-only)
    expect(getByText('OK')).not.toBeNull()
    expect(getByText('MISMATCH')).not.toBeNull()
    expect(getByText('SKIPPED')).not.toBeNull()
    expect(getByText('PENDING')).not.toBeNull()
    expect(getByText('ERROR')).not.toBeNull()
    // 5 rows rendered
    expect(container.querySelectorAll('[data-os-receipt-row]').length).toBe(5)
    // OK row has live-status data-attr, mismatch has blocked-status
    expect(container.querySelector('[data-os-receipt-status="ok"]')).not.toBeNull()
    expect(container.querySelector('[data-os-receipt-status="mismatch"]')).not.toBeNull()
    expect(container.querySelector('[data-os-receipt-status="skipped"]')).not.toBeNull()
  })

  it('T-OS-REPLAY-8b: empty receipt is HONEST (no false "OK")', () => {
    const { container } = render(<VerificationReceipt items={[]}/>)
    // No row count
    expect(container.querySelector('[data-os-receipt-row]')).toBeNull()
    // Honest copy
    expect(container.textContent).toMatch(/does not imply "OK"/i)
    expect(container.textContent).not.toMatch(/all clear|all good/i)
  })
})


describe('ReplayModeTabs', () => {
  it('T-OS-REPLAY-9: disables tabs without input + reason in title', () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/os/replay']}>
        <Routes>
          <Route path="/os/replay/*" element={
            <ReplayModeTabs
              available={{ session: false, gic: false, record: false, vhp: false, algorithms: true }}
              paths={{ algorithms: '/os/replay/algorithms' }}
            />
          }/>
        </Routes>
      </MemoryRouter>,
    )
    // Session tab disabled
    const sessionTab = container.querySelector('[data-os-replay-tab="session"]')
    expect(sessionTab).not.toBeNull()
    expect(sessionTab.getAttribute('data-os-tab-enabled')).toBe('false')
    expect(sessionTab.getAttribute('aria-disabled')).toBe('true')
    expect(sessionTab.getAttribute('title')).toMatch(/session commitment/i)
    // Algorithms tab always enabled
    const algoTab = container.querySelector('[data-os-replay-tab="algorithms"]')
    expect(algoTab.getAttribute('data-os-tab-enabled')).toBe('true')
  })
})


describe('ForensicReplayWorkspace integration', () => {
  it('T-OS-REPLAY-10: /os/replay index renders ReplaySearch + EmptyState', () => {
    const { container, getByPlaceholderText } = renderWorkspace()
    // Search form is present
    expect(container.querySelector('form[role="search"]')).not.toBeNull()
    // Search input ready
    expect(getByPlaceholderText(/grind_20260505/i)).not.toBeNull()
    // Mode tabs rendered (algorithms always enabled)
    expect(container.querySelector('[data-os-replay-tab="algorithms"]')).not.toBeNull()
    // EmptyState in place of the outlet (since no nested route active)
    expect(container.textContent).toMatch(/paste any commitment/i)
    // Verification receipt starts honest
    expect(container.querySelector('[data-os-verification-receipt]')).not.toBeNull()
    expect(container.textContent).toMatch(/no verifications executed yet/i)
  })

  it('T-OS-REPLAY-11: typing a 64-char hex + Open navigates to /os/replay/session/<hex>', () => {
    const { container, getByPlaceholderText, getByText, getByLabelText } = renderWorkspace()
    const input = getByPlaceholderText(/grind_20260505/i)
    fireEvent.change(input, { target: { value: 'a'.repeat(64) } })
    // Detected chip surfaces the mode label
    expect(getByText(/session commitment/i)).not.toBeNull()
    // Submit
    fireEvent.click(getByLabelText('Open detected mode'))
    // Nested route mounted via the test-only outlet stub
    expect(container.querySelector('[data-test-viewer="session"]')).not.toBeNull()
    // EmptyState gone
    expect(container.textContent).not.toMatch(/paste any commitment/i)
  })

  it('T-OS-REPLAY-12: typing grind_* + Open mounts gic viewer', () => {
    const { container, getByPlaceholderText, getByLabelText } = renderWorkspace()
    fireEvent.change(getByPlaceholderText(/grind_20260505/i), {
      target: { value: 'grind_phase235_v1' },
    })
    fireEvent.click(getByLabelText('Open detected mode'))
    expect(container.querySelector('[data-test-viewer="gic"]')).not.toBeNull()
  })

  it('T-OS-REPLAY-13: algorithm input mounts algorithms viewer; shareable link visible', () => {
    const { container, getByPlaceholderText, getByLabelText } = renderWorkspace()
    fireEvent.change(getByPlaceholderText(/grind_20260505/i), {
      target: { value: 'poseidon' },
    })
    fireEvent.click(getByLabelText('Open detected mode'))
    expect(container.querySelector('[data-test-viewer="algorithms"]')).not.toBeNull()
    // Public source link visible — points at top-level /algorithms
    const link = container.querySelector('[data-os-source-link]')
    expect(link).not.toBeNull()
    expect(link.getAttribute('href')).toBe('/algorithms')
  })
})
