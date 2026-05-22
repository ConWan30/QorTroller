/**
 * Evidence OS — AppShell
 *
 * v2 design pass · item E — chrome unified with the operator dashboard. The
 * surface now wears the SAME three-landmark spine as the dashboard:
 *
 *   [ STRIP   — Syne medial-T wordmark · numbered tabs · bridge/kill-switch ]
 *   [ EYEBROW — NN · WORKSPACE NAME  +  Agents · PV-CI · VPM · GIC · Blockers ]  (shared <ViewEyebrowBar>)
 *   [ workspace body ]
 *
 * The numbered tabs use the dashboard's exact bordered-box + accent treatment;
 * the old StatusStrip's metrics are promoted into the shared eyebrow row (the
 * dashboard shows view-name + 3 readouts there; Evidence OS shows view-name +
 * the fleet metrics — same component, same height, same fonts).
 *
 * De-duplicated against the dashboard's tabs — keeps only the surfaces with no
 * dashboard analog: 01 Evidence Graph · 02 Forensic Replay · 03 Protocol State.
 *
 * Semantic landmarks: <header> strip · <nav> tabs · <main> outlet.
 */
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useOsStatus } from './components/StatusStrip'
import DataBadge from './components/DataBadge'
import { ViewEyebrowBar } from '../design/Eyebrow'
import { RealityDot } from '../design/realityHeartbeat'
import './theme.css'
import '../design/qortroller-kit.css'

const _WORKSPACES = [
  { to: '/os/evidence', num: '01', label: 'Evidence Graph',  name: 'EVIDENCE GRAPH',  accent: '#5bd6a3' },
  { to: '/os/replay',   num: '02', label: 'Forensic Replay', name: 'FORENSIC REPLAY', accent: '#5bd6a3' },
  { to: '/os/protocol', num: '03', label: 'Protocol State',  name: 'PROTOCOL STATE',  accent: '#f0a868' },
]

const _LEGACY_LINKS = [
  { to: '/',           label: 'Classic Operator Cockpit' },
  { to: '/explorer',   label: 'Public Forensic Explorer' },
  { to: '/algorithms', label: 'Algorithm Catalog' },
]

export default function AppShell() {
  const status = useOsStatus()
  const { pathname } = useLocation()
  const active = _WORKSPACES.find((w) => pathname.startsWith(w.to)) || _WORKSPACES[0]

  // Shared eyebrow content — view names itself + the fleet metrics (the old
  // StatusStrip cells). Honest: bridge status drives the status word; coherence
  // reads "—" / dim when unauthenticated or offline.
  const eyebrow = {
    num: active.num,
    name: active.name,
    status: status.bridgeStatus === 'live' ? 'LIVE'
      : status.bridgeStatus === 'mock' ? 'MOCK DATA' : 'BRIDGE UNREACHABLE',
    statusTone: status.bridgeStatus === 'live' ? 'live'
      : status.bridgeStatus === 'mock' ? 'mock' : 'blocked',
    readouts: [
      { label: 'Agents',   value: status.agentCount, tone: 'amber' },
      { label: 'PV-CI',    value: status.pvCi, tone: 'chain' },
      { label: 'VPM',      value: status.vpm, tone: 'amber' },
      { label: 'GIC',      value: status.gic, tone: 'chain' },
      { label: 'Blockers', value: status.blockerCount,
        tone: !status.coherenceAvailable ? 'dim' : status.blockerCount > 0 ? 'blocked' : 'live' },
    ],
  }

  return (
    <div
      className="os-shell qt-design-root"
      style={{ display: 'flex', flexDirection: 'column', minHeight: '100dvh',
               fontFamily: "'JetBrains Mono', ui-monospace, monospace" }}
    >
      {/* ── STRIP — wordmark · numbered tabs · status (dashboard chrome) ── */}
      <header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
        padding: '6px 16px', borderBottom: '1px solid var(--border)',
        background: 'rgba(4,6,10,0.95)', backdropFilter: 'blur(12px)',
        minWidth: 0, maxWidth: '100vw', overflow: 'hidden',
      }}>
        {/* left — wordmark + dashboard link */}
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, minWidth: 0, flexShrink: 1 }}>
          <NavLink to="/" aria-label="Return to operator dashboard" style={{
            fontFamily: "'Syne', system-ui, sans-serif", fontSize: 18, fontWeight: 700,
            letterSpacing: '-0.02em', color: '#d4dde8', textDecoration: 'none',
            display: 'inline-flex', alignItems: 'baseline', whiteSpace: 'nowrap', flexShrink: 0,
          }}>
            <span>Qor</span><span style={{ color: '#f0a868', fontWeight: 800 }}>T</span><span>roller</span>
          </NavLink>
          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9,
            letterSpacing: '0.12em', textTransform: 'uppercase', color: '#f0a868a6', whiteSpace: 'nowrap' }}>
            Evidence OS
          </span>
        </div>

        {/* center — numbered tabs only (dashboard-identical). Legacy/public
            links live in the footer so the strip never overcrowds + overlaps. */}
        <nav aria-label="Evidence OS workspaces" style={{ display: 'flex', gap: 2, flexShrink: 0 }}>
          {_WORKSPACES.map((w) => {
            const isActive = active.to === w.to
            return (
              <NavLink key={w.to} to={w.to} data-os-nav-link={w.to} title={w.name} style={{
                background: isActive ? `${w.accent}18` : 'transparent',
                border: `1px solid ${isActive ? w.accent + '55' : 'rgba(255,255,255,0.06)'}`,
                borderRadius: 4, padding: '4px 14px', textDecoration: 'none',
                display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 2,
                lineHeight: 1.1, whiteSpace: 'nowrap',
              }}>
                <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, fontWeight: 500,
                  letterSpacing: '0.14em', color: isActive ? w.accent : 'rgba(200,216,232,0.30)' }}>{w.num}</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 6,
                  fontFamily: "'Syne', system-ui, sans-serif", fontSize: 13,
                  fontWeight: isActive ? 700 : 500, letterSpacing: '0.01em',
                  color: isActive ? w.accent : 'rgba(200,216,232,0.50)' }}>
                  {w.label}
                  {isActive && <span style={{ width: 4, height: 4, borderRadius: '50%',
                    background: w.accent, boxShadow: `0 0 6px ${w.accent}` }} />}
                </span>
              </NavLink>
            )
          })}
        </nav>

        {/* right — honest bridge + kill-switch + merkle */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0, flexShrink: 1, justifyContent: 'flex-end' }}>
          <RealityDot />
          <DataBadge status={status.bridgeStatus} label={`BRIDGE ${status.bridgeLabel}`}
                     ariaLabel={`Bridge state: ${status.bridgeLabel}`} />
          <DataBadge status={status.killSwitchPaused ? 'killswitch' : 'live'}
                     label={status.killSwitchPaused ? 'KILL-SWITCH PAUSED' : 'CHAIN LIVE'}
                     ariaLabel={status.killSwitchPaused ? 'Chain submissions paused' : 'Chain submissions live'} />
          <code style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10,
            color: 'var(--text-faint)', whiteSpace: 'nowrap' }} title={status.firstAgentMerkle}>
            {status.merkleShort}
          </code>
        </div>
      </header>

      {/* ── EYEBROW — shared spine row (identical to the dashboard) ── */}
      <ViewEyebrowBar data={eyebrow} />

      {/* ── BODY ── */}
      <main role="main" aria-label="Active workspace"
            style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <Outlet />
      </main>

      {/* ── FOOT — legacy & public escape hatches (off the strip to avoid
          overcrowding); right-aligned, dim, always reachable. ── */}
      <nav aria-label="Legacy and public links" style={{
        display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 16,
        height: 28, padding: '0 16px', borderTop: '1px solid var(--border)',
        background: 'var(--bg)', flexShrink: 0, overflowX: 'auto',
      }}>
        {_LEGACY_LINKS.map((l) => (
          <NavLink key={l.to} to={l.to} style={{
            fontFamily: "'JetBrains Mono', monospace", fontSize: 10, letterSpacing: '0.06em',
            color: 'var(--text-faint)', textDecoration: 'none', whiteSpace: 'nowrap',
          }}>{l.label} →</NavLink>
        ))}
      </nav>
    </div>
  )
}
