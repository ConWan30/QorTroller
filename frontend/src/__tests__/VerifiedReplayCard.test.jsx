/**
 * Verified Replay Card — render contract tests.
 *
 *   T-REPLAY-1  loading state renders "Loading…" empty-state
 *   T-REPLAY-2  bridge-offline (error) renders honest "bridge unreachable"
 *               — does NOT fabricate a card (noMock contract)
 *   T-REPLAY-3  empty proof list renders "NO MATCHING PROOF" honest empty
 *               state with the ?demo=1 hint
 *   T-REPLAY-4  ?demo=1 renders the DEMO badge LOUDLY so a streamer
 *               preview is never confused with a real proof
 *   T-REPLAY-5  real proof from the hook renders the headline verdict
 *               ("PROOF BUILT") and the proof-token specimen
 *
 * The ProofFoil gradient is computed in a separate component; tests
 * just confirm it renders without crashing on various proof tokens.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import React from 'react'

const mockUseLatestVhrProof = vi.fn()
vi.mock('../api/bridgeApi', () => ({
  useLatestVhrProof: (...args) => mockUseLatestVhrProof(...args),
}))

import VerifiedReplayCardDapp from '../dapps/VerifiedReplay'

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <VerifiedReplayCardDapp />
    </MemoryRouter>,
  )
}

describe('Verified Replay Card', () => {
  it('T-REPLAY-1 loading state renders honestly', () => {
    mockUseLatestVhrProof.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    })
    renderAt('/replay')
    expect(screen.getByText(/Loading…/i)).toBeTruthy()
  })

  it('T-REPLAY-2 bridge unreachable renders honest state, never a fake card', () => {
    mockUseLatestVhrProof.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    })
    renderAt('/replay')
    expect(screen.getByText(/Bridge unreachable/i)).toBeTruthy()
    // Should NOT render fake proof token chrome
    expect(screen.queryByText(/PROOF BUILT/i)).toBeNull()
  })

  it('T-REPLAY-3 empty proof list renders NO MATCHING PROOF with demo hint', () => {
    mockUseLatestVhrProof.mockReturnValue({
      data: { pending_replay_proofs: [] },
      isLoading: false,
      isError: false,
    })
    renderAt('/replay')
    expect(screen.getByText(/NO MATCHING PROOF/i)).toBeTruthy()
    expect(screen.getByText(/\?demo=1/)).toBeTruthy()
  })

  it('T-REPLAY-4 ?demo=1 renders DEMO badge loud and clear', () => {
    mockUseLatestVhrProof.mockReturnValue({
      data: { pending_replay_proofs: [] },
      isLoading: false,
      isError: false,
    })
    renderAt('/replay?demo=1')
    // DEMO badge present — must be visible / loud
    expect(screen.getByText('DEMO')).toBeTruthy()
    // Share strip clarifies this is a demo
    expect(screen.getByText(/this is a demo card from a fixture/i)).toBeTruthy()
  })

  it('T-REPLAY-5 real proof renders verdict + proof-token specimen', () => {
    const realProof = {
      outcome: 'vhr_proof_built',
      session_id: 'grind_phase235_v1',
      ts_ns: 1780703825000000000,
      extra: JSON.stringify({
        replay_proof_token: '0x47ab9d3f5e2c1b8a604fd97b3e2c1a8d617e4cbf4a39d8e215b9c47a832e76c5d',
        poac_chain_root: '0x0e9d453d904220148d632e75802b71bdff74c7197aa8afcbfec5d36a61ab48da',
        block_number: 44355513,
      }),
    }
    mockUseLatestVhrProof.mockReturnValue({
      data: { pending_replay_proofs: [realProof] },
      isLoading: false,
      isError: false,
    })
    renderAt('/replay')
    expect(screen.getByText('PROOF BUILT')).toBeTruthy()
    expect(screen.getByText(/cryptographic proof generated/i)).toBeTruthy()
    // Block number rendered
    expect(screen.getByText(/#44355513/)).toBeTruthy()
    // Proof token truncated specimen (first 10 hex chars after 0x)
    expect(screen.getByText(/0x47ab9d3f5e/)).toBeTruthy()
  })
})
