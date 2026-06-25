import { describe, it, expect } from 'vitest'
import { vpmVisual, laneVisual, textureCss } from './vpmVisual'
import { explainFor, EXPLAIN } from '../explain'

describe('vpmVisual — honesty-as-aesthetic (never green unless proven)', () => {
  it('only `live` is the proven/glow treatment', () => {
    const live = vpmVisual('live')
    expect(live.glow).toBe(true)
    expect(live.label).toBe('LIVE')
  })

  it('unproven states never glow and carry a warning texture', () => {
    for (const s of ['unverified', 'revoked']) {
      const v = vpmVisual(s)
      expect(v.glow).toBe(false)
      expect(v.texture).toBe('banded')
    }
  })

  it('preview/sim states are striped, not live', () => {
    expect(vpmVisual('dry-run').texture).toBe('striped')
    expect(vpmVisual('emulated').texture).toBe('striped')
    expect(vpmVisual('dry-run').glow).toBe(false)
  })

  it('unknown / malformed / missing state falls back to UNKNOWN, never live', () => {
    for (const s of [undefined, null, 'totally-made-up', 42]) {
      const v = vpmVisual(s)
      expect(v.label).toBe('UNKNOWN')
      expect(v.glow).toBe(false)
    }
  })

  it('case-insensitive on the frozen vocabulary', () => {
    expect(vpmVisual('LIVE').label).toBe('LIVE')
  })
})

describe('laneVisual — BCRA lanes share the honesty language', () => {
  it('connected glows; degraded/disconnected/unknown do not', () => {
    expect(laneVisual('connected').glow).toBe(true)
    expect(laneVisual('degraded').glow).toBe(false)
    expect(laneVisual('disconnected').glow).toBe(false)
    expect(laneVisual('unknown').glow).toBe(false)
  })
  it('unknown fallback for anything off-vocabulary', () => {
    expect(laneVisual('nonsense').label).toBe('UNKNOWN')
  })
})

describe('textureCss', () => {
  it('returns a gradient for textured states and transparent for none', () => {
    expect(textureCss('striped', '#fff')).toContain('repeating-linear-gradient')
    expect(textureCss('none', '#fff')).toBe('transparent')
  })
})

describe('explain registry — every entry carries the honest-limit line', () => {
  it('every term has is / you / limit', () => {
    for (const e of Object.values(EXPLAIN)) {
      expect(e.is && e.you && e.limit).toBeTruthy()
    }
  })
  it('explainFor is case-insensitive and null-safe', () => {
    expect(explainFor('PoCP')).toBeTruthy()
    expect(explainFor('nope')).toBeNull()
    expect(explainFor(undefined)).toBeNull()
  })
})
