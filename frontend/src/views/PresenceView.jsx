// PRESENCE — "You are live, right now."
// Causal presence (your inputs drive the screen) + active-play occupancy, read from real hooks.
// The adaptive-trigger force-curve fingerprint animation is a later stage; this view is honest
// about what is measured now and what is coming, and never claims a presence it cannot read.

import { motion } from 'framer-motion'
import { useActivePlayOccupancy, usePlayerSessionStatus } from '../api/bridgeApi'
import { FONTS, GAMER } from '../shared/design/tokens'
import { laneVisual } from '../shared/design/vpmVisual'
import { ExplainChip } from '../components/ExplainChip'

const APOP_TONE = {
  ACTIVE_MATCH_PLAY:    GAMER.cyan,
  COMPETITIVE_CONTROL:  GAMER.green,
  MATCH_TRANSITION:     GAMER.t2,
  NON_COMPETITIVE_MENU: GAMER.red,
  UNKNOWN_LOW_EVIDENCE: GAMER.t3,
}

export function PresenceView() {
  const { data: apop } = useActivePlayOccupancy()
  const { data: session } = usePlayerSessionStatus()
  const state = apop?.occupancy_state || 'UNKNOWN_LOW_EVIDENCE'
  const tone = APOP_TONE[state] || GAMER.t3

  return (
    <div style={{ flex: 1, overflow: 'auto', background: GAMER.bg, padding: '24px 20px 40px',
      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20 }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontFamily: FONTS.mono, fontSize: 11, letterSpacing: '0.32em',
          textTransform: 'uppercase', color: GAMER.t3 }}>Presence</div>
        <div style={{ fontFamily: FONTS.body, fontSize: 13, color: GAMER.t2, marginTop: 6 }}>
          Proof your hands are driving this — right now, not relayed or replayed.
          <ExplainChip term="pocp" label="causal presence" />
        </div>
      </div>

      <motion.div
        animate={{ boxShadow: [`0 0 0 ${tone}00`, `0 0 40px ${tone}33`, `0 0 0 ${tone}00`] }}
        transition={{ duration: 2.4, repeat: Infinity }}
        style={{ width: '100%', maxWidth: 620, borderRadius: 14, padding: '28px',
          border: `1.5px solid ${tone}`, background: GAMER.bg1, textAlign: 'center' }}
      >
        <div style={{ fontFamily: FONTS.mono, fontSize: 10, letterSpacing: '0.2em',
          textTransform: 'uppercase', color: GAMER.t3, marginBottom: 10 }}>
          Active play occupancy
          <ExplainChip term="pitl" label="play occupancy" />
        </div>
        <div style={{ fontFamily: FONTS.display, fontSize: 'clamp(28px,6vw,46px)', fontWeight: 700,
          color: tone, letterSpacing: '0.02em', lineHeight: 1.05 }}>
          {state.replace(/_/g, ' ')}
        </div>
      </motion.div>

      <div style={{ width: '100%', maxWidth: 620, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <Stat label="Causal coupling" term="pocp"
          value={session?.causal_presence != null ? `${session.causal_presence}` : 'not yet read'} />
        <Stat label="Recency-bound" term="recency"
          value={session?.recency_bound ? 'bound' : 'not bound'} />
      </div>

      <div style={{ width: '100%', maxWidth: 620, borderRadius: 12, padding: '16px 18px',
        border: `1px dashed ${GAMER.bd}`, background: GAMER.bg3 }}>
        <div style={{ fontFamily: FONTS.display, fontSize: 14, fontWeight: 700, color: GAMER.t1, marginBottom: 6 }}>
          Your force-curve fingerprint
          <ExplainChip term="forcecurve" label="force-curve" />
        </div>
        <div style={{ fontFamily: FONTS.body, fontSize: 12.5, color: GAMER.t3, lineHeight: 1.5 }}>
          The live animated fingerprint of how your fingers press the adaptive triggers arrives in a
          later stage. Until then this view shows only what the bridge measures now — no placeholder
          curve is drawn, because it would not be your real signal.
        </div>
      </div>
    </div>
  )
}

function Stat({ label, value, term }) {
  return (
    <div style={{ flex: 1, minWidth: 200, borderRadius: 10, padding: '14px 16px',
      background: GAMER.bg1, border: `1px solid ${GAMER.bd}` }}>
      <div style={{ fontFamily: FONTS.mono, fontSize: 10, letterSpacing: '0.12em',
        textTransform: 'uppercase', color: GAMER.t3, marginBottom: 6 }}>
        {label}<ExplainChip term={term} label={label} />
      </div>
      <div style={{ fontFamily: FONTS.display, fontSize: 20, fontWeight: 700, color: GAMER.t1 }}>{value}</div>
    </div>
  )
}
