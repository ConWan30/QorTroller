# World Model Provenance Lane (WMP)

## Verified Human Action Provenance for World-Model Consumers

**Version:** 1.0 (v1 ship, fixtures-first per W1-D operator decision)
**Status:** Lane shipped 2026-06-06 — assembler + exporter + consumer verifier + Phase-2 consent registry stub
**Grounding:** Fei-Fei Li / World Labs, *A Functional Taxonomy of World Models* (June 2026)
**Additive over:** Arc 5 (VHR) + Arc 6 (PoSR) + Arc 4 (ConsentManifest)
**New FROZEN-v1 primitive:** NONE. **New PV-CI invariant:** NONE.

---

## 1. Honest POMDP placement

Li's taxonomy defines a single POMDP loop and three world-model functions:

- **Renderer** outputs **observations** (pixels). Contract: visual fidelity.
- **Simulator** outputs **state** (geometry / physics / dynamics). Contract: structural fidelity.
- **Planner** outputs **actions** (what to do next). Contract: closing perception → action.

**QorTroller is none of these.** It does not output pixels, synthesized state, or
decisions. It instruments the **agent → action edge** of a *real* human in the
loop and stamps that edge with cryptographic provenance.

In Li's own framing, QorTroller is not a world model — it is a
**provenance-attested source of the scarcest input the taxonomy names.**

Li states the bottleneck directly:

- Renderers are *"awash in internet video,"* but *"simulators and planners face
  acute shortages of 3D assets and robot demonstrations."*
- On planner demos: *"candor is required about what those demos actually
  show… none validated at the complexity, variability, or duration that
  real-world deployment demands."*
- The structural risk of generative data: synthetic output *"can look
  correct while containing… nonsensical physics."*

WMP answers exactly this gap in the **human action-demonstration channel**:
attach to a human action trace a cryptographic proof of *real human
authorship* (Arc 5 VHR), *real recency and session duration* (Arc 6 PoSR),
and *gamer consent* (Arc 4). The lane is the trust layer under the
demonstration data that planners and simulators are starved for — the
candor Li asks for, made cryptographic.

### What WMP can and cannot provide (state to every consumer)

- ✅ **CAN:** provenance-attested human **action** sequences (controller input
  dynamics), with proofs that the demonstrator was a real, recent,
  consenting human.

- ❌ **CANNOT:** the **observation** channel (what the human saw — the
  screen / game state). Capturing it is the framebuffer scope violation the
  protocol permanently forbids. Consumers receive the action edge, not
  full `(observation, action)` tuples. The schema's `scope_disclosure`
  block says so explicitly.

- ❌ **CANNOT (by design, and this is the safety property):** the
  biomechanical micro-signal. Exports are post-φ (60 Hz, 4-bit quantized,
  `FORBIDDEN_COLUMNS`-wiped). The anti-cheat's discriminative power lives
  in the high-frequency micro-tremor variance that φ destroys, so exported
  corpora cannot be used to train a bot past the liveness moat — the
  moat's signal is not in the export. Macro-intent (gameplay strategy)
  does export; that is already public in every esports replay and carries
  no liveness signal.

---

## 2. What the lane is / is not

**Is:** a packaging + export + consumer-verification layer over proofs
that already exist (VHR, PoSR, consent). It assembles a `ProvenanceBundle`
per consented session, exports batches in a training-friendly format, and
ships a **consumer-side verifier** so a world-model researcher can
cryptographically confirm "real human, real recency, real consent" before
trusting the data.

**Is NOT:**

- Not a generative model of human behavior (no adversary training target).
- Not a queryable "human-likeness scoring" oracle (static export only).
- Not synthetic-augmented (real sessions only — the realness IS the value;
  synthetic data would contaminate the one falsifiable empirical claim).
- Not a PoAC schema change (the 228-byte record is FROZEN; bundles
  reference proofs, never modify the record).
- Not a new commitment family or PV-CI category.

---

## 3. v1 architecture (this commit set)

### WMP-1 — `bridge/vapi_bridge/wmp/bundle_assembler.py`

Builds a `ProvenanceBundle` from a sanitized session matrix (Arc 5
post-φ), an Arc 5 VHR Groth16 proof, an Arc 6 PoSR open/close beacon
pair, and an Arc 4 consent reference. The assembler:

- **Reuses** `ReplayPreProcessor.FORBIDDEN_COLUMNS` directly (no fork) —
  the data-floor frozenset pinned by `INV-VHR-004`. Tested by identity
  comparison (`asm.forbidden_columns is ReplayPreProcessor.FORBIDDEN_COLUMNS`).
- Raises `DataFloorViolationError` if caller-supplied `extra_metadata`
  contains a forbidden field. Error fires **before** bundle assembly.
- Always emits a `scope_disclosure` block with FROZEN values
  (`ACTION_ONLY`, `ABSENT_BY_DESIGN_DATA_FLOOR`,
  `MACRO_INTENT_POST_PHI_NOT_BIOMECHANICAL`, `is_full_pomdp_tuple=False`).
- References (does not copy) the VHR / PoSR proofs by hex / address.

### WMP-2 — `scripts/wmp_export.py`

JSONL batch exporter with `corpus_manifest.json` index. Honest scope:

- **Deferred-export guard hard-returns `False` in v1.** Real-gamer data
  cannot leave the script. Per W1-D, the cryptographic consent leg lives
  in WMP-4 below and is undeployed in v1.
- `--allow-fixtures --fixture-corpus PATH` is the only enabled v1 path.
  Fixture bundles carry `scope_synthetic=True`.
- Idempotent + resumable — `bundle_hash` (SHA-256 of canonical JSON)
  dedupes across re-runs.
- `corpus_manifest.json` carries **no PII** — no gamer wallet, no
  device_id, no session_id beyond the opaque bundle hash.

### WMP-3 — `sdk/wmp_verify.py` + `scripts/verify_action_provenance.py`

The five-check consumer verifier. **This is the value-add of the lane.**

```
1. HUMANITY      — Arc 5 VHR Groth16 verify (v1: structural stub;
                   Phase-2 wires snarkjs)
2. MATRIX↔ROOT   — Poseidon(matrix) == sanitizedTraceRoot
                   (v1: STRUCTURAL_REHASH_v1 over canonical bytes;
                    Phase-2 promotes to Poseidon-over-BN254)
3. RECENCY       — Arc 6 verifyBeacon(open) + verifyBeacon(close)
                   + temporal-order check. Empty Arc 6 registry →
                   BEACON_REGISTRY_NOT_DEPLOYED honest no-op.
4. CONSENT       — Arc 4 reference + WMP world-model dimension.
                   v1: CONSENT_GATE_DEFERRED honest no-op (W1-D).
                   Phase-2 view-calls VAPIWorldModelConsentRegistry.
5. SCOPE HONESTY — scope_disclosure block must carry FROZEN values
                   verbatim; missing or overclaiming → REJECTED.
```

The matrix↔root re-hash check is the **canonical home** for the long-open
Arc 5 off-circuit root finding. The producer computes Poseidon once off-
circuit via `compute_inputs_replay_proof.js`; the consumer can be handed
a valid proof paired with a *different* matrix unless someone re-runs the
hash. **WMP-3 is the first and only place this check lives.**

### WMP-4 — `contracts/contracts/VAPIWorldModelConsentRegistry.sol`

Greenfield single-mapping consent registry. **NOT deployed in v1** —
ships as Solidity + Hardhat test + estimate-only deploy script.

```solidity
mapping(address => bool) private _worldModelConsent;
function setWorldModelConsent(bool granted) external {
    _worldModelConsent[msg.sender] = granted;  // msg.sender == gamer
    ...
}
function isWorldModelConsentGranted(address gamer) external view returns (bool);
```

The contract is the cryptographic path that lifts WMP-2's
`world_model_consent_present(gamer)` from "always False" to a live
on-chain view-call.

**Why greenfield and not Arc 4 v2?** The Arc 4
`VAPIConsentManifestRegistry` is already deployed at `0x5F7c8068…`; its
struct layout is frozen by Solidity storage rules. Adding a Dimension 9
field requires an Arc 4 v2 redeploy plus a per-gamer migration write.
Greenfield sidesteps both.

**Why distinct from replay consent?** A gamer can grant Arc 4
`allowReplayProofs=true` (sell replays) while withholding world-model
consent (refuse training-corpus export), or vice versa. Granular
sovereignty across distinct buyer / use-case classes.

---

## 4. W1-D operator decision rationale

The spec considered three W1 options:

- **W1-A** — new Dimension 9 in Arc 4 manifest. **Non-operational** in v1
  because Arc 4 is already deployed and its struct layout is storage-
  frozen by Solidity. A "W1-A-v2" path exists (Arc 4 v2 redeploy +
  migration) but pays the redeploy cost up front.
- **W1-B** — reuse Arc 4 Dimension 8 (`allowReplayProofs`). Sovereignty-
  weaker (conflates two distinct uses); operational today. Acceptable
  *only* if every WMP bundle's `scope_disclosure` discloses the
  conflation explicitly.
- **W1-C** — off-chain `world_model_export_consented` flag in the
  bridge's `consent_ledger`. **Trust regression** — moves consent out of
  the cryptographically-verifiable set; consumers must trust QorTroller
  on the consent leg. The off-chain → on-chain migration story is also
  broken (the bridge writing a gamer's consent forges what
  `msg.sender == gamer` exists to forbid).
- **W1-D (operator-chosen)** — build the full lane on fixtures + ship a
  flagged minimal greenfield contract as Phase-2 promote. Preserves
  cryptographic verifiability of every leg; zero on-chain cost in v1
  (matches W1-C's cost benefit without its regression); when the first
  real buyer needs export, deploy WMP-4 (small contract, no migration).

W1-D is what shipped.

---

## 5. Consumer quickstart

For a world-model researcher who wants to **verify** a corpus without
trusting QorTroller's infrastructure:

```bash
# Single bundle (e.g., fixture):
python scripts/verify_action_provenance.py \
    --bundle path/to/bundle.json \
    --allow-synthetic

# JSONL corpus:
python scripts/verify_action_provenance.py \
    --corpus path/to/wmp_corpus.jsonl \
    --allow-synthetic
```

Output: one JSON line per bundle plus a summary line. Exit 0 iff ALL
bundles VERIFIED. `--allow-synthetic` accepts `scope_synthetic=True`
fixtures; without it, synthetic bundles are REJECTED (the v1 export path
only produces synthetic / fixture bundles, so the flag is required for
v1 end-to-end testing).

---

## 6. Honesty rails (held across every WMP commit)

1. **Post-φ only.** Exports contain only the Arc 5 sanitized macro-intent
   matrix. Raw HID, L4 features, biometric snapshots, and any
   observation/screen data NEVER export. Enforced by the reused Arc 5
   `FORBIDDEN_COLUMNS` guard.

2. **No generative model, no scoring oracle.** The lane exports static
   data and verifies provenance. It never builds a predictor of human
   behavior and never exposes a queryable human-likeness endpoint.

3. **No synthetic contamination.** Real sessions only (when v1's
   deferred-export guard lifts in Phase-2). The corpus's value is that
   every trace is real and provenance-proven; a synthetic trace would
   void that claim and must never enter the real-data export path.

4. **Action channel only, disclosed.** Every bundle's `scope_disclosure`
   states the observation channel is absent by design and the fidelity
   is macro-intent, not biomechanical. No consumer may be allowed to
   over-claim full-tuple or biometric-grade data.

5. **No FROZEN edit, no new commitment family, no PV-CI category change.**
   WMP-4 adds a Solidity contract for consent infrastructure; it does
   not touch the FROZEN `VAPI-CONSENT-v1` family (that preimage belongs
   to the per-category `VAPIConsentRegistry` and is unrelated).

6. **QorTroller is a provenance source, not a world model.** Every WMP
   doc and SDK surface states this placement explicitly.

7. **Cryptographic verifiability preserved.** W1-D's deferral path keeps
   every leg (humanity, recency, consent) on a cryptographic track. The
   v1 stubs are clearly labeled; the Phase-2 promote replaces them with
   on-chain view-calls and full Groth16 verify.

---

## 7. Phase-2 promote checklist

When the first real world-model buyer needs export:

1. **Deploy WMP-4** —
   `VAPI_WMC_DEPLOY_CONFIRM=1 npx hardhat run scripts/deploy-vapi-world-model-consent-registry.js --network iotex_testnet`.
   Estimate-only cost: target ~0.10–0.30 IOTX (tiny contract).
2. **Wire the bridge** — set `WORLD_MODEL_CONSENT_REGISTRY_ADDRESS=<deployed>`
   in `bridge/.env`. WMP-2's `world_model_consent_present(gamer)` reads
   the registry view-call.
3. **Gamer consent flow** — surface "Grant world-model export" in the
   Consent Cockpit dApp (`/consent`). Wired identically to
   `VAPIConsentRegistry.grantConsent` — `msg.sender == gamer` enforced
   by the contract; bridge cannot write.
4. **Promote WMP-3 stubs** — wire `snarkjs groth16 verify` against the
   published verifying key; wire `verifyBeacon` view-calls against the
   live Arc 6 registry; swap `STRUCTURAL_REHASH_v1` for
   Poseidon-over-BN254 via `circomlibjs` Node helper.
5. **First real-corpus export** — `wmp_export.py` `world_model_consent_present`
   lambda flips to view-call result.

Nothing on this list spends IOTX before there is a paying buyer.

---

## 8. References

- *A Functional Taxonomy of World Models* — Fei-Fei Li / World Labs, June 2026
- Arc 5 (VHR) — `bridge/vapi_bridge/replay_proof_pipeline/`
- Arc 6 (PoSR) — `VAPITemporalBeaconRegistry` LIVE `0x962440312a995b21d4E203bE6d93021CC22bA051` (deployed 2026-06-05; keeper unset)
- Arc 4 (ConsentManifest) — `VAPIConsentManifestRegistry` LIVE `0x5F7c8068D0e61818FCD613D47e68a9Ea906a2743`
- FROZEN data-floor — `ReplayPreProcessor.FORBIDDEN_COLUMNS` (`pre_processor.py:162`), pinned by `INV-VHR-004`
- Off-circuit root finding (now closed) — Arc 5 spec §1.2 / §6 + WMP-3 `check_matrix_root_rehash`
