/**
 * Phase O5-PUBLIC-VIEWER — Browser-side VAPI cryptographic verifier catalog.
 *
 * One function per FROZEN-v1 primitive. Each function mirrors the Python
 * implementation at `bridge/vapi_bridge/<module>.py` byte-for-byte, so an
 * external auditor can re-derive every cryptographic claim VAPI makes
 * using nothing but a browser's Web Crypto API.
 *
 * No dependencies. Every output is SHA-256 -> 32B (-> 64-char lowercase hex).
 *
 * Discipline:
 *   - Each verifier is deterministic (no Date.now, no Math.random).
 *   - Each verifier accepts canonical byte-shape inputs (hex strings ->
 *     bytes; integers -> big-endian byte arrays).
 *   - Failures throw; the caller is responsible for try/catch UX.
 *
 * The vitest test file `frontend/src/__tests__/vapi_verifier.test.jsx`
 * carries (a) one happy-path vector per verifier and (b) one tamper-
 * detect vector per verifier — total 28 tests that lock byte-identical
 * output against the Python originals.
 */

// ---------------------------------------------------------------------------
// Byte primitives — small helpers shared across all verifiers
// ---------------------------------------------------------------------------

/** SHA-256 -> 64-char lowercase hex. */
export async function sha256Hex(bytes) {
  const buf = await window.crypto.subtle.digest('SHA-256', bytes)
  return bytesToHex(new Uint8Array(buf))
}

/** Uint8Array -> 64-char lowercase hex string. */
export function bytesToHex(bytes) {
  const out = new Array(bytes.length)
  for (let i = 0; i < bytes.length; i++) {
    out[i] = bytes[i].toString(16).padStart(2, '0')
  }
  return out.join('')
}

/** Lowercase hex string -> Uint8Array. Accepts optional 0x prefix. */
export function hexToBytes(hex) {
  if (typeof hex !== 'string') {
    throw new Error('hexToBytes: input must be a string')
  }
  const stripped = hex.toLowerCase().startsWith('0x') ? hex.slice(2) : hex
  if (stripped.length % 2 !== 0) {
    throw new Error(`hexToBytes: odd hex length ${stripped.length}`)
  }
  const out = new Uint8Array(stripped.length / 2)
  for (let i = 0; i < out.length; i++) {
    out[i] = parseInt(stripped.substr(i * 2, 2), 16)
  }
  return out
}

/** Concatenate multiple Uint8Array chunks into one. */
export function concatBytes(...chunks) {
  let total = 0
  for (const c of chunks) total += c.length
  const out = new Uint8Array(total)
  let off = 0
  for (const c of chunks) {
    out.set(c, off)
    off += c.length
  }
  return out
}

/** Big-endian uint64 -> 8 bytes. JavaScript safe-int range only — for
 * values > 2^53 callers should use BigInt; we encode the low 8 bytes
 * via DataView with BigInt support. */
export function uint64BE(n) {
  const buf = new ArrayBuffer(8)
  const view = new DataView(buf)
  view.setBigUint64(0, BigInt(n), false)
  return new Uint8Array(buf)
}

/** Big-endian uint32 -> 4 bytes. */
export function uint32BE(n) {
  const buf = new ArrayBuffer(4)
  const view = new DataView(buf)
  view.setUint32(0, Number(n) >>> 0, false)
  return new Uint8Array(buf)
}

/** Big-endian uint8 -> 1 byte. */
export function uint8(n) {
  return new Uint8Array([Number(n) & 0xff])
}

/** UTF-8 encode a string. */
export function utf8(s) {
  return new TextEncoder().encode(String(s))
}

/** Canonical-JSON encode (sorted keys, no whitespace, ensure_ascii=False
 * equivalent — output is the exact same bytes Python emits with
 * json.dumps(..., sort_keys=True, separators=(",", ":")).
 * Returns Uint8Array of UTF-8 bytes.
 */
export function canonicalJsonBytes(obj) {
  return utf8(canonicalJsonStringify(obj))
}

/** Canonical-JSON stringify — recursive key-sort + tight separators. */
export function canonicalJsonStringify(obj) {
  if (obj === null) return 'null'
  if (typeof obj === 'number' || typeof obj === 'boolean') return JSON.stringify(obj)
  if (typeof obj === 'string') return JSON.stringify(obj)
  if (Array.isArray(obj)) {
    return '[' + obj.map(canonicalJsonStringify).join(',') + ']'
  }
  if (typeof obj === 'object') {
    const keys = Object.keys(obj).sort()
    const pairs = keys.map(k => JSON.stringify(k) + ':' + canonicalJsonStringify(obj[k]))
    return '{' + pairs.join(',') + '}'
  }
  return JSON.stringify(obj)
}


// ---------------------------------------------------------------------------
// FROZEN-v1 domain tag constants (byte-literal mirrors of Python sources)
// ---------------------------------------------------------------------------

export const FROZEN_TAGS = Object.freeze({
  GIC_GENESIS:        utf8('VAPI-GIC-GENESIS-v1'),            // 19B
  MLGA_SESSION:       utf8('VAPI-MLGA-SESSION-v1'),           // 20B
  WEC_GENESIS:        utf8('VAPI-WEC-GENESIS-v1'),            // 19B
  VAME:               utf8('VAPI-VAME-v1'),                   // 12B
  CORPUS_SNAPSHOT:    utf8('VAPI-CORPUS-SNAPSHOT-v1'),        // 23B
  CONSENT:            utf8('VAPI-CONSENT-v1'),                // 15B
  BIOMETRIC_SNAPSHOT: utf8('VAPI-BIOMETRIC-SNAPSHOT-v1'),     // 26B
  LISTING:            utf8('VAPI-LISTING-v1'),                // 15B
  FRR:                utf8('VAPI-FRR-v1'),                    // 11B
  ZKBA_ARTIFACT:      utf8('VAPI-ZKBA-ARTIFACT-v1'),          // 21B
  AGENT_COMMIT:       utf8('VAPI-AGENT-COMMIT-v1'),           // 20B
  PDA:                utf8('VAPI-PHYSICAL-DATA-ATTESTATION-v1'),  // 33B
  BT_WITNESS:         utf8('VAPI-BT-WITNESS-v1'),             // 18B
})


// ---------------------------------------------------------------------------
// VERIFIER #1 — PoAC record body hash
// Per CLAUDE.md INVARIANT: record_hash = SHA-256(raw[:164])
//   164-byte body (NOT 228 — the body excludes the 64B ECDSA-P256 signature)
//   Wire layout body: prev_poac_hash(32) || sensor_commitment(32) ||
//   model_manifest(32) || world_model(32) || inference(1) || action(1) ||
//   confidence(1) || battery(1) || counter_be(4) || timestamp_be(8) ||
//   latitude(8 IEEE754) || longitude(8) || bounty_id_be(4) = 164B total
// ---------------------------------------------------------------------------

export async function verifyPoacRecordHash(raw228Bytes) {
  if (!(raw228Bytes instanceof Uint8Array) || raw228Bytes.length !== 228) {
    throw new Error('verifyPoacRecordHash: input must be 228-byte Uint8Array')
  }
  // The verifier hashes the BODY ONLY (bytes 0-163), not the full 228 bytes.
  // This is the FROZEN INV from CLAUDE.md.
  const body = raw228Bytes.slice(0, 164)
  return await sha256Hex(body)
}


// ---------------------------------------------------------------------------
// VERIFIER #2 — GIC chain genesis
// SHA-256(tag(19B) || grind_session_id_utf8 || ts_ns_be(8B))
// ---------------------------------------------------------------------------

export async function verifyGicGenesis(grindSessionId, tsNs) {
  const pre = concatBytes(
    FROZEN_TAGS.GIC_GENESIS,
    utf8(grindSessionId),
    uint64BE(tsNs),
  )
  return await sha256Hex(pre)
}


// ---------------------------------------------------------------------------
// VERIFIER #3 — GIC chain step (no domain tag — prev_gic IS the binding)
// SHA-256(prev_gic(32B) || commitment_bytes(32B) || verdict_code(1B) ||
//          host_state_code(1B) || ts_ns_be(8B))
// ---------------------------------------------------------------------------

export async function verifyGicChainLink(prevGicHex, commitmentHex, verdictCode, hostStateCode, tsNs) {
  const prev = hexToBytes(prevGicHex)
  const commit = hexToBytes(commitmentHex)
  if (prev.length !== 32) throw new Error('verifyGicChainLink: prev_gic must be 32B')
  if (commit.length !== 32) throw new Error('verifyGicChainLink: commitment must be 32B')
  const pre = concatBytes(
    prev, commit,
    uint8(verdictCode),
    uint8(hostStateCode),
    uint64BE(tsNs),
  )
  return await sha256Hex(pre)
}


// ---------------------------------------------------------------------------
// VERIFIER #4 — MLGA session dataproof
// SHA-256(tag(20B) || start_ts_ns(8B) || end_ts_ns(8B) || n_poac(8B) ||
//          n_r2(4B) || n_l2(4B) || apop_sha256(32B) || bt_obs(1B) ||
//          gic_advances(4B)) = 89B preimage -> 32B
// apop_sha256 = SHA-256(canonical_json(apop_state_counts))
// ---------------------------------------------------------------------------

export async function verifyMlgaDataproof({
  startTsNs, endTsNs, nPoacRecords,
  nTriggerPullsR2, nTriggerPullsL2,
  apopStateCounts, btObservability, gicAdvancesInSession,
}) {
  const apopSha = await sha256Hex(canonicalJsonBytes(apopStateCounts || {}))
  const pre = concatBytes(
    FROZEN_TAGS.MLGA_SESSION,
    uint64BE(startTsNs),
    uint64BE(endTsNs),
    uint64BE(nPoacRecords),
    uint32BE(nTriggerPullsR2),
    uint32BE(nTriggerPullsL2),
    hexToBytes(apopSha),
    uint8(btObservability),
    uint32BE(gicAdvancesInSession),
  )
  return await sha256Hex(pre)
}


// ---------------------------------------------------------------------------
// VERIFIER #5 — Watchdog Event Chain genesis
// SHA-256(tag(19B) || grind_session_id_utf8 || ts_ns_be(8B))
// ---------------------------------------------------------------------------

export async function verifyWecGenesis(grindSessionId, tsNs) {
  const pre = concatBytes(
    FROZEN_TAGS.WEC_GENESIS,
    utf8(grindSessionId),
    uint64BE(tsNs),
  )
  return await sha256Hex(pre)
}


// ---------------------------------------------------------------------------
// VERIFIER #6 — Watchdog Event Chain link
// SHA-256(prev_wec(32B) || event_code(1B) || pid_be(4B) ||
//          session_id_hash(16B) || ts_ns_be(8B))
// session_id_hash = SHA-256(grind_session_id)[:16]
// ---------------------------------------------------------------------------

export async function verifyWecChainLink(prevWecHex, eventCode, pid, grindSessionId, tsNs) {
  const sidHashFull = await sha256Hex(utf8(grindSessionId))
  const sidHash16 = hexToBytes(sidHashFull).slice(0, 16)
  const pre = concatBytes(
    hexToBytes(prevWecHex),
    uint8(eventCode),
    uint32BE(pid),
    sidHash16,
    uint64BE(tsNs),
  )
  return await sha256Hex(pre)
}


// ---------------------------------------------------------------------------
// VERIFIER #7 — VAME commitment
// SHA-256(tag(12B) || chain_head_16b || ts_ns_be(8B) || endpoint_utf8 || body_bytes)
// ---------------------------------------------------------------------------

export async function verifyVameCommitment({
  chainHead16bHex, tsNs, endpoint, bodyBytes,
}) {
  const chainHead = hexToBytes(chainHead16bHex || '0'.repeat(32))
  // Pad/truncate chain_head to exactly 16 bytes
  const head16 = new Uint8Array(16)
  head16.set(chainHead.slice(0, 16))
  const body = bodyBytes instanceof Uint8Array ? bodyBytes : utf8(String(bodyBytes || ''))
  const pre = concatBytes(
    FROZEN_TAGS.VAME,
    head16,
    uint64BE(tsNs),
    utf8(endpoint),
    body,
  )
  return await sha256Hex(pre)
}


// ---------------------------------------------------------------------------
// VERIFIER #8 — VPM integrity label hash
// SHA-256(canonical_json(integrity_label_dict))
// ---------------------------------------------------------------------------

export async function verifyVpmIntegrityLabelHash(integrityLabelDict) {
  return await sha256Hex(canonicalJsonBytes(integrityLabelDict))
}


// ---------------------------------------------------------------------------
// VERIFIER #9 — ZKBA commitment (composable artifact)
// SHA-256(tag(21B) || class_byte(1B) || weight_byte(1B) || n_components_be(1B) ||
//          sorted_component_hashes || ts_ns_be(8B))
// Component hashes lexicographically sorted before concatenation.
// ---------------------------------------------------------------------------

export async function verifyZkbaCommitment({
  zkbaClass, proofWeight, componentHashesHex, tsNs,
}) {
  if (!Array.isArray(componentHashesHex)) {
    throw new Error('verifyZkbaCommitment: componentHashesHex must be array')
  }
  const sortedHex = [...componentHashesHex].map(s => s.toLowerCase()).sort()
  const componentBytes = concatBytes(...sortedHex.map(hexToBytes))
  const pre = concatBytes(
    FROZEN_TAGS.ZKBA_ARTIFACT,
    uint8(zkbaClass),
    uint8(proofWeight),
    uint8(sortedHex.length),
    componentBytes,
    uint64BE(tsNs),
  )
  return await sha256Hex(pre)
}


// ---------------------------------------------------------------------------
// VERIFIER #10 — Corpus snapshot
// SHA-256(tag(23B) || wiki_hash(32B) || agent_root(32B) || ratio_milli_be(8B) ||
//          corpus_n_be(8B) || ts_ns_be(8B))
// ---------------------------------------------------------------------------

export async function verifyCorpusSnapshot({
  wikiHashHex, agentRootHex, ratioMilli, corpusN, tsNs,
}) {
  const pre = concatBytes(
    FROZEN_TAGS.CORPUS_SNAPSHOT,
    hexToBytes(wikiHashHex),
    hexToBytes(agentRootHex),
    uint64BE(ratioMilli),
    uint64BE(corpusN),
    uint64BE(tsNs),
  )
  return await sha256Hex(pre)
}


// ---------------------------------------------------------------------------
// VERIFIER #11 — Consent hash (per-category)
// SHA-256(tag(15B) || device_id_b32 || category_bitmask_be(4B) ||
//          expires_at_be(8B) || ts_ns_be(8B))
// device_id_b32 = SHA-256(device_id_utf8) -> 32B
// ---------------------------------------------------------------------------

export async function verifyConsentHash({
  deviceId, categoryBitmask, expiresAt, tsNs,
}) {
  const deviceIdB32Hex = await sha256Hex(utf8(deviceId))
  const pre = concatBytes(
    FROZEN_TAGS.CONSENT,
    hexToBytes(deviceIdB32Hex),
    uint32BE(categoryBitmask),
    uint64BE(expiresAt),
    uint64BE(tsNs),
  )
  return await sha256Hex(pre)
}


// ---------------------------------------------------------------------------
// VERIFIER #12 — Listing commitment (marketplace)
// SHA-256(tag(15B) || seller_b32 || sepproof_commit(32B) || biometric_snap(32B)
//          || corpus_snap(32B) || gic(32B) || consent_bitmask_be(4B) ||
//          data_class(1B) || ts_ns_be(8B))
// ---------------------------------------------------------------------------

export async function verifyListingCommitment({
  sellerAddress, sepproofCommitHex, biometricSnapHex,
  corpusSnapHex, gicHex, consentBitmask, dataClass, tsNs,
}) {
  const sellerB32Hex = await sha256Hex(utf8(sellerAddress))
  const pre = concatBytes(
    FROZEN_TAGS.LISTING,
    hexToBytes(sellerB32Hex),
    hexToBytes(sepproofCommitHex),
    hexToBytes(biometricSnapHex),
    hexToBytes(corpusSnapHex),
    hexToBytes(gicHex),
    uint32BE(consentBitmask),
    uint8(dataClass),
    uint64BE(tsNs),
  )
  return await sha256Hex(pre)
}


// ---------------------------------------------------------------------------
// VERIFIER #13 — Biometric snapshot
// SHA-256(tag(26B) || feature_root(32B) || n_features_be(4B) ||
//          device_id_b32 || ts_ns_be(8B))
// ---------------------------------------------------------------------------

export async function verifyBiometricSnapshot({
  featureRootHex, nFeatures, deviceId, tsNs,
}) {
  const deviceIdB32Hex = await sha256Hex(utf8(deviceId))
  const pre = concatBytes(
    FROZEN_TAGS.BIOMETRIC_SNAPSHOT,
    hexToBytes(featureRootHex),
    uint32BE(nFeatures),
    hexToBytes(deviceIdB32Hex),
    uint64BE(tsNs),
  )
  return await sha256Hex(pre)
}


// ---------------------------------------------------------------------------
// VERIFIER #14 — Fleet Readiness Root (FRR)
// SHA-256(tag(11B) || sorted_by_agent_id[agent_id_be(32B) || phase_code(1B)]
//          for each agent || ts_ns_be(8B))
// Agents are sorted by agent_id bytes ascending before concatenation.
// ---------------------------------------------------------------------------

export async function verifyFrr({ agents, tsNs }) {
  // agents: array of { agentIdHex, phaseCode }
  if (!Array.isArray(agents)) {
    throw new Error('verifyFrr: agents must be array')
  }
  const pairs = agents.map(a => ({
    bytes: hexToBytes(a.agentIdHex),
    phaseCode: a.phaseCode,
  }))
  pairs.sort((a, b) => {
    for (let i = 0; i < a.bytes.length; i++) {
      if (a.bytes[i] !== b.bytes[i]) return a.bytes[i] - b.bytes[i]
    }
    return 0
  })
  const agentChunks = pairs.map(p => concatBytes(p.bytes, uint8(p.phaseCode)))
  const pre = concatBytes(
    FROZEN_TAGS.FRR,
    ...agentChunks,
    uint64BE(tsNs),
  )
  return await sha256Hex(pre)
}


// ---------------------------------------------------------------------------
// VERIFIER #15 — Cedar bundle Merkle root
// Binary Merkle tree over per-policy SHA-256 leaves; odd levels are
// promoted by duplication (last-leaf-duplicate semantics).
// ---------------------------------------------------------------------------

export async function verifyCedarBundleMerkle(policyLeaves) {
  if (!Array.isArray(policyLeaves) || policyLeaves.length === 0) {
    throw new Error('verifyCedarBundleMerkle: policyLeaves must be non-empty array')
  }
  let level = policyLeaves.map(leaf => {
    if (typeof leaf === 'string') return hexToBytes(leaf)
    if (leaf instanceof Uint8Array) return leaf
    throw new Error('verifyCedarBundleMerkle: leaf must be hex string or Uint8Array')
  })
  while (level.length > 1) {
    const next = []
    for (let i = 0; i < level.length; i += 2) {
      const left = level[i]
      const right = (i + 1 < level.length) ? level[i + 1] : level[i]  // duplicate odd
      const combined = concatBytes(left, right)
      const buf = await window.crypto.subtle.digest('SHA-256', combined)
      next.push(new Uint8Array(buf))
    }
    level = next
  }
  return bytesToHex(level[0])
}


// ---------------------------------------------------------------------------
// Verifier registry — name -> function. Used by the CryptoReplayPanel
// to render the verifier catalog dynamically.
// ---------------------------------------------------------------------------

export const VERIFIERS = Object.freeze({
  verifyPoacRecordHash,
  verifyGicGenesis,
  verifyGicChainLink,
  verifyMlgaDataproof,
  verifyWecGenesis,
  verifyWecChainLink,
  verifyVameCommitment,
  verifyVpmIntegrityLabelHash,
  verifyZkbaCommitment,
  verifyCorpusSnapshot,
  verifyConsentHash,
  verifyListingCommitment,
  verifyBiometricSnapshot,
  verifyFrr,
  verifyCedarBundleMerkle,
})

export const VERIFIER_COUNT = Object.keys(VERIFIERS).length  // == 15
