/* QorTroller v2 design pass — item A: the persistent eyebrow-row spine.
 *
 * One new landmark, identical on every surface (6 dashboard tabs + 3 Evidence OS
 * workspaces), sitting between the top STRIP and the view body:
 *
 *   [ STRIP   — wordmark · tabs · status ]            (existing)
 *   [ EYEBROW — NN · NAME · STATUS  +  live readouts ]  ← this component
 *   [ view body ]
 *
 * The eyebrow is where a view *names itself* — `01 · GAMER · LIVE` — plus the 2-3
 * live readouts that view cares about most. Same 32px height, same JetBrains Mono
 * caps at 0.14em, same amber view-name, same chain-green live readouts on every
 * surface, so the rhythm is uniform across all nine.
 *
 * Two feed modes, one identical bar:
 *   - Dashboard: each view calls `useViewEyebrow({...})`; <ViewEyebrowBar/> reads
 *     it from context (persists across tab switches — no remount, no shift).
 *   - Evidence OS: AppShell knows route + global metrics, so it passes
 *     `<ViewEyebrowBar data={{...}} />` directly.
 *
 * Colors are literal hex (not var()) so the bar renders correctly whether or not
 * it sits under a `.qt-design-root` ancestor (the dashboard shell is not).
 */
import { createContext, useContext, useEffect, useState } from 'react'
import { useRealityHeartbeat, agoLabel } from './realityHeartbeat'
import { isMockActive } from '../api/mockBridge'

const TONE = {
  live: '#5bd6a3', chain: '#5bd6a3', verified: '#5bd6a3',
  pending: '#f0a868', amber: '#f0a868',
  blocked: '#d65b78', err: '#d65b78', mock: '#d65b78',
  dormant: '#5a6878', dim: '#8a98ab',
}
const toneColor = (t) => TONE[t] || '#d4dde8'

const C = {
  bg: '#04060a', border: '#1b2433', faint: '#5a6878', ghost: '#36404e',
  amber: '#f0a868', text: '#d4dde8',
}

const EyebrowContext = createContext({ content: null, setContent: () => {} })

export function EyebrowProvider({ children }) {
  const [content, setContent] = useState(null)
  return (
    <EyebrowContext.Provider value={{ content, setContent }}>
      {children}
    </EyebrowContext.Provider>
  )
}

/* A view registers its eyebrow content. Shape:
   { num:'01', name:'GAMER · LIVE', status:'LIVE', statusTone:'live',
     readouts:[{label:'CHAIN', value:'47/100', tone:'chain'}, ...] } */
export function useViewEyebrow(content) {
  const { setContent } = useContext(EyebrowContext)
  const serialized = JSON.stringify(content)
  useEffect(() => { setContent(content) }, [serialized, setContent]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => setContent(null), [setContent])
}

/* The persistent 32px bar. Reads context unless an explicit `data` prop is given
   (Evidence OS path). Renders an empty bar when there's no content so the spine
   never shifts height between views. */
export function ViewEyebrowBar({ data }) {
  const ctx = useContext(EyebrowContext)
  const c = data || ctx.content
  // v2 · item D — degrade to a single honest "bridge unreachable" line on the
  // right when the heartbeat goes stale (only after a real beat; not while
  // first connecting, and never when on mock data). Same 32px row → no shift.
  const { alive, everBeat, sinceMs } = useRealityHeartbeat()
  const bridgeDead = everBeat && !alive && !isMockActive()
  return (
    <div
      role="status"
      aria-live="polite"
      data-qt-eyebrow=""
      style={{
        flexShrink: 0,
        height: 32,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 16,
        padding: '0 24px',
        borderBottom: `1px solid ${C.border}`,
        background: C.bg,
        fontFamily: "'JetBrains Mono', ui-monospace, monospace",
        fontSize: 11,
        letterSpacing: '0.14em',
        textTransform: 'uppercase',
        overflowX: 'auto',
        whiteSpace: 'nowrap',
      }}
    >
      {/* left — the view names itself */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 9, flexShrink: 0 }}>
        {c ? (
          <>
            <span style={{ color: C.faint }}>{c.num}</span>
            <span style={{ color: C.ghost }}>·</span>
            <span style={{ color: C.amber, fontWeight: 600 }}>{c.name}</span>
            {c.status && (
              <>
                <span style={{ color: C.ghost }}>·</span>
                <span style={{ color: toneColor(c.statusTone) }}>{c.status}</span>
              </>
            )}
          </>
        ) : (
          <span style={{ color: C.ghost }}>—</span>
        )}
      </div>

      {/* right — honest bridge-drop line, else the 2-3 live readouts */}
      {bridgeDead ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0, color: TONE.blocked }}>
          <span>BRIDGE UNREACHABLE</span>
          <span style={{ color: C.faint }}>— LAST KNOWN {agoLabel(sinceMs)}</span>
        </div>
      ) : (c && c.readouts && c.readouts.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 18, flexShrink: 0 }}>
          {c.readouts.map((r, i) => (
            <span key={i}>
              <span style={{ color: C.faint }}>{r.label} </span>
              <span style={{ color: toneColor(r.tone) }}>{r.value}</span>
            </span>
          ))}
        </div>
      ))}
    </div>
  )
}
