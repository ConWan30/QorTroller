#!/usr/bin/env node
/**
 * Retina Phase 3 — Poseidon-2 chain over canonical event field elements.
 *
 * Mirrors the VHR sanitizedTraceRoot construction (Arc 5 compute_inputs_replay_proof.js):
 *   h_0 = Poseidon(2)([0, e_0])
 *   h_{i+1} = Poseidon(2)([h_i, e_{i+1}])
 *   events_root = h_n encoded as 32-byte big-endian (uint256 BE)
 *
 * INPUT (stdin JSON):
 *   { "field_elements": ["<decimal>", ...] }
 *
 * OUTPUT (stdout JSON):
 *   { "events_root_dec": "...", "events_root_hex": "<64 hex, no 0x>" }
 *
 * EXIT: 0 ok | 1 malformed input | 2 circomlibjs missing
 */
"use strict";

const fs = require("fs");

function die(code, msg) {
  process.stderr.write(msg + "\n");
  process.exit(code);
}

let buildPoseidon;
try {
  ({ buildPoseidon } = require("circomlibjs"));
} catch (e) {
  die(
    2,
    "ERROR: circomlibjs not installed — run npm install in " + __dirname
  );
}

function fieldToHex32BE(poseidon, F, val) {
  const obj = F.toObject(val);
  let hex = obj.toString(16);
  if (hex.length > 64) {
    throw new Error("field element exceeds 32 bytes");
  }
  return hex.padStart(64, "0");
}

async function chainFieldElements(fieldElements) {
  const poseidon = await buildPoseidon();
  const F = poseidon.F;
  const elems = fieldElements.map((s, idx) => {
    if (typeof s !== "string" || !/^[0-9]+$/.test(s)) {
      throw new Error("field_elements[" + idx + "] must be a decimal string");
    }
    return BigInt(s);
  });
  if (elems.length === 0) {
    elems.push(0n);
  }
  let h = poseidon([0n, elems[0]]);
  for (let i = 1; i < elems.length; i++) {
    h = poseidon([h, elems[i]]);
  }
  return {
    events_root_dec: F.toObject(h).toString(),
    events_root_hex: fieldToHex32BE(poseidon, F, h),
  };
}

async function main() {
  let raw = "";
  try {
    raw = fs.readFileSync(0, "utf8");
  } catch (e) {
    die(1, "ERROR: cannot read stdin: " + e.message);
  }
  let body;
  try {
    body = JSON.parse(raw || "{}");
  } catch (e) {
    die(1, "ERROR: stdin is not valid JSON: " + e.message);
  }
  const fieldElements = body.field_elements;
  if (!Array.isArray(fieldElements)) {
    die(1, "ERROR: field_elements must be an array");
  }
  try {
    const out = await chainFieldElements(fieldElements);
    process.stdout.write(JSON.stringify(out));
  } catch (e) {
    die(1, "ERROR: " + e.message);
  }
}

main();
