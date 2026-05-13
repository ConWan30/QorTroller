/**
 * Phase O4-VPM-INT Stream C.5 — VpmGrammarVerifier (Layer 3)
 *
 * Layer 3 of the three-layer Anti-Hype Visual Grammar enforcement per
 * Phase O4 plan section 5.2:
 *
 *   Layer 1 (Compiler-side, Python):  Stream A.1+A.2 — each compiler's
 *                                     test band asserts the emitted HTML
 *                                     contains the canonical DOM signature
 *                                     for its declared visual_state.
 *   Layer 2 (Bridge-side, Python):    Stream B.6 — vpm-audit-status
 *                                     endpoint surfaces visual grammar
 *                                     coverage across all 6 compilers.
 *   Layer 3 (Frontend-side, this):    Reads the rendered iframe DOM via
 *                                     contentDocument; runs the
 *                                     six-state DOM signature assertions
 *                                     client-side. Failure surfaces as
 *                                     a red badge on the registry row.
 *
 * The FROZEN signature matrix mirrors
 * scripts/vpm_visual_grammar.py:VISUAL_STATE_SIGNATURES byte-for-byte.
 * If the Python-side signatures change, this JavaScript constant MUST
 * update atomically.
 *
 * What this catches:
 *   - Compiler bug that drops the stripe-mask for dry-run state
 *   - Manifest-vs-DOM forgery: row claims visual_state="live" but emitted
 *     HTML actually shows the dry-run stripe pattern (overclaim attempt)
 *   - Browser-render-time tamper (extension injection, MITM rewrite)
 *   - Cached HTML drifted from current visual grammar requirements
 *
 * The verifier runs ONCE per iframe load. Re-render of the parent
 * component does not trigger re-verification (deterministic input ->
 * deterministic check; no need to repeat).
 */
import { useEffect, useState } from 'react'
import { FONTS } from '../shared/design/tokens'

// FROZEN signature matrix mirrored from scripts/vpm_visual_grammar.py
// VISUAL_STATE_SIGNATURES. Each entry is the tuple of substrings ALL of
// which MUST appear in the emitted VPM HTML body for that state to be
// correctly rendered. Drift between this constant and the Python module
// surfaces as a Layer 3 grammar violation in the test bands.
const VISUAL_STATE_SIGNATURES_FROZEN = Object.freeze({
  'live': [
    'class="vpm-saturation-class"',
    'data-vpm-visual-state="live"',
  ],
  'dry-run': [
    'class="vpm-stripe-mask"',
    'id="vpm-stripe-pattern"',
    'data-vpm-visual-state="dry-run"',
  ],
  'emulated': [
    'class="vpm-body vpm-emulated"',
    'filter: grayscale(100%)',
    'data-vpm-visual-state="emulated"',
  ],
  'frozen-disabled': [
    'class="vpm-lock-icon"',
    'data-vpm-visual-state="frozen-disabled"',
  ],
  'revoked': [
    'class="vpm-redacted-banner"',
    'text-decoration: line-through',
    'data-vpm-visual-state="revoked"',
  ],
  'unverified': [
    'repeating-linear-gradient',
    '#d65b78',
    '#020408',
    'data-vpm-visual-state="unverified"',
  ],
})

const META_TAG_REQUIRED  = '<meta name="vpm-visual-state"'
const ARIA_ROLE_REQUIRED = 'role="status"'


/**
 * Run the Layer 3 grammar check against the inner HTML of an iframe
 * document. Returns:
 *
 *   {
 *     ok:                 bool,
 *     declared_state:     string ('live' / 'dry-run' / etc.) | null,
 *     missing_signatures: string[],
 *     missing_meta:       bool,
 *     missing_aria:       bool,
 *     reason:             string (human-readable summary)
 *   }
 *
 * Exported so unit tests can exercise it with a string of HTML directly
 * (no iframe required).
 */
export function verifyVpmGrammar(htmlText, declaredState) {
  if (typeof htmlText !== 'string' || htmlText.length === 0) {
    return {
      ok: false,
      declared_state: declaredState || null,
      missing_signatures: [],
      missing_meta: true,
      missing_aria: true,
      reason: 'empty HTML body',
    }
  }
  if (!declaredState || !VISUAL_STATE_SIGNATURES_FROZEN[declaredState]) {
    return {
      ok: false,
      declared_state: declaredState || null,
      missing_signatures: [],
      missing_meta: false,
      missing_aria: false,
      reason: `unknown declared visual_state: ${declaredState}`,
    }
  }
  const required = VISUAL_STATE_SIGNATURES_FROZEN[declaredState]
  const missing_signatures = required.filter((sig) => !htmlText.includes(sig))
  const missing_meta = !htmlText.includes(META_TAG_REQUIRED)
  const missing_aria = !htmlText.includes(ARIA_ROLE_REQUIRED)
  const ok = missing_signatures.length === 0 && !missing_meta && !missing_aria
  let reason
  if (ok) {
    reason = `all 6-state signatures + meta + aria markers present for state=${declaredState}`
  } else {
    const parts = []
    if (missing_signatures.length > 0) {
      parts.push(`missing signature substrings: ${missing_signatures.join(', ')}`)
    }
    if (missing_meta)  parts.push('missing <meta name="vpm-visual-state">')
    if (missing_aria) parts.push('missing role="status" aria block')
    reason = parts.join(' | ')
  }
  return {
    ok,
    declared_state: declaredState,
    missing_signatures,
    missing_meta,
    missing_aria,
    reason,
  }
}


/**
 * VpmGrammarVerifier — React component that consumes an iframe ref +
 * the declared visual_state, runs the grammar check on iframe load, and
 * surfaces the result as a colored badge.
 *
 * Props:
 *   iframeRef     — React ref to a mounted <iframe> element
 *   declaredState — the visual_state the manifest claims for this VPM
 *   onResult      — optional callback(result) invoked after check
 */
export function VpmGrammarVerifier({ iframeRef, declaredState, onResult }) {
  const [result, setResult] = useState(null)

  useEffect(() => {
    let cancelled = false
    function runCheck() {
      const el = iframeRef && iframeRef.current
      if (!el) return
      let htmlText = ''
      try {
        const doc = el.contentDocument
        if (doc && doc.documentElement) {
          htmlText = doc.documentElement.outerHTML
        }
      } catch {
        // Cross-origin access denied or detached iframe — treat as
        // unverifiable (badge shows UNVERIFIABLE, not OK).
      }
      const r = htmlText
        ? verifyVpmGrammar(htmlText, declaredState)
        : {
            ok: false,
            declared_state: declaredState,
            missing_signatures: [],
            missing_meta: false,
            missing_aria: false,
            reason: 'iframe contentDocument inaccessible',
          }
      if (!cancelled) {
        setResult(r)
        if (typeof onResult === 'function') {
          try { onResult(r) } catch { /* caller-side errors are non-fatal */ }
        }
      }
    }

    // Run after a microtask to give the iframe time to render
    // (load event may have fired before this component mounts).
    const t = setTimeout(runCheck, 50)

    // Also re-run on iframe load event in case the iframe is still
    // mid-render at mount time.
    const el = iframeRef && iframeRef.current
    if (el) el.addEventListener('load', runCheck)

    return () => {
      cancelled = true
      clearTimeout(t)
      if (el) el.removeEventListener('load', runCheck)
    }
  }, [iframeRef, declaredState])

  if (!result) {
    return (
      <span data-vpm-grammar-status="pending" style={{
        fontFamily:    FONTS.mono,
        fontSize:      10,
        color:         'rgba(200,216,232,0.4)',
      }}>checking grammar…</span>
    )
  }

  const baseStyle = {
    padding:       '2px 8px',
    borderRadius:  4,
    fontFamily:    FONTS.mono,
    fontSize:      10,
    fontWeight:    600,
    letterSpacing: '0.06em',
    border:        '1px solid',
  }
  if (result.ok) {
    return (
      <span data-vpm-grammar-status="ok" style={{
        ...baseStyle,
        background:  '#5bd6a31a',
        color:       '#5bd6a3',
        borderColor: '#5bd6a3',
      }} title={result.reason}>GRAMMAR OK</span>
    )
  }
  // Special-case: iframe inaccessible (e.g. cross-origin or unloaded)
  if (result.reason === 'iframe contentDocument inaccessible') {
    return (
      <span data-vpm-grammar-status="unverifiable" style={{
        ...baseStyle,
        background:  '#7a8a9b1a',
        color:       '#7a8a9b',
        borderColor: '#7a8a9b',
      }} title={result.reason}>UNVERIFIABLE</span>
    )
  }
  // Any other failure path is a hard FAIL — red badge per plan §5.5
  return (
    <span data-vpm-grammar-status="fail" style={{
      ...baseStyle,
      background:  '#d65b781a',
      color:       '#d65b78',
      borderColor: '#d65b78',
    }} title={result.reason}>
      GRAMMAR FAIL
    </span>
  )
}

// Exported for tests + cross-component reuse
export { VISUAL_STATE_SIGNATURES_FROZEN }
