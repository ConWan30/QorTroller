/**
 * Phase O5-PUBLIC-VIEWER — PoacBodyHasher
 *
 * Fetches a 228-byte PoAC record via /public/record/{device}/{counter},
 * renders the byte-layout table (body bytes 0-163 / signature 164-227),
 * and lets the operator click "Re-hash bytes [0:164]" to recompute the
 * record_hash in the browser via verifyPoacRecordHash.
 *
 * The exclusivity claim made visible: VAPI's hash is SHA-256 of the
 * BODY ONLY, not the full 228 bytes — and you can see this for
 * yourself in any browser.
 */
import { useState } from 'react'
import { fetchPublicRecordBytes } from '../../api/publicForensic'
import { verifyPoacRecordHash, bytesToHex } from '../../crypto/vapi_verifier'

const _MONO = 'JetBrains Mono, ui-monospace, monospace'

export default function PoacBodyHasher() {
  const [deviceId, setDeviceId] = useState('')
  const [counter, setCounter] = useState(0)
  const [raw, setRaw] = useState(null)
  const [recomputed, setRecomputed] = useState('')
  const [err, setErr] = useState(null)
  const [loading, setLoading] = useState(false)

  async function onFetch() {
    setErr(null)
    setRecomputed('')
    setRaw(null)
    setLoading(true)
    try {
      const bytes = await fetchPublicRecordBytes(deviceId, counter)
      if (bytes === null) {
        setErr('record not found')
      } else {
        setRaw(bytes)
      }
    } catch (e) {
      setErr(String(e.message || e))
    } finally {
      setLoading(false)
    }
  }

  async function onHash() {
    if (!raw) return
    setErr(null)
    try {
      const hex = await verifyPoacRecordHash(raw)
      setRecomputed(hex)
    } catch (e) {
      setErr(String(e.message || e))
    }
  }

  return (
    <div data-vapi-poac-hasher="panel" style={{
      padding:    '12px',
      background: 'rgba(10,14,20,0.85)',
      border:     '1px solid rgba(240,168,104,0.25)',
      borderRadius: 4,
    }}>
      <div style={{
        fontFamily: _MONO, fontSize: 11, fontWeight: 700,
        color: '#f0a868', letterSpacing: '0.12em',
        marginBottom: 8, textTransform: 'uppercase',
      }}>
        PoAC Record Body Hasher · SHA-256(raw[:164])
      </div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 8, alignItems: 'center' }}>
        <input
          data-vapi-poac-input="device-id"
          placeholder="device_id"
          value={deviceId}
          onChange={e => setDeviceId(e.target.value)}
          style={{ flex: 1, padding: 6, fontFamily: _MONO, fontSize: 10, background: '#020408', color: '#ffe8d4', border: '1px solid #1a0e05' }}
        />
        <input
          data-vapi-poac-input="counter"
          type="number"
          placeholder="counter"
          value={counter}
          onChange={e => setCounter(parseInt(e.target.value || '0', 10))}
          style={{ width: 100, padding: 6, fontFamily: _MONO, fontSize: 10, background: '#020408', color: '#ffe8d4', border: '1px solid #1a0e05' }}
        />
        <button
          onClick={onFetch}
          disabled={loading || !deviceId}
          style={{
            padding: '6px 14px', fontFamily: _MONO, fontSize: 10,
            background: '#f0a86833', color: '#f0a868', border: '1px solid #f0a868',
            cursor: loading || !deviceId ? 'not-allowed' : 'pointer',
          }}
        >
          {loading ? 'Loading…' : 'Fetch'}
        </button>
        <button
          onClick={onHash}
          disabled={!raw}
          style={{
            padding: '6px 14px', fontFamily: _MONO, fontSize: 10,
            background: raw ? '#5bd6a333' : '#33333333',
            color: raw ? '#5bd6a3' : '#7a8a9b',
            border: `1px solid ${raw ? '#5bd6a3' : '#7a8a9b'}`,
            cursor: raw ? 'pointer' : 'not-allowed',
          }}
        >
          Hash body[0:164]
        </button>
      </div>
      {err && (
        <div style={{ color: '#d65b78', fontFamily: _MONO, fontSize: 10, marginBottom: 6 }}>
          {err}
        </div>
      )}
      {raw && (
        <div style={{ fontFamily: _MONO, fontSize: 10, color: '#7a8a9b', lineHeight: 1.5 }}>
          <div>raw_length: {raw.length} bytes</div>
          <div>body[0:164] first 16 hex: <code style={{ color: '#ffe8d4' }}>{bytesToHex(raw.slice(0, 16))}…</code></div>
          <div>signature[164:228] first 16 hex: <code style={{ color: '#cc8855' }}>{bytesToHex(raw.slice(164, 180))}…</code></div>
          {recomputed && (
            <div style={{ marginTop: 8, color: '#5bd6a3' }}>
              record_hash recomputed: <code>{recomputed}</code>
            </div>
          )}
        </div>
      )}
      <div style={{ marginTop: 8, fontFamily: _MONO, fontSize: 10, color: '#7a8a9b', lineHeight: 1.5, fontStyle: 'italic' }}>
        Per FROZEN INV: record_hash = SHA-256(raw[:164]) — body only, NOT
        the full 228 bytes. Signature bytes [164:228] are NOT in the
        hash domain.
      </div>
    </div>
  )
}
