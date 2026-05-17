/**
 * Evidence OS — ReplaySearch
 *
 * Single input surface for /os/replay. Operator pastes ANY of:
 *
 *   - 64-char session commitment hash      → session viewer
 *   - "grind_YYYYMMDD_v1" / "grind_*"      → GIC chain explorer
 *   - "<deviceIdHex64>/<counter>"          → PoAC record viewer
 *   - "<deviceIdHex64> <counter>"          → PoAC record viewer
 *   - "VHP-<n>" or pure integer            → VHP credential viewer
 *   - free-text                            → algorithm catalog query
 *
 * Detection is deliberate (not magical): see detectInput() below.
 * The detected type is rendered as a chip BEFORE submit so the
 * operator can sanity-check before navigating.
 *
 * Discipline:
 *   - role=search wrapping form; explicit <label> for input
 *   - "Detected: X" chip with status word — never icon-only
 *   - Mode override row lets operator force a mode if detection
 *     disagrees with intent (e.g. operator wants algorithm search
 *     for a string that looks like a counter)
 */
import { useState, useMemo } from 'react'
import PropTypes from 'prop-types'
import DataBadge from './DataBadge'

const _MONO = 'JetBrains Mono, ui-monospace, monospace'

const _HEX64 = /^[0-9a-fA-F]{64}$/
const _DEVICE_COUNTER = /^([0-9a-fA-F]{64})[\s/](\d{1,12})$/
const _VHP_TAG = /^VHP[-_]?(\d{1,12})$/i
const _INT  = /^\d{1,12}$/

/**
 * Pure detection — no router, no fetch. Returns:
 *   { mode, params, label, reason }
 *   mode: 'session'|'gic'|'record'|'vhp'|'algorithm'|'empty'
 *   params: route param dict ready to plug into a Link path
 *   label: human-readable badge text
 *   reason: why this mode was chosen (operator-facing)
 *
 * Exported for unit testing — see __tests__/ReplaySearch.detect.test.jsx
 */
export function detectInput(rawIn) {
  const raw = (rawIn || '').trim()
  if (!raw) return {
    mode: 'empty', params: {}, label: 'empty', reason: 'Enter a hash, grind id, or query',
  }

  if (_HEX64.test(raw)) {
    return {
      mode: 'session',
      params: { commitmentHex: raw.toLowerCase() },
      label: 'session commitment',
      reason: '64-char hex matches a VPM artifact commitment hash',
    }
  }

  const dc = raw.match(_DEVICE_COUNTER)
  if (dc) {
    return {
      mode: 'record',
      params: { deviceId: dc[1].toLowerCase(), counter: dc[2] },
      label: 'PoAC record',
      reason: '64-char hex + counter matches device/counter pair',
    }
  }

  if (raw.toLowerCase().startsWith('grind_') || raw.toLowerCase().startsWith('grind-')) {
    return {
      mode: 'gic',
      params: { grindSessionId: raw },
      label: 'grind session id',
      reason: 'Starts with "grind_" — matches GIC genesis id convention',
    }
  }

  const vhpTag = raw.match(_VHP_TAG)
  if (vhpTag) {
    return {
      mode: 'vhp',
      params: { tokenId: vhpTag[1] },
      label: 'VHP token',
      reason: 'Matches VHP-<n> token-id convention',
    }
  }

  if (_INT.test(raw)) {
    return {
      mode: 'vhp',
      params: { tokenId: raw },
      label: 'VHP token (integer)',
      reason: 'Pure integer — defaulting to VHP token id (use override to force algorithm query)',
    }
  }

  // Fall through — anything else is an algorithm/catalog search
  return {
    mode: 'algorithm',
    params: { q: raw },
    label: 'algorithm query',
    reason: 'Free-text — searching algorithm catalog',
  }
}

const _MODE_BADGE = {
  session:   'verified',
  gic:       'live',
  record:    'verified',
  vhp:       'verified',
  algorithm: 'pending',
  empty:     'dormant',
}

export default function ReplaySearch({
  initialValue = '',
  initialOverride = '',
  onSubmit,
}) {
  const [value, setValue]       = useState(initialValue)
  const [override, setOverride] = useState(initialOverride) // ''|'session'|'gic'|'record'|'vhp'|'algorithm'

  const auto = useMemo(() => detectInput(value), [value])
  const effective = override ? { ...auto, mode: override, reason: `Operator override → ${override}` } : auto

  const submit = (e) => {
    e?.preventDefault?.()
    if (effective.mode === 'empty') return
    onSubmit?.(effective)
  }

  return (
    <form
      role="search"
      aria-label="Forensic replay search"
      onSubmit={submit}
      style={{
        display:       'flex',
        flexDirection: 'column',
        gap:           10,
        padding:       '14px 16px',
        background:    'var(--os-panel)',
        border:        '1px solid var(--os-border)',
        borderLeft:    '3px solid var(--os-accent)',
        borderRadius:  'var(--os-radius)',
        fontFamily:    _MONO,
      }}
    >
      <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span style={{
          fontSize:       'var(--os-text-min)',
          letterSpacing:  '0.08em',
          textTransform:  'uppercase',
          color:          'var(--os-text-faint)',
        }}>
          Search by hash, grind id, device/counter, VHP token, or algorithm name
        </span>
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          autoComplete="off"
          spellCheck={false}
          placeholder="e.g. 250a8aae… · grind_20260505_v1 · 0xdeadbeef…/42 · VHP-2 · poseidon"
          aria-describedby="replay-search-detected"
          style={{
            fontFamily:   _MONO,
            // Stage 5.4 (Android responsive audit Finding A1): input
            // font-size must be ≥16px to suppress Chrome Android auto-
            // zoom-on-focus (which doesn't auto-zoom back and leaves
            // operator stuck at zoomed level). 13px label token is
            // correct for non-interactive text; interactive controls
            // need 16px floor on mobile.
            fontSize:     '16px',
            color:        'var(--os-text)',
            background:   'var(--os-bg)',
            border:       '1px solid var(--os-border)',
            borderRadius: 'var(--os-radius)',
            padding:      '10px 12px',
          }}
        />
      </label>

      <div
        id="replay-search-detected"
        style={{
          display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap',
        }}
      >
        <span style={{
          fontSize: 'var(--os-text-min)',
          color: 'var(--os-text-faint)',
        }}>Detected:</span>
        <DataBadge status={_MODE_BADGE[effective.mode] || 'dormant'} label={effective.label.toUpperCase()}/>
        <span style={{
          fontSize: 'var(--os-text-min)',
          color: 'var(--os-text-dim)',
          flex: 1, minWidth: 0,
        }}>{effective.reason}</span>
        <button
          type="submit"
          disabled={effective.mode === 'empty'}
          aria-label="Open detected mode"
          style={{
            fontFamily:    _MONO,
            fontSize:      'var(--os-text-min)',
            fontWeight:    600,
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
            padding:       '6px 14px',
            color:         effective.mode === 'empty'
              ? 'var(--os-text-faint)' : 'var(--os-accent)',
            background:    'transparent',
            border:        `1px solid ${effective.mode === 'empty'
              ? 'var(--os-border)' : 'var(--os-accent)'}`,
            borderRadius:  'var(--os-radius)',
            cursor:        effective.mode === 'empty' ? 'not-allowed' : 'pointer',
          }}
        >Open</button>
      </div>

      {/* Mode override — operator can force a different mode */}
      <div style={{
        display: 'flex', gap: 6, flexWrap: 'wrap',
        fontSize: 'var(--os-text-min)',
        color: 'var(--os-text-faint)',
      }}>
        <span style={{ alignSelf: 'center' }}>Force mode:</span>
        {['', 'session', 'gic', 'record', 'vhp', 'algorithm'].map(m => (
          <button
            key={m || 'auto'}
            type="button"
            onClick={() => setOverride(m)}
            aria-pressed={override === m}
            style={{
              fontFamily:    _MONO,
              fontSize:      'var(--os-text-min)',
              padding:       '3px 8px',
              color:         override === m ? 'var(--os-accent)' : 'var(--os-text-dim)',
              background:    override === m ? 'var(--os-accent-soft)' : 'transparent',
              border:        `1px solid ${override === m ? 'var(--os-accent)' : 'var(--os-border)'}`,
              borderRadius:  'var(--os-radius)',
              cursor:        'pointer',
            }}
          >{m || 'auto'}</button>
        ))}
      </div>
    </form>
  )
}

ReplaySearch.propTypes = {
  initialValue:    PropTypes.string,
  initialOverride: PropTypes.string,
  onSubmit:        PropTypes.func,
}
