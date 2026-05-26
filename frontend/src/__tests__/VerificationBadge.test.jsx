/**
 * Phase 3 Path B — Gameplay Workflow Layer (Commit 3)
 * VerificationBadge component tests.
 *
 *   T-VB-1   computeVerdict: bridge offline OR no data → DORMANT
 *            (regression guard against fabricated VERIFIED when bridge
 *            is unreachable — same honesty class as T-OS-L4-3)
 *
 *   T-VB-2   computeVerdict: all four signals positive → VERIFIED
 *            (humanity ≥ 0.85 AND onchain===true AND vhp.valid===true
 *            AND enforcement_active===true)
 *
 *   T-VB-3   computeVerdict: onchain===null (RPC unavailable) → PENDING
 *            (CRITICAL distinction — null ≠ false; chain unreachable is
 *            not the same as chain saying "not eligible")
 *
 *   T-VB-4   computeVerdict: explicit-negative signals → UNVERIFIED
 *            (humanity<0.5 OR onchain===false OR vhp.valid===false)
 *
 *   T-VB-5   render: dormant badge shows "—" label, NOT a verdict word
 *
 *   T-VB-6   render: VERIFIED state shows the VERIFIED label + verdict
 *            data attribute (consumable by visual regression tools)
 *
 *   T-VB-7   render: click expands tray, exposes all four sub-signals
 *            with honest dashes for null inputs
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { VerificationBadge, computeVerdict } from '../components/VerificationBadge'

// ── computeVerdict pure-logic tests ───────────────────────────────────────────

describe('computeVerdict — pure verdict logic', () => {
  it('T-VB-1: bridge offline OR no data → DORMANT (no fabrication)', () => {
    expect(computeVerdict(null,     false)).toBe('DORMANT')
    expect(computeVerdict(undefined, false)).toBe('DORMANT')
    expect(computeVerdict({},        true)).toBe('DORMANT')
    // Even a perfect payload returns DORMANT when bridgeDown is true —
    // the bridge being unreachable is a higher-priority honesty signal.
    expect(computeVerdict({
      humanity_prob: 0.99,
      is_fully_eligible: { onchain: true },
      vhp_status: { valid: true },
      enforcement_active: true,
    }, true)).toBe('DORMANT')
  })

  it('T-VB-2: all four signals positive → VERIFIED', () => {
    expect(computeVerdict({
      humanity_prob: 0.92,
      is_fully_eligible: { onchain: true,  source: 'onchain' },
      vhp_status:        { valid: true,    expires_in_days: 42 },
      enforcement_active: true,
    }, false)).toBe('VERIFIED')
    // Exactly-at-threshold (0.85) must also be VERIFIED
    expect(computeVerdict({
      humanity_prob: 0.85,
      is_fully_eligible: { onchain: true },
      vhp_status:        { valid: true },
      enforcement_active: true,
    }, false)).toBe('VERIFIED')
  })

  it('T-VB-3: onchain===null (RPC unavailable) → PENDING, NOT UNVERIFIED', () => {
    // CRITICAL distinction: chain unreachable ≠ chain says "ineligible".
    // The endpoint distinguishes onchain={true|false|null}; the badge must too.
    const v = computeVerdict({
      humanity_prob: 0.92,
      is_fully_eligible: { onchain: null, source: 'unavailable' },
      vhp_status:        { valid: true },
      enforcement_active: true,
    }, false)
    expect(v).toBe('PENDING')
    expect(v).not.toBe('UNVERIFIED')
    // vhp_status absent (no VHP issued yet) is also PENDING, not UNVERIFIED.
    expect(computeVerdict({
      humanity_prob: 0.92,
      is_fully_eligible: { onchain: true },
      vhp_status:        null,
      enforcement_active: true,
    }, false)).toBe('PENDING')
  })

  it('T-VB-4: explicit-negative signals → UNVERIFIED', () => {
    // humanity < 0.5 alone is enough
    expect(computeVerdict({
      humanity_prob: 0.3,
      is_fully_eligible: { onchain: true },
      vhp_status:        { valid: true },
      enforcement_active: true,
    }, false)).toBe('UNVERIFIED')
    // chain says "not eligible" alone is enough (even with high humanity)
    expect(computeVerdict({
      humanity_prob: 0.95,
      is_fully_eligible: { onchain: false },
      vhp_status:        { valid: true },
      enforcement_active: true,
    }, false)).toBe('UNVERIFIED')
    // VHP expired alone is enough
    expect(computeVerdict({
      humanity_prob: 0.95,
      is_fully_eligible: { onchain: true },
      vhp_status:        { valid: false },
      enforcement_active: true,
    }, false)).toBe('UNVERIFIED')
  })
})

// ── Render tests ──────────────────────────────────────────────────────────────

describe('VerificationBadge — render honesty', () => {
  it('T-VB-5: dormant badge shows "—" label, NOT a verdict word', () => {
    render(<VerificationBadge data={null} bridgeDown={true} />)
    const pill = screen.getByTestId('verification-badge-pill')
    expect(pill.dataset.verdict).toBe('DORMANT')
    // Label is the dash — never VERIFIED/PENDING/UNVERIFIED in dormant state
    expect(pill.textContent).toMatch(/—/)
    expect(pill.textContent).not.toMatch(/VERIFIED/)
    expect(pill.textContent).not.toMatch(/PENDING/)
    expect(pill.textContent).not.toMatch(/UNVERIFIED/)
  })

  it('T-VB-6: VERIFIED state renders the VERIFIED label + data-verdict attr', () => {
    render(<VerificationBadge
      data={{
        humanity_prob: 0.92,
        is_fully_eligible: { onchain: true, source: 'onchain' },
        vhp_status:        { valid: true, expires_in_days: 42 },
        enforcement_active: true,
        host_signer_active: true,
      }}
      bridgeDown={false}
    />)
    const pill = screen.getByTestId('verification-badge-pill')
    expect(pill.dataset.verdict).toBe('VERIFIED')
    expect(pill.textContent).toMatch(/VERIFIED/)
    // Tray is collapsed by default
    expect(screen.queryByTestId('verification-badge-tray')).toBeNull()
  })

  it('T-VB-7: click expands tray, exposes all four sub-signals honestly', () => {
    const onExpanded = vi.fn()
    render(<VerificationBadge
      data={{
        humanity_prob: 0.92,
        // onchain=null exercises the "RPC unavailable" honest-dash render
        is_fully_eligible: { onchain: null, source: 'unavailable' },
        vhp_status:        { valid: true, expires_in_days: 42 },
        enforcement_active: true,
      }}
      bridgeDown={false}
      onExpandedChange={onExpanded}
    />)
    // Click to expand
    fireEvent.click(screen.getByTestId('verification-badge-pill'))
    expect(onExpanded).toHaveBeenCalledWith(true)
    const tray = screen.getByTestId('verification-badge-tray')
    const txt = tray.textContent
    // All four sub-signal labels render
    expect(txt).toMatch(/humanity/i)
    expect(txt).toMatch(/on-chain/i)
    expect(txt).toMatch(/vhp/i)
    expect(txt).toMatch(/enforcement/i)
    // Honest values: humanity formatted, vhp days, enforcement on,
    // on-chain shows RPC UNAVAILABLE (NOT fabricated "ELIGIBLE")
    expect(txt).toMatch(/0\.92/)
    expect(txt).toMatch(/42d/)
    expect(txt).toMatch(/ON/)
    expect(txt).toMatch(/RPC UNAVAILABLE/)
    expect(txt).not.toMatch(/✕ NOT ELIGIBLE/)  // null ≠ false
    // Click again to collapse
    fireEvent.click(screen.getByTestId('verification-badge-pill'))
    expect(screen.queryByTestId('verification-badge-tray')).toBeNull()
  })
})
