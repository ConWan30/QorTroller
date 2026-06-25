// Honesty-as-aesthetic — the QorTroller signature.
//
// Maps the FROZEN VPM closed-enum `visual_state` to a visual treatment. The whole
// point: the UI CANNOT render a state the protocol can't prove. A panel/verdict NEVER
// picks its own color — it derives it from the server's visual_state. There is no
// `live` styling path that isn't gated on the server actually saying `live`.
//
// FROZEN vocabulary (mirrors scripts/vsd_ui_compiler.py:322 / VPMVisualState):
//   live · dry-run · emulated · frozen-disabled · revoked · unverified
//
// Colors reuse the GAMER tokens but here each color MEANS a proof-state (semantic,
// never decorative): green=proven, cyan=live signal, orange=provisional, red=unproven.

import { GAMER } from './tokens'

// Every state QorTroller can be in, with an honest, gamer-legible treatment.
const STATES = {
  live: {
    label: 'LIVE',
    color: GAMER.green,
    glow: true,
    texture: 'none',
    blurb: 'Verified. Proven by the protocol right now.',
  },
  'dry-run': {
    label: 'DRY RUN',
    color: GAMER.cyan,
    glow: false,
    texture: 'striped',
    blurb: 'A preview. Real checks ran, but this is not a committed, live result.',
  },
  emulated: {
    label: 'EMULATED',
    color: GAMER.t2,
    glow: false,
    texture: 'striped',
    blurb: 'Simulated input. Not a real capture from your controller.',
  },
  'frozen-disabled': {
    label: 'LOCKED',
    color: GAMER.t3,
    glow: false,
    texture: 'locked',
    blurb: 'This feature is reserved or gated. It cannot render as active.',
  },
  revoked: {
    label: 'REVOKED',
    color: GAMER.red,
    glow: false,
    texture: 'banded',
    blurb: 'Consent was withdrawn. This artifact is no longer valid.',
  },
  unverified: {
    label: 'UNVERIFIED',
    color: GAMER.orange,
    glow: false,
    texture: 'banded',
    blurb: 'The protocol could not prove this state. Treat it as not yet trusted.',
  },
}

// Anything off the frozen set (or missing) is honestly UNKNOWN — never silently green.
const UNKNOWN = {
  label: 'UNKNOWN',
  color: GAMER.t3,
  glow: false,
  texture: 'banded',
  blurb: 'No reading yet. The bridge has not reported this.',
}

export function vpmVisual(state) {
  if (typeof state !== 'string') return UNKNOWN
  return STATES[state.toLowerCase()] || UNKNOWN
}

// Lane states from BCRA (connected / degraded / disconnected / unknown) → the same
// honesty language, so one mapper drives both the per-lane lights and the overall verdict.
const LANE = {
  connected:    { color: GAMER.green,  label: 'CONNECTED',    glow: true  },
  degraded:     { color: GAMER.orange, label: 'DEGRADED',     glow: false },
  disconnected: { color: GAMER.red,    label: 'DISCONNECTED', glow: false },
  unknown:      { color: GAMER.t3,     label: 'UNKNOWN',      glow: false },
}

export function laneVisual(state) {
  if (typeof state !== 'string') return LANE.unknown
  return LANE[state.toLowerCase()] || LANE.unknown
}

// CSS background for a texture token — striped (preview), banded (warning), locked, none.
export function textureCss(texture, color) {
  if (texture === 'striped') {
    return `repeating-linear-gradient(135deg, ${color}14 0 6px, transparent 6px 12px)`
  }
  if (texture === 'banded') {
    return `repeating-linear-gradient(90deg, ${color}20 0 10px, transparent 10px 20px)`
  }
  if (texture === 'locked') {
    return `repeating-linear-gradient(45deg, ${color}18 0 3px, transparent 3px 8px)`
  }
  return 'transparent'
}
