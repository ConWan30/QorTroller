# Plan: Phase O4-W3B-POSEIDON-AS — close POSEIDON_HASH delta via AssemblyScript Poseidon(BN254)

**Plan status:** DRAFT (awaiting operator approval via ExitPlanMode)
**Date:** 2026-05-13
**Anchor commit:** HEAD `40da5755` (post-frontend-operator-console)
**Author:** VAPI Principal Architect
**Canonical location:** `wiki/phases/phase_o4_w3b_poseidon_as.md` (repository-tracked as of pass-2 revision 2026-05-14). The home-directory plan file `~/.claude/plans/rustling-soaring-rossum.md` is retained as an operational scratchpad per operator preference; this repository-tracked copy is canonical for execution reference.
**Supersedes:** This plan's content previously occupied the home-directory plan file `~/.claude/plans/rustling-soaring-rossum.md`. The prior occupant of that file — the v4 §15 backlog autonomous completion plan — was substantively executed via prior agent dispatches (commits `020644ba` / `6accdf85` / `849e9e34` / `dfdeaf2b` / `084b0f17` / `48e177e5`).
**Pass-3 revision (2026-05-14):** Arity-set correction `{t=3,t=6,t=9}` → `{t=2,t=3,t=9}` surfaced during P.2 exploration (Risk #7 fired + caught at the P.2 boundary as designed). P.1 already executed + committed (`14b2fa28`); P.0 resolved to AMBER (operator-confirmed). See the **Pass-3 revision note** section below for the full finding + rationale.

---

## Pass-3 revision note (2026-05-14)

P.1 executed and committed (`14b2fa28`); P.0 resolved to **AMBER** (operator-confirmed — no quick BN254-compatible 2nd Poseidon reference; circomlibjs is the single reference). P.2's *exploration phase* then surfaced a plan-scope finding **before any vector-generation code was written** — Risk #7 ("Phase 62 ZK invariant interpretation wrong (arity)") firing and being caught at the P.2 boundary exactly as the safety discipline designed.

**Finding:** the plan's Poseidon arity set `{t=3, t=6, t=9}` was mis-derived. Read directly from the authoritative circuit sources:
- `PitlSessionProof.circom:106` — `featureCommitment = Poseidon(8)` → **t=9** ✓ (plan correct)
- `PitlSessionProof.circom` C5 — `nullifierHash = Poseidon(2)(deviceIdHash, epoch)` → **t=3** ✓ (plan correct)
- `compute_inputs_pitl.js:73` — `deviceIdHash = Poseidon(1)(deviceId)` → **t=2** ✗ (plan MISSED this — the applet must derive `deviceIdHash` from the raw `keccak256(pubkey)` PoAC `OFF_DEVICE_ID` field before it can compute `nullifierHash`)
- `ZKSepProof.circom:166` — `Poseidon(5)` → t=6 — belongs to `validate_zk_sepproof.ts`, which has **no active POSEIDON_HASH stub** (only a descriptive wire-format comment). W.2 is therefore a **confirmed no-op** and **t=6 drops out of scope entirely**.

**Correction (a clean swap, not an expansion):** arity set `{t=3, t=6, t=9}` → **`{t=2, t=3, t=9}`** — still 3 arities. `t=6` (W.2-secondary) is replaced by `t=2` (Poseidon(1), deviceIdHash, primary applet).

**Decision-4 note:** `compute_inputs_pitl.js` (header: "Phase 26") computes `featureCommitment = Poseidon(7)(scaledFeatures)` and never reads `inferenceCodeFromBody` — it is **stale** relative to the Phase-62 deployed circuit's `Poseidon(8)`. `pitl_prover.py._real_proof` calls it, so the real-proof path appears non-functional (the circuit's C1 constraint would reject). **This is a pre-existing protocol bug, outside this plan's scope** — filed separately for operator triage; NOT folded into Phase O4-W3B-POSEIDON-AS. The consequence for this plan: **the circuit source — not `compute_inputs_pitl.js` — is the parameter-set oracle.** (The mock path `pitl_prover.py._mock_proof` IS Phase-62-correct; only the real path's helper is stale. Whether the real path is exercised in production is itself unconfirmed — if `dry_run=True` and mock is the only path used, the bug is latent, not active.)

**AMBER test-count reconciliation:** P.0's confirmed AMBER outcome means V.3 (cross-reference triangulation) is SKIPPED. The plan's `+24` / `≥3752` headline was the GREEN figure. Corrected to the confirmed-AMBER figure: **`+22` / `≥3750`** (V.1=10 + V.2=6 + T.1=6; V.3=2 skipped). [This 4th reconciliation is beyond the operator's three explicitly-scoped pass-3 items — applied because P.0's confirmed AMBER makes the GREEN headline stale; flag to revert if preferred.]

Authoritative source files for the arity correction: `contracts/circuits/PitlSessionProof.circom`, `contracts/circuits/ZKSepProof.circom`, `bridge/zk_artifacts/compute_inputs_pitl.js`. No FROZEN region modified — the circuits are READ, never edited.

---

## Context — why this change is being made

The W3bstream applet `scripts/w3bstream/validate_poac_record.ts` currently sits at audit verdict **STUB_DEPS_BLOCKED** (commit `084b0f17`). Three crypto-integration deltas closed via Stream A.PARTIAL (`48e177e5`): `ABI_ENCODER` + `CONSENT_RETURN_DATA` + `DEVICE_ID_TO_GAMER`. Two remain explicitly deferred under Hard Rule:

- **POSEIDON_HASH** — atomic-stopped 2026-05-14 because no Python Poseidon reference was available in agent runtime for vector-verification of a hand-written AS implementation. Documented in `DEPENDENCY_BLOCKERS` roster of `scripts/w3bstream_applet_audit.py:234-248`.
- **P256_VERIFY** — preserved as stub because no W3bstream runtime testbed exists for ECDSA-P256 AS-side testing. Stays out of scope for this plan (closure path is operator-runtime coordination with W3bstream team, not agent-resolvable).

This plan closes POSEIDON_HASH agent-side via an in-protocol AssemblyScript Poseidon(BN254) implementation, validated by differential testing against ≥2 independent reference implementations, pinned by 3 new PV-CI invariants via governance ceremony (83 → 86), and wired into the applet's `_encode_submit_proof` ABI encoder (`validate_poac_record.ts:408-454`).

**Architectural payoff:** AS Poseidon becomes a protocol-internal cryptographic *capability* that survives ecosystem evolution — distinct in shape from the 10 PATTERN-017 commitment-family primitives (which are domain-tagged SHA-256 commitment producers, each yielding a 32-byte commitment via a canonical byte tag). POSEIDON-BN254-AS is **not** itself a commitment family with a domain tag in the PATTERN-017 sense; it is the hash-function capability that SUPPORTS PATTERN-017 #8 ZK-SEPPROOF and the Phase 62 PitlSessionProof circuit by making their commitment computation verifiable in-applet. The PATTERN-017 commitment-family count stays at **10 unchanged**. The methodology layer's three-zone privacy compartmentalization claim regains structural integrity at the W3bstream applet boundary (commitment chain verifiable in-zone, not just Groth16 proof).

**Out of scope (residual gaps deliberately preserved):**
- P256_VERIFY closure (Hard Rule defer; external runtime testbed required).
- `humanityProbInt` zero placeholder at `validate_poac_record.ts:434` (not Poseidon-related; classifier-derived).
- `epoch` zero placeholder at `validate_poac_record.ts:444` (W3bstream chain-introspection delta; SEPARATE follow-on phase required before applet registration — without real epoch, nullifierHash becomes deterministic per device and breaks anti-replay at `PITLSessionRegistry.submitPITLProof`).
- **`compute_inputs_pitl.js` staleness / real-proof-path bug** (Decision-4, surfaced at P.2 exploration) — `compute_inputs_pitl.js` computes `featureCommitment = Poseidon(7)` but the Phase-62 circuit requires `Poseidon(8)`; the real-proof path in `pitl_prover.py` appears non-functional. Pre-existing protocol bug, **filed separately for operator triage** — NOT fixed by this plan. The only consequence for this plan: the **circuit source is the parameter-set oracle**, not the stale helper.

**Applet registration to W3bstream remains operator-runtime** and is NOT part of this plan. POSEIDON_HASH closure ships agent-side cryptographic correctness; registration ceremony waits for `epoch` delta closure + operator three-factor at console.w3bstream.com.

---

## Existing utilities to reuse (no new code where possible)

| Utility | Path | Reuse for |
|---|---|---|
| circomlibjs Poseidon (primary reference) | `contracts/circuits/node_modules/circomlibjs` + `bridge/zk_artifacts/node_modules/circomlibjs` (vendored v0.1.7) | P.2 vector generator + V.3 cross-reference |
| Existing Poseidon-using helpers | `bridge/zk_artifacts/compute_inputs.js` + `compute_inputs_pitl.js` + `compute_inputs_passport.js` | Reference *invocation pattern* only (`buildPoseidon()` + `F.toObject()`). **NOT a parameter-set oracle** — `compute_inputs_pitl.js` is stale (Phase-26 era; computes `Poseidon(7)` not the Phase-62 `Poseidon(8)`). See Pass-3 revision note. |
| **PitlSessionProof circuit (authoritative oracle)** | `contracts/circuits/PitlSessionProof.circom:106` (`Poseidon(8)` featureCommitment) + C5 (`Poseidon(2)` nullifierHash) | Arity oracle for `validate_poac_record.ts` — featureCommitment t=9, nullifierHash t=3, deviceIdHash t=2 (`compute_inputs_pitl.js:73` `Poseidon(1)`) |
| ZK-SEPPROOF circuit | `contracts/circuits/ZKSepProof.circom:166` (`Poseidon(5)`) | Arity reference for `validate_zk_sepproof.ts` — **W.2 is a confirmed no-op** (that applet has no active POSEIDON_HASH stub); t=6 OUT of this plan's scope |
| BN254 field constants | `contracts/contracts/Groth16VerifierZKSepProof.sol:24-27` | Authoritative scalar field r literal |
| PV-CI governance ceremony pattern | `scripts/vapi_invariant_gate.py` `--generate --reason "<category>: <text>" --confirm-governance` | PV.1 (mirrors commit `1bbf163f` 77→83) |
| INVARIANTS PATTERN-017 shape | `scripts/vapi_invariant_gate.py` INV-CORPUS-001/002 entries | Template for INV-POSEIDON-AS-001/002/003 |
| Governance phrase | `_GOVERNANCE_PHRASE = "I understand this changes a frozen protocol invariant"` (vapi_invariant_gate.py:78) | PV.1 operator step |
| Test infrastructure pattern | `bridge/tests/test_w3bstream_applet_audit.py` (17 tests T-W3B-1..17) | T.1 new tests T-W3B-18..23 + 4 updates |

---

## Safety discipline — non-negotiable protective rules

Mirrors the discipline that held the prior plan to zero regressions across 17 atomic commits:

1. **Preflight checks ship NO code.** P.0 is verification-only. If preflight fails on critical deps, plan halts cleanly; no commits.
2. **Baseline-before-refactor.** Capture bridge passing count (3728 at HEAD `40da5755`) and Hardhat (542) before any commit. Post-commit count MUST be ≥ baseline.
3. **Stream independence.** P.* (build pipeline) is independent of I.* (impl). V.* depends on I.*. PV.* depends on V.*. W.* depends on PV.*. T.* depends on W.*. If V.* fails, atomic-stop; I.* code revert; investigation precedes new commit.
4. **FROZEN region untouched.** PoAC wire format byte-stable. No `.circom` files modified. Phase 62 ZK invariant (`Poseidon(8)(scaledFeatures[0..6], inferenceCodeFromBody)` per `PitlSessionProof.circom:106`) describes the contract the AS impl REPLICATES — not modifies. PV-CI gate verification passes post-commit on every commit.
5. **Atomic-stop on test regression.** Bridge passing count < 3728 OR Hardhat < 542 OR PV-CI < 83 (during plan) / < 86 (post-PV.1) → revert + investigate.
6. **No wallet operations.** `CHAIN_SUBMISSION_PAUSED=true` held throughout. 0 IOTX impact. Applet registration NOT in scope.
7. **No mainnet deploys.** Per operator standing constraint.
8. **Differential discipline mandatory.** Single-reference Poseidon implementations historically ship subtle bugs (S-box exponent, MDS transposition, round-constant indexing). V.* enforces ≥2 independent references AND per-round state verification AND boundary inputs. NOT just final-output vector matching.

---

## Execution order (safest-first; each stream gates the next)

```
   P.0 (preflight; no commit) → branch on 2nd-reference availability
         ↓
   P.1 (AS build pipeline; infra-only) → baseline asc compile of unmodified applet
         ↓
   P.2 (vector generator; Node.js + circomlibjs) → produces 3-arity vector file
         ↓
   P.3 (2nd reference; conditional GREEN/AMBER per P.0) → vector cross-validation
         ↓
   I.1 (AS Poseidon module; 3 arities) → standalone module, no applet wiring yet
   I.2 (byte interface helper) → 32-byte ↔ field conversion
         ↓
   V.1 (vector match) → +10 tests; all arities {t=2,t=3,t=9} × full vector set; AS output == reference
   V.2 (per-round differential) → +6 tests; 50 vectors/arity; intermediate states match
   V.3 (cross-reference) → SKIPPED (AMBER confirmed at P.0 — no 2nd reference)
         ↓
   PV.1 (governance ceremony 83 → 86) → operator three-factor for 3 new INVs
         ↓
   W.1 (wire validate_poac_record.ts) → replace placeholder fills (poseidon_t2 + t3 + t9)
   W.2 (wire validate_zk_sepproof.ts) → CONFIRMED NO-OP (no active POSEIDON_HASH stub there)
   W.3 (audit script update) → move POSEIDON_HASH to CLOSED_DELTAS
         ↓
   T.1 (test alignment) → update 4 + add 6 tests (cumulative +22 across V.1 + V.2 + T.1; V.3 SKIPPED)
         ↓
   D.1 (CLAUDE.md NOTE + MEMORY.md index) → state file currency
```

If any stream fails irrecoverably, prior streams remain on main; failure stream's working tree reverted; plan exits with documented remaining work.

---

## Stream P.0 — Preflight (no commit; verification only)

**Goal:** Verify all external deps available; branch plan path on 2nd-reference outcome.

| Check | Pass criterion | Failure path |
|---|---|---|
| `node --version` ≥ 18 + `npm` available | Standard exit | Halt plan; operator install Node 18+ |
| `contracts/circuits/node_modules/circomlibjs` exists + `buildPoseidon()` importable | `node -e "require('circomlibjs')"` succeeds | Halt; fallback `bridge/zk_artifacts/node_modules/circomlibjs` |
| AssemblyScript compiler available | `npx asc --version` returns ≥0.27 | P.1 installs `assemblyscript` devDep |
| WASM runtime for AS testing | `node --experimental-wasm-modules` works OR `wasm3` available | Use Node WASM (preferred; in-tree) |
| **2nd Poseidon reference available** | Try in order: (a) `pip install poseidon-hash` from PyPI; (b) `pip install py-iden3-crypto`; (c) `cargo install` arkworks Poseidon (slow); (d) Python impl from spec (fallback) | **Branch decision (see below)** |

**P.0 decision branches:**

- **GREEN** (2nd reference available in <10 min preflight): Full plan executes as drafted. V.3 cross-reference enforced; INV-POSEIDON-AS-003 pins both vector hashes.
- **AMBER** (only circomlibjs available; 2nd reference requires significant install / spec port): Single-reference path; V.3 deferred; V.2 per-round verification + V.1 boundary-input coverage compensate; PV-CI invariant body explicitly documents "single-reference verified" caveat. Plan ships with reduced cryptographic-correctness assurance documented in invariant + audit + commit body.
- **RED** (circomlibjs unavailable; vendored references broken): Halt entire plan; investigate; operator decision required before retry. Plan retains zero impact.

Preflight outcome **logged in P.1 commit body** so the path taken is permanent record.

---

## Stream P.1 — AS build pipeline (infra-only; ~1 commit)

**Goal:** Establish AssemblyScript compilation toolchain for the W3bstream applet folder without touching applet source.

| Commit | Scope | Risk |
|---|---|---|
| P.1 | New `scripts/w3bstream/package.json` (`assemblyscript` devDep + `asc` build script + `vector-gen` script entry). New `scripts/w3bstream/asconfig.json` (target wasm32 + optimizeLevel 3 + runtime stub). Verify baseline compile: `cd scripts/w3bstream && npx asc validate_poac_record.ts --outFile validate_poac_record.wasm --target release` succeeds against UNMODIFIED applet source. Captures baseline WASM binary size for comparison in W.1. | LOW (pure infra; no applet source modified) |

**Critical files (new):**
- `scripts/w3bstream/package.json`
- `scripts/w3bstream/asconfig.json`
- `scripts/w3bstream/.gitignore` (excludes `node_modules/`, `*.wasm`, `dist/`)

**Pre-commit verification:** `cd scripts/w3bstream && npx asc validate_poac_record.ts --outFile /tmp/baseline.wasm` clean. PV-CI 83/83 PASS (no PV-CI files touched).

---

## Stream P.2 — Vector generator (Node.js + circomlibjs; ~1 commit)

**Goal:** Produce canonical test vector file from circomlibjs reference for all 3 arities (t=2 / t=3 / t=9 — circomlib internal-state sizes for `Poseidon(1)` / `Poseidon(2)` / `Poseidon(8)` respectively; per Pass-3 revision — `t=6`/`Poseidon(5)` dropped, `t=2`/`Poseidon(1)` for deviceIdHash added).

| Commit | Scope | Risk |
|---|---|---|
| P.2 | New `scripts/w3bstream/poseidon_vector_generator.js` (Node.js script using `buildPoseidon()` from vendored circomlibjs). Generates: (a) 1000 random-input vectors per arity {t=2, t=3, t=9}; (b) ~30 boundary-input vectors per arity (zero, p-1, all-ones, sequential ramp, hand-picked collision-test inputs from circomlib's own test corpus); (c) 50 vectors per arity with per-round intermediate state captures (for V.2). Output: `scripts/w3bstream/poseidon_test_vectors.json` (~5 MB; vector arrays + per-round states + metadata header documenting circomlibjs version + BN254 prime literal + R_F/R_P per arity). SHA-256 of vector file computed and printed; file's SHA-256 will be pinned by INV-POSEIDON-AS-003. **PARAMETER-SET VERIFICATION (Risk #1 boundary gate; oracle = the CIRCUIT per Decision-4):** P.2 anchors on the in-scope **Phase 62 `PitlSessionProof.circom`** as the parameter-set oracle — NOT `compute_inputs_pitl.js` (stale; see Pass-3 revision note) and NOT the out-of-scope ZK-SEPPROOF path. P.2 produces ONE canonical vector for each of the corrected arities {t=2, t=3, t=9} from circomlibjs, then verifies them against the circuit's authoritative definitions: `featureCommitment = Poseidon(8)(scaledFeatures[0..6], inferenceCodeFromBody)` (`PitlSessionProof.circom:106`), `nullifierHash = Poseidon(2)(deviceIdHash, epoch)` (C5), `deviceIdHash = Poseidon(1)(deviceId)` (`compute_inputs_pitl.js:73` — note: only the *deviceIdHash* line of that helper matches the circuit; its featureCommitment line is the stale part). circomlibjs's parameter set was already confirmed at P.0 via the canonical test vector `Poseidon([1,2]) = 7853200…813530`. If the arity/input-ordering used by the generator does not match the circuit source exactly, plan halts at P.2 with documented diagnosis (which arity/ordering drifted; what the circuit actually specifies). P.2 commit body documents the parameter-set verification outcome + the specific test inputs used + the circuit source lines consulted. This catches Risk #1 at the P.2 boundary BEFORE substantial I.* work is sunk cost. | LOW (read-only references; produces single data file; adds one read-only contract verification call) |

**Critical files (new):**
- `scripts/w3bstream/poseidon_vector_generator.js`
- `scripts/w3bstream/poseidon_test_vectors.json` (generated artifact; checked in for reproducibility)
- `scripts/w3bstream/poseidon_test_vectors.sha256` (single-line file with hash; convenience for INV-POSEIDON-AS-003)

**Pre-commit verification:** Re-run generator from clean state; vector file byte-identical to checked-in version (determinism check). Parameter-set verification step PASSES against the `PitlSessionProof.circom` authoritative arity/ordering definitions (Risk #1 boundary gate cleared; oracle = circuit source per Decision-4). PV-CI PASS.

---

## Stream P.3 — Differential reference (GREEN/AMBER per P.0; ~1 commit OR skipped)

**GREEN path** (2nd reference available):

| Commit | Scope | Risk |
|---|---|---|
| P.3 | Add `scripts/w3bstream/poseidon_vector_validator.py` that loads vector file + uses 2nd-reference Poseidon implementation + asserts byte-identical output for every vector across both references. Failure = halt plan (refs disagree → P.0 was wrong about 2nd ref correctness; investigate before proceeding). PASS = vectors validated across 2 independent impls; INV-POSEIDON-AS-003 pins file hash with confidence. | LOW (read-only; no code mutation; only validation) |

**AMBER path** (single-reference only; P.3 SKIPPED):

P.3 ships a stub validator that prints "AMBER PATH — single-reference vectors; differential validation deferred to ecosystem availability". Commit body documents which 2nd-reference candidates were tried in P.0 + why each failed. V.* compensates via expanded per-round verification + symbolic round-constant audit.

**Critical files (new GREEN):**
- `scripts/w3bstream/poseidon_vector_validator.py`

---

## Stream I.1 — AS Poseidon module (substantive; ~2 commits with safety preflight)

**Goal:** Implement Poseidon(BN254) in AssemblyScript for arities t∈{2,3,9} (covering `Poseidon(1)/Poseidon(2)/Poseidon(8)` — per Pass-3 revision).

| Commit | Scope | Risk + Safety |
|---|---|---|
| I.1a | **BASELINE CAPTURE + INFRASTRUCTURE:** Run `cd contracts && npx hardhat test` capture baseline (542). Run `python -m pytest bridge/tests/ -q` capture baseline (3728). Document in I.1a commit body. Add `scripts/w3bstream/poseidon_bn254.ts` with: BN254 prime constant (32-byte big-endian); 256-bit modular arithmetic over 4×u64 limbs (add / sub / mul / reduce mod p); S-box `x^5 mod p`; field-element load/store helpers. NO Poseidon permutation yet; NO arity-specific hash functions yet. Smoke test: AS-compile clean; basic mod-mul correctness on known small inputs (e.g., 2 * 3 mod p == 6). | MEDIUM; modular arithmetic is the most subtle layer; explicit baseline gate |
| I.1b | Add Poseidon permutation (full + partial rounds); round constants table emitted as `const` byte arrays generated by P.2's vector script (parallel output: a separate `poseidon_constants_gen.js` writes `scripts/w3bstream/poseidon_constants.generated.ts` from circomlibjs Grain LFSR output); MDS matrix per arity; three hash entry points: `poseidon_t2(in0: ArrayBuffer): ArrayBuffer` (1×32B input — `Poseidon(1)`, for deviceIdHash), `poseidon_t3(in0: ArrayBuffer, in1: ArrayBuffer): ArrayBuffer` (2×32B inputs — `Poseidon(2)`, for nullifierHash), `poseidon_t9(inputs: ArrayBuffer): ArrayBuffer` (8×32B inputs — `Poseidon(8)`, for featureCommitment). All return canonical 32-byte big-endian field-element output matching circomlibjs `F.toObject()` byte order. NO applet wiring yet. | MEDIUM-HIGH; the substantive cryptographic work |

**Critical files (new):**
- `scripts/w3bstream/poseidon_bn254.ts`
- `scripts/w3bstream/poseidon_constants.generated.ts` (from `poseidon_constants_gen.js`)
- `scripts/w3bstream/poseidon_constants_gen.js`

**Pre-commit verification per I.1 commit:**
- `cd scripts/w3bstream && npx asc poseidon_bn254.ts --outFile /tmp/poseidon.wasm` clean
- Smoke micro-test: a tiny harness Node script calls compiled WASM Poseidon for ONE known vector, prints output. Must match the corresponding vector in `poseidon_test_vectors.json`. (Not a comprehensive test; just smoke that the wiring is alive.)
- PV-CI 83/83 PASS (no PV-CI files touched yet)
- No regression on bridge or Hardhat counts

---

## Stream I.2 — Byte interface helper (~1 commit; trivial)

| Commit | Scope | Risk |
|---|---|---|
| I.2 | Add `scripts/w3bstream/poseidon_field_io.ts` with `bytes32_to_field(ptr: i32): Field` and `field_to_bytes32(field: Field, outPtr: i32): void` helpers. Big-endian 32-byte input → BN254 field element (reduces mod p if input ≥ p); field → 32-byte big-endian output. Matches circomlibjs `F.toObject()` convention exactly. | LOW (small focused helpers) |

---

## Stream V.* — Validation (substantive; ~3 commits)

**Goal:** Cryptographic-correctness verification via three independent techniques.

| Commit | Scope | Risk + Safety |
|---|---|---|
| V.1 | New `bridge/tests/test_w3bstream_poseidon_as.py` with `T-W3B-POSEIDON-AS-1..10`. For each arity {t=2, t=3, t=9}: compile AS Poseidon to WASM; invoke from pytest via subprocess Node WASM runtime; feed first 100 random-input vectors from `poseidon_test_vectors.json`; assert AS output byte-identical to expected. Plus boundary-input coverage: 30 boundary vectors per arity (zero, p-1, all-ones, sequential, weak inputs). **If ANY vector mismatches → atomic-stop V.1; revert; investigate root cause** (likely modular reduction, S-box exponent, or round-constant indexing). | MEDIUM-HIGH; this is where AS impl bugs surface; explicit revert path |
| V.2 | Extend test file with `T-W3B-POSEIDON-AS-11..16` for per-round differential. For 50 vectors per arity: AS Poseidon exports per-round state via a debug-mode build flag (`poseidon_bn254_debug.ts` mirror that emits state after each round to a buffer); test reads round-state buffer and asserts byte-identical match to circomlibjs per-round states stored in vector file. **Catches MDS / round-constant / S-box bugs that happen to cancel in final output but corrupt intermediate state.** | HIGH catch-rate; explicit revert path |
| V.3 | **SKIPPED — AMBER confirmed at P.0** (no quick BN254-compatible 2nd reference; circomlibjs is the single reference). Cross-reference triangulation `T-W3B-POSEIDON-AS-17..18` is NOT shipped. V.1 boundary-input coverage + V.2 per-round verification are the compensating differential discipline. The single-reference caveat is documented in the PV.1 invariant bodies + W.3 audit + commit bodies. | N/A — skipped |

**Critical files (new):**
- `bridge/tests/test_w3bstream_poseidon_as.py`
- `scripts/w3bstream/poseidon_bn254_debug.ts` (V.2 only; per-round-emitting variant)
- `scripts/w3bstream/poseidon_runtime.js` (Node.js WASM invocation helper used by pytest subprocess)

**Pre-commit verification per V.* commit:**
- `python -m pytest bridge/tests/test_w3bstream_poseidon_as.py -v` all new tests PASS
- Bridge total passing ≥ baseline + N (N = tests added in commit)
- PV-CI PASS

---

## Stream PV.1 — Governance ceremony (PV-CI 83 → 86; ~1 commit)

**Goal:** Pin POSEIDON-AS module via 3 new PV-CI invariants. Ceremony pattern mirrors commit `1bbf163f` (PV-CI 77→83) verbatim.

| Commit | Scope | Risk + Safety |
|---|---|---|
| PV.1 | Edit `scripts/vapi_invariant_gate.py` to add: INV-POSEIDON-AS-001 (pin `function poseidon_t9` declaration in `scripts/w3bstream/poseidon_bn254.ts`); INV-POSEIDON-AS-002 (pin `BN254_PRIME` byte-literal in same file — the EXACT 32-byte big-endian prime; protects against modular-reduction bugs from prime drift); INV-POSEIDON-AS-003 (pin `POSEIDON_VECTORS_SHA256` constant in the same file matching vector file hash; protects against vector-file tampering). Regenerate allowlist via `python scripts/vapi_invariant_gate.py --generate --reason "ceremony_update: POSEIDON-BN254-AS protocol-internal cryptographic capability pinned (Phase O4-W3B-POSEIDON-AS supports PATTERN-017 #8 ZK-SEPPROOF plus Phase 62 ZK verification)" --confirm-governance` + operator types exact phrase `I understand this changes a frozen protocol invariant`. Allowlist entry count 83 → 86. Bridge governance event POST 404 acceptable if bridge offline (matches Phase 224 + O1-FRR-PARALLEL precedent). | LOW (governance gate; standard pattern; operator-runtime three-factor at PowerShell terminal — agent CANNOT execute --confirm-governance autonomously per Hard Rule) |

**Critical files (modified + regenerated):**
- `scripts/vapi_invariant_gate.py` (INVARIANTS dict: 83 entries → 86 entries)
- `.github/INVARIANTS_ALLOWLIST.json` (regenerated)

**Pre-commit verification:** `python scripts/vapi_invariant_gate.py --report` returns 86/86 PASS.

**Operator three-factor required at PowerShell terminal:**
1. Run `python scripts/vapi_invariant_gate.py --generate --reason "..." --confirm-governance`
2. Type exact governance phrase when prompted
3. Verify allowlist regenerated to 86 entries before commit

This stream requires operator authorization. Plan execution halts at PV.1 commit boundary pending operator presence.

---

## Stream W.* — Wire into applet (~3 commits)

**Goal:** Replace zero-placeholder fills with real Poseidon calls; audit verdict transition.

| Commit | Scope | Risk + Safety |
|---|---|---|
| W.1 | Edit `scripts/w3bstream/validate_poac_record.ts`: import `poseidon_t9` + `poseidon_t3` + `poseidon_t2` from `poseidon_bn254.ts`. Replace `memory.fill(headStart + 64, 0, 32)` (featureCommitment) at line 431 with: extract scaledFeatures from PoAC body + extract inferenceCodeFromBody + call `poseidon_t9` + write 32B output. Replace `memory.fill(headStart + 160, 0, 32)` (nullifierHash) at line 441 with: **first compute `deviceIdHash = poseidon_t2(deviceId)`** from the raw `keccak256(pubkey)` PoAC `OFF_DEVICE_ID` field (Pass-3 revision — the circuit's `nullifierHash = Poseidon(2)(deviceIdHash, epoch)` requires `deviceIdHash = Poseidon(1)(deviceId)` per `compute_inputs_pitl.js:73`), **then `nullifierHash = poseidon_t3(deviceIdHash, epoch)`** + write 32B output. **NOTE: `epoch` is still zero per separate W3bstream-runtime delta; nullifierHash becomes Poseidon(deviceIdHash, 0) deterministic per device.** Comment block at lines 392-406 updated to reflect new state (POSEIDON_HASH closed; nullifierHash anti-replay still broken pending epoch delta closure). asc compile clean. Binary size compared to P.1 baseline (5144 bytes); document delta in commit body. | MEDIUM (real cryptographic computation now in critical path; binary size +∼KB acceptable) |
| W.2 | **CONFIRMED NO-OP** (Pass-3 revision). `scripts/w3bstream/validate_zk_sepproof.ts` has **no active POSEIDON_HASH stub** — verified at P.2 exploration: it carries only one descriptive wire-format comment (`featureCommitment (uint256 BE; Poseidon output)`), it receives `featureCommitment` rather than computing it. No `memory.fill(...0, 32)` Poseidon placeholder exists there. `t=6`/`Poseidon(5)` is therefore OUT of this plan's scope. W.2 ships as a no-op confirmation commit body documenting this verification (or folds into W.3's commit body). | NONE (no-op; documentation only) |
| W.3 | Edit `scripts/w3bstream_applet_audit.py`: move POSEIDON_HASH from `CRYPTO_INTEGRATION_DELTAS` (lines 165-176) to `CLOSED_DELTAS` with closure phase `Phase O4-W3B-POSEIDON-AS` + summary referencing the closure approach. Remove "AssemblyScript Poseidon implementation" entry from `DEPENDENCY_BLOCKERS` (lines 234-248). Audit verdict logic: stays at `STUB_DEPS_BLOCKED` because P256_VERIFY remains dep-blocked (closed_deltas 3 → 4; open_deltas 2 → 1). Update `crypto_deltas_closed` count documented in audit report. | LOW (audit-script-only changes; no protocol code) |

**Critical files (modified):**
- `scripts/w3bstream/validate_poac_record.ts` (W.1)
- `scripts/w3bstream/validate_zk_sepproof.ts` (W.2; conditional)
- `scripts/w3bstream_applet_audit.py` (W.3)

**Pre-commit verification per W.* commit:**
- `cd scripts/w3bstream && npx asc validate_poac_record.ts --outFile /tmp/applet.wasm` clean
- `python scripts/w3bstream_applet_audit.py` runs; verdict expectations match commit's scope
- `python -m pytest bridge/tests/test_w3bstream_applet_audit.py -v` — see T.1 for which assertions update
- PV-CI 86/86 PASS

---

## Stream T.1 — Bridge test alignment (~1 commit)

**Goal:** Update existing tests for new audit state; add 6 new applet tests (5 Poseidon WASM smoke-tests + 1 anti-replay-broken regression artifact).

| Commit | Scope | Risk |
|---|---|---|
| T.1 | Edit `bridge/tests/test_w3bstream_applet_audit.py`: update **T-W3B-4** (assert `"POSEIDON_HASH" not in open_ids`; keep `"P256_VERIFY" in open_ids`); **T-W3B-13** (verdict stays `STUB_DEPS_BLOCKED` because P256_VERIFY blocks transition); **T-W3B-14** (assert POSEIDON_HASH not in DEPENDENCY_BLOCKERS; only P256_VERIFY blocker remains); **T-W3B-15** (extend closed_deltas to include POSEIDON_HASH; 4 of 5 closed now). Add **T-W3B-18..22**: applet WASM smoke-test (compile + invoke + assert featureCommitment is non-zero for non-zero feature vector + assert nullifierHash is non-zero for non-zero deviceIdHash + assert deterministic across two invocations + assert different inputs produce different outputs + assert byte-order is canonical big-endian). Add **T-W3B-23** (anti-replay-broken regression artifact, Risk #11): asserts nullifierHash is deterministic given the same deviceIdHash + `epoch=0` across two invocations; test name + docstring explicitly state — "Anti-replay is currently structurally broken pending Phase TBD epoch delta closure. This test exists to surface the broken state to test-suite readers. When the epoch delta closes, this test MUST be rewritten to assert non-deterministic nullifierHash across different epochs." T.1 commit body documents T-W3B-23 as a deliberate regression artifact, NOT a passing-as-correct-behavior test — it makes the broken anti-replay state legible to anyone reading the test suite without reading CLAUDE.md or the W.1 commit body. | LOW (test-file-only) |

**Pre-commit verification:**
- `python -m pytest bridge/tests/test_w3bstream_applet_audit.py -v` all 23 tests PASS (17 original + 6 added by T.1)
- Bridge total passing ≥ 3728 + 22 = 3750 (V.1=10 + V.2=6 + T.1=6 all landed by this point in the stream order; V.3=2 SKIPPED under confirmed AMBER)
- PV-CI 86/86 PASS

---

## Stream D.1 — Docs sync (~1 commit; pure docs)

| Commit | Scope | Risk |
|---|---|---|
| D.1 | Append top NOTE entry to `CLAUDE.md` summarizing Phase O4-W3B-POSEIDON-AS: POSEIDON-BN254-AS protocol-internal cryptographic capability — **explicitly distinguished** from PATTERN-017 commitment-family primitives (it is the hash-function capability that SUPPORTS PATTERN-017 #8 ZK-SEPPROOF + Phase 62 PitlSessionProof verification, NOT a new domain-tagged commitment family; PATTERN-017 commitment-family count stays 10); PV-CI 83 → 86; AS Poseidon BN254 module + vector file + differential validation; closed_deltas 3 → 4; remaining open: P256_VERIFY (external runtime testbed required); `epoch` zero-placeholder separately documented as W3bstream-runtime delta out of scope. Update `MEMORY.md` index entry. | NONE (docs only) |

**Pre-commit verification:** PV-CI 86/86 PASS (no code touched).

---

## End-to-end verification (final check before pushing)

Run after every stream's last commit:

1. `python -m pytest bridge/tests/ --ignore=bridge/tests/test_e2e_simulation.py -q` — passing count ≥ 3728 + 22 (V.1=10 + V.2=6 + T.1=6; V.3 SKIPPED under confirmed AMBER) = ≥ 3750 projected post-T.1
2. `cd contracts && npx hardhat test` — passing count ≥ 542 (unchanged baseline)
3. `python scripts/vapi_invariant_gate.py --report` — 86/86 PASS post-PV.1
4. `python scripts/w3bstream_applet_audit.py` — verdict STUB_DEPS_BLOCKED with closed_deltas count=4 + open_deltas={P256_VERIFY only}
5. `cd scripts/w3bstream && npx asc validate_poac_record.ts --outFile /tmp/applet.wasm && wc -c /tmp/applet.wasm` — binary size logged
6. `python scripts/cfss_lane_drift_sweep.py` — PASS unchanged
7. `python scripts/g7_curator_review_readiness_audit.py` — unchanged (Curator state not touched)
8. `python scripts/replay_artifact.py --dir frontend/src/artifacts` — 6 artifacts PASS
9. `git log --oneline -15` — shows planned commits in expected order

If ANY check fails, the most-recent commit is reverted and the cause investigated before continuing.

---

## Risk register (each risk has explicit halt + fallback)

| # | Risk | Severity | Halt trigger | Fallback |
|---|---|---|---|---|
| 1 | circomlibjs Poseidon parameter set differs from what verifier contracts expect | HIGH | **P.2 parameter-set verification step** — canonical vector fails to match deployed verifier output. Caught at the P.2 boundary BEFORE substantial I.* work begins (not at V.1, where I.* implementation would already be sunk cost). Multiple Poseidon parameter sets exist in the ecosystem; some shipped incompatible variants — P.2 boundary verification is the structural guard. | Halt at P.2; documented diagnosis names which circuit emitted incompatible output + which parameter components drifted (round constants / MDS matrix / R_F/R_P) + what alternative reference would match; the deployed ceremony VK is the ground truth — AS impl must match what the circuit emitted, full stop. No I.* work begins until P.2 parameter-set verification clears. |
| 2 | 2nd Poseidon reference unavailable in agent runtime | MEDIUM | P.0 preflight check fails | **AMBER path**: single-reference; V.3 deferred; INV-POSEIDON-AS body documents caveat; plan ships with reduced cryptographic-correctness assurance documented in invariant text + audit script + commit body. Stream independence holds — all other streams unaffected. |
| 3 | AS modular arithmetic on 4×u64 limbs produces subtle wrong results | MEDIUM-HIGH | V.1 vector mismatch on >0.1% of random vectors | Atomic-stop V.1; revert I.1b; debug specific failing vector; isolate to add/sub/mul/reduce step; ship targeted fix-commit before re-attempting V.1 |
| 4 | AS Poseidon binary size exceeds W3bstream tier limit | MEDIUM | W.1 produces WASM >256 KB | Investigate W3bstream tier limits + binary; round-constant tables may need code-generation rather than literal data (smaller binary at runtime expansion cost); halt; operator decision |
| 5 | Per-round state verification reveals divergence at round N (S-box / MDS bug) | MEDIUM-HIGH | V.2 per-round mismatch | Atomic-stop V.2; revert I.1b; isolate to specific round; investigate S-box exponent OR MDS matrix OR round-constant indexing; ship targeted fix-commit |
| 6 | Vector file SHA-256 drifts after legitimate edits | LOW | INV-POSEIDON-AS-003 fails PV-CI post-vector-file-modification | Rebuild vectors via P.2 script; verify new hash matches cross-reference outputs; update invariant via NEW governance ceremony (`ceremony_update` reason category) |
| 7 | Phase 62 ZK invariant interpretation wrong (arity, input order, scaling) | HIGH | V.1 vector mismatch on featureCommitment specifically OR W.1 binary fails smoke against deployed verifier | Re-verify `PitlSessionProof.circom` source vs AS-side mapping; correct AS-side scaledFeatures extraction OR input ordering; reflect in code comments + audit. **FIRED + RESOLVED at P.2 exploration boundary 2026-05-14** — the plan's arity set `{t=3,t=6,t=9}` was mis-derived; corrected to `{t=2,t=3,t=9}` via Pass-3 revision *before any vector-generation code was written* (zero sunk cost). See Pass-3 revision note. The risk remains live for the remaining streams (V.1 onward) as a residual guard. |
| 8 | Wallet drain via accidental chain submission | LOW (Hard Rule) | N/A — plan is wallet-free | Plan has zero chain ops; CHAIN_SUBMISSION_PAUSED=true holds; if any chain submission attempted, Phase 237.5 Path C+ kill-switch caught at chain.py level |
| 9 | PV-CI governance ceremony fails (wrong phrase / missing flag) | LOW | PV.1 step rejected at PowerShell terminal | Re-run with correct flags; no commit ships until ceremony succeeds; standard pattern from `1bbf163f` |
| 10 | Bridge test count regresses on any commit | MEDIUM | `python -m pytest bridge/tests/ -q` post-commit < 3728 | Revert offending commit; investigate cause; ship targeted fix-commit before continuing stream |
| 11 | `epoch` zero-placeholder + new Poseidon nullifierHash produces apparent applet "working" state that masks broken anti-replay | LOW (documented; scope-bounded) | N/A — explicitly documented as residual gap | W.1 commit body + CLAUDE.md NOTE explicitly state nullifierHash is deterministic per device until separate epoch delta closure; applet NOT registered with W3bstream until that closure |

---

## Stream independence verification — what happens if each stream fails entirely

| Stream that fails entirely | Streams that still ship |
|---|---|
| P.0 RED | None (preflight halt; zero impact) |
| P.1 | None (downstream depends; halt) |
| P.2 | None (V.* depends on vectors) |
| P.3 | I.* + V.1 + V.2 + PV.1 + W.* + T.1 + D.1 (V.3 skipped under AMBER) |
| I.1 | None (downstream depends; halt) |
| I.2 | V.* skips byte-IO; tests work direct on pointers; awkward but functional |
| V.1 / V.2 / V.3 | None per stream — V failure means crypto unverified; PV.1 + W.* cannot proceed |
| PV.1 | W.* + T.1 + D.1 still ship but invariants unpinned; audit verdict transitions without governance ceremony (architectural debt) |
| W.* | T.1 + D.1 still ship (test-only + docs-only) |
| T.1 | D.1 still ships |
| D.1 | All prior streams already on main |

The plan's critical path is P.* → I.* → V.* → PV.1 → W.*. Streams P.3, T.1, D.1 are independence layers around it.

---

## What this plan does NOT do

- **Does NOT fire W3bstream applet registration** — operator-runtime at console.w3bstream.com; ALSO requires `epoch` delta closure (separate phase) before registration would be functional (anti-replay)
- **Does NOT close P256_VERIFY delta** — Hard Rule defer (no W3bstream runtime testbed); separate sequence (operator coordination)
- **Does NOT close `humanityProbInt` zero-placeholder** — classifier-derived; not Poseidon-related; separate scope
- **Does NOT close `epoch` zero-placeholder** — W3bstream chain-introspection delta; must close before applet registration is functional
- **Does NOT modify FROZEN ZK circuits** — Phase 62 `PitlSessionProof.circom` + Phase 237 `ZKSepProof.circom` are FROZEN; AS impl REPLICATES their Poseidon usage, never modifies
- **Does NOT deploy any contracts** — wallet-free; CHAIN_SUBMISSION_PAUSED=true held
- **Does NOT bypass governance ceremony** — PV.1 requires operator three-factor at PowerShell terminal

---

## Estimated execution time

| Stream | Estimated effort (GREEN) | Estimated effort (AMBER fallback) |
|---|---|---|
| P.0 | 0.5 hour | 0.5 hour |
| P.1 | 1 hour | 1 hour |
| P.2 | 2 hours (incl. Risk #1 parameter-set verification) | 2 hours (incl. Risk #1 parameter-set verification) |
| P.3 | 1 hour | 0.5 hour (stub validator) |
| I.1 | 5-7 hours | 5-7 hours |
| I.2 | 0.5 hour | 0.5 hour |
| V.1 | 1.5 hours | 1.5 hours |
| V.2 | 2 hours | 2 hours |
| V.3 | 1 hour | SKIPPED |
| PV.1 | 0.5 hour (excluding operator-runtime wait) | 0.5 hour |
| W.1 | 1 hour | 1 hour |
| W.2 | 0.5 hour | 0.5 hour |
| W.3 | 0.5 hour | 0.5 hour |
| T.1 | 1 hour | 1 hour |
| D.1 | 0.5 hour | 0.5 hour |
| **Total** | **~17.5-19.5 hours, 5-7 sessions** | **~15.5-17.5 hours, 4-6 sessions** |

Operator-runtime moments inside the timeline:
- P.0 preflight 2nd-reference choice (5-10 min operator presence)
- PV.1 governance ceremony (5 min operator presence — types governance phrase)

All other work is autonomous-agent-resolvable.

---

## Architectural payoff at landing

| Metric | HEAD `40da5755` | Post-plan target | Δ |
|---|---|---|---|
| Bridge tests | 3728 passing | ≥ 3750 passing | +22 (V.1=10 + V.2=6 + T.1=6; V.3 SKIPPED under confirmed AMBER) |
| Hardhat tests | 542 | 542 | unchanged |
| PV-CI invariants | 83 | 86 | +3 (INV-POSEIDON-AS-001/002/003) |
| FSCA contradiction rules | 27 | 27 | unchanged |
| FROZEN-v1 primitives (PATTERN-017 commitment families) | 10 | 10 | unchanged |
| Protocol-internal cryptographic capabilities | n/a | +1 | POSEIDON-BN254-AS — supports PATTERN-017 #8 ZK-SEPPROOF + Phase 62 PitlSessionProof circuit verification; distinct in shape from the 10 domain-tagged SHA-256 commitment families |
| W3bstream applet verdict | STUB_DEPS_BLOCKED (3 closed / 2 open) | STUB_DEPS_BLOCKED (4 closed / 1 open) | crypto_deltas_closed +1 |
| Wallet IOTX impact | n/a | 0 | **0 (wallet-free)** |
| CHAIN_SUBMISSION_PAUSED | true | true | held |

**Architectural integrity gains:**
1. Three-zone privacy compartmentalization claim regains structural integrity at W3bstream applet boundary (commitment chain verifiable in-zone)
2. POSEIDON-BN254-AS converts an external dependency (no AS Poseidon library available in ecosystem) → a protocol-internal cryptographic capability; Phase 62 + Phase 237 circuits gain in-applet verifiable commitment computation. The PATTERN-017 commitment-family count is unchanged at 10 — POSEIDON-BN254-AS is the supporting hash-function capability, not an 11th commitment family
3. PV-CI gate's cryptographic-correctness pinning surface grows: BN254 prime literal + vector hash + function signature all locked at SHA-256 level against future drift
4. Audit script's `crypto_deltas_closed` array gains its 4th entry; "incompleteness with visible limits" posture strengthens (3 of 5 → 4 of 5; only P256_VERIFY remains open and explicitly documented external-runtime-testbed gate)

---

*— VAPI Principal Architect, 2026-05-13*
