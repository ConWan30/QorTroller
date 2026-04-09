// src/shared/design/tokens.js
// Three-tier VAPI color system — each tier has its own identity
// Fonts: Rajdhani (display), JetBrains Mono (data), Syne (body)

export const FONTS = {
  display: "'Rajdhani', sans-serif",
  mono:    "'JetBrains Mono', monospace",
  body:    "'Syne', system-ui, sans-serif",
}

export const GAMER = {
  bg:     '#050a0f',
  bg1:    '#081218',
  bg2:    '#0a1820',
  bg3:    '#050c12',
  cyan:   '#00d4ff',
  green:  '#00ff88',
  orange: '#ff9500',
  red:    '#ff3b5c',
  t1:     '#d4f0ff',
  t2:     '#7ab8cc',
  t3:     '#3a6070',
  bd:     '#0e2535',
  bd2:    '#0a1620',
}

export const DEVELOPER = {
  bg:     '#030507',
  bg1:    '#060a0e',
  bg2:    '#090d12',
  bg3:    '#03060a',
  orange: '#ff6b00',
  amber:  '#ffaa44',
  red:    '#ff3b5c',
  green:  '#00ff88',
  t1:     '#ffe8d4',
  t2:     '#cc8855',
  t3:     '#5a3520',
  bd:     '#1a0e05',
  bd2:    '#100805',
}

export const MANUFACTURER = {
  bg:     '#020408',
  bg1:    '#04080f',
  bg2:    '#060c16',
  bg3:    '#030610',
  blue:   '#4a9eff',
  gold:   '#ffd700',
  green:  '#00ff88',
  red:    '#ff3b5c',
  orange: '#ff9500',
  t1:     '#d4e8ff',
  t2:     '#6a9acc',
  t3:     '#1e3a5a',
  bd:     '#0a1828',
  bd2:    '#060c18',
}

// CSS custom properties injected into :root per tier
export const CSS_VARS = {
  gamer: `
    --tier-bg: ${GAMER.bg};
    --tier-bg1: ${GAMER.bg1};
    --tier-accent: ${GAMER.cyan};
    --tier-accent2: ${GAMER.green};
    --tier-t1: ${GAMER.t1};
    --tier-t2: ${GAMER.t2};
    --tier-t3: ${GAMER.t3};
    --tier-bd: ${GAMER.bd};
  `,
  developer: `
    --tier-bg: ${DEVELOPER.bg};
    --tier-bg1: ${DEVELOPER.bg1};
    --tier-accent: ${DEVELOPER.orange};
    --tier-accent2: ${DEVELOPER.amber};
    --tier-t1: ${DEVELOPER.t1};
    --tier-t2: ${DEVELOPER.t2};
    --tier-t3: ${DEVELOPER.t3};
    --tier-bd: ${DEVELOPER.bd};
  `,
  manufacturer: `
    --tier-bg: ${MANUFACTURER.bg};
    --tier-bg1: ${MANUFACTURER.bg1};
    --tier-accent: ${MANUFACTURER.blue};
    --tier-accent2: ${MANUFACTURER.gold};
    --tier-t1: ${MANUFACTURER.t1};
    --tier-t2: ${MANUFACTURER.t2};
    --tier-t3: ${MANUFACTURER.t3};
    --tier-bd: ${MANUFACTURER.bd};
  `,
}

// Google Fonts import string for index.html
export const FONT_IMPORT =
  'https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600;700&family=JetBrains+Mono:wght@400;500&family=Syne:wght@400;500;700&display=swap'
