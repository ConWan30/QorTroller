// src/shared/design/animations.js
// Framer Motion variants for VAPI three-tier frontend

export const PAGE_ENTER = {
  initial:   { opacity: 0, y: 8 },
  animate:   { opacity: 1, y: 0, transition: { duration: 0.22, ease: 'easeOut' } },
  exit:      { opacity: 0, y: -4, transition: { duration: 0.15 } },
}

export const STAGGER_CONTAINER = {
  animate: { transition: { staggerChildren: 0.06 } },
}

export const STAGGER_ITEM = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.2 } },
}

// PITL layer stack — 80ms apart, L0 first
export const PITL_CONTAINER = {
  animate: { transition: { staggerChildren: 0.08, delayChildren: 0.1 } },
}

export const PITL_ROW = {
  initial: { opacity: 0, x: -12 },
  animate: { opacity: 1, x: 0, transition: { duration: 0.25, ease: 'easeOut' } },
}

// Feed items fade in from top
export const FEED_ITEM = {
  initial: { opacity: 0, y: -6 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.2 } },
  exit:    { opacity: 0, transition: { duration: 0.1 } },
}

// Address/hash fields — left border pulse on first render
export const HASH_PULSE = {
  initial:   { borderLeftColor: 'transparent' },
  animate:   {
    borderLeftColor: ['transparent', 'var(--tier-accent)', 'transparent'],
    transition: { duration: 1.2, times: [0, 0.5, 1], delay: 0.3 },
  },
}

// Card entry for manufacturer cert grid
export const CERT_CARD = {
  initial:   { opacity: 0, scale: 0.97 },
  animate:   { opacity: 1, scale: 1, transition: { duration: 0.2 } },
  whileHover: { scale: 1.01, transition: { duration: 0.12 } },
}

// Score gauge fill
export const GAUGE_FILL = (score) => ({
  initial:  { width: '0%' },
  animate:  { width: `${score * 100}%`, transition: { duration: 1.4, ease: 'easeOut', delay: 0.2 } },
})

// Separation ratio bar
export const RATIO_BAR = (ratio) => ({
  initial:  { width: '0%' },
  animate:  { width: `${ratio * 100}%`, transition: { duration: 1.6, ease: 'easeOut', delay: 0.3 } },
})

// Pipeline node stagger — 120ms apart, left-to-right reveal
export const PIPELINE_NODE_CONTAINER = {
  animate: { transition: { staggerChildren: 0.12, delayChildren: 0.08 } },
}

export const PIPELINE_NODE = {
  initial: { opacity: 0, scale: 0.9, y: 6 },
  animate: { opacity: 1, scale: 1, y: 0, transition: { duration: 0.22, ease: 'easeOut' } },
}

// Left-edge drawer — slides in from negative x (mirrors GamerView's right-edge pattern)
export const DRAWER_SLIDE_LEFT = {
  initial:  { x: -300, opacity: 0 },
  animate:  { x: 0, opacity: 1, transition: { duration: 0.2, ease: 'easeOut' } },
  exit:     { x: -300, opacity: 0, transition: { duration: 0.15 } },
}
