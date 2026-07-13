/**
 * PKG-UI-02 — ReceiptReveal
 * Choreography SETTLE → SURFACES → HONESTY → SHARE_SPLIT.
 *
 * ANIMATES: stage chrome (copy fades, panel layout).
 * NEVER animates: verdict strings, tone colors, progressive "checking…",
 * green-check theater, crop counts. Verdicts render instantly and statically
 * the moment their stage is visible (dignity, not suspense-theater).
 */
import React, { useEffect, useMemo, useState, useCallback } from 'react'
import {
  STREAM_PAL, STREAM_FONTS, VERDICT_TONE_COLOR, CHOREOGRAPHY_STAGES,
} from './streamTokens'

const DEFAULT_CHOREO = [
  { stage: 'SETTLE', ms: 400, copy: 'session closed -- sealing the pack' },
  { stage: 'SURFACES', ms: 800, copy: 'presence + authorship + state' },
  { stage: 'HONESTY', ms: 500, copy: 'known gaps disclosed, never hidden' },
  { stage: 'SHARE_SPLIT', ms: 600, copy: 'LOCAL full stays here; SHARE postcard is redacted for strangers' },
]

/**
 * Pure stage index helper (testable).
 * reducedMotion or forceComplete → last stage (all visible).
 */
export function choreographyVisibleThrough(stageIndex, choreography = DEFAULT_CHOREO) {
  const stages = (choreography || DEFAULT_CHOREO).map((c) => c.stage)
  return stages.slice(0, Math.min(stageIndex + 1, stages.length))
}

export function ReceiptReveal({
  model = null,
  /** When true, skip stage delays and show full reveal immediately. */
  forceComplete = false,
  /** Injected clock for tests (ms). */
  nowMs = null,
}) {
  const choreo = model?.choreography?.length ? model.choreography : DEFAULT_CHOREO
  const [stageIdx, setStageIdx] = useState(forceComplete ? choreo.length - 1 : 0)
  const [reduced, setReduced] = useState(false)
  const [copied, setCopied] = useState(null)

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    setReduced(mq.matches)
    const fn = () => setReduced(mq.matches)
    mq.addEventListener?.('change', fn)
    return () => mq.removeEventListener?.('change', fn)
  }, [])

  // Advance stages by declared ms; skip entirely under reduced-motion / forceComplete.
  useEffect(() => {
    if (forceComplete || reduced) {
      setStageIdx(choreo.length - 1)
      return undefined
    }
    setStageIdx(0)
    let i = 0
    let timer
    const tick = () => {
      const ms = Number(choreo[i]?.ms) || 400
      timer = setTimeout(() => {
        i += 1
        if (i < choreo.length) {
          setStageIdx(i)
          tick()
        }
      }, ms)
    }
    tick()
    return () => clearTimeout(timer)
  }, [choreo, forceComplete, reduced, nowMs])

  const visible = useMemo(
    () => new Set(choreographyVisibleThrough(stageIdx, choreo)),
    [stageIdx, choreo],
  )

  const surfaces = model?.surfaces || {}
  const ft = model?.f_t66b1 || {
    code: 'F-T66B-1',
    line: 'incomplete -- not hidden. Zero-false-read holds.',
    status: 'OPEN',
  }
  const localBody = model?.local?.body_text || ''
  const shareBody = model?.share?.body_text || ''

  const copyShare = useCallback(async () => {
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(shareBody)
        setCopied('share')
        setTimeout(() => setCopied(null), 1500)
      }
    } catch {
      setCopied('fail')
    }
  }, [shareBody])

  const downloadShare = useCallback(() => {
    const blob = new Blob([shareBody || ''], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `session_receipt_${model?.session_label || 'session'}.share.md`
    a.click()
    URL.revokeObjectURL(url)
  }, [shareBody, model?.session_label])

  if (!model || model._present === false) {
    return (
      <div data-testid="receipt-reveal-absent" style={{ color: STREAM_PAL.dim, fontFamily: STREAM_FONTS.mono, fontSize: 12 }}>
        no receipt reveal yet — run <code>qortroller stop</code> / <code>receipt --write-ui</code>
      </div>
    )
  }

  return (
    <div
      data-testid="receipt-reveal"
      data-stage={choreo[stageIdx]?.stage || 'SETTLE'}
      data-verdict-animated="false"
      style={{
        fontFamily: STREAM_FONTS.mono,
        color: STREAM_PAL.ink,
        maxWidth: 720,
      }}
    >
      <div style={{
        fontSize: 11, letterSpacing: '0.12em', textTransform: 'uppercase',
        color: STREAM_PAL.amber, marginBottom: 16,
      }}>
        Receipt Reveal · {model.session_label || 'session'}
      </div>

      {/* SETTLE — ambient copy only */}
      {visible.has('SETTLE') && (
        <div data-testid="stage-SETTLE" style={{ color: STREAM_PAL.dim, fontSize: 13, marginBottom: 18 }}>
          {choreo.find((c) => c.stage === 'SETTLE')?.copy || 'session closed'}
        </div>
      )}

      {/* SURFACES — verdicts INSTANT + STATIC when visible */}
      {visible.has('SURFACES') && (
        <div data-testid="stage-SURFACES" style={{ display: 'grid', gap: 10, marginBottom: 20 }}>
          {['posp', 'kas', 'v3'].map((key) => {
            const s = surfaces[key]
            if (!s) return null
            const tone = s.tone || 'absent'
            const col = VERDICT_TONE_COLOR[tone] || STREAM_PAL.dim
            return (
              <div
                key={key}
                data-testid={`surface-${key}`}
                data-tone={tone}
                data-verdict={s.verdict || ''}
                style={{
                  border: `1px solid ${STREAM_PAL.bd}`,
                  borderLeft: `3px solid ${col}`,
                  borderRadius: 6,
                  padding: '10px 12px',
                  background: STREAM_PAL.void1,
                }}
              >
                {/* Verdict line: no CSS transition on color/text — dignity rail */}
                <div style={{ color: col, fontSize: 13, transition: 'none' }}>
                  {s.line || `${key}: ${s.verdict || '—'}`}
                </div>
                {s.dignity ? (
                  <div style={{ color: STREAM_PAL.dim, fontSize: 10, marginTop: 4, letterSpacing: '0.08em' }}>
                    {s.dignity}
                  </div>
                ) : null}
              </div>
            )
          })}
        </div>
      )}

      {/* HONESTY — F-T66B-1 always static text */}
      {visible.has('HONESTY') && (
        <div
          data-testid="stage-HONESTY"
          data-ft66b1={ft.code || 'F-T66B-1'}
          style={{
            border: `1px solid ${STREAM_PAL.bd}`,
            borderRadius: 6,
            padding: '12px 14px',
            marginBottom: 20,
            background: 'rgba(240,168,104,0.06)',
          }}
        >
          <div style={{ color: STREAM_PAL.amber, fontSize: 11, letterSpacing: '0.1em', marginBottom: 6 }}>
            {ft.code || 'F-T66B-1'} · {ft.status || 'OPEN'}
          </div>
          <div style={{ color: STREAM_PAL.ink, fontSize: 12, transition: 'none' }}>
            {ft.line}
          </div>
        </div>
      )}

      {/* SHARE_SPLIT — LOCAL full | SHARE redacted; export affordances */}
      {visible.has('SHARE_SPLIT') && (
        <div data-testid="stage-SHARE_SPLIT" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <div data-testid="local-surface" style={panelStyle}>
            <div style={panelHead}>LOCAL · full</div>
            <pre style={preStyle}>{localBody || '(empty)'}</pre>
          </div>
          <div data-testid="share-surface" style={panelStyle}>
            <div style={panelHead}>SHARE · redacted</div>
            <pre style={preStyle}>{shareBody || '(empty)'}</pre>
            <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
              <button
                type="button"
                data-testid="copy-share"
                onClick={copyShare}
                style={btnStyle}
              >
                {copied === 'share' ? 'copied' : 'copy postcard'}
              </button>
              <button
                type="button"
                data-testid="download-share"
                onClick={downloadShare}
                style={btnStyle}
              >
                download .share.md
              </button>
            </div>
            <div style={{ color: STREAM_PAL.dim, fontSize: 10, marginTop: 8 }}>
              stranger verify: <code>qortroller verify --share …</code>
              {model.share?.shows_crop_counts === false ? ' · no crop counts' : ''}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

const panelStyle = {
  border: `1px solid ${STREAM_PAL.bd}`,
  borderRadius: 6,
  padding: 12,
  background: STREAM_PAL.void1,
  minHeight: 120,
}
const panelHead = {
  color: STREAM_PAL.amber,
  fontSize: 10,
  letterSpacing: '0.12em',
  textTransform: 'uppercase',
  marginBottom: 8,
}
const preStyle = {
  margin: 0,
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-word',
  fontSize: 10,
  lineHeight: 1.5,
  color: STREAM_PAL.ink,
  maxHeight: 220,
  overflow: 'auto',
  transition: 'none',
}
const btnStyle = {
  fontFamily: STREAM_FONTS.mono,
  fontSize: 10,
  letterSpacing: '0.06em',
  textTransform: 'uppercase',
  color: STREAM_PAL.cyan,
  background: 'transparent',
  border: `1px solid ${STREAM_PAL.bd}`,
  borderRadius: 4,
  padding: '6px 10px',
  cursor: 'pointer',
}

export { CHOREOGRAPHY_STAGES, DEFAULT_CHOREO }
export default ReceiptReveal
