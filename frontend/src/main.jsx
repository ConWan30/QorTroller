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

            <Route path="/" element={<App />} />
            <Route path="*" element={<App />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    </WagmiProvider>
  </React.StrictMode>
)
