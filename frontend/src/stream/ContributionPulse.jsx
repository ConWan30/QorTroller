/**
 * STREAM-2 Q2 — ContributionPulse
 * Ledger as earned heartbeat history. Lifecycle pixels:
 *   PENDING (local, not on-chain) → ANCHORED (only with real tx short).
 * Never paints "on-chain" early. Empty ledger is dignified, not a fail.
 */
import React from 'react'
import { STREAM_PAL, STREAM_FONTS } from './streamTokens'

function lifecycleColor(lc) {
  if (lc === 'ANCHORED') return STREAM_PAL.earned
  if (lc === 'PENDING') return STREAM_PAL.amber
  return STREAM_PAL.dim
}

export function ContributionPulse({ contribution = null }) {
  const present = Boolean(contribution && contribution.present)
  const recent = Array.isArray(contribution?.recent) ? contribution.recent : []
  const count = contribution?.entry_count ?? 0
  const intact = contribution?.chain_intact

  return (
    <div
      data-testid="contribution-pulse"
      data-present={present ? 'true' : 'false'}
      data-chain-intact={intact === true ? 'true' : intact === false ? 'false' : 'unknown'}
      style={{
        fontFamily: STREAM_FONTS.mono,
        border: `1px solid ${STREAM_PAL.bd}`,
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
        Contribution · pulse
      </div>
      {!present ? (
        <div data-testid="contribution-empty" style={{ color: STREAM_PAL.dim, fontSize: 12, lineHeight: 1.6 }}>
          {contribution?.line || 'no contributions logged yet — local ledger empty'}
        </div>
      ) : (
        <>
          <div style={{ color: STREAM_PAL.ink, fontSize: 12, marginBottom: 10, lineHeight: 1.5 }}>
            <span data-testid="contribution-count">{count}</span>
            {' entries · chain '}
            <span data-testid="contribution-chain">
              {intact === true ? 'intact' : intact === false ? 'broken' : 'unknown'}
            </span>
            <span style={{ color: STREAM_PAL.dim }}> · LOCAL until a real tx anchors</span>
          </div>
          <div data-testid="contribution-history" style={{ display: 'grid', gap: 6 }}>
            {recent.map((row, i) => {
              const lc = row.lifecycle || (row.anchored ? 'ANCHORED' : 'PENDING')
              const col = lifecycleColor(lc)
              // Honesty: never show ANCHORED without anchor_tx_short
              const honestLc = (lc === 'ANCHORED' && !row.anchor_tx_short) ? 'PENDING' : lc
              return (
                <div
                  key={`${row.session_id_short || i}-${i}`}
                  data-testid={`contribution-row-${i}`}
                  data-lifecycle={honestLc}
                  data-anchored={honestLc === 'ANCHORED' ? 'true' : 'false'}
                  data-w3s={row.w3s_attested ? 'true' : 'false'}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    fontSize: 11,
                    color: STREAM_PAL.ink,
                    borderLeft: `2px solid ${lifecycleColor(honestLc)}`,
                    paddingLeft: 8,
                  }}
                >
                  <span
                    aria-hidden
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      background: lifecycleColor(honestLc),
                      flexShrink: 0,
                      boxShadow: honestLc === 'ANCHORED' ? `0 0 6px ${col}` : 'none',
                    }}
                  />
                  <span style={{ color: STREAM_PAL.dim, minWidth: 90 }}>
                    {row.session_id_short || '—'}
                  </span>
                  <span style={{ color: STREAM_PAL.ink }}>{row.posp_verdict || 'ABSENT'}</span>
                  <span style={{ color: lifecycleColor(honestLc), letterSpacing: '0.06em' }}>
                    {honestLc}
                    {honestLc === 'ANCHORED' && row.anchor_tx_short
                      ? ` · tx ${row.anchor_tx_short}…`
                      : ''}
                  </span>
                  {row.w3s_attested ? (
                    <span style={{ color: STREAM_PAL.dim }} title="leg-2 mechanical only">w3s</span>
                  ) : null}
                </div>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}

export default ContributionPulse
