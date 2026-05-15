/**
 * Phase O4-VPM-INT Stream C — VpmFilterChips component tests.
 *
 * T-VPM-C-CHIPS-1: renders 7 vpm_id chips + 7 visual_state chips
 *                  (6 FROZEN states + ALL)
 * T-VPM-C-CHIPS-2: selected chip carries active styling + click invokes
 *                  onSelect with the value
 * T-VPM-C-CHIPS-3: FROZEN 6-element VISUAL_STATES tuple matches the
 *                  Python-side canonical set
 */
import { describe, it, expect, vi } from 'vitest'
import { render, fireEvent } from '@testing-library/react'
import {
  VpmFilterChips,
  VPM_VISUAL_STATES_FROZEN,
  VPM_ID_OPTIONS,
  VISUAL_STATE_OPTIONS,
} from '../components/VpmFilterChips'


describe('VpmFilterChips', () => {
  it('T-VPM-C-CHIPS-1: renders all chip options', () => {
    const { container } = render(
      <VpmFilterChips
        vpmId=""
        visualState=""
        onVpmIdChange={() => {}}
        onVisualStateChange={() => {}}
      />
    )
    // 8 vpm_id chips (ALL + 7 compilers — Phase O5-MLGA Stage 4
    // added MLGA-SESSION-v1 as the 7th compiler).
    expect(VPM_ID_OPTIONS).toHaveLength(8)
    // 7 visual_state chips (ALL + 6 FROZEN states)
    expect(VISUAL_STATE_OPTIONS).toHaveLength(7)
    // Each chip rendered as a button with data-vpm-filter-chip attr
    const chips = container.querySelectorAll('[data-vpm-filter-chip]')
    expect(chips.length).toBe(15)
  })

  it('T-VPM-C-CHIPS-2: clicking a chip invokes onSelect', () => {
    const onVpmIdChange = vi.fn()
    const onVisualStateChange = vi.fn()
    const { container } = render(
      <VpmFilterChips
        vpmId=""
        visualState=""
        onVpmIdChange={onVpmIdChange}
        onVisualStateChange={onVisualStateChange}
      />
    )
    // Click HONESTY-BOARD-v1 chip
    const honestyBoard = container.querySelector('[data-vpm-filter-chip="HONESTY-BOARD-v1"]')
    expect(honestyBoard).not.toBeNull()
    fireEvent.click(honestyBoard)
    expect(onVpmIdChange).toHaveBeenCalledWith('HONESTY-BOARD-v1')

    // Click dry-run chip
    const dryRun = container.querySelector('[data-vpm-filter-chip="dry-run"]')
    expect(dryRun).not.toBeNull()
    fireEvent.click(dryRun)
    expect(onVisualStateChange).toHaveBeenCalledWith('dry-run')
  })

  it('T-VPM-C-CHIPS-3: VPM_VISUAL_STATES_FROZEN matches Python canonical set', () => {
    // Mirrors scripts/vpm_visual_grammar.py VISUAL_STATES tuple
    expect(VPM_VISUAL_STATES_FROZEN).toEqual([
      'live',
      'dry-run',
      'emulated',
      'frozen-disabled',
      'revoked',
      'unverified',
    ])
    expect(Object.isFrozen(VPM_VISUAL_STATES_FROZEN)).toBe(true)
  })
})
