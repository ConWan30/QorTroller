/**
 * Phase O4-VPM-INT Stream C — VpmGrammarVerifier (Layer 3) tests.
 *
 * T-VPM-C-GRAMMAR-1: FROZEN signature matrix matches Python canonical
 *                    VISUAL_STATE_SIGNATURES (scripts/vpm_visual_grammar.py)
 * T-VPM-C-GRAMMAR-2: verifyVpmGrammar(htmlText, state) returns ok=true
 *                    when all canonical substrings + meta + aria present
 * T-VPM-C-GRAMMAR-3: missing one signature substring -> ok=false +
 *                    missing_signatures populated
 * T-VPM-C-GRAMMAR-4: missing <meta name="vpm-visual-state"> -> missing_meta=true
 * T-VPM-C-GRAMMAR-5: missing role="status" aria block -> missing_aria=true
 * T-VPM-C-GRAMMAR-6: unknown declared_state -> ok=false with helpful reason
 * T-VPM-C-GRAMMAR-7: empty htmlText -> ok=false (treated as missing)
 * T-VPM-C-GRAMMAR-8: per-state happy-path coverage — for each of 6
 *                    FROZEN visual states, a minimal HTML carrying that
 *                    state's signature passes
 */
import { describe, it, expect } from 'vitest'
import {
  verifyVpmGrammar,
  VISUAL_STATE_SIGNATURES_FROZEN,
} from '../components/VpmGrammarVerifier'


// Helper: build a minimal HTML body that contains the canonical
// signature substrings for `state` + meta + aria, so verifyVpmGrammar
// returns ok=true.
function _minimalCompliantHtml(state) {
  const sigs = VISUAL_STATE_SIGNATURES_FROZEN[state]
  return (
    '<!DOCTYPE html><html><head>' +
    `<meta name="vpm-visual-state" content="${state}">` +
    '</head><body>' +
    `<div role="status">${state.toUpperCase()}</div>` +
    sigs.map((s) => `<span>${s}</span>`).join('') +
    '</body></html>'
  )
}


describe('VpmGrammarVerifier (Layer 3 Anti-Hype Visual Grammar)', () => {
  it('T-VPM-C-GRAMMAR-1: FROZEN signature matrix matches Python canonical', () => {
    expect(VISUAL_STATE_SIGNATURES_FROZEN.live).toEqual([
      'class="vpm-saturation-class"',
      'data-vpm-visual-state="live"',
    ])
    expect(VISUAL_STATE_SIGNATURES_FROZEN['dry-run']).toEqual([
      'class="vpm-stripe-mask"',
      'id="vpm-stripe-pattern"',
      'data-vpm-visual-state="dry-run"',
    ])
    expect(VISUAL_STATE_SIGNATURES_FROZEN.emulated).toEqual([
      'class="vpm-body vpm-emulated"',
      'filter: grayscale(100%)',
      'data-vpm-visual-state="emulated"',
    ])
    expect(VISUAL_STATE_SIGNATURES_FROZEN['frozen-disabled']).toEqual([
      'class="vpm-lock-icon"',
      'data-vpm-visual-state="frozen-disabled"',
    ])
    expect(VISUAL_STATE_SIGNATURES_FROZEN.revoked).toEqual([
      'class="vpm-redacted-banner"',
      'text-decoration: line-through',
      'data-vpm-visual-state="revoked"',
    ])
    expect(VISUAL_STATE_SIGNATURES_FROZEN.unverified).toEqual([
      'repeating-linear-gradient',
      '#d65b78',
      '#020408',
      'data-vpm-visual-state="unverified"',
    ])
    expect(Object.isFrozen(VISUAL_STATE_SIGNATURES_FROZEN)).toBe(true)
  })

  it('T-VPM-C-GRAMMAR-2: ok=true on compliant HTML for state=live', () => {
    const html = _minimalCompliantHtml('live')
    const result = verifyVpmGrammar(html, 'live')
    expect(result.ok).toBe(true)
    expect(result.declared_state).toBe('live')
    expect(result.missing_signatures).toEqual([])
    expect(result.missing_meta).toBe(false)
    expect(result.missing_aria).toBe(false)
  })

  it('T-VPM-C-GRAMMAR-3: missing one signature substring -> ok=false', () => {
    let html = _minimalCompliantHtml('dry-run')
    // Strip the stripe-mask signature substring (simulating compiler drift)
    html = html.replace('class="vpm-stripe-mask"', 'class="some-other-mask"')
    const result = verifyVpmGrammar(html, 'dry-run')
    expect(result.ok).toBe(false)
    expect(result.missing_signatures).toContain('class="vpm-stripe-mask"')
    expect(result.reason).toContain('missing signature substrings')
  })

  it('T-VPM-C-GRAMMAR-4: missing <meta name="vpm-visual-state"> -> ok=false', () => {
    let html = _minimalCompliantHtml('live')
    html = html.replace('<meta name="vpm-visual-state"', '<meta name="other-meta-tag"')
    const result = verifyVpmGrammar(html, 'live')
    expect(result.ok).toBe(false)
    expect(result.missing_meta).toBe(true)
    expect(result.reason).toContain('missing <meta name="vpm-visual-state">')
  })

  it('T-VPM-C-GRAMMAR-5: missing role="status" aria block -> ok=false', () => {
    let html = _minimalCompliantHtml('live')
    html = html.replace('role="status"', 'role="alert"')
    const result = verifyVpmGrammar(html, 'live')
    expect(result.ok).toBe(false)
    expect(result.missing_aria).toBe(true)
    expect(result.reason).toContain('missing role="status" aria block')
  })

  it('T-VPM-C-GRAMMAR-6: unknown declared_state -> ok=false with helpful reason', () => {
    const html = _minimalCompliantHtml('live')
    const result = verifyVpmGrammar(html, 'psychedelic')
    expect(result.ok).toBe(false)
    expect(result.declared_state).toBe('psychedelic')
    expect(result.reason).toContain('unknown declared visual_state: psychedelic')
  })

  it('T-VPM-C-GRAMMAR-7: empty HTML body -> ok=false', () => {
    const result = verifyVpmGrammar('', 'live')
    expect(result.ok).toBe(false)
    expect(result.reason).toBe('empty HTML body')
  })

  it.each(['live', 'dry-run', 'emulated', 'frozen-disabled', 'revoked', 'unverified'])(
    'T-VPM-C-GRAMMAR-8 per-state happy path: state=%s passes',
    (state) => {
      const html = _minimalCompliantHtml(state)
      const result = verifyVpmGrammar(html, state)
      expect(result.ok).toBe(true)
      expect(result.declared_state).toBe(state)
    }
  )
})
