/**
 * Phase O5-PUBLIC-VIEWER — AlgorithmCatalog
 *
 * Renders the protocol's FROZEN-v1 cryptographic algorithm catalog
 * as a browsable grid. Every card shows: domain tag (byte sequence),
 * primitive name, preimage byte layout, output spec, Python source
 * file:line ref. This IS the protocol's published algorithm catalog —
 * any auditor can read it, find the Python implementation, and
 * confirm the JS verifier in vapi_verifier.js mirrors it.
 */
import { usePublicAlgorithms } from '../../api/publicForensic'

const _MONO = 'JetBrains Mono, ui-monospace, monospace'

export default function AlgorithmCatalog() {
  const { data, isLoading, error } = usePublicAlgorithms()

  if (isLoading) {
    return <div style={{ padding: 16, color: '#7a8a9b', fontFamily: _MONO, fontSize: 11 }}>
      Loading algorithm catalog…
    </div>
  }
  if (error) {
    return <div style={{ padding: 16, color: '#d65b78', fontFamily: _MONO, fontSize: 11 }}>
      Catalog unavailable: {String(error.message || error)}
    </div>
  }
  const tags = data?.tags || []

  return (
    <div data-vapi-algorithm-catalog="panel" style={{
      padding:    '12px',
      background: 'rgba(10,14,20,0.85)',
      border:     '1px solid rgba(240,168,104,0.25)',
      borderRadius: 4,
    }}>
      <div style={{
        fontFamily: _MONO, fontSize: 11, fontWeight: 700,
        color: '#f0a868', letterSpacing: '0.12em',
        marginBottom: 12, textTransform: 'uppercase',
      }}>
        FROZEN-v1 Algorithm Catalog · {tags.length} primitives
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 10 }}>
        {tags.map((t, i) => (
          <div key={i} data-vapi-algo-card={t.tag} style={{
            padding: 10,
            background: 'rgba(2,4,8,0.6)',
            border: '1px solid rgba(122,138,155,0.18)',
            borderRadius: 4,
          }}>
            <div style={{ fontFamily: _MONO, fontSize: 10, color: '#f0a868', fontWeight: 700, marginBottom: 4 }}>
              {t.tag}
            </div>
            <div style={{ fontFamily: _MONO, fontSize: 10, color: '#cc8855', marginBottom: 4 }}>
              {t.primitive}
            </div>
            <div style={{ fontFamily: _MONO, fontSize: 9, color: '#7a8a9b', marginBottom: 4, lineHeight: 1.4 }}>
              <strong style={{ color: '#7a8a9b' }}>preimage:</strong> {t.preimage}
            </div>
            <div style={{ fontFamily: _MONO, fontSize: 9, color: '#7a8a9b', marginBottom: 4 }}>
              <strong>output:</strong> {t.output}
            </div>
            <div style={{ fontFamily: _MONO, fontSize: 9, color: '#5bd6a3' }}>
              {t.py_module}::{t.py_function}
            </div>
          </div>
        ))}
      </div>
      <div style={{
        marginTop: 12, fontFamily: _MONO, fontSize: 10,
        color: '#7a8a9b', fontStyle: 'italic', lineHeight: 1.5,
      }}>
        {data?.discipline}
      </div>
    </div>
  )
}
