/**
 * Consent Cockpit dApp — render contract tests.
 *
 *   T-COCKPIT-1  PostureBanner DEPLOY-HOLD posture shows when contractAddress
 *                is empty (useConsentSubmit().contractAddress === ''). Banner
 *                copy contains the BRIDGE-NEVER-GRANTS sovereignty headline.
 *
 *   T-COCKPIT-2  wallet-disconnected IdentityCard shows the CONNECT WALLET
 *                CTA + the sovereignty sub-line. No wallet address is shown.
 *
 *   T-COCKPIT-3  wallet-connected IdentityCard shows the connected address
 *                + derived device_id (lower-cased, no 0x prefix). The
 *                derivation matches what the bridge consent_ledger keys on.
 *
 *   T-COCKPIT-4  ReceiptTimeline mounts with header "RECEIPT TIMELINE";
 *                wallet-disconnected state shows the "connect your wallet"
 *                empty message rather than fabricated entries (noMock).
 *
 * Mocks: wagmi (useAccount/useConnect/useDisconnect), useConsentSubmit,
 * useConsentStatus (read), useConsentHistory (timeline read). React-router
 * is wrapped via <MemoryRouter> rather than mocked since the Cockpit's
 * <Link> components are pure-display and don't trigger navigation in
 * test render.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import React from 'react'

// --- mocks (hoisted) ---
const mockUseAccount    = vi.fn()
const mockUseConnect    = vi.fn(() => ({ connect: vi.fn() }))
const mockUseDisconnect = vi.fn(() => ({ disconnect: vi.fn() }))

vi.mock('wagmi', () => ({
  useAccount:    () => mockUseAccount(),
  useConnect:    () => mockUseConnect(),
  useDisconnect: () => mockUseDisconnect(),
}))

vi.mock('wagmi/connectors', () => ({
  injected: () => ({ id: 'mock-injected' }),
}))

const mockUseConsentSubmit = vi.fn()
vi.mock('../hooks/useConsentSubmit', () => ({
  useConsentSubmit: () => mockUseConsentSubmit(),
}))

const mockUseConsentStatus  = vi.fn()
const mockUseConsentHistory = vi.fn()
vi.mock('../api/bridgeApi', () => ({
  useConsentStatus:  (deviceId) => mockUseConsentStatus(deviceId),
  useConsentHistory: (deviceId, limit) => mockUseConsentHistory(deviceId, limit),
}))

// Minimal heartbeat-store stub so <CockpitChrome> renders without
// pulling in the real zustand store (which expects a provider).
vi.mock('../heartbeat/useHeartbeat', () => ({
  useHeartbeatStore: (selector) => selector({ merkleRoot: '', onChainConfirmed: false }),
}))

// realityHeartbeat exports a dot component — stub it to avoid pulling
// in its internals.
vi.mock('../design/realityHeartbeat', () => ({
  RealityDot: () => <span data-testid="reality-dot" />,
}))

import ConsentCockpitDapp from '../dapps/ConsentCockpit'

function renderCockpit() {
  return render(
    <MemoryRouter>
      <ConsentCockpitDapp />
    </MemoryRouter>,
  )
}

describe('Consent Cockpit dApp', () => {
  it('T-COCKPIT-1 shows DEPLOY-HOLD banner when registry address is empty', () => {
    mockUseAccount.mockReturnValue({ address: undefined, isConnected: false })
    mockUseConsentSubmit.mockReturnValue({
      ready:    false,
      pending:  false,
      error:    null,
      grant:    vi.fn(),
      revoke:   vi.fn(),
      contractAddress: '',
    })
    mockUseConsentStatus.mockReturnValue({ data: undefined, refetch: vi.fn() })
    mockUseConsentHistory.mockReturnValue({ data: { entries: [] }, isLoading: false, isError: false })

    renderCockpit()

    expect(
      screen.getByText(/REGISTRY DEPLOY-HOLD/i),
    ).toBeTruthy()
    expect(
      screen.getByText(/only authority over your consent/i),
    ).toBeTruthy()
  })

  it('T-COCKPIT-2 shows CONNECT WALLET CTA when wallet disconnected', () => {
    mockUseAccount.mockReturnValue({ address: undefined, isConnected: false })
    mockUseConsentSubmit.mockReturnValue({
      ready:    false,
      pending:  false,
      error:    null,
      grant:    vi.fn(),
      revoke:   vi.fn(),
      contractAddress: '',
    })
    mockUseConsentStatus.mockReturnValue({ data: undefined, refetch: vi.fn() })
    mockUseConsentHistory.mockReturnValue({ data: { entries: [] }, isLoading: false, isError: false })

    renderCockpit()

    // CTA button copy: "CONNECT WALLET →"
    const cta = screen.getByRole('button', { name: /connect wallet/i })
    expect(cta).toBeTruthy()
  })

  it('T-COCKPIT-3 shows connected address + derived device_id when wallet connected', () => {
    const ADDR = '0xAbCdEf0123456789abcdef0123456789AbCdEf01'
    mockUseAccount.mockReturnValue({ address: ADDR, isConnected: true })
    mockUseConsentSubmit.mockReturnValue({
      ready:    false,
      pending:  false,
      error:    null,
      grant:    vi.fn(),
      revoke:   vi.fn(),
      contractAddress: '',
    })
    mockUseConsentStatus.mockReturnValue({ data: { categories: {} }, refetch: vi.fn() })
    mockUseConsentHistory.mockReturnValue({ data: { entries: [] }, isLoading: false, isError: false })

    renderCockpit()

    // Full address displayed (not truncated)
    expect(screen.getByText(ADDR)).toBeTruthy()
    // device_id is the lower-cased address with the 0x prefix stripped
    const expectedDeviceId = ADDR.toLowerCase().replace(/^0x/, '')
    expect(screen.getByText(expectedDeviceId)).toBeTruthy()
  })

  it('T-COCKPIT-4 mounts ReceiptTimeline with header and empty wallet message', () => {
    mockUseAccount.mockReturnValue({ address: undefined, isConnected: false })
    mockUseConsentSubmit.mockReturnValue({
      ready:    false,
      pending:  false,
      error:    null,
      grant:    vi.fn(),
      revoke:   vi.fn(),
      contractAddress: '',
    })
    mockUseConsentStatus.mockReturnValue({ data: undefined, refetch: vi.fn() })
    mockUseConsentHistory.mockReturnValue({ data: { entries: [] }, isLoading: false, isError: false })

    renderCockpit()

    expect(screen.getByText(/RECEIPT TIMELINE/)).toBeTruthy()
    // Wallet-disconnected empty-state message
    expect(
      screen.getByText(/Connect your wallet to view your consent receipt history/i),
    ).toBeTruthy()
  })
})
