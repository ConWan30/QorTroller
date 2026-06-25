import { useState, Suspense, lazy } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ViewSelector } from './ViewSelector'
import { HeartbeatProvider } from './heartbeat/HeartbeatProvider'
import { FONTS } from './shared/design/tokens'
// QRESCE-0001 v0.5 gamer-aesthetic Tweaks layer (newer Claude-Design export).
import { QtTweaksProvider } from './design/Tweaks'
// v2 design pass · item A — the persistent eyebrow-row spine.
import { EyebrowProvider, ViewEyebrowBar } from './design/Eyebrow'
import './design/qortroller-kit.css'
// Phase 238 Frontend Foundation Revamp — VAPI theme tokens (CSS variable lock)
import './styles/vapi-theme.css'

// Gamer-first full replacement (2026-06-24): the SPA is now gamer-only. Six tabs aligned to a
// gamer's necessity — LIVE (the Moment of Proof connect-state), PRESENCE, VAULT, RECEIPTS, MARKET,
// CODEX. The prior pro views (operator/manufacturer/grant/partner/forensic/developer/vpm/reference/
// chat) are removed from the app chrome; their files remain in src/views (recoverable in git) and
// the outreach decks stay served as static frontend/public/*.html so those URLs keep working.
const GamerView       = lazy(() => import('./views/GamerView').then((m) => ({ default: m.GamerView })))
const PresenceView    = lazy(() => import('./views/PresenceView').then((m) => ({ default: m.PresenceView })))
const VaultView       = lazy(() => import('./views/VaultView').then((m) => ({ default: m.VaultView })))
const ReceiptsView    = lazy(() => import('./views/ReceiptsView').then((m) => ({ default: m.ReceiptsView })))
const MarketplaceView = lazy(() => import('./views/MarketplaceView').then((m) => ({ default: m.MarketplaceView })))
const CodexView       = lazy(() => import('./views/CodexView').then((m) => ({ default: m.CodexView })))

const VIEW_MAP = {
  live:     GamerView,
  presence: PresenceView,
  vault:    VaultView,
  receipts: ReceiptsView,
  market:   MarketplaceView,
  codex:    CodexView,
}

function ViewLoader() {
  return (
    <div style={{
      flex:           1,
      display:        'flex',
      alignItems:     'center',
      justifyContent: 'center',
      fontFamily:     FONTS.mono,
      fontSize:       11,
      letterSpacing:  '2px',
      color:          'rgba(74,158,255,0.4)',
    }}>
      LOADING ···
    </div>
  )
}

export function App() {
  const [activeView, setActiveView] = useState('live')
  const ActiveComponent = VIEW_MAP[activeView] || GamerView

  return (
    <HeartbeatProvider>
      <QtTweaksProvider>
      <EyebrowProvider>
      <div style={{
        display:       'flex',
        flexDirection: 'column',
        height:        '100dvh',
        width:         '100%',
        maxWidth:      '100vw',
        overflow:      'hidden',
        overflowX:     'hidden',
        background:    '#020408',
      }}>
        <ViewSelector activeView={activeView} onViewChange={setActiveView} />

        {/* v2 · item A — persistent eyebrow spine. Same 32px row on every tab;
            each view registers its name + live readouts via useViewEyebrow. */}
        <ViewEyebrowBar />

        <AnimatePresence mode="wait">
          <motion.div
            key={activeView}
            initial={{ opacity: 0, scale: 0.99 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 1.01 }}
            transition={{ duration: 0.18, ease: 'easeInOut' }}
            style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}
          >
            <Suspense fallback={<ViewLoader />}>
              <ActiveComponent />
            </Suspense>
          </motion.div>
        </AnimatePresence>
      </div>
      </EyebrowProvider>
      </QtTweaksProvider>
    </HeartbeatProvider>
  )
}
