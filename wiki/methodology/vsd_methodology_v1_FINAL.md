# Verified Synthesis Discipline (VSD) — Methodology Specification v1.0 FINAL

**Status:** v1.0 FINAL (FROZEN-candidate, NotebookLM-ready)
**Author:** VAPI Architect (single deployer, bridge wallet `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692`)
**Scope:** VAPI-internal. Not a generic PKM methodology.
**Date:** 2026-05-10
**Supersedes:** v0.1 draft (2026-05-10 AM)
**Changes from v0.1:** PBSA exemplar pointer made durable rather than dated; Stream J adversarial note canonical seeding; FRR scopeRoots as second eigenspace seed; F1+F2+F4+F5 enhancements promoted to v1.0 bootstrap; novelty analysis updated with current empirical anchors.

---

## 0. NotebookLM Reading Note

This document is the canonical methodology reference for VSD as ingested into the VAPI/VSD master corpus on NotebookLM. Every section is structured for source-grounded retrieval. When NotebookLM is asked questions about VSD methodology, invariants, note types, harness mechanics, or bootstrap procedure, the answers are grounded in this document. When asked about VAPI protocol state, the answers are grounded in the most recent PBSA note in `notes/pbsa/` of the vault, not in this document. This document is the methodology; PBSA notes are the protocol state. The two are deliberately separate.

---

## 1. TL;DR

Verified Synthesis Discipline is to research synthesis what FROZEN-v1 + PV-CI is to protocol invariants: an immutable, declarative eval harness expressed as markdown invariants in `eval/INVARIANTS.md` plus the aspirational Python harness `vsd_eval_harness.py`, gating an editable synthesis orchestrator in `orchestrator/`. The methodology inherits VAPI's foundational architectural commitments — honesty-first per-component flagging, immutable-versus-editable separation, ceremony-gated capability expansion, continuous deployer-verified provenance — and applies them to the act of synthesizing external research into protocol-relevant insight. Phase-Boundary State Assessments emerge as natural first-class outputs.

The methodology is genuinely novel against prior art on five conjoined axes. Karpathy's autoresearch loop, released March 7, 2026, applied for the first time to external-research synthesis (not training, not coding skills, not prompt optimization) with a markdown-encoded immutable harness. C2PA-analogous content-bound manifests under the name Synthesis Provenance Triple — claim plus ingredient chain plus architect signature — bound to a single deployer wallet, replacing freeform epistemic-status tags with cryptographically verifiable provenance over atomic markdown notes. NotebookLM coupling as a regenerated secondary index whose corpus subset is determined by harness-passing notes only, never by hand. Adversarial synthesis as a first-class note type structurally required for any defense claim, formalizing a discipline VAPI already practices through its WIF corpus into harness-checkable invariants. Eigenspace anchoring of synthesis identity through cryptographic references to VAPI's empirically-validated AIT N=37 biometric corpus and the on-chain FRR fleet-coordination commitment, making the vault's identity claims reducible to verifiable on-chain artifacts.

The vault is bootstrappable today through the seven-step procedure in §11, executable as a parallel architectural workstream during the natural shadow_age accumulation window between Phase O1-FRR-PARALLEL completion and the O3_ACT promotion gate clearing in mid-to-late May 2026.

---

## 2. The Five VSD Invariants — the Irreducible Commitments

The methodology rests on five invariants frozen at bootstrap. These are the VSD analog of VAPI's nine FROZEN-v1 primitives and 55 PV-CI locked invariants.

| ID    | Name                                  | Borrowed from              | New in VSD                                                                                  |
|-------|---------------------------------------|----------------------------|---------------------------------------------------------------------------------------------|
| VSD-1 | Immutable harness, editable orchestrator | Karpathy autoresearch | Markdown-encoded harness; harness expresses synthesis fidelity, not training fidelity       |
| VSD-2 | Per-claim provenance triple           | C2PA, PROV-O               | Single-deployer-key signing; markdown-native; atomic per note revision                      |
| VSD-3 | Honesty-first flagging is harness-checked | Digital garden epistemic status | Confidence and effort fields are validated invariants, not advisory prose                |
| VSD-4 | Phase-boundary state assessment as native output | None directly | PBSA template plus harness rule: every phase increment emits a PBSA, signed                 |
| VSD-5 | NotebookLM is a regenerated secondary index | None directly         | Corpus equals harness-passing note set; manual addition forbidden; regen on tag/PBSA        |

These five invariants are frozen at the moment of bootstrap. Modifying any of them requires a numbered VSDIP proposal (§12) plus a re-freeze ceremony documented in `eval/FROZEN.md`. They are not subject to ordinary edits.

---

## 3. Vault Filesystem Layout

The vault is filesystem-portable markdown plus signed JSON manifests. It opens as an Obsidian vault but does not depend on any Obsidian plugin. NotebookLM ingests the corpus snapshot directory directly. The structure is:

```
vsd-vault/
├── README.md                           # vault entry point
├── MEMORY.md                           # cross-session context
├── .vsd/                               # tooling — not load-bearing for vault semantics
│   ├── vsd_eval_harness.py             # immutable Python harness
│   ├── vsd_synthesizer.py              # editable orchestrator script
│   ├── vsd_provenance.py               # signing/verification utility
│   ├── vsd_notebooklm_export.py        # corpus regeneration
│   └── results.tsv                     # synthesis ledger (git-tracked)
├── eval/                               # IMMUTABLE LAYER (the harness)
│   ├── INVARIANTS.md                   # declarative invariants in markdown
│   ├── NOTE_SCHEMAS.md                 # frontmatter schemas for each note type
│   ├── HARNESS_RATIONALE.md            # why each invariant exists
│   └── FROZEN.md                       # version, freeze date, hash of this directory
├── orchestrator/                       # EDITABLE LAYER (the synthesizer skill)
│   ├── SKILL.md                        # the operating skill
│   ├── SYNTHESIS_LOOP.md               # the synthesis cycle
│   ├── PRIORS.md                       # accumulated synthesis heuristics
│   └── BOUNDARIES.md                   # what the orchestrator must not modify
├── notes/                              # synthesis output — nine note types
│   ├── claim/                          # atomic claim notes
│   ├── ingredient/                     # external sources
│   ├── synthesis/                      # synthesis notes combining claims and ingredients
│   ├── pbsa/                           # phase-boundary state assessments
│   ├── decision/                       # architect decisions
│   ├── adversarial/                    # attack vectors and closure evidence (F1)
│   ├── eigenspace/                     # biometric and structural eigenspace anchors (F2)
│   ├── study/                          # empirical studies with preregistration discipline (F4)
│   └── industry/                       # industry-mapping notes (F5)
├── manifests/                          # provenance manifests, one directory per note
│   └── <note-uuid>/
│       ├── 001.manifest.json           # signed manifest, revision 001
│       ├── 001.sig                     # detached Ed25519 signature
│       └── ...
├── proposals/                          # VSDIP proposals (F3)
│   ├── VSDIP-0001-initial-methodology.md
│   └── ...
├── corpus/                             # NotebookLM-ready snapshots
│   ├── snapshot-<timestamp>/
│   │   ├── MANIFEST.txt
│   │   └── *.md
│   └── current -> snapshot-<latest>/
└── archive/                            # quarantined notes that no longer pass harness
```

The `.vsd/` directory contains tooling that lives outside vault semantics — deleting it should not corrupt the vault, only suspend programmatic checks. The `eval/` directory is the FROZEN harness; after bootstrap, the only legal mutation is a documented re-freeze ceremony per §4.4. The `orchestrator/` directory is the editable synthesizer, mirroring Karpathy's `program.md` but expanded into multiple files so the boundary discipline is explicit. The `notes/` directory holds nine note types — five core types from v0.1 plus four additions promoted from F1/F2/F4/F5 to v1.0 bootstrap. The `manifests/` directory is a sidecar architecture so the markdown stays clean and NotebookLM-friendly. The `proposals/` directory holds numbered VSDIPs that govern any change to the harness or methodology. The `corpus/` directory is derived state, regenerable, and never edited by hand.

---

## 4. Note Types and Frontmatter Schemas

All note files are markdown with YAML frontmatter. No `[[wikilinks]]` are load-bearing for cross-reference; the methodology requires UUID-based references in `refs:` frontmatter so the vault remains valid when ingested into NotebookLM, which does not render Obsidian wikilinks.

### 4.1 `claim/` note

The atomic single-claim, VAPI-internal proposition. Frontmatter schema:

```yaml
---
type: claim
id: c-2026-05-10-0001
title: Battery-stratified separation ratio is the north-star metric
created: 2026-05-10T14:23:00Z
modified: 2026-05-10T14:23:00Z
phase: O1-FRR-PARALLEL
status: draft | review | frozen
confidence: certain | highly-likely | likely | possible | unlikely | highly-unlikely | remote | impossible
effort: 47
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
contradicts: []
supersedes: null
manifest: manifests/c-2026-05-10-0001/001.manifest.json
---
```

The `confidence:` field uses the eight Kesselman estimative words from Rachel F. Kesselman's 2008 thesis on verbal probability expressions in National Intelligence Estimates, as adopted by Gwern in his confidence-tags scheme on gwern.net/about. Free-form prose is forbidden in this field; harness invariant VSD-INV-2 enforces this.

### 4.2 `ingredient/` note

External source with verbatim quote, paraphrase, and content hash. Frontmatter schema:

```yaml
---
type: ingredient
id: i-2026-05-10-0001
title: "C2PA spec — definition of Active Manifest"
source_url: https://spec.c2pa.org/specifications/...
source_hash: sha256:<hash-of-fetched-content>
fetched: 2026-05-10T14:23:00Z
deployer: 0x0Cf36...
license: CC-BY | CC0 | fair-use | proprietary
quote_verbatim: |
  "Active Manifest — The last manifest in the list of C2PA Manifests..."
manifest: manifests/i-2026-05-10-0001/001.manifest.json
---
```

The `source_hash` field is critical. Drift in source content forces a new ingredient ID rather than a silent update, exactly mirroring C2PA's hard-binding philosophy where tampering with content invalidates the binding.

### 4.3 `synthesis/` note

Combines claims and ingredients into a derivation. Frontmatter schema:

```yaml
---
type: synthesis
id: s-2026-05-10-0001
title: VSD provenance scheme should mirror C2PA active-manifest semantics
phase: O1-FRR-PARALLEL
status: draft
confidence: highly-likely
effort: 47
deployer: 0x0Cf36...
ingredients: [i-2026-05-10-0001, i-2026-05-10-0002]
claims_created: [c-2026-05-10-0001]
relationship_to_predecessor: parentOf | componentOf | inputTo | null
manifest: manifests/s-2026-05-10-0001/001.manifest.json
---
```

The `relationship_to_predecessor` field is borrowed verbatim from C2PA's ingredient relationship taxonomy: an ingredient is either the `parentOf` the current asset, a `componentOf` that asset, or `inputTo` the creation of an asset. Harness invariant VSD-INV-7 enforces this.

### 4.4 `pbsa/` note (Phase-Boundary State Assessment)

The first-class phase-transition output. Generated only at phase boundaries. Frontmatter schema:

```yaml
---
type: pbsa
id: pbsa-O1-FRR-PARALLEL-shipped
phase_from: O1-FRR-IN-FLIGHT
phase_to: O1-FRR-PARALLEL-SHIPPED
created: 2026-05-10T22:00:00Z
deployer: 0x0Cf36...
honesty_flags:
  deployed_verified:
    - FRR primitive (FROZEN-v1 #9, on-chain at 0x3aee5a26...)
    - Sentry scopeRoot 0x1af7854a... (matches O2 SUGGEST Merkle)
    - Guardian scopeRoot 0x70ccf51f... (matches O2 SUGGEST Merkle)
    - Curator scopeRoot 0xeb400a5c... (matches O2 SUGGEST Merkle)
    - advancement_log row id=2 with fleet_phase_aligned=True
  emulated:
    - Curator using MockKMSClient on testnet (mainnet requires HSM provisioning)
  undeployed:
    - parallel_o3_anchor.py (next ship after shadow_age clears 504h)
    - Third Groth16 verifier (FRR ZK proof)
  deferred:
    - O4-O6 capability expansion (per design phase specifications)
readiness_score: null
readiness_score_methodology: |
  No readiness score this PBSA — FRR is fleet-coordination primitive,
  not biometric or tournament-readiness primitive. North-star metric
  unchanged from prior PBSA (AIT 1.199, N=37, all_pairs_above_1=True).
gates_passed:
  - FRR primitive frozen and on chain
  - Three scopeRoots anchored matching pre-authored Merkles
  - Stream J two latent bugs closed (T-O1-FRR-7 regression test locks fixes)
  - Wallet impact 0.179 IOTX vs 0.18 estimate (planning held)
  - PV-CI invariants 49 → 55 (+6 FRR family invariants)
  - Bridge tests 2822 → 2832 (+10)
gates_pending:
  - shadow_age >= 504h per agent (Sentry+Guardian ~14.6 days remaining; Curator ~21 days)
  - draft_payload_count >= 50 per agent
  - operator_disagreement_rate < 5%
  - AWS KMS HSM provisioning for Curator agent (mainnet path)
manifest: manifests/pbsa-O1-FRR-PARALLEL-shipped/001.manifest.json
---

# Required body sections (enforced by harness):

## State of the Protocol
## What Is Genuinely Done
## What Is Emulated/Flagged
## What Is Undeployed
## North-Star Metric Movement
## Outstanding Gates
## Recommendation
```

The PBSA exemplar above shows what the methodology produces as a templated output. The current canonical PBSA seed for the vault at bootstrap time is whatever state assessment exists in the protocol repository at that moment. The vault bootstrap procedure (§11 step 4) reads the most recent state assessment from the protocol repository and reformats it into the PBSA schema as the seed `pbsa/` entry. This pointer is durable rather than dated — it survives the protocol's ship cadence without requiring methodology updates.

### 4.5 `decision/` note

Records architect-level decisions: pause, resume, freeze, unfreeze, scope change. Frontmatter schema:

```yaml
---
type: decision
id: d-2026-05-10-0001
title: "Bootstrap VSD vault during shadow_age accumulation window"
created: 2026-05-10T...
deployer: 0x0Cf36...
decision: pause | resume | freeze | unfreeze | scope-change | bootstrap | promotion
links_to_state: pbsa-O1-FRR-PARALLEL-shipped
manifest: manifests/d-2026-05-10-0001/001.manifest.json
---
```

### 4.6 `adversarial/` note (F1, promoted to v1.0 bootstrap)

VAPI is an anti-cheat protocol; its threat model is that adversaries will try to defeat it. A standard synthesis discipline produces notes describing what is true; a VAPI-native synthesis discipline must produce notes describing what an adversary would attempt and what defenses close those attacks. This note type formalizes the discipline that VAPI already practices through its WIF corpus into harness-checkable invariants. Frontmatter schema:

```yaml
---
type: adversarial
id: adv-2026-05-10-0001
title: "Canonical-name vs Q9-hex schema mismatch in store helpers"
created: 2026-05-10T22:30:00Z
deployer: 0x0Cf36...
attack_vector: "Watcher passes canonical name 'anchor_sentry' to store
  helpers querying activation_log keyed on Q9-frozen agentId
  '0xb21e1ec2...'. All queries silently return None in production."
attack_cost_estimate: "zero — surfaces only under live empirical
  conditions; V-checks against documented specifications cannot detect"
defense_status: deployed-verified | emulated | undeployed | undefended
closure_evidence: |
  Fix: _resolve_agent_id_for_store translator using existing cfg-attr
  mapping. Backward-compat preserved via canonical-name fallback when
  cfg attr missing. Regression test T-O1-FRR-7 locks the fix.
  Commit 79dacc88 (Stream J + live anchor record).
related_wif: null
manifest: manifests/adv-2026-05-10-0001/001.manifest.json
---
```

Harness invariant VSD-INV-13: any claim about a defense (in any note type) must be accompanied by at least one adversarial note documenting the attack it closes. This is the synthesis-domain analog of `triage_prereq_required=True` — closure as an architectural property, not a marketing one.

### 4.7 `eigenspace/` note (F2, promoted to v1.0 bootstrap)

The protocol's identity claims rest on eigenspaces — biometric (the AIT corpus) and structural (the FRR fleet commitment). The vault anchors its synthesis identity to these eigenspaces through this note type. Frontmatter schema:

```yaml
---
type: eigenspace
id: eig-2026-05-10-0001
title: "AIT biometric eigenspace, N=37 corpus snapshot"
created: 2026-05-10T...
deployer: 0x0Cf36...
eigenspace_class: biometric | structural | composite
measurement_date: 2026-04-20
sample_size: 37
sample_breakdown: "P1=13, P2=10, P3=14"
pooled_metric:
  ratio: 1.199
  all_pairs_above_1: true
stratified_metric: null
methodology_hash: sha256:<hash-of-analyze_interperson_separation.py-Phase-229>
dataset_hash: sha256:<hash-of-AIT-corpus-files>
on_chain_anchor:
  primitive: BIOMETRIC-SNAPSHOT-v1
  ceremony_block: 43451392
  vk_hash: "0x32fda285..."
freshness_window_days: 90
manifest: manifests/eig-2026-05-10-0001/001.manifest.json
---
```

A second eigenspace note seeds at bootstrap from the FRR ship:

```yaml
---
type: eigenspace
id: eig-2026-05-10-0002
title: "Fleet structural eigenspace, FRR-anchored at O1-FRR-PARALLEL"
created: 2026-05-10T22:00:00Z
deployer: 0x0Cf36...
eigenspace_class: structural
measurement_date: 2026-05-10
component_commitments:
  sentry_scopeRoot: "0x1af7854a..."
  guardian_scopeRoot: "0x70ccf51f..."
  curator_scopeRoot: "0xeb400a5c..."
fleet_commitment:
  primitive: FRR-v1
  frr_hash: "0x3aee5a26..."
  fleet_phase_aligned: true
  advancement_log_row: 2
on_chain_anchor:
  contract: AdvancementLog
  tx_commits: ["4ddeb43c", "79dacc88"]
freshness_window_days: 30
manifest: manifests/eig-2026-05-10-0002/001.manifest.json
---
```

Harness invariant VSD-INV-14: any PBSA citing a readiness score or north-star metric must reference at least one frozen eigenspace note within its stated freshness window.

### 4.8 `study/` note (F4, promoted to v1.0 bootstrap)

Empirical studies with preregistration discipline. Frontmatter schema:

```yaml
---
type: study
id: study-2026-05-10-0001
title: "Phase 213 zero-padded FFT fix re-measure of tremor_resting separation"
created: 2026-05-10T...
deployer: 0x0Cf36...
hypothesis: |
  Phase 213 zero-padded FFT (4096-point) resolves P1≈3.1Hz vs P3≈3.7Hz
  to distinct bins, lifting tremor_resting all_pairs_p0_ok from False
  to True without new sessions.
preregistration_hash: sha256:<hash-of-this-frontmatter-at-creation>
preregistration_locked: 2026-05-10T...
dataset_hash: sha256:<hash-of-tremor_resting-corpus-N27>
methodology_hash: sha256:<hash-of-Phase-213-FFT-implementation>
result_summary: null
result_locked: null
replication_status: not-attempted | attempted | confirmed | failed-replication
negative_result: null
manifest: manifests/study-2026-05-10-0001/001.manifest.json
---
```

Harness invariant VSD-INV-15: a study note where `result_summary` is non-empty must have a non-null `preregistration_hash` set at an earlier timestamp. The harness checks the temporal order; you cannot retrofit a hypothesis to fit the data because the hash chain catches it.

### 4.9 `industry/` note (F5, promoted to v1.0 bootstrap)

Industry-mapping notes for adjacent applications of VAPI. Frontmatter schema:

```yaml
---
type: industry
id: ind-2026-05-10-0001
title: "Remote-proctored examinations and certifications"
created: 2026-05-10T...
deployer: 0x0Cf36...
industry_name: "Remote proctored examinations"
use_case: |
  Eigenspace-as-identity primitive answers the structural problem of
  someone other than the registered candidate completing the exam,
  which current proctoring solutions solve poorly.
vapi_components_required:
  - AIT eigenspace (biometric identity anchor)
  - PoAC record format (228-byte commitment)
  - PHYSICAL_DATA_ATTESTATION v1
  - Three-zone privacy compartmentalization
deployed_components_required:
  - AIT separation ratio > 1.0 across all required probes (PARTIAL — AIT clear, free-form open)
  - Sufficient corpus for examinee-population eigenspace (UNDEPLOYED — VAPI corpus is N=3)
regulatory_constraints:
  - FERPA in US educational contexts
  - GDPR Art. 22 (automated decision-making) in EU
  - State-level testing-board approval
market_size_evidence: null
disqualifying_factors:
  - VAPI corpus is N=3 players; examination-population identity requires N>>3
  - DualShock Edge controller is wrong form factor for examination context
honest_assessment: |
  VAPI's primitives are structurally applicable conditional on a
  separate corpus build, separate hardware integration work, and
  separate regulatory approval that VAPI has not done. Honest framing
  is "VAPI's architecture would apply IF [list of work]" not "VAPI
  applies to remote proctoring."
manifest: manifests/ind-2026-05-10-0001/001.manifest.json
---
```

Harness invariant VSD-INV-16: an industry note claiming applicability must explicitly enumerate `regulatory_constraints` and `disqualifying_factors` fields as non-empty. A note that claims applicability without naming constraints fails the invariant.

---

## 5. The Immutable Harness Layer

The harness layer in `eval/` encodes sixteen declarative invariants. Each invariant is stated as markdown plus an aspirational Python check signature. The markdown is normative at v1.0; the Python ships as `def ... -> CheckResult: ...` signatures with `pass` bodies, with full implementations slated for v1.1 per VSDIP-0002. This is honest about current state — the harness is real as discipline, partial as automation.

### 5.1 Sixteen invariants

The full list, with brief descriptions:

**VSD-INV-1: Frontmatter schema conformance.** Every note in `notes/` must have YAML frontmatter conforming to the schema in `NOTE_SCHEMAS.md` for its declared type.

**VSD-INV-2: Confidence is a Kesselman estimative word.** The `confidence:` field must be one of the eight estimative words. Free-form prose forbidden; defends against epistemic-status-as-witticism drift.

**VSD-INV-3: Deployer identity does not fragment.** The `deployer:` field must equal `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692` in every note. Mirrors VAPI's continuous deployer-verified provenance commitment.

**VSD-INV-4: Manifest exists and verifies.** For every note, `manifests/<id>/<latest>.manifest.json` must exist, must hard-bind via SHA-256 to the canonicalized note bytes, and the detached `.sig` must verify against the architect's published Ed25519 public key.

**VSD-INV-5: Honesty-first flagging is mandatory at PBSA boundaries.** Every PBSA note must contain non-empty `honesty_flags.emulated`, `honesty_flags.undeployed`, and `honesty_flags.deployed_verified` lists, or explicitly state `honesty_flags.exhaustive_review_completed: true` with a linked decision note.

**VSD-INV-6: Ingredient hash matches fetched content.** Drift in source content forces a new ingredient ID, not a silent update.

**VSD-INV-7: Synthesis notes declare ingredient relationship.** Every synthesis note must set `relationship_to_predecessor` to one of `parentOf`, `componentOf`, `inputTo`, or null. Borrowed verbatim from C2PA ingredient relationship taxonomy.

**VSD-INV-8: Novelty claims are programmatically checkable.** Any note tagging itself `tags: [novelty-claim]` must include a `prior_art:` list with at least three entries citing methodology, what is borrowed, and what is new.

**VSD-INV-9: Frozen notes are append-only.** Notes with `status: frozen` must not be modified. Modifications require a new note that supersedes the frozen one.

**VSD-INV-10: Emulated and undeployed components are not weighted in scores.** PBSA notes claiming a readiness score must exclude emulated and undeployed components from the numerator unless `readiness_score_methodology` explicitly states otherwise. Direct inheritance of VAPI's honesty-first commitment.

**VSD-INV-11: NotebookLM corpus is harness-derived.** `corpus/current/` must contain only notes for which all preceding invariants pass. Manual addition is forbidden; regen via `vsd_notebooklm_export.py` only.

**VSD-INV-12: Phase-boundary requires a PBSA.** Any commit that increments the `phase:` field on any note must include a new PBSA note for the boundary, or be reverted.

**VSD-INV-13 (F1): Defense claims require adversarial closure.** Any claim about a defense in any note type must be accompanied by at least one adversarial note documenting the attack it closes.

**VSD-INV-14 (F2): Readiness scores require eigenspace anchoring.** Any PBSA citing a readiness score or north-star metric must reference at least one frozen eigenspace note within its stated freshness window.

**VSD-INV-15 (F4): Studies require preregistration temporal order.** A study note where `result_summary` is non-empty must have a non-null `preregistration_hash` set at an earlier timestamp.

**VSD-INV-16 (F5): Industry claims require constraint enumeration.** An industry note claiming applicability must explicitly enumerate `regulatory_constraints` and `disqualifying_factors` as non-empty fields.

### 5.2 Harness rationale and freeze

`eval/HARNESS_RATIONALE.md` contains a paragraph for each invariant explaining why it is frozen — the rationale future architects must read before any re-freeze ceremony. `eval/FROZEN.md` records the freeze version, freeze date, hash of the `eval/` directory, and architect signature. Re-freeze requires a decision note authorizing the change, a new PBSA documenting protocol state at re-freeze, a bumped freeze version, and re-signing with the deployer-anchored key.

---

## 6. The Editable Orchestrator Layer

`orchestrator/SKILL.md` is the direct analog of Karpathy's `program.md`. It includes a literal CAN/CANNOT block specifying what the synthesizer is and is not authorized to modify. The synthesizer can create or modify notes in `notes/`, add manifests, edit `orchestrator/` files except `BOUNDARIES.md`, update `MEMORY.md`, and trigger NotebookLM corpus regeneration. The synthesizer cannot modify any file in `eval/` (it is FROZEN), cannot modify `vsd_eval_harness.py`, cannot add deployer addresses other than `0x0Cf36...`, cannot edit a note with `status: frozen` (must supersede instead), and cannot commit a phase-increment without a PBSA.

The synthesis loop runs through nine steps per cycle: state the question being synthesized; pull ingredients into ingredient notes and sign manifests; draft claim notes from ingredients; draft synthesis notes combining claims and declaring ingredient relationship; run `vsd_eval_harness.py` and fix or revert on failure; commit; if a phase boundary was crossed, write the PBSA note; append a row to `.vsd/results.tsv`; regenerate the corpus if any frozen note changed status.

The simplicity criterion is inherited verbatim from Karpathy's autoresearch: a small synthesis improvement that adds three new note types is not worth it; conversely, removing a note (superseding it cleanly) and the harness still passes is a great outcome.

`orchestrator/PRIORS.md` accumulates synthesis heuristics over time. `orchestrator/BOUNDARIES.md` records meta-rules the orchestrator itself cannot self-modify, making the immutable/editable separation itself an invariant.

---

## 7. Provenance Mechanism — the Synthesis Provenance Triple

The provenance scheme is a deliberate, simplified port of the C2PA Manifest architecture to atomic markdown notes signed by a single architect-controlled key. Each note revision has a manifest JSON file modeled on the C2PA `claim-map-v2` CDDL structure with `created_assertions` and `gathered_assertions` arrays.

The hard binding works through a `vsd.hash.note` assertion containing the SHA-256 of the canonicalized note in UTF-8 with LF line endings, with the `manifest:` field in frontmatter excluded from the hash range — exactly analogous to C2PA's `exclusions` mechanism for `c2pa.hash.data`. Tampering with the note produces a hash mismatch, causing harness invariant VSD-INV-4 to fail.

Ingredient chaining works through `gathered_assertions` with `relationship` set to `parentOf`, `componentOf`, or `inputTo`. Each ingredient assertion carries the hash of the ingredient's own manifest, yielding a recursively validatable provenance directed acyclic graph. This is directly modeled on the C2PA chain of provenance.

The active manifest for each note is the highest-numbered revision under `manifests/<id>/`. Older revisions are retained for audit but are not the binding manifest. This is the direct port of C2PA §2.3.7 to atomic notes.

Signing uses a single Ed25519 architect key paired conceptually with the bridge wallet `0x0Cf36...`. The wallet is on IoTeX and uses secp256k1; for vault provenance, an Ed25519 key signed once by the wallet at bootstrap establishes the cryptographic linkage between protocol identity and synthesis identity — the deployer-anchored synthesis key. Detached signatures are stored as `<rev>.sig` next to each manifest, generated using `openssl pkey`. The `vsd_provenance.py` utility provides `sign_note()`, `verify_note()`, and `verify_chain()` functions.

The architecture is novel because C2PA is for media assets, signed by enterprise X.509 certificates on a published trust list, governed by a coalition. VSD ports the architecture to atomic markdown synthesis notes, signed by a single architect key anchored to a deployer wallet, governed by a single individual. The intellectual move — content-bound, ingredient-chaining, active-manifest provenance for atomic markdown — does not appear in any prior-art family surveyed.

---

## 8. NotebookLM Coupling

The vault-to-NotebookLM pipeline runs through `vsd_notebooklm_export.py`, which walks `notes/`, runs `vsd_eval_harness.py`, and copies into `corpus/snapshot-<timestamp>/` only the notes that pass all sixteen invariants. Drift notes, draft notes failing VSD-INV-2, unsigned notes failing VSD-INV-4 — all excluded. `corpus/current` is symlinked to the latest snapshot.

The corpus uses one file per note retaining frontmatter (NotebookLM ingests markdown verbatim), a `MANIFEST.txt` at the top of each snapshot listing every included note ID with its SHA-256 and active-manifest hash (this becomes part of the NotebookLM source set so the model can be queried about provenance state), and an inline `Provenance:` line at the top of each exported file's body promoting confidence, effort, and deployed-emulated-undeployed flags so honesty-first flagging survives the transition into a tool that does not render YAML frontmatter contextually.

Regeneration triggers are event-driven, not time-based. Any commit that adds or removes a `notes/**/*.md` file triggers regen. Any change in a note's status from draft or review to frozen, or frozen to superseded, triggers regen. Any new PBSA note triggers mandatory regen. Any harness re-freeze triggers regen.

The compensation for NotebookLM lacking Obsidian's structure includes promoting frontmatter to plain-text `Provenance:` headers in exported bodies, including the `MANIFEST.txt` index as a queryable source, forbidding `[[wikilinks]]` from being load-bearing per §4 (using UUIDs in `refs:` frontmatter instead, which export cleanly as plain text), naming source files `<id>--<slug>.md` so NotebookLM citation links are stable across regenerations, and following the master-corpus pattern advocated by Steven Johnson, Editorial Director of NotebookLM and Google Labs, where one master corpus stores all raw material and smaller focused notebooks pull selected sources from it. The vault's `corpus/current` is precisely that master corpus.

The `Provenance:` header that begins each exported note takes the form: `Provenance: type=synthesis | confidence=highly-likely | effort=47min | deployer=0x0Cf36... | manifest_hash=sha256:abc... | phase=O1-FRR-PARALLEL | status=frozen`. This single line makes confidence and provenance queryable in NotebookLM without the user needing to remember to ask.

---

## 9. Honesty-First Synthesis Flagging

Every claim, synthesis, and PBSA note must distinguish four states for any protocol component referenced. Deployed-verified means the component is on-chain, transactions exist, the bridge wallet signed it; counts in scores. Emulated means the component runs in code but is not wired to live infrastructure (Phase O0 operator agents shipped inactive; Curator currently uses MockKMSClient on testnet); explicitly excluded from readiness scores per VSD-INV-10. Undeployed means the component does not yet exist in code; explicitly excluded. Deferred means the component is intentionally postponed with a linked decision note; excluded but not held against the score.

A synthesis note claiming "VAPI is X% ready" must, by VSD-INV-10, derive X exclusively from deployed-verified components, or specify a different methodology in `readiness_score_methodology`. This is not a guideline. It is a harness check.

---

## 10. Novelty Analysis with Current Empirical Anchors

The novelty analysis in this section reflects what is true at v1.0 freeze date 2026-05-10. Future evolutions update through numbered VSDIPs.

| Component                                  | Borrowed from                       | New in VSD                                          |
|--------------------------------------------|-------------------------------------|-----------------------------------------------------|
| Atomic single-idea notes                   | Zettelkasten / Smart Notes / Evergreen | (no claim)                                       |
| Confidence/epistemic-status tags           | Gwern's Kesselman scheme; Maggie Appleton's "Epistemic Disclosure" | Harness-checked; not advisory                  |
| Maps of Content                            | LYT (Nick Milo)                     | Deliberately omitted; PBSA notes substitute        |
| PARA actionability                         | Tiago Forte                         | Deliberately omitted; phase model substitutes      |
| Bidirectional links                        | Roam / Obsidian                     | Deliberately non-load-bearing; UUIDs canonical     |
| Immutable eval / editable orchestrator     | Karpathy autoresearch (2026-03-07)  | Markdown-encoded harness; synthesis-fidelity       |
| Manifest + hard binding + ingredient chain | C2PA Technical Specification        | Markdown-native; single-deployer; atomic notes     |
| Workflow provenance                        | RO-Crate / PROV-O / FAIR            | Lightweight; no JSON-LD/RDF; per-note granularity  |
| Sentence-level citations                   | Elicit (PRISMA 2020)                | Verbatim quote with source_hash invariant          |
| Improvement-proposal lifecycle             | EIP-1 / IIP-1                       | Compressed to {draft, review, frozen, superseded}  |
| Phase-boundary state assessment            | (none)                              | Templated, harness-checked, per-phase artifact     |
| NotebookLM as regenerated secondary index  | (none)                              | Corpus = harness-passing subset; no manual editing |
| Honesty-first as harness invariant         | VAPI architecture                   | Imported into synthesis domain                     |
| Adversarial note as required closure       | VAPI WIF practice                   | Formalized into harness-checked invariant (F1)     |
| Eigenspace as identity anchor              | VAPI biometric/structural eigenspaces | Synthesis identity reduces to on-chain artifacts (F2) |
| Empirical study with preregistration       | OSF / AsPredicted                   | Hash-chained temporal order; harness-enforced (F4) |
| Industry-mapping with constraint discipline | (none)                              | Constraints + disqualifiers are required fields (F5) |

The conjunction of Karpathy harness pattern plus C2PA-style content-bound provenance plus VAPI honesty-first imported into knowledge work plus PBSA as native output plus NotebookLM as harness-derived projection plus adversarial-as-required-closure plus eigenspace identity anchoring plus preregistration-as-harness-check plus constraint-disciplined industry mapping is not present in any prior art surveyed. The conjunction is what is genuinely novel. Each piece is honestly attributed.

This methodology meets the same novelty bar as the seven previously validated VAPI claims: AGaaS delivery model, Composable Proof Triple, 228-byte frozen format as protocol constant, AutoResearch applied to skill self-improvement, biometric eigenspace as tournament identity anchor, `triage_prereq_required=True` as attack vector closure, and three-zone privacy compartmentalization for biometric data on a public chain.

---

## 11. Recommendations — the Bootstrap Sequence

The seven-step bootstrap sequence is executable in one Claude Code `/vapi` session for setup plus one or two follow-up sessions for first-cycle synthesis. The natural bootstrap window is between Phase O1-FRR-PARALLEL completion (shipped 2026-05-10) and the O3_ACT promotion gate clearing in mid-to-late May 2026, during the shadow_age accumulation period when protocol-side work has natural quiet. Bootstrapping in this window means the vault is live in time to synthesize against the O3_ACT ship as its second PBSA.

### Step 1 — Create vault skeleton

Create the directory structure under `vsd-vault/`. Initialize git with commit signing enabled to mirror continuous deployer-verified provenance. Generate the architect Ed25519 key using `openssl genpkey -algorithm ed25519`. Move to step 2 when the vault skeleton exists and the architect key is generated.

### Step 2 — Write the harness

Create `eval/INVARIANTS.md` from §5.1 with all sixteen invariants, `eval/NOTE_SCHEMAS.md` from §4 with all nine note type schemas, `eval/HARNESS_RATIONALE.md` with one paragraph per invariant, and `eval/FROZEN.md` with computed freeze hash and architect signature. Stub `vsd_eval_harness.py` with function signatures from §5; `pass` bodies are acceptable at v1.0 because the markdown invariants are normative. Move to step 3 when the harness is signed and committed.

### Step 3 — Write the orchestrator

Create `orchestrator/SKILL.md` from §6, `orchestrator/PRIORS.md` (initially empty), and `orchestrator/BOUNDARIES.md` listing exactly which `eval/*` files are forbidden to modify. Move to step 4 when the orchestrator exists and Claude Code can read `SKILL.md` as its operating skill.

### Step 4 — Seed canonical notes for each note type

Create one note per type as the worked example. The `decision/` note records the bootstrap decision itself. The `ingredient/` note quotes verbatim from the C2PA active-manifest specification used in this methodology. The `claim/` note states that battery-stratified separation ratio is the north-star metric. The `synthesis/` note explains why VSD adopts C2PA semantics. The `pbsa/` note seeds from whatever the most recent state assessment in the protocol repository is at bootstrap time, reformatted into the §4.4 schema with full honesty_flags taxonomy. The `adversarial/` note documents the Stream J canonical-name versus Q9-hex schema mismatch as the canonical first finding. The `eigenspace/` note seeds the AIT N=37 corpus as the first biometric eigenspace and the FRR scopeRoots as the first structural eigenspace. The `study/` note preregisters the Phase 213 tremor_resting re-measure with `result_summary: null` and `preregistration_hash` locked. The `industry/` note seeds remote-proctored examinations as the first industry-mapping note, with full constraint and disqualifier enumeration. For each note, generate the manifest, sign it, and store the signature. Move to step 5 when at least one note per type exists, harness passes, and any waivers are explicitly recorded.

### Step 5 — First corpus regeneration

Run `vsd_notebooklm_export.py` to walk `notes/`, compute the inclusion set, copy markdown into `corpus/snapshot-<timestamp>/`, and write `MANIFEST.txt`. Symlink `corpus/current` to the new snapshot. Move to step 6 when `corpus/current/` exists with the seeded files and a valid manifest.

### Step 6 — Wire to NotebookLM

Create a single NotebookLM notebook called "VAPI/VSD master corpus" following the master-corpus pattern. Upload the files from `corpus/current/`. Test the query "Which components of VAPI are emulated?" — the answer should derive from the seeded PBSA note's `honesty_flags.emulated` list. Test the query "What attack closed the canonical-name mismatch?" — the answer should derive from the Stream J adversarial note. Test the query "What is VAPI's current AIT separation ratio?" — the answer should derive from the eigenspace note. Move to step 7 when NotebookLM correctly cites the seeded notes for these three queries.

### Step 7 — First synthesis cycle

With everything wired, execute the synthesis loop from `orchestrator/SKILL.md`. Pick one open question — for example, "Which industries beyond competitive gaming have the strongest case for VAPI primitive applicability given current empirical anchors?" — pull ingredients, draft claims, write a synthesis note, run the harness, commit, and update `MEMORY.md`. Produce the canonical purpose synthesis note `s-purpose-of-vapi.md` as a deliverable of this cycle, structured around the four sub-questions (what problem competitive gaming has, what makes VAPI's approach structural rather than incremental, which adjacent industries inherit which subsets of value, what VAPI is not for). The vault is now operating under VSD.

### Benchmarks that would change these recommendations

If after one synthesis cycle the harness-check overhead exceeds approximately 10% of synthesis time, reduce invariants to the minimum set {1, 2, 3, 4, 9, 10, 13, 14}. If NotebookLM fails to surface honesty-first flags in queries, promote the `Provenance:` header to two lines (separate confidence and provenance lines). If the architect Ed25519 key is rotated, the deployer-anchored signing chain requires a new bootstrap signature from the bridge wallet, and a re-freeze ceremony for `eval/FROZEN.md` documenting the rotation. If a future overnight harness-driven self-improvement loop is added (analogous to MindStudio's reported 30–50 cycles pushing prompt pass rates from 40–50% to 75–85%), the editable orchestrator itself becomes an autoresearch target — explicitly v1.1+, not v1.0.

---

## 12. VSDIP Process (F3, promoted to v1.0 bootstrap)

Future evolutions of VSD are tracked as numbered VSDIP proposals — VSD Improvement Proposals — mirroring the IoTeX IIP and Ethereum EIP lifecycles. Any change to `eval/` ships as a numbered VSDIP. The proposal repository becomes a parallel deployer-signed artifact alongside the protocol's contract registry, giving the methodology its own audit trail rather than treating it as ambient project hygiene.

VSDIP-0001 is this document. VSDIP-0002 is reserved for the v1.1 work to implement the Python harness fully. VSDIP-0003 is reserved for any post-bootstrap discovery that requires invariant adjustment. The lifecycle states are draft, review, frozen, superseded — compressed from EIP-1's longer lifecycle because the VSD process serves a single architect, not a multi-stakeholder community.

---

## 13. Caveats

The Python harness is aspirational at v1.0. The markdown invariants in `eval/INVARIANTS.md` are normative and human-checkable now; the Python checks ship as function signatures with `pass` bodies. This is honest about current state — the harness is real as discipline, partial as automation. Programmatic enforcement is a v1.1 task tracked as VSDIP-0002.

Single-architect discipline is assumed. VSD assumes one architect, one bridge wallet, one signing key. Multi-author VAPI, if it ever exists, would require extending the deployer-anchored model to a multi-sig — the methodology does not preclude this, but v1.0 does not specify it.

Obsidian compatibility is preserved but not load-bearing. YAML frontmatter renders as Properties in Obsidian 1.4+; the vault opens as a normal Obsidian vault. But VSD's correctness does not depend on any Obsidian plugin. If Obsidian disappears tomorrow, the vault remains valid plain markdown plus signed JSON manifests.

NotebookLM is a moving target. Source caps, audio support, Gemini integration, and ingestion behavior change frequently. The corpus pipeline is intentionally simple — markdown files plus a manifest text file — so it survives most NotebookLM changes. If NotebookLM begins natively understanding YAML frontmatter, the `Provenance:` header promotion can be removed. The documented clinical-AI failure modes where NotebookLM occasionally generates outputs unsupported by sources or miscounts sources are addressed by VSD-INV-11: the corpus is a harness-derived projection, so any spurious NotebookLM claim can be rebutted by pointing to the `MANIFEST.txt`.

C2PA mapping is structural, not literal. VSD uses C2PA's architecture (manifest plus hard binding plus ingredient chain plus active manifest) but does not produce C2PA-conformant manifests. Manifests are JSON, not JUMBF/CBOR; signatures are detached Ed25519, not COSE_Sign1; trust anchor is a single architect key, not an X.509 trust list. Calling VSD manifests "C2PA-style" is honest; calling them C2PA-conformant would not be.

Novelty claims require ongoing defense. The novelty analysis in §10 is a snapshot at v1.0 freeze date. As new prior art emerges — particularly future Karpathy autoresearch derivatives or new content-provenance schemes for text — the architect must update `notes/decision/` with the comparison. Novelty is not a property; it is a discipline.

The methodology is bootstrapped by itself. This very specification is, by VSD's own rules, a synthesis note (`s-vsd-methodology-spec-v1`) with ingredients (Karpathy autoresearch repository and program.md verbatim text; C2PA Technical Specification §2.3.7 and §8.1; Andy Matuschak's notes.andymatuschak.org evergreen-notes entries; Maggie Appleton's "Epistemic Disclosure" and "A Brief History & Ethos of the Digital Garden" essays; Gwern's gwern.net/about confidence-tags section and the Kesselman estimative-words list; EIP-1 and IoTeX IIP-1; RO-Crate 1.1 and PROV-O specifications; Elicit's PRISMA 2020 documentation; Steven Johnson's NotebookLM master-corpus tip; Kirill Krainov's coding-skill autoresearch port and MindStudio's prompt-quality autoresearch port; the VAPI state assessment of 2026-05-10; the VAPI Phase O1-FRR-PARALLEL ship documentation including Stream J latent-bug findings) and a hard-binding manifest. Bootstrapping the vault is the act of moving this document into `notes/synthesis/` and signing its manifest. There is no chicken-and-egg problem; there is simply Step 4 of the bootstrap sequence.

The protocol's ship cadence is fast enough that examples cited in this specification may go stale before bootstrap completes. The 2026-05-10 state assessment was canonical for less than 24 hours before the FRR ship and Stream J landed. The right response is to treat the methodology specification itself the same way the protocol treats FROZEN-v1 primitives: freeze the structure, allow the examples to be replaced. The PBSA exemplar pointer in step 4 of bootstrap reads "the most recent state assessment in the protocol repository at bootstrap time" rather than naming a specific dated document. This is a small wording choice that makes the methodology robust against the cadence.

---

## 14. Cross-References

Within VAPI protocol documentation: `Whitepaperv4.md`, `VAPI_INVARIANTS.md`, `VAPI_BIOMETRIC_PRIVACY.md`, `VAPI_CORPUS.md`, `VAPI_CONTEXT.md`, `VAPI_AGENTS.md`, `VAPI_WHAT_IF.md`, `vapi_state_assessment_2026_05_10.md`, `PHASE_O0_DESIGN_PASS_2C.md`, `PHASE_237_ZK_SEPPROOF_VERIFICATION.md`, `vapi_autoresearch.py`, `vapi_eval_harness.py`.

External prior art at v1.0 freeze date: `github.com/karpathy/autoresearch` and `program.md` therein; `spec.c2pa.org` Technical Specification 1.0 and 2.0; `notes.andymatuschak.org` Evergreen notes entries; `maggieappleton.com/garden-history` and "Epistemic Disclosure"; `gwern.net/about` confidence-tags scheme; `eips.ethereum.org/EIPS/eip-1`; `github.com/iotexproject/iips`; RO-Crate 1.1 specification; W3C PROV-O specification; `elicit.com` PRISMA 2020 documentation; Steven Johnson NotebookLM master-corpus practice on x.com/stevenbjohnson; Kirill Krainov "Karpathy's Autoresearch: Improving Agentic Coding Skills" on zerocopy.blog; MindStudio "How to Use Claude Code with AutoResearch to Build Self-Improving AI Skills".

---

## 15. Document Metadata

**Document version:** 1.0 FINAL
**Generated:** 2026-05-10
**Supersedes:** v0.1 draft (2026-05-10 AM)
**Next refresh:** Driven by VSDIP process; no scheduled refresh
**Author authority:** VAPI Architect, sole deployer (`0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692`)
**Tags:** #vsd #methodology #vapi #frozen-v1-candidate #notebook-llm-corpus #verification-first #honesty-first
