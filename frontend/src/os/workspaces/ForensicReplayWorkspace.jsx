/**
 * Evidence OS Stage 4 — Forensic Replay
 *
 * One unified search/input surface that folds the 6 public forensic
 * routes into one in-OS workspace WITHOUT duplicating cryptographic
 * logic. The existing 6 top-level public routes (/explorer, /session/*,
 * /gic/*, /record/*, /vhp/*, /algorithms) are preserved unchanged
 * per operator brief; this workspace mounts the same viewer components
 * via nested routes under /os/replay/*.
 *
 * Composition (no new endpoints, no new cryptographic logic):
 *   ReplaySearch          — input-type detection (session / gic /
 *                           record / vhp / algorithm)
 *   ReplayModeTabs        — segmented control across 5 modes; tabs
 *                           disabled until operator has entered a
 *                           value that resolves to them
 *   <Outlet/>             — renders one of:
 *                             PublicSessionViewer
 *                             GicChainExplorerView
 *                             PoacRecordExplorerView
 *                             VhpCredentialView
 *                             AlgorithmCatalogView
 *                           per the active nested route
 *   VerificationReceipt   — Stage 4 audit footer; in v1 each viewer
 *                           already runs its own crypto-replay surface
 *                           (CryptoReplayPanel / PoacBodyHasher /
 *                           GicChainTimeline), so the receipt here
 *                           starts in "no checks yet — open a viewer
 *                           to recompute" state and is populated as
 *                           the operator drills in
 *
 * Safety:
 *   - No operator API key required for /public/* routes (the viewers
 *     route through publicForensic.js which calls /public/* without
 *     x-api-key header)
 *   - Iframe sandboxing in VpmIframe untouched ("allow-scripts
 *     allow-same-origin" stays FROZEN per INV-VPM-SANDBOX-001)
 *   - When the viewers hit a 404 / offline, they already render
 *     honest empty states — no fabrication
 */
import { useState, useMemo, useCallback } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import WorkspaceHeader      from '../components/WorkspaceHeader'
import ReplaySearch         from '../components/ReplaySearch'
import ReplayModeTabs       from '../components/ReplayModeTabs'
import VerificationReceipt  from '../components/VerificationReceipt'
import ReplaySourceLink     from '../components/ReplaySourceLink'
import EmptyState           from '../components/EmptyState'

function _pathFor(mode, params) {
  switch (mode) {
    case 'session':    return `/os/replay/session/${params.commitmentHex}`
    case 'gic':        return `/os/replay/gic/${encodeURIComponent(params.grindSessionId)}`
    case 'record':     return `/os/replay/record/${params.deviceId}/${params.counter}`
    case 'vhp':        return `/os/replay/vhp/${params.tokenId}`
    case 'algorithm':  return `/os/replay/algorithms${params.q ? `?q=${encodeURIComponent(params.q)}` : ''}`
    case 'algorithms': return '/os/replay/algorithms'
    default:           return null
  }
}

function _publicSourceLinkFor(pathname) {
  // Map the in-OS nested route to its top-level public URL so the
  // operator can copy/share a clean shareable link.
  if (pathname.includes('/os/replay/session/')) {
    const hex = pathname.split('/').pop()
    return { href: `/session/${hex}`, label: 'Open shareable public viewer' }
  }
  if (pathname.includes('/os/replay/gic/')) {
    const sid = decodeURIComponent(pathname.split('/').pop())
    return { href: `/gic/${sid}`, label: 'Open shareable public viewer' }
  }
  if (pathname.includes('/os/replay/record/')) {
    const tail = pathname.split('/os/replay/record/')[1]
    return { href: `/record/${tail}`, label: 'Open shareable public viewer' }
  }
  if (pathname.includes('/os/replay/vhp/')) {
    const tk = pathname.split('/').pop()
    return { href: `/vhp/${tk}`, label: 'Open shareable public viewer' }
  }
  if (pathname.includes('/os/replay/algorithms')) {
    return { href: '/algorithms', label: 'Open algorithm catalog' }
  }
  return null
}

export default function ForensicReplayWorkspace() {
  const navigate = useNavigate()
  const loc      = useLocation()

  // Track the most recent value typed per mode so tabs stay enabled
  // even after navigation. Lives in workspace state — not URL, not
  // localStorage; resets on full reload (acceptable for v1).
  const [paths, setPaths] = useState({
    session:    null,
    gic:        null,
    record:     null,
    vhp:        null,
    algorithms: '/os/replay/algorithms',
  })

  const handleSubmit = useCallback((detected) => {
    const target = _pathFor(detected.mode, detected.params)
    if (!target) return
    setPaths(prev => ({
      ...prev,
      // Map 'algorithm' → 'algorithms' tab key
      [detected.mode === 'algorithm' ? 'algorithms' : detected.mode]: target,
    }))
    navigate(target)
  }, [navigate])

  const available = useMemo(() => ({
    session:    Boolean(paths.session),
    gic:        Boolean(paths.gic),
    record:     Boolean(paths.record),
    vhp:        Boolean(paths.vhp),
    algorithms: true,
  }), [paths])

  const sourceLink = _publicSourceLinkFor(loc.pathname)
  const isIndex = loc.pathname === '/os/replay' || loc.pathname === '/os/replay/'

  // Stage 4 v1 — the viewers each emit their own verifications
  // already (CryptoReplayPanel re-hashes server-side values; PoAC
  // body hasher recomputes record_hash; GIC timeline recomputes
  // genesis + every link). The receipt here surfaces a HONEST
  // "checks live inside the viewer" pointer plus the public-API
  // source for the active mode, instead of duplicating that logic.
  const receiptItems = useMemo(() => {
    if (isIndex) return []
    const ts = Date.now()
    const items = []
    if (loc.pathname.includes('/session/')) {
      items.push({
        id: 'session-info', status: 'skipped',
        claim: 'Session-level commitments + Integrity Label hash + linked GIC links',
        reason: 'In-viewer CryptoReplayPanel runs the actual SHA-256 re-derivations row-by-row; scroll inside the viewer below to see live OK / MISMATCH per primitive.',
        source: '/public/session/<commitment>', algorithm: 'vapi_verifier.js (multiple)',
        tsMs: ts,
      })
    }
    if (loc.pathname.includes('/gic/')) {
      items.push({
        id: 'gic-info', status: 'skipped',
        claim: 'GIC chain — genesis + every link recomputed locally',
        reason: 'GicChainExplorerView re-hashes via verifyGicGenesis + verifyGicChainLink for every link in the chain; OK/MISMATCH appears alongside each link inside the viewer.',
        source: '/public/gic/<grindSessionId>', algorithm: 'verifyGicGenesis · verifyGicChainLink',
        tsMs: ts,
      })
    }
    if (loc.pathname.includes('/record/')) {
      items.push({
        id: 'record-info', status: 'skipped',
        claim: '228-byte PoAC record body hash',
        reason: 'PoacBodyHasher inside the viewer fetches the raw 228-byte blob and recomputes SHA-256(raw[:164]) in the browser. Match/mismatch surfaces in the viewer.',
        source: '/public/record/<deviceId>/<counter>', algorithm: 'verifyPoacRecordHash',
        tsMs: ts,
      })
    }
    if (loc.pathname.includes('/vhp/')) {
      items.push({
        id: 'vhp-info', status: 'skipped',
        claim: 'VHP credential — soulbound token state + expiresAt + isValid',
        reason: 'VhpCredentialView fetches on-chain state via /public/vhp/<tokenId>; expiresAt and isValid are protocol-side fields. No browser-side re-hashing is published for VHP in v1.',
        source: '/public/vhp/<tokenId>', algorithm: '(no v1 browser-side verifier)',
        tsMs: ts,
      })
    }
    if (loc.pathname.includes('/algorithms')) {
      items.push({
        id: 'algos-info', status: 'skipped',
        claim: 'Frozen-v1 domain tag catalog',
        reason: 'AlgorithmCatalogView renders the 14 FROZEN-v1 cryptographic primitives and their byte layouts. There is no claim to verify here — this is the protocol\'s own specification surface.',
        source: '/public/algorithms', algorithm: '(specification, not computation)',
        tsMs: ts,
      })
    }
    return items
  }, [loc.pathname, isIndex])

  return (
    <>
      <WorkspaceHeader
        title="Forensic Replay"
        description="Paste any cryptographic claim from QorTroller and re-derive it in this browser. No operator API key required. The same six public routes mounted at /explorer · /session · /gic · /record · /vhp · /algorithms are reused unchanged here, inside the Evidence OS shell."
        right={sourceLink && (
          <ReplaySourceLink href={sourceLink.href} label={sourceLink.label}/>
        )}
      />

      <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
        <ReplaySearch onSubmit={handleSubmit}/>

        <ReplayModeTabs available={available} paths={paths}/>

        {/* Active viewer mounts here via nested route */}
        <div data-os-replay-outlet style={{
          minHeight: 360,
          background: 'var(--os-panel)',
          border: '1px solid var(--os-border)',
          borderRadius: 'var(--os-radius)',
          overflow: 'hidden',
        }}>
          {isIndex ? (
            <EmptyState
              title="Paste any commitment, grind id, device/counter, or VHP token id"
              body={
                <>
                  This workspace re-runs cryptographic verifications in your
                  browser using the same FROZEN-v1 algorithms the protocol
                  publishes. The detected input type appears under the
                  search box; clicking <strong>Open</strong> mounts the
                  corresponding viewer here. The six top-level public
                  routes (<code>/session/…</code>, <code>/gic/…</code>,{' '}
                  <code>/record/…</code>, <code>/vhp/…</code>,{' '}
                  <code>/algorithms</code>, <code>/explorer</code>) remain
                  available for sharing and bookmarking.
                </>
              }
              source="ReplaySearch · ReplayModeTabs · 5 viewers · 14 verifiers"
            />
          ) : (
            <Outlet/>
          )}
        </div>

        <VerificationReceipt items={receiptItems} title="Verification receipt — current mode"/>
      </div>
    </>
  )
}
