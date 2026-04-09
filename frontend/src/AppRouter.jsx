// src/AppRouter.jsx
import React, { Suspense, lazy } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { TierSelector } from './shared/components/TierSelector'
import { FONTS } from './shared/design/tokens'

// Lazy-load tier roots for code splitting
const GamerRoot        = lazy(() => import('./tiers/gamer/GamerRoot'))
const DeveloperRoot    = lazy(() => import('./tiers/developer/DeveloperRoot'))
const ManufacturerRoot = lazy(() => import('./tiers/manufacturer/ManufacturerRoot'))

function Loading({ accent = '#00d4ff' }) {
  return (
    <div style={{
      minHeight:      '60vh',
      display:        'flex',
      alignItems:     'center',
      justifyContent: 'center',
      fontFamily:     FONTS.mono,
      fontSize:       9,
      letterSpacing:  '2px',
      color:          accent,
    }}>
      LOADING ···
    </div>
  )
}

export function AppRouter() {
  return (
    <BrowserRouter>
      <Suspense fallback={<Loading />}>
        <Routes>
          <Route path="/"                  element={<TierSelector />} />
          <Route path="/gamer/*"           element={<GamerRoot />} />
          <Route path="/developer/*"       element={<DeveloperRoot />} />
          <Route path="/manufacturer/*"    element={<ManufacturerRoot />} />
          <Route path="*"                  element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}
