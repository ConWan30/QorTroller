/**
 * STREAM-2 Q3 — ScoreMoment
 * Provenance-tagged score pixels: MEASURED / OPERATOR-REPORTED as design elements.
 * UNSCORED is dignified (never painted as 0). Tags ARE the novelty.
 */
import React from 'react'
import { STREAM_PAL, STREAM_FONTS, VERDICT_TONE_COLOR } from './streamTokens'

function SourceTag({ source, testId }) {
  const s = (source || 'ABSENT').toUpperCase()
  let color = STREAM_PAL.dim
  if (s === 'MEASURED') color = STREAM_PAL.cyan
  else if (s === 'OPERATOR-REPORTED') color = STREAM_PAL.amber
  else if (s === 'DERIVED') color = STREAM_PAL.partial
  return (
    <span
      data-testid={testId}
      data-source={s}
      style={{
        color,
        fontSize: 9,
        letterSpacing: '0.1em',
        border: `1px solid ${color}55`,
        borderRadius: 3,
        padding: '1px 5px',
        marginLeft: 6,
        textTransform: 'uppercase',
      }}
    >
      {s}
    </span>
  )
}

export function ScoreMoment({ scorecard = null }) {
  const present = Boolean(scorecard && scorecard.present)
  const status = scorecard?.recall_status || 'UNSCORED'
  const authored = scorecard?.authored || { value: null, source: 'ABSENT' }
  const reported = scorecard?.reported || { value: null, source: 'ABSENT' }
  const tone = scorecard?.dignity_tone || 'honest_null'
  const toneColor = VERDICT_TONE_COLOR[tone] || STREAM_PAL.dim

  return (
    <div
      data-testid="score-moment"
      data-present={present ? 'true' : 'false'}
      data-recall-status={status}
      data-dignity={tone}
      style={{
        fontFamily: STREAM_FONTS.mono,
        border: `1px solid ${STREAM_PAL.bd}`,
        borderLeft: `3px solid ${toneColor}`,
        borderRadius: 6,
        padding: '12px 14px',
        background: STREAM_PAL.void1,
      }}
    >
      <div style={{
        color: STREAM_PAL.amber,
        fontSize: 10,
        letterSpacing: '0.12em',
        textTransform: 'uppercase',
        marginBottom: 8,
      }}>
        Score · provenance
        {scorecard?.label ? (
          <span style={{ color: STREAM_PAL.dim, marginLeft: 8 }}>{scorecard.label}</span>
        ) : null}
      </div>

      {!present ? (
        <div data-testid="score-unscored-absent" style={{ color: STREAM_PAL.dim, fontSize: 12, lineHeight: 1.6 }}>
          {scorecard?.display || 'score unscored — no scorecard artifact'}
        </div>
      ) : (
        <>
          <div data-testid="score-display" style={{
            color: STREAM_PAL.ink,
            fontSize: 14,
            lineHeight: 1.7,
            marginBottom: 8,
          }}>
            <span data-testid="score-authored-value">
              authored {authored.value === null || authored.value === undefined ? '—' : authored.value}
            </span>
            <SourceTag source={authored.source || 'MEASURED'} testId="tag-authored" />
            <span style={{ color: STREAM_PAL.dim }}> / </span>
            <span data-testid="score-reported-value">
              reported{' '}
              {status === 'UNSCORED' || status === 'UNSCORED_DECLINED' || reported.value === null
                || reported.value === undefined
                ? 'UNSCORED'
                : reported.value}
            </span>
            <SourceTag
              source={reported.source || 'OPERATOR-REPORTED'}
              testId="tag-reported"
            />
          </div>
          <div style={{ color: STREAM_PAL.dim, fontSize: 11, lineHeight: 1.6 }}>
            <span data-testid="score-recall-status">recall {status}</span>
            {scorecard.kas_verdict ? (
              <span> · KAS {scorecard.kas_verdict}</span>
            ) : null}
            {scorecard.posp_verdict ? (
              <span> · PoSP {scorecard.posp_verdict}</span>
            ) : null}
          </div>
          <div style={{
            color: STREAM_PAL.dim,
            fontSize: 10,
            marginTop: 8,
            lineHeight: 1.5,
          }} data-testid="score-tag-legend">
            MEASURED = instruments · OPERATOR-REPORTED = only they know · UNSCORED ≠ 0
          </div>
        </>
      )}
    </div>
  )
}

export default ScoreMoment
