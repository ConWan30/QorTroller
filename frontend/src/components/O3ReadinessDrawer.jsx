// Phase O3-READINESS-DASHBOARD — top-edge slide-down drawer
//
// Hosts O3ReadinessDashboard. Slides DOWN from the top edge so its handle
// (positioned top-center) avoids collision with the two bottom-edge drawers
// shipped in Phase O1 C5 (bottom-right) and Phase O2-DRAFT-REVIEW-FRONTEND
// (bottom-left).
//
// Activation gate handled by parent. Inner panel polls only when open.

import { motion, AnimatePresence } from 'framer-motion'
import { FONTS, DEVELOPER } from '../shared/design/tokens'
import { O3ReadinessDashboard } from './O3ReadinessDashboard'

const DRAWER_HEIGHT_VH = 55

export function O3ReadinessDrawer({ open, onClose, fleetAligned = false }) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ y: '-100%' }}
          animate={{ y: 0 }}
          exit={{ y: '-100%' }}
          transition={{ type: 'tween', duration: 0.22, ease: 'easeOut' }}
          style={{
            position: 'absolute',
            left: 0, right: 0, top: 0,
            height: `${DRAWER_HEIGHT_VH}vh`,
            background: `linear-gradient(0deg, ${DEVELOPER.bg1} 0%, ${DEVELOPER.bg} 100%)`,
            borderBottom: `1px solid ${DEVELOPER.green}66`,
            boxShadow: `0 8px 32px ${DEVELOPER.green}1a`,
            display: 'flex',
            flexDirection: 'column',
            zIndex: 22, // Above OperatorAgentsDrawer (20) + DraftReviewDrawer (21)
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
                letterSpacing: '0.22em', color: DEVELOPER.green,
                textTransform: 'uppercase',
              }}>
                O3 Readiness — Triple Dual-Anchor Countdown
              </div>
              {fleetAligned && (
                <div style={{
                  fontFamily: FONTS.mono, fontSize: 9, fontWeight: 700,
                  color: DEVELOPER.green,
                  background: `${DEVELOPER.green}22`,
                  border: `1px solid ${DEVELOPER.green}66`,
                  borderRadius: 3,
                  padding: '2px 6px',
                  letterSpacing: '0.1em',
                }}>FLEET ALIGNED</div>
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
              CLOSE ↑
            </button>
          </div>

          {/* Body */}
          <div style={{ flex: 1, minHeight: 0, padding: '12px 16px' }}>
            <O3ReadinessDashboard enabled={open} />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

// Handle positioned top-CENTER to avoid the two bottom handles.
export function O3ReadinessDrawerHandle({ onClick, fleetAligned = false }) {
  return (
    <motion.button
      onClick={onClick}
      whileHover={{ y: 3 }}
      style={{
        position: 'absolute',
        left: '50%',
        transform: 'translateX(-50%)',
        top: 16,
        height: 24,
        padding: '0 12px',
        background: fleetAligned
          ? `linear-gradient(0deg, ${DEVELOPER.green}33, ${DEVELOPER.bg1})`
          : `linear-gradient(0deg, ${DEVELOPER.green}1a, ${DEVELOPER.bg1})`,
        border: `1px solid ${DEVELOPER.green}66`,
        borderRadius: 4,
        cursor: 'pointer',
        zIndex: 10,
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        boxShadow: fleetAligned
          ? `0 0 16px ${DEVELOPER.green}44`
          : `0 0 8px ${DEVELOPER.green}1a`,
      }}
    >
      <span style={{
        fontFamily: FONTS.mono, fontSize: 8, fontWeight: 600,
        color: DEVELOPER.green,
        letterSpacing: '0.16em',
        textTransform: 'uppercase',
      }}>
        ↓ O3 Readiness
      </span>
      {fleetAligned && (
        <span style={{
          fontFamily: FONTS.mono, fontSize: 8, fontWeight: 700,
          color: DEVELOPER.green,
          background: `${DEVELOPER.green}33`,
          padding: '1px 5px',
          borderRadius: 2,
        }}>★</span>
      )}
    </motion.button>
  )
}
