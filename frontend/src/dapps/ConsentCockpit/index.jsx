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
import { useConsentStatus, useWalletDevices } from '../../api/bridgeApi'
import { ConsentMatrix, CONSENT_CATEGORIES } from '../../components/ConsentMatrix'
import { FONTS, GAMER } from '../../shared/design/tokens'
import { CockpitChrome } from './CockpitChrome'
import { ReceiptTimeline } from './ReceiptTimeline'

const IOTEX_ADDR_PREFIX = 'https://testnet.iotexscan.io/address/'

// F3 (2026-06-05) — Decision D1-C: the Cockpit MUST NOT derive device_id
// from the wallet address. That would conflate the consent AUTHORITY (the
// gamer's secp256k1 wallet, the signer of grant/revoke txs) with the
// consent SUBJECT (the controller, identified by keccak256(controller_pubkey)
// per FROZEN PoAC rule). One wallet can register multiple certified
// controllers; the prior wallet-derived shim broke for every gamer with a
// controller registered via the legitimate VAPIPoEPRegistry path.
//
// The Cockpit now sources device_id from `useWalletDevices`, which reads
// VAPIPoEPRegistry.DeviceRegistered (primary, gamer-signed) + VHP
// fallback. When multiple bindings exist, a selector lets the gamer pick
// which controller's consent to manage.

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

function ControllerSelector({ bindings, selectedDeviceId, onSelect }) {
  if (!bindings || bindings.length <= 1) return null
  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ fontFamily: FONTS.mono, fontSize: 8, color: GAMER.t3, letterSpacing: '0.16em', marginBottom: 6 }}>
        SELECT CONTROLLER ({bindings.length} REGISTERED)
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {bindings.map((b) => {
          const selected = b.device_id === selectedDeviceId
          const sourceLabel = b.source === 'VAPIPoEPRegistry'
            ? 'gamer-signed registration'
            : b.source === 'VHPMinted'
            ? 'bridge-attested binding'
            : b.source
          return (
            <button
              key={b.device_id}
              onClick={() => onSelect(b.device_id)}
              style={{
                textAlign:    'left',
                padding:      '8px 10px',
                background:   selected ? GAMER.cyan + '22' : 'transparent',
                border:       `1px solid ${selected ? GAMER.cyan : GAMER.bd2}`,
                borderRadius: 3,
                cursor:       'pointer',
                color:        selected ? GAMER.t1 : GAMER.t2,
                fontFamily:   FONTS.mono,
                fontSize:     10,
              }}
            >
              <div style={{ wordBreak: 'break-all' }}>
                {b.device_id.slice(0, 16)}…{b.device_id.slice(-8)}
              </div>
              <div style={{ fontSize: 8, color: GAMER.t3, marginTop: 2, letterSpacing: '0.08em' }}>
                {sourceLabel}{b.valid === false ? ' · EXPIRED' : ''}
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}

function IdentityCard({
  isConnected,
  address,
  bindings,
  bindingsLoading,
  selectedDeviceId,
  onSelectDevice,
  contractAddress,
  registryDeployed,
  onConnect,
  onDisconnect,
}) {
  const selectedBinding = (bindings || []).find((b) => b.device_id === selectedDeviceId) || null
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
        IDENTITY · AUTHORITY + SUBJECT
      </div>

      {isConnected ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {/* AUTHORITY — the consent signer. Always the connected wallet. */}
          <div>
            <div style={{ fontFamily: FONTS.mono, fontSize: 8, color: GAMER.t3, letterSpacing: '0.16em', marginBottom: 4 }}>
              WALLET · AUTHORITY (signs every grant + revoke)
            </div>
            <div style={{ fontFamily: FONTS.mono, fontSize: 12, color: GAMER.t1, wordBreak: 'break-all' }}>
              {address}
            </div>
          </div>

          {/* SUBJECT — the controller. Sourced from on-chain bindings; NOT
              derived from the wallet (D1-C). When no binding exists, the
              Cockpit is honest about it rather than fabricating an id. */}
          <div>
            <div style={{ fontFamily: FONTS.mono, fontSize: 8, color: GAMER.t3, letterSpacing: '0.16em', marginBottom: 4 }}>
              DEVICE · SUBJECT (the certified controller)
            </div>
            {bindingsLoading && (
              <div style={{ fontFamily: FONTS.mono, fontSize: 10, color: GAMER.t3 }}>
                Resolving on-chain controller bindings…
              </div>
            )}
            {!bindingsLoading && !selectedBinding && (
              <div style={{
                padding:      '8px 10px',
                background:   GAMER.orange + '14',
                border:       `1px solid ${GAMER.orange}44`,
                borderRadius: 3,
                fontFamily:   FONTS.mono,
                fontSize:     9,
                color:        GAMER.orange,
                lineHeight:   1.55,
              }}>
                No on-chain controller binding found for this wallet.
                Register your DualShock Edge with VAPIPoEPRegistry to
                exercise consent here. The Cockpit will not fabricate a
                subject identifier from your wallet address.
              </div>
            )}
            {!bindingsLoading && selectedBinding && (
              <>
                <div style={{ fontFamily: FONTS.mono, fontSize: 11, color: GAMER.t2, wordBreak: 'break-all' }}>
                  {selectedBinding.device_id}
                </div>
                <div style={{ fontFamily: FONTS.mono, fontSize: 8, color: GAMER.t3, marginTop: 4, letterSpacing: '0.08em' }}>
                  {selectedBinding.source === 'VAPIPoEPRegistry'
                    ? '✓ gamer-signed registration · VAPIPoEPRegistry'
                    : selectedBinding.source === 'VHPMinted'
                    ? '✓ bridge-attested binding · VAPIVerifiedHumanProof'
                    : selectedBinding.source}
                  {selectedBinding.valid === false ? ' · EXPIRED' : ''}
                </div>
                <ControllerSelector
                  bindings={bindings}
                  selectedDeviceId={selectedDeviceId}
                  onSelect={onSelectDevice}
                />
              </>
            )}
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

  // F3: resolve the wallet's on-chain-registered controllers via
  // /agent/wallet-devices (PoEP primary + VHP fallback). Never derive
  // device_id from the wallet address.
  const { data: walletDevicesData, isLoading: bindingsLoading } = useWalletDevices(address, { includeVhp: true })
  const bindings = walletDevicesData?.bindings || []

  // Selected controller defaults to the first binding (typically the
  // most-recent gamer-signed PoEP registration). Operator can switch
  // via the ControllerSelector when multiple controllers are bound.
  const [selectedDeviceId, setSelectedDeviceId] = useState('')
  useEffect(() => {
    if (bindings.length === 0) {
      setSelectedDeviceId('')
      return
    }
    if (!selectedDeviceId || !bindings.find((b) => b.device_id === selectedDeviceId)) {
      setSelectedDeviceId(bindings[0].device_id)
    }
  }, [bindings, selectedDeviceId])

  // Consent state + history queries key on the SUBJECT (controller),
  // not the AUTHORITY (wallet). This is the D1-C fix made operational.
  const { data: consentStatus, refetch } = useConsentStatus(selectedDeviceId)
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
          bindings={bindings}
          bindingsLoading={bindingsLoading}
          selectedDeviceId={selectedDeviceId}
          onSelectDevice={setSelectedDeviceId}
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
          deviceId={selectedDeviceId}
          walletConnected={isConnected}
        />

        <DisclosureFooter />
      </main>
    </div>
  )
}
