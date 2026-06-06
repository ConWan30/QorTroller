// src/main.jsx
// Phase 237-EXTEND: WagmiProvider wired in for the first time. ConsentPanel
// (and any future on-chain write surface — Phase 238 marketplace, Phase 239
// readiness consent, etc.) requires wagmi hooks to be inside this provider.
// The wagmi v2 docs require WagmiProvider OUTSIDE QueryClientProvider so its
// internal queries reuse the same client.
import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { WagmiProvider } from 'wagmi'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { wagmiConfig } from './shared/wagmiConfig'
import { App } from './App'
import PublicSessionViewer from './views/PublicSessionViewer'
import GicChainExplorerView from './views/GicChainExplorerView'
import PoacRecordExplorerView from './views/PoacRecordExplorerView'
import VhpCredentialView from './views/VhpCredentialView'
import AlgorithmCatalogView from './views/AlgorithmCatalogView'
import PublicExplorerLandingView from './views/PublicExplorerLandingView'

// Evidence OS — Phase O5-EVIDENCE-OS Stage 1
// Forensic instrument panel; new IA replacing the audience-tab SPA
// gradually. Existing legacy views preserved at /, /session, /gic,
// /record, /vhp, /algorithms, /explorer.
import AppShell from './os/AppShell'
import EvidenceGraphWorkspace from './os/workspaces/EvidenceGraphWorkspace'
import ForensicReplayWorkspace from './os/workspaces/ForensicReplayWorkspace'
import ProtocolStateWorkspace from './os/workspaces/ProtocolStateWorkspace'
import { Navigate } from 'react-router-dom'
import { markReality } from './design/realityHeartbeat'
// LiveMatchWorkspace + OperatorQueueWorkspace are intentionally NOT routed here:
// they duplicated the dashboard's Gamer / Operator·Evidence tabs and were
// de-duplicated out of Evidence OS (QRESCE-0001 v0.5 design alignment). The
// component files are preserved (still unit-tested) but no longer have an /os tab.

// Consent Cockpit dApp (2026-06-04) — standalone, top-level surface at
// /consent that supersedes the right-edge ConsentPanel drawer formerly
// embedded inside GamerView. Lazy-loaded so the dashboard bundle doesn't
// pay for wagmi-write code paths unless the gamer opens the dApp.
const ConsentCockpitDapp = React.lazy(() => import('./dapps/ConsentCockpit'))

// Verified Replay Card (2026-06-06) — public, share-able cryptographic
// proof artifact. /replay/:hash renders the card with chrome (back-link,
// copy-URL strip); /replay/embed/:hash strips chrome + transparent
// background for streamer OBS overlays. Lazy-loaded for the same bundle
// hygiene reason as the Cockpit. The card is the viral mechanism — the
// moment a PROOF_BUILT outcome becomes a Discord / Twitter screenshot.
const VerifiedReplayCardDapp = React.lazy(() => import('./dapps/VerifiedReplay'))

// Mainstream gamer onboarding (2026-06-06) — /start. Editorial-trailer
// surface for first-time gamers who heard about the protocol from a
// streamer and need an entry door that isn't the operator dashboard.
// Scroll-triggered storytelling in three acts; pulls live GIC chain
// head so the "this is real right now" moment lands. Lazy-loaded so the
// dashboard bundle doesn't pay for framer-motion until /start opens.
const StartDapp = React.lazy(() => import('./dapps/Start'))

// Public Hardware Authenticity Verify (2026-06-06) — /verify/:deviceId.
// No auth, no wallet, no chrome. Reads VAPIManufacturerDeviceRegistry
// via the public_forensic_api /device/:deviceId endpoint and renders a
// forensic-certificate verdict. Bookmark-able, share-able, embed-friendly.
// Lazy-loaded so the dashboard doesn't pay for the certificate styling.
const HardwareVerifyDapp = React.lazy(() => import('./dapps/HardwareVerify'))

// WMP Researcher Landing (2026-06-06) — /research. Editorial-scientific
// surface for AI / world-model research labs. Side-rail TOC, dense type,
// runnable in-browser verifier that mirrors sdk/wmp_verify.py byte-
// identically (structural rehash port). Trust-by-execution. Lazy-loaded.
const ResearchDapp = React.lazy(() => import('./dapps/Research'))

import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

// v2 · item D — feed the reality heartbeat from the data layer: any successful
// bridge query is a real beat that drives the app-wide ● LIVE signal.
queryClient.getQueryCache().subscribe((event) => {
  if (event?.type === 'updated' && event.query?.state?.status === 'success') {
    markReality(event.query.state.dataUpdatedAt)
  }
})

// Phase O5-PUBLIC-VIEWER — BrowserRouter wraps the app so the public
// route /session/:commitmentHex resolves alongside the default operator
// dashboard at /. INV-PUBLIC-ROUTE-001 pins these two minimum routes.
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <WagmiProvider config={wagmiConfig}>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/session/:commitmentHex" element={<PublicSessionViewer />} />
            <Route path="/gic/:grindSessionId" element={<GicChainExplorerView />} />
            <Route path="/record/:deviceId/:counter" element={<PoacRecordExplorerView />} />
            <Route path="/vhp/:tokenId" element={<VhpCredentialView />} />
            <Route path="/algorithms" element={<AlgorithmCatalogView />} />
            <Route path="/explorer" element={<PublicExplorerLandingView />} />

            {/* Evidence OS — nested under /os with AppShell layout.
                /os redirects to /os/evidence (signature workspace). */}
            <Route path="/os" element={<AppShell />}>
              <Route index element={<Navigate to="evidence" replace />} />
              <Route path="evidence" element={<EvidenceGraphWorkspace />} />
              {/* Stage 4 — Forensic Replay folds the 6 public viewers
                  inside the OS shell via nested routes. The viewers
                  themselves are reused unchanged; they read params
                  via useParams() which works for nested routes too. */}
              <Route path="replay" element={<ForensicReplayWorkspace />}>
                <Route path="session/:commitmentHex" element={<PublicSessionViewer />} />
                <Route path="gic/:grindSessionId"    element={<GicChainExplorerView />} />
                <Route path="record/:deviceId/:counter" element={<PoacRecordExplorerView />} />
                <Route path="vhp/:tokenId"           element={<VhpCredentialView />} />
                <Route path="algorithms"             element={<AlgorithmCatalogView />} />
              </Route>
              <Route path="protocol" element={<ProtocolStateWorkspace />} />
            </Route>

            {/* Consent Cockpit dApp — standalone, bookmark-able URL.
                /cockpit aliases /consent for share-link ergonomics. */}
            <Route
              path="/consent"
              element={
                <React.Suspense fallback={null}>
                  <ConsentCockpitDapp />
                </React.Suspense>
              }
            />
            <Route path="/cockpit" element={<Navigate to="/consent" replace />} />

            {/* Verified Replay Card dApp — public, no auth, no wallet.
                /replay/:hash is the share-able URL; /replay/embed/:hash
                is the OBS-overlay variant (transparent + chrome-less).
                Both routes share the same component; the component
                inspects window.location.pathname to switch modes. */}
            <Route
              path="/replay/embed/:hash"
              element={
                <React.Suspense fallback={null}>
                  <VerifiedReplayCardDapp />
                </React.Suspense>
              }
            />
            <Route
              path="/replay/:hash"
              element={
                <React.Suspense fallback={null}>
                  <VerifiedReplayCardDapp />
                </React.Suspense>
              }
            />
            <Route
              path="/replay"
              element={
                <React.Suspense fallback={null}>
                  <VerifiedReplayCardDapp />
                </React.Suspense>
              }
            />

            {/* Mainstream gamer onboarding — /start (alias /play). The
                editorial-trailer surface; closes by routing to /consent. */}
            <Route
              path="/start"
              element={
                <React.Suspense fallback={null}>
                  <StartDapp />
                </React.Suspense>
              }
            />
            <Route path="/play" element={<Navigate to="/start" replace />} />

            {/* Public Hardware Authenticity Verify. /verify accepts manual
                input; /verify/:deviceId resolves on-chain. */}
            <Route
              path="/verify/:deviceId"
              element={
                <React.Suspense fallback={null}>
                  <HardwareVerifyDapp />
                </React.Suspense>
              }
            />
            <Route
              path="/verify"
              element={
                <React.Suspense fallback={null}>
                  <HardwareVerifyDapp />
                </React.Suspense>
              }
            />

            {/* WMP Researcher Landing — /research (alias /wmp). */}
            <Route
              path="/research"
              element={
                <React.Suspense fallback={null}>
                  <ResearchDapp />
                </React.Suspense>
              }
            />
            <Route path="/wmp" element={<Navigate to="/research" replace />} />

            <Route path="/" element={<App />} />
            <Route path="*" element={<App />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    </WagmiProvider>
  </React.StrictMode>
)
