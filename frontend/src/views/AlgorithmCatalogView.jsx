/**
 * Phase O5-PUBLIC-VIEWER Stage 5 — Algorithm Catalog standalone route
 *
 * Public route at /algorithms. Reuses the AlgorithmCatalog component
 * but as a standalone page (no session context required). Reference
 * documentation for journalists, auditors, and partners browsing
 * the protocol's FROZEN-v1 cryptographic algorithm family.
 */
import { Link } from 'react-router-dom'
import AlgorithmCatalog from '../components/public/AlgorithmCatalog'

const _MONO = 'JetBrains Mono, ui-monospace, monospace'
const _ACCENT = '#f0a868'

export default function AlgorithmCatalogView() {
  return (
    <div style={{ minHeight: '100dvh', background: '#020408', color: '#ffe8d4', overflow: 'auto' }}>
      <div style={{
        padding: '16px 24px', background: 'rgba(2,4,8,0.9)',
        borderBottom: `1px solid ${_ACCENT}`, display: 'flex', gap: 16, alignItems: 'center',
      }}>
        <Link to="/" style={{ fontFamily: _MONO, fontSize: 11, color: _ACCENT, textDecoration: 'none' }}>← QorTroller</Link>
        <div style={{ fontFamily: _MONO, fontSize: 11, fontWeight: 700, color: _ACCENT, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
          FROZEN-v1 Cryptographic Algorithm Catalog
        </div>
        <div style={{ flex: 1 }} />
        <Link to="/explorer" style={{ fontFamily: _MONO, fontSize: 11, color: '#7a8a9b' }}>Explorer →</Link>
      </div>
      <div style={{ padding: '24px' }}>
        <div style={{ marginBottom: 18, fontFamily: _MONO, fontSize: 11, color: '#7a8a9b', lineHeight: 1.7 }}>
          The complete QorTroller (V.A.P.I. reference implementation) cryptographic primitive catalog. Every
          domain tag listed below has a corresponding Python implementation
          AND a browser-side verifier in <code style={{ color: '#5bd6a3' }}>
          frontend/src/crypto/vapi_verifier.js</code>. Each one produces a
          SHA-256 output reproducible in any modern browser via Web Crypto.
          External auditors can clone the repo, find the Python algorithm
          at the listed file:line, and confirm the JS verifier mirrors it
          byte-for-byte against pinned test vectors.
        </div>
        <AlgorithmCatalog />
      </div>
    </div>
  )
}
