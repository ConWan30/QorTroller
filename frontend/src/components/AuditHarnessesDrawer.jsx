// Phase O4 post-backlog-closure — Audit harnesses drawer + handle.
//
// Strictly-additive: NEW drawer at TOP-RIGHT (the only remaining
// uncluttered drawer position; existing drawers occupy top-CENTER,
// bottom-LEFT, bottom-RIGHT). Mirrors the existing drawer pattern:
//   - AnimatePresence slide-in
//   - DEVELOPER design tokens
//   - Activation-gated (parent passes `enabled` for the inner hooks)
//   - Conditional polling: panels poll only while drawer is open
//
// Three panels stacked vertically (G7 + CFSS + Curator-graduation).
// Together they surface the operator-facing state of every gate the
// Curator O2 → O3 graduation ceremony depends on.
//
// Drawer height: 65vh (taller than the 55vh OperatorAgentsDrawer
// because three panels need more vertical space). Width: 360px
// (anchored to right edge; slides in from right).
// zIndex: 23 (above the existing drawers at 20/21/22 so it stacks on top
// when any of them is also open).

import { motion, AnimatePresence } from 'framer-motion'
import { FONTS, DEVELOPER } from '../shared/design/tokens'
import { G7ReadinessPanel } from './G7ReadinessPanel'
import { CFSSLaneDriftPanel } from './CFSSLaneDriftPanel'
import { CuratorGraduationPanel } from './CuratorGraduationPanel'

const DRAWER_WIDTH_PX = 380

export function AuditHarnessesDrawer({ open, onClose }) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ x: '100%' }}
          animate={{ x: 0 }}
          exit={{ x: '100%' }}
          transition={{ type: 'tween', duration: 0.22, ease: 'easeOut' }}
          style={{
            position: 'absolute',
            top: 60,
            right: 0,
            bottom: 60,
            width: DRAWER_WIDTH_PX,
            background: `linear-gradient(180deg, ${DEVELOPER.bg1} 0%, ${DEVELOPER.bg} 100%)`,
            borderLeft: `1px solid ${DEVELOPER.orange}66`,
            boxShadow: `-8px 0 32px ${DEVELOPER.orange}1a`,
            display: 'flex',
            flexDirection: 'column',
            zIndex: 23,
            overflowY: 'auto',
          }}
        >
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '10px 16px',
            borderBottom: `1px solid ${DEVELOPER.bd}`,
          }}>
            <div style={{
              fontFamily: FONTS.display, fontSize: 12, fontWeight: 700,
              letterSpacing: '0.22em', color: DEVELOPER.orange,
              textTransform: 'uppercase',
            }}>
              Audit Harnesses
            </div>
            <button
              onClick={onClose}
              style={{
                background: 'transparent',
                border: `1px solid ${DEVELOPER.bd}`,
                borderRadius: 3,
                padding: '4px 10px',
                fontFamily: FONTS.mono, fontSize: 11,
                color: DEVELOPER.fg2,
                cursor: 'pointer',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.color = DEVELOPER.fg }}
              onMouseLeave={(e) => { e.currentTarget.style.color = DEVELOPER.fg2 }}
            >
              ✕ Close
            </button>
          </div>

          {/* Three panels stacked. enabled={open} = poll only while drawer is visible. */}
          <G7ReadinessPanel enabled={open} />
          <div style={{ borderTop: `1px solid ${DEVELOPER.bd}` }} />
          <CFSSLaneDriftPanel enabled={open} />
          <div style={{ borderTop: `1px solid ${DEVELOPER.bd}` }} />
          <CuratorGraduationPanel enabled={open} />

          <div style={{
            marginTop: 'auto',
            padding: '10px 16px',
            borderTop: `1px solid ${DEVELOPER.bd}`,
            fontFamily: FONTS.mono, fontSize: 9, color: DEVELOPER.fg2,
            lineHeight: 1.4,
          }}>
            Wallet-free + read-only. Polls bridge HTTP every 60s while open.
            <br />
            Bridge endpoints: <code>/operator/g7-curator-readiness</code>,
            <code>/cfss-lane-drift-status</code>, <code>/curator-graduation-readiness</code>.
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

// Drawer handle — anchored at TOP-RIGHT below the O3ReadinessDrawerHandle
// (which is at top-CENTER). Click to toggle the drawer.
//
// readinessVerdict prop (READY/BLOCKED/FAIL/ERROR) tints the handle:
// when verdict=READY the operator sees a green ★ badge calling out
// that Curator graduation is cleared.
export function AuditHarnessesDrawerHandle({ onClick, readinessVerdict = '' }) {
  const tint = readinessVerdict === 'READY'
    ? DEVELOPER.green
    : (readinessVerdict === 'FAIL' || readinessVerdict === 'ERROR')
      ? DEVELOPER.red
      : DEVELOPER.amber

  return (
    <button
      onClick={onClick}
      style={{
        position: 'absolute',
        top: 16,
        right: 16,
        background: DEVELOPER.bg1,
        border: `1px solid ${tint}66`,
        borderRadius: 4,
        padding: '6px 12px',
        fontFamily: FONTS.display, fontSize: 10, fontWeight: 700,
        letterSpacing: '0.16em', color: tint,
        textTransform: 'uppercase',
        cursor: 'pointer',
        zIndex: 19,
        display: 'flex', alignItems: 'center', gap: 6,
      }}
      title="Open Audit Harnesses drawer (G7 + CFSS + Curator graduation)"
      onMouseEnter={(e) => { e.currentTarget.style.background = `${tint}11` }}
      onMouseLeave={(e) => { e.currentTarget.style.background = DEVELOPER.bg1 }}
    >
      <span style={{ fontFamily: FONTS.mono, fontSize: 12 }}>⌖</span>
      Audits
      {readinessVerdict === 'READY' && (
        <span style={{ fontSize: 11, color: DEVELOPER.green }} title="Curator graduation cleared">
          ★
        </span>
      )}
    </button>
  )
}
