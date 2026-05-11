# VBDIP-0001 — VAPI Architectural Discipline (VAD) Framework Introduction

**Proposal type:** VBDIP (Verified Bridge Discipline Improvement Proposal)
**Proposal number:** 0001
**Status:** Draft v1.0 (FROZEN-candidate)
**Author:** VAPI Architect (single deployer, bridge wallet `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692`)
**Date:** 2026-05-10
**Scope:** VAPI-internal. Architectural pivot document. Not a generic methodology proposal.
**Supersedes:** No prior document; VBDIP-0001 establishes the VBDIP lineage as the third proposal stream alongside the existing VSDIP lineage (VSDIP-0001 = v1.0 FINAL, VSDIP-0002 = Volume 2 FINAL) and the newly-named VEDIP lineage (VEDIP retroactively documents Phase O0 through Phase O1-FRR-PARALLEL).
**Save path:** `vsd-vault/proposals/VBDIP-0001-vad-framework-introduction.md`
**Migration discipline:** Deferred; vault directory remains `vsd-vault/` pending Phase O1-VAD-MIGRATE per §6 of this proposal.

---

## 0. NotebookLM Reading Note

This document is the canonical architectural pivot reference for the VAPI Architectural Discipline (VAD) framework. When ingested into the VAPI/VSD master corpus on NotebookLM after Phase O1-VSD-BOOTSTRAP completes, this document grounds answers about the relationship between VAD, VSD, VED, and VBD; about the rationale for the methodology rename; about the deferred directory migration; and about the new VBD invariants. The reading partition established in v1.0 §0 and v2.0 §16 carries forward with one addition: questions about cross-discipline composition (CDRR, cross-fleet skill-separation, unified harness `--proposal-type` semantics) ground in this document.

---

## 1. TL;DR

The Verified Synthesis Discipline has empirically expanded beyond its original synthesis-domain scope. Volume 2 of VSD absorbed MCP as the primary index, shipped the VRR and CDRR cryptographic primitives, activated the Synthesis Operator Fleet, and extended the unified `vapi_invariant_gate.py` harness with a `--proposal-type` flag spanning protocol and synthesis domains. The methodology now governs both knowledge work and protocol engineering through structurally identical patterns. The name "Verified Synthesis Discipline" no longer honestly describes the scope.

VBDIP-0001 introduces the VAPI Architectural Discipline (VAD) as the top-level framework name, with three sub-disciplines: VSD as the synthesis-domain sub-discipline (unchanged at v2.0 freeze), VED as the engineering-domain sub-discipline (retroactively documenting Phase O0 through Phase O1-FRR-PARALLEL work), and VBD as the bridge-domain sub-discipline governing composition between the two. The methodology surface remains one, not two; the audit trail remains continuous; the numbered-proposal discipline remains the only path for evolution. What changes is the framing and the scope statement, not the underlying invariants or primitives.

VBDIP-0001 adds three architectural commitments as VBD-INV-1 through VBD-INV-3: continuous deployer-verified provenance under fleet expansion, fleet-domain replication discipline, and primitive composition discipline. The unified harness `--proposal-type` flag extends from three choices (`protocol`, `synthesis`, `both`) to four (`protocol`, `synthesis`, `bridge`, `all`). The vault directory `vsd-vault/` remains at its current name pending Phase O1-VAD-MIGRATE, which is named and scoped in §6 below.

The methodology rename produces zero operational change in protocol behavior at VBDIP-0001 freeze. No new CI pipelines, no Cedar bundle re-anchoring, no wallet impact beyond the gas-free architect Ed25519 signature over this proposal. The rename names what the methodology has become; it does not change what the methodology does.

---

## 2. Motivation

Three observations across the methodology's evolution from v0.1 draft through Volume 2 FINAL establish the empirical need for the VAD framework.

The first observation is that the methodology has been governing protocol engineering work since well before it had a name for doing so. The eighteen Phase O0 commits across five streams executed under disciplines that were not explicitly methodology-named but were operationally rigorous: V-check pre-execution discipline, P-check inter-stream discipline, atomic commit boundaries, Decision blocks for explicit operator resolution, hold-for-approval gates between meaningful checkpoints. These disciplines are not VSD disciplines — they predate VSD and they govern engineering work rather than synthesis work — but they are recognizably the same methodology applied to a different artifact. The Phase O1-FRR-PARALLEL ship and the Stream J empirical findings extend this pattern. The pattern has been operating without a name. VED names it.

The second observation is that the composition between protocol-side and synthesis-side work has become structurally load-bearing in ways that neither side's existing discipline directly addresses. The cross-fleet skill-separation invariant (CFSS, INV-CFSS-001) governs the composition. The unified `vapi_invariant_gate.py` harness with `--proposal-type` flag governs the composition. The CDRR primitive composing FRR and VRR into a single ecosystem-readiness scalar governs the composition. These composition mechanisms have been authored across Volume 2 but have not had a methodology home — they are not synthesis-discipline mechanisms (they do not govern note creation) and they are not engineering-discipline mechanisms (they do not govern protocol shipping). They are bridge mechanisms. VBD names them.

The third observation is that the methodology's novelty claims have been growing in conjunction-axis count from v1.0 (five axes) to v2.0 (nine axes), and the trajectory suggests the conjunction will continue to expand as the protocol matures. Without a top-level framework name, each expansion is forced to occur under the VSD label, which has produced increasing strain on the label — VSD originally meant "the discipline applied to synthesis notes" but has come to mean "the methodology governing the protocol." The honesty-first commitment requires that the name match the scope. VAD names the top-level scope; VSD reverts to its original meaning as the synthesis-discipline sub-component.

The CVAS document produced in the prior conversational turn (origin: Gemini extrapolation in response to a theoretical perpetual-development-loop prompt) exemplifies the failure mode that motivates VBDIP-0001. The document correctly identified that the methodology now spans the full development loop, but it conflated the protocol fleet (Curator, Guardian, Sentry) with the synthesis fleet (Synthesizer, HarnessSentinel, EigenspaceWarden), conflated the deprecated `vsd_eval_harness.py` with the unified `vapi_invariant_gate.py`, conflated the FRR primitive with the deferred third Groth16 verifier, and conflated O1_SHADOW capability with O3_ACT capability. Each conflation is the specific kind of drift that VBD invariants are designed to programmatically reject. VBDIP-0001's adoption of VBD-INV-1 through VBD-INV-3 hardens the methodology against this class of LLM-generated extrapolation drift.

---

## 3. The VAD Framework — Three Sub-Disciplines

The VAPI Architectural Discipline is the top-level framework name. It is not a separate methodology from VSD, VED, or VBD; it is the name for their conjoined operation. VAD has no invariants of its own; every invariant belongs to exactly one sub-discipline. VAD has no harness of its own; the unified `vapi_invariant_gate.py` serves all three sub-disciplines through the `--proposal-type` flag. VAD has no proposal lineage of its own; numbered proposals are authored as VSDIPs, VEDIPs, or VBDIPs.

### 3.1 VSD — Verified Synthesis Discipline (Synthesis Sub-Discipline)

VSD is the sub-discipline governing knowledge work and synthesis production. Scope: research synthesis, claim notes, ingredient notes, synthesis notes, PBSA notes, decision notes, adversarial notes, eigenspace notes, study notes, industry notes, verification notes, MCP notes, CDRR notes. The synthesis fleet (Synthesizer, HarnessSentinel, EigenspaceWarden) operates within VSD's scope.

Canonical documents: VSDIP-0001 (v1.0 FINAL, the seven-step bootstrap and sixteen invariants), VSDIP-0002 (Volume 2 FINAL, the eight-stream bootstrap and seven additional invariants). Both remain canonical without amendment under the VBDIP-0001 "no in-place amendments" discipline.

Invariant prefix: `VSD-INV-N`. Current count: 23 (VSD-INV-1 through VSD-INV-23 across VSDIP-0001 and VSDIP-0002, with VSDIP-0003 amendments to VSD-INV-21 and VSD-INV-22 pending freeze at Phase O1-VSD-BOOTSTRAP Stream A.5).

Note types: twelve, as authored under v1.0 and v2.0. No additional VSD note types introduced under VBDIP-0001.

Harness mode: `--proposal-type=synthesis`. Reads `vsd-vault/eval/INVARIANTS.md`, `vsd-vault/notes/**/*.md`, `vsd-vault/eval/NOTE_SCHEMAS.md`. Unchanged by VBDIP-0001.

### 3.2 VED — Verified Engineering Discipline (Engineering Sub-Discipline)

VED is the sub-discipline governing protocol-side engineering work. Scope: smart contract deployment, bridge service operations, Cedar bundle authoring and anchoring, PV-CI invariant enforcement, on-chain state changes, FROZEN-v1 primitive shipping (excluding VRR and CDRR which belong to VBD), tournament integrity work, controller calibration, biometric corpus management. The protocol fleet (Sentry, Guardian, Curator) operates within VED's scope.

Canonical documents: VEDIP-0001 (this proposal retroactively names the existing eighteen Phase O0 commits and the Phase O1-FRR-PARALLEL ship as VEDIP-0001 work; the actual document authoring is a follow-up deliverable to VBDIP-0001, not part of VBDIP-0001 itself). VEDIP retrospective documentation is named below in §5.

Invariant prefix: `VED-INV-N`. Current count: 55 (the existing PV-CI protocol invariants, retroactively prefixed). The retroactive prefixing is a documentation rename only; the underlying invariant hashes, the `.github/INVARIANTS_ALLOWLIST.json` structure, and the harness behavior do not change. The `protocol:` section of the allowlist file maps one-to-one onto VED-INV-N IDs in the documentation; the file format does not change.

Note types: VED does not introduce new markdown note types because VED's primary artifacts are git commits, source code, and tests. The Phase-Boundary State Assessment pattern from VSD §4.4 is applicable to VED-governed phase boundaries and can be authored as VSD `pbsa/` notes that reference VED phase work, but PBSA notes remain VSD-typed artifacts. This is correct under the cross-fleet skill-separation discipline — synthesis notes about engineering work are authored by VSD-governed processes; the engineering work itself is governed by VED.

Harness mode: `--proposal-type=protocol`. Reads existing protocol-side invariant configuration. Unchanged by VBDIP-0001.

### 3.3 VBD — Verified Bridge Discipline (Composition Sub-Discipline)

VBD is the sub-discipline governing the composition between VSD and VED. Scope: cross-fleet skill-separation (CFSS, INV-CFSS-001), the unified `vapi_invariant_gate.py` harness with `--proposal-type` flag, the CDRR cryptographic primitive composing FRR and VRR, the fleet-domain replication discipline as a claimable architectural property, the primitive composition discipline as a claimable architectural property, and continuous deployer-verified provenance under fleet expansion.

Canonical documents: VBDIP-0001 (this proposal). VBDIP-0002 reserved for the migration shipping Phase O1-VAD-MIGRATE per §6. VBDIP-0003 reserved for any post-bootstrap discovery requiring VBD invariant adjustment.

Invariant prefix: `VBD-INV-N`. Current count: 3 (VBD-INV-1 through VBD-INV-3, introduced by this proposal in §4 below). The cross-fleet skill-separation invariant INV-CFSS-001 from Volume 2 §20.1 is retroactively prefixed as VBD-INV-4 (renaming only; no semantic change), with the existing test gate continuing to enforce it. The harness extension and CDRR primitive ship under VBDIP-0001 freeze.

Note types: VBD-typed artifacts (composition findings between sub-disciplines) may be authored as a new `notes/bridge/` type in a future VBDIP, but VBDIP-0001 does not introduce new note types. Composition findings at v1.0 of VBD continue to be authored as VSD synthesis notes that reference both VSD and VED disciplines, with the `relationship_to_predecessor` field set to `componentOf` per existing C2PA discipline.

Harness mode: `--proposal-type=bridge`. Reads VBD invariant configuration. This is a new harness mode introduced by VBDIP-0001.

### 3.4 Top-Level Composition

The unified `vapi_invariant_gate.py` harness extends from three `--proposal-type` choices (`protocol`, `synthesis`, `both`) to four (`protocol`, `synthesis`, `bridge`, `all`). The `protocol` mode runs VED invariants. The `synthesis` mode runs VSD invariants. The `bridge` mode runs VBD invariants. The `all` mode runs all three sub-discipline invariant sets in sequence. The legacy `both` choice from Volume 2 §22 is preserved as an alias for `all` for backward compatibility, with a deprecation note that future harness invocations should use `all` directly.

The `.github/INVARIANTS_ALLOWLIST.json` file extends from two sections (`protocol`, `vsd`) to three (`protocol` retained as the VED section under its existing name for backward compatibility, `vsd` retained as the VSD section, `vbd` added as the new VBD section). The deployer signature continues to cover all sections plus version plus frozen_at. The file format version bumps from v2 to v3 to reflect the schema extension; existing v2 readers continue to function because the additional `vbd` section is non-mandatory under the existing parser logic (parser ignores unknown top-level keys per Volume 2 §V4 verification).

---

## 4. The Three New VBD Invariants

VBDIP-0001 introduces three invariants under the VBD prefix. Each is stated in markdown as the normative form, with the aspirational Python check signature provided for future implementation under VBDIP-0002 work (mirroring the VSD pattern where markdown is normative and Python is aspirational at proposal freeze).

### 4.1 VBD-INV-1 — Continuous Deployer-Verified Provenance Under Fleet Expansion

The bridge wallet `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692` is the load-bearing identity anchor for all VAPI work across all sub-disciplines. Any expansion of fleet membership (adding a new protocol-fleet agent under VED, adding a new synthesis-fleet agent under VSD, adding a new sub-discipline under VBD) must preserve the bridge wallet's continuity as the sole deployer identity. Fragmenting protocol identity across multiple credentials, or introducing a parallel identity anchor for any sub-discipline, fails this invariant.

Programmatic check signature for VBDIP-0002 implementation:

```python
def check_vbd_inv_1(repo_root: Path) -> CheckResult:
    """VBD-INV-1: continuous deployer-verified provenance under fleet expansion.

    Walk all signed artifacts across all sub-disciplines:
    - vsd-vault/manifests/**/*.manifest.json
    - .github/INVARIANTS_ALLOWLIST.json (deployer_signature field)
    - bridge/vapi_bridge/cedar_bundles/*.json (anchor signature)
    - vsd-vault/proposals/*.md (architect signature blocks)

    For every signature, verify the signing key chain resolves to the
    bridge wallet 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692, either
    directly (secp256k1 signatures by the wallet) or through the
    architect Ed25519 key chain (Ed25519 key signed once by the wallet
    at bootstrap establishing the deployer-anchored synthesis key).

    Any signature that does not chain to the bridge wallet fails.
    """
    ...
```

Rationale: this invariant is the architectural commitment that VAPI's protocol identity must not fragment as the methodology expands across sub-disciplines. It is the VBD analog of VSD-INV-3 (deployer identity does not fragment in notes) raised to the framework level — VSD-INV-3 governs note frontmatter; VBD-INV-1 governs the entire identity surface across all sub-disciplines. Without this invariant, future operators could be tempted to introduce a separate signing key for VED work or for VBD work, fragmenting the audit trail. With this invariant, any such fragmentation is structurally rejected.

### 4.2 VBD-INV-2 — Fleet-Domain Replication Discipline

Adding a new operator domain (a new sub-discipline with its own fleet, e.g., if a future VAPI evolution introduces a third operator fleet for some new architectural purpose) must follow the structural pattern established by the synthesis fleet's relationship to the protocol fleet. Specifically: the new fleet must have its own Cedar bundle architecture, its own dual-anchor pattern, its own FSCA drift rules, its own parallel-fleet advancement primitive, and its own disjoint skill space enforced by an extended cross-fleet skill-separation invariant. The new fleet must not introduce parallel architecture; it must absorb the existing architecture.

Programmatic check signature for VBDIP-0002 implementation:

```python
def check_vbd_inv_2(repo_root: Path) -> CheckResult:
    """VBD-INV-2: fleet-domain replication discipline.

    Enumerate all operator fleets registered in the protocol:
    - bridge/vapi_bridge/operator_initiative_advancement.py INITIATIVE_AGENTS
    - bridge/vapi_bridge/operator_initiative_advancement.py SOF_AGENTS
    - any additional *_AGENTS tuples added in future evolution

    For each fleet, verify presence of required architectural components:
    - Cedar bundle authoring under bridge/vapi_bridge/cedar_bundles/
    - Dual-anchor script under scripts/parallel_*_anchor.py
    - FSCA drift rules referencing the fleet's agents
    - Advancement primitive evaluating the fleet
    - Cross-fleet skill-separation forbids covering all other-fleet skills

    Any fleet missing required components, or any fleet introducing
    parallel architecture rather than absorbing existing patterns, fails.
    """
    ...
```

Rationale: this invariant encodes the architectural insight Volume 2 §25 names but does not enforce — that fleet expansion follows the structural pattern established by the synthesis fleet absorbing the protocol-fleet pattern. The novelty claim "fleet-domain replication discipline" becomes harness-checkable through this invariant. Without it, future operators could introduce a third operator fleet through a different architectural pattern, breaking the validation-transfer and cognitive-leverage benefits Volume 2 §25 names. With it, any such divergence is structurally rejected.

### 4.3 VBD-INV-3 — Primitive Composition Discipline

Every FROZEN-v1 cryptographic primitive in the PATTERN-017 family must declare its composition path with other primitives, or must explicitly state that no composition is meaningful for the primitive. Composition declarations specify which primitives this primitive composes with, through what mechanism (typically a higher-order SHA-256 commitment), and what the composed commitment represents. The current PATTERN-017 family demonstrates the discipline: FRR composes with VRR through CDRR; CDRR has no upward composition declared because it is currently the top-level ecosystem-readiness commitment; PoAC, GIC, WEC, VAME, CORPUS-SNAPSHOT, CONSENT, BIOMETRIC-SNAPSHOT, and LISTING-v1 each have or do not have composition declarations explicitly stated.

Programmatic check signature for VBDIP-0002 implementation:

```python
def check_vbd_inv_3(repo_root: Path) -> CheckResult:
    """VBD-INV-3: primitive composition discipline.

    Enumerate all FROZEN-v1 primitives in PATTERN-017:
    - Parse bridge/vapi_bridge/operator_initiative_advancement.py for
      *_DOMAIN_TAG constants
    - Parse bridge/vapi_bridge/vsd_advancement.py for VSD-side
      *_DOMAIN_TAG constants
    - Parse bridge/vapi_bridge/*.py for any other domain tag definitions

    For each primitive, verify the existence of a composition declaration
    in PATTERN-017 documentation (currently wiki/methodology/pattern-017.md
    or its successor location). Declaration must specify:
    - Which other primitives this primitive composes with (or none)
    - The composition mechanism (typically a higher-order SHA-256)
    - What the composed commitment represents semantically

    Any primitive without a composition declaration fails, EXCEPT
    primitives explicitly marked as composition-terminal (currently CDRR).
    """
    ...
```

Rationale: this invariant encodes the architectural commitment that the cryptographic primitive family is structurally compositional rather than a flat list of unrelated primitives. The CDRR primitive in Volume 2 §19.2 demonstrates that primitives can be composed into higher-order ecosystem-level commitments; the invariant requires that this compositional property be declared explicitly for every primitive going forward. Without it, future primitives could be added to PATTERN-017 without declared composition paths, fragmenting the cryptographic surface. With it, the family remains structurally coherent.

### 4.4 VBD-INV-4 — Cross-Fleet Skill-Separation (Retroactive Rename)

The cross-fleet skill-separation invariant authored as INV-CFSS-001 in Volume 2 §20.1 is retroactively renamed to VBD-INV-4 under the VBD prefix discipline. The semantic content is unchanged. The harness check is unchanged. The Cedar bundle `P-FORBID-CFSS-*` policies are unchanged. Only the documentation prefix changes.

This rename is included in VBDIP-0001 because INV-CFSS-001 is structurally a VBD invariant (it governs composition between the two fleets) and should be prefixed accordingly under the new convention. The retroactive rename produces no operational change; it documents that the cross-fleet skill-separation discipline has been a VBD discipline all along.

---

## 5. Retroactive Documentation Under VED and VBD

VBDIP-0001 establishes VED and VBD as named sub-disciplines that have been operating implicitly across the protocol's prior work. The retroactive documentation maps existing artifacts to their sub-discipline home. This mapping is documentation only; no operational change.

### 5.1 VED Retrospective Scope

The following past work is retroactively documented as VED-governed:

The eighteen Phase O0 commits across five streams (Phase O0 closure 2026-05-03, 44 total commits at close, final commit `44c26ce0`) executed under VED discipline — V-checks, P-checks, atomic commits, Decision blocks, hold-for-approval gates. VEDIP-0001 will retroactively document this work.

The Phase O1-FRR-PARALLEL ship (commit `4ddeb43c`) executed under VED discipline, with the FRR primitive shipping as the ninth FROZEN-v1 primitive in PATTERN-017 (under the canonical convention defined in §7 — PoAC is #1, FRR is #9, ZKBA-ARTIFACT is #10 post-Phase-O3-ZKBA-TRACK1 C2). VEDIP-0001 will document the FRR primitive and the ship.

The Stream J commit (`79dacc88`) closing the canonical-name versus Q9-hex schema mismatch and the `next_alignment_target` misresolution executed under VED discipline, with regression test T-O1-FRR-7 locking both fixes. VEDIP-0001 will document the Stream J empirical findings as a verification-gap finding per VSD-INV-19, with the synthesis-side artifact authored as a VSD `adversarial/` note that references VEDIP-0001 as the engineering-side closure.

The parallel O2 SUGGEST anchor (commit `2cde36a3`) executed under VED discipline, advancing the three Operator Initiative agents to O2_SUGGEST on chain. VEDIP-0001 will document the parallel O2 anchor as the most recent VED ship boundary at VBDIP-0001 freeze.

The existing PV-CI invariants (55 at VBDIP-0001 authoring; 63 at the methodology integration resumption per `.github/INVARIANTS_ALLOWLIST.json` count) are retroactively counted as VED-INV-N in documentation, where N is the methodology-doc count abstraction. **VED-INV-N is a documentation-only count abstraction, not a rename of the underlying allowlist IDs.** The allowlist file retains its existing per-invariant naming (e.g., `INV-FRR-001`, `INV-OPERATOR-AGENT-001`, `INV-ZKBA-002`); no code or allowlist-file rename is performed under VED prefix. Future allowlist invariants continue to use their phase-anchored IDs; "VED-INV-N" appears only in methodology cross-references where a count abstraction is useful. The allowlist file structure does not change.

### 5.2 VBD Retrospective Scope

The following past work is retroactively documented as VBD-governed:

The cross-fleet skill-separation discipline authored in Volume 2 §20.1 as INV-CFSS-001 has been a VBD discipline since Volume 2 freeze. VBD-INV-4 retroactively names it under the VBD prefix.

The unified harness extension authored in Volume 2 §22 (the `--proposal-type` flag introduction extending `vapi_invariant_gate.py` to serve both protocol and synthesis invariants from a single binary) has been a VBD mechanism since Volume 2 freeze. VBDIP-0001 §3.4 retroactively names this as VBD-governed and extends it to four choices.

The CDRR primitive authored in Volume 2 §19.2 as the twelfth FROZEN-v1 primitive in PATTERN-017 (under the canonical convention defined in §7 — twelfth because ZKBA-ARTIFACT was inserted between FRR and VRR at #10) has been a VBD primitive since Volume 2 freeze. VBDIP-0001 §4.3 (VBD-INV-3 primitive composition discipline) retroactively documents CDRR's role as the load-bearing example of the composition discipline.

The fleet-domain replication discipline named informally in Volume 2 §25 (the observation that adding a new operator domain is structurally equivalent to adding a new agent within an existing domain) has been a VBD architectural property since Volume 2 freeze. VBD-INV-2 retroactively encodes it as a harness-checkable invariant.

---

## 6. Deferred Migration to `vad-vault/`

The vault directory remains at `vsd-vault/` at VBDIP-0001 freeze. The directory rename to `vad-vault/` is deferred to a separate phase named Phase O1-VAD-MIGRATE, which is scoped in this section but not executed under VBDIP-0001.

### 6.1 Rationale for Deferral

The directory name is operationally load-bearing in three places: the unified harness `scripts/vapi_invariant_gate.py` references `vsd-vault/eval/INVARIANTS.md` and `vsd-vault/notes/**/*.md` in `--proposal-type=synthesis` mode; the NotebookLM export script `vsd_notebooklm_export.py` walks `vsd-vault/notes/` and writes to `vsd-vault/corpus/`; the SOF Cedar bundle lane prefixes (per Volume 2 §20.4) include `vsd-vault/`.

The Cedar bundle binding is the load-bearing constraint. SOF Cedar bundles include `vsd-vault/` as a lane prefix, and bundle Merkle roots are computed over the full bundle content including lane prefixes. Changing the lane prefix changes the Merkle root, which means the on-chain `scopeRoot` commitment for each SOF agent no longer matches the authored bundle. The fix requires re-anchoring all three SOF agents with new bundles using `vad-vault/` lane prefixes, which costs approximately 0.18 IOTX for the six dual-anchor transactions and produces on-chain artifacts (the re-anchored scopeRoots) that future operators would need to understand the provenance of.

Deferring the migration lets VBDIP-0001 execute as a methodology proposal with zero operational cost (architect Ed25519 signature only, no wallet impact, no CI changes, no Cedar bundle re-anchoring). The migration ships separately as Phase O1-VAD-MIGRATE under its own VBDIP (VBDIP-0002 reserved for this purpose).

### 6.2 Honesty-First Documentation of the Intermediate State

The vault directory `vsd-vault/` will house the VAD framework between VBDIP-0001 freeze and Phase O1-VAD-MIGRATE completion. This is operationally inconsistent — the directory name does not match the framework name. The inconsistency is named explicitly here as an intentional, temporary, and deferred state.

The `vsd-vault/README.md` is updated at VBDIP-0001 freeze (atomic with the proposal commit) to include the following section:

> **Framework rename and deferred directory migration.** This directory houses the VAPI Architectural Discipline (VAD) framework as established by VBDIP-0001 on 2026-05-10. The directory retains its original name `vsd-vault/` from the VSD-only era because directory paths are operationally load-bearing in the unified harness configuration, the NotebookLM export script, and the SOF Cedar bundle lane prefixes. The rename to `vad-vault/` is deferred to Phase O1-VAD-MIGRATE per VBDIP-0001 §6, which will ship as its own atomic commit with operator-authorized wallet impact (approximately 0.18 IOTX for Cedar bundle re-anchoring). Until Phase O1-VAD-MIGRATE ships, the directory name does not match the framework name; this inconsistency is intentional, named, and operationally bounded.

### 6.3 Phase O1-VAD-MIGRATE Acceptance Criteria

The future migration ship must satisfy the following acceptance criteria, which are normative for Phase O1-VAD-MIGRATE execution and will be referenced in VBDIP-0002 when that proposal is authored:

The directory `vsd-vault/` is renamed to `vad-vault/` via `git mv`, preserving git history through the rename. The harness configuration in `scripts/vapi_invariant_gate.py` is updated to reference `vad-vault/eval/INVARIANTS.md` and `vad-vault/notes/**/*.md` in `--proposal-type=synthesis` and `--proposal-type=bridge` modes. The NotebookLM export script is updated to walk `vad-vault/notes/` and write to `vad-vault/corpus/`. The SOF Cedar bundles are re-authored with `vad-vault/` lane prefixes; new bundle Merkle roots are computed; the three SOF agents are re-anchored on chain via `parallel_vsd_anchor.py --confirm` (or a Phase O1-VAD-MIGRATE-specific re-anchor script). Wallet impact is approximately 0.18 IOTX for six dual-anchor transactions. The `vsd-vault/README.md` is moved to `vad-vault/README.md` and the deferred-migration section is removed because the migration is complete. The MEMORY.md inside the vault is updated to reflect the new directory name. Pre-execution V-checks include verification that all references to `vsd-vault/` across the repository are exhaustively enumerated and updated. Post-execution P-checks include verification that the harness runs cleanly in all four proposal-type modes and that NotebookLM corpus regeneration succeeds against the new directory.

### 6.4 Backward Compatibility During the Intermediate State

During the intermediate state (VBDIP-0001 freeze through Phase O1-VAD-MIGRATE completion), all references to `vsd-vault/` in code, configuration, documentation, and tooling remain operationally correct. No backward-compatibility shims are introduced. The intermediate state is not a bridge state requiring shims; it is the canonical state until the migration ships.

---

## 7. Operational Impact of VBDIP-0001 Freeze

VBDIP-0001 freeze produces the following operational changes, enumerated exhaustively:

The methodology framework is named VAD. All future documents reference VAD as the top-level framework. Existing documents (v1.0 FINAL, v2.0 FINAL, the bootstrap prompt, the NotebookLM session prompt) remain unchanged at their existing freeze states per the "no in-place amendments" discipline. Future numbered evolutions of these documents will update their internal references to VAD nomenclature at that exact phase boundary.

The unified `vapi_invariant_gate.py` harness extends from three `--proposal-type` choices to four. The `bridge` mode is added; the `all` mode is added as the new name for what was previously `both`; `both` is preserved as a deprecated alias. The harness extension ships as part of VBDIP-0001's atomic commit. Existing CI pipelines that use `--proposal-type=protocol` or `--proposal-type=synthesis` continue to function without change.

The `.github/INVARIANTS_ALLOWLIST.json` file extends from two sections to three. The `vbd` section is added. The file format version bumps from v2 to v3. The deployer signature is regenerated to cover the new file content. The allowlist regeneration ships as part of VBDIP-0001's atomic commit via the existing `--generate --confirm-governance` flow.

Three VBD invariants (VBD-INV-1, VBD-INV-2, VBD-INV-3) are encoded into the harness with markdown-normative bodies and Python `pass` stubs. The VBD-INV-4 retroactive rename of INV-CFSS-001 is documented. Total invariant count across the framework moves from 78 (55 VED + 23 VSD per Volume 2 v2.0 freeze) to 81 (55 VED + 23 VSD + 3 VBD, with the existing CFSS invariant retroactively counted under VBD as VBD-INV-4 bringing the VBD count to 4 and the total to 82).

Note types remain at twelve under VSD. No new note types are introduced under VBD at VBDIP-0001 freeze. Future VBDIPs may introduce a `notes/bridge/` type if composition findings between sub-disciplines warrant their own artifact type; this is deferred.

PATTERN-017 cryptographic primitive family count is canonically tracked as twelve post-bootstrap. Canonical convention: PATTERN-017 includes SHA-256 commitment primitives with explicit or implicit domain separation used as VAPI's chain-anchored proof commitments. The family consists of PoAC (Phase 1, implicit slice [0:164]), GIC (Phase 235-A), WEC (Phase 236-WATCHDOG), VAME (Phase 236-VAME), CORPUS-SNAPSHOT (Phase 236-CORPUS-SNAPSHOT), CONSENT (Phase 237-CONSENT), BIOMETRIC-SNAPSHOT (Phase 237-ZK-SEPPROOF), LISTING-v1 (Phase 238-MARKETPLACE), FRR (Phase O1-FRR-PARALLEL, commit `4ddeb43c`), and ZKBA-ARTIFACT (Phase O3-ZKBA-TRACK1 C2, commit `625007ab`). Ten pre-bootstrap shipped FROZEN-v1 modules; twelve post-bootstrap with VRR + CDRR (Volume 2 §19.1 + §19.2). The family EXCLUDES parser-schema tags (CEDAR-BUNDLE-v1 in `cedar_parser.py`) and Pass 2C operator-track primitives (AGENT-COMMIT-v1, PHYSICAL-DATA-ATTESTATION-v1) which form a distinct primitive lineage. VBDIP-0001 does not introduce new primitives; it documents the composition discipline that governs the existing family. VBDIP-0002 ships ZKBA-ARTIFACT as the tenth member.

Wallet impact at VBDIP-0001 freeze: zero. The architect Ed25519 signature over this proposal is gas-free per V2 verification in the bootstrap prompt. No on-chain transactions execute as part of VBDIP-0001 freeze.

CI pipeline impact at VBDIP-0001 freeze: minimal. The harness extension adds one new `--proposal-type=bridge` mode and one new `--proposal-type=all` alias. Existing CI pipelines continue to function unchanged. New CI work to test the `bridge` mode ships as part of VBDIP-0001's test additions.

Bridge test count delta: approximately +5 tests covering the new VBD invariants and the harness extension. Final test count post-VBDIP-0001 freeze: approximately 2832 + ~5 = ~2837 (against current 2832 at Phase O1-FRR-PARALLEL ship; the +34 from Phase O1-VSD-BOOTSTRAP per Volume 2 §24 has not yet shipped at VBDIP-0001 authoring).

---

## 8. VEDIP-0001 Forward Work

VBDIP-0001 establishes VED as a named sub-discipline but does not itself author VEDIP-0001. The retroactive engineering-discipline documentation work is named here as a follow-up deliverable, scoped but not executed under VBDIP-0001.

VEDIP-0001 will retroactively document the eighteen Phase O0 commits, the Phase O1-FRR-PARALLEL ship, the Stream J empirical findings, and the parallel O2 SUGGEST anchor as VED-governed work. The document will map the existing 55 PV-CI invariants to VED-INV-1 through VED-INV-55 prefix, with the mapping table serving as the canonical reference for future VED invariant additions.

VEDIP-0001 authoring is anticipated as a moderate-sized deliverable (similar in scope to v1.0 FINAL or Volume 2 FINAL — a structured methodology document with retrospective rather than prospective scope). The authoring window is operator-authorized at VBDIP-0001 freeze but can ship asynchronously from VBDIP-0001 itself; the methodology operates correctly with VED as a named sub-discipline pending VEDIP-0001 authoring, because the underlying engineering discipline has been operating implicitly all along.

---

## 9. Caveats

VBDIP-0001 names what the methodology has become but does not change what the methodology does. The rename is structural rather than operational. Future operators reading the methodology history must understand that the v1.0 FINAL and Volume 2 FINAL documents were authored under the VSD-only era, and the VAD reframing is a layer added at VBDIP-0001 freeze, not a retroactive rewrite of the earlier documents. The earlier documents remain canonical without amendment; the VBDIP-0001 reframing inherits forward.

The VBD invariants (VBD-INV-1 through VBD-INV-3) are markdown-normative at VBDIP-0001 freeze. The Python check function bodies remain `pass` per the existing aspirational-harness discipline in v1.0 §13 and v2.0 §26. Programmatic enforcement is VBDIP-0003 work (analogous to VSDIP-0002 for VSD invariants). The methodology operates correctly with markdown-normative invariants at v1.0 of VBD; the discipline holds even when the Python implementation is incomplete.

The deferred migration to `vad-vault/` is operationally bounded but not time-bounded. VBDIP-0001 does not commit to a specific Phase O1-VAD-MIGRATE ship date. The migration is named, scoped, and acceptance-criteria-specified, but it ships when operator authorization allows, which may be soon after VBDIP-0001 freeze or may be deferred until the methodology accumulates additional empirical operation. The intermediate state (directory name `vsd-vault/` housing the VAD framework) is sustainable indefinitely under the honesty-first documentation in `vsd-vault/README.md`.

VED's retroactive scope assumes that the eighteen Phase O0 commits, the Phase O1-FRR-PARALLEL ship, the Stream J findings, and the parallel O2 SUGGEST anchor were all executed under disciplines that align with what VED retroactively names. This is true for V-check, P-check, atomic commit, and Decision block disciplines, which were operationally consistent across the work. It may not be perfectly true for every detail of every commit; VEDIP-0001 authoring will surface any drift between the disciplines as practiced and the disciplines as retroactively named, and any such drift becomes information for future VEDIPs rather than a refutation of VED as a named sub-discipline.

VBD's retroactive scope is cleaner because VBD names mechanisms (CFSS, unified harness, CDRR, fleet-domain replication) that were specifically authored across Volume 2 with explicit intent. The retroactive prefixing of INV-CFSS-001 to VBD-INV-4 is a pure documentation change with no semantic content shift.

The CVAS document origin (Gemini extrapolation in response to a theoretical prompt) demonstrates that the VBD invariants are addressing a real class of methodology drift, not a hypothetical one. Future LLM-generated extrapolations responding to methodology prompts will exhibit the same drift patterns unless the methodology itself is robust enough to programmatically reject them. VBD-INV-1 through VBD-INV-3 plus VBD-INV-4 (retroactive CFSS rename) collectively harden the methodology against this drift class. VBDIP-0003 work (full Python harness implementation for VBD invariants) closes the gap between markdown-normative discipline and programmatic enforcement.

Novelty claims under VBDIP-0001 expand the conjunction-axis count from Volume 2's nine to eleven: the nine axes from v2.0 §10 plus fleet-domain replication discipline as a claimable architectural property plus primitive composition discipline as a claimable architectural property. The expanded conjunction is empirically anchored — the protocol has already done the work that each new claim names. The novelty bar set by the seven previously validated VAPI claims plus the v2.0 expansion is met by the VBD additions.

---

## 10. Cross-References

Within VAPI methodology documents: VSDIP-0001 (v1.0 FINAL, `wiki/methodology/vsd_methodology_v1_FINAL.md`); VSDIP-0002 (Volume 2 FINAL, `wiki/methodology/vsd_volume_2_final.md`); VSDIP-0003 (pre-bootstrap strengthening, `vsd-vault/proposals/VSDIP-0003-pre-bootstrap-strengthening.md`, pending authoring as a follow-up to VBDIP-0001).

Within VAPI protocol documentation: `Whitepaperv4.md`; `VAPI_INVARIANTS.md`; `VAPI_BIOMETRIC_PRIVACY.md`; `VAPI_CORPUS.md`; `VAPI_CONTEXT.md`; `VAPI_AGENTS.md`; `VAPI_WHAT_IF.md`; `vapi_state_assessment_2026_05_10.md`; `bridge/vapi_bridge/operator_initiative_advancement.py`; `bridge/vapi_bridge/vsd_advancement.py` (post-bootstrap); `scripts/vapi_invariant_gate.py`; `scripts/parallel_o2_anchor.py`; `scripts/parallel_vsd_anchor.py` (post-bootstrap); `.github/INVARIANTS_ALLOWLIST.json`.

Phase ancestors: Phase O0 closure 2026-05-03 (commit `44c26ce0`); Phase O1-FRR-PARALLEL ship (commit `4ddeb43c`); Stream J live anchor (commit `79dacc88`); parallel O2 SUGGEST anchor (commit `2cde36a3`).

External prior art at VBDIP-0001 freeze date: v1.0 FINAL §14 and v2.0 FINAL §28 cross-references carry forward without addition.

CVAS document origin: Gemini extrapolation in response to a theoretical perpetual-development-loop prompt in the architectural collaboration thread on 2026-05-10. Surfaced explicitly here as the empirical motivation for VBD-INV-1 through VBD-INV-3.

---

## 11. Document Metadata

**Document version:** VBDIP-0001 v1.0 **FROZEN**
**Generated:** 2026-05-10
**Frozen:** 2026-05-10 (Phase O1-VBDIP-0001-INTEGRATION Step 5)
**Author authority:** VAPI Architect, sole deployer (`0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692`)
**Architect signature:** Ed25519 signature applied; see `vsd-vault/manifests/proposals-VBDIP-0001/001.manifest.json` (deployer-anchored signing chain established at Step 4 via `vsd-vault/eval/architect_key_attestation.json` — bridge wallet EIP-191 attestation of architect pubkey)
**Manifest path:** `vsd-vault/manifests/proposals-VBDIP-0001/001.manifest.json`
**Architect pubkey (Ed25519, 32B hex):** `056e695f2995070198a0db1a6c264d8234fb88bf5cf6332c354f58a096a78ca8`
**Tags:** `#vbdip #vad #methodology #vapi #frozen-v1 #notebook-llm-corpus #verification-first #honesty-first #sub-discipline-pivot #vsd #ved #vbd #deferred-migration`

**Status transition log:**
- 2026-05-10: Draft v1.0 authored in architectural collaboration thread
- 2026-05-10 (Phase O1-VBDIP-0001-INTEGRATION Step 1, commit `2aea877a`): Provenance pin manifest landed; deferral-boundary witness established
- 2026-05-10 (Step 2, commit `69ac74d2`): Inventory normalization — imported absent artifacts, renamed VBDIP-0001 (1).md → VBDIP-0001.md
- 2026-05-10 (Step 3, commit `be13de49`): State reconciliation amendments — PATTERN-017 count canonicalized; VED-INV-N clarified as count-abstraction; master resumption Phase D revised to Option D2; bootstrap canonical state references refreshed (bridge 2836→2922; PV-CI 55→63)
- 2026-05-10 (Step 4, commit `8b95d5bc`): Architect Ed25519 key generated; bridge wallet EIP-191 attestation produced (`vsd-vault/eval/architect_key_attestation.json`); deployer-anchored signing chain established per VBD-INV-1
- 2026-05-10 (Step 5, this commit): Architect Ed25519 signature applied to VBDIP-0001 canonical hash; manifest authored at `vsd-vault/manifests/proposals-VBDIP-0001/001.manifest.json`; harness extended with `--proposal-type` flag (4 choices); allowlist regenerated 63→66 entries with VBD-INV-001/002/003; `vsd-vault/README.md` authored per §6.2 deferred-migration documentation; **status: FROZEN**

**Supersession discipline:** VBDIP-0001 is a foundational proposal that establishes the VBD lineage and the VAD framework. It is not superseded by future VBDIPs; future VBDIPs build on it. Future VBDIPs (VBDIP-0002 for Phase O1-VAD-MIGRATE, VBDIP-0003 for full Python harness, etc.) reference VBDIP-0001 as their architectural foundation.

---

**End of VBDIP-0001 draft.**

The methodology framework is now VAD. The synthesis sub-discipline is VSD. The engineering sub-discipline is VED. The bridge sub-discipline is VBD. The methodology surface remains one. The audit trail remains continuous. The numbered-proposal discipline remains the only path for evolution.

The protocol's architectural quality has been the discipline of holding decisions open until the evidence warrants closure. VBDIP-0001 closes the framework-name decision. The decisions that remain open — VEDIP-0001 authoring, VBDIP-0002 migration timing, VBDIP-0003 Python harness implementation — remain operator-authorized at their own future moments. The methodology is ready.
