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
import { wagmiConfig } from './shared/wagmiConfig'
import { App } from './App'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <WagmiProvider config={wagmiConfig}>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </WagmiProvider>
  </React.StrictMode>
)
