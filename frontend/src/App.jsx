import { useState, Suspense, lazy } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ViewSelector } from './ViewSelector'
import { HeartbeatProvider } from './heartbeat/HeartbeatProvider'
import { FONTS } from './shared/design/tokens'

const GamerView        = lazy(() => import('./views/GamerView').then((m) => ({ default: m.GamerView })))
const DeveloperView    = lazy(() => import('./views/DeveloperView').then((m) => ({ default: m.DeveloperView })))
const ManufacturerView = lazy(() => import('./views/ManufacturerView').then((m) => ({ default: m.ManufacturerView })))
// 4th view: BRP renderer post-milestone incorporation (OQ-7).
// Pre-ceremony, live: false posture. See frontend/src/brp/VENDORED_FROM.md.
const BrpView          = lazy(() => import('./views/BrpView').then((m) => ({ default: m.BrpView })))

const VIEW_MAP = {
  gamer:        GamerView,
  developer:    DeveloperView,
  manufacturer: ManufacturerView,
  brp:          BrpView,
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
        overflow:      'hidden',
        background:    '#020408',
      }}>
        <ViewSelector activeView={activeView} onViewChange={setActiveView} />

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
