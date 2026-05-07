// Phase O1 C8 — DriftAlertBadge
//
// Cross-view drift visibility. Operator might be in GamerView during a grind
// when bundle drift or scope-governance drift fires — the C5 drawer is in
// DeveloperView, so they'd miss the event entirely. C8 surfaces the drift
// count as a floating top-right badge visible in ALL four views (Gamer /
// Developer / Manufacturer / BRP).
//
// Activation gate: hidden when no Cedar bundle anchored (useOperatorActivation
// returns row_count=0). When o1Active=false, polling is disabled via
// react-query enabled flag — zero polling cost for non-O1 operators.
//
// Visual: red pulsing ring + count when drift findings exist in 24h window.
// Click navigates to DeveloperView (parent provides onClick handler).
// Fully hidden when drift count is zero (no clutter for clean state).

import { motion, AnimatePresence } from 'framer-motion'
import { useOperatorActivation, useDriftLog } from '../api/bridgeApi'
import { FONTS, DEVELOPER } from '../shared/design/tokens'

export function DriftAlertBadge({ activeView, onClick }) {
  const { data: activation } = useOperatorActivation()
  const o1Active = (activation?.row_count ?? 0) > 0

  const { data: driftSummary } = useDriftLog({
    sinceMinutes: 1440, limit: 50, enabled: o1Active,
  })
  const driftCount = driftSummary?.row_count ?? 0

  // Hide when no drift OR not in O1 SHADOW phase
  if (!o1Active || driftCount === 0) return null

  // Hide when operator is already in DeveloperView (the panel is right there)
  if (activeView === 'developer') return null

  return (
    <AnimatePresence>
      <motion.button
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -10 }}
        transition={{ duration: 0.18 }}
        onClick={onClick}
        title={`${driftCount} drift finding${driftCount === 1 ? '' : 's'} in last 24h — click to open DeveloperView`}
        style={{
          position: 'fixed',
          top: 8,
          right: 16,
          zIndex: 100,
          background: `linear-gradient(180deg, ${DEVELOPER.red}33, rgba(2,4,8,0.95))`,
          border: `1px solid ${DEVELOPER.red}aa`,
          borderRadius: 4,
          padding: '6px 12px',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          boxShadow: `0 0 16px ${DEVELOPER.red}66`,
        }}
      >
        {/* Pulsing dot */}
        <motion.span
          animate={{ opacity: [0.4, 1, 0.4] }}
          transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }}
          style={{
            display: 'inline-block',
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: DEVELOPER.red,
            boxShadow: `0 0 8px ${DEVELOPER.red}`,
          }}
        />
        <span style={{
          fontFamily: FONTS.mono,
          fontSize: 9,
          fontWeight: 600,
          color: DEVELOPER.red,
          letterSpacing: '0.14em',
          textTransform: 'uppercase',
        }}>
          O1 Drift
        </span>
        <span style={{
          fontFamily: FONTS.mono,
          fontSize: 10,
          fontWeight: 700,
          color: '#ffffff',
          background: DEVELOPER.red,
          padding: '1px 6px',
          borderRadius: 3,
          minWidth: 18,
          textAlign: 'center',
        }}>
          {driftCount > 99 ? '99+' : driftCount}
        </span>
      </motion.button>
    </AnimatePresence>
  )
}
