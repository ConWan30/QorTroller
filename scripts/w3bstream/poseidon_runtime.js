#!/usr/bin/env node
/**
 * poseidon_runtime.js -- Phase O4-W3B-POSEIDON-AS Streams V.1 + V.2
 *
 * Node.js WASM invocation helper. Loads an asc-compiled Poseidon(BN254) module
 * via its asc-generated ESM loader and verifies the AssemblyScript
 * implementation (Streams I.1a/I.1b) against the committed test-vector corpus
 * (poseidon_test_vectors.json, Stream P.2).
 *
 * Used by bridge/tests/test_w3bstream_poseidon_as.py as a subprocess: ONE
 * invocation per mode runs the full verification band and emits a single JSON
 * result object to stdout that the pytest tests assert against.
 *
 * Two modes:
 *
 *   --mode final  (default; V.1)
 *     Loads dist/poseidon_bn254.{js,wasm}. For each arity {t2,t3,t9}: feeds
 *     N random + all boundary vectors, asserts final-output byte-identical to
 *     the circomlibjs reference. Plus the 3 published circomlib BN254
 *     canonical vectors and per-arity determinism.
 *
 *   --mode per-round  (V.2)
 *     Loads dist/poseidon_bn254_debug.{js,wasm}. For each arity: feeds the 50
 *     per_round vectors, splits the densely-packed per-round-state output
 *     buffer into (R_F+R_P) x t field elements, and asserts EVERY intermediate
 *     round state is byte-identical to the circomlibjs per-round states stored
 *     in the vector file. Catches MDS / round-constant / S-box bugs whose
 *     error cancels by the final output but corrupts intermediate state.
 *
 * This is the V.1/V.2 verification gate -- the INDEPENDENT check that the AS
 * implementation produces output byte-identical to the circomlibjs reference.
 * Any mismatch is a hard failure.
 *
 * Usage:  node poseidon_runtime.js <vector-file> [--mode final|per-round] [--random-count N]
 *   --mode          : final (default) or per-round
 *   --random-count N : final-mode only; how many random-band vectors per arity
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

// circomlib BN254 round structure -- R_F constant 8; R_P + t per arity.
// (These mirror poseidon_bn254.ts R_P_T* / arity constants exactly.)
const ARITY_META = {
  t2: { t: 2, nIn: 1, rF: 8, rP: 56 },
  t3: { t: 3, nIn: 2, rF: 8, rP: 57 },
  t9: { t: 9, nIn: 8, rF: 8, rP: 63 },
};

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

// 32-byte big-endian buffer (or sub-slice) -> decimal string
function bytes32BEToDec(u8) {
  let v = 0n;
  for (let i = 0; i < u8.length; i++) v = (v << 8n) | BigInt(u8[i]);
  return v.toString();
}

// Load + instantiate an asc-compiled module by base name (dist/<base>.{js,wasm}).
async function loadModule(base) {
  const wasmPath = path.join(HERE, "dist", base + ".wasm");
  const loaderPath = path.join(HERE, "dist", base + ".js");
  if (!fs.existsSync(wasmPath) || !fs.existsSync(loaderPath)) {
    throw new Error(
      "WASM artifacts not found -- compile " + base + ".ts first. Missing: " +
        (fs.existsSync(wasmPath) ? loaderPath : wasmPath)
    );
  }
  const loader = await import(pathToFileURL(loaderPath).href);
  const wasmModule = await WebAssembly.compile(fs.readFileSync(wasmPath));
  return await loader.instantiate(wasmModule, {});
}

// --- final-output mode (V.1) ------------------------------------------------

async function runFinalMode(doc, randomCount) {
  const ex = await loadModule("poseidon_bn254");

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
    const got = bytes32BEToDec(new Uint8Array(outBuf));
    return { ok: got === vec.output, got: got, expected: vec.output };
  }

  const result = { mode: "final", arities: {}, canonical: {}, determinism: {}, random_count: randomCount };

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

  return result;
}

// --- per-round mode (V.2) ---------------------------------------------------

async function runPerRoundMode(doc) {
  const ex = await loadModule("poseidon_bn254_debug");

  const ARITIES = {
    t2: { nIn: 1, call: (b) => ex.poseidon_t2_debug(b[0]) },
    t3: { nIn: 2, call: (b) => ex.poseidon_t3_debug(b[0], b[1]) },
    t9: {
      nIn: 8,
      call: (b) => {
        const cat = new Uint8Array(256);
        for (let i = 0; i < 8; i++) cat.set(new Uint8Array(b[i]), i * 32);
        return ex.poseidon_t9_debug(cat.buffer);
      },
    },
  };

  const result = { mode: "per-round", arities: {} };

  for (const arityKey of ["t2", "t3", "t9"]) {
    const meta = ARITY_META[arityKey];
    const totalRounds = meta.rF + meta.rP;
    const t = meta.t;
    const vecs = doc.vectors[arityKey].per_round || [];

    let vectorsTested = 0;
    let roundStatesChecked = 0;
    let roundStatesPassed = 0;
    let finalOutputMatches = 0;
    const mismatches = [];

    for (let vi = 0; vi < vecs.length; vi++) {
      const vec = vecs[vi];
      if (vec.inputs.length !== meta.nIn) {
        mismatches.push({ vector: vi, reason: "input count " + vec.inputs.length + " != " + meta.nIn });
        continue;
      }
      if (!Array.isArray(vec.round_states) || vec.round_states.length !== totalRounds) {
        mismatches.push({ vector: vi, reason: "round_states length mismatch" });
        continue;
      }
      const inBufs = vec.inputs.map((d) => decToBytes32BE(d).buffer);
      const outBuf = ARITIES[arityKey].call(inBufs);
      const outU8 = new Uint8Array(outBuf);
      const expectedBytes = totalRounds * t * 32;
      if (outU8.length !== expectedBytes) {
        mismatches.push({
          vector: vi,
          reason: "debug output buffer is " + outU8.length + " bytes, expected " + expectedBytes,
        });
        continue;
      }
      vectorsTested++;

      // split densely-packed buffer: round r, element i at (r*t + i)*32
      let vectorOk = true;
      for (let r = 0; r < totalRounds; r++) {
        for (let i = 0; i < t; i++) {
          roundStatesChecked++;
          const off = (r * t + i) * 32;
          const got = bytes32BEToDec(outU8.subarray(off, off + 32));
          const expected = vec.round_states[r][i];
          if (got === expected) {
            roundStatesPassed++;
          } else {
            vectorOk = false;
            if (mismatches.length < 8) {
              mismatches.push({
                vector: vi,
                round: r,
                element: i,
                expected: expected,
                got: got,
              });
            }
          }
        }
      }
      // final-round state[0] must equal the declared output (closes the loop
      // between the per-round path and the V.1 final-output path)
      const finalOff = ((totalRounds - 1) * t + 0) * 32;
      const finalGot = bytes32BEToDec(outU8.subarray(finalOff, finalOff + 32));
      if (finalGot === vec.output) finalOutputMatches++;
      else if (vectorOk && mismatches.length < 8) {
        mismatches.push({
          vector: vi,
          round: "final",
          element: 0,
          expected: vec.output,
          got: finalGot,
          reason: "final state[0] != declared output",
        });
      }
    }

    result.arities[arityKey] = {
      total_rounds: totalRounds,
      state_width: t,
      vectors_tested: vectorsTested,
      round_states_checked: roundStatesChecked,
      round_states_passed: roundStatesPassed,
      round_states_failed: roundStatesChecked - roundStatesPassed,
      final_output_matches: finalOutputMatches,
      mismatches: mismatches.slice(0, 8),
    };
  }

  return result;
}

async function main() {
  const vectorFile = process.argv[2];
  let mode = "final";
  let randomCount = 100;
  const modeIdx = process.argv.indexOf("--mode");
  if (modeIdx >= 0 && process.argv[modeIdx + 1]) mode = process.argv[modeIdx + 1];
  const rcIdx = process.argv.indexOf("--random-count");
  if (rcIdx >= 0 && process.argv[rcIdx + 1]) randomCount = parseInt(process.argv[rcIdx + 1], 10);

  if (!vectorFile || !fs.existsSync(vectorFile)) {
    console.log(JSON.stringify({ error: "vector file not found: " + String(vectorFile) }));
    return;
  }
  const doc = JSON.parse(fs.readFileSync(vectorFile, "utf8"));

  let result;
  if (mode === "per-round") {
    result = await runPerRoundMode(doc);
  } else if (mode === "final") {
    result = await runFinalMode(doc, randomCount);
  } else {
    console.log(JSON.stringify({ error: "unknown --mode: " + mode }));
    return;
  }
  console.log(JSON.stringify(result));
}

main().catch((e) => {
  console.log(JSON.stringify({ error: String((e && e.stack) || e) }));
});
