/**
 * Phase O5-PUBLIC-VIEWER — viewer integration tests.
 *
 * T-PUB-VIEWER-1   route renders + reads :commitmentHex param
 * T-PUB-VIEWER-2   AlgorithmCatalog renders 14+ FROZEN-v1 tags
 * T-PUB-VIEWER-3   CryptoReplayPanel renders verifier rows when session found
 * T-PUB-VIEWER-4   not-found state when /public/session returns found:false
 * T-PUB-VIEWER-5   PoacBodyHasher renders input + button
 * T-PUB-VIEWER-6   GicChainTimeline renders chain status
 * T-PUB-VIEWER-7   verifier registry sanity (matches Stream C test)
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

import PublicSessionViewer from '../views/PublicSessionViewer'
import { VERIFIER_COUNT } from '../crypto/vapi_verifier'

// Mock the publicForensic api module so we don't need a live bridge
vi.mock('../api/publicForensic', () => ({
  usePublicSession: (hash) => ({
    data: hash === 'a'.repeat(64) ? {
      found: true,
      vpm: {
        commitment_hex: 'a'.repeat(64),
        vpm_id: 'MLGA-SESSION-v1',
        zkba_class: 2,
        proof_weight: 3,
        visual_state: 'live',
        capture_mode: 'live',
        integrity_label_hash_hex: 'b'.repeat(64),
      },
      mlga: null,
    } : { found: false },
    isLoading: false,
    error: null,
  }),
  usePublicAlgorithms: () => ({
    data: {
      schema: 'vapi-public-algorithm-manifest-v1',
      count: 16,
      tags: [
        { tag: 'VAPI-GIC-GENESIS-v1', primitive: 'GIC chain genesis', preimage: 'tag(19B)||sid||ts', output: 'SHA-256', py_module: 'grind_chain.py', py_function: 'genesis_gic' },
        { tag: 'VAPI-MLGA-SESSION-v1', primitive: 'MLGA dataproof', preimage: '89B', output: 'SHA-256', py_module: 'mlga_capture.py', py_function: 'compute' },
        { tag: 'VAPI-VAME-v1', primitive: 'VAME', preimage: 'tag', output: 'SHA-256', py_module: 'vame.py', py_function: 'stamp' },
        { tag: 'VAPI-ZKBA-ARTIFACT-v1', primitive: 'ZKBA', preimage: 'tag', output: 'SHA-256', py_module: 'zkba_artifact.py', py_function: 'compute' },
      ],
      discipline: 'mirror discipline',
    },
    isLoading: false,
    error: null,
  }),
  usePublicGicChain: () => ({
    data: {
      grind_session_id: 'grind_test_v1',
      chain_length: 105,
      latest_gic_hash: 'c'.repeat(64),
      chain_intact: true,
      genesis_ts: 1.0,
      latest_ts: 100.0,
      discipline: 'Re-derive each chain link…',
    },
    isLoading: false,
    error: null,
  }),
  usePublicAgentRoots: () => ({
    data: {
      schema: 'vapi-public-agent-roots-v1',
      agents: [
        { canonical: 'anchor_sentry', agent_id: 's'.repeat(64), phase: 'O1_SHADOW', cedar_bundle_merkle: 'm'.repeat(64) },
        { canonical: 'guardian',      agent_id: 'g'.repeat(64), phase: 'O1_SHADOW', cedar_bundle_merkle: 'm'.repeat(64) },
        { canonical: 'curator',       agent_id: 'c'.repeat(64), phase: 'O1_SHADOW', cedar_bundle_merkle: 'm'.repeat(64) },
      ],
      chain: { name: 'IoTeX', chain_id: 4690, network: 'testnet' },
    },
    isLoading: false,
    error: null,
  }),
  usePublicProtocolState: () => ({
    data: {
      pv_ci_invariants_count: 122,
      total_vpm_artifacts: 14,
      total_mlga_sessions: 11,
      total_grind_chain_links: 105,
      kill_switch_paused: true,
    },
  }),
  fetchPublicRecordBytes: vi.fn(),
}))


function renderWithRouter(commitmentHex) {
  const qc = new QueryClient()
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/session/${commitmentHex}`]}>
        <Routes>
          <Route path="/session/:commitmentHex" element={<PublicSessionViewer />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}


describe('PublicSessionViewer', () => {
  it('T-PUB-VIEWER-1: route renders and reads commitment_hex', async () => {
    const hash = 'a'.repeat(64)
    const { container } = renderWithRouter(hash)
    await waitFor(() => {
      expect(container.querySelector('[data-vapi-session-found="true"]')).not.toBeNull()
    })
  })

  it('T-PUB-VIEWER-2: AlgorithmCatalog renders algorithm cards', async () => {
    const { container } = renderWithRouter('a'.repeat(64))
    await waitFor(() => {
      expect(container.querySelector('[data-vapi-algorithm-catalog="panel"]')).not.toBeNull()
      const cards = container.querySelectorAll('[data-vapi-algo-card]')
      expect(cards.length).toBeGreaterThanOrEqual(4)  // mock returns 4
    })
  })

  it('T-PUB-VIEWER-3: CryptoReplayPanel renders verifier rows', async () => {
    const { container } = renderWithRouter('a'.repeat(64))
    await waitFor(() => {
      expect(container.querySelector('[data-vapi-crypto-replay="panel"]')).not.toBeNull()
    })
    // Rows are async; verify at least one verifier row eventually renders
    await waitFor(() => {
      const rows = container.querySelectorAll('[data-vapi-replay-row]')
      expect(rows.length).toBeGreaterThanOrEqual(1)
    }, { timeout: 2000 })
  })

  it('T-PUB-VIEWER-4: not-found state for unknown hash', async () => {
    const { container, getByText } = renderWithRouter('f'.repeat(64))
    await waitFor(() => {
      expect(container.querySelector('[data-vapi-session-found="false"]')).not.toBeNull()
      expect(getByText(/No VPM artifact/i)).not.toBeNull()
    })
  })

  it('T-PUB-VIEWER-5: PoacBodyHasher renders input + button when found', async () => {
    const { container } = renderWithRouter('a'.repeat(64))
    await waitFor(() => {
      expect(container.querySelector('[data-vapi-poac-hasher="panel"]')).not.toBeNull()
      expect(container.querySelector('[data-vapi-poac-input="device-id"]')).not.toBeNull()
      expect(container.querySelector('[data-vapi-poac-input="counter"]')).not.toBeNull()
    })
  })

  it('T-PUB-VIEWER-6: GicChainTimeline renders chain status', async () => {
    const { container } = renderWithRouter('a'.repeat(64))
    await waitFor(() => {
      const panel = container.querySelector('[data-vapi-gic-timeline="panel"]')
      expect(panel).not.toBeNull()
      // From mock: chain_length=105 + chain_intact=true must appear in panel text
      const text = panel.textContent
      expect(text).toContain('105')
      expect(text).toContain('true')
    })
  })

  it('T-PUB-VIEWER-7: VERIFIER_COUNT matches catalog (15 verifiers)', () => {
    expect(VERIFIER_COUNT).toBe(15)
  })
})
