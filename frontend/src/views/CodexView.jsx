// CODEX — the plain-language explainer hub. Every complex QorTroller concept in gamer terms,
// each with its honest limit. Renders the same EXPLAIN registry the inline ExplainChips use, so
// the words stay consistent everywhere.

import { FONTS, GAMER } from '../shared/design/tokens'
import { EXPLAIN } from '../shared/explain'

export function CodexView() {
  const entries = Object.values(EXPLAIN)
  return (
    <div style={{ flex: 1, overflow: 'auto', background: GAMER.bg, padding: '24px 20px 40px',
      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18 }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontFamily: FONTS.mono, fontSize: 11, letterSpacing: '0.32em',
          textTransform: 'uppercase', color: GAMER.t3 }}>Codex</div>
        <div style={{ fontFamily: FONTS.body, fontSize: 13, color: GAMER.t2, marginTop: 6, maxWidth: 480 }}>
          Everything QorTroller does, in plain language — including what each thing does not claim.
        </div>
      </div>

      <div style={{ width: '100%', maxWidth: 820, display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 14 }}>
        {entries.map((e) => (
          <div key={e.title} style={{ borderRadius: 12, padding: '16px 18px',
            background: GAMER.bg1, border: `1px solid ${GAMER.bd}` }}>
            <div style={{ fontFamily: FONTS.display, fontSize: 15, fontWeight: 700, color: GAMER.t1,
              marginBottom: 10, lineHeight: 1.2 }}>{e.title}</div>
            {[['What it is', e.is, GAMER.cyan],
              ['Why it matters to you', e.you, GAMER.green],
              ['The honest limit', e.limit, GAMER.orange]].map(([h, body, c]) => (
              <div key={h} style={{ marginBottom: 8 }}>
                <div style={{ fontFamily: FONTS.mono, fontSize: 9, letterSpacing: '0.14em',
                  textTransform: 'uppercase', color: c, marginBottom: 2 }}>{h}</div>
                <div style={{ fontFamily: FONTS.body, fontSize: 12.5, lineHeight: 1.5, color: GAMER.t2 }}>{body}</div>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}
