/* QorTroller design-system primitives — Wordmark, StatusChip, Panel, Hash,
   Icon, OverlayPanel. Ported from the Claude-design export (bundle 5)
   Primitives.jsx + GamerView's inline OverlayPanel, converted from the
   global-window pattern to ES named exports. Styling lives in
   qortroller-kit.css; all components must render inside a .qt-design-root
   ancestor so the var(--*) tokens resolve. */
import { useMemo } from 'react'

export function Wordmark({ size = 22 }) {
  return (
    <span className="qt-wordmark" style={{ fontSize: size }}>
      Qor<span className="t">T</span>roller
    </span>
  )
}

/* StatusChip — ALWAYS pair with a text label. Never color-only. */
export function StatusChip({ tone = 'live', children }) {
  return <span className={`s-chip s-chip--${tone}`}>{children}</span>
}

/* Panel — surface with optional eyebrow + meta + breathing animation. */
export function Panel({ eyebrow, meta, children, soft, raised, breath, padding = true, style }) {
  const cls = [
    'p-panel',
    soft && 'p-panel--soft',
    raised && 'p-panel--raised',
    breath && 'p-panel--breath',
  ].filter(Boolean).join(' ')
  return (
    <section className={cls} style={style}>
      {(eyebrow || meta) && (
        <header className="p-head">
          {eyebrow && <span className="p-head__eye">{eyebrow}</span>}
          {meta && <span className="p-head__meta">{meta}</span>}
        </header>
      )}
      {padding ? <div className="p-body">{children}</div> : children}
    </section>
  )
}

/* OverlayPanel — floating translucent panel for the twin-dominant Gamer view. */
export function OverlayPanel({ children, style, accent = false }) {
  return (
    <div
      className={`overlay-panel ${accent ? 'overlay-panel--accent' : ''}`}
      style={{ position: 'absolute', ...style }}
    >
      {children}
    </div>
  )
}

/* Hash — middle-ellipsis hash specimen, mono. */
export function Hash({ value, length = 8, tone = 'chain', title }) {
  const short = useMemo(() => {
    if (!value) return '—'
    if (value.length <= length * 2 + 1) return value
    return `${value.slice(0, length)}…${value.slice(-length)}`
  }, [value, length])
  const color = tone === 'err' ? 'var(--status-blocked)'
    : tone === 'dim' ? 'var(--text-dim)'
      : tone === 'amber' ? 'var(--accent-amber)'
        : 'var(--chain)'
  return (
    <span className="mono" style={{ color, fontVariantLigatures: 'none' }} title={title || value}>
      {short}
    </span>
  )
}

/* Icon — inline SVG by name. Stroke 1.5, no fill. */
export function Icon({ name, size = 16, color = 'currentColor' }) {
  const common = {
    width: size, height: size, viewBox: '0 0 24 24',
    fill: 'none', stroke: color, strokeWidth: 1.5,
    strokeLinecap: 'round', strokeLinejoin: 'round',
  }
  switch (name) {
    case 'chevron':  return <svg {...common}><polyline points="9 18 15 12 9 6" /></svg>
    case 'copy':     return <svg {...common}><rect x="9" y="9" width="13" height="13" rx="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></svg>
    case 'external': return <svg {...common}><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" /><polyline points="15 3 21 3 21 9" /><line x1="10" y1="14" x2="21" y2="3" /></svg>
    case 'info':     return <svg {...common}><circle cx="12" cy="12" r="10" /><line x1="12" y1="16" x2="12" y2="12" /><line x1="12" y1="8" x2="12.01" y2="8" /></svg>
    case 'x':        return <svg {...common}><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
    case 'search':   return <svg {...common}><circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" /></svg>
    case 'pause':    return <svg {...common}><rect x="6" y="4" width="4" height="16" /><rect x="14" y="4" width="4" height="16" /></svg>
    case 'shield':   return <svg {...common}><path d="M9 12l2 2 4-4" /><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /></svg>
    case 'link':     return <svg {...common}><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" /><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" /></svg>
    case 'alert':    return <svg {...common}><circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" /></svg>
    case 'clock':    return <svg {...common}><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></svg>
    case 'play':     return <svg {...common}><polygon points="5 3 19 12 5 21 5 3" /></svg>
    case 'refresh':  return <svg {...common}><polyline points="23 4 23 10 17 10" /><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" /></svg>
    case 'cpu':      return <svg {...common}><rect x="4" y="4" width="16" height="16" rx="2" /><rect x="9" y="9" width="6" height="6" /><line x1="9" y1="1" x2="9" y2="4" /><line x1="15" y1="1" x2="15" y2="4" /><line x1="9" y1="20" x2="9" y2="23" /><line x1="15" y1="20" x2="15" y2="23" /><line x1="20" y1="9" x2="23" y2="9" /><line x1="20" y1="14" x2="23" y2="14" /><line x1="1" y1="9" x2="4" y2="9" /><line x1="1" y1="14" x2="4" y2="14" /></svg>
    default:         return null
  }
}
