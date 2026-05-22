import { useState, Suspense, lazy } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ViewSelector } from './ViewSelector'
import { HeartbeatProvider } from './heartbeat/HeartbeatProvider'
import { FONTS } from './shared/design/tokens'
import { DriftAlertBadge } from './components/DriftAlertBadge'
// QRESCE-0001 v0.5 gamer-aesthetic Tweaks layer (newer Claude-Design export).
// Mounted at the app root — matching the design's
// root.render(<QtTweaksProvider><App/></QtTweaksProvider>) — so the opt-in vibe
// (scanlines / CRT / grain / hash-storm / glow / GIC landing FX) + the visible
// toggle + the foot vibe-label are app-wide. Default state is forensic-restraint.
import { QtTweaksProvider } from './design/Tweaks'
// v2 design pass · item A — the persistent eyebrow-row spine (shared across all
// 6 dashboard tabs + the 3 Evidence OS workspaces). Each view names itself here.
import { EyebrowProvider, ViewEyebrowBar } from './design/Eyebrow'
import './design/qortroller-kit.css'
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
// Tab 05 — IoTeX grant-evaluator deck (brand-locked Claude-Design export served
// from /grant-brief.html). Public; no auth gate (sharable with evaluators).
const GrantBriefView   = lazy(() => import('./views/GrantBriefView').then((m) => ({ default: m.GrantBriefView })))
// Tab 06 — Reference codex (brand-locked /qortroller-reference.html): the
// canonical "what / how / forward" reference for QorTroller. Public; no auth.
const ReferenceView    = lazy(() => import('./views/ReferenceView').then((m) => ({ default: m.ReferenceView })))

const VIEW_MAP = {
  gamer:        GamerView,
  forensic:     ForensicView,
  operator:     OperatorView,
  grant:        GrantBriefView,
  reference:    ReferenceView,
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
      </EyebrowProvider>
      </QtTweaksProvider>
    </HeartbeatProvider>
  )
}
