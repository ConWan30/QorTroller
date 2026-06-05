// Consent Cockpit dApp — standalone surface at /consent.
//
// SUPERSEDES the right-edge ConsentPanel drawer (frontend/src/components/
// ConsentPanel.jsx) that was previously mounted inside GamerView. The
// drawer surface was structurally wrong for QorTroller's most important
// invariant — `BRIDGE NEVER GRANTS OR REVOKES CONSENT` — because it hid
// gamer-sovereign authority under a slide-out inside a gameplay tab.
//
// The Cockpit makes that invariant the headline of its own page, with
// a bookmark-able URL the gamer (or a regulator) can share. It reuses:
//   • useConsentSubmit (wagmi grant/revoke against VAPIConsentRegistry)
//   • ConsentMatrix (4-category 4-bit display/edit component)
//   • useConsentStatus (bridge read-side; current bitmask)
//   • useConsentHistory (new bridge endpoint; GRANT/REVOKE timeline)
//
// Pre-deploy posture: VAPIConsentRegistry is on operator deploy-hold per
// CLAUDE.md (`CHAIN_SUBMISSION_PAUSED=true`). When VITE_CONSENT_REGISTRY_
// ADDRESS is unset, the Cockpit shows a DEPLOY-HOLD banner and disables
// grant/revoke with an inline explanation. The receipt timeline still
// renders from the local consent_ledger so the surface remains useful.
// On-chain writes auto-light when the env var is set post-deploy — no
// code change at deploy time.

import { useEffect, useMemo, useState } from 'react'
import { useAccount, useConnect, useDisconnect } from 'wagmi'
import { injected } from 'wagmi/connectors'
import { useConsentSubmit } from '../../hooks/useConsentSubmit'
import { useConsentStatus } from '../../api/bridgeApi'
import { ConsentMatrix, CONSENT_CATEGORIES } from '../../components/ConsentMatrix'
import { FONTS, GAMER } from '../../shared/design/tokens'
import { CockpitChrome } from './CockpitChrome'
import { ReceiptTimeline } from './ReceiptTimeline'

const IOTEX_ADDR_PREFIX = 'https://testnet.iotexscan.io/address/'

function deviceIdFromAddress(address) {
  if (!address) return ''
  return address.toLowerCase().replace(/^0x/, '')
}

function categoryBitmaskFromStatus(consentStatus) {
  // useConsentStatus shape: { categories: { TOURNAMENT_GATE: {granted}, ... } }
  // Map to the 4-bit bitmask ConsentMatrix expects.
  if (!consentStatus?.categories) return 0
  let mask = 0
  for (const cat of CONSENT_CATEGORIES) {
    if (consentStatus.categories[cat.key]?.granted) {
      mask |= (1 << cat.bit)
    }
  }
  return mask
}

function Section({ children, style }) {
  return (
    <section
      style={{
        background:    'rgba(8,18,24,0.55)',
        border:        `1px solid ${GAMER.bd}`,
        borderRadius:  6,
        padding:       '18px 20px',
        ...style,
      }}
    >
      {children}
    </section>
  )
}

function PostureBanner({ registryAddress, registryDeployed }) {
  const live = registryDeployed
  return (
    <div
      style={{
        padding:       '14px 20px',
        background:    live ? GAMER.green + '14' : GAMER.orange + '14',
        border:        `1px solid ${(live ? GAMER.green : GAMER.orange)}55`,
        borderRadius:  6,
        marginBottom:  20,
        display:       'flex',
        flexDirection: 'column',
        gap:           4,
      }}
    >
      <div
        style={{
          fontFamily:    FONTS.mono,
          fontSize:      10,
          letterSpacing: '0.18em',
          color:         live ? GAMER.green : GAMER.orange,
          fontWeight:    700,
        }}
      >
        {live ? '✓ REGISTRY LIVE' : '⚠ REGISTRY DEPLOY-HOLD — READ-ONLY'}
      </div>
      <div
        style={{
          fontFamily: FONTS.body,
          fontSize:   16,
          color:      GAMER.t1,
          fontWeight: 600,
        }}
      >
        You are the only authority over your consent.
      </div>
      <div
        style={{
          fontFamily: FONTS.body,
          fontSize:   12,
          color:      GAMER.t2,
          lineHeight: 1.55,
        }}
      >
        The QorTroller bridge can read your on-chain consent state. It
        cannot grant or revoke on your behalf. Every action below is
        signed by your wallet — your wallet is the only authority.
      </div>
      {!live && (
        <div
          style={{
            fontFamily:    FONTS.mono,
            fontSize:      10,
            color:         GAMER.t3,
            lineHeight:    1.55,
            marginTop:     6,
          }}
        >
          On-chain registry not yet deployed for this network.
          Grant / revoke buttons are disabled until the registry address
          is configured. The receipt timeline below still shows your
          local bridge-side consent activity.
        </div>
      )}
      {live && registryAddress && (
        <div style={{ fontFamily: FONTS.mono, fontSize: 9, color: GAMER.t3, marginTop: 4 }}>
          Registry:{' '}
          <a
            href={IOTEX_ADDR_PREFIX + registryAddress}
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: GAMER.cyan, textDecoration: 'none' }}
          >
            {registryAddress.slice(0, 10)}…{registryAddress.slice(-6)} ↗
          </a>
        </div>
      )}
    </div>
  )
}

function IdentityCard({
  isConnected,
  address,
  deviceId,
  contractAddress,
  registryDeployed,
  onConnect,
  onDisconnect,
}) {
  return (
    <Section>
      <div
        style={{
          fontFamily:    FONTS.mono,
          fontSize:      10,
          letterSpacing: '0.18em',
          color:         GAMER.cyan,
          fontWeight:    600,
          marginBottom:  12,
        }}
      >
        IDENTITY
      </div>

      {isConnected ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div>
            <div style={{ fontFamily: FONTS.mono, fontSize: 8, color: GAMER.t3, letterSpacing: '0.16em', marginBottom: 4 }}>
              WALLET
            </div>
            <div style={{ fontFamily: FONTS.mono, fontSize: 12, color: GAMER.t1, wordBreak: 'break-all' }}>
              {address}
            </div>
          </div>
          <div>
            <div style={{ fontFamily: FONTS.mono, fontSize: 8, color: GAMER.t3, letterSpacing: '0.16em', marginBottom: 4 }}>
              DEVICE ID (derived)
            </div>
            <div style={{ fontFamily: FONTS.mono, fontSize: 11, color: GAMER.t2, wordBreak: 'break-all' }}>
              {deviceId}
            </div>
          </div>
          {registryDeployed && contractAddress && (
            <div>
              <div style={{ fontFamily: FONTS.mono, fontSize: 8, color: GAMER.t3, letterSpacing: '0.16em', marginBottom: 4 }}>
                CONSENT REGISTRY
              </div>
              <div style={{ fontFamily: FONTS.mono, fontSize: 11 }}>
                <a
                  href={IOTEX_ADDR_PREFIX + contractAddress}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: GAMER.cyan, textDecoration: 'none' }}
                >
                  {contractAddress} ↗
                </a>
              </div>
            </div>
          )}
          <button
            onClick={onDisconnect}
            style={{
              alignSelf:      'flex-start',
              marginTop:      4,
              padding:        '6px 14px',
              background:     'transparent',
              border:         `1px solid ${GAMER.t3}`,
              color:          GAMER.t2,
              fontFamily:     FONTS.mono,
              fontSize:       9,
              letterSpacing:  '0.14em',
              cursor:         'pointer',
              borderRadius:   3,
            }}
          >
            DISCONNECT
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 12 }}>
          <div style={{ fontFamily: FONTS.body, fontSize: 13, color: GAMER.t2, lineHeight: 1.55 }}>
            Connect your wallet to view and exercise your consent. Your
            wallet is the only authority — the bridge cannot act on your
            behalf.
          </div>
          <button
            onClick={onConnect}
            style={{
              padding:        '10px 22px',
              background:     GAMER.cyan + '33',
              border:         `1px solid ${GAMER.cyan}`,
              color:          GAMER.cyan,
              fontFamily:     FONTS.mono,
              fontSize:       12,
              letterSpacing:  '0.16em',
              cursor:         'pointer',
              borderRadius:   3,
              fontWeight:     600,
            }}
          >
            CONNECT WALLET →
          </button>
        </div>
      )}
    </Section>
  )
}

function AuthorityMatrix({
  bitmask,
  isConnected,
  ready,
  pending,
  pendingCategoryKey,
  lastTxStatus,
  onToggleCategory,
}) {
  // ConsentMatrix.onChange yields the FULL new bitmask. We diff against
  // the current bitmask to discover which bit flipped and dispatch a
  // single grant/revoke for that category.
  const handleMatrixChange = (newBitmask) => {
    const changed = newBitmask ^ bitmask
    if (changed === 0) return
    // exactly one bit flipped in normal interaction
    let bit = 0
    let scratch = changed
    while ((scratch & 1) === 0 && bit < 32) {
      scratch >>>= 1
      bit += 1
    }
    const category = CONSENT_CATEGORIES.find((c) => c.bit === bit)
    if (!category) return
    const shouldGrant = (newBitmask & (1 << bit)) !== 0
    onToggleCategory(category.key, shouldGrant)
  }

  return (
    <Section>
      <div
        style={{
          fontFamily:    FONTS.mono,
          fontSize:      10,
          letterSpacing: '0.18em',
          color:         GAMER.cyan,
          fontWeight:    600,
          marginBottom:  14,
          display:       'flex',
          justifyContent: 'space-between',
          alignItems:    'center',
        }}
      >
        <span>AUTHORITY MATRIX</span>
        {pending && pendingCategoryKey && (
          <span
            style={{
              fontFamily:    FONTS.mono,
              fontSize:      9,
              color:         GAMER.orange,
              letterSpacing: '0.14em',
            }}
          >
            {pendingCategoryKey} · {lastTxStatus || 'SIGNING'}…
          </span>
        )}
      </div>

      <div
        style={{
          opacity: isConnected ? 1 : 0.55,
          pointerEvents: (isConnected && ready && !pending) ? 'auto' : 'none',
        }}
      >
        <ConsentMatrix
          bitmask={bitmask}
          mode={isConnected && ready ? 'edit' : 'display'}
          onChange={handleMatrixChange}
        />
      </div>

      {isConnected && !ready && (
        <div
          style={{
            marginTop:   12,
            padding:     '8px 12px',
            background:  GAMER.orange + '14',
            border:      `1px solid ${GAMER.orange}44`,
            borderRadius: 3,
            fontFamily:  FONTS.mono,
            fontSize:    9,
            color:       GAMER.orange,
            lineHeight:  1.55,
          }}
        >
          On-chain writes disabled: consent registry address not
          configured. The matrix shows your last-known consent state
          from the bridge; toggle controls re-enable once VAPIConsentRegistry
          is deployed and VITE_CONSENT_REGISTRY_ADDRESS is set.
        </div>
      )}
    </Section>
  )
}

function DisclosureFooter() {
  return (
    <Section style={{ background: 'rgba(8,18,24,0.4)', borderColor: GAMER.bd2 }}>
      <div
        style={{
          fontFamily:    FONTS.mono,
          fontSize:      10,
          letterSpacing: '0.18em',
          color:         GAMER.t2,
          fontWeight:    600,
          marginBottom:  10,
        }}
      >
        BRIDGE NEVER GRANTS OR REVOKES CONSENT
      </div>
      <div style={{ fontFamily: FONTS.body, fontSize: 12, color: GAMER.t2, lineHeight: 1.65 }}>
        Phase 237-CONSENT — your wallet signs every grant and revoke. The
        bridge can read your on-chain consent state but cannot modify it.
        You retain ownership of your data and can revoke at any time. The
        on-chain VAPIConsentRegistry is the gamer-authoritative source of
        truth; the local bridge consent_ledger mirrors it for operational
        reads only.
      </div>
      <div style={{ marginTop: 10, fontFamily: FONTS.mono, fontSize: 9, color: GAMER.t3, lineHeight: 1.55 }}>
        This invariant is pinned at the protocol layer (see CLAUDE.md hard
        rules: <em>BRIDGE NEVER GRANTS OR REVOKES CONSENT ON BEHALF OF GAMER</em>).
        The Consent Cockpit dApp is a presentation surface; it is
        cryptographically prevented from impersonating you. Your wallet
        is the only authority.
      </div>
    </Section>
  )
}

export default function ConsentCockpitDapp() {
  const { address, isConnected } = useAccount()
  const { connect } = useConnect()
  const { disconnect } = useDisconnect()
  const { ready, pending, error, grant, revoke, contractAddress } = useConsentSubmit()

  const deviceId = useMemo(() => deviceIdFromAddress(address), [address])
  const { data: consentStatus, refetch } = useConsentStatus(deviceId)
  const bitmask = useMemo(() => categoryBitmaskFromStatus(consentStatus), [consentStatus])

  const [pendingCategoryKey, setPendingCategoryKey] = useState(null)
  const [lastTxStatus, setLastTxStatus]             = useState(null)
  const [lastError, setLastError]                   = useState(null)

  useEffect(() => {
    if (error) setLastError(String(error.message || error))
  }, [error])

  const registryDeployed = Boolean(contractAddress)

  const handleToggle = async (categoryKey, shouldGrant) => {
    if (!isConnected) {
      setLastError('Connect your wallet first.')
      return
    }
    if (!ready) {
      setLastError('Consent registry address not configured — on-chain writes disabled.')
      return
    }
    setPendingCategoryKey(categoryKey)
    setLastError(null)
    try {
      setLastTxStatus('SIGNING')
      if (shouldGrant) {
        // v1: simple no-expiry consent with random hash. Phase-2 will
        // compute the canonical consent_hash from compute_consent_hash()
        // (Phase 237 FROZEN formula) and POST tx_hash back to bridge.
        const expiresAt = 0
        const consentHash =
          '0x' +
          Array.from({ length: 32 }, () =>
            Math.floor(Math.random() * 256).toString(16).padStart(2, '0'),
          ).join('')
        await grant(categoryKey, expiresAt, consentHash)
      } else {
        await revoke(categoryKey)
      }
      setLastTxStatus('BROADCAST')
      setTimeout(() => refetch(), 4000)
    } catch (e) {
      setLastError(String(e?.shortMessage || e?.message || e))
      setLastTxStatus(null)
    } finally {
      setPendingCategoryKey(null)
    }
  }

  return (
    <div
      style={{
        minHeight:   '100vh',
        background:  GAMER.bg,
        color:       GAMER.t1,
        display:     'flex',
        flexDirection: 'column',
      }}
    >
      <CockpitChrome />

      <main
        role="main"
        aria-label="Consent Cockpit"
        style={{
          flex:       1,
          width:      '100%',
          maxWidth:   880,
          margin:     '0 auto',
          padding:    '28px 24px 60px',
          display:    'flex',
          flexDirection: 'column',
          gap:        20,
        }}
      >
        <PostureBanner
          registryAddress={contractAddress}
          registryDeployed={registryDeployed}
        />

        <IdentityCard
          isConnected={isConnected}
          address={address}
          deviceId={deviceId}
          contractAddress={contractAddress}
          registryDeployed={registryDeployed}
          onConnect={() => connect({ connector: injected() })}
          onDisconnect={() => disconnect()}
        />

        <AuthorityMatrix
          bitmask={bitmask}
          isConnected={isConnected}
          ready={ready}
          pending={pending}
          pendingCategoryKey={pendingCategoryKey}
          lastTxStatus={lastTxStatus}
          onToggleCategory={handleToggle}
        />

        {lastError && (
          <div
            style={{
              padding:      '10px 14px',
              background:   GAMER.red + '14',
              border:       `1px solid ${GAMER.red}55`,
              borderRadius: 4,
              fontFamily:   FONTS.mono,
              fontSize:     10,
              color:        GAMER.red,
              lineHeight:   1.5,
            }}
          >
            {lastError}
          </div>
        )}

        <ReceiptTimeline
          deviceId={deviceId}
          walletConnected={isConnected}
        />

        <DisclosureFooter />
      </main>
    </div>
  )
}
