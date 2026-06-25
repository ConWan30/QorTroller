// ExplainChip — a small "?" beside any complex term. Click to open a plain-language
// popover: What it is / Why it matters to you / The honest limit. The honest-limit line
// is always shown — anti-overclaim applied to the words.

import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { FONTS, GAMER } from '../shared/design/tokens'
import { explainFor } from '../shared/explain'

export function ExplainChip({ term, label }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  const info = explainFor(term)

  useEffect(() => {
    if (!open) return
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    const onEsc = (e) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onDoc)
    document.addEventListener('keydown', onEsc)
    return () => { document.removeEventListener('mousedown', onDoc); document.removeEventListener('keydown', onEsc) }
  }, [open])

  if (!info) return null

  return (
    <span ref={ref} style={{ position: 'relative', display: 'inline-flex', verticalAlign: 'middle' }}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label={`What is ${label || info.title}?`}
        aria-expanded={open}
        style={{
          width: 16, height: 16, borderRadius: '50%', cursor: 'pointer',
          border: `1px solid ${open ? GAMER.cyan : GAMER.t3}`,
          background: open ? `${GAMER.cyan}22` : 'transparent',
          color: open ? GAMER.cyan : GAMER.t2,
          fontFamily: FONTS.mono, fontSize: 10, lineHeight: 1, fontWeight: 700,
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          padding: 0, transition: 'all 0.15s ease',
        }}
      >?</button>

      <AnimatePresence>
        {open && (
          <motion.div
            role="dialog"
            initial={{ opacity: 0, y: 4, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 4, scale: 0.98 }}
            transition={{ duration: 0.14 }}
            style={{
              position: 'absolute', top: 22, left: 0, zIndex: 200, width: 280,
              background: GAMER.bg1, border: `1px solid ${GAMER.bd}`, borderRadius: 8,
              padding: '12px 14px', boxShadow: '0 12px 40px rgba(0,0,0,0.6)',
              textAlign: 'left',
            }}
          >
            <div style={{
              fontFamily: FONTS.display, fontSize: 14, fontWeight: 700, color: GAMER.t1,
              letterSpacing: '0.02em', marginBottom: 8,
            }}>{info.title}</div>

            {[['What it is', info.is, GAMER.cyan],
              ['Why it matters to you', info.you, GAMER.green],
              ['The honest limit', info.limit, GAMER.orange]].map(([h, body, c]) => (
              <div key={h} style={{ marginBottom: 8 }}>
                <div style={{
                  fontFamily: FONTS.mono, fontSize: 9, letterSpacing: '0.14em',
                  textTransform: 'uppercase', color: c, marginBottom: 2,
                }}>{h}</div>
                <div style={{ fontFamily: FONTS.body, fontSize: 12.5, lineHeight: 1.5, color: GAMER.t2 }}>
                  {body}
                </div>
              </div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </span>
  )
}
