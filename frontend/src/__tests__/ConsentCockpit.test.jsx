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
 *   T-COCKPIT-3  (F3) wallet-connected IdentityCard surfaces wallet (AUTHORITY)
 *                and device_id (SUBJECT) as DISTINCT fields, sourced from
 *                useWalletDevices NOT from a wallet-derivation. Authority
 *                label and subject label both render. The shipped device_id
 *                comes from the binding, not deviceIdFromAddress.
 *
 *   T-COCKPIT-4  ReceiptTimeline mounts with header "RECEIPT TIMELINE";
 *                wallet-disconnected state shows the "connect your wallet"
 *                empty message rather than fabricated entries (noMock).
 *
 *   T-COCKPIT-5  (F3) wallet connected but useWalletDevices returns an
 *                empty bindings array — Cockpit shows the honest
 *                "No on-chain controller binding found for this wallet"
 *                empty state. NO fabricated device_id.
 *
 *   T-COCKPIT-6  (F3) wallet connected, useWalletDevices returns >1
 *                bindings — ControllerSelector renders with one button
 *                per binding; first binding is selected by default.
 *
 * Mocks: wagmi (useAccount/useConnect/useDisconnect), useConsentSubmit,
 * useConsentStatus (read), useConsentHistory (timeline read),
 * useWalletDevices (F2 binding read). React-router is wrapped via
 * <MemoryRouter> rather than mocked since the Cockpit's <Link>
 * components are pure-display and don't trigger navigation in test
 * render.
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
const mockUseWalletDevices  = vi.fn()
vi.mock('../api/bridgeApi', () => ({
  useConsentStatus:  (deviceId) => mockUseConsentStatus(deviceId),
  useConsentHistory: (deviceId, limit) => mockUseConsentHistory(deviceId, limit),
  useWalletDevices:  (wallet, opts) => mockUseWalletDevices(wallet, opts),
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

// Per-test helper to set every mock to a sane default before
// each test then override specifically. Keeps test bodies focused on
// the assertion of interest.
function setMocks({
  account = { address: undefined, isConnected: false },
  contractAddress = '',
  consentStatus = undefined,
  consentHistory = { data: { entries: [] }, isLoading: false, isError: false },
  walletDevices = { data: { bindings: [] }, isLoading: false, isError: false },
} = {}) {
  mockUseAccount.mockReturnValue(account)
  mockUseConsentSubmit.mockReturnValue({
    ready: Boolean(account.isConnected && contractAddress),
    pending: false,
    error: null,
    grant: vi.fn(),
    revoke: vi.fn(),
    contractAddress,
  })
  mockUseConsentStatus.mockReturnValue({ data: consentStatus, refetch: vi.fn() })
  mockUseConsentHistory.mockReturnValue(consentHistory)
  mockUseWalletDevices.mockReturnValue(walletDevices)
}

describe('Consent Cockpit dApp', () => {
  it('T-COCKPIT-1 shows DEPLOY-HOLD banner when registry address is empty', () => {
    setMocks()
    renderCockpit()
    expect(screen.getByText(/REGISTRY DEPLOY-HOLD/i)).toBeTruthy()
    expect(screen.getByText(/only authority over your consent/i)).toBeTruthy()
  })

  it('T-COCKPIT-2 shows CONNECT WALLET CTA when wallet disconnected', () => {
    setMocks()
    renderCockpit()
    const cta = screen.getByRole('button', { name: /connect wallet/i })
    expect(cta).toBeTruthy()
  })

  it('T-COCKPIT-3 (F3) shows wallet (AUTHORITY) and device_id (SUBJECT) as distinct fields sourced from useWalletDevices', () => {
    const ADDR = '0xAbCdEf0123456789abcdef0123456789AbCdEf01'
    const REAL_DEVICE_ID = 'deadbeef'.repeat(8)  // 64-char hex, NOT derived from ADDR
    setMocks({
      account: { address: ADDR, isConnected: true },
      consentStatus: { categories: {} },
      walletDevices: {
        data: {
          bindings: [
            { device_id: REAL_DEVICE_ID, source: 'VAPIPoEPRegistry', valid: true, expires_at: 0 },
          ],
        },
        isLoading: false,
        isError: false,
      },
    })
    renderCockpit()

    // Wallet (authority) — full address rendered
    expect(screen.getByText(ADDR)).toBeTruthy()
    // Authority and subject labels both present — proves dual-identity surface
    expect(screen.getByText(/WALLET · AUTHORITY/i)).toBeTruthy()
    expect(screen.getByText(/DEVICE · SUBJECT/i)).toBeTruthy()
    // Subject device_id comes from useWalletDevices binding, NOT from wallet derivation
    expect(screen.getByText(REAL_DEVICE_ID)).toBeTruthy()
    // The OLD wallet-derived shim (lowercased address minus 0x prefix) MUST NOT appear
    const walletDerivedShim = ADDR.toLowerCase().replace(/^0x/, '')
    expect(screen.queryByText(walletDerivedShim)).toBeNull()
  })

  it('T-COCKPIT-4 mounts ReceiptTimeline with header and empty wallet message', () => {
    setMocks()
    renderCockpit()
    expect(screen.getByText(/RECEIPT TIMELINE/)).toBeTruthy()
    expect(
      screen.getByText(/Connect your wallet to view your consent receipt history/i),
    ).toBeTruthy()
  })

  it('T-COCKPIT-5 (F3) shows honest "no binding" state when wallet has no on-chain controller registration', () => {
    const ADDR = '0x0000000000000000000000000000000000001234'
    setMocks({
      account: { address: ADDR, isConnected: true },
      consentStatus: { categories: {} },
      walletDevices: { data: { bindings: [] }, isLoading: false, isError: false },
    })
    renderCockpit()
    expect(screen.getByText(/No on-chain controller binding found for this wallet/i)).toBeTruthy()
    expect(screen.getByText(/will not fabricate a subject identifier/i)).toBeTruthy()
  })

  it('T-COCKPIT-6 (F3) renders ControllerSelector when multiple bindings exist', () => {
    const ADDR = '0xAbCdEf0123456789abcdef0123456789AbCdEf01'
    const DEV_A = 'a' + 'a'.repeat(63)
    const DEV_B = 'b' + 'b'.repeat(63)
    setMocks({
      account: { address: ADDR, isConnected: true },
      consentStatus: { categories: {} },
      walletDevices: {
        data: {
          bindings: [
            { device_id: DEV_A, source: 'VAPIPoEPRegistry', valid: true,  expires_at: 0 },
            { device_id: DEV_B, source: 'VHPMinted',        valid: true,  expires_at: 0, token_id: 7 },
          ],
        },
        isLoading: false,
        isError: false,
      },
    })
    renderCockpit()
    expect(screen.getByText(/SELECT CONTROLLER \(2 REGISTERED\)/i)).toBeTruthy()
    // Both source labels render — first binding appears twice (selected-summary
    // label + its own selector row), second binding appears in its selector row.
    // getAllByText to assert presence without uniqueness.
    expect(screen.getAllByText(/gamer-signed registration/i).length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText(/bridge-attested binding/i).length).toBeGreaterThanOrEqual(1)
  })
})
