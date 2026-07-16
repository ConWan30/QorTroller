/*
 * UC-3 — Buyer-category ZK PROVER (the missing half).
 *
 * The verifier has been LIVE on-chain (VAPIBuyerCategoryVerifier) and mirrored bridge-side
 * (zk_buyer_verifier.py, read-only staticcall) since Phase 238; the ceremony is done
 * (_final.zkey + verification_key.json committed). What was missing is the PROVER: given a
 * buyer's Curator-issued credential, generate the Groth16 proof the verifier accepts. This is it.
 *
 * A buyer proves "I hold an unexpired Curator credential for category C" WITHOUT revealing the
 * credential — the category-gated selling mechanism (UC-3) for certified-human corpora.
 *
 * Circuit (VAPIBuyerCategoryVerifier.circom):
 *   public : claimedCategory, currentTimestamp, credentialCommitment, nullifierHash
 *   private: buyerDID, credentialNonce, categoryId, issuedAt, expiresAt
 *   C1  categoryId === claimedCategory
 *   C1b categoryId in [1,4]                                    (INV-BUY-001 FROZEN enum)
 *   nx  currentTimestamp < expiresAt                          (unexpired)
 *   C3  credentialCommitment === Poseidon(5)(DID,cat,issued,expires,nonce)
 *   C4  nullifierHash        === Poseidon(2)(DID,nonce)
 *   pubSignals (output-first): [valid=1, claimedCategory, currentTimestamp, credentialCommitment, nullifierHash]
 *
 * RAILS: no chain write (verify is a staticcall that already exists); no new ceremony (reuse the
 * committed zkey/vkey); fail-CLOSED on category out of [1,4] or expired credential. Acceptance =
 * snarkjs fullProve -> LOCAL groth16 verify against the committed vkey (grok round-1 primary test);
 * on-chain submission is out of scope.
 *
 * HONEST CEILING (grok round-2): this proves PREIMAGE KNOWLEDGE of a credential for category C
 * (C1/C1b/notExpired/C3/C4) — it does NOT prove "a Curator ISSUED this credential". A buyer could
 * invent (DID,cat,nonce,issued,expires), compute the commitment, and prove category C. Trust must
 * anchor OUTSIDE the proof: (1) the Curator-published membership of credentialCommitment, (2) the
 * nullifier not already spent, (3) currentTimestamp set by the verifier not the buyer. Today
 * VAPIBuyerRegistry stores buyerDID + evidenceHash (not the Poseidon commitment), so option-(b)
 * membership is NOT wired end-to-end — that is an ISSUANCE/composability gate, not a prover defect.
 * The prover alone is NOT marketplace authorization; it is the (previously missing) PROVE half.
 *
 * Exit codes: 0 ok+verified | 2 deps missing | 3 bad input | 4 category out of [1,4] |
 *             5 expired | 6 claimed!=actual | 7 fullProve/verify failed
 *
 * Usage:
 *   node prove_buyer_category.js                       # golden fixture (self-test)
 *   node prove_buyer_category.js <credential.json>     # real credential
 *   node prove_buyer_category.js <credential.json> --out <dir>   # also write proof.json/public.json
 */
"use strict";
const fs = require("fs");
const path = require("path");

const DIR = __dirname;
const WASM = path.join(DIR, "VAPIBuyerCategoryVerifier_js", "VAPIBuyerCategoryVerifier.wasm");
const ZKEY = path.join(DIR, "VAPIBuyerCategoryVerifier_final.zkey");
const VKEY = path.join(DIR, "VAPIBuyerCategoryVerifier_verification_key.json");

// The Hardhat golden fixture (contracts/test/VAPIBuyerCategoryVerifier.test.js) — a self-test credential.
const GOLDEN = {
  buyerDID: "12345678901234567890",
  categoryId: 3,            // ESPORTS
  claimedCategory: 3,
  issuedAt: 1700000000,
  expiresAt: 1800000000,
  currentTimestamp: 1750000000,
  credentialNonce: "98765432109876543210",
};

function die(code, msg) { process.stderr.write("ERROR: " + msg + "\n"); process.exit(code); }

let snarkjs, buildPoseidon;
try {
  snarkjs = require("snarkjs");
  ({ buildPoseidon } = require("circomlibjs"));
} catch (e) {
  die(2, "deps missing (snarkjs / circomlibjs). Run `npm install` in contracts/. " + e.message);
}
for (const p of [WASM, ZKEY, VKEY]) {
  if (!fs.existsSync(p)) die(2, "circuit artifact missing: " + p + " (compile the circuit first).");
}

function loadCredential(argv) {
  if (argv.length === 0 || argv[0].startsWith("--")) return { ...GOLDEN, _golden: true };
  let raw;
  try { raw = fs.readFileSync(argv[0], "utf8"); } catch (e) { die(3, "cannot read " + argv[0]); }
  let c;
  try { c = JSON.parse(raw); } catch (e) { die(3, "credential not valid JSON: " + e.message); }
  // claimedCategory defaults to the true categoryId (the honest disclosure)
  if (c.claimedCategory === undefined) c.claimedCategory = c.categoryId;
  return c;
}

async function main() {
  const argv = process.argv.slice(2);
  const cred = loadCredential(argv);
  let outDir = null;
  for (let i = 0; i < argv.length; i++) if (argv[i] === "--out" && argv[i + 1]) outDir = argv[i + 1];

  const need = ["buyerDID", "categoryId", "issuedAt", "expiresAt", "currentTimestamp", "credentialNonce"];
  for (const k of need) if (cred[k] === undefined) die(3, "credential missing field: " + k);

  const cat = Number(cred.categoryId);
  const claimed = Number(cred.claimedCategory);
  // fail-CLOSED rails (the circuit enforces these too; we reject BEFORE proving for a clean error)
  if (!(cat >= 1 && cat <= 4)) die(4, `categoryId ${cat} outside FROZEN enum [1,4] (INV-BUY-001)`);
  if (claimed !== cat) die(6, `claimedCategory ${claimed} != categoryId ${cat} (C1 would fail)`);
  if (!(Number(cred.currentTimestamp) < Number(cred.expiresAt)))
    die(5, `credential expired: currentTimestamp ${cred.currentTimestamp} >= expiresAt ${cred.expiresAt}`);

  const poseidon = await buildPoseidon();
  const F = poseidon.F;
  const dec = (v) => BigInt(v).toString();
  const pos = (arr) => F.toObject(poseidon(arr.map((x) => BigInt(x)))).toString();

  // Poseidon commitments — order EXACTLY matches the circuit (grok round-1 footgun #1).
  const credentialCommitment = pos([cred.buyerDID, cred.categoryId, cred.issuedAt, cred.expiresAt, cred.credentialNonce]);
  const nullifierHash = pos([cred.buyerDID, cred.credentialNonce]);

  const input = {
    claimedCategory: dec(cred.claimedCategory),
    currentTimestamp: dec(cred.currentTimestamp),
    credentialCommitment,
    nullifierHash,
    buyerDID: dec(cred.buyerDID),
    credentialNonce: dec(cred.credentialNonce),
    categoryId: dec(cred.categoryId),
    issuedAt: dec(cred.issuedAt),
    expiresAt: dec(cred.expiresAt),
  };

  let proof, publicSignals;
  try {
    ({ proof, publicSignals } = await snarkjs.groth16.fullProve(input, WASM, ZKEY));
  } catch (e) {
    die(7, "fullProve failed: " + e.message);
  }

  const vkey = JSON.parse(fs.readFileSync(VKEY, "utf8"));
  const ok = await snarkjs.groth16.verify(vkey, publicSignals, proof);
  // pubSignals output-first: [valid, claimedCategory, currentTimestamp, credentialCommitment, nullifierHash]
  const validOutput = publicSignals[0] === "1";
  const pubOk = publicSignals[1] === input.claimedCategory
    && publicSignals[2] === input.currentTimestamp   // grok round-2: belt+suspenders on the full layout
    && publicSignals[3] === credentialCommitment
    && publicSignals[4] === nullifierHash;

  const result = {
    ok: Boolean(ok && validOutput && pubOk),
    verified_local: Boolean(ok),
    valid_output: validOutput,
    public_layout_ok: pubOk,
    category: cat,
    golden: Boolean(cred._golden),
    credential_commitment: credentialCommitment,
    nullifier_hash: nullifierHash,
    public_signals: publicSignals,
  };

  if (outDir) {
    fs.mkdirSync(outDir, { recursive: true });
    fs.writeFileSync(path.join(outDir, "proof.json"), JSON.stringify(proof, null, 1));
    fs.writeFileSync(path.join(outDir, "public.json"), JSON.stringify(publicSignals, null, 1));
    result.out_dir = outDir;
  }
  process.stdout.write(JSON.stringify(result, null, 1) + "\n");
  if (!result.ok) die(7, "proof did not verify against the committed vkey (or public layout mismatch)");
  process.exit(0);
}

main().catch((e) => die(7, "unexpected: " + (e && e.message ? e.message : e)));
