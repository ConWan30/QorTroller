#!/usr/bin/env node
/**
 * Data Economy Arc 5 — VHR circuit input assembler.
 *
 * Reads a private-inputs JSON file (Python-emitted) and produces the full
 * snarkjs `groth16 fullprove` input.json by computing the two public Poseidon
 * commitments off-circuit byte-identically to the in-wasm Poseidon:
 *
 *   vhpCommitment      = Poseidon(2)(vhpTokenId, sessionNonce)
 *   sanitizedTraceRoot = Poseidon-2-chain over the canonical
 *                        VAPI-VHR-MATRIX-v1 byte serialization of the
 *                        SanitizedReplayMatrix (see CANONICAL ENCODING below)
 *
 * Both are field-native — circomlibjs's `poseidon([inputs])` is the same
 * permutation snarkjs's compiled .wasm uses, so the on-circuit Poseidon
 * constraints `vhpHasher.out === vhpCommitment` are satisfied for honest
 * inputs without any drift risk.
 *
 * The other public inputs (poacChainRoot, consentPolicyHash, humanityThreshold)
 * are passed through verbatim from the private-inputs file — they come from
 * the pre-processor / consent manifest and are field elements already.
 *
 * INVOCATION (mirrors zk_sepproof_prover precedent):
 *   node compute_inputs_replay_proof.js <private_inputs.json>
 *     [--print-commitments]      // also echo decimal commitments to stderr
 *     [--out <circuit_input.json>]  // default: stdout
 *
 * EXIT CODES:
 *   0 — wrote a valid input JSON
 *   1 — input file unreadable / malformed
 *   2 — circomlibjs not installed (`npm install` in this directory)
 *   3 — encoding sanity check failed (e.g. matrix field length mismatch)
 *
 * ──────────────────────────────────────────────────────────────────────────
 * CANONICAL MATRIX ENCODING — FROZEN-v1 (VAPI-VHR-MATRIX-v1)
 * ──────────────────────────────────────────────────────────────────────────
 *
 *   bytes = b"VAPI-VHR-MATRIX-v1"          (18 bytes — domain tag)
 *        || ticks                          (4 bytes — big-endian uint32)
 *        || for each tick i in [0, ticks):
 *             stick_L_sector[i]            (1 byte)
 *             stick_R_sector[i]            (1 byte)
 *             trigger_L_state[i]           (1 byte)
 *             trigger_R_state[i]           (1 byte)
 *             button_mask[2i]              (1 byte — uint16 lo byte)
 *             button_mask[2i+1]            (1 byte — uint16 hi byte)
 *             imu_gravity_sector[i]        (1 byte)
 *   total = 22 + 7 * ticks
 *
 *   Pack into 30-byte big-endian chunks (last chunk zero-padded on the right
 *   to 30 bytes). Each 30-byte chunk parses as a BN254 field element with
 *   top 2 bytes of each 32-byte representation implicitly zero — safely
 *   under the BN254 scalar modulus.
 *
 *   Sequential Poseidon-2 chain (domain-tagged via prefix; capacity = h_i):
 *     h_0 = 0
 *     h_{i+1} = Poseidon(2)([h_i, c_i])
 *     sanitizedTraceRoot = h_n  (n = number of 30-byte chunks)
 *
 *   A drift in ANY of these constants (domain tag, byte order, field order
 *   within a tick, chunk size, chain construction) silently produces a
 *   different root → every off-chain verifier rejects, every proof bound to
 *   the old encoding becomes unverifiable. Pinned by PV-CI invariants
 *   INV-VHR-MATRIX-001 / -002 / -003.
 *
 * ──────────────────────────────────────────────────────────────────────────
 */

"use strict";

const fs = require("fs");
const path = require("path");

// FROZEN canonical encoding constants.
const DOMAIN_TAG = Buffer.from("VAPI-VHR-MATRIX-v1", "utf8");   // 18 bytes
const TICKS_BYTES = 4;                                           // big-endian uint32
const PER_TICK_BYTES = 7;
const CHUNK_BYTES = 30;                                          // safely under BN254

function dieMissingCircomlibjs(err) {
  process.stderr.write(
    "ERROR: circomlibjs not installed in " + __dirname + "\n" +
    "       Install with:\n" +
    "         cd " + __dirname + "\n" +
    "         npm install\n" +
    "       (package.json in this directory declares circomlibjs as a dep.)\n" +
    "       Underlying require error: " + err.message + "\n"
  );
  process.exit(2);
}

let buildPoseidon;
try {
  ({ buildPoseidon } = require("circomlibjs"));
} catch (e) {
  dieMissingCircomlibjs(e);
}

// ── Helpers ────────────────────────────────────────────────────────────────

function readPrivateInputs(jsonPath) {
  let raw;
  try {
    raw = fs.readFileSync(jsonPath, "utf8");
  } catch (e) {
    process.stderr.write("ERROR: cannot read " + jsonPath + ": " + e.message + "\n");
    process.exit(1);
  }
  try {
    return JSON.parse(raw);
  } catch (e) {
    process.stderr.write("ERROR: malformed JSON in " + jsonPath + ": " + e.message + "\n");
    process.exit(1);
  }
}

function hexToBuf(hex, expectedBytes, name) {
  if (typeof hex !== "string") {
    process.stderr.write("ERROR: " + name + " must be a hex string, got " + typeof hex + "\n");
    process.exit(3);
  }
  let h = hex.startsWith("0x") || hex.startsWith("0X") ? hex.slice(2) : hex;
  if (h.length !== expectedBytes * 2) {
    process.stderr.write(
      "ERROR: " + name + " length " + (h.length / 2) +
      " bytes != expected " + expectedBytes + "\n"
    );
    process.exit(3);
  }
  return Buffer.from(h, "hex");
}

function fieldToDec(poseidon, F, val) {
  // Field elements returned by circomlibjs are Uint8Array; F.toObject(buf) yields BigInt.
  return F.toObject(val).toString();
}

function decimalOrHexToFieldDecimal(value, name) {
  // Accept either decimal string, decimal int, or 0x-prefixed hex (32B field).
  if (typeof value === "number") return BigInt(value).toString();
  if (typeof value === "bigint") return value.toString();
  if (typeof value !== "string") {
    process.stderr.write("ERROR: " + name + " must be int or string, got " + typeof value + "\n");
    process.exit(3);
  }
  let s = value.trim();
  if (s.startsWith("0x") || s.startsWith("0X")) {
    return BigInt(s).toString();
  }
  if (!/^[0-9]+$/.test(s)) {
    process.stderr.write("ERROR: " + name + " must be a decimal integer string, got " + value + "\n");
    process.exit(3);
  }
  return s;
}

// ── Canonical matrix bytes (VAPI-VHR-MATRIX-v1) ────────────────────────────

function canonicalMatrixBytes(matrix) {
  const ticks = matrix.ticks | 0;
  if (ticks < 0 || ticks > 0xffffffff) {
    process.stderr.write("ERROR: ticks " + matrix.ticks + " out of uint32 range\n");
    process.exit(3);
  }

  const stickL  = hexToBuf(matrix.stick_L_sector,     ticks,     "stick_L_sector");
  const stickR  = hexToBuf(matrix.stick_R_sector,     ticks,     "stick_R_sector");
  const trigL   = hexToBuf(matrix.trigger_L_state,    ticks,     "trigger_L_state");
  const trigR   = hexToBuf(matrix.trigger_R_state,    ticks,     "trigger_R_state");
  const buttons = hexToBuf(matrix.button_mask,        ticks * 2, "button_mask");
  const imu     = hexToBuf(matrix.imu_gravity_sector, ticks,     "imu_gravity_sector");

  const total = DOMAIN_TAG.length + TICKS_BYTES + ticks * PER_TICK_BYTES;
  const out = Buffer.alloc(total);
  let p = 0;
  DOMAIN_TAG.copy(out, p); p += DOMAIN_TAG.length;
  out.writeUInt32BE(ticks, p); p += TICKS_BYTES;
  for (let i = 0; i < ticks; i++) {
    out[p++] = stickL[i];
    out[p++] = stickR[i];
    out[p++] = trigL[i];
    out[p++] = trigR[i];
    out[p++] = buttons[2 * i];
    out[p++] = buttons[2 * i + 1];
    out[p++] = imu[i];
  }
  if (p !== total) {
    process.stderr.write("ERROR: encoding wrote " + p + " bytes, expected " + total + "\n");
    process.exit(3);
  }
  return out;
}

// 30-byte chunks → BigInt field elements
function bytesToFieldChunks(buf) {
  const out = [];
  for (let off = 0; off < buf.length; off += CHUNK_BYTES) {
    const chunk = Buffer.alloc(CHUNK_BYTES);
    buf.copy(chunk, 0, off, Math.min(off + CHUNK_BYTES, buf.length));
    // Big-endian interpretation
    let v = 0n;
    for (let i = 0; i < CHUNK_BYTES; i++) {
      v = (v << 8n) | BigInt(chunk[i]);
    }
    out.push(v);
  }
  // Empty matrix (ticks=0 means 22 raw bytes, still produces one chunk). If the
  // input was ever zero-length, emit one zero element so the chain is well-defined.
  if (out.length === 0) out.push(0n);
  return out;
}

async function computeSanitizedTraceRoot(poseidon, F, matrix) {
  const bytes = canonicalMatrixBytes(matrix);
  const chunks = bytesToFieldChunks(bytes);
  // Sequential Poseidon-2 chain: h_0 = 0; h_{i+1} = poseidon([h_i, c_i])
  let h = poseidon([0n, chunks[0]]);
  for (let i = 1; i < chunks.length; i++) {
    h = poseidon([h, chunks[i]]);
  }
  return fieldToDec(poseidon, F, h);
}

async function computeVhpCommitment(poseidon, F, vhpTokenIdDec, sessionNonceDec) {
  const out = poseidon([BigInt(vhpTokenIdDec), BigInt(sessionNonceDec)]);
  return fieldToDec(poseidon, F, out);
}

// ── Main ───────────────────────────────────────────────────────────────────

async function main() {
  const argv = process.argv.slice(2);
  if (argv.length < 1 || argv[0].startsWith("--")) {
    process.stderr.write(
      "usage: node compute_inputs_replay_proof.js <private_inputs.json> " +
      "[--print-commitments] [--out <circuit_input.json>]\n"
    );
    process.exit(1);
  }
  const privPath = argv[0];
  let outPath = null;
  let printCommit = false;
  for (let i = 1; i < argv.length; i++) {
    if (argv[i] === "--print-commitments") printCommit = true;
    else if (argv[i] === "--out" && argv[i + 1]) { outPath = argv[i + 1]; i++; }
  }

  const priv = readPrivateInputs(privPath);

  // Required private + pass-through public fields.
  const need = [
    "humanityProbabilityWitness", "humanityThreshold",
    "vhpTokenId", "sessionNonce",
    "poacChainRoot", "consentPolicyHash",
    "matrix",
  ];
  for (const k of need) {
    if (!(k in priv)) {
      process.stderr.write("ERROR: private inputs missing required field: " + k + "\n");
      process.exit(3);
    }
  }

  const vhpTokenIdDec   = decimalOrHexToFieldDecimal(priv.vhpTokenId,   "vhpTokenId");
  const sessionNonceDec = decimalOrHexToFieldDecimal(priv.sessionNonce, "sessionNonce");
  const humThresholdDec = decimalOrHexToFieldDecimal(priv.humanityThreshold, "humanityThreshold");
  const humWitnessDec   = decimalOrHexToFieldDecimal(priv.humanityProbabilityWitness, "humanityProbabilityWitness");
  const poacChainDec    = decimalOrHexToFieldDecimal(priv.poacChainRoot, "poacChainRoot");
  const consentHashDec  = decimalOrHexToFieldDecimal(priv.consentPolicyHash, "consentPolicyHash");

  const poseidon = await buildPoseidon();
  const F = poseidon.F;

  const sanitizedTraceRootDec = await computeSanitizedTraceRoot(poseidon, F, priv.matrix);
  const vhpCommitmentDec      = await computeVhpCommitment(poseidon, F, vhpTokenIdDec, sessionNonceDec);

  // FROZEN public-input order — matches VAPIReplayProofVerifier.circom
  // `component main {public [...]}` declaration order.
  const circuitInput = {
    sanitizedTraceRoot:          sanitizedTraceRootDec,
    poacChainRoot:               poacChainDec,
    consentPolicyHash:           consentHashDec,
    humanityThreshold:           humThresholdDec,
    vhpCommitment:               vhpCommitmentDec,
    humanityProbabilityWitness:  humWitnessDec,
    vhpTokenId:                  vhpTokenIdDec,
    sessionNonce:                sessionNonceDec,
  };

  if (printCommit) {
    process.stderr.write("sanitizedTraceRoot = " + sanitizedTraceRootDec + "\n");
    process.stderr.write("vhpCommitment      = " + vhpCommitmentDec + "\n");
  }

  const json = JSON.stringify(circuitInput);
  if (outPath) {
    fs.writeFileSync(outPath, json);
  } else {
    process.stdout.write(json + "\n");
  }
}

main().catch((e) => {
  process.stderr.write("ERROR: " + (e && e.stack || e) + "\n");
  process.exit(1);
});
