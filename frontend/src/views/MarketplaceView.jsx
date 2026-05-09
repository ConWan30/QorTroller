/**
 * Phase 238 Frontend — MarketplaceView (top-level tab).
 *
 * 4 audiences served simultaneously:
 *   - Sellers     : "0 anchored listings yet" CTA + per-seller history
 *   - Buyers      : tier badge legend + listing grid (display-only)
 *   - Auditors    : Curator status pill + flagged listings hot-bar
 *   - Operators   : listing creation form + manual review trigger (hidden in O1)
 *
 * Real-time twin pulse — TwinControllerStream consumes SSE feed; every
 * curator_verdict / listing-anchor / consent-revocation animates here.
 */
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  useMarketplaceStatus,
  useCuratorStatus,
  useCuratorFlaggedListings,
} from '../api/bridgeApi'
import { TierBadge, TierLegend } from '../components/TierBadge'
import { TwinControllerStream } from '../components/TwinControllerStream'
import { ConsentMatrix, CONSENT_CATEGORIES } from '../components/ConsentMatrix'

const PRIMITIVE_BADGES = [
  { key: 'GIC',                 label: 'GIC',          tooltip: 'Grind Integrity Chain — per-session cognitive continuity' },
  { key: 'WEC',                 label: 'WEC',          tooltip: 'Watchdog Event Chain — operational continuity' },
  { key: 'VAME',                label: 'VAME',         tooltip: 'Application-Layer Message Envelope' },
  { key: 'CORPUS-SNAPSHOT',     label: 'CORPUS',       tooltip: 'Corpus snapshot anchor (governance posture)' },
  { key: 'CONSENT',             label: 'CONSENT',      tooltip: 'Per-category consent registry' },
  { key: 'BIOMETRIC-SNAPSHOT',  label: 'BIO-SNAP',     tooltip: 'Biometric snapshot — geometric inputs' },
  { key: 'SEPPROOF',            label: 'SEPPROOF',     tooltip: 'ZK separation proof — corpus ratio>1.0' },
  { key: 'LISTING-v1',          label: 'LISTING',      tooltip: 'PALL listing commitment — composes the prior 7' },
]

export function MarketplaceView() {
  const market   = useMarketplaceStatus()
  const curator  = useCuratorStatus()
  const flagged  = useCuratorFlaggedListings({ sinceMinutes: 1440, limit: 20 })
  const [demoConsentBitmask, setDemoConsentBitmask] = useState(0b1011)  // demo state

  return (
    <div style={{
      flex:       1,
      display:    'flex',
      flexDirection: 'column',
      background: 'var(--vapi-void)',
      color:      'var(--vapi-tier-verified)',
      fontFamily: "'JetBrains Mono', monospace",
      overflow:   'auto',
      padding:    16,
      gap:        16,
    }}>
      {/* Header */}
      <header style={{
        display:        'flex',
        justifyContent: 'space-between',
        alignItems:     'flex-start',
        gap:            16,
      }}>
        <div>
          <h1 style={{
            margin:     0,
            fontFamily: "'Rajdhani', sans-serif",
            fontSize:   24,
            fontWeight: 700,
            letterSpacing: '0.08em',
            color:      'var(--vapi-orange)',
          }}>
            MARKETPLACE
          </h1>
          <div style={{
            fontSize:   10,
            color:      'var(--vapi-tier-basic)',
            marginTop:  4,
            letterSpacing: '0.05em',
          }}>
            Phase 238 — Provenance-Anchored Listing Layer (PALL)
          </div>
        </div>

        {/* Tier badge legend */}
        <div style={{ textAlign: 'right' }}>
          <div style={{
            fontSize:    9,
            color:       'var(--vapi-tier-basic)',
            marginBottom: 4,
            letterSpacing: '0.06em',
          }}>
            CRYPTOGRAPHIC TIER MULTIPLIER (computed from on-chain isRecorded)
          </div>
          <TierLegend />
        </div>
      </header>

      {/* Top-row stats */}
      <div style={{
        display:               'grid',
        gridTemplateColumns:   'repeat(auto-fit, minmax(180px, 1fr))',
        gap:                   12,
      }}>
        <Stat
          label="TOTAL LISTINGS"
          value={market.data?.total_listings ?? '—'}
          accent="var(--vapi-orange)"
        />
        <Stat
          label="ANCHORED"
          value={market.data?.anchored_listings ?? '—'}
          accent="var(--vapi-cyan)"
        />
        <Stat
          label="CURATOR REVIEWS"
          value={curator.data?.total_reviews ?? '—'}
          accent="var(--vapi-cyan)"
        />
        <Stat
          label="FLAGGED"
          value={curator.data?.flagged_reviews ?? '—'}
          accent={(curator.data?.flagged_reviews ?? 0) > 0
            ? 'var(--vapi-warn)'
            : 'var(--vapi-tier-basic)'}
        />
      </div>

      {/* 7-primitive composition strip — VAPI exclusivity showcase */}
      <section>
        <SectionHeader>SEVEN-PRIMITIVE COMPOSITION (each LISTING-v1 binds these anchors)</SectionHeader>
        <div style={{
          display:  'flex',
          gap:      6,
          flexWrap: 'wrap',
          padding:  '8px 0',
        }}>
          {PRIMITIVE_BADGES.map((p) => (
            <span
              key={p.key}
              title={p.tooltip}
              style={{
                padding:        '3px 9px',
                background:     'rgba(34, 211, 238, 0.05)',
                border:         '1px solid rgba(34, 211, 238, 0.3)',
                borderRadius:   2,
                color:          'var(--vapi-cyan)',
                fontSize:       9,
                letterSpacing:  '0.08em',
                cursor:         'help',
              }}
            >
              {p.label}
            </span>
          ))}
        </div>
      </section>

      {/* Twin controller real-time stream */}
      <section>
        <SectionHeader>
          TWIN CONTROLLER · LIVE PROVENANCE THEATER
          <span style={{
            marginLeft:  10,
            fontSize:    8,
            color:       'var(--vapi-tier-basic)',
            fontWeight:  400,
          }}>
            every pulse maps to a verifiable backend signal
          </span>
        </SectionHeader>
        <TwinControllerStream
          consentBitmask={demoConsentBitmask}
          height={280}
        />
      </section>

      {/* Body — split into 2 columns */}
      <section style={{
        display:               'grid',
        gridTemplateColumns:   'repeat(auto-fit, minmax(320px, 1fr))',
        gap:                   16,
      }}>
        {/* Left: Listings or empty state */}
        <Panel title="LISTINGS">
          {(market.data?.total_listings ?? 0) === 0 ? (
            <EmptyState
              title="0 anchored listings yet"
              cta="Be the first to anchor cryptographic provenance"
            />
          ) : (
            <ListingGrid latest={market.data} />
          )}
        </Panel>

        {/* Right: Flagged hot-bar */}
        <Panel title={`FLAGGED LISTINGS · LAST 24H (${flagged.data?.total ?? 0})`}>
          {(flagged.data?.listings?.length ?? 0) === 0 ? (
            <EmptyState
              title="No flags"
              cta="Curator review pipeline is quiet"
              accent="var(--vapi-cyan)"
            />
          ) : (
            <FlaggedList rows={flagged.data?.listings ?? []} />
          )}
        </Panel>
      </section>

      {/* Consent matrix demo */}
      <section>
        <SectionHeader>CONSENT MATRIX · phase 237 per-category registry</SectionHeader>
        <div style={{
          padding:    12,
          background: 'rgba(255,255,255,0.02)',
          border:     '1px solid rgba(34,211,238,0.15)',
          borderRadius: 3,
        }}>
          <ConsentMatrix
            bitmask={demoConsentBitmask}
            mode="edit"
            onChange={setDemoConsentBitmask}
            highlightCleared={['MARKETPLACE']}
          />
        </div>
      </section>

      <footer style={{
        padding:       '12px 0',
        borderTop:     '1px solid rgba(255,255,255,0.04)',
        fontSize:      9,
        color:         'var(--vapi-tier-basic)',
        letterSpacing: '0.05em',
        textAlign:     'center',
      }}>
        <span>WALLET-FREE INFRASTRUCTURE READY</span>
        <span style={{ margin: '0 8px' }}>·</span>
        <span>STEP I-FINAL — REQUIRES ~0.16 IOTX ON-CHAIN ACTIVATION</span>
        <span style={{ margin: '0 8px' }}>·</span>
        <span>scripts/curator_preflight_runbook.py</span>
      </footer>
    </div>
  )
}

function Stat({ label, value, accent }) {
  return (
    <div style={{
      padding:      12,
      background:   'rgba(255,255,255,0.02)',
      border:       `1px solid ${accent}`,
      borderColor:  accent,
      borderRadius: 3,
    }}>
      <div style={{
        fontSize:      9,
        color:         'var(--vapi-tier-basic)',
        letterSpacing: '0.08em',
        marginBottom:  6,
      }}>{label}</div>
      <div style={{
        fontSize:    24,
        fontWeight:  600,
        color:       accent,
        fontFamily:  "'Rajdhani', sans-serif",
      }}>{value}</div>
    </div>
  )
}

function SectionHeader({ children }) {
  return (
    <div style={{
      fontSize:      10,
      color:         'var(--vapi-orange)',
      letterSpacing: '0.12em',
      fontWeight:    600,
      paddingBottom: 6,
      borderBottom:  '1px solid rgba(255, 107, 0, 0.2)',
      marginBottom:  8,
    }}>
      {children}
    </div>
  )
}

function Panel({ title, children }) {
  return (
    <div style={{
      padding:    14,
      background: 'rgba(255,255,255,0.02)',
      border:     '1px solid rgba(34, 211, 238, 0.15)',
      borderRadius: 3,
      minHeight:  220,
    }}>
      <SectionHeader>{title}</SectionHeader>
      {children}
    </div>
  )
}

function EmptyState({ title, cta, accent = 'var(--vapi-orange)' }) {
  return (
    <div style={{
      padding:    32,
      textAlign:  'center',
      color:      'var(--vapi-tier-basic)',
    }}>
      <div style={{
        fontSize:    18,
        color:       accent,
        marginBottom: 8,
        fontFamily:  "'Rajdhani', sans-serif",
      }}>{title}</div>
      <div style={{ fontSize: 10, opacity: 0.7 }}>{cta}</div>
    </div>
  )
}

function ListingGrid({ latest }) {
  if (!latest) return null
  return (
    <div>
      <div style={{ fontSize: 10, color: 'var(--vapi-tier-basic)', marginBottom: 8 }}>LATEST</div>
      <div style={{
        padding:    10,
        background: 'rgba(255,255,255,0.03)',
        borderLeft: `3px solid var(--vapi-cyan)`,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
          <span style={{ fontSize: 10 }}>
            commitment: {String(latest.latest_commitment ?? '').slice(0, 24)}...
          </span>
          <TierBadge
            tier={Math.min(3, latest.latest_anchors_present ?? 0)}
            showMultiplier
          />
        </div>
        <div style={{ fontSize: 9, color: 'var(--vapi-tier-basic)', marginTop: 6 }}>
          seller: {String(latest.latest_seller ?? '').slice(0, 16)}...  ·
          price: {latest.latest_price_iotx ?? 0} IOTX  ·
          on-chain: {latest.latest_on_chain ? '✓' : '—'}
        </div>
      </div>
    </div>
  )
}

function FlaggedList({ rows }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 10 }}>
      {rows.slice(0, 8).map((r, i) => (
        <div
          key={`${r.listing_commitment}-${i}`}
          style={{
            padding:    '6px 10px',
            background: 'rgba(255,255,255,0.02)',
            borderLeft: `3px solid ${
              r.severity === 'CRITICAL' || r.severity === 'HIGH' ? 'var(--vapi-block)' : 'var(--vapi-warn)'
            }`,
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--vapi-warn)', fontWeight: 600 }}>{r.verdict}</span>
            <span style={{ fontSize: 8, color: 'var(--vapi-tier-basic)' }}>
              {String(r.listing_commitment ?? '').slice(0, 12)}...
            </span>
          </div>
          {r.reason_detail && (
            <div style={{
              fontSize:     9,
              color:        'var(--vapi-tier-basic)',
              marginTop:    3,
              whiteSpace:   'nowrap',
              overflow:     'hidden',
              textOverflow: 'ellipsis',
            }}>{r.reason_detail}</div>
          )}
        </div>
      ))}
    </div>
  )
}
