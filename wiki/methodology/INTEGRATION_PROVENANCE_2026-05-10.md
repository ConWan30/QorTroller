---
title: "VBDIP-0001 Integration Provenance Manifest — 2026-05-10"
date: 2026-05-10
type: integration_witness
status: pending_operator_review
purpose: deferral_boundary_witness
authority: VAPI Architect (bridge wallet 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692)
relates_to: VBDIP-0001-vad-framework-introduction.md
relates_to_phase: Phase O1-VSD-BOOTSTRAP (pre-execution integration)
---

# VBDIP-0001 Integration Provenance Manifest

> **What this document is.** The forensic witness for the resumption of
> VBDIP-0001 integration from its 2026-05-10 deferral boundary. It captures
> SHA-256 hashes of every methodology artifact at its source location at the
> moment integration resumed, plus the Phase A V-check drift findings, the
> state delta since artifact authoring, and the explicit known gaps.
>
> **Why it exists.** VBD-INV-1 (continuous deployer-verified provenance
> under fleet expansion) is recursively self-applied to VBDIP-0001's own
> integration. This manifest converts the integration from a narrative claim
> ("we resumed from the architectural-collaboration thread artifacts") into
> a mechanically verifiable claim ("compute SHA-256 of file X; compare to
> the entry below").
>
> **Authority.** The hashes recorded here are the authoritative starting
> state for all subsequent integration work (Steps 2-5 per the secure
> resumption procedure). Any artifact whose tree-state hash diverges from
> the post-Step-2 hash recorded below has either been edited (intended,
> via Step 3 amendments — recorded in a follow-up hash block) or corrupted
> (unintended, requires investigation before further integration).

---

## 1. Deferral Context

The architectural collaboration thread of 2026-05-10 produced six
methodology artifacts intended as the canonical methodology surface for
VAPI's evolution from the Verified Synthesis Discipline (VSD) to the VAPI
Architectural Discipline (VAD). Authoring concluded the same day and the
artifacts were saved out to local disk. **Integration into the repository
tree was deferred** — the artifacts existed in mixed locations (some at
`wiki/methodology/`, some only in `C:\Users\Contr\Downloads\`, some with
duplicate-download filename suffixes, one absent entirely) but had not
been frozen, hash-anchored, or provenance-attested as a coherent set.

While the integration was deferred, the protocol itself continued to
ship. Six atomic commits landed on `origin/main` between 2026-05-10
methodology authoring and 2026-05-10 integration resumption (same date;
sub-day commit cadence):

| Commit | Phase |
|--------|-------|
| `f7d21bcf` | Phase O1-FRR-SDK-LOCK NOTE (CLAUDE.md update) |
| `4afcac8d` | Phase O1-FRR-SDK-LOCK ship (PV-CI invariants pin SDK + UI drawer layout) |
| `db195b2d` | Phase O1-FRR-SDK NOTE |
| `0076082b` | Phase O1-FRR-SDK ship (VAPIFleetReadinessRoot SDK client) |
| `f137ded6` | Phase O3-READINESS-DASHBOARD NOTE |
| `8fecfcd7` | Phase O3-READINESS-DASHBOARD ship |
| `c46e04cb` | Phase O2-DRAFT-REVIEW-FRONTEND NOTE |
| `3d5923e7` | Phase O2-DRAFT-REVIEW-FRONTEND ship |
| `af42c91d` | Phase O2-GUARDIAN-CURATOR-TRIGGERS-ARC NOTE (consolidated) |
| `32997d18` | Phase O2-CURATOR-TRIGGERS ship |
| `3238c68f` | Phase O2-GUARDIAN-TRIGGERS ship |
| `73e70838` | Phase O2-GUARDIAN-CURATOR-TRIGGERS-PRELUDE |
| `3eede644` | Phase O2-GIT-TRIGGER-AUTOWIRE |

State delta (authoring → integration boundary):

- Bridge tests: **2836 → 2922** (+86)
- PV-CI invariants: **55 → 63** (+8)
- HEAD commit at integration resumption: **`f7d21bcf`**

This delta is the empirical justification for Phase B amendment work to
the bootstrap canonical and master resumption prompt.

**Integration resumption authorized:** 2026-05-10, by operator
acknowledgment of the recommended five-step secure procedure (Provenance
Pin → Inventory Normalization → State Reconciliation Amendments →
Architect Key + Attestation → VBDIP-0001 Freeze).

---

## 2. Artifact Inventory and Hashes

Six methodology artifacts comprise the canonical VAD methodology surface
per VBDIP-0001 §10 + claude_code_master_resumption_prompt.md Phase A. The
table below captures each artifact's source location, intended tree
location, SHA-256 content hash, line count, and integration disposition.

| # | Artifact | Source Path | Intended Tree Path | SHA-256 (32B) | Lines | Disposition |
|---|----------|-------------|-------------------|---------------|-------|-------------|
| 1 | VSD v1.0 FINAL | `C:\Users\Contr\Downloads\vsd_methodology_v1_FINAL.md` | `wiki/methodology/vsd_methodology_v1_FINAL.md` | `c5a38a2bb1fb3bd8e4eb3e188724b46fea79579b3d81083b61cd38f534d263ca` | 619 | Step 2: import |
| 2 | VSD Volume 2 FINAL | `wiki/methodology/vsd_volume_2_final.md` (already in tree) | `wiki/methodology/vsd_volume_2_final.md` | `c746bcb7be7fbba94a6a5f338f8c8fbe8ee7bad3fb58650b491229f214278e13` | 1102 | In tree; no move |
| 3 | Phase O1-VSD-BOOTSTRAP canonical execution prompt | `wiki/methodology/phase_o1_vsd_bootstrap_canonical.md` (already in tree) | `wiki/methodology/phase_o1_vsd_bootstrap_canonical.md` | `a685b8f0b6a149f57eff9f7a8b6b09ab1db894cdc234dc43955084ec07842be3` | 418 | In tree; no move |
| 4 | NotebookLM session prompt | **NOT LOCATED** | `wiki/methodology/notebooklm_session_prompt.md` | `(absent)` | `(absent)` | **MISSING-ARTIFACT-001** — see §5 |
| 5 | VBDIP-0001 VAD framework introduction draft | `wiki/methodology/VBDIP-0001-vad-framework-introduction (1).md` (in tree, suffixed) | `wiki/methodology/VBDIP-0001-vad-framework-introduction.md` (no suffix) | `50754b93bdf95ad5b92d51cbab8e5064e9286576ba175f725253a75a7a3e4315` | 351 | Step 2: `git mv` to drop suffix |
| 6 | Master resumption prompt | `C:\Users\Contr\Downloads\claude_code_master_resumption_prompt.md` | `wiki/methodology/claude_code_master_resumption_prompt.md` | `e3c97e350003efa7332f706d6c5d139d59a4671ee74f6111d7ecc930de83d97d` | 152 | Step 2: import |

**Hash verification commands** (any future operator can reproduce):

```bash
# Pre-Step-2 source hashes (current state of this manifest):
sha256sum "C:/Users/Contr/Downloads/vsd_methodology_v1_FINAL.md"                                  # → c5a38a2bb1fb...263ca
sha256sum "wiki/methodology/vsd_volume_2_final.md"                                                 # → c746bcb7be7f...278e13
sha256sum "wiki/methodology/phase_o1_vsd_bootstrap_canonical.md"                                   # → a685b8f0b6a1...842be3
sha256sum "wiki/methodology/VBDIP-0001-vad-framework-introduction (1).md"                          # → 50754b93bdf9...a74315
sha256sum "C:/Users/Contr/Downloads/claude_code_master_resumption_prompt.md"                       # → e3c97e350003...e83d97d

# Post-Step-2 tree hashes (will be recorded as a Step-2 hash-block append below):
sha256sum "wiki/methodology/vsd_methodology_v1_FINAL.md"                                           # MUST equal c5a38a2bb1fb...263ca
sha256sum "wiki/methodology/VBDIP-0001-vad-framework-introduction.md"                              # MUST equal 50754b93bdf9...a74315
sha256sum "wiki/methodology/claude_code_master_resumption_prompt.md"                               # MUST equal e3c97e350003...e83d97d
```

The pre/post-Step-2 hash equality is the byte-preservation invariant: a
`git mv` and a copy from outside the tree must not alter content. Any
divergence is a Step 2 STOP condition.

### 2.1 Note on the VBDIP-0001 duplicate-download artifact

Three byte-identical copies of VBDIP-0001 exist on disk:

```
50754b93bdf95ad5b92d51cbab8e5064e9286576ba175f725253a75a7a3e4315  wiki/methodology/VBDIP-0001-vad-framework-introduction (1).md
50754b93bdf95ad5b92d51cbab8e5064e9286576ba175f725253a75a7a3e4315  C:/Users/Contr/Downloads/VBDIP-0001-vad-framework-introduction.md
50754b93bdf95ad5b92d51cbab8e5064e9286576ba175f725253a75a7a3e4315  C:/Users/Contr/Downloads/VBDIP-0001-vad-framework-introduction (1).md
```

The `" (1)"` suffix is a Windows browser duplicate-download artifact —
zero semantic content difference. The in-tree filename inherits the
suffix from the original copy operation. Step 2 normalizes via `git mv`
to the canonical no-suffix form.

VBDIP-0001's own metadata at line 10 declares its eventual canonical
save path as `vsd-vault/proposals/VBDIP-0001-vad-framework-introduction.md`,
NOT `wiki/methodology/`. The current `wiki/methodology/` placement is a
**pre-bootstrap staging location**. The final move to `vsd-vault/proposals/`
happens during Phase O1-VSD-BOOTSTRAP Stream A when the vault skeleton is
created. Step 2 of this integration leaves it in `wiki/methodology/` with
the corrected filename; the eventual move is bootstrap-Stream-A scope.

---

## 3. Phase A V-Check Drift Findings (Verbatim)

The Phase A read-only state reconciliation produced 9 V-check DRIFT
findings and 1 PASS against the master resumption prompt's V-A1..V-A10
specifications. They are recorded here verbatim for forensic continuity.

| V-check | Required outcome | Actual | Status |
|---------|------------------|--------|--------|
| V-A1 | bootstrap-prompt protocol state matches CLAUDE.md | Bootstrap doc references state at Phase O1-FRR-PARALLEL ship; CLAUDE.md head is Phase O1-FRR-SDK-LOCK (6 ships later same day) | **DRIFT** |
| V-A2 | wallet ≥ 15.0 IOTX | ~15.44 IOTX per CLAUDE.md (not live-queried; chain RPC not exercised this session per kill-switch posture) | **PASS-by-memory** (not chain-verified) |
| V-A3 | 49 contracts matches deployed-addresses.json | 51 contract address entries in file; CLAUDE.md asserts 49 LIVE | **DRIFT — 2 entry discrepancy** |
| V-A4 | bootstrap-prompt PV-CI 55 matches current | Current: 63 entries | **DRIFT — +8 invariants** |
| V-A5 | PATTERN-017 count 9 pre-bootstrap | CLAUDE.md memory: 7 LIVE (excludes PoAC + FRR); State Assessment §2.3: 9 (PoAC as #1; FRR as #9); Volume 2 §17 + §19.1 hedges "ninth-actually-tenth" for VRR; VBDIP-0001 §7 asserts 11 total post-bootstrap | **DRIFT — three sources count three different ways; this IS the Phase B Amendment #1 target** |
| V-A6 | bridge tests 2836 ± 20 | Current: 2922 (delta +86, well outside ±20) | **DRIFT — +86** |
| V-A7 | methodology doc supersession check | `phase_o1_vsd_bootstrap_canonical.md` exists in tree (not `…_prompt.md` as resumption prompt names); v1.0 FINAL + NotebookLM session prompt + resumption prompt itself NOT in tree | **DRIFT — three of six canonical artifacts missing from tree; one filename mismatch** |
| V-A8 | `CHAIN_SUBMISSION_PAUSED=true` | bridge/.env:208 = CHAIN_SUBMISSION_PAUSED=true | **PASS** |
| V-A9 | new phases shipped since thread closure | Six ships since 2026-05-10 same day: O1-FRR-SDK + O1-FRR-SDK-LOCK + O3-READINESS-DASHBOARD + O2-DRAFT-REVIEW-FRONTEND + O2-GUARDIAN-CURATOR-TRIGGERS-ARC + O2-AUTONOMOUS-COMPLETION arc | **DRIFT — six new ships affect bootstrap scope** |
| V-A10 | shadow_age progression | CLAUDE.md cites Sentry/Guardian 152.13h and Curator 6.79h at 2026-05-10. Per state-assessment §2.4 + parallel O2 anchor 2026-05-10 the agents are now at O2_SUGGEST not O1_SHADOW; the 152.13h figure was the O2-readiness shadow_age at moment of O2 anchor, not a current advancing clock toward O3 | **DRIFT — bootstrap doc refers to O1_SHADOW shadow_age but agents elevated to O2_SUGGEST same day** |

**V-check pass rate: 1 of 10 PASS (V-A8). Nine DRIFT findings.**

The high drift count is expected and not blocking — it reflects the
6-commit protocol-side delta that landed between methodology authoring
and integration resumption. The drift findings drive the Phase B
amendment scope (Step 3 of secure resumption); they do not invalidate
the methodology artifacts themselves.

---

## 4. Critical Structural Findings

Three findings surfaced during Phase A read-only reconciliation require
explicit resolution before progressing past Step 1.

### Finding 1 — Methodology artifact inventory mismatch

The resumption prompt names six methodology files at `wiki/methodology/`.
Three are absent from the tree (one is absent entirely from on-disk
sources). One has a duplicate-download suffix. The on-tree bootstrap is
named `_canonical.md`, not `_prompt.md` as the resumption prompt asserts.

**Disposition:** Step 2 imports the located absent files and renames
VBDIP-0001 to drop the suffix. Step 3 amendments correct the filename
reference in claude_code_master_resumption_prompt.md (Phase D) and any
cross-references in VBDIP-0001 §10 that name `_prompt.md`.

### Finding 2 — PATTERN-017 family count is unreconciled

Four load-bearing documents count the FROZEN-v1 cryptographic primitive
family differently:

- **CLAUDE.md memory header:** "Seven FROZEN-v1 cryptographic primitives
  LIVE (PATTERN-017): GIC + WEC + VAME + CORPUS-SNAPSHOT + CONSENT +
  BIOMETRIC-SNAPSHOT + LISTING-v1." — excludes PoAC; treats FRR as not
  yet LIVE (despite Phase O1-FRR-PARALLEL having shipped commit
  `4ddeb43c`).
- **State Assessment §2.3 table:** 9 entries (PoAC as #1, GIC as #2, ...,
  FRR as #9 "this ship").
- **Volume 2 §17:** "VRR (Vault Readiness Root) as the ninth FROZEN-v1
  cryptographic primitive in the PATTERN-017 family." §19.1 internally
  hedges: "ninth-actually-tenth in PATTERN-017."
- **VBDIP-0001 §7:** "PATTERN-017 cryptographic primitive family count
  remains at eleven (the eight pre-Volume-2 primitives plus FRR, VRR,
  CDRR)." — implies pre-V2 count is 8.

**Recommended canonical convention** (Step 3 Amendment #1 target):
adopt the State Assessment §2.3 convention. PoAC is #1 (the founding
member of the family). Post-FRR LIVE count = 9. Post-bootstrap (when
VRR + CDRR ship) = 11. Reconcile by updating four documents in the same
Step 3 commit:

1. CLAUDE.md memory header: revise from "Seven FROZEN-v1 ... LIVE
   (PATTERN-017)" to "Nine FROZEN-v1 cryptographic primitives LIVE
   (PATTERN-017): PoAC + GIC + WEC + VAME + CORPUS-SNAPSHOT + CONSENT
   + BIOMETRIC-SNAPSHOT + LISTING-v1 + FRR. Eleven total at Phase
   O1-VSD-BOOTSTRAP completion (+ VRR + CDRR)."
2. State Assessment §2.3 — already correct; preserve as canonical reference.
3. Volume 2 §17 + §19.1 — drop the "ninth-actually-tenth" hedge; assert
   "VRR is the tenth FROZEN-v1 primitive" cleanly.
4. VBDIP-0001 §7 — revise from "eleven (eight pre-Volume-2 + FRR + VRR
   + CDRR)" to "eleven (nine pre-bootstrap PoAC..FRR + VRR + CDRR);
   nine pre-VBDIP-0001-freeze".

This is itself a VBD-INV-3 (primitive composition discipline) self-
application — the methodology discipline applied to the methodology's
own count drift. The four-document reconciliation in one Step 3 atomic
commit prevents future drift recurrence.

### Finding 3 — Contract address count mismatch

`contracts/deployed-addresses.json` contains 51 contract address entries.
CLAUDE.md asserts "49 contracts ALL LIVE." The 2-entry gap is likely
legacy contracts (TournamentGate v1, possibly one other early version)
that are deployed but no longer counted as "live infrastructure".

**Disposition:** Not bootstrap-blocking. Recommend addressed during
Step 3 either by (a) explicit reconciliation of CLAUDE.md to "51 LIVE",
(b) annotation of `_legacy_superseded` keys in deployed-addresses.json
naming the two superseded contracts, or (c) deferral to a follow-up
maintenance commit. Operator judgment on which option.

### MISSING-ARTIFACT-001 — NotebookLM session prompt absent

`notebooklm_session_prompt.md` is referenced in:

- VBDIP-0001 §10 cross-references (as "the NotebookLM session contract")
- claude_code_master_resumption_prompt.md Phase A (as the fourth of the
  five canonical methodology artifacts to read alongside VBDIP-0001)
- claude_code_master_resumption_prompt.md "Pre-Paste Operational
  Checklist" (as a precondition file that must be saved at the named
  path before pasting the resumption prompt)

The file exists at no on-disk location reachable from this session:
- ❌ `wiki/methodology/notebooklm_session_prompt.md` — absent
- ❌ `C:/Users/Contr/Downloads/notebooklm_session_prompt.md` — absent
- ❌ Broader `C:/Users/Contr/` recursive search (max-depth 3) — absent

Three resolution options for operator decision before Step 2 begins:

- **Option M1** — Author/locate the NotebookLM session prompt from
  architectural-collaboration-thread artifacts; manifest amended with
  hash + line count post-location; integration proceeds with all six
  artifacts present.
- **Option M2** — Acknowledge as never-shipped; amend resumption prompt
  Phase A and VBDIP-0001 §10 cross-references to remove the artifact
  reference; integration proceeds with five canonical artifacts.
- **Option M3** — Defer to a follow-up phase; manifest captures absence
  as MISSING-ARTIFACT-001; integration proceeds with five of six
  artifacts; resumption prompt and VBDIP-0001 cross-references annotated
  with a "(authoring deferred)" status pending future authoring.

**No automated determination possible** — requires operator authority on
whether the artifact exists, was lost, or was never authored.

---

## 5. State Snapshot at Integration Boundary

For forensic completeness, the protocol-state values asserted as
authoritative at integration resumption.

| Dimension | Value | Source |
|-----------|-------|--------|
| HEAD commit | `f7d21bcf` | `git rev-parse HEAD` |
| Branch | `main` | `git rev-parse --abbrev-ref HEAD` |
| Phase | Phase O1-FRR-SDK-LOCK COMPLETE 2026-05-10 | CLAUDE.md header |
| Bridge tests | 2922 (delta) | CLAUDE.md |
| SDK tests | 548 | CLAUDE.md |
| Hardhat tests | 528 | CLAUDE.md |
| Contracts (LIVE per CLAUDE.md / entries in deployed-addresses.json) | 49 / 51 | CLAUDE.md vs file |
| PV-CI invariants | 63 | INVARIANTS_ALLOWLIST.json (counted) |
| Operator agent fleet (Sentry/Guardian/Curator) | All at O2_SUGGEST | CLAUDE.md + state assessment §2.4 |
| Wallet balance | ~15.44 IOTX (per CLAUDE.md; not chain-verified this session) | CLAUDE.md |
| Wallet address | `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692` | CLAUDE.md |
| `CHAIN_SUBMISSION_PAUSED` | `true` | bridge/.env:208 |
| FROZEN-v1 primitive count (pending reconciliation) | 7 LIVE per memory / 9 LIVE per state assessment | Finding 2 |

This snapshot is the authoritative pre-integration state. Subsequent
integration steps may amend memory headers and state assertions in the
methodology documents (Step 3 Amendments) but do not modify the
protocol-side artifacts (CLAUDE.md, deployed-addresses.json,
INVARIANTS_ALLOWLIST.json, bridge code, contracts) at any of Steps 1-5.

The Phase B amendments target methodology *draft documents only* —
filling them with current authoritative state values rather than the
authoring-time values they were authored against. This is the
"no in-place amendments to FROZEN documents" discipline applied
correctly: the FROZEN documents (v1.0 FINAL, Volume 2 FINAL) are not
amended; the still-draft documents (VBDIP-0001 FROZEN-candidate,
master resumption prompt, bootstrap canonical pre-execution) are.

---

## 6. Hash Reproduction Procedure

Any future operator (architect themselves, post-rotation successor, or
external auditor with read access to this repository) can verify the
provenance recorded in this manifest:

1. Check out the commit that lands this manifest (Step 1 atomic commit).
   This commit's parent is `f7d21bcf` per §1.
2. Run `sha256sum` against each artifact at the source path listed in §2
   table column 3. The output must equal the SHA-256 in column 5.
3. After Step 2 atomic commit lands, run `sha256sum` against each
   artifact at the *intended tree path* (column 4). Output must equal
   the SHA-256 in column 5 (byte-preservation invariant).
4. Step 3 amendments will produce new hashes for the amended documents.
   Those post-amendment hashes will be recorded in a Step-3 hash-block
   appended to this manifest (§7 placeholder below).

If any verification step fails:
- **Pre-Step-2 hash mismatch:** the source artifact has been edited or
  corrupted between manifest authoring and verification. STOP and
  investigate.
- **Step-2 byte-preservation violation:** `git mv` or copy operation
  altered content. STOP and revert Step 2 commit.
- **Step-3 post-amendment hash divergence from Step-3 manifest entry:**
  amendment landed but produced different bytes than recorded. STOP and
  investigate the amendment commit.

---

## 7. Hash Block Appendix (Append-Only)

Subsequent integration steps append hash blocks here. Each block records
the artifact hashes at that step's atomic commit boundary, providing a
chain of byte-state snapshots from deferral boundary through integration
completion.

### 7.1 Step 1 — Provenance Pin (this commit)

Hashes match §2 table. This commit lands the manifest as the deferral-
boundary witness; no other artifacts move.

### 7.2 Step 2 — Inventory Normalization (landed)

Step 2 atomic commit applied 2026-05-10. The byte-preservation invariant
(pre-operation hashes equal post-operation hashes) is satisfied for all
five methodology .md files brought under version control. The PDF
artifact (`DualSense Edge Sensor-Stack Characterization for VAPI Track-1
Anti-Cheat Feature Architecture.pdf`) remains untracked at Step 2 close;
binary inclusion is deferred to a separate operator decision.

Post-operation hashes:

| File | Hash | Operation |
|------|------|-----------|
| `wiki/methodology/VBDIP-0001-vad-framework-introduction.md` | `50754b93bdf95ad5b92d51cbab8e5064e9286576ba175f725253a75a7a3e4315` | rename (drop `" (1)"` suffix); byte-identical to source |
| `wiki/methodology/vsd_methodology_v1_FINAL.md` | `c5a38a2bb1fb3bd8e4eb3e188724b46fea79579b3d81083b61cd38f534d263ca` | import from Downloads; byte-identical to source |
| `wiki/methodology/claude_code_master_resumption_prompt.md` | `e3c97e350003efa7332f706d6c5d139d59a4671ee74f6111d7ecc930de83d97d` | import from Downloads; byte-identical to source |
| `wiki/methodology/vsd_volume_2_final.md` | `c746bcb7be7fbba94a6a5f338f8c8fbe8ee7bad3fb58650b491229f214278e13` | scope expansion: pre-existing on filesystem but untracked; added in Step 2 as inventory normalization |
| `wiki/methodology/phase_o1_vsd_bootstrap_canonical.md` | `a685b8f0b6a149f57eff9f7a8b6b09ab1db894cdc234dc43955084ec07842be3` | scope expansion: pre-existing on filesystem but untracked; added in Step 2 as inventory normalization |

Scope expansion rationale: Step 2's literal name "Inventory Normalization"
implies all methodology .md artifacts referenced by the deferral-boundary
manifest §2 inventory should be reconciled to canonical git-tracked state.
The §2 inventory marked `vsd_volume_2_final.md` and
`phase_o1_vsd_bootstrap_canonical.md` as "In tree; no move" — meaning
filesystem-present, but git-tracking was not verified at manifest authoring.
Step 2 closes that gap by `git add`-ing both alongside the 3 originally
scoped operations. The PDF artifact is deferred pending binary-inclusion
operator decision.

MISSING-ARTIFACT-001 disposition: **M3** (defer as named open item per
operator decision recorded in VBDIP-0001 Step 1 commit body
`2aea877a`). `notebooklm_session_prompt.md` remains absent from all
on-disk locations; Step 3 amendments may resolve via N2-class rename
or cross-reference removal in the resumption prompt + VBDIP-0001 §10.

Step 2 commit references this manifest hash block; future readers may
verify byte preservation by recomputing SHA-256 of each file at the Step
2 commit SHA and comparing against this table.

### 7.3 Step 3 — Phase B State Reconciliation Amendments (landed)

Step 3 atomic commit applied 2026-05-10. Four amendments applied across
five files (Amendment #1 cascades to 4 documents per Finding 2 in §4 of
this manifest).

Amendment summary:

| # | Target | Section | Change |
|---|--------|---------|--------|
| **#1** | `wiki/methodology/VBDIP-0001-vad-framework-introduction.md` | §7 | PATTERN-017 count canonicalized: 12 post-bootstrap (10 pre-bootstrap including ZKBA + VRR + CDRR). Canonical convention defined explicitly (PoAC=1 ... ZKBA=10, VRR=11, CDRR=12); EXCLUDES parser-schema tags + Pass 2C op-track primitives. |
| **#1** | `wiki/methodology/VBDIP-0001-vad-framework-introduction.md` | §5.1 | FRR position annotated as #9; ZKBA as #10 |
| **#1** | `wiki/methodology/VBDIP-0001-vad-framework-introduction.md` | §5.2 | CDRR position annotated as #12 (was "eleventh"); ZKBA insertion explained |
| **#1** | `wiki/methodology/vsd_volume_2_final.md` | §17 | VRR position revised from "ninth" to "eleventh" with cross-reference to VBDIP-0001 §7 canonical convention |
| **#1** | `wiki/methodology/vsd_volume_2_final.md` | §19.1 | "ninth-actually-tenth" hedge dropped; FRR explicitly positioned at #9; full sequence enumerated |
| **#1** | `wiki/assessments/vapi_state_assessment_2026_05_10.md` | §2.3 | Table row #10 added for ZKBA-ARTIFACT (Phase O3-ZKBA-TRACK1 C2 ship); FRR row "THIS SHIP" marker removed (now historical) |
| **#2** | `wiki/methodology/VBDIP-0001-vad-framework-introduction.md` | §5.1 | VED-INV-N clarified as methodology-doc count-abstraction NOT allowlist rename; existing INV-* IDs in allowlist preserved |
| **#3** | `wiki/methodology/claude_code_master_resumption_prompt.md` | Phase D | Recommendation revised from Option D1 to **Option D2** with full rationale (D2 = freeze VBDIP-0001 before bootstrap; avoids in-place amendment of saved bootstrap prompt; cleanest audit trail) |
| **#4** | `wiki/methodology/phase_o1_vsd_bootstrap_canonical.md` | §1 | State references refreshed: bridge tests 2836 → 2922 (+86); PV-CI invariants 55 → 63 (+8); 9 → 10 FROZEN-v1 primitives shipped post-Phase-O3-ZKBA-TRACK1 C2; commits 3df5e59f + 625007ab + 2aea877a + 69ac74d2 cross-referenced |

Post-amendment hashes:

| File | Pre-Step-3 Hash | Post-Step-3 Hash |
|------|-----------------|------------------|
| `wiki/methodology/VBDIP-0001-vad-framework-introduction.md` | `50754b93bdf95ad5b92d51cbab8e5064e9286576ba175f725253a75a7a3e4315` | `83d9266350c3d38c83647fbeffcb0f297f3f03b809fde7c55973d245d3cac6f9` |
| `wiki/methodology/vsd_volume_2_final.md` | `c746bcb7be7fbba94a6a5f338f8c8fbe8ee7bad3fb58650b491229f214278e13` | `44406f7838ec3ba967cde74585aa6ebad2c140551692618654ffcf10c64bbda9` |
| `wiki/assessments/vapi_state_assessment_2026_05_10.md` | (Step 1 baseline, not Step 2 inventory; was already in tree pre-Step-1 — see Phase A §2 inventory) | `fb6d894720852502f57eec68cc713aa5ac673b6662151116f2f680d1e045613f` |
| `wiki/methodology/claude_code_master_resumption_prompt.md` | `e3c97e350003efa7332f706d6c5d139d59a4671ee74f6111d7ecc930de83d97d` | `8df38969a42399a89ea402e59d18625227f38ef666c4b5d83c9810e8cec7553c` |
| `wiki/methodology/phase_o1_vsd_bootstrap_canonical.md` | `a685b8f0b6a149f57eff9f7a8b6b09ab1db894cdc234dc43955084ec07842be3` | `cddc9784d61358ed791946de901da051fb209d3f89129dcec3bfb7a375fa2dd1` |

Canonical PATTERN-017 family count convention (Amendment #1 codification):

> PATTERN-017 family = SHA-256 commitment primitives with explicit or
> implicit domain separation used as VAPI's chain-anchored proof
> commitment family. Convention INCLUDES: PoAC (#1, implicit slice
> [0:164]), GIC (#2, b"VAPI-GIC-GENESIS-v1"), WEC (#3,
> b"VAPI-WEC-GENESIS-v1"), VAME (#4, b"VAPI-VAME-v1"), CORPUS-SNAPSHOT
> (#5, b"VAPI-CORPUS-SNAPSHOT-v1"), CONSENT (#6, b"VAPI-CONSENT-v1"),
> BIOMETRIC-SNAPSHOT (#7, b"VAPI-BIOMETRIC-SNAPSHOT-v1"), LISTING-v1 (#8,
> b"VAPI-LISTING-v1"), FRR (#9, b"VAPI-FRR-v1"), ZKBA-ARTIFACT (#10,
> b"VAPI-ZKBA-ARTIFACT-v1"). Post-bootstrap additions: VRR (#11), CDRR
> (#12). EXCLUDES: CEDAR-BUNDLE-v1 (parser schema, not chain commitment),
> AGENT-COMMIT-v1 + PHYSICAL-DATA-ATTESTATION-v1 (Pass 2C operator-track
> primitives forming a distinct lineage).

Pre-bootstrap count: 10 shipped. Post-bootstrap count: 12 shipped.

CLAUDE.md NOTE entries are historical-phase records and are NOT amended
in Step 3 (the "no in-place amendments to historical records" discipline
preserves the phase-boundary witness pattern). Current state assertions
for CLAUDE.md happen in Z9 sync of PLAN-VBDIP-0002-ZKBA-PARALLEL-v1.

### 7.4 Step 4 — Architect Key + Bridge Wallet Attestation (landed)

Step 4 atomic commit applied 2026-05-10. Deployer-anchored signing chain
established per VBD-INV-1 (continuous deployer-verified provenance).
Architect Ed25519 private key remains LOCAL ONLY (gitignored via
`vsd-vault/.gitignore`); architect public key + signature attestation
committed to canonical tree.

| Field | Value |
|-------|-------|
| Architect Ed25519 public key (32B raw hex) | `056e695f2995070198a0db1a6c264d8234fb88bf5cf6332c354f58a096a78ca8` |
| SHA-256 of architect public key bytes | `5f37e4322db987ce5b97f11e622eef88f5611caa0d58cbe492c83df1ea860e96` |
| Bridge wallet address (signer) | `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692` |
| Recovered address (signature verification) | `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692` (MATCHES expected) |
| Signing method | EIP-191 (`eth_account.Account.sign_message` over canonical JSON envelope) |
| Attestation timestamp (ts_ns, uint64) | `1778468776325676600` |
| Attestation purpose tag (FROZEN at v1.0) | `vsd-architect-key-anchor-v1` |
| Envelope canonical SHA-256 | `ce3f74be4715a2e0f109090d67c2cd99e3776a13148cf70016c5ff5b9dfcdf2d` |
| Attestation file path | `vsd-vault/eval/architect_key_attestation.json` |
| Attestation canonical SHA-256 | `14ad3970d592bd00a8cdc13bc7ff45e4ece209c692b8f7cd7389740992a1307a` |
| Signature (EIP-191; 65 bytes hex with `0x` prefix) | `0xb21a94de29f642f4282366e937d66ab6c92054597a225754ee2b469ecf2b64f867067c75bee2528693816a6bde0033b93346c128f5f21195e5720fc574c673731b` |
| Architect private key file path | `vsd-vault/architect_key.pem` — **GITIGNORED**; NEVER committed |
| Architect public key file path | `vsd-vault/architect_pubkey.pem` — gitignored by root `.gitignore:82 (*.pem)` rule; convenience artifact; pubkey hex is the canonical reference and IS recorded in the attestation JSON committed at the path above |

Security properties (verified post-execution):

- `vsd-vault/architect_key.pem` is gitignored via `vsd-vault/.gitignore` line 12. `git check-ignore` confirms.
- Bridge wallet private key (`BRIDGE_PRIVATE_KEY` in `bridge/.env`) was read once for signing, never echoed, never persisted by the attestation script.
- The attestation envelope is canonical-JSON sorted-key encoded; signature is reproducible by any future verifier who:
  1. Reads the architect pubkey hex from the attestation JSON
  2. Reconstructs the envelope: `{architect_pubkey_ed25519, attested_at_ts_ns, purpose, bridge_wallet_address}` with sorted keys + tight JSON separators
  3. Encodes via EIP-191 (`encode_defunct`)
  4. Calls `Account.recover_message(message, signature)` with the recorded signature
  5. Confirms recovered address equals `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692`

The attestation script (`scripts/vsd_attest_architect_key.py`) is committed alongside the attestation JSON to enable reproducibility from raw inputs.

This signature is the root of the deployer-anchored signing chain. All future architect-Ed25519-signed methodology artifacts inherit trust from this attestation. Any change to the architect key (rotation) requires Procedure-VSD-K1 (defined in `vsd-vault/eval/PROCEDURES.md` once Stream A.5 of Phase O1-VSD-BOOTSTRAP ships VSDIP-0003) and a new attestation with a forward-reference to this one in the rotation chain.

### 7.5 Step 5 — VBDIP-0001 Freeze (landed)

Step 5 atomic commit applied 2026-05-10. VBDIP-0001 transitions from
FROZEN-candidate to **FROZEN** with architect Ed25519 signature applied
to the proposal's canonical content hash; manifest committed; harness
extended; allowlist regenerated; vault README authored.

| Artifact | Hash / Value | Notes |
|----------|--------------|-------|
| `wiki/methodology/VBDIP-0001-vad-framework-introduction.md` | `56da19e2e593396dff10b72cbc5c2a1d1c8a4658eb52de548d0b57829a18ea27` | FROZEN content; byte length 44,518; §11 status transition log records the freeze |
| `vsd-vault/manifests/proposals-VBDIP-0001/001.manifest.json` | `46d786952c9979177afe221180e340577c10b0dbec67b9d6fccb7fc41a7c69e4` | Canonical-JSON; byte length 1,393; embeds architect Ed25519 signature over `proposal_canonical_hash` |
| Architect Ed25519 signature (64B hex) | `ea59071b0640f6fab03507f403bdd618e320ab6bfe3d27951150bcc30a029aca8101f644d882b1e0f152419279434470a03557e0fbff842e49de8a9b5fd6e103` | Signs the 32-byte canonical hash of VBDIP-0001; verified PASS at signing time |
| Architect pubkey (32B hex) | `056e695f2995070198a0db1a6c264d8234fb88bf5cf6332c354f58a096a78ca8` | Matches Step 4 attestation (`architect_key_attestation.json`); deployer-anchored signing chain holds |
| `frozen_at_ts_ns` | `1778469491278228500` | Uint64; recorded in manifest |
| `scripts/vapi_invariant_gate.py` | extended | +VBD_INVARIANTS list (3 entries) + `_select_invariants_for_proposal_type()` + `_parse_proposal_type_arg()` + `--proposal-type` flag (4 choices: protocol / bridge / synthesis / all; `both` preserved as deprecated alias); default `protocol` preserves backward compat |
| `.github/INVARIANTS_ALLOWLIST.json` | 63 → 66 entries | Regenerated via `--generate --proposal-type=all --reason "invariant_change: ..." --confirm-governance`. Governance phrase piped (`I understand this changes a frozen protocol invariant`). Bridge POST failed gracefully (bridge not running; expected per kill-switch posture). |
| `vsd-vault/README.md` | new | Per VBDIP-0001 §6.2 deferred-migration documentation; describes VAD framework, sub-discipline mapping, numbered-proposal lineage, deferred `vsd-vault/` → `vad-vault/` rename via Phase O1-VAD-MIGRATE (gated on VBDIP-0002 numbering resolution N1/N2'/N3). |
| New PV-CI invariants registered | VBD-INV-001, VBD-INV-002, VBD-INV-003 | Markdown-normative; Python check bodies remain stubs at v1.0 per VBDIP-0001 §9 (programmatic enforcement deferred to VBDIP-0003). Each invariant pattern-matches the `check_vbd_inv_N` function signature documented in VBDIP-0001 §4.1/§4.2/§4.3. |
| VBD-INV-4 (retroactive CFSS rename) | reserved | Not registered in this commit. INV-CFSS-001 ships at Phase O1-VSD-BOOTSTRAP Stream B (per VBDIP-0001 §4.4 + Volume 2 §20.1). Retroactive rename applies when CFSS lands; tracked as deferred Step 5 follow-up. |

Bridge gate verification post-Step-5:

| Command | Result |
|---------|--------|
| `python scripts/vapi_invariant_gate.py --proposal-type=protocol --report` | 63 invariants — All pass |
| `python scripts/vapi_invariant_gate.py --proposal-type=bridge --report` | 3 VBD invariants — All pass |
| `python scripts/vapi_invariant_gate.py --proposal-type=all --report` | 66 invariants — All pass |
| `python scripts/vapi_invariant_gate.py --report` (default = protocol; backward compat) | 63 invariants — All pass |

Verification procedure for future readers (replayable from canonical inputs):

```python
import hashlib, json
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

# 1. Read VBDIP-0001 at this commit
vbdip = Path('wiki/methodology/VBDIP-0001-vad-framework-introduction.md').read_bytes()
canonical_hash = hashlib.sha256(vbdip).hexdigest()
assert canonical_hash == '56da19e2e593396dff10b72cbc5c2a1d1c8a4658eb52de548d0b57829a18ea27'

# 2. Read manifest, extract pubkey + signature
manifest = json.loads(Path('vsd-vault/manifests/proposals-VBDIP-0001/001.manifest.json').read_bytes())
assert manifest['proposal_canonical_hash'] == canonical_hash
pk_bytes = bytes.fromhex(manifest['architect_pubkey_ed25519'])
sig_bytes = bytes.fromhex(manifest['signature'])

# 3. Verify Ed25519 signature over canonical hash bytes
Ed25519PublicKey.from_public_bytes(pk_bytes).verify(sig_bytes, bytes.fromhex(canonical_hash))

# 4. Verify architect pubkey chains to bridge wallet via attestation
attestation = json.loads(Path('vsd-vault/eval/architect_key_attestation.json').read_bytes())
assert attestation['envelope']['architect_pubkey_ed25519'] == manifest['architect_pubkey_ed25519']
assert attestation['recovered_address'] == '0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692'
```

VBDIP-0001 is now **FROZEN**. The VAD methodology framework — VSD synthesis + VED engineering + VBD bridge sub-disciplines — is established as the canonical methodology surface. The 5-step secure resumption procedure is complete. VBDIP-0002 Track 2 activation gate #1 (per VBDIP-0002 §16) is now satisfied; the remaining Track 2 gates are operator-decision + wallet-impact gates (numbering resolution; compiler harness implementation; AgentScope/Cedar permissions; Curator review readiness; internal projection first).

---

## 8. Cross-References

- VBDIP-0001 draft: `wiki/methodology/VBDIP-0001-vad-framework-introduction (1).md` (Step 2 → drop suffix)
- VSD Volume 2 FINAL: `wiki/methodology/vsd_volume_2_final.md`
- Phase O1-VSD-BOOTSTRAP canonical: `wiki/methodology/phase_o1_vsd_bootstrap_canonical.md`
- VSD v1.0 FINAL: `C:\Users\Contr\Downloads\vsd_methodology_v1_FINAL.md` (Step 2 → import to `wiki/methodology/`)
- Master resumption prompt: `C:\Users\Contr\Downloads\claude_code_master_resumption_prompt.md` (Step 2 → import to `wiki/methodology/`)
- NotebookLM session prompt: `(absent — MISSING-ARTIFACT-001)`
- Authoritative state source: `CLAUDE.md` (project root)
- Memory index: `C:\Users\Contr\.claude\projects\C--Users-Contr-vapi-pebble-prototype\memory\MEMORY.md`
- State assessment: `wiki/assessments/vapi_state_assessment_2026_05_10.md`
- Allowlist: `.github/INVARIANTS_ALLOWLIST.json`
- Deployed addresses: `contracts/deployed-addresses.json`
- Kill-switch: `bridge/.env:208`

---

## 9. Document Metadata

**Document version:** 1.0 (initial integration provenance witness)
**Generated:** 2026-05-10
**Author authority:** VAPI Architect, sole deployer (`0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692`)
**Architect signature:** none yet (manifest pre-dates architect key generation in Step 4 — intentional; the manifest is the deferral-boundary witness, not a methodology artifact requiring signature)
**Manifest path:** this file — `wiki/methodology/INTEGRATION_PROVENANCE_2026-05-10.md`
**Status:** pending operator review; no commit yet
**Tags:** `#integration-provenance #vbdip-0001 #vad #methodology-resumption #deferral-boundary-witness #verification-first #honesty-first #append-only`

**Status transition log:**
- 2026-05-10: Step 1 manifest authored; pending operator review
- (pending): Operator confirms Finding 1/2/3 dispositions + MISSING-ARTIFACT-001 resolution option
- (pending): Atomic commit 1 lands manifest into tree
- (pending): Step 2 atomic commit 2 lands; §7.2 hash block appended
- (pending): Step 3 atomic commit 3 lands; §7.3 hash block appended
- (pending): Step 4 atomic commit 4 lands; §7.4 hash block appended
- (pending): Step 5 atomic commit 5 lands; §7.5 hash block appended; integration complete

**Append-only discipline:** §7 hash blocks are append-only. Once a step's
hash block is recorded, it is not modified. If an integration step has
to be re-attempted after revert, the new attempt's hash block is appended
*alongside* the original (with revert reason noted), not instead of it.
This preserves the forensic record of any failed integration attempt.

---

**End of integration provenance manifest.**

This document is the deferral-boundary witness for VBDIP-0001 integration
resumption on 2026-05-10. The hashes recorded above are the authoritative
starting state. All subsequent integration steps verify against this
baseline; deviations surface as findings rather than be absorbed silently.

The methodology framework is VAPI Architectural Discipline (VAD), pending
VBDIP-0001 freeze in Step 5 per Option D2 sequencing. Integration proceeds
under Verification-First Discipline with hold-for-operator-approval at
every step boundary. The kill-switch (`CHAIN_SUBMISSION_PAUSED=true`)
remains held throughout Steps 1-5; no on-chain activity occurs.
