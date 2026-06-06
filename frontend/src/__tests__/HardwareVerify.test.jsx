/**
 * /verify/:deviceId Hardware Authenticity Verify — render contract tests.
 *
 *   T-VERIFY-1  /verify (no device_id) renders the manual-input prompt
 *               and headline "Verify any controller. No login."
 *   T-VERIFY-2  REGISTERED + Path A → ✓ verdict, "REGISTERED" headline,
 *               silicon-rooted detail copy
 *   T-VERIFY-3  Not registered → ✗ verdict, "NOT REGISTERED" — no
 *               fabrication
 *   T-VERIFY-4  REGISTRY_UNAVAILABLE → honest "REGISTRY UNAVAILABLE",
 *               never claims registered
 *   T-VERIFY-5  INVALID_HEX from endpoint → "INVALID DEVICE ID" + hex
 *               hint
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import HardwareVerifyDapp from '../dapps/HardwareVerify'

// Mock fetch globally; per-test response.
const mockFetch = vi.fn()
beforeEach(() => {
  globalThis.fetch = mockFetch
  mockFetch.mockReset()
})

function renderAt(path) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
  })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/verify" element={<HardwareVerifyDapp />} />
          <Route path="/verify/:deviceId" element={<HardwareVerifyDapp />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

async function waitForText(re) {
  for (let i = 0; i < 30; i++) {
    const found = screen.queryByText(re)
    if (found) return found
    await new Promise((r) => setTimeout(r, 20))
  }
  throw new Error(`text not found: ${re}`)
}

describe('/verify hardware authenticity', () => {
  it('T-VERIFY-1 no device_id renders manual-input prompt', () => {
    renderAt('/verify')
    expect(screen.getByText(/Verify any controller/)).toBeTruthy()
    expect(screen.getByText(/No login/)).toBeTruthy()
    expect(screen.getByPlaceholderText(/64-char hex/i)).toBeTruthy()
  })

  it('T-VERIFY-2 REGISTERED + Path A renders ✓ verdict', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        device_id: 'a'.repeat(64),
        registered: true,
        signing_path_code: 1,
        signing_path_label: 'PATH_A_SILICON_ROOTED',
        proof_tier_code: 1,
        proof_tier_label: 'FULL_DUALSENSE_EDGE_CFI_ZCP1',
        registry_address: '0x2e5B5FB1',
        source: 'VAPIManufacturerDeviceRegistry',
        discipline: 'Verify on-chain via VAPIManufacturerDeviceRegistry view calls.',
        explorer_address: 'https://testnet.iotexscan.io/address/0x2e5B5FB1',
      }),
    })
    renderAt('/verify/' + 'a'.repeat(64))
    await waitForText(/REGISTERED/)
    expect(screen.getByText('REGISTERED')).toBeTruthy()
    expect(screen.getByText(/Silicon-rooted manufacturer-attested/i)).toBeTruthy()
  })

  it('T-VERIFY-3 Not registered renders ✗ verdict, no fabrication', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        device_id: 'b'.repeat(64),
        registered: false,
        signing_path_code: 0,
        signing_path_label: 'UNREGISTERED',
        proof_tier_code: 0,
        proof_tier_label: 'UNREGISTERED',
        source: 'VAPIManufacturerDeviceRegistry',
      }),
    })
    renderAt('/verify/' + 'b'.repeat(64))
    await waitForText(/NOT REGISTERED/)
    expect(screen.getByText('NOT REGISTERED')).toBeTruthy()
    // Must NOT contain "REGISTERED" without "NOT" — the verdict
    // headline is exactly "NOT REGISTERED" and the silicon-rooted
    // detail copy must NOT appear
    expect(screen.queryByText(/Silicon-rooted/i)).toBeNull()
  })

  it('T-VERIFY-4 REGISTRY_UNAVAILABLE renders honest, never claims registered', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        device_id: 'c'.repeat(64),
        registered: false,
        source: 'REGISTRY_UNAVAILABLE',
        discipline: 'VAPIManufacturerDeviceRegistry not configured on this bridge.',
      }),
    })
    renderAt('/verify/' + 'c'.repeat(64))
    await waitForText(/REGISTRY UNAVAILABLE/)
    expect(screen.getByText(/no on-chain claim can be made/i)).toBeTruthy()
  })

  it('T-VERIFY-5 INVALID_HEX renders user-input issue copy', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        device_id: 'NOT-HEX',
        registered: false,
        source: 'INVALID_HEX',
      }),
    })
    renderAt('/verify/NOT-HEX')
    await waitForText(/INVALID DEVICE ID/)
    expect(screen.getByText(/must be a 64-character hex string/i)).toBeTruthy()
  })
})
