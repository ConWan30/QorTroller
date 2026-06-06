import { useState, useEffect } from 'react'
import { useViewEyebrow } from '../design/Eyebrow'

// Real deck-stage.js keys (verified): arrows / PgUp-Dn / Space / Home / End /
// number-jump, browser print, Esc. No invented shortcuts.
const SHORTCUTS = [
  ['← →', 'Previous / next slide'],
  ['Space · PgDn', 'Next slide'],
  ['PgUp', 'Previous slide'],
  ['Home · End', 'First / last slide'],
  ['1 – 9', 'Jump to slide'],
  ['Ctrl / ⌘ + P', 'Print to PDF'],
  ['?', 'Toggle this help'],
  ['Esc', 'Close'],
]

// QorTroller — IoTeX Grant Brief (tab 05).
//
// Renders the brand-locked grant-evaluator deck (frontend/public/grant-brief.html)
// full-bleed in an iframe. The deck is the FROZEN source of truth exported from
// Claude Design (Syne + JetBrains Mono, void-black #04060a graticule, medial-T
// amber #f0a868 wordmark, chain-green #5bd6a3 data; 9 slides + speaker notes
// driven by /deck-stage.js). It is intentionally self-contained and public —
// sharable with grant evaluators who hold no operator credentials.
//
// The accessible name is carried by the iframe `title` attribute (NOT a nested
// <title> inside the deck). The relative wrapper gives the absolutely-positioned
// iframe a sized, positioned containing block so it fills the view area beneath
// the tab bar rather than escaping to the viewport.
export function GrantBriefView() {
  // v2 · item A — eyebrow spine (full-bleed .qt-stage iframe view).
  useViewEyebrow({
    num: '05', name: 'GRANT · BRIEF', status: 'IoTeX', statusTone: 'amber',
    readouts: [{ label: 'SLIDES', value: '21', tone: 'chain' }, { label: 'NAV', value: '? = KEYS', tone: 'dim' }],
  })

  // v2 · item F — keyboard-shortcut overlay (evaluators don't read linearly).
  // `?` toggles, Esc closes. (Works when the parent has focus; the ? button is
  // the always-available fallback since the iframe may hold focus.)
  const [showHelp, setShowHelp] = useState(false)
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === '?') { setShowHelp((v) => !v); e.preventDefault() }
      else if (e.key === 'Escape') setShowHelp(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <div style={{ position: 'relative', flex: 1, minHeight: 0, width: '100%', background: '#000' }}>
      <iframe
        src="/grant-brief.html"
        title="QorTroller — IoTeX Grant Brief"
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          border: 'none',
          background: '#000',
        }}
        // Deck contains inline <script> for deck-stage; needs scripts.
        sandbox="allow-scripts allow-same-origin"
      />

      {/* always-available "?" affordance (top-right) */}
      <button
        type="button"
        onClick={() => setShowHelp((v) => !v)}
        aria-label="Keyboard shortcuts"
        title="Keyboard shortcuts (?)"
        style={{
          position: 'absolute', top: 12, right: 14, zIndex: 5,
          width: 26, height: 26, borderRadius: 4, cursor: 'pointer',
          background: 'rgba(10,14,20,0.85)', border: '1px solid #2a3850',
          color: '#f0a868', fontFamily: "'JetBrains Mono', monospace", fontSize: 13, lineHeight: 1,
        }}
      >?</button>

      {showHelp && (
        <div
          onClick={() => setShowHelp(false)}
          role="dialog" aria-label="Keyboard shortcuts"
          style={{
            position: 'absolute', inset: 0, zIndex: 6, display: 'grid', placeItems: 'center',
            background: 'rgba(2,4,8,0.72)', backdropFilter: 'blur(2px)', cursor: 'pointer',
          }}
        >
          <div style={{
            minWidth: 320, background: 'rgba(10,14,20,0.97)', border: '1px solid #2a3850',
            borderRadius: 6, padding: '18px 20px',
          }}>
            <div style={{
              fontFamily: "'JetBrains Mono', monospace", fontSize: 11, letterSpacing: '0.14em',
              textTransform: 'uppercase', color: '#5a6878', marginBottom: 14,
            }}>Keyboard · Shortcuts</div>
            {SHORTCUTS.map(([k, d]) => (
              <div key={k} style={{ display: 'flex', justifyContent: 'space-between', gap: 24, padding: '6px 0' }}>
                <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12, color: '#f0a868' }}>{k}</span>
                <span style={{ fontFamily: "'Syne', system-ui, sans-serif", fontSize: 13, color: '#d4dde8' }}>{d}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
