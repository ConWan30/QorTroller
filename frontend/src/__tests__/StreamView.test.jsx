/**
 * StreamView SPA tests (A2A-PKG round-13 · PKG-UI React).
 *
 *   T-SV-1  normalizeStreamModel missing → UNKNOWN, never LIVE
 *   T-SV-2  normalizeStreamModel LIVE fixture → presence live + respiration
 *   T-SV-3  loadStreamSnapshots fail-open (404) → no fabricated LIVE
 *   T-SV-4  classifyStreamSurfaceMode ceremony / stream / receipt / empty
 *   T-SV-5  WitnessRespiration renders presence line + data attributes
 *   T-SV-6  ReceiptReveal forceComplete shows all stages; verdicts static
 *   T-SV-7  ReceiptReveal HYGIENE line is non-shaming
 *   T-SV-8  choreographyVisibleThrough pure helper
 *   T-SV-9  BirthCeremonyMap stages + ROI hint
 *   T-SV-10 StreamView with initial props: mode + noMock rails attributes
 *   T-SV-11 deliberately_absent discipline (no crop/fps on live model)
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import React from 'react'

import {
  normalizeStreamModel,
  emptyStreamModel,
  loadStreamSnapshots,
  classifyStreamSurfaceMode,
  choreographyVisibleThrough,
  WitnessRespiration,
  ReceiptReveal,
  BirthCeremonyMap,
} from '../stream'
import { StreamView } from '../views/StreamView'
import { EyebrowProvider } from '../design/Eyebrow'

import streamLive from '../stream/fixtures/stream.live.json'
import receiptPartial from '../stream/fixtures/receipt.partial.json'
import ceremonyProv from '../stream/fixtures/ceremony.provisioning.json'

function wrap(ui) {
  return render(<EyebrowProvider>{ui}</EyebrowProvider>)
}

describe('loadLocalSnapshot — noMock pure helpers', () => {
  it('T-SV-1: missing/invalid → UNKNOWN, never LIVE', () => {
    const m = normalizeStreamModel(null)
    expect(m.on_screen.freshness_class).toBe('UNKNOWN')
    expect(m.on_screen.presence_tone).toBe('unknown')
    expect(m.fabricated_liveness).toBe(false)
    expect(m.mock).toBe(false)
    expect(m.signing_material_present).toBe(false)
    expect(emptyStreamModel().on_screen.presence_line).toMatch(/unknown/i)
  })

  it('T-SV-2: LIVE fixture normalizes to witness live', () => {
    const m = normalizeStreamModel(streamLive)
    expect(m.on_screen.presence_line).toBe('your witness is live')
    expect(m.on_screen.presence_tone).toBe('live')
    expect(m.on_screen.freshness_class).toBe('LIVE')
    expect(m.novelty).toBe('witness_respiration')
    expect(m.fabricated_liveness).toBe(false)
  })

  it('T-SV-3: loadStreamSnapshots 404 → fail-open UNKNOWN', async () => {
    const fetchImpl = vi.fn(async () => ({ ok: false, status: 404 }))
    const out = await loadStreamSnapshots('/stream-ui', fetchImpl)
    expect(out.stream.on_screen.freshness_class).toBe('UNKNOWN')
    expect(out.stream.on_screen.presence_tone).not.toBe('live')
    expect(out.stream.fabricated_liveness).toBe(false)
    expect(out.receipt._present).toBe(false)
  })

  it('T-SV-4: classifyStreamSurfaceMode', () => {
    expect(classifyStreamSurfaceMode({
      stream: emptyStreamModel(),
      ceremony: { _present: false },
      receipt: { _present: false },
    })).toBe('EMPTY')

    expect(classifyStreamSurfaceMode({
      stream: normalizeStreamModel(streamLive),
      ceremony: { _present: true, ceremony_complete: true, stages: [] },
      receipt: { _present: false },
    })).toBe('STREAM')

    expect(classifyStreamSurfaceMode({
      stream: emptyStreamModel(),
      ceremony: { ...ceremonyProv, _present: true },
      receipt: { _present: false },
    })).toBe('CEREMONY')

    expect(classifyStreamSurfaceMode({
      stream: normalizeStreamModel(streamLive),
      ceremony: { _present: true, ceremony_complete: true },
      receipt: { ...receiptPartial, _present: true },
    })).toBe('RECEIPT')
  })
})

describe('WitnessRespiration', () => {
  it('T-SV-5: renders presence line + honesty attributes', () => {
    render(
      <WitnessRespiration
        presenceLine="your witness is live"
        presenceTone="live"
        nodeState="LIVE"
        freshnessClass="LIVE"
        sessionIdDisplay="m13_x"
        pack="observer-only"
      />,
    )
    expect(screen.getByTestId('presence-line').textContent).toBe('your witness is live')
    const root = screen.getByTestId('witness-respiration')
    expect(root.getAttribute('data-presence-tone')).toBe('live')
    expect(root.getAttribute('data-fabricated-liveness')).toBe('false')
  })
})

describe('ReceiptReveal choreography + dignity', () => {
  it('T-SV-8: choreographyVisibleThrough pure', () => {
    expect(choreographyVisibleThrough(0)).toEqual(['SETTLE'])
    expect(choreographyVisibleThrough(2)).toEqual(['SETTLE', 'SURFACES', 'HONESTY'])
    expect(choreographyVisibleThrough(9)).toEqual([
      'SETTLE', 'SURFACES', 'HONESTY', 'SHARE_SPLIT',
    ])
  })

  it('T-SV-6: forceComplete shows all stages; verdicts static attrs', () => {
    render(
      <ReceiptReveal
        model={{ ...receiptPartial, _present: true }}
        forceComplete
      />,
    )
    expect(screen.getByTestId('stage-SETTLE')).toBeTruthy()
    expect(screen.getByTestId('stage-SURFACES')).toBeTruthy()
    expect(screen.getByTestId('stage-HONESTY')).toBeTruthy()
    expect(screen.getByTestId('stage-SHARE_SPLIT')).toBeTruthy()
    const root = screen.getByTestId('receipt-reveal')
    expect(root.getAttribute('data-verdict-animated')).toBe('false')
    expect(screen.getByTestId('surface-posp').getAttribute('data-tone')).toBe('partial')
    expect(screen.getByTestId('surface-kas').getAttribute('data-tone')).toBe('hygiene')
    expect(screen.getByTestId('copy-share')).toBeTruthy()
    expect(screen.getByTestId('download-share')).toBeTruthy()
  })

  it('T-SV-7: HYGIENE line is non-shaming', () => {
    render(
      <ReceiptReveal
        model={{ ...receiptPartial, _present: true }}
        forceComplete
      />,
    )
    const kas = screen.getByTestId('surface-kas')
    expect(kas.textContent).toMatch(/not a player failure/i)
    expect(kas.textContent).not.toMatch(/you failed/i)
  })
})

describe('BirthCeremonyMap', () => {
  it('T-SV-9: stages + ROI overlay hint', () => {
    render(<BirthCeremonyMap model={{ ...ceremonyProv, _present: true }} />)
    expect(screen.getByTestId('ceremony-stage-port').getAttribute('data-status')).toBe('done')
    expect(screen.getByTestId('ceremony-stage-controller').getAttribute('data-status')).toBe('current')
    expect(screen.getByTestId('roi-overlay-hint').textContent).toMatch(/CLI remains the writer/i)
  })
})

describe('StreamView integration', () => {
  it('T-SV-10: initial LIVE → mode STREAM + noMock rails', () => {
    wrap(
      <StreamView
        initial={{
          stream: normalizeStreamModel(streamLive),
          status: { freshness_class: 'LIVE', witness_live: true, _source: 'ok' },
          ceremony: { ...ceremonyProv, ceremony_complete: true, _present: true },
          receipt: { _present: false },
        }}
        enabled={false}
      />,
    )
    const root = screen.getByTestId('stream-view')
    expect(root.getAttribute('data-mock')).toBe('false')
    expect(root.getAttribute('data-fabricated-liveness')).toBe('false')
    expect(root.getAttribute('data-signing-material')).toBe('false')
    expect(root.getAttribute('data-mode')).toBe('STREAM')
    expect(screen.getByTestId('presence-line').textContent).toBe('your witness is live')
  })

  it('T-SV-11: deliberately_absent includes crop_counts and fps', () => {
    const m = normalizeStreamModel(streamLive)
    expect(m.deliberately_absent).toContain('crop_counts')
    expect(m.deliberately_absent).toContain('fps')
  })
})
