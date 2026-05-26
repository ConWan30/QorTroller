/**
 * VerificationBadge — Phase 3 Path B Gameplay Workflow Layer (Commit 3)
 *
 * Single-glance "am I verified?" surface for the gamer. Composes the four
 * sub-signals returned by GET /operator/player/session-status into one
 * tri-state pill (VERIFIED / PENDING / UNVERIFIED) with an optional
 * click-expand tray that reveals each underlying signal.
 *
 * Honesty contract:
 *   - bridge unreachable OR no data → "—" (faint), NEVER fabricates VERIFIED
 *   - on-chain `null` (RPC unavailable, not "false") → PENDING, NOT UNVERIFIED
 *     The endpoint distinguishes onchain={true|false|null}; the badge must too.
 *   - Mirrors the discipline of StatusStrip Blockers tile (T-OS-L4-3 / L4-4):
 *     dormant on missing data is the only correct render.
 *
 * Verdict thresholds (intentionally documented, not derived elsewhere):
 *   VERIFIED   = humanity_prob ≥ 0.85
 *              AND is_fully_eligible.onchain === true (NOT null)
 *              AND vhp_status.valid === true
 *              AND enforcement_active === true
 *   UNVERIFIED = humanity_prob < 0.5
 *              OR is_fully_eligible.onchain === false  (explicit chain "no")
 *              OR vhp_status.valid === false           (explicit expiry)
 *   PENDING    = everything else (signals partially unavailable)
 *   DORMANT    = no data at all (bridge offline, no device)
 *
 * Layout: top-center floating pill (z3, above twin + GIC constellation, below
 * eyebrow). NOT a corner panel — the in-code warning at GamerView.jsx:722
 * documents that the 4-corner composition was deliberate after the prior
 * ChipStrip experiment overcrowded it. This badge is intentionally narrow
 * (~140px) so it does not compete with the corner instruments.
 */
import { useState } from 'react'

// Verdict computation is pure + exported so tests can pin thresholds without
// rendering. Returns one of: VERIFIED | UNVERIFIED | PENDING | DORMANT.
export function computeVerdict(data, bridgeDown) {
  if (bridgeDown || !data) return 'DORMANT'

  const hp        = data.humanity_prob
  const onchain   = data.is_fully_eligible?.onchain
  const vhpValid  = data.vhp_status?.valid
  const enforce   = data.enforcement_active

  // Explicit-negative shortcuts → UNVERIFIED. Order matters: vhp_status===null
  // (no VHP issued yet) is NOT vhp.valid===false, so it never fires this branch.
  if (typeof hp === 'number' && hp < 0.5)  return 'UNVERIFIED'
  if (onchain === false)                   return 'UNVERIFIED'
  if (vhpValid === false)                  return 'UNVERIFIED'

  // All-green path requires every signal to be present + positive.
  const allGreen =
    typeof hp === 'number' && hp >= 0.85
    && onchain === true
    && vhpValid === true
    && enforce  === true
  if (allGreen) return 'VERIFIED'

  return 'PENDING'
}

const VERDICT_TONE = {
  VERIFIED:   { color: 'var(--chain, #5bd6a3)',          label: 'VERIFIED',   sigil: '✓' },
  PENDING:    { color: 'var(--accent-amber, #f4b860)',    label: 'PENDING',    sigil: '◐' },
  UNVERIFIED: { color: 'var(--status-blocked, #ff5577)',  label: 'UNVERIFIED', sigil: '✕' },
  DORMANT:    { color: 'var(--text-faint, #6a7480)',      label: '—',          sigil: '·' },
}

function SubSignal({ label, value, tone }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 12 }}>
      <span className="label" style={{ fontSize: 10, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-faint, #6a7480)' }}>
        {label}
      </span>
      <span className="mono" style={{ fontSize: 11, color: tone || 'var(--text-dim, #b8c1cc)' }}>{value}</span>
    </div>
  )
}

export function VerificationBadge({ data, bridgeDown = false, onExpandedChange }) {
  const [expanded, setExpanded] = useState(false)
  const verdict = computeVerdict(data, bridgeDown)
  const tone    = VERDICT_TONE[verdict]

  function toggle() {
    const next = !expanded
    setExpanded(next)
    if (onExpandedChange) onExpandedChange(next)
  }

  // Sub-signal display values — every "unavailable" path renders as the
  // honest "—" faint string, never a fabricated default. Each ?. is load-
  // bearing: a missing nested field MUST not crash the badge.
  const hp        = data?.humanity_prob
  const onchain   = data?.is_fully_eligible?.onchain
  const source    = data?.is_fully_eligible?.source
  const vhpValid  = data?.vhp_status?.valid
  const vhpDays   = data?.vhp_status?.expires_in_days
  const enforce   = data?.enforcement_active

  const hpDisplay      = typeof hp === 'number' ? hp.toFixed(2) : '—'
  const hpTone         = (typeof hp === 'number')
    ? (hp >= 0.85 ? 'var(--chain)' : hp >= 0.5 ? 'var(--accent-amber)' : 'var(--status-blocked)')
    : 'var(--text-faint)'

  const onchainDisplay = onchain === true ? '● ELIGIBLE'
    : onchain === false ? '✕ NOT ELIGIBLE'
    : `— ${source === 'unavailable' ? 'RPC UNAVAILABLE' : 'NO CHAIN'}`
  const onchainTone    = onchain === true ? 'var(--chain)'
    : onchain === false ? 'var(--status-blocked)'
    : 'var(--text-faint)'

  const vhpDisplay     = vhpValid === true  ? `VALID${typeof vhpDays === 'number' ? ` · ${vhpDays}d` : ''}`
    : vhpValid === false ? 'EXPIRED'
    : '—'
  const vhpTone        = vhpValid === true ? 'var(--chain)'
    : vhpValid === false ? 'var(--status-blocked)'
    : 'var(--text-faint)'

  const enforceDisplay = enforce === true ? '● ON' : enforce === false ? '○ OFF' : '—'
  const enforceTone    = enforce === true ? 'var(--chain)'
    : enforce === false ? 'var(--accent-amber)'
    : 'var(--text-faint)'

  return (
    <div
      data-testid="verification-badge"
      style={{
        position:      'absolute',
        top:           54,
        left:          '50%',
        transform:     'translateX(-50%)',
        zIndex:        4,
        display:       'flex',
        flexDirection: 'column',
        alignItems:    'center',
        pointerEvents: 'auto',
      }}
    >
      <button
        type="button"
        onClick={toggle}
        aria-label={`Verification status: ${tone.label}`}
        aria-expanded={expanded}
        data-testid="verification-badge-pill"
        data-verdict={verdict}
        style={{
          display:        'inline-flex',
          alignItems:     'center',
          gap:            10,
          padding:        '7px 16px',
          minWidth:       140,
          background:     `linear-gradient(180deg, rgba(8,18,24,0.78) 0%, rgba(5,10,15,0.92) 100%)`,
          border:         `1px solid ${tone.color}55`,
          borderRadius:   18,
          boxShadow:      `0 0 16px ${tone.color}26`,
          cursor:         'pointer',
          color:          tone.color,
          font:           '600 11px/1 var(--font-mono, ui-monospace, monospace)',
          letterSpacing:  '0.12em',
          textTransform:  'uppercase',
        }}
      >
        <span style={{ fontSize: 14, lineHeight: 1 }}>{tone.sigil}</span>
        <span>{tone.label}</span>
      </button>

      {expanded && (
        <div
          data-testid="verification-badge-tray"
          style={{
            marginTop:     8,
            minWidth:      260,
            padding:       '10px 14px',
            background:    `linear-gradient(180deg, rgba(8,18,24,0.85) 0%, rgba(5,10,15,0.95) 100%)`,
            border:        `1px solid var(--border-soft, rgba(255,255,255,0.08))`,
            borderRadius:  6,
            boxShadow:     `0 8px 24px rgba(0,0,0,0.4)`,
            display:       'grid',
            gap:           7,
          }}
        >
          <SubSignal label="humanity"    value={hpDisplay}      tone={hpTone} />
          <SubSignal label="on-chain"    value={onchainDisplay} tone={onchainTone} />
          <SubSignal label="vhp"         value={vhpDisplay}     tone={vhpTone} />
          <SubSignal label="enforcement" value={enforceDisplay} tone={enforceTone} />
        </div>
      )}
    </div>
  )
}
