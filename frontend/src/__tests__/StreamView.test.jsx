/**
 * StreamView SPA tests (A2A-PKG round-13 · PKG-UI React + STREAM-2 node face).
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
 *   T-SV-12 STREAM-2 NodeIdentityMark derived-not-minted + unformed
 *   T-SV-13 STREAM-2 ContributionPulse PENDING never paints early on-chain
 *   T-SV-14 STREAM-2 ScoreMoment provenance tags MEASURED / OPERATOR-REPORTED
 *   T-SV-15 STREAM-2 StreamView LIVE fixture paints node face + blink ABSENT fires
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
  NodeIdentityMark,
  ContributionPulse,
  ScoreMoment,
  WitnessBlink,
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
    expect(m.novelty).toMatch(/witness_respiration/)
    expect(m.fabricated_liveness).toBe(false)
    // STREAM-2 pass-through
    expect(m.on_screen.node_id_short).toBe('a1b2c3d4e5f6')
    expect(m.on_screen.node_identity?.present).toBe(true)
    expect(m.on_screen.kills_seen).toBe(3)
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

describe('STREAM-2 node face surfaces', () => {
  it('T-SV-12: NodeIdentityMark derived claim + unformed honesty', () => {
    const { unmount } = render(
      <NodeIdentityMark
        identity={{
          present: true,
          node_id_short: 'deadbeefcafe',
          claim_language: 'derived_not_minted',
          device_id_short: '581a836c98b3',
          device_on_chain_evidence: true,
        }}
      />,
    )
    expect(screen.getByTestId('node-id-short').textContent).toBe('deadbeefcafe')
    expect(screen.getByTestId('node-claim').textContent).toMatch(/derived/i)
    expect(screen.getByTestId('node-identity-mark').getAttribute('data-claim')).toBe(
      'derived_not_minted',
    )
    unmount()
    render(<NodeIdentityMark identity={{ present: false, line: 'node identity unformed' }} />)
    expect(screen.getByTestId('node-id-unformed').textContent).toMatch(/unformed/i)
    expect(screen.getByTestId('node-identity-mark').getAttribute('data-present')).toBe('false')
  })

  it('T-SV-13: ContributionPulse PENDING never claims on-chain without tx', () => {
    render(
      <ContributionPulse
        contribution={{
          present: true,
          entry_count: 1,
          chain_intact: true,
          recent: [{
            session_id_short: 'sess_a',
            posp_verdict: 'SYNCHRONIZED',
            w3s_attested: false,
            lifecycle: 'PENDING',
            anchored: false,
            anchor_tx_short: null,
          }],
        }}
      />,
    )
    const row = screen.getByTestId('contribution-row-0')
    expect(row.getAttribute('data-lifecycle')).toBe('PENDING')
    expect(row.getAttribute('data-anchored')).toBe('false')
    expect(row.textContent).not.toMatch(/on-chain/i)
    // Fake ANCHORED without tx demotes to PENDING in render honesty
    const { unmount } = render(
      <ContributionPulse
        contribution={{
          present: true,
          entry_count: 1,
          chain_intact: true,
          recent: [{
            session_id_short: 'sess_b',
            lifecycle: 'ANCHORED',
            anchored: true,
            anchor_tx_short: null,
          }],
        }}
      />,
    )
    // second mount — last contribution-row-0 is the demoted one
    const rows = screen.getAllByTestId('contribution-row-0')
    const demoted = rows[rows.length - 1]
    expect(demoted.getAttribute('data-lifecycle')).toBe('PENDING')
    unmount()
  })

  it('T-SV-14: ScoreMoment provenance tags + UNSCORED dignity', () => {
    render(
      <ScoreMoment
        scorecard={{
          present: true,
          label: 'm13',
          recall_status: 'UNSCORED',
          authored: { value: 8, source: 'MEASURED' },
          reported: { value: null, source: 'OPERATOR-REPORTED' },
          kas_verdict: 'AUTHORED_SESSION',
          posp_verdict: 'SYNCHRONIZED',
          dignity_tone: 'honest_null',
        }}
      />,
    )
    expect(screen.getByTestId('tag-authored').getAttribute('data-source')).toBe('MEASURED')
    expect(screen.getByTestId('tag-reported').getAttribute('data-source')).toBe('OPERATOR-REPORTED')
    expect(screen.getByTestId('score-reported-value').textContent).toMatch(/UNSCORED/)
    expect(screen.getByTestId('score-moment').getAttribute('data-recall-status')).toBe('UNSCORED')
    expect(screen.getByTestId('score-authored-value').textContent).toMatch(/8/)
  })

  it('T-SV-15: StreamView LIVE paints node face + fresh_fires ABSENT', () => {
    wrap(
      <StreamView
        initial={{
          stream: normalizeStreamModel(streamLive),
          status: {
            freshness_class: 'LIVE',
            witness_live: true,
            node_identity: streamLive.on_screen.node_identity,
            contribution: streamLive.on_screen.contribution,
            scorecard: streamLive.on_screen.scorecard,
            witness_blink: streamLive.on_screen.witness_blink,
            _source: 'ok',
          },
          ceremony: { ...ceremonyProv, ceremony_complete: true, _present: true },
          receipt: { _present: false },
        }}
        enabled={false}
      />,
    )
    expect(screen.getByTestId('stream-node-face')).toBeTruthy()
    expect(screen.getByTestId('node-id-short').textContent).toBe('a1b2c3d4e5f6')
    expect(screen.getByTestId('contribution-pulse').getAttribute('data-present')).toBe('true')
    expect(screen.getByTestId('score-moment').getAttribute('data-recall-status')).toBe('UNSCORED')
    expect(screen.getByTestId('witness-blink').getAttribute('data-kills-seen')).toBe('3')
    expect(screen.getByTestId('fresh-fires-absent').textContent).toMatch(/ABSENT/i)
    expect(screen.getByTestId('witness-blink').getAttribute('data-fresh-fires')).toBe('ABSENT')
  })

  it('T-SV-15b: WitnessBlink absent sink stays honest', () => {
    render(<WitnessBlink blink={{ kills_seen: null, fresh_fires_status: 'ABSENT', line: 'unknown' }} />)
    expect(screen.getByTestId('witness-blink').getAttribute('data-kills-seen')).toBe('absent')
  })
})
