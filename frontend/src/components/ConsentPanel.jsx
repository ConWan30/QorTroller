// ============================================================================
// DEPRECATED 2026-06-04 — superseded by the standalone Consent Cockpit dApp
// at /consent (frontend/src/dapps/ConsentCockpit/).
//
// This component is preserved in the tree for one release cycle so any
// cross-reference or test that still touches it does not break in the same
// PR. It is NO LONGER mounted in GamerView. Do NOT import this in new code;
// link to /consent instead.
//
// Removal target: next cleanup commit after the Cockpit ships.
// ============================================================================
//
// Phase 237-EXTEND — ConsentPanel (historical context preserved below)
//
// Right-edge slide-in drawer mirroring the PCCDrawer pattern (GamerView.jsx).
// Surfaces per-category consent state for the connected wallet AND lets the
// gamer grant/revoke directly via VAPIConsentRegistry — first wallet-write
// surface in this frontend.
//
// Honest UX scope: this is the MINIMUM-VIABLE consent surface — functional
// (4 toggles, wallet-connect button, disclosure copy) but NOT polished
// (no copy-review for legal defensibility, no animation polish, no mobile
// responsiveness, no per-category tooltips). Polished UX is a future phase.
//
// Self-sovereignty invariant: every grant/revoke is signed by the gamer's
// wallet (msg.sender on the contract). The bridge is a READER of consent
// state; it never writes on behalf of a gamer.

import { useEffect, useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useAccount, useConnect, useDisconnect } from 'wagmi'
import { injected } from 'wagmi/connectors'
import { useConsentSubmit } from '../hooks/useConsentSubmit'
import { useConsentStatus } from '../api/bridgeApi'
import { FONTS, GAMER } from '../shared/design/tokens'

const CATEGORIES = [
  {
    key: 'TOURNAMENT_GATE',
    label: 'Tournament gate',
    description: 'Required for VAPI tournament eligibility. Without this, the system cannot verify human presence.',
    severity: 'required',
  },
  {
    key: 'ANONYMIZED_RESEARCH',
    label: 'Anonymized research',
    description: 'Population-level biometric patterns shared with researchers. No identifiers leave the bridge.',
    severity: 'optional',
  },
  {
    key: 'MANUFACTURER_CERT',
    label: 'Hardware OEM certification',
    description: 'Allows your data into the OEM cert evaluation pool. Helps controller manufacturers improve.',
    severity: 'optional',
  },
  {
    key: 'MARKETPLACE',
    label: 'Data marketplace',
    description: 'Anonymized session data may be sold to research partners. You retain ownership and can revoke at any time.',
    severity: 'optional',
  },
]

// Mock device id for status query — in production the device_id is the
// gamer's wallet (lower-cased, no 0x prefix). Bridge consent_ledger uses
// device_id as the row key.
function deviceIdFromAddress(address) {
  if (!address) return ''
  return address.toLowerCase().replace(/^0x/, '')
}

function Glass({ children, style, accent = GAMER.cyan }) {
  return (
    <div style={{
      background: `linear-gradient(180deg, rgba(8,18,24,0.55) 0%, rgba(5,10,15,0.72) 100%)`,
      backdropFilter: 'blur(14px) saturate(140%)',
      WebkitBackdropFilter: 'blur(14px) saturate(140%)',
      border: `1px solid ${accent}26`,
      borderRadius: 8,
      boxShadow: `0 0 24px ${accent}1a, inset 0 1px 0 rgba(255,255,255,0.04)`,
      ...style,
    }}>
      {children}
    </div>
  )
}

function ToggleRow({ category, granted, pending, onToggle }) {
  const tone = granted ? GAMER.green : GAMER.t2
  return (
    <div style={{
      padding: '12px 0',
      borderBottom: `1px solid ${GAMER.bd2}`,
      opacity: pending ? 0.5 : 1,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
        <span style={{ fontFamily: FONTS.mono, fontSize: 10, color: GAMER.t1, fontWeight: 600 }}>
          {category.label}
        </span>
        <button
          onClick={() => onToggle(category.key, !granted)}
          disabled={pending}
          style={{
            padding: '4px 10px',
            background: granted ? GAMER.green + '33' : 'transparent',
            border: `1px solid ${tone}`,
            borderRadius: 4,
            color: tone,
            fontFamily: FONTS.mono,
            fontSize: 8,
            letterSpacing: '0.12em',
            cursor: pending ? 'wait' : 'pointer',
            minWidth: 60,
          }}
        >
          {granted ? 'GRANTED' : 'GRANT'}
        </button>
      </div>
      <div style={{ marginTop: 4, fontFamily: FONTS.mono, fontSize: 8, color: GAMER.t3, lineHeight: 1.5 }}>
        {category.description}
      </div>
      {category.severity === 'required' && !granted && (
        <div style={{ marginTop: 4, fontFamily: FONTS.mono, fontSize: 7, color: GAMER.orange, letterSpacing: '0.1em' }}>
          REQUIRED for tournament play
        </div>
      )}
    </div>
  )
}

export function ConsentPanel({ manualOpen, onCloseManual }) {
  const open = manualOpen
  const { address, isConnected } = useAccount()
  const { connect } = useConnect()
  const { disconnect } = useDisconnect()
  const { ready, pending, error, grant, revoke, contractAddress } = useConsentSubmit()

  const deviceId = useMemo(() => deviceIdFromAddress(address), [address])
  const { data: consentStatus, refetch } = useConsentStatus(deviceId)

  const [pendingCategory, setPendingCategory] = useState(null)
  const [lastError, setLastError] = useState(null)

  useEffect(() => {
    if (error) setLastError(String(error.message || error))
  }, [error])

  async function handleToggle(categoryKey, shouldGrant) {
    if (!ready) {
      setLastError(
        !isConnected
          ? 'Connect your wallet first'
          : 'CONSENT_REGISTRY_ADDRESS not configured in frontend/.env.local'
      )
      return
    }
    setPendingCategory(categoryKey)
    setLastError(null)
    try {
      if (shouldGrant) {
        // Phase 237-EXTEND minimum-viable: expiresAt=0 (no expiry); consentHash
        // is the keccak-style placeholder. Production would derive consent_hash
        // from compute_consent_hash() (Phase 237 frozen formula).
        const expiresAt = 0
        const consentHash =
          '0x' + Array.from({ length: 32 }, () =>
            Math.floor(Math.random() * 256).toString(16).padStart(2, '0')
          ).join('')
        await grant(categoryKey, expiresAt, consentHash)
      } else {
        await revoke(categoryKey)
      }
      // Optimistic refetch — bridge consent_ledger doesn't auto-update from
      // chain events yet; on-chain state will reflect after tx confirms but
      // the local row needs explicit operator-record-category-consent (or
      // future Phase 238 chain event listener) for bridge to mirror it.
      // For now we refetch the bridge state to show whatever it has.
      setTimeout(() => refetch(), 4000)
    } catch (e) {
      setLastError(String(e?.shortMessage || e?.message || e))
    } finally {
      setPendingCategory(null)
    }
  }

  return (
    <>
      {/* Right-edge collapsed handle, lower-half (offset from PCCDrawer's middle) */}
      <div
        onClick={() => onCloseManual(!manualOpen)}
        style={{
          position: 'absolute',
          top: 'calc(50% + 110px)',
          right: open ? 320 : 0,
          transform: 'translateY(-50%)',
          width: 28,
          height: 96,
          background: GAMER.cyan + '26',
          border: `1px solid ${GAMER.cyan}66`,
          borderRight: 'none',
          borderRadius: '6px 0 0 6px',
          cursor: 'pointer',
          zIndex: 11,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transition: 'right 0.32s ease',
        }}
        title="Per-category consent"
      >
        <span style={{
          fontFamily: FONTS.mono,
          fontSize: 8,
          color: GAMER.cyan,
          letterSpacing: '0.16em',
          writingMode: 'vertical-rl',
          transform: 'rotate(180deg)',
        }}>
          {open ? 'CONSENT' : 'CONSENT ▶'}
        </span>
      </div>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ x: 320 }} animate={{ x: 0 }} exit={{ x: 320 }}
            transition={{ duration: 0.32, ease: 'easeInOut' }}
            style={{ position: 'absolute', top: 0, right: 0, bottom: 0, width: 320, zIndex: 10 }}
          >
            <Glass style={{
              height: '100%',
              borderRadius: 0,
              borderLeft: `1px solid ${GAMER.cyan}33`,
              padding: '16px 16px',
              overflow: 'auto',
            }}>
              {/* Drawer header */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                <span style={{
                  fontFamily: FONTS.mono,
                  fontSize: 9,
                  letterSpacing: '0.16em',
                  color: GAMER.cyan,
                  fontWeight: 600,
                }}>
                  PER-CATEGORY CONSENT
                </span>
                <button
                  onClick={() => onCloseManual(false)}
                  style={{ background: 'transparent', border: 'none', color: GAMER.t2, cursor: 'pointer', fontFamily: FONTS.mono, fontSize: 14 }}
                >×</button>
              </div>

              {/* Wallet-connect / address */}
              <div style={{
                padding: '10px 12px',
                marginBottom: 14,
                background: isConnected ? GAMER.green + '14' : GAMER.orange + '14',
                border: `1px solid ${isConnected ? GAMER.green : GAMER.orange}44`,
                borderRadius: 4,
              }}>
                <div style={{ fontFamily: FONTS.mono, fontSize: 7, color: GAMER.t3, letterSpacing: '0.16em', marginBottom: 4 }}>
                  WALLET
                </div>
                {isConnected ? (
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6 }}>
                    <span style={{ fontFamily: FONTS.mono, fontSize: 9, color: GAMER.t1 }}>
                      {address?.slice(0, 6)}…{address?.slice(-4)}
                    </span>
                    <button
                      onClick={() => disconnect()}
                      style={{ background: 'transparent', border: `1px solid ${GAMER.t3}`, color: GAMER.t2, fontFamily: FONTS.mono, fontSize: 8, padding: '2px 6px', cursor: 'pointer' }}
                    >
                      DISCONNECT
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => connect({ connector: injected() })}
                    style={{
                      width: '100%',
                      padding: '6px 10px',
                      background: GAMER.cyan + '33',
                      border: `1px solid ${GAMER.cyan}`,
                      color: GAMER.cyan,
                      fontFamily: FONTS.mono,
                      fontSize: 9,
                      letterSpacing: '0.12em',
                      cursor: 'pointer',
                    }}
                  >
                    CONNECT WALLET
                  </button>
                )}
              </div>

              {/* Contract address — operator transparency */}
              {contractAddress && (
                <div style={{ marginBottom: 14, fontFamily: FONTS.mono, fontSize: 7, color: GAMER.t3 }}>
                  Registry: {contractAddress.slice(0, 10)}…{contractAddress.slice(-6)}
                </div>
              )}

              {/* Toggles */}
              {CATEGORIES.map((cat) => {
                const status = consentStatus?.categories?.[cat.key]
                const granted = Boolean(status?.granted)
                return (
                  <ToggleRow
                    key={cat.key}
                    category={cat}
                    granted={granted}
                    pending={pending && pendingCategory === cat.key}
                    onToggle={handleToggle}
                  />
                )
              })}

              {/* Error surface */}
              {lastError && (
                <div style={{
                  marginTop: 14,
                  padding: '8px 10px',
                  background: GAMER.red + '14',
                  border: `1px solid ${GAMER.red}44`,
                  borderRadius: 4,
                  fontFamily: FONTS.mono,
                  fontSize: 8,
                  color: GAMER.red,
                  lineHeight: 1.5,
                }}>
                  {lastError}
                </div>
              )}

              {/* Footer notes */}
              <div style={{
                marginTop: 18,
                paddingTop: 12,
                borderTop: `1px solid ${GAMER.bd}`,
                fontFamily: FONTS.mono,
                fontSize: 7,
                color: GAMER.t3,
                lineHeight: 1.6,
              }}>
                Phase 237-CONSENT — your wallet signs every grant and revoke.
                The bridge can read your on-chain consent but cannot modify it.
                You retain ownership of your data and can revoke at any time.
              </div>
            </Glass>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
