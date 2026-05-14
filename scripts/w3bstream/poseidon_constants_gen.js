#!/usr/bin/env node
/**
 * poseidon_constants_gen.js -- Phase O4-W3B-POSEIDON-AS Stream I.1b
 *
 * Emits scripts/w3bstream/poseidon_constants.generated.ts -- the Poseidon(BN254)
 * round constants (C) and MDS matrices (M) for the three arities the VAPI
 * W3bstream applet needs, as AssemblyScript `const` data ready for the
 * poseidon_bn254.ts permutation.
 *
 *   t=2  = circomlib Poseidon(1)  -- deviceIdHash      (1 input)
 *   t=3  = circomlib Poseidon(2)  -- nullifierHash     (2 inputs)
 *   t=9  = circomlib Poseidon(8)  -- featureCommitment (8 inputs)
 *
 * Source of truth: circomlibjs/src/poseidon_constants.json. circomlibjs 0.1.7's
 * `exports` field only exposes the "." entry -- package subpaths are blocked,
 * so the package root is resolved from the main entry (the same pattern
 * poseidon_vector_generator.js already uses).
 *
 * Each field element from poseidon_constants.json is a hex string; this script
 * decodes it to a 4xu64 little-endian limb tuple (the internal representation
 * used by poseidon_bn254.ts), reduced mod p. The emitted file is a flat
 * StaticArray<u64>:
 *   - C arrays: length t*(R_F+R_P)*4 (one field element = 4 limbs), indexed
 *     as C[(r*t + i)*4 + limb].
 *   - M arrays: length t*t*4, indexed as M[(i*t + j)*4 + limb].
 *
 * Deterministic: re-run from clean state produces a byte-identical
 * poseidon_constants.generated.ts. Pure ASCII output.
 *
 * Usage:  node poseidon_constants_gen.js
 *   (run via `npm run constants-gen` from scripts/w3bstream/)
 */

"use strict";

const fs = require("fs");
const path = require("path");

// circomlibjs 0.1.7 `exports` blocks subpaths -- resolve package root from main.
const CIRCOMLIBJS_ROOT = path.join(path.dirname(require.resolve("circomlibjs")), "..");
const poseidonConstants = JSON.parse(
  fs.readFileSync(path.join(CIRCOMLIBJS_ROOT, "src", "poseidon_constants.json"), "utf8")
);
const CIRCOMLIBJS_VERSION = JSON.parse(
  fs.readFileSync(path.join(CIRCOMLIBJS_ROOT, "package.json"), "utf8")
).version;

// BN254 scalar field prime.
const P = 21888242871839275222246405745257275088548364400416034343698204186575808495617n;

// Poseidon round counts (from circomlibjs/src/poseidon_reference.js).
const N_ROUNDS_F = 8;
const N_ROUNDS_P = [56, 57, 56, 60, 60, 63, 64, 63, 60, 66, 60, 65, 70, 60, 64, 68];

// Arities in scope (per pass-3 revision of the phase plan).
const ARITIES = [
  { key: "T2", t: 2, nIn: 1, purpose: "deviceIdHash" },
  { key: "T3", t: 3, nIn: 2, purpose: "nullifierHash" },
  { key: "T9", t: 9, nIn: 8, purpose: "featureCommitment" },
];

const MASK64 = (1n << 64n) - 1n;

// Decode a field element (BigInt) to 4 little-endian u64 limbs as hex strings.
function toLimbs(v) {
  let x = ((v % P) + P) % P;
  const limbs = [];
  for (let i = 0; i < 4; i++) {
    limbs.push("0x" + (x & MASK64).toString(16).padStart(16, "0"));
    x >>= 64n;
  }
  return limbs;
}

// Emit a StaticArray<u64> literal, 4 limbs per line for readability.
function emitArray(name, flatLimbs) {
  const lines = [];
  lines.push(`export const ${name}: StaticArray<u64> = [`);
  for (let i = 0; i < flatLimbs.length; i += 4) {
    const grp = flatLimbs.slice(i, i + 4).join(", ");
    lines.push(`  ${grp},`);
  }
  lines.push("];");
  return lines.join("\n");
}

function main() {
  const out = [];
  out.push("/**");
  out.push(" * poseidon_constants.generated.ts -- Phase O4-W3B-POSEIDON-AS Stream I.1b");
  out.push(" *");
  out.push(" * GENERATED FILE -- do not hand-edit. Regenerate via:");
  out.push(" *   node scripts/w3bstream/poseidon_constants_gen.js");
  out.push(" *");
  out.push(" * Poseidon(BN254) round constants (C) and MDS matrices (M) for the three");
  out.push(" * arities the VAPI W3bstream applet needs, REPLICATED from");
  out.push(" * circomlibjs/src/poseidon_constants.json (circomlibjs " + CIRCOMLIBJS_VERSION + ").");
  out.push(" *");
  out.push(" *   t=2  Poseidon(1)  deviceIdHash       R_F=8  R_P=56");
  out.push(" *   t=3  Poseidon(2)  nullifierHash      R_F=8  R_P=57");
  out.push(" *   t=9  Poseidon(8)  featureCommitment  R_F=8  R_P=63");
  out.push(" *");
  out.push(" * Each field element is stored as 4 little-endian u64 limbs (the internal");
  out.push(" * representation used by poseidon_bn254.ts).");
  out.push(" *   C_T<n>: flat, length t*(R_F+R_P)*4; element (r,i) at (r*t + i)*4 + limb.");
  out.push(" *   M_T<n>: flat, length t*t*4;         element (i,j) at (i*t + j)*4 + limb.");
  out.push(" *");
  out.push(" * BN254 prime p =");
  out.push(" *   21888242871839275222246405745257275088548364400416034343698204186575808495617");
  out.push(" */");
  out.push("");

  for (const { key, t, nIn, purpose } of ARITIES) {
    const idx = t - 2;
    const Craw = poseidonConstants.C[idx];
    const Mraw = poseidonConstants.M[idx];
    const rP = N_ROUNDS_P[idx];
    const totalRounds = N_ROUNDS_F + rP;

    if (Craw.length !== t * totalRounds) {
      throw new Error(
        `C length mismatch for t=${t}: got ${Craw.length}, expected ${t * totalRounds}`
      );
    }
    if (Mraw.length !== t || Mraw.some((row) => row.length !== t)) {
      throw new Error(`M shape mismatch for t=${t}: expected ${t}x${t}`);
    }

    // C: flat [r*t + i] -> 4 limbs each.
    const cFlat = [];
    for (let k = 0; k < Craw.length; k++) {
      const limbs = toLimbs(BigInt(Craw[k]));
      for (let l = 0; l < 4; l++) cFlat.push(limbs[l]);
    }
    // M: flat [i*t + j] -> 4 limbs each.
    const mFlat = [];
    for (let i = 0; i < t; i++) {
      for (let j = 0; j < t; j++) {
        const limbs = toLimbs(BigInt(Mraw[i][j]));
        for (let l = 0; l < 4; l++) mFlat.push(limbs[l]);
      }
    }

    out.push(
      `// --- t=${t} (circomlib Poseidon(${nIn}) -- ${purpose}); R_F=${N_ROUNDS_F} R_P=${rP} ---`
    );
    out.push(emitArray(`C_${key}`, cFlat));
    out.push("");
    out.push(emitArray(`M_${key}`, mFlat));
    out.push("");
  }

  const text = out.join("\n");
  const outPath = path.join(__dirname, "poseidon_constants.generated.ts");
  fs.writeFileSync(outPath, text, "utf8");

  console.log("poseidon_constants_gen.js: wrote " + outPath);
  console.log("  circomlibjs version: " + CIRCOMLIBJS_VERSION);
  for (const { key, t, nIn } of ARITIES) {
    const idx = t - 2;
    const rP = N_ROUNDS_P[idx];
    const totalRounds = N_ROUNDS_F + rP;
    console.log(
      `  ${key}: Poseidon(${nIn}) t=${t}  C ${t * totalRounds} elems (${t * totalRounds * 4} limbs)  M ${t}x${t} (${t * t * 4} limbs)`
    );
  }
}

main();
