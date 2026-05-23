import { useViewEyebrow } from '../design/Eyebrow'

// QorTroller — Reference (tab 06).
//
// Renders the standalone, brand-locked Reference codex
// (frontend/public/qortroller-reference.html) full-bleed in an iframe. The page
// is the single "what / how / forward" reference for QorTroller: identity
// (V.A.P.I. category + sovereignty thesis), function (PITL stack, 228-byte PoAC
// wire format, humanity formula, GIC chain, operator fleet, consent, on-chain
// anchoring, the FROZEN-v1 primitive family, hardware), and forward roadmap.
//
// The page is self-contained (local Syne + JetBrains Mono, no CDN) and is the
// brand-locked SOURCE OF TRUTH that a Claude-Design pass enhances with motion
// (see docs/qortroller-reference-claude-design-prompt.md). The enhanced file
// drops back in at the same /qortroller-reference.html path — no code change.
//
// Named export per the App.jsx lazy adapter convention. No auth gate.
export function ReferenceView() {
  // v2 · item A — eyebrow spine (full-bleed .qt-stage iframe view).
  useViewEyebrow({
    num: '06', name: 'REFERENCE · CODEX', status: 'CANON', statusTone: 'chain',
    readouts: [{ label: 'SECTIONS', value: '11', tone: 'chain' }, { label: 'SCOPE', value: 'WHAT·HOW·FORWARD', tone: 'amber' }],
  })
  return (
    <div style={{ position: 'relative', flex: 1, minHeight: 0, width: '100%', background: '#04060a' }}>
      <iframe
        src="/qortroller-reference.html"
        title="QorTroller — Reference"
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          border: 'none',
          background: '#04060a',
        }}
        // Self-contained page with inline <style>; scripts allowed for the
        // Claude-Design motion pass (scroll-reveals, byte assembly, etc.).
        sandbox="allow-scripts allow-same-origin"
      />
    </div>
  )
}
