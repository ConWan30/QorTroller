/**
 * /start mainstream gamer onboarding — render contract tests.
 *
 *   T-START-1  hero headline renders ("Your hands left a signature.")
 *   T-START-2  Act II evidence — live chain ticker — surfaces the real
 *              chain_length from the bridge hook (NOT a fabricated number)
 *   T-START-3  bridge-asleep state shown honestly when useGrindChain
 *              fails / returns no data (noMock contract preserved)
 *   T-START-4  CTA links to /consent (the Cockpit destination)
 */
import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

// jsdom lacks IntersectionObserver; framer-motion's useScroll uses it.
// Stub before any component imports so the module load doesn't blow.
beforeAll(() => {
  if (typeof globalThis.IntersectionObserver === 'undefined') {
    globalThis.IntersectionObserver = class IntersectionObserverStub {
      constructor() {}
      observe() {}
      unobserve() {}
      disconnect() {}
      takeRecords() { return [] }
    }
  }
})

const mockUseGrindChain = vi.fn()
vi.mock('../api/bridgeApi', () => ({
  useGrindChain: () => mockUseGrindChain(),
}))

import StartDapp from '../dapps/Start'

function renderStart() {
  return render(
    <MemoryRouter>
      <StartDapp />
    </MemoryRouter>,
  )
}

describe('/start gamer onboarding', () => {
  it('T-START-1 hero headline renders', () => {
    mockUseGrindChain.mockReturnValue({ data: { chain_length: 100, chain_intact: true }, isError: false })
    renderStart()
    // "Your hands left a signature." — split across nodes but findable
    expect(screen.getByText(/Your hands/)).toBeTruthy()
    expect(screen.getByText(/signature\./)).toBeTruthy()
  })

  it('T-START-2 live chain ticker surfaces real chain_length', () => {
    mockUseGrindChain.mockReturnValue({
      data: {
        chain_length: 1234,
        chain_intact: true,
        latest_gic_hash: '0xabcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789',
      },
      isError: false,
    })
    renderStart()
    expect(screen.getByText('1,234')).toBeTruthy()
    expect(screen.getByText(/PoAC frames signed, hash-chained, anchored/)).toBeTruthy()
    expect(screen.getByText(/● chain intact/)).toBeTruthy()
  })

  it('T-START-3 bridge-asleep state shows honest empty (noMock)', () => {
    mockUseGrindChain.mockReturnValue({ data: undefined, isError: true })
    renderStart()
    expect(screen.getByText(/the bridge is asleep right now/i)).toBeTruthy()
    // Must NOT fabricate a chain number
    expect(screen.queryByText(/PoAC frames signed/)).toBeNull()
  })

  it('T-START-4 CTA links to /consent', () => {
    mockUseGrindChain.mockReturnValue({ data: { chain_length: 100 }, isError: false })
    renderStart()
    const cta = screen.getByText(/Open the Consent Cockpit/i)
    expect(cta).toBeTruthy()
    // closest anchor href === /consent
    const anchor = cta.closest('a')
    expect(anchor?.getAttribute('href')).toBe('/consent')
  })
})
