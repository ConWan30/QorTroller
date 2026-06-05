// Consent Cockpit dApp — receipt timeline.
//
// Renders the gamer's GRANT/REVOKE history (most recent first) for the
// connected wallet's device_id. Reads from /agent/consent-history via
// useConsentHistory (bridgeApi). Each row is a discrete cryptographic
// receipt; tx_hash is rendered with an IoTeX explorer link when present,
// otherwise marked as 'local-ledger only' until the Phase-2 write-back
// endpoint persists wagmi-confirmed receipts.
//
// Honesty rails:
//   • noMock on the underlying hook — receipt history must never be faked
//   • disconnected wallet → 'connect wallet to view receipt history'
//   • empty history → 'no consent activity yet'
//   • bridge offline → react-query holds last value; component shows
//     'offline — last seen Nm ago' rather than fabricating

import { useConsentHistory } from '../../api/bridgeApi'
import { FONTS, GAMER } from '../../shared/design/tokens'

const IOTEX_TX_PREFIX = 'https://testnet.iotexscan.io/tx/'

function formatTs(tsSeconds) {
  if (!tsSeconds) return '—'
  const d = new Date(tsSeconds * 1000)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toISOString().replace('T', ' ').slice(0, 19) + ' UTC'
}

function ActionPill({ action }) {
  const isGrant = action === 'GRANT'
  const color   = isGrant ? GAMER.green : GAMER.orange
  return (
    <span
      style={{
        display:        'inline-block',
        padding:        '2px 8px',
        background:     color + '22',
        border:         `1px solid ${color}66`,
        borderRadius:   3,
        color,
        fontFamily:     FONTS.mono,
        fontSize:       9,
        fontWeight:     600,
        letterSpacing:  '0.14em',
        textTransform:  'uppercase',
        minWidth:       60,
        textAlign:      'center',
      }}
    >
      {action}
    </span>
  )
}

function TimelineRow({ entry }) {
  const hasTx = Boolean(entry.tx_hash)
  return (
    <div
      role="listitem"
      style={{
        display:       'grid',
        gridTemplateColumns: 'auto 1fr auto',
        alignItems:    'center',
        gap:           14,
        padding:       '12px 16px',
        borderBottom:  `1px solid ${GAMER.bd2}`,
        fontFamily:    FONTS.mono,
        fontSize:      11,
      }}
    >
      <ActionPill action={entry.action} />

      <div style={{ minWidth: 0 }}>
        <div style={{ color: GAMER.t1, fontWeight: 600, fontSize: 11 }}>
          {entry.category}
        </div>
        <div style={{ color: GAMER.t3, fontSize: 9, marginTop: 2 }}>
          {formatTs(entry.ts)}
        </div>
      </div>

      <div style={{ textAlign: 'right', minWidth: 120 }}>
        {hasTx ? (
          <a
            href={IOTEX_TX_PREFIX + entry.tx_hash}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              fontFamily:     FONTS.mono,
              fontSize:       9,
              color:          GAMER.cyan,
              textDecoration: 'none',
              letterSpacing:  '0.04em',
            }}
          >
            {entry.tx_hash.slice(0, 8)}…{entry.tx_hash.slice(-6)} ↗
          </a>
        ) : (
          <span
            style={{
              fontFamily:    FONTS.mono,
              fontSize:      9,
              color:         GAMER.t3,
              letterSpacing: '0.06em',
            }}
            title="No on-chain tx hash recorded for this entry. v1 shows local-ledger receipts; Phase-2 write-back will persist wagmi-confirmed tx hashes."
          >
            local-ledger
          </span>
        )}
      </div>
    </div>
  )
}

export function ReceiptTimeline({ deviceId, walletConnected }) {
  const { data, isLoading, isError } = useConsentHistory(deviceId, 50)

  // Section header is rendered regardless of state for consistent layout.
  const header = (
    <div
      style={{
        padding:       '12px 16px',
        borderBottom:  `1px solid ${GAMER.bd}`,
        display:       'flex',
        justifyContent: 'space-between',
        alignItems:    'center',
      }}
    >
      <span
        style={{
          fontFamily:    FONTS.mono,
          fontSize:      10,
          letterSpacing: '0.18em',
          color:         GAMER.cyan,
          fontWeight:    600,
        }}
      >
        RECEIPT TIMELINE
      </span>
      <span
        style={{
          fontFamily: FONTS.mono,
          fontSize:   9,
          color:      GAMER.t3,
        }}
      >
        {data?.entries?.length ? `${data.entries.length} event${data.entries.length === 1 ? '' : 's'}` : ''}
      </span>
    </div>
  )

  // Empty-state body (shared layout)
  function EmptyMessage({ children }) {
    return (
      <div
        style={{
          padding:    '24px 16px',
          textAlign:  'center',
          fontFamily: FONTS.mono,
          fontSize:   10,
          color:      GAMER.t3,
          lineHeight: 1.6,
        }}
      >
        {children}
      </div>
    )
  }

  return (
    <section
      aria-label="Consent receipt timeline"
      style={{
        border:       `1px solid ${GAMER.bd}`,
        borderRadius: 6,
        background:   'rgba(8,18,24,0.55)',
        overflow:     'hidden',
      }}
    >
      {header}

      {!walletConnected && (
        <EmptyMessage>Connect your wallet to view your consent receipt history.</EmptyMessage>
      )}

      {walletConnected && isLoading && (
        <EmptyMessage>Loading receipts…</EmptyMessage>
      )}

      {walletConnected && isError && (
        <EmptyMessage>
          Bridge offline. Receipt history will resume when the bridge
          becomes reachable.
        </EmptyMessage>
      )}

      {walletConnected && !isLoading && !isError && data?.entries?.length === 0 && (
        <EmptyMessage>
          No consent activity yet for this wallet.
          {!data?.consent_ledger_enabled && (
            <div style={{ marginTop: 8, color: GAMER.orange }}>
              consent_ledger disabled on bridge — entries cannot be recorded.
            </div>
          )}
        </EmptyMessage>
      )}

      {walletConnected && !isLoading && !isError && data?.entries?.length > 0 && (
        <div role="list">
          {data.entries.map((entry, idx) => (
            <TimelineRow key={`${entry.category}:${entry.action}:${entry.ts}:${idx}`} entry={entry} />
          ))}
        </div>
      )}
    </section>
  )
}
