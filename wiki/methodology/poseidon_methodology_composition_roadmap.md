# Poseidon Methodology-Layer Composition Roadmap — Future-Vector Orchestration

**Document type:** Forward-vector orchestration roadmap (planning artifact only — executes nothing)
**Author:** VAPI Principal Architect
**Date:** 2026-05-14
**Status:** DRAFT roadmap — sequences phases that begin AFTER Phase O4-W3B-POSEIDON-AS lands
**Prerequisite (hard dependency):** `wiki/phases/phase_o4_w3b_poseidon_as.md` — the POSEIDON-BN254-AS capability + the 3 PV-CI invariants (INV-POSEIDON-AS-001/002/003) MUST exist on `main` before ANY phase in this roadmap can begin.

---

## 0. What this document is — and is not

This is a **planning artifact**. It sequences how VAPI's methodology layer (Layer 7) composes against a cryptographic capability that is *currently being shipped by a separate, in-flight plan* — Phase O4-W3B-POSEIDON-AS. It does not implement, modify, deploy, or execute anything. Every phase it describes is gated on that prerequisite plan landing first.

The roadmap covers four synergies, in priority order:

1. **ZKBA-ZK variant** (LEAD — fullest treatment) — a Poseidon-committed variant of PATTERN-017 family member #10 whose commitment is a valid Groth16 public input.
2. **VSD interconnection** — the Poseidon vector corpus as an architect-signed VSD-vault manifest; a Poseidon-Merkle of VSD-vault manifests.
3. **VED / VBDIP-0001 catalog entry** — the differential-self-check-at-generation-boundary pattern as a catalogable Verified Engineering Discipline.
4. **Poseidon Reproducibility Card VPM** — the vector corpus rendered as a Verified Projection Media compiler target under the 3-layer Anti-Hype Visual Grammar.

---

## 1. Context — POSEIDON-BN254-AS and the ZK-adjacent vs ZK-native boundary

### 1.1 What POSEIDON-BN254-AS is

Phase O4-W3B-POSEIDON-AS (plan at `wiki/phases/phase_o4_w3b_poseidon_as.md`, DRAFT status as of 2026-05-14) ships **POSEIDON-BN254-AS**: a protocol-internal AssemblyScript implementation of Poseidon over the BN254 scalar field, for the W3bstream applet `scripts/w3bstream/validate_poac_record.ts`. It covers the three internal-state arities the deployed VAPI circuits use — circomlib `Poseidon(1)/Poseidon(2)/Poseidon(8)` for deviceIdHash / nullifierHash / featureCommitment respectively. It is validated by differential testing against circomlibjs 0.1.7 (and, on the GREEN preflight path, a second independent reference), carries a deterministic test-vector corpus, and is pinned by 3 new PV-CI invariants (INV-POSEIDON-AS-001/002/003), taking the PV-CI gate from **83 → 86**.

The prerequisite plan is explicit on one framing point, and this roadmap inherits it verbatim: **POSEIDON-BN254-AS is a protocol-internal cryptographic *capability*, not an 11th PATTERN-017 commitment family.** The PATTERN-017 commitment-family count stays at **10**. POSEIDON-BN254-AS is the hash-function capability that *supports* PATTERN-017 #8 (ZK-SEPPROOF) and the Phase 62 PitlSessionProof circuit by making their commitment computation verifiable in-applet — it is not itself a domain-tagged commitment producer in the PATTERN-017 sense.

### 1.2 The ZK-adjacent vs ZK-native boundary — the load-bearing insight

VAPI's methodology layer currently contains constructs *named* "ZK" whose own commitment is **not in-circuit-verifiable**. The clearest case is PATTERN-017 family member #10: the Zero-Knowledge Biometric Artifact (ZKBA), implemented in `bridge/vapi_bridge/zkba_artifact.py`. `compute_zkba_commitment()` hashes with **SHA-256** under the FROZEN domain tag `b"VAPI-ZKBA-ARTIFACT-v1"` (21 bytes). ZKBA artifacts *reference* ZK-proven state — they compose commitments of FROZEN-v1 primitives, several of which are themselves anchored against on-chain ZK verifier deploys — but the ZKBA commitment **itself** cannot be a Groth16 public input efficiently. SHA-256 costs roughly 25k constraints per block in a Groth16 circuit; Poseidon costs roughly 200–1200 depending on arity. A SHA-256-committed artifact named "ZK" is therefore **ZK-adjacent**: it sits next to ZK-proven state and inherits trust by reference, but the artifact's own commitment is not natively provable in zero knowledge.

POSEIDON-BN254-AS is the **first protocol-internal primitive that bridges this boundary**. Before it, VAPI had no agent-runtime-verifiable Poseidon implementation at all — that is precisely the gap the prerequisite plan closes (the `POSEIDON_HASH` delta in `scripts/w3bstream_applet_audit.py` was atomic-stopped on exactly this absence per the 2026-05-14 streams-continuation NOTE in `CLAUDE.md`). Once POSEIDON-BN254-AS exists and is invariant-pinned, the methodology layer can — for the first time — produce **ZK-native** commitments: commitments computed with a hash whose output lands in the BN254 scalar field and is therefore a valid circuit public input.

This roadmap sequences the methodology-layer work that becomes possible *because* that boundary is now bridgeable.

### 1.3 Hard dependency restated

Every phase below has the same gate: **Phase O4-W3B-POSEIDON-AS must land on `main` first**, specifically producing (a) the `poseidon_bn254.ts` AS module with the three arity entry points, (b) the committed test-vector corpus, and (c) the 3 PV-CI invariants INV-POSEIDON-AS-001/002/003 in `scripts/vapi_invariant_gate.py` with the allowlist regenerated to 86 entries. Until those three artifacts exist, this roadmap is inert.

---

## 2. SYNERGY 1 (LEAD) — ZKBA-ZK variant: a Poseidon-committed ZKBA whose commitment is a valid Groth16 public input

> **This is the highest-leverage phase the roadmap sequences. It is given a near-phase-plan shape below; the other three synergies are sketched at lower resolution.**

### 2.1 The gap the ZKBA-ZK variant closes

Today `compute_zkba_commitment()` (`bridge/vapi_bridge/zkba_artifact.py`, FROZEN FORMULA v1) produces:

```
ZKBA_commitment = SHA-256(
    _DOMAIN_TAG(21)            # b"VAPI-ZKBA-ARTIFACT-v1"
    || zkba_class_byte(1)
    || proof_weight_byte(1)
    || n_components_byte(1)
    || sorted_component_hashes(n × 32)
    || ts_ns_be(8)
) = 32B
```

This is the FROZEN-v1 formula and **stays FROZEN — it is not touched**. The ZKBA-ZK variant is exactly that: a *variant of the existing PATTERN-017 family member #10*, not a new family and not a v2 break of the existing one. It introduces a second, parallel commitment path that uses Poseidon instead of SHA-256, selected explicitly per-artifact, while the SHA-256 path remains the default and the v1 byte layout remains permanently frozen.

The payoff: a Poseidon-committed ZKBA commitment is an element of the BN254 scalar field. It can be a Groth16 public input directly. That makes it possible to prove, in zero knowledge, **"I hold a ZKBA artifact whose commitment is X"** — without revealing the preimage (the component hashes, the class, the proof weight, the timestamp). This is what the "ZK" in "ZKBA" always implied at the naming level but the SHA-256 implementation never delivered. POSEIDON-BN254-AS closes the gap between the name and the cryptographic shape.

### 2.2 What the variant is — precise scope

A **ZKBA-ZK artifact** is a ZKBA artifact (PATTERN-017 #10, class ∈ the 7 ZKBAClass values, proof_weight ∈ the 6 ProofWeightClass values) whose `input_commitment` is computed via a Poseidon sponge over BN254 instead of SHA-256, such that the resulting commitment is a single BN254 field element renderable as a 64-char hex string AND directly usable as a Groth16 public input. The component-hash composition discipline is preserved conceptually — components are still combined canonically (sorted, length-prefixed) — but the combining hash is Poseidon, and each component must itself be reduced into / be representable in the scalar field. The exact arity selection (how many Poseidon permutations, what the sponge rate/capacity split is, how `n` components fold into the fixed-arity entry points POSEIDON-BN254-AS exposes) is a **design decision deferred to the phase plan itself** — this roadmap does not pin it, because it depends on the final shape of the AS module's arity entry points, which only become FROZEN when Phase O4-W3B-POSEIDON-AS lands.

What it is **not**:
- Not an 11th PATTERN-017 commitment family. It is a variant of #10. The family count stays 10.
- Not a replacement for SHA-256 ZKBA. The SHA-256 path is the default and remains; ZKBA-ZK is opt-in per-artifact via a manifest field (see §2.4).
- Not a v2 of the FROZEN ZKBA formula. `compute_zkba_commitment()` v1 is byte-stable forever. The Poseidon path is a *new function* alongside it, with its own FROZEN-v1 discipline once shipped.

### 2.3 Why this is leverage, not just a feature

The methodology layer's central architectural claim is **"verifiable claims with visible limits"** (per the Whitepaper v4 framing, `9a335c1b`). A ZKBA artifact named "Zero-Knowledge Biometric Artifact" whose commitment cannot be proven in zero knowledge is a *visible limit* — an honest gap between name and shape that VAPI has correctly documented rather than hidden. The ZKBA-ZK variant converts that visible-limit into a delivered capability. After it lands, the methodology layer can say: ZKBA artifacts marked `commitment_hash_algo: poseidon-bn254` have commitments that ARE valid Groth16 public inputs, and the "ZK" in their name is cryptographically substantiated, not aspirational.

It also unlocks the downstream composability the Appendix A forward-extensions in `VBDIP-0002-zkba-visual-projections.md` gesture at — §A.1 ZKBA-PROVENANCE-COMPOSITE and §A.4 ZKBA-DUAL-ANCHOR both become structurally cleaner when the artifact commitment is field-native, because a Poseidon-Merkle over ZKBA-ZK commitments is itself in-circuit-provable (this connects directly to SYNERGY 2 below).

### 2.4 Concrete amendment path — VBDIP-0002 v1.x amendment + G4 validator branch

The variant requires a schema amendment. The concrete path:

**(a) VBDIP-0002 v1.x amendment adding `commitment_hash_algo`.** The `vapi-zkba-manifest-v1` schema (defined at VBDIP-0002 §9.2, FROZEN at v1.0; the implementation schema literal is `vapi-zkba-manifest-v1`, the design-time spec name is `zkba.projection_manifest.v1` — both are recognized per the documented schema-name drift in `scripts/zkba_manifest_validator.py`) gains one new optional field:

```
commitment_hash_algo: "sha256" | "poseidon-bn254"
```

Absence ⇒ `"sha256"` (the FROZEN-v1 default; every existing artifact and every existing manifest remains valid with zero migration). Presence of `"poseidon-bn254"` marks a ZKBA-ZK artifact. Because this is an *additive optional field* with a default that preserves all prior behavior, it is a v1.x amendment, not a v2.0 break — consistent with the additive-amendment discipline VBDIP-0002 already used for its v1.1 Appendix B absorption.

**The amendment text itself is NOT drafted by this roadmap.** Authoring a VBDIP-0002 v1.x amendment is an **OPERATOR-GATED governance ceremony** — it touches a FROZEN methodology proposal, and the supersession discipline plus the architect Ed25519 signing chain (`vsd-vault/eval/architect_key_attestation.json`) both apply. This roadmap flags it as operator-runtime work and stops there. It does not write the amendment, does not pre-stage the schema diff, does not modify `VBDIP-0002-zkba-visual-projections.md`.

**(b) `zkba_manifest_validator.py` (G4 validator) branch.** `scripts/zkba_manifest_validator.py` currently validates the 8-field FROZEN ZKBAManifest shape (`REQUIRED_FIELDS` frozenset) and never raises (fail-open `ManifestValidationResult`). The amendment requires a new validator branch: when `commitment_hash_algo == "poseidon-bn254"` is present, the validator additionally asserts that `input_commitment_hex` is a valid BN254 scalar-field element (i.e. the 256-bit value it encodes is `< r`, the BN254 group order — the authoritative `r` literal is at `contracts/contracts/Groth16VerifierZKSepProof.sol:24-27` per the prerequisite plan's reuse table). When the field is absent or `"sha256"`, the validator behaves exactly as today. This branch is **agent-actionable** (it is wallet-free, side-effect-free, import-safe Python) — but it is gated on the v1.x amendment landing first, because the validator must not recognize a schema field the amendment hasn't yet defined.

### 2.5 Sequencing within the ZKBA-ZK phase

A coherent ordering for the eventual phase (each gates the next; this is the *recommended* sequence, not an executed one):

1. **Z.0 — Prerequisite confirmation.** Verify Phase O4-W3B-POSEIDON-AS landed: `poseidon_bn254.ts` present, test-vector corpus present, INV-POSEIDON-AS-001/002/003 in the allowlist, PV-CI gate at 86. If not, halt — the roadmap phase cannot begin.
2. **Z.1 — VBDIP-0002 v1.x amendment** (OPERATOR-GATED governance ceremony). Operator authors + architect-signs the `commitment_hash_algo` schema amendment. Agent does not perform this.
3. **Z.2 — `zkba_manifest_validator.py` Poseidon branch** (agent-actionable, post-Z.1). New validator branch for `poseidon-bn254`: BN254 field-element range check on `input_commitment_hex`. Test band added. Wallet-free.
4. **Z.3 — Poseidon ZKBA commitment function** (agent-actionable, post-Z.1). A new function alongside `compute_zkba_commitment()` in (or beside) `bridge/vapi_bridge/zkba_artifact.py` — its own FROZEN-v1 discipline, its own domain separation, computing the Poseidon path. The SHA-256 `compute_zkba_commitment()` is untouched. Differential-tested against the POSEIDON-BN254-AS vector corpus so the bridge-side Python path and the applet-side AS path agree byte-for-byte.
5. **Z.4 — PV-CI invariant for the Poseidon ZKBA path** (OPERATOR-GATED governance ceremony). Pins the new function signature + domain separation, mirroring the INV-ZKBA-001/002/003 pattern. Takes PV-CI 86 → 87+. Requires the `--confirm-governance` ceremony.
6. **Z.5 — One ZKBA-ZK artifact target** (agent-actionable, post-Z.3). The first concrete ZKBA-ZK artifact — sequenced the same way the 7 existing ZKBA artifact targets were (GIC ledger → VHP card → AIT snapshot → … → HARDWARE card). The natural first target is the class whose downstream consumer most wants in-circuit verifiability — a strong candidate is **AIT** (the AIT separation snapshot is the headline empirical anchor, ratio=1.199 N=37, and an in-circuit-provable AIT commitment lets a gamer prove "my biometric corpus cleared the separation gate" without revealing the corpus). The specific first target is a phase-plan decision, not pinned here.
7. **Z.6 — docs sync.** `CLAUDE.md` NOTE + `MEMORY.md` index entry. Pure docs.

Steps Z.1 and Z.4 are operator-runtime governance ceremonies; the agent cannot execute `--confirm-governance` autonomously per the Hard Rules. Steps Z.2, Z.3, Z.5, Z.6 are wallet-free agent-actionable work, each gated on its predecessor.

### 2.6 Files this synergy grounds against (verified present at this worktree HEAD)

- `bridge/vapi_bridge/zkba_artifact.py` — FROZEN ZKBA primitive (PATTERN-017 #10); `compute_zkba_commitment()` + `ZKBAClass` (7 values) + `ProofWeightClass` (6 values) + `ZKBADraftResult`. Confirmed present.
- `scripts/zkba_manifest_validator.py` — G4 validator; `validate_zkba_manifest()` + `ManifestValidationResult` + `REQUIRED_FIELDS` + `DEFAULT_PROOF_WEIGHT_BY_CLASS`; documents the `vapi-zkba-manifest-v1` ↔ `zkba.projection_manifest.v1` schema-name drift. Confirmed present.
- `wiki/methodology/VBDIP-0002-zkba-visual-projections.md` — VBDIP-0002 with v1.1 Appendix B amendment; §9.2 Projection Manifest Schema (schema FROZEN at v1.0); §5 ZKBA Artifact Classes; §6 Proof-Weight Honesty Taxonomy. Confirmed present.

---

## 3. SYNERGY 2 — VSD interconnection

Two distinct interconnections between POSEIDON-BN254-AS and the Verified Synthesis Discipline (VSD), one of the three VAD sub-disciplines under VBDIP-0001 (`wiki/methodology/VBDIP-0001-vad-framework-introduction.md`; the VSD-vault lives at `vsd-vault/`, with `vsd-vault/eval/architect_key_attestation.json` anchoring the architect Ed25519 signing chain to the bridge wallet).

### 3.1 The Poseidon vector corpus as an architect-signed VSD-vault manifest

The POSEIDON-BN254-AS test-vector corpus is a **Verified-Synthesis-Discipline-shaped artifact by construction**: it is a synthesized artifact (generated from circomlibjs) whose *verification is built into its generation* (the differential cross-check against ≥1 independent reference is part of producing it, not a separate downstream step). That is the VSD shape — synthesis with verification fused at the generation boundary.

The forward-vector phase: promote the vector corpus into an **architect-signed VSD-vault manifest**, parallel to how VBDIP-0001 itself was frozen with an architect Ed25519 signature in `vsd-vault/manifests/proposals-VBDIP-0001/001.manifest.json`. A `vsd-vault/manifests/poseidon-vectors/` manifest would carry: the corpus content hash, the circomlibjs version it was generated against, the BN254 prime literal, the R_F/R_P round parameters per arity, and the architect Ed25519 signature over the manifest's canonical hash. This makes the corpus's provenance independently verifiable — anyone with the architect public key + the canonical-JSON algorithm + SHA-256 can confirm the corpus is the one the architect synthesized and signed.

**Operator-gated:** producing an architect Ed25519 signature requires the architect private key (`vsd-vault/architect_key.pem`, gitignored — NEVER committed). The agent can prepare the manifest *shape* but cannot sign it. The signing step is operator-runtime.

### 3.2 A Poseidon-Merkle of VSD-vault manifests — in-circuit-provable

The VSD-vault currently has exactly one signed manifest (`proposals-VBDIP-0001/001.manifest.json`). As the vault grows (the Poseidon-vectors manifest above; future VSDIP/VEDIP/VBDIP manifests), the natural integrity structure is a Merkle tree over manifest hashes. Today that Merkle would be SHA-256 or keccak — and therefore **not in-circuit-provable**: you could not efficiently prove "manifest M is in the VSD-vault Merkle with root R" inside a Groth16 circuit.

A **Poseidon-Merkle** of VSD-vault manifests changes that. Built with POSEIDON-BN254-AS as the node-combining hash, the vault root becomes a BN254 field element, and membership proofs become in-circuit-provable. This is the same structural win as SYNERGY 1 applied one layer up: from "an individual artifact commitment is field-native" to "the methodology vault's integrity root is field-native." It connects directly to ZKBA-ZK §2.3 — a Poseidon-Merkle over ZKBA-ZK commitments and a Poseidon-Merkle over VSD-vault manifests are the same construction at two scales.

This is a later phase than §3.1 (it needs ≥2 vault manifests to be meaningful, and it depends on §3.1's manifest discipline existing first).

### 3.3 Files this synergy grounds against (verified present)

- `vsd-vault/` — `README.md`, `eval/architect_key_attestation.json`, `manifests/proposals-VBDIP-0001/001.manifest.json`, `proposals/`. Confirmed present.
- `wiki/methodology/VBDIP-0001-vad-framework-introduction.md` — VAD framework; VSD/VED/VBD sub-disciplines. Confirmed present.
- `wiki/methodology/vsd_methodology_v1_FINAL.md`, `vsd_volume_2_final.md` — VSD methodology corpus. Confirmed present.

---

## 4. SYNERGY 3 — VED / VBDIP-0001 catalog entry: the differential-self-check-at-generation-boundary pattern

Phase O4-W3B-POSEIDON-AS's defining engineering discipline is its **differential-self-check at the generation boundary**: it runs two independent implementations (circomlibjs + ideally a second reference) and cross-checks *every artifact at synthesis time, before any downstream code that consumes the artifact exists* — the plan's Stream V (V.1 vector match, V.2 per-round differential, V.3 cross-reference) enforces this, and the plan's safety rule #8 explicitly mandates "≥2 independent references AND per-round state verification AND boundary inputs," not just final-output matching.

This is a **catalogable Verified Engineering Discipline (VED) pattern**. VED is the second VAD sub-discipline, retrospectively named in `VEDIP-0001-engineering-discipline-retrospective.md` (which catalogs VED across Phase O0, Phase O1-FRR-PARALLEL, Stream J, and other engineering surfaces). The differential-self-check pattern is distinct from anything VEDIP-0001 currently catalogs — it is specifically about *generating an artifact whose correctness is cross-validated against independent oracles before the artifact is trusted by anything*. POSEIDON-BN254-AS is its **first cryptographic-primitive instance**: a hand-written crypto implementation that is not trusted until it agrees, per-round and at boundary inputs, with independent references.

The forward-vector recommendation: add this pattern to the VEDIP-0001 discipline catalog as a named VED pattern (e.g. "differential-synthesis-verification" or similar — the name is a VEDIP-0001 authoring decision, not pinned here), with POSEIDON-BN254-AS cited as the first cryptographic instance and a forward note that the pattern generalizes to any future hand-written primitive (the prerequisite plan's risk register already anticipates this — single-reference Poseidon implementations historically ship S-box / MDS / round-constant bugs, which is exactly why the differential discipline exists).

**Discipline note:** amending `VEDIP-0001-engineering-discipline-retrospective.md` is a methodology-doc edit. VEDIP-0001 is a retrospective spec; whether a catalog addition needs the architect signing chain or is docs-only is a VEDIP-0001 governance decision the operator makes. This roadmap flags it as methodology-layer authoring work, not a code change, and does not draft the catalog entry.

### 4.1 Files this synergy grounds against (verified present)

- `wiki/methodology/VEDIP-0001-engineering-discipline-retrospective.md` — VED retrospective spec; the discipline catalog. Confirmed present.
- `wiki/methodology/VBDIP-0001-vad-framework-introduction.md` — defines VED as a VAD sub-discipline. Confirmed present.
- `wiki/phases/phase_o4_w3b_poseidon_as.md` — Stream V + safety rule #8 + risk register #3/#5 are the differential-discipline source. Confirmed present.

---

## 5. SYNERGY 4 — Poseidon Reproducibility Card VPM

A new **Verified Projection Media (VPM)** compiler target: the POSEIDON-BN254-AS vector corpus rendered as a VPM artifact, subject to the 3-layer Anti-Hype Visual Grammar.

### 5.1 What it is

VPM is the methodology layer's delivered-media surface — `scripts/vsd_ui_compiler.py:compile_vpm_artifact()` is the FROZEN compiler entry point (confirmed present), `scripts/vpm_audit.py` is the audit harness (confirmed present), and the 3-layer Anti-Hype Visual Grammar enforces a FROZEN 6-state DOM signature (live / dry-run / emulated / frozen-disabled / revoked / unverified) at compile-time (Python compiler), bridge-time (Python audit), and browser-time (JavaScript grammar verifier). This was shipped in Phase O4-VPM-INTEGRATION (per the `CLAUDE.md` NOTE).

A **Poseidon Reproducibility Card** VPM would render the vector corpus as a deterministic HTML artifact: the corpus content hash, the circomlibjs version, the per-arity round parameters, the differential-verification result, and — critically — the **single-reference-verified caveat**. If Phase O4-W3B-POSEIDON-AS lands on its **AMBER preflight path** (only circomlibjs available, no second independent reference — the plan's P.0 decision branch documents this outcome explicitly), the corpus carries reduced cryptographic-correctness assurance. The Anti-Hype Visual Grammar would *force that caveat to render*: the card could not honestly display a "fully verified" state — it would render the "unverified" or a single-reference-qualified state in its FROZEN 6-state DOM signature. This is exactly the structural-honesty defense the VPM grammar was built for (the "DePIN-photoshop-attack" defense per Phase O4 plan §5.5) — a Poseidon corpus that was only single-reference-verified cannot be visually projected as if it were double-verified.

### 5.2 VBDIP-0002A §10 registry ladder placement

The VPM Projection Registry lives in VBDIP-0002A §10 (`vsd-vault/proposals/drafts/VBDIP-0002A-verified-projection-media.DRAFT.md` — VBDIP-0002A is PARTIALLY ABSORBED into VBDIP-0002 v1.1 Appendix B, but §10 is one of the three sections **retained as sidecar**, so §10 is the authoritative registry location). The §10 lifecycle ladder is: **Reserved → Draft Manifest → Compiler Target → Test Fixture → Active**. The §10 registry table currently lists 10 IDs (PROOF-TRAILER-v1, PROOF-WALLET-v1, QR-ELIGIBILITY-v1, HARDWARE-LINEAGE-v1, CONSENT-CAPSULE-v1, DISPUTE-PACKET-v1, MARKET-LISTING-v1, DEV-SANDBOX-v1, HONESTY-BOARD-v1, AGENT-REVIEW-v1) — note the `CLAUDE.md` Phase O4 NOTE records that 8 of those 10 have since advanced to active lifecycle stages, while the §10 *table in the sidecar file* still shows the original Reserved baseline.

A Poseidon Reproducibility Card would take an **11th registry-ladder ID** (e.g. `POSEIDON-REPRO-CARD-v1` — the exact ID is a VBDIP-0002A authoring decision), entering at **Reserved** and promotable to **Draft Manifest** once a wrapper manifest shape exists. Adding a new §10 registry ID is a methodology-doc edit to the VBDIP-0002A sidecar.

**Operator-gated / discipline note:** assigning a new §10 registry ID edits the VBDIP-0002A sidecar (governed methodology doc). This roadmap flags it as methodology-layer authoring work; it does not assign the ID, does not edit the sidecar, does not write the wrapper manifest. The compiler-target work itself (a new `compile_vpm_artifact()` target for the card) would be agent-actionable wallet-free work, but only *after* the registry ID is assigned and the wrapper manifest shape is drafted — i.e. after the ID reaches at least Draft Manifest on the §10 ladder.

### 5.3 Files this synergy grounds against (verified present)

- `scripts/vsd_ui_compiler.py` — `compile_vpm_artifact()` FROZEN compiler entry point. Confirmed present.
- `scripts/vpm_audit.py` — VPM audit harness. Confirmed present.
- `scripts/vsd_vpm_wrapper.py` — VPM wrapper layer (`vapi-vpm-manifest-v1`). Confirmed present.
- `vsd-vault/proposals/drafts/VBDIP-0002A-verified-projection-media.DRAFT.md` — §10 VPM Projection Registry + lifecycle ladder + 10-ID registry table. Confirmed present.

---

## 6. Dependency graph / sequencing table

Everything below is gated on **Phase O4-W3B-POSEIDON-AS landing first** (the root dependency — capability + test-vector corpus + INV-POSEIDON-AS-001/002/003 + PV-CI gate at 86).

```
   Phase O4-W3B-POSEIDON-AS  [PREREQUISITE — must land on main first]
   (poseidon_bn254.ts + vector corpus + INV-POSEIDON-AS-001/002/003 + PV-CI 86)
            |
            +-----------------------------+-----------------------------+-----------------------------+
            |                             |                             |                             |
   SYNERGY 1 (LEAD)              SYNERGY 2                     SYNERGY 3                     SYNERGY 4
   ZKBA-ZK variant              VSD interconnection           VED catalog entry             Poseidon Repro Card VPM
            |                             |                             |                             |
   Z.1 VBDIP-0002 v1.x          3.1 Poseidon-vectors          VEDIP-0001 catalog            5.2 VBDIP-0002A §10
       amendment [OP-GATED]         VSD-vault manifest            addition                      registry ID [OP-GATED
            |                        [OP-GATED — architect      [methodology-doc edit;          methodology-doc edit]
   Z.2 zkba_manifest_validator      Ed25519 signature]            governance per VEDIP-0001]          |
       Poseidon branch                  |                              (independent;          5.x compile_vpm_artifact()
       [agent-actionable]          3.2 Poseidon-Merkle of            can begin once             Poseidon Repro Card target
            |                          VSD-vault manifests           prerequisite lands)        [agent-actionable; gated on
   Z.3 Poseidon ZKBA                   [needs >=2 vault                                          registry ID reaching
       commitment function             manifests; depends                                       Draft Manifest]
       [agent-actionable]              on 3.1 first]
            |
   Z.4 PV-CI invariant for
       Poseidon ZKBA path
       [OP-GATED governance ceremony]
            |
   Z.5 First ZKBA-ZK artifact target
       [agent-actionable]
            |
   Z.6 docs sync [docs-only]
```

| Phase | Synergy | Depends on | Gate type | Wallet |
|---|---|---|---|---|
| **(prereq)** Phase O4-W3B-POSEIDON-AS | — | — | operator-approved plan | 0 IOTX |
| Z.1 VBDIP-0002 v1.x amendment | 1 (LEAD) | prerequisite | **OPERATOR-GATED governance ceremony** | 0 IOTX |
| Z.2 `zkba_manifest_validator.py` Poseidon branch | 1 (LEAD) | Z.1 | agent-actionable | 0 IOTX |
| Z.3 Poseidon ZKBA commitment function | 1 (LEAD) | Z.1, prerequisite vector corpus | agent-actionable | 0 IOTX |
| Z.4 PV-CI invariant for Poseidon ZKBA path | 1 (LEAD) | Z.3 | **OPERATOR-GATED governance ceremony** (`--confirm-governance`) | 0 IOTX |
| Z.5 First ZKBA-ZK artifact target | 1 (LEAD) | Z.3 | agent-actionable | 0 IOTX |
| Z.6 docs sync | 1 (LEAD) | Z.5 | docs-only | 0 IOTX |
| 3.1 Poseidon-vectors VSD-vault manifest | 2 | prerequisite | **OPERATOR-GATED** (architect Ed25519 signature) | 0 IOTX |
| 3.2 Poseidon-Merkle of VSD-vault manifests | 2 | 3.1, ≥2 vault manifests | agent-actionable (prep) + design decision | 0 IOTX |
| VEDIP-0001 catalog addition | 3 | prerequisite | methodology-doc edit; VEDIP-0001 governance decision | 0 IOTX |
| 5.2 VBDIP-0002A §10 registry ID | 4 | prerequisite | **OPERATOR-GATED** methodology-doc edit (VBDIP-0002A sidecar) | 0 IOTX |
| 5.x Poseidon Repro Card compile target | 4 | 5.2 reaching Draft Manifest | agent-actionable | 0 IOTX |

Synergies 1–4 are **independent of each other** — they share only the common prerequisite. Within SYNERGY 1 the Z.* sequence is strictly ordered. Within SYNERGY 2, 3.2 depends on 3.1. SYNERGIES 3 and 4 are each single-track and can begin as soon as the prerequisite lands. The LEAD phase (SYNERGY 1) should be sequenced first for highest leverage; SYNERGIES 2/3/4 can be interleaved or deferred at operator discretion.

---

## 7. What this roadmap does NOT do

- **Does NOT execute anything.** It is a planning artifact. No code, no test files, no contract changes, no compiler targets, no manifests. The only file it creates is itself (`wiki/methodology/poseidon_methodology_composition_roadmap.md`).
- **Does NOT draft the VBDIP-0002 v1.x amendment.** The `commitment_hash_algo` schema amendment (SYNERGY 1, Z.1) is an OPERATOR-GATED governance ceremony touching a FROZEN methodology proposal. This roadmap names the field and the additive-amendment shape; it does not write the amendment text and does not modify `VBDIP-0002-zkba-visual-projections.md`.
- **Does NOT modify any FROZEN region.** `compute_zkba_commitment()` v1 (`bridge/vapi_bridge/zkba_artifact.py`) stays byte-stable forever. The `vapi-zkba-manifest-v1` schema at v1.0 is untouched (the amendment is additive). The 228-byte PoAC wire format, the FROZEN ZK circuits, and every other FROZEN-v1 primitive are out of scope.
- **Does NOT touch the PATTERN-017 commitment-family count.** It stays 10. POSEIDON-BN254-AS is a *capability*. The ZKBA-ZK variant is a *variant of existing family member #10*. Neither is an 11th family. This framing is inherited verbatim from the prerequisite plan.
- **Does NOT sign anything.** The architect-signed VSD-vault manifest (SYNERGY 2, 3.1) and any PV-CI governance ceremony (Z.4) require the architect private key / the `--confirm-governance` operator phrase. The agent cannot perform these. They are flagged operator-runtime.
- **Does NOT touch the wallet, chain, or mainnet.** Every phase is wallet-free, 0 IOTX, `CHAIN_SUBMISSION_PAUSED=true` posture preserved. No chain operations. No mainnet anything. Mainnet deploys remain explicitly blocked until the Operator Initiative is complete per the operator directive.
- **Does NOT begin before the prerequisite lands.** Every phase is gated on Phase O4-W3B-POSEIDON-AS being on `main` with the capability + test-vector corpus + 3 PV-CI invariants present. Until then this roadmap is inert.

---

## 8. Cross-reference

**Prerequisite plan:** `wiki/phases/phase_o4_w3b_poseidon_as.md` — Phase O4-W3B-POSEIDON-AS (DRAFT status as of 2026-05-14; awaiting operator approval via ExitPlanMode). This roadmap sequences work that begins only AFTER that plan lands. Every phase here inherits that plan's framing: POSEIDON-BN254-AS is a protocol-internal cryptographic capability, distinct in shape from the 10 domain-tagged SHA-256 PATTERN-017 commitment families; the family count stays 10.

**Repo facts that could NOT be verified at this worktree HEAD (flagged for check before this doc is cherry-picked to main):**
- The prerequisite plan brief stated `scripts/w3bstream/poseidon_test_vectors.json` is "already committed at HEAD" — it is **NOT present** at this worktree's HEAD (`worktree-agent-ac738f56280272f5a`, HEAD `94a4dde3`). `scripts/w3bstream/` contains only `process_gsr_packet.ts`, `validate_poac_record.ts`, `validate_zk_sepproof.ts`. This is consistent with `phase_o4_w3b_poseidon_as.md` being DRAFT (its Stream P.2 is what *produces* the vector file) — but the brief's claim that the corpus is committed could not be confirmed. The roadmap treats the corpus as a prerequisite-plan deliverable, not an existing artifact.
- INV-POSEIDON-AS-001/002/003 are **not yet in** `scripts/vapi_invariant_gate.py` — consistent with the prerequisite plan being unexecuted; the roadmap treats them as prerequisite deliverables.
- The "3,225-vector test corpus" figure from the brief could not be verified (file absent).
- All VBDIP section numbers, the VBDIP-0002A §10 registry ladder, the `vsd-vault/` structure, `zkba_artifact.py`, `zkba_manifest_validator.py`, `vsd_ui_compiler.py`, `vpm_audit.py`, and `vsd_vpm_wrapper.py` WERE verified present and are cited accurately.

---

*— VAPI Principal Architect, 2026-05-14. Planning artifact only.*
