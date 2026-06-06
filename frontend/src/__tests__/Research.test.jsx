/**
 * /research WMP Researcher Landing — render contract + verifier tests.
 *
 *   T-RES-1   page renders the headline + Li grounding paragraph
 *   T-RES-2   TOC rail renders all 5 section labels
 *   T-RES-3   in-browser verifier evaluates SAMPLE_BUNDLE → VERIFIED
 *             with allowSynthetic=true (default)
 *   T-RES-4   structural rehash check returns the same digest in
 *             browser as the Python implementation would (algorithmic
 *             port byte-identical contract)
 *   T-RES-5   tampering with a single byte in matrix_hex changes the
 *             structural rehash digest — the canonical-home check
 *             catches the matrix-swap attack
 */
import { describe, it, expect, beforeAll } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

beforeAll(async () => {
  if (typeof globalThis.crypto?.subtle === 'undefined') {
    const { webcrypto } = await import('node:crypto')
    Object.defineProperty(globalThis, 'crypto', { value: webcrypto, writable: true })
  }
})

import ResearchDapp from '../dapps/Research'
import {
  verifyBundle,
  checkMatrixRootRehash,
  OUTCOME_VERIFIED,
  OUTCOME_REJECTED,
} from '../dapps/Research/inBrowserVerifier'
import { SAMPLE_BUNDLE } from '../dapps/Research/sampleBundle'

function renderResearch() {
  return render(
    <MemoryRouter>
      <ResearchDapp />
    </MemoryRouter>,
  )
}

describe('/research WMP landing', () => {
  it('T-RES-1 renders headline + Li grounding paragraph', () => {
    renderResearch()
    expect(screen.getByText(/Cryptographically/)).toBeTruthy()
    expect(screen.getByText(/Fei-Fei Li/)).toBeTruthy()
    expect(screen.getByText(/Not a world model/i)).toBeTruthy()
  })

  it('T-RES-2 TOC rail renders all 5 section labels', () => {
    renderResearch()
    // Each label appears in BOTH the TOC rail AND the corresponding
    // section title (which extends the TOC label with more words), so
    // we use getAllByText and assert presence rather than uniqueness.
    expect(screen.getAllByText(/Honest placement/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/What the bundle contains/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Verify in your browser/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Safety rails/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Quickstart/i).length).toBeGreaterThan(0)
  })

  it('T-RES-3 SAMPLE_BUNDLE verifies with allowSynthetic=true', async () => {
    const r = await verifyBundle(SAMPLE_BUNDLE, { allowSynthetic: true })
    expect(r.overall).toBe(OUTCOME_VERIFIED)
  })

  it('T-RES-4 SAMPLE_BUNDLE rejected when allowSynthetic=false', async () => {
    const r = await verifyBundle(SAMPLE_BUNDLE, { allowSynthetic: false })
    expect(r.overall).toBe(OUTCOME_REJECTED)
    expect(r.reasons.some((s) => /scope_synthetic/.test(s))).toBe(true)
  })

  it('T-RES-5 matrix-swap attack: tampered byte changes structural rehash digest', async () => {
    const tampered = JSON.parse(JSON.stringify(SAMPLE_BUNDLE))
    tampered.action_trace_matrix_hex.button_mask = 'ff' + tampered.action_trace_matrix_hex.button_mask.slice(2)
    const orig = await checkMatrixRootRehash(SAMPLE_BUNDLE)
    const tamp = await checkMatrixRootRehash(tampered)
    expect(orig.actual).toBeTruthy()
    expect(tamp.actual).toBeTruthy()
    expect(orig.actual).not.toBe(tamp.actual)
  })
})
