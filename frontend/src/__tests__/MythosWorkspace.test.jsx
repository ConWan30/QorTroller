/**
 * Mythos Audit Fleet Workspace — render contract tests.
 *
 *   T-MYTHOS-1   workspace renders all 15 variant cells
 *   T-MYTHOS-2   CLEAN state cells show green ● indicator
 *   T-MYTHOS-3   open findings cause a cell to show WARN / open count
 *   T-MYTHOS-4   clicking a cell opens the detail panel with variant label
 *   T-MYTHOS-5   bridge-offline state renders BRIDGE UNREACHABLE
 */
import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// Stub useMythosFindings before importing the workspace
vi.mock('../api/bridgeApi', () => ({
  useMythosFindings: vi.fn(),
}))

import { useMythosFindings } from '../api/bridgeApi'
import MythosWorkspace from '../os/workspaces/MythosWorkspace'

function renderWorkspace() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <MythosWorkspace />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

const SAMPLE_FINDINGS = [
  {
    id: 1, finding_id: 'f-001', variant: 'frozen_drift',
    severity: 'HIGH', title: 'FROZEN tag missing', description: 'tag absent',
    resolved: 0, created_at: 1717700000,
  },
  {
    id: 2, finding_id: 'f-002', variant: 'frontend_brand_drift',
    severity: 'MEDIUM', title: 'Brand drift detected', description: 'inter found',
    resolved: 0, created_at: 1717700100,
  },
]

describe('Mythos Audit Fleet Workspace', () => {
  it('T-MYTHOS-1 renders all 15 variant cells', () => {
    useMythosFindings.mockReturnValue({ data: { findings: [], cadence: {} }, isLoading: false, isError: false })
    renderWorkspace()
    // Each cell shows its short label; spot-check 5 distinct ones
    expect(screen.getByText('FROZEN')).toBeTruthy()
    expect(screen.getByText('STABILITY')).toBeTruthy()
    expect(screen.getByText('CORPUS')).toBeTruthy()
    expect(screen.getByText('BRAND')).toBeTruthy()
    expect(screen.getByText('CURATOR')).toBeTruthy()
  })

  it('T-MYTHOS-2 CLEAN cells show green ● indicator', () => {
    useMythosFindings.mockReturnValue({ data: { findings: [], cadence: {} }, isLoading: false, isError: false })
    renderWorkspace()
    // Each clean cell renders '●' (no open findings)
    const dots = screen.getAllByText('●')
    expect(dots.length).toBe(15)
  })

  it('T-MYTHOS-3 open findings show count indicator on cell', () => {
    useMythosFindings.mockReturnValue({
      data: { findings: SAMPLE_FINDINGS, cadence: {} },
      isLoading: false, isError: false,
    })
    renderWorkspace()
    // frozen_drift has 1 open finding → shows '▲ 1'
    expect(screen.getAllByText('▲ 1').length).toBeGreaterThan(0)
    // Header shows total open findings count
    expect(screen.getAllByText('2 OPEN').length).toBeGreaterThan(0)
  })

  it('T-MYTHOS-4 clicking a cell opens detail panel', async () => {
    useMythosFindings.mockReturnValue({
      data: { findings: SAMPLE_FINDINGS, cadence: {} },
      isLoading: false, isError: false,
    })
    renderWorkspace()
    // Click the Frozen Drift cell (button with aria-label containing 'Frozen Drift')
    const cell = screen.getByRole('button', { name: /Frozen Drift/i })
    fireEvent.click(cell)
    await waitFor(() => {
      expect(screen.getByText('FROZEN tag missing')).toBeTruthy()
    })
    // Panel shows close button
    expect(screen.getByText('✕ CLOSE')).toBeTruthy()
  })

  it('T-MYTHOS-5 bridge offline renders BRIDGE UNREACHABLE', () => {
    useMythosFindings.mockReturnValue({ data: undefined, isLoading: false, isError: true })
    renderWorkspace()
    expect(screen.getByText('BRIDGE UNREACHABLE')).toBeTruthy()
  })
})
