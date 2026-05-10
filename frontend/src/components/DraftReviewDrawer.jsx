// Phase O2-DRAFT-REVIEW-FRONTEND — DraftReviewDrawer
//
// Slide-up bottom drawer hosting DraftReviewPanel. Mirrors OperatorAgentsDrawer
// (Phase O1 C5) but takes the LEFT half of the bottom edge so the two drawers
// don't collide. Handle positioned bottom-left to avoid the existing
// OperatorAgentsDrawerHandle at bottom-right.
//
// Activation gate (parent's responsibility): drawer + handle only render when
// useOperatorActivation().data?.row_count > 0. Conditional polling: when
// closed, the inner panel's enabled prop is set to `open` so polling halts
// while drawer is hidden.

import { motion, AnimatePresence } from 'framer-motion'
import { FONTS, DEVELOPER } from '../shared/design/tokens'
import { DraftReviewPanel } from './DraftReviewPanel'

const DRAWER_HEIGHT_VH = 60

export function DraftReviewDrawer({ open, onClose, unreviewedCount = 0 }) {
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
            borderTop: `1px solid ${DEVELOPER.amber}66`,
            boxShadow: `0 -8px 32px ${DEVELOPER.amber}1a`,
            display: 'flex',
            flexDirection: 'column',
            zIndex: 21, // Above OperatorAgentsDrawer (zIndex 20)
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
                letterSpacing: '0.22em', color: DEVELOPER.amber,
                textTransform: 'uppercase',
              }}>
                Draft Review — O2 Suggest Decisions
              </div>
              {unreviewedCount > 0 && (
                <div style={{
                  fontFamily: FONTS.mono, fontSize: 9, fontWeight: 600,
                  color: DEVELOPER.amber,
                  background: `${DEVELOPER.amber}22`,
                  border: `1px solid ${DEVELOPER.amber}66`,
                  borderRadius: 3,
                  padding: '2px 6px',
                }} title="Unreviewed drafts in last 7d (decision IS NULL)">
                  {unreviewedCount} PENDING
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

          {/* Body */}
          <div style={{ flex: 1, minHeight: 0, padding: '12px 16px' }}>
            <DraftReviewPanel enabled={open} />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

// Handle positioned bottom-LEFT (avoids overlap with OperatorAgentsDrawerHandle
// at bottom-right and the bottom-center status chips in DeveloperView).
export function DraftReviewDrawerHandle({ onClick, unreviewedCount = 0 }) {
  const hasPending = unreviewedCount > 0
  return (
    <motion.button
      onClick={onClick}
      whileHover={{ y: -3 }}
      style={{
        position: 'absolute',
        left: 16,
        bottom: 16,
        height: 24,
        padding: '0 12px',
        background: hasPending
          ? `linear-gradient(180deg, ${DEVELOPER.amber}33, ${DEVELOPER.bg1})`
          : `linear-gradient(180deg, ${DEVELOPER.amber}1a, ${DEVELOPER.bg1})`,
        border: `1px solid ${DEVELOPER.amber}66`,
        borderRadius: 4,
        cursor: 'pointer',
        zIndex: 10,
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        boxShadow: hasPending
          ? `0 0 16px ${DEVELOPER.amber}44`
          : `0 0 8px ${DEVELOPER.amber}1a`,
      }}
    >
      <span style={{
        fontFamily: FONTS.mono, fontSize: 8, fontWeight: 600,
        color: DEVELOPER.amber,
        letterSpacing: '0.16em',
        textTransform: 'uppercase',
      }}>
        ↑ Draft Review
      </span>
      {hasPending && (
        <span style={{
          fontFamily: FONTS.mono, fontSize: 8, fontWeight: 700,
          color: DEVELOPER.amber,
          background: `${DEVELOPER.amber}33`,
          padding: '1px 5px',
          borderRadius: 2,
        }}>
          {unreviewedCount}
        </span>
      )}
    </motion.button>
  )
}
