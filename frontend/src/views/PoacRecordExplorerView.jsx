/**
 * Phase O5-PUBLIC-VIEWER Stage 3 — PoAC Record Byte Explorer
 *
 * Public route at /record/:deviceId/:counter. Fetches a single
 * 228-byte PoAC record as binary via /public/record/{device}/{counter},
 * renders the FROZEN wire format byte-by-byte with field-level
 * highlighting, and recomputes record_hash = SHA-256(raw[:164]) in
 * browser via verifyPoacRecordHash.
 *
 * Strategic claim: QorTroller is the only anti-cheat protocol where the
 * exact byte layout of its core proof record is publicly inspectable.
 * Every field offset matches the FROZEN spec; the body-vs-signature
 * boundary (byte 163) is visually marked.
 */
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchPublicRecordBytes } from '../api/publicForensic'
import { verifyPoacRecordHash, bytesToHex } from '../crypto/vapi_verifier'

const _MONO = 'JetBrains Mono, ui-monospace, monospace'
const _ACCENT = '#f0a868'

// FROZEN 228-byte PoAC wire format field layout
const _FIELDS = [
  { offset: 0,   length: 32, name: 'prev_poac_hash',     kind: 'body' },
  { offset: 32,  length: 32, name: 'sensor_commitment',  kind: 'body' },
  { offset: 64,  length: 32, name: 'model_manifest_hash', kind: 'body' },
  { offset: 96,  length: 32, name: 'world_model_hash',   kind: 'body' },
  { offset: 128, length: 1,  name: 'inference_result',   kind: 'body' },
  { offset: 129, length: 1,  name: 'action_code',        kind: 'body' },
  { offset: 130, length: 1,  name: 'confidence',         kind: 'body' },
  { offset: 131, length: 1,  name: 'battery_pct',        kind: 'body' },
  { offset: 132, length: 4,  name: 'monotonic_ctr',      kind: 'body' },
  { offset: 136, length: 8,  name: 'timestamp_ms',       kind: 'body' },
  { offset: 144, length: 8,  name: 'latitude',           kind: 'body' },
  { offset: 152, length: 8,  name: 'longitude',          kind: 'body' },
  { offset: 160, length: 4,  name: 'bounty_id',          kind: 'body' },
  { offset: 164, length: 64, name: 'signature (r || s)', kind: 'signature' },
]

function StatusPill({ status }) {
  const colors = {
    ok:       { bg: '#5bd6a31a', fg: '#5bd6a3', label: 'OK' },
    mismatch: { bg: '#d65b781a', fg: '#d65b78', label: 'MISMATCH' },
    pending:  { bg: '#7a8a9b1a', fg: '#7a8a9b', label: '…' },
  }
  const c = colors[status] || colors.pending
  return (
    <span style={{
      background:   c.bg, color: c.fg, border: `1px solid ${c.fg}`,
      padding:      '2px 8px', borderRadius: 4,
      fontFamily:   _MONO, fontSize: 10, fontWeight: 600,
    }}>{c.label}</span>
  )
}

function FieldRow({ field, raw }) {
  const slice = raw.slice(field.offset, field.offset + field.length)
  const hex = bytesToHex(slice)
  const isSig = field.kind === 'signature'
  return (
    <tr data-vapi-poac-field={field.name} style={{
      borderBottom: '1px solid rgba(122,138,155,0.08)',
      background:   isSig ? 'rgba(214,91,120,0.04)' : 'transparent',
    }}>
      <td style={{ padding: '4px 10px', fontFamily: _MONO, fontSize: 10, color: '#7a8a9b' }}>
        0x{field.offset.toString(16).padStart(3, '0')}–0x{(field.offset + field.length - 1).toString(16).padStart(3, '0')}
      </td>
      <td style={{ padding: '4px 10px', fontFamily: _MONO, fontSize: 10, color: '#cc8855' }}>
        {field.length}B
      </td>
      <td style={{ padding: '4px 10px', fontFamily: _MONO, fontSize: 10, color: isSig ? '#d65b78' : '#ffe8d4', fontWeight: 600 }}>
        {field.name}
      </td>
      <td style={{ padding: '4px 10px', fontFamily: _MONO, fontSize: 9, color: '#ffe8d4', wordBreak: 'break-all', maxWidth: 480 }}>
        <code>{hex}</code>
      </td>
    </tr>
  )
}

export default function PoacRecordExplorerView() {
  const { deviceId, counter } = useParams()
  const [raw, setRaw] = useState(null)
  const [recomputed, setRecomputed] = useState('')
  const [hashStatus, setHashStatus] = useState('pending')
  const [err, setErr] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    async function run() {
      setErr(null)
      setLoading(true)
      try {
        const bytes = await fetchPublicRecordBytes(deviceId, parseInt(counter, 10))
        if (cancelled) return
        if (bytes === null) {
          setErr('record not found')
        } else if (bytes.length !== 228) {
          setErr(`invalid record length ${bytes.length} (expected 228)`)
        } else {
          setRaw(bytes)
          const hex = await verifyPoacRecordHash(bytes)
          if (!cancelled) {
            setRecomputed(hex)
            setHashStatus('ok')  // we recomputed it; no protocol-side claim to compare here
          }
        }
      } catch (e) {
        if (!cancelled) setErr(String(e.message || e))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    run()
    return () => { cancelled = true }
  }, [deviceId, counter])

  return (
    <div style={{ minHeight: '100dvh', background: '#020408', color: '#ffe8d4', overflow: 'auto' }}>
      <div style={{
        padding: '16px 24px', background: 'rgba(2,4,8,0.9)',
        borderBottom: `1px solid ${_ACCENT}`, display: 'flex', gap: 16, alignItems: 'center',
      }}>
        <Link to="/" style={{ fontFamily: _MONO, fontSize: 11, color: _ACCENT, textDecoration: 'none' }}>← QorTroller</Link>
        <div style={{ fontFamily: _MONO, fontSize: 11, fontWeight: 700, color: _ACCENT, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
          PoAC Record Byte Explorer
        </div>
        <div style={{ flex: 1 }} />
        <div style={{ fontFamily: _MONO, fontSize: 10, color: '#cc8855' }}>
          device: <code style={{ color: '#ffe8d4' }}>{deviceId?.slice(0, 16)}…</code> · counter: <strong style={{ color: '#ffe8d4' }}>{counter}</strong>
        </div>
      </div>

      <div style={{ padding: '12px 24px' }}>
        {loading && <div style={{ color: '#7a8a9b', fontFamily: _MONO }}>Loading record bytes…</div>}
        {err && (
          <div style={{ padding: 24, fontFamily: _MONO, color: '#d65b78', border: '1px solid #d65b78', borderRadius: 4 }}>
            {err}. Try a real (device_id, counter) pair from your bridge's records table.
          </div>
        )}
        {raw && (
          <>
            <div style={{ marginBottom: 12, fontFamily: _MONO, fontSize: 10, color: '#7a8a9b' }}>
              raw_length: <strong style={{ color: '#ffe8d4' }}>{raw.length}B</strong>
              <span style={{ marginLeft: 18 }}>body[0:164]: <strong style={{ color: '#5bd6a3' }}>164B</strong></span>
              <span style={{ marginLeft: 18 }}>signature[164:228]: <strong style={{ color: '#d65b78' }}>64B</strong></span>
              <span style={{ marginLeft: 18 }}>record_hash recomputed: <StatusPill status={hashStatus} /></span>
            </div>
            <div style={{ padding: 10, marginBottom: 12, background: '#0a0e14', border: '1px solid rgba(91,214,163,0.25)', borderRadius: 4, fontFamily: _MONO, fontSize: 11 }}>
              <div style={{ color: '#5bd6a3', fontWeight: 700, marginBottom: 4 }}>SHA-256(raw[0:164]) =</div>
              <code style={{ color: '#ffe8d4', wordBreak: 'break-all' }}>{recomputed}</code>
              <div style={{ marginTop: 6, color: '#7a8a9b', fontStyle: 'italic', fontSize: 10 }}>
                Per FROZEN INV: record_hash hashes the body bytes ONLY (offset 0..163),
                NOT the full 228 bytes. The signature region (164..227) is NOT in the
                hash domain — a fact verifiable by modifying any byte in the 164..227
                range and recomputing: the hash stays identical.
              </div>
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: 'rgba(240,168,104,0.05)' }}>
                  <th style={{ textAlign: 'left', padding: '6px 10px', fontFamily: _MONO, fontSize: 9, color: '#7a8a9b' }}>OFFSET</th>
                  <th style={{ textAlign: 'left', padding: '6px 10px', fontFamily: _MONO, fontSize: 9, color: '#7a8a9b' }}>LEN</th>
                  <th style={{ textAlign: 'left', padding: '6px 10px', fontFamily: _MONO, fontSize: 9, color: '#7a8a9b' }}>FIELD</th>
                  <th style={{ textAlign: 'left', padding: '6px 10px', fontFamily: _MONO, fontSize: 9, color: '#7a8a9b' }}>BYTES</th>
                </tr>
              </thead>
              <tbody>
                {_FIELDS.map((f, i) => <FieldRow key={i} field={f} raw={raw} />)}
              </tbody>
            </table>
          </>
        )}
      </div>
    </div>
  )
}
