/**
 * Phase O4-VPM-INT Stream C.3 — VpmIframe
 *
 * Sandboxed iframe for rendering a VPM artifact's HTML. The sandbox
 * attribute is LITERAL per Phase O4 plan section 3 Stream C.3 / candidate
 * INV-VPM-SANDBOX-001:
 *
 *   sandbox="allow-scripts allow-same-origin"
 *
 * `allow-scripts` is required (VPMs render inline JS for procedural art
 * + integrity-label hash recompute hooks).
 * `allow-same-origin` is required to read the iframe contentDocument via
 * postMessage / direct DOM access for the Layer 3 grammar verifier
 * (VpmGrammarVerifier reads the iframe DOM after onLoad).
 *
 * NOT included: allow-forms, allow-popups, allow-top-navigation,
 * allow-modals, allow-pointer-lock, allow-presentation, allow-downloads.
 * A VPM that triggers any of those features visibly fails in the
 * sandbox — which is the intended fail-loud behavior per the plan §3
 * Stream C.3 commentary.
 *
 * Two source modes:
 *   - When `htmlText` is provided AND < 500 KB, uses srcdoc (renders
 *     entirely in-memory; no network fetch).
 *   - Otherwise, uses src={artifactUrl} which goes to
 *     /operator/vpm-artifact/{commitmentHex} (bridge serves HTML with
 *     FROZEN CSP headers per Phase O4 plan section 3 Stream B.2).
 *
 * The onLoad callback fires when the iframe finishes rendering and
 * receives the iframe element reference — VpmGrammarVerifier consumes
 * this to read contentDocument and run the 6-state DOM signature
 * assertions.
 */
import { useRef, useEffect } from 'react'

const SRCDOC_SIZE_LIMIT = 500 * 1024  // 500 KB per plan §3 Stream C.3

export function VpmIframe({
  htmlText,
  artifactUrl,
  onIframeReady,
  width  = '100%',
  height = '100%',
  title  = 'VPM Artifact',
}) {
  const ref = useRef(null)
  const useSrcdoc = typeof htmlText === 'string' && htmlText.length < SRCDOC_SIZE_LIMIT

  // Fire ready callback once iframe has loaded its content. The iframe's
  // load event fires after both srcdoc and src render paths.
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const handler = () => {
      if (typeof onIframeReady === 'function') {
        try {
          onIframeReady(el)
        } catch {
          // Caller errors must not crash the iframe wrapper
        }
      }
    }
    el.addEventListener('load', handler)
    // If iframe is already complete (srcdoc cached path), fire once after mount.
    if (useSrcdoc && el.contentDocument && el.contentDocument.readyState === 'complete') {
      // Defer to next tick to keep ordering consistent
      setTimeout(handler, 0)
    }
    return () => {
      el.removeEventListener('load', handler)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [htmlText, artifactUrl, useSrcdoc])

  // FROZEN sandbox attribute. Do NOT modify without VBDIP-0002 Appendix B
  // amendment + INV-VPM-SANDBOX-001 governance ceremony per Phase O4
  // plan section 4.1.
  const sandboxAttr = "allow-scripts allow-same-origin"

  if (useSrcdoc) {
    return (
      <iframe
        ref={ref}
        data-vpm-iframe="srcdoc"
        sandbox={sandboxAttr}
        srcDoc={htmlText}
        title={title}
        referrerPolicy="no-referrer"
        loading="lazy"
        style={{
          width,
          height,
          border: 'none',
          background: '#020408',
          display: 'block',
        }}
      />
    )
  }

  return (
    <iframe
      ref={ref}
      data-vpm-iframe="src"
      sandbox={sandboxAttr}
      src={artifactUrl}
      title={title}
      referrerPolicy="no-referrer"
      loading="lazy"
      style={{
        width,
        height,
        border: 'none',
        background: '#020408',
        display: 'block',
      }}
    />
  )
}

// Exported for tests + grammar verifier reuse
export const VPM_IFRAME_SANDBOX = "allow-scripts allow-same-origin"
export const VPM_IFRAME_SRCDOC_LIMIT_BYTES = SRCDOC_SIZE_LIMIT
