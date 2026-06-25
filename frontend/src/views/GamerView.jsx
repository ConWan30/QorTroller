// LIVE — "The Moment of Proof". The gamer-first front door.
//
// The instant a controller connects, this renders the four BCRA lanes (controller / agents /
// chain / operational) as honest lights and ONE honesty-gated verdict whose entire treatment
// (color / glow / texture) is derived ONLY from the server's VPM visual_state. It is impossible
// to render `live` here unless the bridge actually says `live`. The controller is the protagonist.
//
// Honesty rails: telemetry comes from useBridgeConnectivity (noMock:true); a bridge outage shows
// the explicit MOCK banner, never a fabricated green. The UI displays the server verdict — it
// never computes proof and never recolors a state to look better.

import { motion, AnimatePresence } from 'framer-motion'
import { useBridgeConnectivity } from '../api/bridgeApi'
import { isMockActive } from '../api/mockBridge'
import { FONTS, GAMER } from '../shared/design/tokens'
import { vpmVisual, laneVisual, textureCss } from '../shared/design/vpmVisual'
import { ExplainChip } from '../components/ExplainChip'

const LANES = [
  { key: 'controller',  name: 'CONTROLLER',  term: 'forcecurve', sub: 'your hands, live' },
  { key: 'agents',      name: 'AGENTS',      term: 'pitl',       sub: 'the watchers' },
  { key: 'chain',       name: 'CHAIN',       term: 'gic',        sub: 'on-chain anchor' },
  { key: 'operational', name: 'OPERATIONAL', term: 'bcra',       sub: 'bridge health' },
]

function Lane({ name, sub, term, lane }) {
  const v = laneVisual(lane?.state)
  return (
    <div style={{
      flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 6,
      padding: '14px 16px', borderRadius: 10,
      background: GAMER.bg1, border: `1px solid ${v.color}33`,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <motion.span
          animate={v.glow ? { boxShadow: [`0 0 4px ${v.color}`, `0 0 12px ${v.color}`, `0 0 4px ${v.color}`] } : {}}
          transition={{ duration: 1.8, repeat: Infinity }}
          style={{ width: 10, height: 10, borderRadius: '50%', background: v.color, flexShrink: 0 }}
        />
        <span style={{ fontFamily: FONTS.display, fontSize: 15, fontWeight: 700, color: GAMER.t1, letterSpacing: '0.04em' }}>
          {name}
        </span>
        <ExplainChip term={term} label={name} />
      </div>
      <div style={{ fontFamily: FONTS.mono, fontSize: 11, letterSpacing: '0.12em', color: v.color, fontWeight: 600 }}>
        {v.label}
      </div>
      <div style={{ fontFamily: FONTS.body, fontSize: 11.5, color: GAMER.t3, lineHeight: 1.4 }}>
        {lane?.evidence || sub}
      </div>
    </div>
  )
}

export function GamerView() {
  const { data, isLoading, isError } = useBridgeConnectivity()
  const mock = isMockActive()
  const visualState = data?.visual_state
  const verdict = vpmVisual(visualState)
  const lanes = data?.lanes || {}

  return (
    <div style={{
      flex: 1, overflow: 'auto', background: GAMER.bg,
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      padding: '24px 20px 40px', gap: 20,
    }}>
      {/* Eyebrow */}
      <div style={{ textAlign: 'center' }}>
        <div style={{
          fontFamily: FONTS.mono, fontSize: 11, letterSpacing: '0.32em', textTransform: 'uppercase',
          color: GAMER.t3,
        }}>
          The Moment of Proof
        </div>
        <div style={{
          fontFamily: FONTS.body, fontSize: 13, color: GAMER.t2, marginTop: 6, maxWidth: 460,
        }}>
          A live human on a certified controller — proven, not asserted.
          <ExplainChip term="vpm" label="honesty labels" />
        </div>
      </div>

      {mock && (
        <div style={{
          fontFamily: FONTS.mono, fontSize: 11, color: GAMER.orange,
          border: `1px solid ${GAMER.orange}55`, background: `${GAMER.orange}11`,
          borderRadius: 6, padding: '6px 12px', letterSpacing: '0.08em',
        }}>
          ● BRIDGE OFFLINE — showing placeholder. No live proof is being made.
        </div>
      )}

      {/* Controller protagonist */}
      <div style={{
        width: '100%', maxWidth: 760, height: 300, borderRadius: 14, overflow: 'hidden',
        border: `1px solid ${verdict.color}33`, background: GAMER.bg3, position: 'relative',
        boxShadow: verdict.glow ? `0 0 60px ${verdict.color}22` : 'none',
      }}>
        <iframe
          title="Your controller"
          src="/controller-twin.html?minimal=1"
          style={{ width: '100%', height: '100%', border: 'none' }}
        />
      </div>

      {/* The honesty-gated verdict — the signature. Color/glow/texture from visual_state ONLY. */}
      <AnimatePresence mode="wait">
        <motion.div
          key={visualState || 'pending'}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.22 }}
          style={{
            width: '100%', maxWidth: 760, borderRadius: 14, padding: '22px 26px',
            border: `1.5px solid ${verdict.color}`,
            background: `linear-gradient(180deg, ${verdict.color}0c, transparent), ${textureCss(verdict.texture, verdict.color)}`,
            textAlign: 'center',
          }}
        >
          <div style={{
            fontFamily: FONTS.mono, fontSize: 10, letterSpacing: '0.24em', textTransform: 'uppercase',
            color: GAMER.t3, marginBottom: 8,
          }}>
            Connection verdict
          </div>
          <motion.div
            animate={verdict.glow ? { textShadow: [`0 0 12px ${verdict.color}66`, `0 0 28px ${verdict.color}aa`, `0 0 12px ${verdict.color}66`] } : {}}
            transition={{ duration: 2.2, repeat: Infinity }}
            style={{
              fontFamily: FONTS.display, fontSize: 'clamp(40px, 9vw, 76px)', fontWeight: 700,
              lineHeight: 1, letterSpacing: '0.02em', color: verdict.color,
            }}
          >
            {isLoading ? '···' : verdict.label}
          </motion.div>
          <div style={{
            fontFamily: FONTS.body, fontSize: 13, color: GAMER.t2, marginTop: 12, maxWidth: 520,
            marginLeft: 'auto', marginRight: 'auto', lineHeight: 1.5,
          }}>
            {isError ? 'The bridge could not be reached. Reconnect to make live proof.' : verdict.blurb}
          </div>
        </motion.div>
      </AnimatePresence>

      {/* Four BCRA lanes */}
      <div style={{
        width: '100%', maxWidth: 760, display: 'flex', gap: 12, flexWrap: 'wrap',
      }}>
        {LANES.map((l) => (
          <Lane key={l.key} name={l.name} sub={l.sub} term={l.term} lane={lanes[l.key]} />
        ))}
      </div>

      {/* Honest footer — what the verdict does and does not claim */}
      <div style={{
        fontFamily: FONTS.body, fontSize: 11.5, color: GAMER.t3, maxWidth: 600, textAlign: 'center',
        lineHeight: 1.5,
      }}>
        This verdict reflects your live connection only. It is not a ranking, and a green light
        means the protocol proved it — never decoration.
        <ExplainChip term="bcra" label="connection readiness" />
      </div>
    </div>
  )
}
