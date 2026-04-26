// Phase 236-VAME — frontend commitment validation
//
// Recomputes the SHA-256 commitment from response body bytes and compares to
// the X-VAME-Commitment sidecar header. Mismatch = VAME_INTEGRITY_FAILURE
// (logged + counted; does NOT throw, so transient/legacy responses still flow).
//
// Formula MUST match bridge/vapi_bridge/vame.py exactly:
//   commitment = SHA-256(
//       "VAPI-VAME-v1"            (12 bytes ASCII)
//       || chain_head_16b         (16 bytes, hex-decoded from X-VAME-Chain-Head)
//       || ts_ns_be(8)            (8 bytes BE uint64, from X-VAME-TS-NS)
//       || endpoint_bytes         (utf-8, from X-VAME-Endpoint)
//       || body_bytes             (raw response body bytes, BEFORE JSON parse)
//   )

const _VAME_TAG = new TextEncoder().encode('VAPI-VAME-v1')
const _VAME_FAILURE_KEY = '__vapiVameFailures'

export function vameFailureCount() {
  try { return parseInt(sessionStorage.getItem(_VAME_FAILURE_KEY) || '0', 10) }
  catch { return 0 }
}

function _bumpFailure() {
  try {
    const n = vameFailureCount() + 1
    sessionStorage.setItem(_VAME_FAILURE_KEY, String(n))
  } catch {}
}

function _hexToBytes(hex) {
  if (!hex || typeof hex !== 'string') return new Uint8Array(0)
  const clean = hex.replace(/^0x/i, '')
  if (clean.length % 2 !== 0) return new Uint8Array(0)
  const out = new Uint8Array(clean.length / 2)
  for (let i = 0; i < out.length; i++) {
    out[i] = parseInt(clean.substr(i * 2, 2), 16)
  }
  return out
}

function _bytesToHex(bytes) {
  return Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('')
}

function _u64BE(n) {
  // ts_ns is up to 2^63 — JavaScript Number loses precision above 2^53.
  // Use BigInt for the full 8-byte big-endian encoding.
  const buf = new Uint8Array(8)
  let v = BigInt(n)
  for (let i = 7; i >= 0; i--) {
    buf[i] = Number(v & 0xffn)
    v >>= 8n
  }
  return buf
}

function _concat(...arrays) {
  let total = 0
  for (const a of arrays) total += a.length
  const out = new Uint8Array(total)
  let off = 0
  for (const a of arrays) { out.set(a, off); off += a.length }
  return out
}

/**
 * Recompute the VAME commitment from sidecar headers + raw body bytes.
 * Returns the 64-char hex commitment, or null if inputs were unusable.
 */
export async function recomputeVameCommitment(headers, endpoint, bodyBytes) {
  const chainHeadHex = headers.get('X-VAME-Chain-Head')
  const tsNsStr      = headers.get('X-VAME-TS-NS')
  if (!chainHeadHex || !tsNsStr) return null

  const chainHead = _hexToBytes(chainHeadHex)
  if (chainHead.length !== 16) return null

  const tsNsBE   = _u64BE(tsNsStr)
  const epBytes  = new TextEncoder().encode(endpoint || '')
  const input    = _concat(_VAME_TAG, chainHead, tsNsBE, epBytes, bodyBytes)

  const digest   = await crypto.subtle.digest('SHA-256', input)
  return _bytesToHex(new Uint8Array(digest))
}

/**
 * Validate the X-VAME-Commitment header against locally recomputed value.
 *
 * Returns:
 *   { status: 'OK' }                     — commitment matched
 *   { status: 'NO_VAME' }                — endpoint did not stamp (legacy / pre-236)
 *   { status: 'MISMATCH', expected, got } — commitment mismatch (logged + counted)
 *
 * Does NOT throw — caller decides what to do (log, ignore, surface to UI).
 */
export async function validateVame(headers, endpoint, bodyBytes) {
  const stamped = headers.get('X-VAME-Commitment')
  if (!stamped) return { status: 'NO_VAME' }

  const expected = await recomputeVameCommitment(headers, endpoint, bodyBytes)
  if (!expected) return { status: 'NO_VAME' }

  if (stamped.toLowerCase() === expected.toLowerCase()) {
    return { status: 'OK' }
  }

  _bumpFailure()
  // Soft warning to the dev console — never throws, never blocks response flow.
  // Aggregate count is in sessionStorage[__vapiVameFailures] for the UI banner.
  // eslint-disable-next-line no-console
  console.warn('[VAME] integrity mismatch on', endpoint,
    '\n  stamped =', stamped,
    '\n  computed =', expected)
  return { status: 'MISMATCH', expected, got: stamped }
}
