// Phase O1 C5 — OperatorAgentsDrawer
//
// Bottom-edge slide-up drawer in DeveloperView. Mirrors the existing left/
// right drawer pattern (gateOpen / pitlOpen) but on the bottom edge so it
// doesn't compete with the centered pipeline visual.
//
// Composes:
//   - ShadowLogPanel   (left half) — Cedar evaluations
//   - DriftFindingsPanel (right half) — drift findings from C4 sweeper
//
// Activation gate (handled by parent): drawer + handle only render when
// useOperatorActivation().data?.row_count > 0. This means operators on the
// main protocol track who haven't activated Phase O1 SHADOW agents see
// DeveloperView unchanged. Zero polling cost; zero UI clutter.
//
// Conditional polling: when drawer is closed, the inner panels' enabled prop
// is set to `open` so polling only happens while drawer is visible. Closed
// drawer = zero shadow/drift queries.

import { motion, AnimatePresence } from 'framer-motion'
import { FONTS, DEVELOPER } from '../shared/design/tokens'
import { ShadowLogPanel } from './ShadowLogPanel'
import { DriftFindingsPanel } from './DriftFindingsPanel'

const DRAWER_HEIGHT_VH = 55  // 55% viewport height when open

export function OperatorAgentsDrawer({ open, onClose, driftCount = 0 }) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ y: '100%' }}
          animate={{ y: 0 }}
          exit={{ y: '100%' }}
          transition={{ type: 'tween', duration: 0.22, ease: 'easeOut' }}
          style={{
            position: 'absolute',
            left: 0, right: 0, bottom: 0,
            height: `${DRAWER_HEIGHT_VH}vh`,
            background: `linear-gradient(180deg, ${DEVELOPER.bg1} 0%, ${DEVELOPER.bg} 100%)`,
            borderTop: `1px solid ${DEVELOPER.orange}66`,
            boxShadow: `0 -8px 32px ${DEVELOPER.orange}1a`,
            display: 'flex',
            flexDirection: 'column',
            zIndex: 20,
          }}
        >
          {/* Drawer header */}
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '10px 16px',
            borderBottom: `1px solid ${DEVELOPER.bd}`,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{
                fontFamily: FONTS.display, fontSize: 12, fontWeight: 700,
                letterSpacing: '0.22em', color: DEVELOPER.orange,
                textTransform: 'uppercase',
              }}>
                Operator Agents — O1 Shadow
              </div>
              {driftCount > 0 && (
                <div style={{
                  fontFamily: FONTS.mono, fontSize: 9, fontWeight: 600,
                  color: DEVELOPER.red,
                  background: `${DEVELOPER.red}22`,
                  border: `1px solid ${DEVELOPER.red}66`,
                  borderRadius: 3,
                  padding: '2px 6px',
                }} title="Drift findings in last 24h">
                  ⚠ {driftCount} DRIFT
                </div>
              )}
            </div>
            <button
              onClick={onClose}
              style={{
                background: 'transparent',
                border: `1px solid ${DEVELOPER.bd}`,
                borderRadius: 3,
                color: DEVELOPER.t2,
                fontFamily: FONTS.mono,
                fontSize: 9,
                padding: '4px 10px',
                cursor: 'pointer',
                letterSpacing: '0.1em',
              }}
            >
              CLOSE ↓
            </button>
          </div>

          {/* Body — two-panel split */}
          <div style={{
            flex: 1, minHeight: 0,
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: 12,
            padding: '12px 16px',
          }}>
            <ShadowLogPanel enabled={open} />
            <DriftFindingsPanel enabled={open} />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

// Handle positioned bottom-right corner (avoids overlap with the bottom-center
// status chips in DeveloperView at bottom: 16).
export function OperatorAgentsDrawerHandle({ onClick, driftCount = 0 }) {
  const hasDrift = driftCount > 0
  return (
    <motion.button
      onClick={onClick}
      whileHover={{ y: -3 }}
      style={{
        position: 'absolute',
        right: 16,
        bottom: 16,
        height: 24,
        padding: '0 12px',
        background: hasDrift
          ? `linear-gradient(180deg, ${DEVELOPER.red}33, ${DEVELOPER.bg1})`
          : `linear-gradient(180deg, ${DEVELOPER.orange}22, ${DEVELOPER.bg1})`,
        border: `1px solid ${hasDrift ? DEVELOPER.red : DEVELOPER.orange}66`,
        borderRadius: 4,
        cursor: 'pointer',
        zIndex: 10,
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        boxShadow: hasDrift
          ? `0 0 16px ${DEVELOPER.red}44`
          : `0 0 8px ${DEVELOPER.orange}1a`,
      }}
    >
      <span style={{
        fontFamily: FONTS.mono, fontSize: 8, fontWeight: 600,
        color: hasDrift ? DEVELOPER.red : DEVELOPER.orange,
        letterSpacing: '0.16em',
        textTransform: 'uppercase',
      }}>
        ↑ O1 Agents
      </span>
      {hasDrift && (
        <span style={{
          fontFamily: FONTS.mono, fontSize: 8, fontWeight: 700,
          color: DEVELOPER.red,
          background: `${DEVELOPER.red}33`,
          padding: '1px 5px',
          borderRadius: 2,
        }}>
          {driftCount}
        </span>
      )}
    </motion.button>
  )
}
