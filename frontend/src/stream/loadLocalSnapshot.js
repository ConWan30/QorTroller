/**
 * PKG-UI-04 React data path — observe CLI-written JSON only.
 *
 * noMock contract (mirrors CLI offline shell):
 *   missing / failed fetch  →  UNKNOWN empty models (never fabricates LIVE)
 *   never calls bridge /agent or /operator
 *   never invents crop counts, biometrics, or signing material
 */

import {
  STREAM_VIEW_SCHEMA,
  STATUS_SNAPSHOT_SCHEMA,
  RECEIPT_REVEAL_SCHEMA,
  BIRTH_CEREMONY_SCHEMA,
} from './streamTokens'

/** Default base under Vite middleware (see vite.config.js /stream-ui). */
export const DEFAULT_STREAM_UI_BASE = '/stream-ui'

/**
 * Pure: map raw stream JSON to a safe on-screen model.
 * Missing/invalid → UNKNOWN presence; fabricated_liveness always false.
 */
export function normalizeStreamModel(raw) {
  if (!raw || typeof raw !== 'object') {
    return emptyStreamModel('missing')
  }
  const on = raw.on_screen && typeof raw.on_screen === 'object' ? raw.on_screen : {}
  const fclass = on.freshness_class || 'UNKNOWN'
  // Hard rail: never promote to LIVE unless explicit freshness_class === LIVE
  const tone = on.presence_tone || (fclass === 'LIVE' ? 'live' : 'unknown')
  const safeTone = fclass === 'LIVE' ? tone : (tone === 'live' ? 'unknown' : tone)
  return {
    schema: raw.schema || STREAM_VIEW_SCHEMA,
    surface: 'stream',
    on_screen: {
      presence_line: on.presence_line || 'witness state unknown',
      presence_tone: fclass === 'LIVE' ? (safeTone === 'live' ? 'live' : safeTone) : (fclass === 'FRESH' ? 'recent' : fclass === 'STALE' ? 'quiet' : fclass === 'EMPTY' ? 'empty' : 'unknown'),
      node_state: on.node_state || '—',
      freshness_class: fclass,
      session_id_display: on.session_id_display || on.session_label || null,
      session_label: on.session_label || null,
      pack: on.pack || null,
      f_t66b1_disclosure_visible: on.f_t66b1_disclosure_visible !== false,
    },
    deliberately_absent: Array.isArray(raw.deliberately_absent) ? raw.deliberately_absent : [],
    novelty: raw.novelty || 'witness_respiration',
    mock: false,
    fabricated_liveness: false,
    signing_material_present: false,
    consent_authority: false,
    _source: 'ok',
  }
}

export function emptyStreamModel(reason = 'missing') {
  return {
    schema: STREAM_VIEW_SCHEMA,
    surface: 'stream',
    on_screen: {
      presence_line: 'witness state unknown',
      presence_tone: 'unknown',
      node_state: '—',
      freshness_class: 'UNKNOWN',
      session_id_display: null,
      session_label: null,
      pack: null,
      f_t66b1_disclosure_visible: true,
    },
    deliberately_absent: [
      'crop_counts', 'fps', 'raw_biometric', 'grind_bar',
      'green_check_theater', 'mock_liveness', 'keys', 'consent',
    ],
    novelty: 'witness_respiration',
    mock: false,
    fabricated_liveness: false,
    signing_material_present: false,
    consent_authority: false,
    _source: reason,
  }
}

export function emptyStatusSnapshot(reason = 'missing') {
  return {
    schema: STATUS_SNAPSHOT_SCHEMA,
    node_state: null,
    freshness_class: 'UNKNOWN',
    witness_live: false,
    mock: false,
    fabricated_liveness: false,
    signing_material_present: false,
    consent_authority: false,
    _source: reason,
  }
}

export function emptyReceiptReveal(reason = 'missing') {
  return {
    schema: RECEIPT_REVEAL_SCHEMA,
    session_label: null,
    pack: null,
    choreography: [
      { stage: 'SETTLE', ms: 400, copy: 'session closed -- sealing the pack' },
      { stage: 'SURFACES', ms: 800, copy: 'presence + authorship + state' },
      { stage: 'HONESTY', ms: 500, copy: 'known gaps disclosed, never hidden' },
      { stage: 'SHARE_SPLIT', ms: 600, copy: 'LOCAL full stays here; SHARE postcard is redacted for strangers' },
    ],
    surfaces: {},
    f_t66b1: {
      code: 'F-T66B-1',
      status: 'OPEN',
      visible_on_local: true,
      visible_on_share: true,
      line: 'incomplete -- not hidden. Zero-false-read holds.',
    },
    local: { surface: 'LOCAL', body_text: '', redaction: 'none' },
    share: { surface: 'SHARE', body_text: '', redaction: 'qortroller-share-v1', shows_crop_counts: false },
    mock: false,
    signing_material_present: false,
    consent_authority: false,
    _source: reason,
    _present: false,
  }
}

export function emptyCeremonyMap(reason = 'missing') {
  return {
    schema: BIRTH_CEREMONY_SCHEMA,
    node_state: null,
    stages: [],
    ceremony_complete: false,
    feel_summary: 'Witness-node birth map unavailable (no ceremony.json).',
    signing_material_present: false,
    _source: reason,
    _present: false,
  }
}

/**
 * Surface mode state machine (pure).
 * BOOT → EMPTY | CEREMONY | STREAM | RECEIPT
 */
export function classifyStreamSurfaceMode({ stream, ceremony, receipt }) {
  if (receipt && receipt._present !== false && receipt.session_label) {
    return 'RECEIPT'
  }
  if (stream && stream.on_screen) {
    const f = stream.on_screen.freshness_class
    const node = stream.on_screen.node_state
    if (f === 'LIVE' || f === 'FRESH' || (node && node !== '—' && node !== 'UNPROVISIONED' && f !== 'UNKNOWN')) {
      // Prefer STREAM when we have any non-empty witness reading
      if (f !== 'UNKNOWN' || (node && node !== '—')) {
        // Ceremony incomplete + EMPTY/UNKNOWN may still show ceremony map
        if (ceremony && ceremony._present !== false && ceremony.ceremony_complete === false
            && (f === 'EMPTY' || f === 'UNKNOWN')
            && (!node || node === 'UNPROVISIONED' || node === 'PROVISIONING' || node === 'FIRST_PROOF_PENDING')) {
          return 'CEREMONY'
        }
        if (f !== 'UNKNOWN' || (node && !['—', 'UNPROVISIONED'].includes(node))) {
          return 'STREAM'
        }
      }
    }
  }
  if (ceremony && ceremony._present !== false && ceremony.ceremony_complete === false
      && Array.isArray(ceremony.stages) && ceremony.stages.length > 0) {
    return 'CEREMONY'
  }
  if (stream && stream._source === 'ok') return 'STREAM'
  return 'EMPTY'
}

async function fetchJson(url, fetchImpl) {
  const r = await fetchImpl(url, { cache: 'no-store' })
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}

/**
 * Load all stream UI snapshots from a base URL (CLI-written dir).
 * Inject `fetchImpl` for tests. Fail-open to UNKNOWN empties — never LIVE.
 */
export async function loadStreamSnapshots(baseUrl = DEFAULT_STREAM_UI_BASE, fetchImpl = globalThis.fetch) {
  const base = String(baseUrl || DEFAULT_STREAM_UI_BASE).replace(/\/$/, '')
  const out = {
    stream: emptyStreamModel('pending'),
    status: emptyStatusSnapshot('pending'),
    ceremony: emptyCeremonyMap('pending'),
    receipt: emptyReceiptReveal('pending'),
  }
  if (typeof fetchImpl !== 'function') {
    out.stream = emptyStreamModel('no_fetch')
    out.status = emptyStatusSnapshot('no_fetch')
    out.ceremony = emptyCeremonyMap('no_fetch')
    out.receipt = emptyReceiptReveal('no_fetch')
    return out
  }
  try {
    const raw = await fetchJson(`${base}/stream.json`, fetchImpl)
    out.stream = normalizeStreamModel(raw)
  } catch {
    out.stream = emptyStreamModel('missing')
  }
  try {
    const raw = await fetchJson(`${base}/status.json`, fetchImpl)
    if (raw && typeof raw === 'object') {
      out.status = {
        ...emptyStatusSnapshot('ok'),
        ...raw,
        mock: false,
        fabricated_liveness: false,
        signing_material_present: false,
        consent_authority: false,
        _source: 'ok',
      }
      // Cross-check: status cannot claim witness_live without LIVE class
      if (out.status.freshness_class !== 'LIVE') {
        out.status.witness_live = false
      }
    }
  } catch {
    out.status = emptyStatusSnapshot('missing')
  }
  try {
    const raw = await fetchJson(`${base}/ceremony.json`, fetchImpl)
    if (raw && typeof raw === 'object') {
      out.ceremony = {
        ...emptyCeremonyMap('ok'),
        ...raw,
        signing_material_present: false,
        _source: 'ok',
        _present: true,
      }
    }
  } catch {
    out.ceremony = emptyCeremonyMap('missing')
  }
  try {
    const raw = await fetchJson(`${base}/receipt.json`, fetchImpl)
    if (raw && typeof raw === 'object' && raw.schema === RECEIPT_REVEAL_SCHEMA) {
      out.receipt = {
        ...emptyReceiptReveal('ok'),
        ...raw,
        mock: false,
        signing_material_present: false,
        consent_authority: false,
        _source: 'ok',
        _present: true,
      }
    } else if (raw && typeof raw === 'object') {
      // Soft accept if session_label present
      out.receipt = {
        ...emptyReceiptReveal('ok'),
        ...raw,
        _source: 'ok',
        _present: Boolean(raw.session_label || raw.local?.body_text),
      }
    }
  } catch {
    out.receipt = emptyReceiptReveal('missing')
  }
  return out
}
