/**
 * Phase O4-VPM-INT Stream C — VpmIframe component tests.
 *
 * T-VPM-C-IFRAME-1: FROZEN sandbox attribute literal value matches
 *                   Phase O4 plan §3 Stream C.3 spec exactly
 * T-VPM-C-IFRAME-2: small htmlText uses srcdoc; renders with sandbox+
 *                   referrerPolicy=no-referrer + loading=lazy
 * T-VPM-C-IFRAME-3: large htmlText (>= 500 KB) falls through to src=
 * T-VPM-C-IFRAME-4: only src or srcdoc — no other allow-* features
 *                   expanded in sandbox attribute
 */
import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import {
  VpmIframe,
  VPM_IFRAME_SANDBOX,
  VPM_IFRAME_SRCDOC_LIMIT_BYTES,
} from '../components/VpmIframe'


describe('VpmIframe', () => {
  it('T-VPM-C-IFRAME-1: FROZEN sandbox literal matches plan §3 Stream C.3 spec', () => {
    // Per plan §3 Stream C.3 commentary + candidate INV-VPM-SANDBOX-001
    expect(VPM_IFRAME_SANDBOX).toBe('allow-scripts allow-same-origin')
    // No expansion: must NOT include allow-forms / allow-popups /
    // allow-top-navigation / allow-modals / allow-pointer-lock /
    // allow-presentation / allow-downloads
    const forbidden = [
      'allow-forms',
      'allow-popups',
      'allow-top-navigation',
      'allow-modals',
      'allow-pointer-lock',
      'allow-presentation',
      'allow-downloads',
      'allow-storage-access-by-user-activation',
    ]
    for (const flag of forbidden) {
      expect(VPM_IFRAME_SANDBOX.includes(flag)).toBe(false)
    }
  })

  it('T-VPM-C-IFRAME-2: small htmlText uses srcdoc with FROZEN sandbox', () => {
    const small = '<html><body>tiny vpm</body></html>'
    const { container } = render(
      <VpmIframe htmlText={small} title="small-test" />
    )
    const iframe = container.querySelector('iframe[data-vpm-iframe="srcdoc"]')
    expect(iframe).not.toBeNull()
    expect(iframe.getAttribute('sandbox')).toBe('allow-scripts allow-same-origin')
    expect(iframe.getAttribute('referrerpolicy')).toBe('no-referrer')
    expect(iframe.getAttribute('loading')).toBe('lazy')
    // srcdoc carries the HTML content
    expect(iframe.getAttribute('srcdoc') || iframe.srcdoc).toContain('tiny vpm')
  })

  it('T-VPM-C-IFRAME-3: large htmlText (>=500 KB) falls through to src=', () => {
    expect(VPM_IFRAME_SRCDOC_LIMIT_BYTES).toBe(500 * 1024)
    // Build 600 KB blob to trigger fallback
    const big = 'x'.repeat(600 * 1024)
    const { container } = render(
      <VpmIframe
        htmlText={big}
        artifactUrl="/operator/operator/vpm-artifact/abc123"
        title="big-test"
      />
    )
    const iframe = container.querySelector('iframe[data-vpm-iframe="src"]')
    expect(iframe).not.toBeNull()
    expect(iframe.getAttribute('src')).toBe('/operator/operator/vpm-artifact/abc123')
    expect(iframe.getAttribute('sandbox')).toBe('allow-scripts allow-same-origin')
  })

  it('T-VPM-C-IFRAME-4: src-only path (no htmlText) renders with sandbox', () => {
    const { container } = render(
      <VpmIframe
        artifactUrl="/operator/operator/vpm-artifact/deadbeef"
        title="src-only"
      />
    )
    const iframe = container.querySelector('iframe[data-vpm-iframe="src"]')
    expect(iframe).not.toBeNull()
    expect(iframe.getAttribute('sandbox')).toBe('allow-scripts allow-same-origin')
    expect(iframe.getAttribute('src')).toBe('/operator/operator/vpm-artifact/deadbeef')
  })
})
