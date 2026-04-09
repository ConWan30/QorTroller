// src/shared/components/index.jsx
// All shared components — imported by tier roots

import React, { Component } from 'react'
import { useConnect, useAccount, useDisconnect } from 'wagmi'
import { injected } from 'wagmi/connectors'
import { useQuery } from '@tanstack/react-query'
import { useAuthStore } from '../store/authStore'
import { FONTS, GAMER, DEVELOPER, MANUFACTURER } from '../design/tokens'
import { IOTEXSCAN, IOPAY_DOWNLOAD } from '../chain'

// ─── BRIDGE STATUS BAR ───────────────────────────────────────
export function BridgeStatusBar({ tier = 'gamer' }) {
  const accent = tier === 'gamer' ? GAMER.cyan
               : tier === 'developer' ? DEVELOPER.orange
               : MANUFACTURER.blue

  const { data, isError } = useQuery({
    queryKey:       ['health'],
    queryFn:        () => fetch('/health').then(r => r.json()),
    refetchInterval: 10_000,
    retry:           1,
  })

  const live = !isError && data?.status === 'ok'

  return (
    <div style={{
      display:        'flex',
      alignItems:     'center',
      gap:            6,
      fontFamily:     FONTS.mono,
      fontSize:       9,
      color:          live ? accent : '#ff3b5c',
      background:     live ? `${accent}08` : '#ff3b5c08',
      border:         `1px solid ${live ? accent : '#ff3b5c'}22`,
      borderRadius:   4,
      padding:        '4px 10px',
      letterSpacing:  '0.5px',
    }}>
      <span style={{
        width: 5, height: 5, borderRadius: '50%',
        background: live ? accent : '#ff3b5c',
        animation: live ? 'vapi-pulse 2s infinite' : 'none',
        flexShrink: 0,
      }} />
      {live ? `IOTX TESTNET · 4690` : 'BRIDGE OFFLINE'}
      {data?.phase && <span style={{ opacity: .5 }}>· Phase {data.phase}</span>}
    </div>
  )
}

// ─── WALLET CONNECT BUTTON ───────────────────────────────────
export function WalletConnectButton({ accent = GAMER.cyan }) {
  const { connect }    = useConnect()
  const { disconnect } = useDisconnect()
  const { address, isConnected } = useAccount()
  const setWallet = useAuthStore(s => s.setWalletAddress)

  React.useEffect(() => {
    if (address) setWallet(address)
  }, [address])

  const shortAddr = address
    ? `${address.slice(0, 6)}···${address.slice(-4)}`
    : null

  const noWallet = typeof window !== 'undefined' && !window.ethereum

  if (noWallet) return (
    <a
      href={IOPAY_DOWNLOAD}
      target="_blank"
      rel="noreferrer"
      style={{
        fontFamily:   FONTS.mono,
        fontSize:     9,
        padding:      '5px 12px',
        border:       `1px solid ${accent}33`,
        borderRadius: 4,
        background:   `${accent}10`,
        color:        accent,
        textDecoration: 'none',
        letterSpacing: '0.8px',
      }}
    >
      Install ioPay
    </a>
  )

  return (
    <button
      onClick={() => isConnected
        ? disconnect()
        : connect({ connector: injected() })
      }
      style={{
        fontFamily:   FONTS.mono,
        fontSize:     9,
        padding:      '5px 12px',
        border:       `1px solid ${accent}33`,
        borderRadius: 4,
        background:   isConnected ? `${accent}18` : `${accent}10`,
        color:        accent,
        cursor:       'pointer',
        letterSpacing: '0.8px',
        transition:   'all .15s',
      }}
    >
      {isConnected ? shortAddr : 'Connect ioPay'}
    </button>
  )
}

// ─── CHAIN ADDRESS LINK ──────────────────────────────────────
export function ChainAddressLink({ address, label, accent = GAMER.cyan }) {
  if (!address) return null
  const short = `${address.slice(0, 8)}···${address.slice(-4)}`
  return (
    <a
      href={`${IOTEXSCAN}/address/${address}`}
      target="_blank"
      rel="noreferrer"
      style={{
        fontFamily:     FONTS.mono,
        fontSize:       9,
        color:          accent,
        textDecoration: 'none',
        borderLeft:     `2px solid ${accent}40`,
        paddingLeft:    6,
        letterSpacing:  '0.3px',
      }}
    >
      {label || short}
    </a>
  )
}

// ─── DEMO MODE BANNER ────────────────────────────────────────
export function DemoModeBanner({ dryRun = true, tier = 'gamer' }) {
  if (!dryRun) return null
  const accent = tier === 'gamer' ? GAMER.orange
               : tier === 'developer' ? DEVELOPER.orange
               : MANUFACTURER.orange
  return (
    <div style={{
      display:      'flex',
      alignItems:   'center',
      gap:          8,
      padding:      '5px 12px',
      background:   `${accent}08`,
      borderBottom: `1px solid ${accent}22`,
      fontFamily:   FONTS.mono,
      fontSize:     9,
      color:        accent,
      letterSpacing: '1px',
    }}>
      <span style={{
        padding: '1px 6px',
        border: `1px solid ${accent}35`,
        borderRadius: 3,
        background: `${accent}12`,
      }}>DRY RUN</span>
      dry_run=True · Enforcement not live · N=0/100 live adjudications
    </div>
  )
}

// ─── ERROR BOUNDARY ──────────────────────────────────────────
export class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }
  render() {
    if (!this.state.hasError) return this.props.children
    const accent = this.props.accent || GAMER.cyan
    return (
      <div style={{
        padding:    '1rem',
        background: '#03060a',
        border:     '1px solid #ff3b5c22',
        borderRadius: 8,
        fontFamily: FONTS.mono,
        fontSize:   10,
      }}>
        <div style={{ color: '#ff3b5c', marginBottom: 4 }}>COMPONENT ERROR</div>
        <div style={{ color: '#3a4050' }}>{this.state.error?.message}</div>
        <div style={{ color: accent, marginTop: 8, fontSize: 9 }}>
          DEMO MODE — API may be offline
        </div>
      </div>
    )
  }
}

// ─── STAT CARD ───────────────────────────────────────────────
export function StatCard({ label, value, unit = '', accent = GAMER.cyan, bg = GAMER.bg2 }) {
  return (
    <div style={{
      background:   bg,
      borderRadius: 6,
      padding:      '8px 10px',
    }}>
      <div style={{
        fontFamily:    FONTS.display,
        fontSize:      8,
        letterSpacing: '1.5px',
        textTransform: 'uppercase',
        color:         GAMER.t3,
        marginBottom:  3,
      }}>
        {label}
      </div>
      <div style={{
        fontFamily: FONTS.mono,
        fontSize:   18,
        fontWeight: 500,
        color:      accent,
        lineHeight: 1,
      }}>
        {value}
        {unit && <span style={{ fontSize: 10, color: GAMER.t3, marginLeft: 3 }}>{unit}</span>}
      </div>
    </div>
  )
}

// ─── PANEL WRAPPER ───────────────────────────────────────────
export function Panel({ title, badge, badgeColor, bg, bd, children, style }) {
  return (
    <div style={{
      background:   bg || GAMER.bg1,
      border:       `1px solid ${bd || GAMER.bd}`,
      borderRadius: 8,
      overflow:     'hidden',
      ...style,
    }}>
      {title && (
        <div style={{
          display:      'flex',
          alignItems:   'center',
          justifyContent: 'space-between',
          padding:      '10px 14px',
          borderBottom: `1px solid ${bd || GAMER.bd}`,
        }}>
          <span style={{
            fontFamily:    FONTS.display,
            fontSize:      9,
            fontWeight:    600,
            letterSpacing: '2px',
            textTransform: 'uppercase',
            color:         '#3a6070',
          }}>
            {title}
          </span>
          {badge && (
            <span style={{
              fontFamily: FONTS.mono,
              fontSize:   8,
              padding:    '2px 8px',
              borderRadius: 3,
              border:     `1px solid ${badgeColor || GAMER.cyan}35`,
              background: `${badgeColor || GAMER.cyan}10`,
              color:      badgeColor || GAMER.cyan,
              whiteSpace: 'nowrap',
            }}>
              {badge}
            </span>
          )}
        </div>
      )}
      {children}
    </div>
  )
}
