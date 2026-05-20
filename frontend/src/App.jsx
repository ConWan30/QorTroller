import { useState, Suspense, lazy } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ViewSelector } from './ViewSelector'
import { HeartbeatProvider } from './heartbeat/HeartbeatProvider'
import { FONTS } from './shared/design/tokens'
import { DriftAlertBadge } from './components/DriftAlertBadge'
// Phase 238 Frontend Foundation Revamp — VAPI theme tokens (CSS variable lock)
import './styles/vapi-theme.css'

const GamerView        = lazy(() => import('./views/GamerView').then((m) => ({ default: m.GamerView })))
const DeveloperView    = lazy(() => import('./views/DeveloperView').then((m) => ({ default: m.DeveloperView })))
const ManufacturerView = lazy(() => import('./views/ManufacturerView').then((m) => ({ default: m.ManufacturerView })))
// 4th view: BRP renderer post-milestone incorporation (OQ-7).
// Pre-ceremony, live: false posture. See frontend/src/brp/VENDORED_FROM.md.
const BrpView          = lazy(() => import('./views/BrpView').then((m) => ({ default: m.BrpView })))
// 5th view: Phase 238 PALL Marketplace — top-level tab.
// Sellers + buyers + auditors share this surface; operator listing form
// hidden in O1.
const MarketplaceView  = lazy(() => import('./views/MarketplaceView').then((m) => ({ default: m.MarketplaceView })))
// VPM Proof page (tab 04) — Claude-Design certificate gallery + forensic
// inspector. Renders each registry artifact via fetch + srcDoc + cache:no-store,
// recomputes its SHA-256 in-browser (HASH-OK), and runs verifyVpmGrammar
// against the FROZEN 6-state visual-grammar markers.
const VpmProofView     = lazy(() => import('./views/VpmProofView').then((m) => ({ default: m.VpmProofView })))
// QRESCE-0001 v0.5 grant-evaluator remodel — two design-language views wired
// to the real bridge hooks + real in-browser verifiers (named exports).
const ForensicView     = lazy(() => import('./views/ForensicView').then((m) => ({ default: m.ForensicView })))
const OperatorView     = lazy(() => import('./views/OperatorView').then((m) => ({ default: m.OperatorView })))

const VIEW_MAP = {
  gamer:        GamerView,
  forensic:     ForensicView,
  operator:     OperatorView,
  developer:    DeveloperView,
  manufacturer: ManufacturerView,
  brp:          BrpView,
  marketplace:  MarketplaceView,
  vpm:          VpmProofView,
}

function ViewLoader() {
  return (
    <div style={{
      flex:           1,
      display:        'flex',
      alignItems:     'center',
      justifyContent: 'center',
      fontFamily:     FONTS.mono,
      fontSize:       9,
      letterSpacing:  '2px',
      color:          'rgba(74,158,255,0.4)',
    }}>
      LOADING ···
    </div>
  )
}

export function App() {
  const [activeView, setActiveView] = useState('gamer')
  const ActiveComponent = VIEW_MAP[activeView]

  return (
    <HeartbeatProvider>
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

        {/* Phase O1 C8 — cross-view drift alert. Hidden by default; renders
            only when O1 SHADOW agents are anchored AND drift findings exist
            in the last 24h AND operator is NOT already in DeveloperView
            (where the dedicated drawer is). Click navigates to DeveloperView. */}
        <DriftAlertBadge
          activeView={activeView}
          onClick={() => setActiveView('developer')}
        />

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
    </HeartbeatProvider>
  )
}
