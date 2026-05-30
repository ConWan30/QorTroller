# Data Economy Ladder — Deploy-Hold Posture & Arc 5 Readiness Audit

**Date:** 2026-05-29 (Arc 5 build closure — was: 2026-05-29 pre-build audit)
**Branch:** `feat/gameplay-workflow-layer`
**Authority:** Operator-directed deploy-hold · Verification-First Discipline applies
**Status:** **Arcs 1–5 BUILT (code)** · all remaining on-chain deploys (Arc 2, Arc 4, Arc 5) HELD pending operator GO + Arc 5 trusted-setup ceremony

---

## 0. Why this document exists

A prior state assessment (2026-05-29, pasted into session) framed the Data
Economy ladder as *"Arcs 1–4 specced but not built."* That framing is
**incorrect** and this document corrects it against verified repository state.
It also records the operator deploy-hold decision in precise, honest terms so
no future session re-derives it wrong, and amends the Arc 5 pre-investigation
checklist so it does not false-halt under the deploy-hold.

Honesty-first: every claim below is backed by a git commit, an on-chain
artifact in `contracts/deployed-addresses.json`, a present/absent file, or the
PV-CI invariant gate (`scripts/vapi_invariant_gate.py --report` → **144
invariants, all pass**, 2026-05-29).

---

## 1. Verified state of each arc (the correction)

"Built" = source + tests committed to `feat/gameplay-workflow-layer`.
"Deployed" = a transaction landed on IoTeX testnet (chain 4690).
These are **distinct** — the pasted assessment conflated them.

| Arc | Component | Code | On-chain deploy | Evidence |
|---|---|---|---|---|
| 1 | VAPIBuyerRegistry + Curator write path | **BUILT** | **DEPLOYED (LIVE)** | `9f8863a9`/`d3b7aa71`/`f32ba1a7`/`b22993d3`; registry `0x3742189eBDC09B115FA7e841C884247E9856130B`; setCuratorWallet fired; Phase 4a/4b scope flips fired (blocks 44074471 / 44074677) |
| 2 | VAPIBuyerCategoryVerifier (ZK category-privacy) | **BUILT** | **DEFERRED** | `7ec4e3d6`/`4b674d0f`/`87d946df`; `VAPIBuyerCategoryVerifier.sol` present; estimate-only deploy script (~0.68 IOTX), NOT broadcast |
| 3 | CuratorPackagingLoop (post-session packaging) | **BUILT** | none required | `c6431be4`/`b90ae776`/`1e29bcc6`; `curator_packaging_loop.py` present; bridge-side dormant |
| 4 | VAPIConsentManifestRegistry (structured 7-dim consent) | **BUILT** | **DEFERRED** | `6bf75830`; `VAPIConsentManifestRegistry.sol` present; bridge read path fail-open |
| 5 | VAPIReplayProofPipeline (VHR proofs) | **BUILT** (Commits 1-4.5) | **DEFERRED** | Pre-processor + circuit + contract wrapper + orchestrator + Curator hook + endpoint; Arc 4 struct extended in-place with Dimension 8; `VAPIReplayProofVerifier.sol` + `MockVAPIReplayProofGroth16Verifier.sol`; deploy script estimate-only; 9 `INV-VHR-001..009` in the gate; 73 Python tests + 17 Hardhat tests |

**Bottom line correction (updated 2026-05-29 post-build):** Arcs 1–5 are *built*.
Arc 1 is *partly deployed* already. The accurate framing is "the Data Economy
ladder is fully built in code, with all remaining on-chain deploys (Arc 2 + Arc 4
+ Arc 5) deliberately withheld pending operator GO + the Arc 5 trusted-setup
ceremony."

---

## 2. The deploy-hold decision (recorded)

**Decision (operator-directed):** All *remaining* Data Economy on-chain deploys
are HELD until Arc 5 is built and the full ladder is verified end-to-end. The
arcs are built in code first; the chain deploys fire together at the end, once
the complete dependency chain (Arc 1 → 5) is proven coherent.

**Why:** Deploying a partially-built data-economy ladder on-chain commits
immutable contract addresses and spends real IOTX against a surface that is
still moving. Batching the deploys at the end means each contract is deployed
against a verified-complete ladder, the wallet is spent once with full
knowledge of inter-contract bindings, and no half-built rung is live on-chain
where a buyer could touch it. This is the same posture stated verbatim in the
Arc 2 record: *"hold on deployment for all until all phases complete; then turn
focus to incorporating the replay proof pipeline spec."*

**How to apply:** Treat "Arc N landed" inside the Data Economy ladder as "Arc N
*built in code*," NOT "Arc N deployed on-chain," until the hold is lifted. Do
not fire any of the deferred deploys below without an explicit operator GO.

### 2.1 What is held (forward-looking)

These deploys are the subject of the hold — none may fire without operator
authorization:

- **Arc 2** — `VAPIBuyerCategoryVerifier` deploy (~0.68 IOTX; script staged, estimate-only)
- **Arc 4** — `VAPIConsentManifestRegistry` deploy (script staged per Arc 4 migration doc)
- **Arc 5** — `VAPIReplayProofVerifier` deploy (~0.5–0.8 IOTX; not yet built)

### 2.2 What already fired (cannot be retroactively held — stated honestly)

The hold is **forward-looking only**. The following are immutable on-chain
facts and are NOT affected by this decision:

- **Arc 1** `VAPIBuyerRegistry` `0x3742189e…` (deploy tx `0xd4346f0b…`, block 44080863)
- **Arc 1** `setCuratorWallet` (tx `0xaf1209fb…`, block 44080937)
- **Phase 4a/4b** Curator scope flips (`updateAgentScope` block 44074471 / `setAgentScopeRoot` block 44074677)
- **Governance** Curator scope-expansion `proposalHash 0x59fb9996…` (BBG tx `0xba96f7cb…`, block 44073691)

Any statement that "Arc 1 deploy is on hold" is inaccurate — it already fired.
The hold governs Arcs 2, 4, and 5 only.

---

## 3. Arc 5 readiness — drift findings (get back on track)

Arc 5's spec (`§10 Pre-Investigation Checklist`) was written assuming Arcs 1–4
were *deployed*. Under the deploy-hold they are *built but not deployed*. This
changes two pre-investigation items, which would otherwise false-halt Arc 5.

### Finding D-1 — Pre-investigation #1 must read "built," not "deployed"

Spec §10 item 1: *"Arc 4 consent manifest v2 landed. Confirm VAPIConsentRegistry
has a `manifestHash(deviceId)` method… If not landed, stop."*

Under the deploy-hold, `VAPIConsentManifestRegistry` is **built but not
deployed by design**. A naive read of this gate ("is it on-chain?") would HALT
Arc 5 incorrectly. **Amendment:** for the deploy-hold window, "Arc 4 landed"
means the contract source + bridge read path are committed (they are:
`6bf75830`). Arc 5 builds against the *code* artifacts; its own deploy joins the
batched deploy at ladder completion.

### Finding D-2 — Manifest binding signature drift — **RESOLVED (Commit 4)**

Spec §3.2 / §6 bound Arc 5's `consentPolicyHash` to
`VAPIConsentRegistry.manifestHash(deviceId)`. Arc 4 **deliberately diverged**:
it shipped a *separate* contract `VAPIConsentManifestRegistry` keyed by **gamer
address** (`msg.sender`), not `deviceId`. **Resolution (Commit 4):** Arc 5's
orchestrator reads via `chain.get_consent_manifest(gamer_address)` →
`getManifest(address)` (gamer-address-keyed, async view). The contract wrapper
does NOT consult any registry directly — consent binding is enforced at the
orchestrator/listing layer, where the gamer's address is in scope. Documented
in the `VAPIReplayProofVerifier.sol` NatSpec "What this wrapper deliberately
does NOT bind on-chain" block.

### Finding D-3 — Dimension 8 extends a built manifest struct — **RESOLVED (operator-fired, Commit 4)**

Spec §4 adds an 8th consent dimension (`allowReplayProofs`, etc.). Arc 4 shipped
a 7-dimension manifest. Operator chose (2026-05-29) to **extend Arc 4's struct
in-place** rather than ship a separate Arc 4.5 contract or a versioned slot,
since Arc 4 is not yet deployed and the "deliberate additive deploy" comment
was relative to v1 `VAPIConsentRegistry`, not against future arcs. **Resolution
(Commit 4):** 4 new fields appended to `ConsentManifest` (`allowReplayProofs`,
`replayHumanityThreshold`, `replayQuantizationBits`, `replayRequireVerdict`);
`_computeManifestHash` extended to cover them; `REPLAY_QUANTIZATION_BITS_FLOOR
= 4` floor pinned to Arc 5 `INV-VHR-001` `RADIAL_BITS = 4`; bridge ABI in
`chain._CONSENT_MANIFEST_ABI` updated; 8 new Hardhat tests T239-CM-D8-1..8.

### Finding D-8 — Spec circom 1.x syntax — **RESOLVED (Commit 2)**

Spec §3.2 used `signal private input X;` which is invalid circom 2.0.0 syntax.
**Resolution (Commit 2):** all signals declared `signal input` in
`VAPIReplayProofVerifier.circom`; privacy designated solely via `component main
{public [...]}`, matching the `VAPIBuyerCategoryVerifier.circom` precedent.

### Finding D-9 — Spec in-circuit matrix Poseidon is infeasible — **RESOLVED (operator-fired, Commit 2)**

Spec §3.2 used `component matrixHasher = Poseidon(NB_TICKS*6)` = `Poseidon(1800)`
at the 300-tick baseline. This is non-compilable (circomlib Poseidon supports
t ≤ 17), would be ~540k constraints if expressed as a sponge (vs the "<25,000"
budget the spec itself states), and would exceed pot15's 32,768-constraint
ceiling — requiring a new ceremony, contradicting "reuse PTAU." **Resolution
(operator-selected 2026-05-29, Commit 2):** off-circuit matrix commitment.
`sanitizedTraceRoot` is a PUBLIC input; the matrix is published alongside the
proof; any verifier recomputes the Poseidon-sponge root off-chain. Circuit
collapses to 553 non-linear constraints. pot15 reuse is genuine. The matrix is
already non-invertible by Commit 1's φ, so hiding it as a private witness was
both infeasible AND conceptually wrong. Pinned by `INV-VHR-005`.

### Finding D-4 — Arc 2 verifier reuse path is sound

Spec §3.4 reuses the Phase 237 PTAU ceremony. Arc 2 already validated this reuse
(`VAPIBuyerCategoryVerifier.circom` compiled 1,447 constraints under the reused
pot15). No drift; Arc 5's ceremony-reuse assumption holds.

---

## 4. Audit result (updated 2026-05-29 post-Arc-5-build)

- **PV-CI:** **153 invariants, all pass** (was 144 pre-build; +9 VHR invariants `INV-VHR-001..009`).
- **Build state:** Arcs 1–5 BUILT and committed (working tree, not yet on `main`). Arc 1 partly deployed; all other deploys HELD. Verified against git + file presence + deployed-addresses.json.
- **Test deltas:** +73 Arc 5 Python tests (pre-processor 11 + witness generator 35 + orchestrator 21 + Curator hook 11 + 4 spec/frozen-constant pins) + 17 Arc 5 Hardhat tests (Dimension 8 8 + VHR contract wrapper 9). Full Hardhat suite passes the same 743/13 as pre-build except the 8 new D8 tests are now in the green column — no Arc-5-introduced regressions.
- **Deploy-hold:** UNCHANGED. Arc 2, Arc 4, Arc 5 deploys remain HELD. Arc 5 also gated on the trusted-setup ceremony (snarkjs `groth16 setup` + contribute + `zkey export solidityverifier` → `Groth16VerifierVAPIReplayProof.sol`) producing the inner verifier address required by `scripts/deploy-vapi-replay-proof-verifier.js`.
- **Ceremony-gate (UPDATED 2026-05-30 — both gates CLOSED):** Arc 5 had two sequential gates before live operation; both are now closed.

  **(a) Trusted-setup ceremony — COMPLETE.** Fired 2026-05-30; 2 independent contributors (claude-code scripted + operator interactive) + IoTeX testnet block 44188831 beacon; final zkey + `Groth16VerifierVAPIReplayProof.sol` + verification key all produced and verified. Full audit transcript at `docs/data-economy-arc5-ceremony-transcript.md`; PV-CI invariants INV-VHR-CEREMONY-001/002 pinned. Solidity verifier ready for operator-fired deploy (still HELD pending `VAPI_REPLAY_PROOF_DEPLOY_CONFIRM=1`).

  **(b) circomlibjs Poseidon helper — COMPLETE.** `bridge/vapi_bridge/replay_proof_pipeline/zk_artifacts/compute_inputs_replay_proof.js` computes vhpCommitment + sanitizedTraceRoot via circomlibjs (the same Poseidon permutation snarkjs's compiled wasm uses) and emits the snarkjs `groth16 fullprove` input.json. Canonical matrix encoding `VAPI-VHR-MATRIX-v1` FROZEN (domain tag + 7-byte-per-tick layout + 30-byte chunks + Poseidon-2 chain), pinned by PV-CI invariants INV-VHR-MATRIX-001/002/003. Python `Groth16Prover` wraps the helper + snarkjs subprocess; orchestrator's `auto_prover()` factory routes to it when artifacts are present, else returns `DeferredProver` with the missing-artifact list. End-to-end verified 2026-05-30: real Groth16 proof produced + verified against ceremony verification key; below-floor humanity proven to fail (`Num2Bits_0` line 38 in the circuit) — the floor constraint binds.

  **Live VHR operation is now possible** in code; on-chain wrapper deploy + `replay_proof_pipeline_enabled=true` Config flip remain operator-fired only.

  **Commit 6 — Bridge-boot integration COMPLETE (2026-05-30):** Closes the honest gap surfaced post-activation: Arc 3 Curator was never instantiated in the live bridge boot, so the parallel `on_session_complete_vhr` hook I shipped in Commit 4.5 had no caller. Commit 6 adds: (a) `CuratorPackagingLoop(...)` construction in `main.py` boot (gated by `cfg.curator_packaging_enabled`, dormant by default), (b) optional `curator_loop=` kwarg on `SessionAdjudicatorValidationAgent` so the validator dispatches the VHR hook from inside `_validate_ruling` after the GIC stamp lands, (c) `Store.get_curator_session_aggregate(ruling_id)` that JOINs `agent_rulings` + `ruling_validation_log` into the orchestrator's expected dict shape, (d) `cfg.vhr_hook_enabled` (default False; the activation flag — separate from `replay_proof_pipeline_enabled`), (e) `cfg.session_gamer_address` (single-tenant testnet/dev gamer wallet). PV-CI invariants INV-VHR-WIRING-001/002/003 pin the kwarg signature + post-GIC-stamp call site + Store accessor. 10 new tests covering aggregate shape + hook dormancy across all 3 gates + fire-and-forget dispatch when all green. Activation now requires: `VHR_HOOK_ENABLED=true` + `SESSION_GAMER_ADDRESS=0x...` + `CURATOR_PACKAGING_ENABLED=true` in `.env` + a consent manifest on-chain for that gamer address, then bridge restart.
- **No action taken that spends wallet, deploys a contract, edits a FROZEN surface, or posts to a third party.** Wallet unchanged (~9.120 IOTX); `CHAIN_SUBMISSION_PAUSED=true`; no FROZEN-v1 surface modified.

### Working-tree note (non-blocking)
`git status` shows ~490 modified entries, but the overwhelming majority are
`contracts/node_modules/**` and `contracts/artifacts/**` churn (dependency +
build artifacts) plus deleted `.claude/worktrees/**` and a scheduled-tasks lock
— not source drift. No Data Economy source file shows unexpected modification.
A `node_modules`/`artifacts` cleanup is advisable but out of scope for this audit.

---

## 5. The true near-term sequence (honest dependency order)

1. **Build Arc 5** against the Arc 1–4 *code* artifacts (deploy-hold in force), resolving findings D-1…D-3 at the pre-investigation hold.
2. **Operator review** of the complete ladder (Arc 1 code+chain, Arcs 2–4 code, Arc 5 code).
3. **Batched deploy** — fire the held deploys (Arc 2 verifier, Arc 4 manifest registry, Arc 5 verifier) together, each behind its estimate_gas×1.25 + hard-cap guard, under explicit operator GO.
4. **Activate** — set the corresponding `*_ADDRESS` env vars to flip the dormant bridge read paths live.

Arc 5 is the architectural blueprint for the top rung of a ladder whose lower
rungs are built (and rung 1 partly deployed). It is not in progress as running
code, and it will not be until it is built and the batched deploy fires — which
is precisely where an honesty-first protocol should hold it.

---

*References: `docs/VAPI_REPLAY_PROOF_PIPELINE_SPEC (1).md` (Arc 5 spec),
`docs/arc4-consent-manifest-migration.md` (Arc 4 divergence),
`docs/data-economy-arc2-orchestration-workflow.md` (Arc 2 deploy handoff),
`contracts/deployed-addresses.json` (on-chain truth).*
