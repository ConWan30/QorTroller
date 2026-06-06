// Public Hardware Authenticity Verify — /verify/:deviceId
//
// Build 4 of operator-directed /goal build order (2→1→4→3→5→6).
//
// No auth. No wallet. No chrome. A single truthful answer.
//
// Use cases this surface enables:
//   • A buyer of a used DualSense Edge on eBay — paste the device_id,
//     get a permanent cryptographic answer (REGISTERED ✓ / NOT)
//   • A tournament organizer at check-in — public URL to scan
//   • A partner integrator validating a fleet — bookmark-able per-device
//   • A future marketplace listing — embed `<iframe src="/verify/...">`
//
// Aesthetic direction: forensic certificate. Closer to a notarial
// document or a wine-authenticity tag than a dashboard. Single page,
// minimal chrome, device_id as the headline, registry view as the
// truthful answer beneath. No graticule (this is a CERTIFICATE, not
// an instrument).
//
// Honesty rails:
//   • noMock — the underlying endpoint is fail-open (REGISTRY_UNAVAILABLE
//     when the registry is unconfigured, RPC_ERROR on chain read failure);
//     this surface displays those states honestly rather than fabricating
//     a REGISTERED claim
//   • Invalid hex → INVALID_HEX state, never a false certificate
//   • Empty device_id (just /verify) → an honest "paste a device_id"
//     prompt; never a sample card pretending to be real

import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

// ── tokens (in-line — certificate room ≠ dashboard room) ──
const PARCHMENT = '#0b0e13'
const PARCHMENT_SOFT = '#10141b'
const CHAIN = '#5bd6a3'
const AMBER = '#f0a868'
const RED = '#d65b78'
const TEXT = '#e0e6ef'
const TEXT_DIM = '#8a96a5'
const TEXT_FAINT = '#5a6675'
const BORDER = '#1a2230'

const Syne = "'Syne', system-ui, sans-serif"
const Mono = "'JetBrains Mono', monospace"

// Fetcher: hits the public_forensic_api /device/:deviceId endpoint.
// public_forensic_api mounts at the root prefix (no /operator), so the
// URL is just /device/<hex>. The bridge bind is localhost:8080 by
// default; for dev served on 5173 we use the same-origin path.
const PUBLIC_BASE = ''

async function fetchDeviceCert(deviceIdHex) {
  if (!deviceIdHex) return null
  const url = `${PUBLIC_BASE}/device/${encodeURIComponent(deviceIdHex)}`
  const res = await fetch(url)
  if (!res.ok) {
    throw new Error(`HTTP ${res.status} from ${url}`)
  }
  return res.json()
}

function useDeviceCert(deviceIdHex) {
  return useQuery({
    queryKey: ['publicDeviceCert', deviceIdHex],
    queryFn: () => fetchDeviceCert(deviceIdHex),
    enabled: Boolean(deviceIdHex),
    staleTime: 30000,
    retry: 1,
  })
}

// ──────────────────────────────────────────────────────────────────────
// VERDICT — the truthful answer
// ──────────────────────────────────────────────────────────────────────

function VerdictBlock({ cert }) {
  const registered = Boolean(cert?.registered)
  const source = String(cert?.source || '')

  // Five honest states the endpoint can produce, each rendered without
  // overclaim:
  //   • REGISTERED + Path A   → ✓ silicon-rooted authentic (the headline)
  //   • REGISTERED + Path B   → ✓ host-held authentic (real but lesser tier)
  //   • Not registered        → ✗ not registered
  //   • REGISTRY_UNAVAILABLE  → registry not configured (no claim possible)
  //   • RPC_ERROR             → chain read failed (transient; try again)
  //   • INVALID_HEX           → device_id malformed (user input issue)
  let tone = TEXT_FAINT
  let symbol = '—'
  let verdict = 'UNKNOWN'
  let detail = ''

  if (source === 'INVALID_HEX') {
    tone = AMBER
    symbol = '!'
    verdict = 'INVALID DEVICE ID'
    detail = 'device_id must be a 64-character hex string (keccak256 of the controller public key).'
  } else if (source === 'REGISTRY_UNAVAILABLE') {
    tone = TEXT_DIM
    symbol = '○'
    verdict = 'REGISTRY UNAVAILABLE'
    detail = 'VAPIManufacturerDeviceRegistry is not configured on this bridge — no on-chain claim can be made about this device.'
  } else if (source === 'RPC_ERROR') {
    tone = AMBER
    symbol = '~'
    verdict = 'CHAIN READ FAILED'
    detail = 'The on-chain read failed transiently. Refresh to retry.'
  } else if (registered) {
    tone = CHAIN
    symbol = '✓'
    verdict = 'REGISTERED'
    if (cert.signing_path_code === 1) {
      detail = 'Silicon-rooted manufacturer-attested authentic controller.'
    } else if (cert.signing_path_code === 2) {
      detail = 'Host-held credential authentic controller.'
    } else {
      detail = 'On-chain registered.'
    }
  } else {
    tone = RED
    symbol = '✗'
    verdict = 'NOT REGISTERED'
    detail = 'No on-chain manufacturer registration exists for this device_id.'
  }

  return (
    <div style={{
      padding: '36px 32px',
      background: PARCHMENT_SOFT,
      border: `1px solid ${tone}55`,
      borderRadius: 8,
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* corner accent — wax-seal-vibe */}
      <span aria-hidden="true" style={{
        position: 'absolute',
        top: -40, right: -40,
        width: 120, height: 120,
        background: `radial-gradient(circle, ${tone}1a, transparent 70%)`,
      }} />

      <div style={{
        display: 'flex',
        alignItems: 'baseline',
        gap: 22,
        marginBottom: 18,
      }}>
        <span style={{
          fontFamily: Syne,
          fontSize: 'clamp(80px, 12vw, 152px)',
          fontWeight: 800,
          color: tone,
          lineHeight: 0.85,
          letterSpacing: '-0.02em',
        }}>
          {symbol}
        </span>
        <div>
          <div style={{
            fontFamily: Mono,
            fontSize: 11,
            color: TEXT_FAINT,
            letterSpacing: '0.24em',
            textTransform: 'uppercase',
            marginBottom: 10,
          }}>
            On-chain verdict
          </div>
          <div style={{
            fontFamily: Syne,
            fontSize: 'clamp(28px, 3.4vw, 44px)',
            fontWeight: 700,
            letterSpacing: '-0.025em',
            color: tone,
            lineHeight: 1.0,
          }}>
            {verdict}
          </div>
        </div>
      </div>

      <p style={{
        fontFamily: Syne,
        fontSize: 17,
        lineHeight: 1.55,
        color: TEXT_DIM,
        margin: '0 0 14px',
        maxWidth: '54ch',
      }}>
        {detail}
      </p>

      {registered && (
        <div style={{
          marginTop: 28,
          paddingTop: 22,
          borderTop: `1px solid ${BORDER}`,
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: 18,
        }}>
          <FieldRow label="Signing path">
            {cert.signing_path_label?.replace(/_/g, ' ').toLowerCase()}
          </FieldRow>
          <FieldRow label="Proof tier">
            {cert.proof_tier_label?.replace(/_/g, ' ').toLowerCase()}
          </FieldRow>
        </div>
      )}
    </div>
  )
}

function FieldRow({ label, children }) {
  return (
    <div>
      <div style={{
        fontFamily: Mono,
        fontSize: 9,
        color: TEXT_FAINT,
        letterSpacing: '0.22em',
        textTransform: 'uppercase',
        marginBottom: 6,
      }}>
        {label}
      </div>
      <div style={{
        fontFamily: Syne,
        fontSize: 14,
        color: TEXT,
      }}>
        {children}
      </div>
    </div>
  )
}

// ──────────────────────────────────────────────────────────────────────
// INPUT — when /verify is opened with no device_id
// ──────────────────────────────────────────────────────────────────────

function ManualInput() {
  const [value, setValue] = useState('')
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        if (!value.trim()) return
        const v = value.trim().replace(/^0x/i, '')
        window.location.href = `/verify/${v}`
      }}
      style={{
        marginTop: 36,
        padding: '24px 26px',
        background: PARCHMENT_SOFT,
        border: `1px solid ${BORDER}`,
        borderRadius: 8,
      }}
    >
      <label style={{
        display: 'block',
        fontFamily: Mono,
        fontSize: 10,
        color: TEXT_FAINT,
        letterSpacing: '0.22em',
        textTransform: 'uppercase',
        marginBottom: 12,
      }}>
        Paste a device_id to verify
      </label>
      <div style={{ display: 'flex', gap: 10 }}>
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="64-char hex · keccak256(controller_pubkey)"
          spellCheck={false}
          style={{
            flex: 1,
            padding: '14px 16px',
            background: PARCHMENT,
            border: `1px solid ${BORDER}`,
            borderRadius: 4,
            fontFamily: Mono,
            fontSize: 12,
            color: TEXT,
            outline: 'none',
            letterSpacing: '0.04em',
          }}
        />
        <button
          type="submit"
          style={{
            padding: '14px 22px',
            background: CHAIN,
            color: PARCHMENT,
            border: 'none',
            borderRadius: 4,
            fontFamily: Mono,
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: '0.16em',
            textTransform: 'uppercase',
            cursor: 'pointer',
          }}
        >
          Verify
        </button>
      </div>
    </form>
  )
}

// ──────────────────────────────────────────────────────────────────────
// DAPP ENTRY
// ──────────────────────────────────────────────────────────────────────

export default function HardwareVerifyDapp() {
  const { deviceId } = useParams()
  const normalized = (deviceId || '').toLowerCase().replace(/^0x/, '')
  const { data: cert, isLoading, isError } = useDeviceCert(normalized)

  return (
    <div style={{
      background: PARCHMENT,
      color: TEXT,
      minHeight: '100vh',
      fontFamily: Syne,
      padding: '40px 6vw 80px',
    }}>
      {/* minimal certificate-document chrome */}
      <header style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'baseline',
        marginBottom: 60,
        paddingBottom: 22,
        borderBottom: `1px solid ${BORDER}`,
      }}>
        <Link to="/" style={{
          fontFamily: Syne,
          fontSize: 19,
          fontWeight: 700,
          color: TEXT,
          textDecoration: 'none',
          letterSpacing: '-0.02em',
        }}>
          Qor<span style={{ color: AMBER, fontWeight: 800 }}>T</span>roller
        </Link>
        <span style={{
          fontFamily: Mono,
          fontSize: 10,
          color: TEXT_FAINT,
          letterSpacing: '0.22em',
          textTransform: 'uppercase',
        }}>
          Hardware · Authenticity · Verify
        </span>
      </header>

      {/* device_id headline */}
      <div style={{ marginBottom: 36 }}>
        <div style={{
          fontFamily: Mono,
          fontSize: 10,
          color: TEXT_FAINT,
          letterSpacing: '0.24em',
          textTransform: 'uppercase',
          marginBottom: 14,
        }}>
          {normalized ? 'device_id' : 'Public hardware certificate'}
        </div>
        {normalized ? (
          <div style={{
            fontFamily: Mono,
            fontSize: 'clamp(13px, 1.4vw, 18px)',
            color: TEXT,
            wordBreak: 'break-all',
            letterSpacing: '0.02em',
            lineHeight: 1.5,
          }}>
            <span style={{ color: TEXT_FAINT }}>0x</span>{normalized}
          </div>
        ) : (
          <h1 style={{
            fontFamily: Syne,
            fontSize: 'clamp(36px, 5.5vw, 68px)',
            fontWeight: 700,
            color: TEXT,
            letterSpacing: '-0.03em',
            lineHeight: 1.0,
            margin: 0,
            maxWidth: '18ch',
          }}>
            Verify any controller. <span style={{ color: AMBER }}>No login.</span>
          </h1>
        )}
      </div>

      {/* verdict / loading / error / manual-entry */}
      {!normalized ? (
        <>
          <p style={{
            fontFamily: Syne,
            fontSize: 18,
            lineHeight: 1.6,
            color: TEXT_DIM,
            margin: '0 0 16px',
            maxWidth: '52ch',
          }}>
            Paste a device_id below. The answer comes from a single on-chain
            view-call against <code style={{ color: AMBER, fontFamily: Mono }}>VAPIManufacturerDeviceRegistry</code> on IoTeX testnet. No
            wallet, no auth, no tracking. Bookmark or share the result URL — the answer is permanent.
          </p>
          <ManualInput />
        </>
      ) : isLoading ? (
        <Loading />
      ) : isError ? (
        <ErrorBlock />
      ) : (
        <VerdictBlock cert={cert} />
      )}

      {/* footer — discipline disclosure */}
      {cert?.discipline && (
        <div style={{
          marginTop: 60,
          paddingTop: 22,
          borderTop: `1px solid ${BORDER}`,
          fontFamily: Mono,
          fontSize: 10,
          color: TEXT_FAINT,
          lineHeight: 1.7,
          letterSpacing: '0.06em',
          maxWidth: '76ch',
        }}>
          {cert.discipline}
          {cert.explorer_address && (
            <>
              {' · '}
              <a
                href={cert.explorer_address}
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: AMBER, textDecoration: 'none' }}
              >
                inspect registry on explorer ↗
              </a>
            </>
          )}
        </div>
      )}
    </div>
  )
}

function Loading() {
  return (
    <div style={{
      padding: '40px 20px',
      fontFamily: Mono,
      fontSize: 12,
      color: TEXT_FAINT,
      letterSpacing: '0.18em',
      textTransform: 'uppercase',
    }}>
      Reading the chain…
    </div>
  )
}

function ErrorBlock() {
  return (
    <div style={{
      padding: '24px 26px',
      background: PARCHMENT_SOFT,
      border: `1px solid ${AMBER}55`,
      borderRadius: 6,
      fontFamily: Mono,
      fontSize: 12,
      color: TEXT_DIM,
      lineHeight: 1.6,
    }}>
      Bridge unreachable. The verification answer needs a live bridge to
      read VAPIManufacturerDeviceRegistry on-chain. Refresh to retry.
    </div>
  )
}
