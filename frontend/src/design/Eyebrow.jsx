/* QorTroller — the persistent eyebrow-row spine (PROVING GROUND).
 *
 * One landmark, identical on every surface, sitting between the tab strip and the
 * view body:
 *
 *   [ TAB STRIP — wordmark · tabs · seal-chip ]            (ViewSelector, 56px)
 *   [ EYEBROW   — NN · NAME · STATUS  +  readouts ]        ← this component (~30px)
 *   [ view body ]
 *
 * Ported faithfully from the Claude Design "PG Eyebrow.dc.html" (round 4 — completes
 * the shared kit alongside PG Tab Strip / PG Footer / PG Stamp). A quiet continuation
 * of the tab strip: --void-1 ground, --void-2 hairlines, Martian Mono num/readouts,
 * Archivo-expanded view name.
 *
 * HONESTY (chrome discipline): status words are STRUCTURAL — steel / ember / ash,
 * never struck-gold. A readout VALUE may earn struck-gold, but only when the caller
 * marks it tone:'chain' for a genuinely-attested fact. Same law as every surface.
 *
 * The React API is unchanged: each view registers via useViewEyebrow({...}); the bar
 * reads it from context (or an explicit `data` prop for the Evidence OS path). Bridge-
 * dead degradation (a single honest "BRIDGE UNREACHABLE" line) is preserved.
 */
import { createContext, useContext, useEffect, useState } from 'react'
import { useRealityHeartbeat, agoLabel } from './realityHeartbeat'
import { isMockActive } from '../api/mockBridge'

const PAL = {
  void1: '#0A1120', void2: '#111B2E',
  steel: '#6E8CA8', ember: '#E0743A', struck: '#F0C667', oxblood: '#B23A4C',
  ash: '#4A5260', bone: '#E9E2D2', boneDim: '#9AA4B2',
}
const DISP = "'Archivo', system-ui, sans-serif"
const MONO = "'Martian Mono', ui-monospace, monospace"

// Status chips are structural chrome → steel / ember / ash, NEVER gold.
const STATUS_TONE = { chain: PAL.steel, live: PAL.steel, verified: PAL.steel, amber: PAL.ember, pending: PAL.ember, blocked: PAL.oxblood, err: PAL.oxblood, mock: PAL.oxblood, dormant: PAL.ash, dim: PAL.ash }
const statusColor = (t) => STATUS_TONE[t] || PAL.steel
// Readout VALUES may earn struck-gold — but only when the caller marks tone:'chain'.
const VALUE_TONE = { chain: PAL.struck, live: PAL.struck, verified: PAL.struck, amber: PAL.ember, pending: PAL.ember, blocked: PAL.oxblood, err: PAL.oxblood, mock: PAL.oxblood, dormant: PAL.ash, dim: PAL.boneDim }
const valueColor = (t) => VALUE_TONE[t] || PAL.boneDim

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
   { num:'01', name:'GAMER · COCKPIT', status:'LIVE', statusTone:'chain',
     readouts:[{label:'CHAIN', value:'47/100', tone:'chain'}, ...] } */
export function useViewEyebrow(content) {
  const { setContent } = useContext(EyebrowContext)
  const serialized = JSON.stringify(content)
  useEffect(() => { setContent(content) }, [serialized, setContent]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => setContent(null), [setContent])
}

/* The persistent ~30px bar. Reads context unless an explicit `data` prop is given
   (Evidence OS path). Renders gracefully (an em-dash) when there's no content so the
   spine never shifts height between views. */
export function ViewEyebrowBar({ data }) {
  const ctx = useContext(EyebrowContext)
  const c = data || ctx.content
  // Degrade to a single honest "bridge unreachable" line on the right when the
  // heartbeat goes stale (only after a real beat; never while first connecting or on mock).
  const { alive, everBeat, sinceMs } = useRealityHeartbeat()
  const bridgeDead = everBeat && !alive && !isMockActive()
  // The DC wiring passes `view-name` (dc-import reserves `name` for the basename); the
  // React API passes `name`. Support both.
  const viewName = c ? (c.viewName || c.name || '') : ''
  return (
    <div
      role="status"
      aria-live="polite"
      data-qt-eyebrow=""
      style={{
        flexShrink: 0,
        minHeight: 30,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 13,
        padding: '0 28px',
        borderBottom: `1px solid ${PAL.void2}`,
        background: PAL.void1,
        overflowX: 'auto',
        whiteSpace: 'nowrap',
      }}
    >
      {/* left — the view names itself */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 13, flexShrink: 0 }}>
        {c ? (
          <>
            {c.num && <span style={{ fontFamily: MONO, fontSize: 10, fontWeight: 500, letterSpacing: '0.14em', color: PAL.ash }}>{c.num}</span>}
            {c.num && <span style={{ color: PAL.void2, fontFamily: MONO, fontSize: 10 }}>·</span>}
            <span style={{ fontFamily: DISP, fontStretch: '125%', fontWeight: 700, fontSize: 11.5, letterSpacing: '0.11em', textTransform: 'uppercase', color: PAL.bone, whiteSpace: 'nowrap' }}>{viewName}</span>
            {c.status && (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontFamily: MONO, fontSize: 9.5, fontWeight: 500, letterSpacing: '0.08em', textTransform: 'uppercase', color: statusColor(c.statusTone), border: `1px solid ${statusColor(c.statusTone)}`, borderRadius: 2, padding: '2px 7px', lineHeight: 1 }}>
                <span style={{ width: 5, height: 5, borderRadius: '50%', background: statusColor(c.statusTone) }} />{c.status}
              </span>
            )}
          </>
        ) : (
          <span style={{ color: PAL.void2, fontFamily: MONO, fontSize: 10 }}>—</span>
        )}
      </div>

      {/* right — honest bridge-drop line, else the 2-3 readouts */}
      {bridgeDead ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0, fontFamily: MONO, fontSize: 9.5, letterSpacing: '0.1em', textTransform: 'uppercase', color: PAL.oxblood }}>
          <span>BRIDGE UNREACHABLE</span>
          <span style={{ color: PAL.ash }}>— LAST KNOWN {agoLabel(sinceMs)}</span>
        </div>
      ) : (c && c.readouts && c.readouts.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexShrink: 0, overflow: 'hidden' }}>
          {c.readouts.map((r, i) => (
            <span key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: 7, whiteSpace: 'nowrap' }}>
              <span style={{ fontFamily: MONO, fontSize: 9.5, letterSpacing: '0.1em', textTransform: 'uppercase', color: PAL.ash }}>{r.label}</span>
              <span style={{ color: PAL.void2, fontFamily: MONO, fontSize: 9.5 }}>·</span>
              <span style={{ fontFamily: MONO, fontSize: 10, letterSpacing: '0.04em', color: valueColor(r.tone) }}>{r.value}</span>
            </span>
          ))}
        </div>
      ))}
    </div>
  )
}
