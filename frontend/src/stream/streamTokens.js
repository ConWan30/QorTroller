/**
 * QorTroller Stream surface tokens (PKG-UI-01..03 React).
 * Gamer-tier cyan presence; void-black field. Verdict dignity colors are
 * structural (never "victory green" theater).
 */
export const STREAM_PAL = {
  void0: '#04060a',
  void1: '#0a0e14',
  void2: '#121820',
  ink: '#e8e8e8',
  dim: '#6a7380',
  cyan: '#00e5ff',
  amber: '#f0a868',
  bone: '#e9e2d2',
  rose: '#c97b8a',   // hygiene — dignified, not shaming red splash
  partial: '#e0a050',
  earned: '#7ec8a3', // muted chain-green, not neon checkmark
  bd: '#1a2030',
}

export const STREAM_FONTS = {
  mono: "'JetBrains Mono', 'Martian Mono', ui-monospace, monospace",
  display: "'Archivo', 'Rajdhani', system-ui, sans-serif",
  body: "'Hanken Grotesk', 'Syne', system-ui, sans-serif",
}

/** presence_tone → pulse color */
export const PRESENCE_TONE_COLOR = {
  live: STREAM_PAL.cyan,
  recent: STREAM_PAL.amber,
  quiet: STREAM_PAL.dim,
  empty: STREAM_PAL.dim,
  unknown: STREAM_PAL.dim,
}

/** verdict dignity tone → color */
export const VERDICT_TONE_COLOR = {
  earned: STREAM_PAL.earned,
  partial: STREAM_PAL.partial,
  hygiene: STREAM_PAL.rose,
  honest_null: STREAM_PAL.dim,
  absent: STREAM_PAL.dim,
}

export const STREAM_VIEW_SCHEMA = 'qortroller-stream-view-v1'
export const STATUS_SNAPSHOT_SCHEMA = 'qortroller-status-snapshot-v1'
export const RECEIPT_REVEAL_SCHEMA = 'qortroller-receipt-reveal-v1'
export const BIRTH_CEREMONY_SCHEMA = 'qortroller-birth-ceremony-v1'

export const CHOREOGRAPHY_STAGES = ['SETTLE', 'SURFACES', 'HONESTY', 'SHARE_SPLIT']
