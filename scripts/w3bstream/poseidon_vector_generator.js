#!/usr/bin/env node
/**
 * poseidon_vector_generator.js -- Phase O4-W3B-POSEIDON-AS Stream P.2
 *
 * Generates canonical Poseidon(BN254) test vectors for the three arities the
 * W3bstream applet `validate_poac_record.ts` needs (per pass-3 revision of
 * wiki/phases/phase_o4_w3b_poseidon_as.md):
 *
 *   t=2  = circomlib Poseidon(1)  -- deviceIdHash    (1 input)
 *   t=3  = circomlib Poseidon(2)  -- nullifierHash   (2 inputs)
 *   t=9  = circomlib Poseidon(8)  -- featureCommitment (8 inputs)
 *
 * TWO INDEPENDENT COMPUTATIONS PER VECTOR -- the parameter-set verification core:
 *   (1) circomlibjs `buildPoseidon()` -- the OPTIMIZED implementation; the
 *       canonical oracle (P.0-verified to produce the published circomlib
 *       BN254 test vectors).
 *   (2) a NAIVE permutation re-implemented in this file from circomlibjs's
 *       own `src/poseidon_reference.js`, driven by the C/M constants in
 *       `circomlibjs/src/poseidon_constants.json`. This naive permutation is
 *       the algorithm that will be ported to AssemblyScript in Stream I.1.
 *
 *   SELF-CHECK (Risk #1 / parameter-set boundary gate): for EVERY generated
 *   vector, naive(inputs) MUST equal opt(inputs). Any mismatch HALTS the
 *   generator with a diagnosis. This proves the constants + the naive
 *   algorithm == circomlibjs's canonical opt hash, BEFORE any AS code is
 *   written against them.
 *
 * PARAMETER-SET VERIFICATION (oracle = the circuit, per Decision-4): the
 * three published canonical circomlib test vectors are asserted explicitly --
 * if circomlibjs reproduces them, its parameter set IS the standard circomlib
 * BN254 Poseidon, which is what the deployed Phase-62 PitlSessionProof
 * verifier (compiled from circomlib's poseidon.circom) uses. `compute_inputs_
 * pitl.js` is NOT used as an oracle -- it is stale (see pass-3 revision note).
 *
 * Output (deterministic -- re-run produces byte-identical files):
 *   poseidon_test_vectors.json     -- vectors + per-round states + metadata
 *   poseidon_test_vectors.sha256   -- SHA-256 of the JSON file (1 line)
 *
 * The vector file's SHA-256 will be pinned by INV-POSEIDON-AS-003 (Stream PV.1).
 *
 * Usage:  node poseidon_vector_generator.js
 *   (run via `npm run vector-gen` from scripts/w3bstream/)
 */

"use strict";

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const { buildPoseidon } = require("circomlibjs");

// circomlibjs 0.1.7's `exports` field only exposes the "." entry -- package
// subpaths like `circomlibjs/src/poseidon_constants.json` are blocked. Resolve
// the package root from the main entry and read the source files directly.
const CIRCOMLIBJS_ROOT = path.join(path.dirname(require.resolve("circomlibjs")), "..");
const poseidonConstants = JSON.parse(
  fs.readFileSync(path.join(CIRCOMLIBJS_ROOT, "src", "poseidon_constants.json"), "utf8")
);
const CIRCOMLIBJS_VERSION = JSON.parse(
  fs.readFileSync(path.join(CIRCOMLIBJS_ROOT, "package.json"), "utf8")
).version;

// -- BN254 scalar field ----------------------------------------------------
const P = 21888242871839275222246405745257275088548364400416034343698204186575808495617n;

// -- Poseidon round counts (from circomlibjs/src/poseidon_reference.js) -----
//   R_F is constant 8; R_P is indexed by [t-2].
const N_ROUNDS_F = 8;
const N_ROUNDS_P = [56, 57, 56, 60, 60, 63, 64, 63, 60, 66, 60, 65, 70, 60, 64, 68];

// -- Arities in scope for validate_poac_record.ts --------------------------
//   key   = label used in the vector file
//   t     = circomlib internal state width (inputs + 1)
//   nIn   = number of inputs (circomlib Poseidon(nIn))
const ARITIES = [
  { key: "t2", t: 2, nIn: 1, purpose: "deviceIdHash" },
  { key: "t3", t: 3, nIn: 2, purpose: "nullifierHash" },
  { key: "t9", t: 9, nIn: 8, purpose: "featureCommitment" },
];

// -- Deterministic seeded RNG ----------------------------------------------
//   randomFieldElement(label, counter) = SHA-256(seed||label||counter) mod P.
//   Fixed seed -> re-run produces byte-identical vector file.
const RNG_SEED = "VAPI-POSEIDON-AS-VECTORS-v1";
function randomFieldElement(label, counter) {
  const h = crypto
    .createHash("sha256")
    .update(`${RNG_SEED}:${label}:${counter}`, "utf8")
    .digest();
  return BigInt("0x" + h.toString("hex")) % P;
}

// -- Constants accessor -- parse hex strings from poseidon_constants.json ----
//   C[t-2] is a FLAT array length t*(R_F+R_P), indexed [r*t + i].
//   M[t-2] is a t-by-t matrix.
function loadConstants(t) {
  const idx = t - 2;
  const Craw = poseidonConstants.C[idx];
  const Mraw = poseidonConstants.M[idx];
  const C = Craw.map((s) => BigInt(s) % P);
  const M = Mraw.map((row) => row.map((s) => BigInt(s) % P));
  const rP = N_ROUNDS_P[idx];
  const totalRounds = N_ROUNDS_F + rP;
  if (C.length !== t * totalRounds) {
    throw new Error(
      `constants length mismatch for t=${t}: C has ${C.length}, expected ${t * totalRounds}`
    );
  }
  if (M.length !== t || M.some((row) => row.length !== t)) {
    throw new Error(`MDS matrix shape mismatch for t=${t}: expected ${t}x${t}`);
  }
  return { C, M, rF: N_ROUNDS_F, rP, totalRounds };
}

// -- Naive Poseidon permutation (port target for AssemblyScript I.1) -------
//   Mirrors circomlibjs/src/poseidon_reference.js exactly:
//     state = [0, ...inputs]
//     per round r: addRoundConstants -> S-box(x^5) -> MDS mix
//     full round  (r < R_F/2 OR r >= R_F/2 + R_P): S-box on ALL state
//     partial round (otherwise):                    S-box on state[0] only
//   Returns { output, roundStates } where roundStates[r] is the state array
//   AFTER round r's MDS mix (used for V.2 per-round differential testing).
function pow5(a) {
  const a2 = (a * a) % P;
  const a4 = (a2 * a2) % P;
  return (a4 * a) % P;
}

function naivePoseidon(inputs, t, C, M, rF, rP) {
  if (inputs.length !== t - 1) {
    throw new Error(`naivePoseidon: expected ${t - 1} inputs for t=${t}, got ${inputs.length}`);
  }
  let state = [0n, ...inputs.map((x) => ((x % P) + P) % P)];
  const totalRounds = rF + rP;
  const roundStates = [];
  for (let r = 0; r < totalRounds; r++) {
    // 1. AddRoundConstants
    state = state.map((a, i) => (a + C[r * t + i]) % P);
    // 2. S-box (x^5)
    if (r < rF / 2 || r >= rF / 2 + rP) {
      state = state.map((a) => pow5(a)); // full round
    } else {
      state[0] = pow5(state[0]); // partial round -- state[0] only
    }
    // 3. MDS mix
    state = state.map((_, i) => {
      let acc = 0n;
      for (let j = 0; j < t; j++) {
        acc = (acc + M[i][j] * state[j]) % P;
      }
      return acc;
    });
    roundStates.push(state.slice());
  }
  return { output: state[0], roundStates };
}

// -- Canonical published circomlib BN254 test vectors ----------------------
//   These are the well-known published values. If circomlibjs reproduces
//   them, its parameter set IS the standard circomlib BN254 Poseidon -- the
//   same one the deployed Phase-62 verifier is compiled from.
const CANONICAL_VECTORS = {
  t2: {
    inputs: [1n],
    expected: 18586133768512220936620570745912940619677854269274689475585506675881198879027n,
  },
  t3: {
    inputs: [1n, 2n],
    expected: 7853200120776062878684798364095072458815029376092732009249414926327459813530n,
  },
  t9: {
    inputs: [1n, 2n, 3n, 4n, 5n, 6n, 7n, 8n],
    expected: 18604317144381847857886385684060986177838410221561136253933256952257712543953n,
  },
};

// -- Boundary-input sets per arity -----------------------------------------
function boundaryInputSets(nIn) {
  const sets = [];
  const fill = (v) => Array(nIn).fill(v);
  sets.push(fill(0n)); // all zero
  sets.push(fill(1n)); // all ones
  sets.push(fill(P - 1n)); // all p-1
  sets.push(fill(2n)); // all twos
  sets.push(fill(P - 2n)); // all p-2
  // sequential ramp 1..nIn
  sets.push(Array.from({ length: nIn }, (_, i) => BigInt(i + 1)));
  // descending ramp
  sets.push(Array.from({ length: nIn }, (_, i) => BigInt(nIn - i)));
  // alternating 0 / p-1
  sets.push(Array.from({ length: nIn }, (_, i) => (i % 2 === 0 ? 0n : P - 1n)));
  // alternating 1 / 0
  sets.push(Array.from({ length: nIn }, (_, i) => (i % 2 === 0 ? 1n : 0n)));
  // single bit set in position 0
  sets.push(fill(0n).map((_, i) => (i === 0 ? 1n : 0n)));
  // single bit set in last position
  sets.push(fill(0n).map((_, i) => (i === nIn - 1 ? 1n : 0n)));
  // powers of two
  sets.push(Array.from({ length: nIn }, (_, i) => 1n << BigInt(i)));
  // high-bit field elements
  sets.push(fill((P - 1n) / 2n));
  sets.push(fill((P + 1n) / 2n % P));
  // 2^128 (limb-boundary stress for the 4xu64 AS impl)
  sets.push(fill(1n << 128n));
  sets.push(fill((1n << 192n) % P));
  sets.push(fill((1n << 255n) % P));
  // mixed limb-boundary
  sets.push(Array.from({ length: nIn }, (_, i) => (1n << BigInt(64 * (i % 4))) % P));
  // p-1 in pos 0, zeros elsewhere
  sets.push(fill(0n).map((_, i) => (i === 0 ? P - 1n : 0n)));
  // small primes
  sets.push(Array.from({ length: nIn }, (_, i) => [2n, 3n, 5n, 7n, 11n, 13n, 17n, 19n][i % 8]));
  // hand-picked: keccak-flavored 32-byte-looking values reduced mod P
  for (let k = 0; k < Math.max(1, 30 - sets.length); k++) {
    sets.push(
      Array.from({ length: nIn }, (_, i) =>
        BigInt("0x" + crypto.createHash("sha256").update(`boundary:${nIn}:${k}:${i}`).digest("hex")) % P
      )
    );
  }
  return sets;
}

// -- Generation parameters -------------------------------------------------
const N_RANDOM = 1000; // random-input vectors per arity
const N_PER_ROUND = 50; // per-round-capture vectors per arity

async function main() {
  const poseidon = await buildPoseidon();
  const F = poseidon.F;

  // opt(inputs) -- canonical circomlibjs hash, returned as a normal BigInt.
  const opt = (inputs) => F.toObject(poseidon(inputs));

  let selfCheckCount = 0;
  const haltOnMismatch = (label, inputs, naiveOut, optOut) => {
    if (naiveOut !== optOut) {
      console.error("");
      console.error("=== P.2 SELF-CHECK FAILURE -- HALT (Risk #1 / parameter-set boundary gate) ===");
      console.error(`  vector:  ${label}`);
      console.error(`  inputs:  [${inputs.map(String).join(", ")}]`);
      console.error(`  naive:   ${naiveOut}`);
      console.error(`  opt:     ${optOut}`);
      console.error("  DIAGNOSIS: the naive permutation (port target for AssemblyScript I.1)");
      console.error("  disagrees with circomlibjs's canonical opt hash. Either the C/M");
      console.error("  constants, the round counts, the S-box, or the round structure in");
      console.error("  naivePoseidon() drifted from circomlibjs/src/poseidon_reference.js.");
      console.error("  No AS implementation work may begin until this clears.");
      process.exit(1);
    }
    selfCheckCount++;
  };

  // -- Parameter-set verification: canonical published test vectors --------
  console.log("=== P.2 PARAMETER-SET VERIFICATION (oracle = circuit-standard circomlib BN254) ===");
  for (const { key, t, nIn } of ARITIES) {
    const cv = CANONICAL_VECTORS[key];
    const optOut = opt(cv.inputs);
    const { C, M, rF, rP } = loadConstants(t);
    const naiveOut = naivePoseidon(cv.inputs, t, C, M, rF, rP).output;
    const optMatch = optOut === cv.expected;
    const naiveMatch = naiveOut === cv.expected;
    console.log(
      `  ${key} (Poseidon(${nIn})): opt ${optMatch ? "MATCH" : "MISMATCH"} / naive ${
        naiveMatch ? "MATCH" : "MISMATCH"
      } vs published canonical vector`
    );
    if (!optMatch || !naiveMatch) {
      console.error("");
      console.error(`=== P.2 PARAMETER-SET VERIFICATION FAILED for ${key} -- HALT ===`);
      console.error(`  published canonical: ${cv.expected}`);
      console.error(`  circomlibjs opt:     ${optOut}`);
      console.error(`  naive (C/M):         ${naiveOut}`);
      console.error("  circomlibjs's parameter set does NOT match the standard circomlib");
      console.error("  BN254 Poseidon. The deployed Phase-62 verifier is compiled from");
      console.error("  circomlib's poseidon.circom -- this generator cannot serve as a");
      console.error("  reference oracle. Investigate before any I.* work.");
      process.exit(1);
    }
  }
  console.log("  PARAMETER-SET VERIFICATION: PASS -- circomlibjs == standard circomlib BN254 Poseidon");
  console.log("");

  // -- Generate vectors per arity ------------------------------------------
  const arityMeta = {};
  const vectors = {};

  for (const { key, t, nIn, purpose } of ARITIES) {
    const { C, M, rF, rP, totalRounds } = loadConstants(t);
    arityMeta[key] = {
      circomlib: `Poseidon(${nIn})`,
      internal_state_width_t: t,
      n_inputs: nIn,
      r_f: rF,
      r_p: rP,
      total_rounds: totalRounds,
      purpose,
    };

    const random = [];
    const boundary = [];
    const perRound = [];

    // (a) random-input vectors
    for (let n = 0; n < N_RANDOM; n++) {
      const inputs = Array.from({ length: nIn }, (_, i) =>
        randomFieldElement(`${key}:random:${n}`, i)
      );
      const naiveOut = naivePoseidon(inputs, t, C, M, rF, rP).output;
      const optOut = opt(inputs);
      haltOnMismatch(`${key}/random/${n}`, inputs, naiveOut, optOut);
      random.push({ inputs: inputs.map(String), output: optOut.toString() });
    }

    // (b) boundary-input vectors
    const bsets = boundaryInputSets(nIn);
    for (let n = 0; n < bsets.length; n++) {
      const inputs = bsets[n];
      const naiveOut = naivePoseidon(inputs, t, C, M, rF, rP).output;
      const optOut = opt(inputs);
      haltOnMismatch(`${key}/boundary/${n}`, inputs, naiveOut, optOut);
      boundary.push({ inputs: inputs.map(String), output: optOut.toString() });
    }

    // (c) per-round-capture vectors -- first the canonical vector, then 49 seeded
    {
      const cv = CANONICAL_VECTORS[key];
      const { output, roundStates } = naivePoseidon(cv.inputs, t, C, M, rF, rP);
      haltOnMismatch(`${key}/per_round/canonical`, cv.inputs, output, opt(cv.inputs));
      perRound.push({
        inputs: cv.inputs.map(String),
        output: output.toString(),
        round_states: roundStates.map((s) => s.map(String)),
      });
    }
    for (let n = 0; n < N_PER_ROUND - 1; n++) {
      const inputs = Array.from({ length: nIn }, (_, i) =>
        randomFieldElement(`${key}:per_round:${n}`, i)
      );
      const { output, roundStates } = naivePoseidon(inputs, t, C, M, rF, rP);
      haltOnMismatch(`${key}/per_round/${n}`, inputs, output, opt(inputs));
      perRound.push({
        inputs: inputs.map(String),
        output: output.toString(),
        round_states: roundStates.map((s) => s.map(String)),
      });
    }

    vectors[key] = { random, boundary, per_round: perRound };
    console.log(
      `  ${key}: ${random.length} random + ${boundary.length} boundary + ${perRound.length} per-round vectors`
    );
  }

  // -- Assemble output -----------------------------------------------------
  const out = {
    metadata: {
      generator: "scripts/w3bstream/poseidon_vector_generator.js",
      phase: "Phase O4-W3B-POSEIDON-AS Stream P.2",
      schema: "vapi-poseidon-test-vectors-v1",
      determinism: "seeded -- re-run from clean state produces a byte-identical file",
      rng_seed: RNG_SEED,
      circomlibjs_version: CIRCOMLIBJS_VERSION,
      bn254_prime: P.toString(),
      reference_algorithm: "circomlibjs/src/poseidon_reference.js (naive permutation)",
      reference_constants: "circomlibjs/src/poseidon_constants.json (C, M)",
      parameter_set_verification:
        "circomlibjs reproduces the published canonical circomlib BN254 test vectors for " +
        "Poseidon(1)/Poseidon(2)/Poseidon(8); naive permutation (the AssemblyScript port " +
        "target) self-checked == circomlibjs opt hash on every vector",
      single_reference_caveat:
        "AMBER path (P.0 confirmed): circomlibjs is the single reference. No independent " +
        "2nd reference was available in the agent runtime. V.3 cross-reference triangulation " +
        "is SKIPPED; V.1 boundary-input coverage + V.2 per-round differential are the " +
        "compensating discipline.",
      arities: arityMeta,
      counts: {
        random_per_arity: N_RANDOM,
        boundary_per_arity_note: "~25-30 (see vectors.<arity>.boundary.length)",
        per_round_per_arity: N_PER_ROUND,
      },
      self_checks_passed: selfCheckCount,
    },
    vectors,
  };

  const json = JSON.stringify(out);
  const outPath = path.join(__dirname, "poseidon_test_vectors.json");
  const shaPath = path.join(__dirname, "poseidon_test_vectors.sha256");
  fs.writeFileSync(outPath, json, "utf8");

  const sha = crypto.createHash("sha256").update(json, "utf8").digest("hex");
  fs.writeFileSync(shaPath, sha + "\n", "utf8");

  console.log("");
  console.log(`  self-checks passed (naive == opt): ${selfCheckCount}`);
  console.log(`  output: ${outPath} (${Buffer.byteLength(json, "utf8")} bytes)`);
  console.log(`  SHA-256: ${sha}`);
  console.log("");
  console.log("=== P.2 vector generation COMPLETE ===");
}

main().catch((err) => {
  console.error("P.2 generator error:", err);
  process.exit(1);
});
