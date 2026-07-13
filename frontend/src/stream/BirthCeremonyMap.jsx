/**
 * PKG-UI-03 — BirthCeremonyMap
 * Witness-node birth stages (not installer progress bar).
 * ROI shows overlay path when present; UI never ACKs (CLI remains the writer).
 */
import React from 'react'
import { STREAM_PAL, STREAM_FONTS } from './streamTokens'

const STATUS_COLOR = {
  done: STREAM_PAL.earned || '#7ec8a3',
  current: '#00e5ff',
  pending: STREAM_PAL.dim,
}

export function BirthCeremonyMap({ model = null }) {
  if (!model || model._present === false || !Array.isArray(model.stages) || model.stages.length === 0) {
    return (
      <div data-testid="birth-ceremony-absent" style={{ color: STREAM_PAL.dim, fontFamily: STREAM_FONTS.mono, fontSize: 12 }}>
        ceremony map unavailable — run <code>qortroller ui</code> to write ceremony.json
      </div>
    )
  }

  return (
    <div
      data-testid="birth-ceremony-map"
      data-complete={String(Boolean(model.ceremony_complete))}
      style={{ fontFamily: STREAM_FONTS.mono, color: STREAM_PAL.ink, maxWidth: 560 }}
    >
      <div style={{
        fontSize: 11, letterSpacing: '0.12em', textTransform: 'uppercase',
        color: STREAM_PAL.amber, marginBottom: 8,
      }}>
        Node birth · {model.node_state || '—'}
      </div>
      <div style={{ color: STREAM_PAL.dim, fontSize: 12, marginBottom: 16, lineHeight: 1.5 }}>
        {model.feel_summary}
      </div>
      <ol style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
        {model.stages.map((s) => {
          const st = s.status || 'pending'
          const col = STATUS_COLOR[st] || STREAM_PAL.dim
          return (
            <li
              key={s.id || s.n}
              data-testid={`ceremony-stage-${s.id}`}
              data-status={st}
              style={{
                border: `1px solid ${STREAM_PAL.bd}`,
                borderLeft: `3px solid ${col}`,
                borderRadius: 6,
                padding: '10px 12px',
                background: st === 'current' ? 'rgba(0,229,255,0.04)' : STREAM_PAL.void1,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                <span style={{ color: col, fontSize: 12 }}>
                  {s.n != null ? `${s.n} · ` : ''}{s.title || s.id}
                </span>
                <span style={{ color: STREAM_PAL.dim, fontSize: 10, letterSpacing: '0.08em' }}>
                  {st}
                </span>
              </div>
              <div style={{ color: STREAM_PAL.ink, fontSize: 12, marginTop: 6 }}>{s.feel}</div>
              <div style={{ color: STREAM_PAL.dim, fontSize: 10, marginTop: 4 }}>
                verb: <code>{s.verb}</code>
              </div>
              {s.id === 'roi' && s.overlay_exists ? (
                <div data-testid="roi-overlay-hint" style={{ color: STREAM_PAL.cyan, fontSize: 11, marginTop: 8 }}>
                  ROI overlay ready (y/N in terminal) — UI shows path only; CLI remains the writer.
                  {s.overlay_path ? (
                    <div style={{ color: STREAM_PAL.dim, marginTop: 2, wordBreak: 'break-all' }}>
                      {s.overlay_path}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </li>
          )
        })}
      </ol>
    </div>
  )
}

export default BirthCeremonyMap
