// Phase O5-MLGA Stage 4 — MlgaLiveDrawer
//
// Bottom-right edge slide-up drawer in DeveloperView. Mirrors the
// OperatorAgentsDrawer pattern (commit 003ea85c) verbatim with z-index
// 23 (above the existing 20/21/22 progression).
//
// Mounts MlgaLivePanel with enabled={open} so polling halts when the
// drawer is closed. Handle badge: green when has_open_session=true;
// chip count = sessions_persisted_total (lifetime).

import { motion, AnimatePresence } from 'framer-motion'
import { FONTS, DEVELOPER } from '../shared/design/tokens'
import { MlgaLivePanel } from './MlgaLivePanel'

const DRAWER_HEIGHT_VH = 60

export function MlgaLiveDrawer({ open, onClose }) {
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
            borderTop: `1px solid ${DEVELOPER.green}66`,
            boxShadow: `0 -8px 32px ${DEVELOPER.green}1a`,
            display: 'flex',
            flexDirection: 'column',
            zIndex: 23,
          }}
        >
          {/* Drawer header */}
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '10px 16px',
            borderBottom: `1px solid ${DEVELOPER.bd}`,
          }}>
            <div style={{
              fontFamily: FONTS.display, fontSize: 12, fontWeight: 700,
              letterSpacing: '0.22em', color: DEVELOPER.green,
              textTransform: 'uppercase',
            }}>
              MLGA Live — Gameplay Audit + VPM artifacts
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

          {/* Body */}
          <div style={{
            flex: 1, minHeight: 0,
            padding: '12px 16px',
            overflow: 'hidden',
          }}>
            <MlgaLivePanel enabled={open} />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

// Handle positioned bottom-right; offset upward from the OperatorAgents
// handle (also at bottom: 16, right: 16) by 36px to avoid stacking.
export function MlgaLiveDrawerHandle({ onClick, hasOpenSession = false, sessionsTotal = 0 }) {
  return (
    <motion.button
      onClick={onClick}
      whileHover={{ y: -3 }}
      style={{
        position: 'absolute',
        right: 16,
        bottom: 52,  // 36px above OperatorAgentsDrawerHandle (bottom: 16)
        height: 24,
        padding: '0 12px',
        background: hasOpenSession
          ? `linear-gradient(180deg, ${DEVELOPER.green}33, ${DEVELOPER.bg1})`
          : `linear-gradient(180deg, ${DEVELOPER.green}22, ${DEVELOPER.bg1})`,
        border: `1px solid ${DEVELOPER.green}66`,
        borderRadius: 4,
        cursor: 'pointer',
        zIndex: 10,
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        boxShadow: hasOpenSession
          ? `0 0 16px ${DEVELOPER.green}44`
          : `0 0 8px ${DEVELOPER.green}1a`,
      }}
      title={hasOpenSession ? 'MLGA session open' : `${sessionsTotal} sessions persisted`}
    >
      <span style={{
        fontFamily: FONTS.mono, fontSize: 8, fontWeight: 600,
        color: DEVELOPER.green,
        letterSpacing: '0.16em',
        textTransform: 'uppercase',
      }}>
        ↑ MLGA {hasOpenSession ? '● LIVE' : ''}
      </span>
      {sessionsTotal > 0 && (
        <span style={{
          fontFamily: FONTS.mono, fontSize: 8, fontWeight: 700,
          color: DEVELOPER.green,
          background: `${DEVELOPER.green}33`,
          padding: '1px 5px',
          borderRadius: 2,
        }}>
          {sessionsTotal}
        </span>
      )}
    </motion.button>
  )
}
