# Data Economy Arc 2 — VAPIBuyerCategoryVerifier (ZK Circuit) — Subagent-Orchestration Workflow

> **How to use this file.** Paste this whole document into a fresh Claude Code
> session as the opening prompt. The session acts as the **orchestrator**: it
> does NOT build Arc 2 directly. It spawns one subagent per phase (via the Agent
> tool), reviews each subagent's report, holds for operator review at the marked
> checkpoints, and only advances when the operator says go. This is the
> agent-orchestration shape — a workflow expressed in a prompt — not the `/vapi`
> skill layer.
>
> **Authority documents (read these first; they are the spec, this file is only
> the orchestration over them):**
> - `C:\Users\Contr\Downloads\QORTROLLER_DATA_ECONOMY_FRAMEWORK (1).md` — §8 "Arc 2
>   — VAPIBuyerCategoryVerifier (ZK Circuit)" is the canonical circuit + bridge
>   spec. The orchestrator and every subagent treat this section as authoritative.
> - `C:\Users\Contr\Downloads\CURATOR_GOVERNANCE_SUBMISSION_PACKAGE (1).md` — CAP-001
>   buyer attestation + constraint inventory C-01..C-10 (data floor, two-key gate,
>   kill-switch). Binding constraints on what Arc 2 may and may not do.
>
> If the live repo disagrees with these docs, **stop and surface the drift** —
> do not silently build to either side. (Arc 1 shipped after exactly this kind of
> drift was caught: the briefing's "buyerAddr/3-cat" reading was wrong; both docs
> said buyerDID/4-cat, which is what deployed.)

---

## Gate — Arc 2 does not start until all of these are true

1. **Arc 1 complete.** Verify on `feat/gameplay-workflow-layer`:
   - `9f8863a9` VAPIBuyerRegistry source + Hardhat tests
   - `d3b7aa71` registry deployed `0x3742189eBDC09B115FA7e841C884247E9856130B` +
     setCuratorWallet fired (curatorWallet = bridge wallet)
   - `f32ba1a7` bridge read path (`is_valid_buyer_credential` / `get_buyer_category`,
     60s TTL, fail-open) + PV-CI INV-BUY-001/002
   - the Commit 2 hash for `bridge/vapi_bridge/curator_attestation.py`
     (`CuratorAttestationModule`) + its 5 tests
2. **Curator attestation operational.** `CuratorAttestationModule.attest_buyer`
   exists, defaults `dry_run=True`, and the on-chain writer path is reachable
   (curatorWallet set). Arc 2's circuit proves possession of a credential that
   this module issues — so Arc 1 issuance must work first.
3. **Operator has authorized an Arc 2 wallet spend.** Arc 2 deploys a Groth16
   verifier contract (~0.5–0.8 IOTX). That deploy is operator-fired only. The
   orchestrator and subagents NEVER fire it autonomously.

If any gate fails, stop and report. Do not partially execute Arc 2.

---

## Pre-investigation findings already in hand (do NOT re-derive)

The Arc 1 closing session ran the framework's Arc 2 pre-investigation checklist
read-only. Bake these into the subagent prompts so Phase 0 confirms rather than
rediscovers:

- **PTAU reusable.** `contracts/circuits/pot15_final.ptau` and
  `contracts/ptau/hermez_final_15.ptau` exist (2^15 = 32,768-constraint capacity).
  BuyerCategoryProof is small (~few thousand constraints) → pot15 is sufficient;
  no new powers-of-tau ceremony needed.
- **Poseidon is the house hash.** All 4 existing circuits
  (`PitlSessionProof`, `TeamProof`, `TournamentPassport`, `ZKSepProof`) include
  `circomlib/circuits/poseidon.circom`. `PitlSessionProof` uses `Poseidon(8)`.
  The framework's `nullifierHash = Poseidon(buyerDID, credentialNonce)` matches
  this exactly — use circomlib Poseidon, same as the rest of the protocol.
- **Semaphore-style nullifiers are NOT net-new.** `PitlSessionProof` C5 is
  `nullifierHash = Poseidon(deviceIdHash, epoch)` ("anti-replay; stored on-chain
  after use"); `TeamProof` is `Poseidon(merkleRoot, identitySecrets[0], epoch)`.
  Arc 2 reuses an established QorTroller anti-replay pattern → scope is smaller
  than the framework checklist's "if not, this is net-new" branch implied.
- **Verifier deploy pattern exists.** `contracts/contracts/PitlSessionProofVerifier.sol`
  (+ `PitlSessionProofVerifierV2.sol`) is the Groth16-verifier precedent.
  `snarkjs ^0.7.6` is in `contracts/package.json`; `circom.exe` v2.2.3 is in
  `contracts/` (per CLAUDE.md gotchas). `snarkjs zkey export solidityverifier`
  generates the `.sol`. Deploy scripts: `contracts/scripts/run-ceremony.js`,
  `run-mpc-ceremony.js`, `deploy-ceremony-registry.js`.

Phase 0's job is to CONFIRM these are still true and map the exact deploy script
+ ABI-registration call surface — not to re-search from scratch.

---

## Orchestration model

The orchestrator (you, the main session) runs the loop:

```
for each phase P in [0,1,2,3,4,5]:
    spawn subagent with P's prompt (below)
    receive subagent report
    if report surfaces drift or a blocker: stop, surface to operator, wait
    else: present report + "Hold for operator review before Phase P+1"
    wait for operator go
```

- **Phase 0** (read-only) → `Explore` subagent.
- **Phases 1, 2, 4, 5** (build/code) → `general-purpose` subagent, one per phase,
  each told explicitly to WRITE code and run tests.
- **Phase 3** (on-chain deploy) → **NO subagent.** Operator-fired script only.
  The orchestrator prepares the command and waits; it never spawns an agent that
  could broadcast.

Every build subagent prompt must carry the safety rails (bottom of this file)
verbatim. Subagents start cold — give them the authority-doc paths, the
pre-investigation findings above, and the exact files to touch.

---

## Phase 0 — Pre-investigation confirmation (Explore subagent, read-only)

**Spawn:** `Agent(subagent_type="Explore", ...)`

**Prompt to the subagent:**
> Read-only investigation for QorTroller Data Economy Arc 2 (ZK buyer-category
> verifier). Authority: `Downloads/QORTROLLER_DATA_ECONOMY_FRAMEWORK (1).md` §8.
> Confirm (do not re-derive — these were found in the Arc 1 session, verify still
> true): (1) `contracts/circuits/pot15_final.ptau` exists and is 2^15;
> (2) circomlib Poseidon is includable from `contracts/node_modules`;
> (3) `PitlSessionProofVerifier.sol` is the Groth16-verifier deploy precedent —
> read its deploy script and how its address + ABI get registered into the bridge
> (`contracts/deployed-addresses.json` + `bridge/vapi_bridge/chain.py`);
> (4) `snarkjs`/`circom` toolchain present and runnable. ALSO map: what does the
> existing PitlSession verifier deploy script do step-by-step, so Arc 2 can mirror
> it. Report under 400 words: confirmed / drifted, plus the exact deploy + ABI-reg
> call surface. Do NOT write code.

**Checkpoint:** orchestrator presents findings. **Hold for operator review before Phase 1.**

---

## Phase 1 — `VAPIBuyerCategoryVerifier.circom` (general-purpose subagent, writes code)

Build the circuit per framework §8. The template (from the doc):

```circom
pragma circom 2.0.0;
include "poseidon.circom";          // circomlib, same path as PitlSessionProof.circom

template BuyerCategoryProof() {
    // Private: buyerDID, credentialNonce, categoryId, issuedAt, expiresAt,
    //          curatorSigR, curatorSigS
    // Public:  claimedCategory, currentTimestamp, curatorPubkey, nullifierHash
    // Constraints:
    //   1. categoryId === claimedCategory
    //   2. currentTimestamp < expiresAt        (not expired)
    //   3. Curator signature valid over (buyerDID, categoryId, issuedAt, expiresAt)
    //   4. nullifierHash === Poseidon(buyerDID, credentialNonce)
    signal output valid;
}
```

**Subagent instructions:**
- Match the include path style of `contracts/circuits/PitlSessionProof.circom`
  (`include "../../node_modules/circomlib/circuits/poseidon.circom";`).
- Reuse the nullifier construction shape from `PitlSessionProof` C5.
- For Constraint 3 (Curator ECDSA-P256 sig in-circuit): this is the hard part.
  Check whether an existing circuit verifies ECDSA-P256 in-circuit; if none does,
  surface the cost (ECDSA-in-circuit is expensive) and propose the framework
  decision: either (a) verify the Curator sig in-circuit, or (b) prove membership
  against a Poseidon commitment the Curator publishes on-chain (cheaper, mirrors
  the registry's existing `evidenceHash`/event model). **Do not pick silently —
  surface both with constraint-count estimates and stop for operator decision.**
- Compile to `.r1cs` + `.sym` + `_js` using the in-repo `circom.exe`. Report
  constraint count vs the pot15 ceiling (32,768).

**P-check:** circuit compiles; constraint count under pot15; no change to any
existing circuit. **Hold for operator review before Phase 2.**

---

## Phase 2 — Proving key + Groth16 verifier `.sol` generation (general-purpose subagent, writes code)

**Subagent instructions:**
- Using `snarkjs` + the reusable `pot15_final.ptau`: `groth16 setup` →
  contribute (a local single-contributor `zkey` is fine for the FIRST prototype;
  the MPC ceremony for the production zkey mirrors `run-mpc-ceremony.js` and is a
  later operator-run step — DO NOT run a multi-party ceremony autonomously).
- Export `VAPIBuyerCategoryVerifier_verification_key.json`.
- `snarkjs zkey export solidityverifier` → `contracts/contracts/VAPIBuyerCategoryVerifier.sol`.
  Verifier contract must match the `PitlSessionProofVerifier.sol` structural
  pattern.
- Add a Hardhat test mirroring the PitlSession verifier tests: a known-good proof
  verifies true, a tampered proof verifies false (use a `Mock` if needed, like
  `contracts/contracts/test/MockZKSepProofGroth16Verifier.sol`).

**P-check:** Hardhat verifier tests pass (target: 6, per framework §8 P-check);
`vapi_invariant_gate.py` 0 violations; no existing contract modified.
**Hold for operator review before Phase 3.**

---

## Phase 3 — Verifier deploy (OPERATOR-FIRED ONLY — no subagent)

This is the `/goal` / autonomy boundary. The orchestrator does NOT spawn an
agent here and does NOT broadcast.

- Orchestrator prepares the deploy command mirroring the PitlSession verifier
  deploy script, with a dry-run / estimate-only first pass.
- Orchestrator presents: estimated gas (~0.5–0.8 IOTX), the exact command, and
  the current wallet balance.
- **Operator runs the deploy themselves** (or explicitly authorizes a single
  `--execute` invocation). On success, operator provides tx hash + address.
- Orchestrator then registers the address in `contracts/deployed-addresses.json`
  and the verifier ABI in `bridge/vapi_bridge/chain.py` (mirroring how the
  PitlSession verifier is registered).

**Hold for operator review before Phase 4.**

---

## Phase 4 — Bridge integration `zk_buyer_verifier.py` (general-purpose subagent, writes code)

Per framework §8:

```python
# bridge/vapi_bridge/zk_buyer_verifier.py
def verify_buyer_category_proof(proof: bytes, claimed_category: int,
                                current_timestamp: int) -> bool:
    """Calls VAPIBuyerCategoryVerifier on-chain. Returns True if proof valid."""
```

**Subagent instructions:**
- Mirror the READ posture of the Arc 1 buyer views: fail-open (return False when
  the verifier address is unset or chain unavailable — an unavailable verifier
  must NEVER grant access). This matches the `is_valid_buyer_credential`
  precedent and constraint C-* on the kill-switch.
- The verifier call is a `view`/`staticcall` — no wallet spend, no gating needed
  beyond the existing read path. Do NOT add a writer.
- Add the verifier address to `config.py` like `buyer_registry_address`
  (defaults to the Phase 3 address once known; empty-string-safe before deploy).

**P-check:** bridge integration tests (target: 3, per framework §8) — proof
verifies true path, fail-open when address unset, fail-open when chain raises;
full bridge suite no regressions; invariant gate clean.
**Hold for operator review before Phase 5.**

---

## Phase 5 — Tests sweep + arc close (general-purpose subagent, writes code/docs)

**Subagent instructions:**
- Confirm full P-check per framework §8: "circuit constraints verified (all
  inputs, all edge cases), verifier contract Hardhat tests (6), bridge
  integration tests (3)."
- Run the full bridge suite (`--ignore=test_e2e_simulation.py`), the Hardhat
  suite, `vapi_invariant_gate.py`, and Mythos crypto/frozen drift. All clean.
- Draft the Arc 2 closing memory entry + MEMORY.md index line (do not invent
  numbers — read them from the actual run).

**The framework's terminal instruction for Arc 2: "Hold for operator review
before Arc 3."** The orchestrator stops here. Arc 3 (Post-Session Curator
Packaging Loop) is a separate workflow.

---

## Safety rails (paste verbatim into every build-subagent prompt)

- **Authority is the two Downloads docs.** If the repo contradicts them, stop and
  surface drift; never silently build to one side.
- **No autonomous wallet spend, no autonomous deploy.** Phase 3 is operator-fired.
  No subagent may call `send_raw_transaction`, run a `--execute` deploy, or run a
  multi-party ceremony. Dry-run / estimate-only only.
- **No FROZEN-surface edits.** Do not touch the 228-byte PoAC wire format, the
  PATTERN-017 commitment families, existing circuits, or the deployed
  VAPIBuyerRegistry. INV-BUY-001 (category enum 1..4) stays frozen.
- **Fail-open reads, fail-loud writes.** The bridge verifier read returns False
  when dormant (never grants access on an unavailable verifier). Any write path
  must propagate reverts, never swallow them.
- **No posting under the operator's identity** to any governance / third-party
  surface.
- **Honesty:** report real constraint counts, real gas, real test counts. A
  failing or skipped test is reported as such — never papered over. If the
  in-circuit Curator-sig decision (Phase 1) is unresolved, say so and stop.

Standing by for Phase 0.
