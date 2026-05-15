/**
 * Mythos audit fix (post-/goal 2026-05-15) — App-level mock indicator.
 *
 * Surfaces `sessionStorage.__vapiMockActive` as a thin amber banner at
 * the very top of every tab (Gamer / Developer / Manufacturer / BRP /
 * Marketplace / VPM Registry). Previously the banner only rendered in
 * GamerView, so operators on other tabs had no signal that they were
 * looking at fabricated data.
 *
 * The flag clears automatically on the next successful fetch via the
 * companion client.js fix that calls deactivateMock() inside apiGet()
 * + apiPost() success paths. This banner just observes the flag and
 * disappears the moment it flips.
 *
 * Polling: 2-second cadence, identical to the prior GamerView impl,
 * so flips are visually instantaneous from the operator's POV without
 * burning render cycles.
 */
import { useEffect, useState } from 'react'
import { isMockActive } from '../api/mockBridge'

export default function GlobalMockBanner() {
  const [active, setActive] = useState(isMockActive())
  useEffect(() => {
    const id = setInterval(() => setActive(isMockActive()), 2000)
    return () => clearInterval(id)
  }, [])

  if (!active) return null
  return (
    <div
      data-vapi-mock-banner="active"
      style={{
        position:       'fixed',
        top:            0,
        left:           0,
        right:          0,
        zIndex:         9999,
        padding:        '6px 12px',
        background:     'rgba(240,168,104,0.18)',
        color:          '#f0a868',
        fontFamily:     'JetBrains Mono, ui-monospace, monospace',
        fontSize:       11,
        fontWeight:     600,
        letterSpacing:  '0.08em',
        textAlign:      'center',
        borderBottom:   '1px solid rgba(240,168,104,0.45)',
        pointerEvents:  'none',
        textTransform:  'uppercase',
      }}
    >
      ⚠ MOCK DATA — BRIDGE OFFLINE / SLOW — values are fabricated,
      not live state. Banner auto-clears on next successful bridge
      response.
    </div>
  )
}
