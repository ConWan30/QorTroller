/**
 * Evidence OS — AppShell
 *
 * Wraps the 5 workspaces with a left-rail nav + global StatusStrip.
 * Semantic landmarks:
 *   <header>  → StatusStrip (already role="navigation" inside)
 *   <nav>     → left rail
 *   <main>    → workspace outlet
 *
 * Routing structure:
 *   /os                 → redirects to /os/evidence (signature view)
 *   /os/live            → LiveMatchWorkspace
 *   /os/evidence        → EvidenceGraphWorkspace
 *   /os/queue           → OperatorQueueWorkspace
 *   /os/replay          → ForensicReplayWorkspace
 *   /os/protocol        → ProtocolStateWorkspace
 *
 * Wired via <Outlet /> from react-router-dom v6 nested route in main.jsx.
 */
import { NavLink, Outlet } from 'react-router-dom'
import StatusStrip from './components/StatusStrip'
import './theme.css'

const _WORKSPACES = [
  {
    to:    '/os/live',
    label: 'Live Match',
    desc:  'Frame-rate cognition feed',
  },
  {
    to:    '/os/evidence',
    label: 'Evidence Graph',
    desc:  'HID → on-chain causal DAG',
  },
  {
    to:    '/os/queue',
    label: 'Operator Queue',
    desc:  'Drafts awaiting decision',
  },
  {
    to:    '/os/replay',
    label: 'Forensic Replay',
    desc:  'Re-derive any historical claim',
  },
  {
    to:    '/os/protocol',
    label: 'Protocol State',
    desc:  'PV-CI / agents / kill-switch',
  },
]

const _LEGACY_LINKS = [
  { to: '/',          label: 'Classic Operator Cockpit' },
  { to: '/explorer',  label: 'Public Forensic Explorer' },
  { to: '/algorithms', label: 'Algorithm Catalog' },
]

export default function AppShell() {
  return (
    <div className="os-shell">
      <StatusStrip />
      <div style={{
        display:    'grid',
        gridTemplateColumns: 'var(--os-rail-width) 1fr',
        minHeight:  'calc(100dvh - var(--os-strip-h))',
      }}>
        {/* Left rail nav */}
        <nav
          aria-label="Evidence OS workspaces"
          style={{
            borderRight:    '1px solid var(--os-border)',
            background:     'var(--os-panel-soft)',
            padding:        '24px 0',
            display:        'flex',
            flexDirection:  'column',
            gap:            2,
          }}
        >
          {_WORKSPACES.map((ws) => (
            <NavLink
              key={ws.to}
              to={ws.to}
              data-os-nav-link={ws.to}
              style={({ isActive }) => ({
                display:        'flex',
                flexDirection:  'column',
                gap:            2,
                padding:        '12px 20px',
                borderLeft:     `3px solid ${isActive ? 'var(--os-accent)' : 'transparent'}`,
                background:     isActive ? 'var(--os-panel)' : 'transparent',
                color:          isActive ? 'var(--os-text)' : 'var(--os-text-dim)',
                textDecoration: 'none',
                fontFamily:     'JetBrains Mono, ui-monospace, monospace',
              })}
            >
              <span style={{
                fontSize:       'var(--os-text-label)',
                fontWeight:     700,
                letterSpacing:  '0.04em',
              }}>{ws.label}</span>
              <span style={{
                fontSize:    'var(--os-text-min)',
                color:       'var(--os-text-faint)',
              }}>{ws.desc}</span>
            </NavLink>
          ))}

          {/* Legacy cockpit links — preserved per operator brief */}
          <div style={{
            marginTop:      24,
            padding:        '12px 20px 4px',
            borderTop:      '1px solid var(--os-border)',
            fontSize:       'var(--os-text-min)',
            color:          'var(--os-text-faint)',
            letterSpacing:  '0.08em',
            textTransform:  'uppercase',
          }}>Legacy & Public</div>
          {_LEGACY_LINKS.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              style={{
                padding:        '8px 20px',
                color:          'var(--os-text-dim)',
                textDecoration: 'none',
                fontSize:       'var(--os-text-base)',
                fontFamily:     'JetBrains Mono, ui-monospace, monospace',
              }}
            >{l.label} →</NavLink>
          ))}
        </nav>

        <main
          role="main"
          aria-label="Active workspace"
          style={{ display: 'flex', flexDirection: 'column' }}
        >
          <Outlet />
        </main>
      </div>
    </div>
  )
}
