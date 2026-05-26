/**
 * Phase 3 Path B — Gameplay Workflow Layer (Commit 2)
 * usePlayerSessionStatus hook contract tests.
 *
 *   T-PSS-FE-1  default deviceId hits GET /operator/player/session-status
 *               (no query string) — bridge resolves most-recent device.
 *
 *   T-PSS-FE-2  explicit deviceId URL-encodes into the device_id query
 *               parameter — prevents a malformed hex id (with '+' or '&')
 *               from corrupting the URL.
 *
 *   T-PSS-FE-3  queryKey includes deviceId so two views querying different
 *               devices keep independent react-query cache entries (no
 *               cross-device leakage from a stale cache).
 *
 *   T-PSS-FE-4  on a transient apiGet failure the hook surfaces the error
 *               instead of swapping in mock data (noMock contract — same
 *               discipline as useCaptureHealth / useGrindChain; preserves
 *               gamer-identity honesty when the bridge is briefly offline).
 *
 *   T-PSS-FE-5  successful response shape passes through unchanged — the
 *               hook is a thin react-query wrapper, not a frozen-shape
 *               adapter (cf. T-OS-L4-1 useBrpControllerOrientation).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'

// Mock the low-level fetcher BEFORE importing the hook so the import
// captures the mocked apiGet (Vitest hoists vi.mock to the top of the file).
vi.mock('../api/client', () => ({
  apiGet:  vi.fn(),
  apiPost: vi.fn(),
  ApiKeyError:        class ApiKeyError extends Error {},
  BridgeOfflineError: class BridgeOfflineError extends Error {},
}))

// Spy on mock activation so T-PSS-FE-4 can assert noMock holds.
vi.mock('../api/mockBridge', () => ({
  activateMock:   vi.fn(),
  deactivateMock: vi.fn(),
  isMockActive:   vi.fn(() => false),
  MOCK: {},
}))

import { apiGet } from '../api/client'
import { activateMock } from '../api/mockBridge'
import { usePlayerSessionStatus } from '../api/bridgeApi'

function wrapper() {
  // Disable retries so failure-path tests resolve fast.
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return ({ children }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('usePlayerSessionStatus — endpoint URL', () => {
  it('T-PSS-FE-1: default deviceId hits /operator/player/session-status without query string', async () => {
    apiGet.mockResolvedValueOnce({ controller_connected: false })
    const { result } = renderHook(() => usePlayerSessionStatus(), { wrapper: wrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(apiGet).toHaveBeenCalledTimes(1)
    expect(apiGet).toHaveBeenCalledWith('/operator/player/session-status')
  })

  it('T-PSS-FE-2: explicit deviceId is URL-encoded into device_id query parameter', async () => {
    apiGet.mockResolvedValueOnce({ controller_connected: false })
    // hex bytes32 with '+' (legal in some encodings, MUST be encoded as %2B)
    const dev = 'abc123+def&xyz'
    const { result } = renderHook(() => usePlayerSessionStatus(dev), { wrapper: wrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(apiGet).toHaveBeenCalledWith(
      '/operator/player/session-status?device_id=abc123%2Bdef%26xyz',
    )
  })
})

describe('usePlayerSessionStatus — cache isolation', () => {
  it('T-PSS-FE-3: queryKey includes deviceId so two devices keep independent cache entries', async () => {
    apiGet
      .mockResolvedValueOnce({ device_id: 'aaa' })
      .mockResolvedValueOnce({ device_id: 'bbb' })
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 } },
    })
    const w = ({ children }) => (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    )
    const r1 = renderHook(() => usePlayerSessionStatus('aaa'), { wrapper: w })
    const r2 = renderHook(() => usePlayerSessionStatus('bbb'), { wrapper: w })
    await waitFor(() => expect(r1.result.current.isSuccess).toBe(true))
    await waitFor(() => expect(r2.result.current.isSuccess).toBe(true))
    expect(r1.result.current.data?.device_id).toBe('aaa')
    expect(r2.result.current.data?.device_id).toBe('bbb')
    // Inspect the cache directly — both keys must coexist.
    const keys = qc.getQueryCache().getAll().map((q) => q.queryKey)
    expect(keys).toEqual(
      expect.arrayContaining([
        ['playerSessionStatus', 'aaa'],
        ['playerSessionStatus', 'bbb'],
      ]),
    )
  })
})

describe('usePlayerSessionStatus — honesty contract', () => {
  it('T-PSS-FE-4: transient failure surfaces error, does NOT activate mock (noMock contract)', async () => {
    // Hook sets retry:1 (one retry = up to 2 attempts). Reject every call so
    // both attempts fail and the hook reaches the error state — anything less
    // and the retry would resolve with undefined and mask the contract.
    apiGet.mockRejectedValue(new Error('bridge unreachable'))
    const { result } = renderHook(() => usePlayerSessionStatus(), { wrapper: wrapper() })
    await waitFor(() => expect(result.current.isError).toBe(true), { timeout: 3000 })
    expect(result.current.error?.message).toBe('bridge unreachable')
    expect(activateMock).not.toHaveBeenCalled()
    expect(result.current.data).toBeUndefined()
  })

  it('T-PSS-FE-5: success response passes through unchanged (thin react-query wrapper)', async () => {
    const payload = {
      controller_connected: true,
      session_active:       true,
      device_id:            'abcd',
      humanity_prob:        0.92,
      is_fully_eligible: { onchain: true, bridge_local: true, source: 'onchain' },
      gic_chain:         { length: 42, integrity: 'intact', last_anchor: null },
      enforcement_active: true,
      host_signer_active: true,
    }
    apiGet.mockResolvedValueOnce(payload)
    const { result } = renderHook(() => usePlayerSessionStatus('abcd'), { wrapper: wrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(payload)
  })
})
