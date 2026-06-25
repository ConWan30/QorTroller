import { useViewEyebrow } from '../design/Eyebrow'

// QorTroller — Partner·Pitch deck (tab 03 in the PROVING GROUND order).
//
// Renders the self-contained PROVING GROUND partner deck (frontend/public/qortroller-partner-pitch.html)
// full-bleed in an iframe. Round-3 re-skin: a scrolling page on the shared kit (forge palette +
// Archivo/Hanken/Martian + /pg-seal.js), NOT the old deck-stage.js slide deck — so the
// keyboard-shortcut/help machinery is gone. The deck carries its own GitHub "Verify the proofs →"
// stamp + footer. Named export per the App.jsx lazy adapter convention. No auth gate.
export function PartnerPitchView() {
  useViewEyebrow({
    num: '03', name: 'PARTNER · PITCH', status: 'OUTREACH', statusTone: 'amber',
    readouts: [{ label: 'SCOPE', value: 'MOAT·BOM·PARTNERS·ASK', tone: 'amber' }],
  })
  return (
    <div style={{ position: 'relative', flex: 1, minHeight: 0, width: '100%', background: '#060910' }}>
      <iframe
        src="/qortroller-partner-pitch.html"
        title="QorTroller — Partner Pitch"
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          border: 'none',
          background: '#060910',
        }}
        // Self-contained PROVING GROUND deck (forge palette + Archivo/Hanken/Martian + /pg-seal.js).
        // The deck carries its own "Verify the proofs →" stamp + footer, so no React overlay here.
        sandbox="allow-scripts allow-same-origin"
      />
    </div>
  )
}
