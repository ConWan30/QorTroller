/**
 * Stage 5.4 — Android responsive audit regression guards.
 *
 * Static-source guards locking the iPhone-15-walkthrough Stage 5.3
 * fixes + the Stage 5.4 Android-specific findings into CI so future
 * edits cannot reintroduce the auto-zoom-on-focus or tap-highlight
 * regressions. Same discipline pattern as
 * EvidenceOSHookContracts.test.jsx (T-OS-L4-4 static-source guard).
 *
 *   T-OS-A1  ReplaySearch input renders with fontSize >= 16px
 *            (Chrome Android auto-zoom-on-focus floor)
 *   T-OS-A2  QueueDetailPanel textarea renders with fontSize >= 16px
 *            (same Chrome Android floor; load-bearing because operator
 *            types ≥10-char audit reason on this control)
 *   T-OS-A3  index.html viewport meta contains viewport-fit=cover
 *            (Pixel gesture-nav safe-inset support)
 *   T-OS-A4  index.html global style contains
 *            -webkit-tap-highlight-color: transparent
 *            (Chrome Android tap-highlight suppression)
 */
import { describe, it, expect } from 'vitest'
import fs from 'fs'
import path from 'path'

const _root = path.resolve(__dirname, '..', '..')

function _read(rel) {
  return fs.readFileSync(path.resolve(_root, rel), 'utf8')
}

describe('Stage 5.4 — Android responsive regression guards', () => {

  it('T-OS-A1: ReplaySearch input fontSize is the 16px floor (Chrome Android auto-zoom guard)', () => {
    const src = _read('src/os/components/ReplaySearch.jsx')
    // The input element's inline style must contain fontSize: '16px'.
    // The 13px label token must NOT appear on the input style line.
    // Match the input opening + at least one line within the style block.
    const inputMatch = src.match(/<input[\s\S]+?style=\{\{([\s\S]+?)\}\}/m)
    expect(inputMatch, 'ReplaySearch input must exist').not.toBeNull()
    const inputStyle = inputMatch[1]
    expect(inputStyle).toMatch(/fontSize:\s*['"]16px['"]/)
    expect(inputStyle).not.toMatch(/fontSize:\s*['"]var\(--os-text-label\)['"]/)
  })

  it('T-OS-A2: QueueDetailPanel textarea fontSize is the 16px floor', () => {
    const src = _read('src/os/components/QueueDetailPanel.jsx')
    const textareaMatch = src.match(/<textarea[\s\S]+?style=\{\{([\s\S]+?)\}\}/m)
    expect(textareaMatch, 'QueueDetailPanel textarea must exist').not.toBeNull()
    const textareaStyle = textareaMatch[1]
    expect(textareaStyle).toMatch(/fontSize:\s*['"]16px['"]/)
    // Specifically reject the prior --os-text-base 12px usage on the textarea.
    expect(textareaStyle).not.toMatch(/fontSize:\s*['"]var\(--os-text-base\)['"]/)
  })

  it('T-OS-A3: index.html viewport meta includes viewport-fit=cover', () => {
    const src = _read('index.html')
    expect(src).toMatch(/<meta\s+name=["']viewport["']\s+content=["'][^"']*viewport-fit=cover/i)
  })

  it('T-OS-A4: index.html global style sets -webkit-tap-highlight-color transparent', () => {
    const src = _read('index.html')
    // Allow any whitespace + comments between the property and value
    expect(src).toMatch(/-webkit-tap-highlight-color:\s*transparent/i)
  })
})
