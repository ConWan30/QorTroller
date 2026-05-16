/**
 * Evidence OS — ReplayModeTabs
 *
 * Segmented control across the 5 forensic-replay modes:
 *
 *   Session    /os/replay/session/:commitmentHex
 *   GIC Chain  /os/replay/gic/:grindSessionId
 *   PoAC Record /os/replay/record/:deviceId/:counter
 *   VHP        /os/replay/vhp/:tokenId
 *   Algorithms /os/replay/algorithms
 *
 * Tabs that don't yet have a value (no input submitted) render as
 * disabled with an inline hint pointing at the search bar above.
 * Tabs the operator HAS visited show as enabled even after they
 * navigate elsewhere, so the operator can pivot between modes
 * without re-typing.
 *
 * Discipline:
 *   - role='tablist' + role='tab' + aria-selected per WAI-ARIA
 *     authoring practice; the route changes are the panel transitions
 *   - Disabled state surfaces the reason ("paste a session hash first")
 *     — never silently disabled
 */
import PropTypes from 'prop-types'
import { Link, useLocation } from 'react-router-dom'

const _MONO = 'JetBrains Mono, ui-monospace, monospace'

const _MODES = [
  { key: 'session',   label: 'Session',     short: 'Hash',     requires: 'session commitment hash' },
  { key: 'gic',       label: 'GIC Chain',   short: 'Chain',    requires: 'grind session id' },
  { key: 'record',    label: 'PoAC Record', short: 'Record',   requires: 'device/counter' },
  { key: 'vhp',       label: 'VHP',         short: 'VHP',      requires: 'VHP token id' },
  { key: 'algorithms', label: 'Algorithms', short: 'Algos',    requires: null }, // always available
]

function _activeMode(pathname) {
  if (pathname.match(/\/os\/replay\/session\//))    return 'session'
  if (pathname.match(/\/os\/replay\/gic\//))        return 'gic'
  if (pathname.match(/\/os\/replay\/record\//))     return 'record'
  if (pathname.match(/\/os\/replay\/vhp\//))        return 'vhp'
  if (pathname.match(/\/os\/replay\/algorithms/))   return 'algorithms'
  return null
}

export default function ReplayModeTabs({ available = {}, paths = {} }) {
  const loc = useLocation()
  const active = _activeMode(loc.pathname)

  return (
    <div
      role="tablist"
      aria-label="Forensic replay modes"
      style={{
        display:        'flex',
        gap:            6,
        padding:        '6px 8px',
        background:     'var(--os-panel)',
        border:         '1px solid var(--os-border)',
        borderRadius:   'var(--os-radius)',
        fontFamily:     _MONO,
        flexWrap:       'wrap',
      }}
    >
      {_MODES.map(m => {
        const isAvailable = m.requires === null || Boolean(available[m.key])
        const isActive    = active === m.key
        const path        = paths[m.key]
        const enabled     = isAvailable && Boolean(path)

        const inner = (
          <span style={{
            display:        'inline-flex',
            alignItems:     'center',
            gap:            6,
            padding:        '5px 12px',
            fontSize:       'var(--os-text-min)',
            fontWeight:     isActive ? 700 : 500,
            letterSpacing:  '0.06em',
            textTransform:  'uppercase',
            color:          isActive
              ? 'var(--os-accent)'
              : enabled
                ? 'var(--os-text)'
                : 'var(--os-text-faint)',
            background:     isActive ? 'var(--os-accent-soft)' : 'transparent',
            border:         `1px solid ${isActive ? 'var(--os-accent)' : 'var(--os-border)'}`,
            borderRadius:   'var(--os-radius)',
            opacity:        enabled || isActive ? 1 : 0.55,
            cursor:         enabled ? 'pointer' : 'not-allowed',
          }}>
            {m.label}
          </span>
        )

        // Use Link only when enabled — disabled tabs render as a span
        // with role=tab + aria-disabled + title explaining what's needed
        if (!enabled) {
          return (
            <span
              key={m.key}
              role="tab"
              aria-selected={isActive}
              aria-disabled="true"
              data-os-replay-tab={m.key}
              data-os-tab-enabled="false"
              title={m.requires ? `Paste a ${m.requires} first` : ''}
              style={{ textDecoration: 'none' }}
            >{inner}</span>
          )
        }

        return (
          <Link
            key={m.key}
            to={path}
            role="tab"
            aria-selected={isActive}
            data-os-replay-tab={m.key}
            data-os-tab-enabled="true"
            style={{ textDecoration: 'none' }}
          >{inner}</Link>
        )
      })}
    </div>
  )
}

ReplayModeTabs.propTypes = {
  /* Map of mode → boolean for "operator has entered an input that
     resolves to this mode in the current session". algorithms is
     always available regardless. */
  available: PropTypes.shape({
    session:    PropTypes.bool,
    gic:        PropTypes.bool,
    record:     PropTypes.bool,
    vhp:        PropTypes.bool,
    algorithms: PropTypes.bool,
  }),
  /* Map of mode → router path the tab links to. */
  paths: PropTypes.shape({
    session:    PropTypes.string,
    gic:        PropTypes.string,
    record:     PropTypes.string,
    vhp:        PropTypes.string,
    algorithms: PropTypes.string,
  }),
}
