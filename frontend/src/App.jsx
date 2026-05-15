import { useState, Suspense, lazy } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ViewSelector } from './ViewSelector'
import { HeartbeatProvider } from './heartbeat/HeartbeatProvider'
import { FONTS } from './shared/design/tokens'
import { DriftAlertBadge } from './components/DriftAlertBadge'
import { OperatorBar } from './components/OperatorBar'
import GlobalMockBanner from './components/GlobalMockBanner'
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
// 6th view: Phase O4-VPM-INT Stream C — VPM Registry tab. Read-only
// inspection surface for the Phase O4 VPM artifacts emitted by the
// Stream A.1+A.2 compilers. Sandboxed iframe rendering + Layer 3
// Anti-Hype Visual Grammar verification.
const VpmRegistryView  = lazy(() => import('./views/VpmRegistryView').then((m) => ({ default: m.VpmRegistryView })))

const VIEW_MAP = {
  gamer:        GamerView,
  developer:    DeveloperView,
  manufacturer: ManufacturerView,
  brp:          BrpView,
  marketplace:  MarketplaceView,
  vpm:          VpmRegistryView,
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
      {/* Mythos audit fix (post-/goal 2026-05-15): App-level mock
          indicator. Shows the 'bridge offline' banner across ALL tabs
          (previously only GamerView surfaced it). Auto-clears on the
          next successful fetch via client.js apiGet/apiPost hooks. */}
      <GlobalMockBanner />
      <div style={{
        display:       'flex',
        flexDirection: 'column',
        height:        '100dvh',
        overflow:      'hidden',
        background:    '#020408',
      }}>
        <ViewSelector activeView={activeView} onViewChange={setActiveView} />

        {/* Phase 238 — three-pill Operator bar (Sentry/Guardian/Curator).
            Always visible; click navigates to DeveloperView for drill-down. */}
        <div style={{
          padding:        '4px 16px',
          borderBottom:   '1px solid rgba(255,255,255,0.04)',
          background:     'rgba(2,4,8,0.85)',
          backdropFilter: 'blur(8px)',
        }}>
          <OperatorBar onClick={() => setActiveView('developer')} />
        </div>

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
