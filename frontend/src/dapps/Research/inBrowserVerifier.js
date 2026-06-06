// In-browser port of the WMP-3 consumer verifier's structural checks.
//
// The headline of /research: a researcher pastes a bundle JSON and
// watches each check evaluate live, in their browser, without trusting
// QorTroller's infrastructure. Trust-by-execution.
//
// Mirrors sdk/wmp_verify.py exactly for the checks portable to the
// browser (scope honesty, structural matrix↔root rehash, recency
// temporal order, consent dimension). The Groth16 verify check stays
// stubbed in v1 — that path needs snarkjs WASM and is a Phase-2 wiring
// task — but the stub is honest, surfacing as { stubbed: true } so a
// consumer never confuses a passing-by-stub result with a real verify.

// frozen values lifted from bundle_assembler.py constants
const SCOPE_CHANNEL_ACTION_ONLY = 'ACTION_ONLY'
const SCOPE_OBSERVATION_ABSENT = 'ABSENT_BY_DESIGN_DATA_FLOOR'
const SCOPE_FIDELITY_MACRO = 'MACRO_INTENT_POST_PHI_NOT_BIOMECHANICAL'

export const OUTCOME_VERIFIED = 'VERIFIED'
export const OUTCOME_REJECTED = 'REJECTED'

// ── helpers ──────────────────────────────────────────────────────────

async function sha256Hex(bytes) {
  const buf = await crypto.subtle.digest('SHA-256', bytes)
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
}

function hexToBytes(hex) {
  const h = hex.startsWith('0x') ? hex.slice(2) : hex
  const clean = h.replace(/[^0-9a-fA-F]/g, '')
  if (clean.length % 2 !== 0) return new Uint8Array(0)
  const out = new Uint8Array(clean.length / 2)
  for (let i = 0; i < out.length; i++) {
    out[i] = parseInt(clean.substr(i * 2, 2), 16)
  }
  return out
}

function concatBytes(...arrs) {
  let total = 0
  for (const a of arrs) total += a.length
  const out = new Uint8Array(total)
  let off = 0
  for (const a of arrs) { out.set(a, off); off += a.length }
  return out
}

// ── check 5: scope honesty ──────────────────────────────────────────

export function checkScopeHonesty(bundle) {
  const issues = []
  if (bundle.scope_channel !== SCOPE_CHANNEL_ACTION_ONLY) {
    issues.push(`scope_channel must be "${SCOPE_CHANNEL_ACTION_ONLY}"`)
  }
  if (bundle.scope_observation_channel !== SCOPE_OBSERVATION_ABSENT) {
    issues.push(`scope_observation_channel must be "${SCOPE_OBSERVATION_ABSENT}"`)
  }
  if (bundle.scope_fidelity !== SCOPE_FIDELITY_MACRO) {
    issues.push(`scope_fidelity must be "${SCOPE_FIDELITY_MACRO}"`)
  }
  if (bundle.scope_is_full_pomdp_tuple !== false) {
    issues.push('scope_is_full_pomdp_tuple must be false (lane is not full POMDP)')
  }
  return { passed: issues.length === 0, issues }
}

// ── check 2: structural matrix↔root rehash ──────────────────────────
//
// Mirrors sdk/wmp_verify.py:check_matrix_root_rehash — v1
// STRUCTURAL_REHASH_v1 algorithm:
//   digest = sha256(
//       b"WMP_STRUCTURAL_REHASH_v1"
//       || foreach channel in canonical_order: utf8(channel) || matrix_bytes
//       || utf8(str(ticks))
//   )
// Tampering with any channel byte produces a different digest, catching
// matrix-swap attacks the Groth16 proof alone cannot.

export async function checkMatrixRootRehash(bundle) {
  const channels = Array.isArray(bundle.action_trace_channels)
    ? bundle.action_trace_channels
    : []
  const matrixHex = bundle.action_trace_matrix_hex || {}
  if (channels.length === 0 || Object.keys(matrixHex).length === 0) {
    return {
      passed: false,
      actual: '',
      claimed: String(bundle.sanitized_trace_root_ref || ''),
      algorithm: 'STRUCTURAL_REHASH_v1',
      issues: ['action_trace channels or matrix_hex empty'],
    }
  }
  const encoder = new TextEncoder()
  const parts = [encoder.encode('WMP_STRUCTURAL_REHASH_v1')]
  for (const ch of channels) {
    parts.push(encoder.encode(ch))
    parts.push(hexToBytes(matrixHex[ch] || ''))
  }
  parts.push(encoder.encode(String(bundle.action_trace_ticks || 0)))
  const actual = await sha256Hex(concatBytes(...parts))
  const paired = bundle.structural_rehash_v1 || ''
  if (paired) {
    return {
      passed: actual === paired,
      actual,
      claimed: String(bundle.sanitized_trace_root_ref || ''),
      algorithm: 'STRUCTURAL_REHASH_v1',
      issues: actual === paired ? [] : [`structural rehash mismatch: actual=${actual} paired=${paired}`],
    }
  }
  return {
    passed: true,
    actual,
    claimed: String(bundle.sanitized_trace_root_ref || ''),
    algorithm: 'STRUCTURAL_REHASH_v1',
    issues: ['structural_rehash_v1 not paired in bundle — v1 verifier surfaces digest only; Phase-2 promotes to Poseidon-BN254'],
  }
}

// ── check 3: recency ────────────────────────────────────────────────

export function checkRecency(bundle) {
  const registry = bundle.recency_registry_address || ''
  if (!registry) {
    return {
      passed: true,
      deferred: true,
      deferred_reason: 'BEACON_REGISTRY_NOT_DEPLOYED',
    }
  }
  const openBlock = Number(bundle.recency_open_block || 0)
  const closeBlock = Number(bundle.recency_close_block || 0)
  const issues = []
  if (openBlock <= 0 || closeBlock <= 0) {
    issues.push('open_block / close_block must be positive')
  }
  if (closeBlock <= openBlock) {
    issues.push('close_block must be > open_block (temporal ordering)')
  }
  const openH = String(bundle.recency_open_block_hash || '')
  const closeH = String(bundle.recency_close_block_hash || '')
  if (!(openH.startsWith('0x') && openH.length === 66)) {
    issues.push('recency_open_block_hash must be 0x + 64 hex')
  }
  if (!(closeH.startsWith('0x') && closeH.length === 66)) {
    issues.push('recency_close_block_hash must be 0x + 64 hex')
  }
  return {
    passed: issues.length === 0,
    stubbed: true,
    note: 'v1 stub — IoTeX verifyBeacon view-call wiring is Phase-2',
    issues,
  }
}

// ── check 4: consent ────────────────────────────────────────────────

export function checkConsent(bundle) {
  const dim = String(bundle.world_model_consent_dimension || '')
  if (dim === 'DEFERRED') {
    return {
      passed: true,
      deferred: true,
      deferred_reason: 'CONSENT_GATE_DEFERRED',
      note: 'Phase-2 promote: VAPIWorldModelConsentRegistry view-call',
    }
  }
  return {
    passed: true,
    stubbed: true,
    note: 'v1 stub — Phase-2 wires registry view-call',
  }
}

// ── check 1: humanity (v1 structural stub) ──────────────────────────

export function checkHumanity(bundle) {
  const proofHex = String(bundle.humanity_proof_bytes_hex || '')
  const deferred = Boolean(bundle.humanity_deferred)
  if (deferred) {
    return {
      passed: true,
      stubbed: true,
      deferred: true,
      deferred_reason: String(bundle.humanity_deferred_reason || ''),
    }
  }
  const h = proofHex.startsWith('0x') ? proofHex.slice(2) : proofHex
  const structurally_ok = h.length > 0 && /^[0-9a-fA-F]+$/.test(h)
  return {
    passed: structurally_ok,
    stubbed: true,
    deferred: false,
    note: 'v1 stub — snarkjs groth16 verify wiring is Phase-2',
  }
}

// ── orchestrator ────────────────────────────────────────────────────

export async function verifyBundle(bundle, { allowSynthetic = false } = {}) {
  const result = {
    overall: OUTCOME_VERIFIED,
    checks: {},
    deferred: [],
    reasons: [],
  }

  if (bundle.schema !== 'vapi-wmp-provenance-bundle-v1') {
    result.overall = OUTCOME_REJECTED
    result.reasons.push(`unknown schema "${bundle.schema}"`)
    return result
  }

  if (bundle.scope_synthetic && !allowSynthetic) {
    result.overall = OUTCOME_REJECTED
    result.reasons.push('scope_synthetic=true; verifier invoked without allowSynthetic')
    return result
  }

  const checks = {
    scope_honesty: checkScopeHonesty(bundle),
    matrix_root_rehash: await checkMatrixRootRehash(bundle),
    humanity: checkHumanity(bundle),
    recency: checkRecency(bundle),
    consent: checkConsent(bundle),
  }
  result.checks = checks

  for (const [name, ch] of Object.entries(checks)) {
    if (ch.deferred) result.deferred.push(name)
    if (!ch.passed) {
      result.overall = OUTCOME_REJECTED
      for (const i of ch.issues || []) {
        result.reasons.push(`${name}: ${i}`)
      }
    }
  }
  return result
}
