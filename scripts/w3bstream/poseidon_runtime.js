#!/usr/bin/env node
/**
 * poseidon_runtime.js -- Phase O4-W3B-POSEIDON-AS Stream V.1
 *
 * Node.js WASM invocation helper. Loads the asc-compiled poseidon_bn254.wasm
 * via the asc-generated ESM loader (dist/poseidon_bn254.js) and verifies the
 * AssemblyScript Poseidon(BN254) implementation against the committed
 * test-vector corpus (poseidon_test_vectors.json, Stream P.2).
 *
 * Used by bridge/tests/test_w3bstream_poseidon_as.py as a subprocess: ONE
 * invocation runs the full verification band across all 3 arities and emits
 * a single JSON result object to stdout that the pytest tests assert against.
 *
 * This is the V.1 verification gate -- it is the INDEPENDENT check that the
 * AS implementation (Streams I.1a/I.1b) produces output byte-identical to the
 * circomlibjs reference for every vector. Any mismatch is a hard failure.
 *
 * Usage:  node poseidon_runtime.js <vector-file> [--random-count N]
 *   --random-count N : how many random-band vectors per arity to test
 *                      (default 100, the V.1 spec; the corpus has 1000 each)
 *
 * Output: a JSON object to stdout. Exit code is always 0 -- the pytest layer
 * interprets the JSON (presence of an "error" key, or per-band failed>0, is
 * the failure signal). This keeps subprocess plumbing simple.
 */

"use strict";

const fs = require("fs");
const path = require("path");
const { pathToFileURL } = require("url");

const HERE = __dirname;
const WASM_PATH = path.join(HERE, "dist", "poseidon_bn254.wasm");
const LOADER_PATH = path.join(HERE, "dist", "poseidon_bn254.js");

// decimal string -> 32-byte big-endian Uint8Array
function decToBytes32BE(decStr) {
  let v = BigInt(decStr);
  if (v < 0n) throw new Error("negative value");
  const out = new Uint8Array(32);
  for (let i = 31; i >= 0; i--) {
    out[i] = Number(v & 0xffn);
    v >>= 8n;
  }
  if (v !== 0n) throw new Error("value exceeds 32 bytes: " + decStr);
  return out;
}

// 32-byte big-endian buffer -> decimal string
function bytes32BEToDec(buf) {
  const u8 = new Uint8Array(buf);
  let v = 0n;
  for (let i = 0; i < u8.length; i++) v = (v << 8n) | BigInt(u8[i]);
  return v.toString();
}

async function main() {
  const vectorFile = process.argv[2];
  let randomCount = 100;
  const rcIdx = process.argv.indexOf("--random-count");
  if (rcIdx >= 0 && process.argv[rcIdx + 1]) {
    randomCount = parseInt(process.argv[rcIdx + 1], 10);
  }

  if (!vectorFile || !fs.existsSync(vectorFile)) {
    console.log(JSON.stringify({ error: "vector file not found: " + String(vectorFile) }));
    return;
  }
  if (!fs.existsSync(WASM_PATH) || !fs.existsSync(LOADER_PATH)) {
    console.log(
      JSON.stringify({
        error:
          "WASM artifacts not found -- compile poseidon_bn254.ts first. Missing: " +
          (fs.existsSync(WASM_PATH) ? LOADER_PATH : WASM_PATH),
      })
    );
    return;
  }

  const doc = JSON.parse(fs.readFileSync(vectorFile, "utf8"));
  const loader = await import(pathToFileURL(LOADER_PATH).href);
  const wasmModule = await WebAssembly.compile(fs.readFileSync(WASM_PATH));
  const ex = await loader.instantiate(wasmModule, {});

  // arity key -> { nIn, call(inBufs) -> ArrayBuffer }
  const ARITIES = {
    t2: { nIn: 1, call: (b) => ex.poseidon_t2(b[0]) },
    t3: { nIn: 2, call: (b) => ex.poseidon_t3(b[0], b[1]) },
    t9: {
      nIn: 8,
      call: (b) => {
        // poseidon_t9 takes ONE 256-byte buffer = 8 x 32B concatenated
        const cat = new Uint8Array(256);
        for (let i = 0; i < 8; i++) cat.set(new Uint8Array(b[i]), i * 32);
        return ex.poseidon_t9(cat.buffer);
      },
    },
  };

  function runVec(arityKey, vec) {
    const spec = ARITIES[arityKey];
    if (vec.inputs.length !== spec.nIn) {
      return { ok: false, reason: "input count " + vec.inputs.length + " != " + spec.nIn };
    }
    let inBufs;
    try {
      inBufs = vec.inputs.map((d) => decToBytes32BE(d).buffer);
    } catch (e) {
      return { ok: false, reason: "input encode error: " + String(e) };
    }
    const outBuf = spec.call(inBufs);
    const got = bytes32BEToDec(outBuf);
    return { ok: got === vec.output, got: got, expected: vec.output };
  }

  const result = { arities: {}, canonical: {}, determinism: {}, random_count: randomCount };

  for (const arityKey of ["t2", "t3", "t9"]) {
    const bands = doc.vectors[arityKey];
    const arityResult = {};
    for (const bandName of ["random", "boundary"]) {
      const all = bands[bandName] || [];
      const vecs = bandName === "random" ? all.slice(0, randomCount) : all;
      let passed = 0;
      const mismatches = [];
      for (let i = 0; i < vecs.length; i++) {
        const r = runVec(arityKey, vecs[i]);
        if (r.ok) {
          passed++;
        } else {
          mismatches.push({
            index: i,
            inputs: vecs[i].inputs,
            expected: r.expected,
            got: r.got,
            reason: r.reason,
          });
        }
      }
      arityResult[bandName] = {
        tested: vecs.length,
        passed: passed,
        failed: vecs.length - passed,
        mismatches: mismatches.slice(0, 5),
      };
    }
    result.arities[arityKey] = arityResult;

    // canonical: per_round[0] is the published canonical vector for this arity
    const canon = bands.per_round[0];
    const cr = runVec(arityKey, canon);
    result.canonical[arityKey] = {
      ok: cr.ok,
      inputs: canon.inputs,
      expected: cr.expected,
      got: cr.got,
    };

    // determinism: same input twice -> identical output
    const cr2 = runVec(arityKey, canon);
    result.determinism[arityKey] = cr.got === cr2.got && cr.ok;
  }

  console.log(JSON.stringify(result));
}

main().catch((e) => {
  console.log(JSON.stringify({ error: String((e && e.stack) || e) }));
});
