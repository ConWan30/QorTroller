---
title: "VBDIP-0002 §9.2 Schema-Name Reconciliation — v1.2 Amendment Proposal"
date: 2026-05-12
proposal_type: VBDIP-RECONCILIATION
proposal_number: "0002R-9.2"
status: "DRAFT / OPERATOR-DECISION-SHAPED"
scope: "Documentation-only. No PV-CI mutation. No code change. No signature application."
parent_documents:
  - "wiki/methodology/VBDIP-0002-zkba-visual-projections.md"
depends_on:
  - "VBDIP-0001-vad-framework-introduction.md"
  - "VEDIP-0001-engineering-discipline-retrospective.md"
authority: "VAPI Architect; bridge wallet 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692"
wallet_impact: "0 IOTX"
chain_impact: "none"
---

# VBDIP-0002 §9.2 Schema-Name Reconciliation — v1.2 Amendment Proposal

## 0. Reading Note

This proposal is a DRAFT. It does not author the resolution itself — it
frames a V-check finding that surfaced during G4 implementation (commit
`210f841b`) and presents three resolution options for operator
authorization.

If accepted, the recommendation in §6 (Option C — codify bilateral
acceptance) ships as a v1.2 amendment to VBDIP-0002 in a subsequent
commit, similar to how the reconciliation plan at commit `f47763fe`
preceded the D-MERGE-SELECTIVE v1.1 amendment at commit `3461b636`.

VBDIP-0001 is FROZEN. VBDIP-0002 is FROZEN-SPEC v1.0 + v1.1 amendment
(Appendix B). VBDIP-0002A is PARTIALLY ABSORBED. This proposal changes
none of those states; it proposes a v1.2 amendment (Appendix C) under
the existing supersession discipline.

---

## 1. The V-Check Finding

During G4 implementation (commit `210f841b`), the manifest validator at
`scripts/zkba_manifest_validator.py` was authored. While reading
VBDIP-0002 §9.2 to scope the validator's required-field set, a
divergence was discovered between the spec text and the implementation:

| Layer | Schema name literal |
|---|---|
| **§9.2 spec design-time text** | `zkba.projection_manifest.v1` |
| **`scripts/vsd_ui_compiler.py:58` implementation** | `vapi-zkba-manifest-v1` |
| **PV-CI invariant INV-ZKBA-003 pin** | `vapi-zkba-manifest-v1` |

### 1.1 How the drift happened

The drift trace:

- **2026-05-10 C3 (commit `3b3081d3`)** — Phase O3-ZKBA-TRACK1 Stream
  Z3 shipped `scripts/vsd_ui_compiler.py` with `_MANIFEST_SCHEMA =
  "vapi-zkba-manifest-v1"`. The implementation chose this name without
  consulting §9.2 text. §9.2 text at that point used
  `zkba.projection_manifest.v1`.

- **2026-05-10 C5 (commit `0791c935`)** — Phase O3-ZKBA-TRACK1 Stream
  Z8 added PV-CI invariant INV-ZKBA-003 pinning
  `vapi-zkba-manifest-v1` in `scripts/vapi_invariant_gate.py` +
  `.github/INVARIANTS_ALLOWLIST.json`. The implementation name was
  FROZEN at the PV-CI layer.

- **2026-05-12 G4 (commit `210f841b`)** — Validator authored. §9.2 text
  re-read for required-field set. Drift discovered.

Neither §9.2 nor INV-ZKBA-003 was updated to match the other across
C3 → C4 → C5 → G4. The drift has existed silently for ~2 days.

### 1.2 Current validator behavior under drift

`scripts/zkba_manifest_validator.py:ACCEPTED_SCHEMA_NAMES` is a
frozenset of both names. `validate_zkba_manifest()` accepts manifests
under either name. The `schema_name_form` field surfaces which name
was seen:

| Value | Meaning |
|---|---|
| `"implementation"` | Manifest uses `vapi-zkba-manifest-v1` (INV-ZKBA-003 pin) |
| `"spec_design_time"` | Manifest uses `zkba.projection_manifest.v1` (§9.2 text) |
| `"unknown"` | Schema string present but not recognized |
| `"absent"` | Schema field missing or not a string |

This forward-compat behavior surfaces through the validator's three
reach surfaces (MCP tool / bridge HTTP endpoint / SDK client) — see
commits `53553047`, `4f63c5d5`, `e4ad7cde`. The drift is now visible
to external tooling on every validation request.

### 1.3 Why this matters

A frozen-spec document with a divergent implementation is a
methodology-integrity issue. The drift question affects:

- **External integrators** reading VBDIP-0002 §9.2 to construct
  manifests will emit under `zkba.projection_manifest.v1` — accepted
  by validator + rejected by INV-ZKBA-003 if they ever pass through
  the PV-CI gate.
- **Future PV-CI consumers** (any module that pins a schema-name
  invariant by reference) currently see only the implementation name.
- **Audit trails** carry one name in spec text, the other in
  invariant allowlist — readers parsing for "the canonical schema
  name" face ambiguity.

The drift does NOT affect:

- Current shipped artifacts (only GIC Continuity Ledger; uses
  implementation name per `vsd_ui_compiler.py`)
- Track 1 PV-CI gate (passes 69/69; INV-ZKBA-003 is satisfied by
  implementation name)
- Wallet, chain state, Cedar authority, FSCA rules

---

## 2. Three Resolution Options

### Option A — Amend §9.2 text in place to match implementation

**Action:** Edit `wiki/methodology/VBDIP-0002-zkba-visual-projections.md`
§9.2 paragraph to use `vapi-zkba-manifest-v1` instead of
`zkba.projection_manifest.v1`. Single-character-class edit in spec
text.

**Cost:** Methodology cost only. No code change. No PV-CI ceremony.

**Risk: HIGH.** Violates the v1.0 supersession discipline locked at
§18:

> "VBDIP-0002 v1.0 is a foundational sidecar. Future revisions (v1.1,
> v1.2, ..., v2.0) build on this freeze; they do not modify v1.0 in
> place."

Editing §9.2 text in place is exactly what supersession discipline
forbids. Even though the edit is "trivial," accepting in-place edits
under the FROZEN-SPEC discipline establishes a precedent that future
editors can soft-amend spec text without authoring a v1.x amendment.

**Recommendation: REJECT** — violates supersession discipline.

### Option B — Migrate implementation to spec name (governance ceremony)

**Action:** Operator-authorized `--confirm-governance` ceremony to:

1. Edit `scripts/vsd_ui_compiler.py:58`: `_MANIFEST_SCHEMA =
   "zkba.projection_manifest.v1"` (matches §9.2).
2. Edit `scripts/vapi_invariant_gate.py` INV-ZKBA-003 pin literal to
   match.
3. Regenerate `.github/INVARIANTS_ALLOWLIST.json` with
   `--confirm-governance` flag + governance phrase ("I understand this
   changes a frozen protocol invariant").
4. Re-emit GIC Continuity Ledger artifact under new schema name (one
   compile run).
5. Update bridge endpoint constant `IMPLEMENTATION_SCHEMA_NAME` in
   `scripts/zkba_manifest_validator.py:71` to match.
6. Update SDK_VERSION marker.
7. Update VEDIP-0001 Appendix A entry for VED-INV-066 to reflect new
   pin literal.
8. Update G3/G4/MCP/endpoint/SDK test expectations referencing the
   schema name string.

**Cost:** Operator-authorized governance ceremony + ~12 file edits +
test re-runs + commit + push. Wallet 0 IOTX.

**Risk: MEDIUM.** Three sub-risks:

1. **PV-CI invariant change**: INV-ZKBA-003 is a FROZEN protocol
   invariant. Changing the pin literal requires `--confirm-governance`
   ceremony. The governance phrase + 3-second pause exists precisely
   to enforce operator awareness of the change.

2. **Existing artifact obsolescence**: The GIC Continuity Ledger
   artifact already on disk (if any) uses the implementation name.
   Re-emission under the new name produces a different
   `input_commitment_hex` (because the manifest contents change), so
   the existing file becomes orphaned. Operator must decide: leave
   orphan + emit new artifact (preserves historical reference) OR
   delete + re-emit (clean re-anchor; documents the rename
   transition).

3. **Coupled-document churn**: VEDIP-0001 Appendix A pinned the
   INV-ZKBA-003 frozen surface as `vapi-zkba-manifest-v1` in its
   documentation alias map. Changing the source pin requires aligning
   the VEDIP-0001 entry, which is a documentation update under
   VEDIP-0001 governance.

**Recommendation: CONSIDER** if operator believes §9.2 design-time
intent should prevail over implementation expedience. The change is
methodologically clean if the spec name is the "right" name. But the
implementation has been in production through 12 commits; migrating
backwards from a 2-day-old C3 decision after 12 downstream commits
is potentially-disruptive.

### Option C — Codify bilateral acceptance via v1.2 amendment (Appendix C)

**Action:** Author Appendix C "Schema Name Reconciliation (v1.2
amendment)" appended between Appendix B (the v1.1 amendment for
VBDIP-0002A absorption) and §18 (document metadata). Appendix C
content (~150 lines):

- §C.1 — Statement of the drift (mirrors §1 of this proposal)
- §C.2 — Bilateral acceptance: BOTH names are recognized
- §C.3 — Canonical name: `vapi-zkba-manifest-v1` (implementation;
  INV-ZKBA-003 pin). New emissions MUST use this name.
- §C.4 — Recognized legacy name: `zkba.projection_manifest.v1` (§9.2
  spec design-time). Validator accepts; no new emissions under this
  name.
- §C.5 — Validator behavior: `schema_name_form` field surfaces which
  name was seen, with FROZEN enum `{"implementation",
  "spec_design_time", "unknown", "absent"}`.
- §C.6 — Migration path: if a future v2 freeze chooses a different
  name (e.g., `vapi-zkba-projection-manifest-v2`), the v2 manifest
  will carry forward both v1 names as ACCEPTED-FOR-VERIFICATION-ONLY.
  No backwards-incompatible breakage.
- §C.7 — Cross-references: VEDIP-0001 Appendix A entry for
  VED-INV-066 reflects implementation name. PV-CI INV-ZKBA-003
  unchanged. Validator at G4 commit `210f841b` already implements
  the bilateral acceptance.
- §C.8 — Status: v1.2 amendment landed.

**Cost:** Methodology cost only. No code change. No PV-CI ceremony.
No signature ceremony. No wallet impact.

**Risk: LOW.** Three risk factors all mitigated:

1. **Supersession compliance**: Appendix C is ADDITIVE, like Appendix
   B before it. v1.0 spec §§1-17 + Appendix A + Appendix B stay
   byte-identical. v1.2 amendment is a new appendix.
2. **PV-CI compliance**: INV-ZKBA-003 unchanged. No governance
   ceremony needed.
3. **Implementation alignment**: Validator at G4 commit `210f841b`
   already implements bilateral acceptance. The amendment codifies
   the working behavior; it doesn't propose a behavior change.

**Recommendation: ACCEPT** — codifies the working state without
violating any discipline. Validator implementation already matches.
External documentation (this proposal + Appendix C) closes the V-check
finding loop.

### Option D — Defer indefinitely (no action)

**Action:** No amendment. Validator continues accepting both names.
§9.2 text stays unchanged. Drift remains documented only in §18
status log + commit body of `210f841b` + project memory file
`project_phase_o3_zkba_lane_b_g3_g4.md`.

**Cost:** Zero immediate cost.

**Risk: LOW immediate, MEDIUM long-term.** The drift exists; deferring
its resolution accumulates methodology-integrity debt that future
sessions must re-derive. External integrators encountering §9.2 will
re-discover the drift independently.

**Recommendation: REJECT** unless operator believes the drift is
genuinely too small to codify. Option C ships ~150 lines of
documentation and closes the finding cleanly; Option D preserves
~150 lines of methodology-integrity debt for marginal short-term
savings.

---

## 3. Comparison Matrix

| Criterion | Option A | Option B | Option C | Option D |
|---|---|---|---|---|
| Supersession discipline | VIOLATES | OK | OK | OK |
| PV-CI ceremony required | No | YES (governance phrase) | No | No |
| Code change required | No | YES (~12 files) | No | No |
| Wallet impact | 0 IOTX | 0 IOTX | 0 IOTX | 0 IOTX |
| Implementation alignment | YES (matches) | YES (migrated) | YES (already aligned) | NO (drift persists) |
| External-integrator clarity | High (spec matches code) | High (code matches spec) | High (both documented) | Low (drift undocumented) |
| Risk of downstream churn | None | MEDIUM (~12 coupled files) | None | None |
| Methodology-integrity debt closed | Yes (improperly) | Yes (heavyweight) | Yes (cleanly) | No |
| Operator authorization needed | Methodology-only | Governance ceremony | Methodology-only | None |

---

## 4. Recommended Resolution

**Option C — Codify bilateral acceptance via v1.2 amendment (Appendix C).**

Rationale:

1. **Lowest methodology cost** that closes the V-check finding cleanly
2. **Honors all three disciplines** (supersession, PV-CI freeze,
   implementation reality)
3. **Matches existing v1.1 amendment pattern** (Appendix B for
   VBDIP-0002A absorption); operators have already accepted this
   pattern at commit `3461b636`
4. **Closes the loop without forcing a backwards-incompatible
   migration** of either the spec or the implementation
5. **Preserves forward optionality** — if a future v2 freeze chooses
   to migrate to a different schema name, the v1.2 codification of
   bilateral acceptance documents the historical drift cleanly

The recommendation does NOT preclude a future operator-authorized
Option B migration. If the operator later decides spec name should
prevail, Option B remains available as a follow-up VBDIP-0002 v2.0
work item. Option C is the v1.x-bounded resolution.

---

## 5. What Changes If Recommendation Accepted

A follow-up commit (single atomic) would:

1. Edit `wiki/methodology/VBDIP-0002-zkba-visual-projections.md`:
   - Insert "Appendix C — Schema Name Reconciliation (v1.2
     amendment)" between Appendix B's closing `---` and §18 header
   - §C.1 through §C.8 contents as described in §2 Option C above
   - §18 metadata: append-only status log entry recording v1.2
     amendment ship
   - Document version field: append "+ v1.2 amendment"

2. No code change.
3. No PV-CI change.
4. No test change.
5. No SDK / Hardhat / contract change.
6. CLAUDE.md: append-only NOTE entry referencing the new amendment +
   linking back to this proposal.
7. MEMORY.md: index entry for the new project memory file.

Wallet impact: 0 IOTX. Chain impact: none.
`CHAIN_SUBMISSION_PAUSED=true` held.

---

## 6. What Changes If Recommendation Rejected

If operator picks **Option A**:
- §9.2 text edit in place violates supersession; operator must also
  amend §18 supersession discipline clause to permit in-place edits
  (which would be a meaningful methodology change). NOT recommended.

If operator picks **Option B**:
- Author a separate VBDIP-0002 v2.0 migration proposal with the full
  ~12-file change list + PV-CI ceremony plan + GIC artifact re-emission
  plan + VEDIP-0001 alignment update. Operator-authorization for
  governance phrase. Scope is significantly larger than this
  proposal's Option C.

If operator picks **Option D**:
- No action. This proposal is filed as "operator-declined" in
  vsd-vault. Drift continues to be documented only via §18 status
  log + commit bodies + project memory.

---

## 7. Acceptance Criteria

This DRAFT proposal is complete when:

1. The V-check finding is named precisely (§1)
2. The drift trace is documented with commit references (§1.1)
3. Current validator behavior under drift is captured (§1.2)
4. Three resolution options are analyzed with cost / risk / discipline
   alignment (§2)
5. A comparison matrix consolidates the options (§3)
6. A primary recommendation is given with rationale (§4)
7. Concrete change list for accepted recommendation is captured (§5)
8. Wallet impact is zero; chain impact is zero;
   `CHAIN_SUBMISSION_PAUSED=true` held

This proposal is NOT signed. The architect signing chain (VBDIP-0001
Step 4) is available for any future operator-authorized v1.2 amendment
landing commit.

---

## 8. What This Proposal Does NOT Do

- Does not change VBDIP-0001 status (FROZEN).
- Does not change VBDIP-0002 status (FROZEN-SPEC v1.0 + v1.1
  amendment).
- Does not change VBDIP-0002A status (PARTIALLY ABSORBED).
- Does not edit §9.2 text in place.
- Does not regenerate `.github/INVARIANTS_ALLOWLIST.json`.
- Does not change INV-ZKBA-003 pin literal.
- Does not change the implementation schema name in
  `scripts/vsd_ui_compiler.py`.
- Does not re-emit any compiled ZKBA artifact.
- Does not author the v1.2 amendment commit itself. The v1.2
  amendment commit, when an operator authorizes it, is a follow-up
  that reads this proposal as scope.
- Does not authorize Track 2 work.

---

## 9. Cross-References

Within VAPI methodology documents:

- `wiki/methodology/VBDIP-0001-vad-framework-introduction.md`
- `wiki/methodology/VBDIP-0002-zkba-visual-projections.md`
  (target document; §9.2 + §18 + future Appendix C)
- `wiki/methodology/VEDIP-0001-engineering-discipline-retrospective.md`
  (VED-INV-066 alias entry; no change required under recommendation)
- `vsd-vault/proposals/drafts/VBDIP-0002-vs-0002A-reconciliation.DRAFT.md`
  (precedent reconciliation plan that preceded the D-MERGE-SELECTIVE
  v1.1 amendment at commit `3461b636`)
- `vsd-vault/proposals/drafts/VBDIP-0002A-verified-projection-media.DRAFT.md`
  (PARTIALLY ABSORBED sidecar)

Within VAPI protocol artifacts (read-only references; no modification):

- `scripts/vsd_ui_compiler.py:58` (`_MANIFEST_SCHEMA` literal)
- `scripts/zkba_manifest_validator.py:71-77`
  (`IMPLEMENTATION_SCHEMA_NAME` + `SPEC_DESIGN_TIME_SCHEMA_NAME` +
  `ACCEPTED_SCHEMA_NAMES`)
- `scripts/vapi_invariant_gate.py` (INV-ZKBA-003 entry)
- `.github/INVARIANTS_ALLOWLIST.json` (allowlist with 69 entries)

Drift trace commits:

- `3b3081d3` — C3, implementation chose `vapi-zkba-manifest-v1`
- `0791c935` — C5, PV-CI INV-ZKBA-003 pinned implementation name
- `210f841b` — G4 validator authored; drift discovered
- `53553047` — MCP tool, drift surfaces through MCP layer
- `4f63c5d5` — bridge HTTP, drift surfaces through HTTP layer
- `e4ad7cde` — SDK, drift surfaces through SDK layer

Authoring boundary:

- repository branch: `main`
- preceding pushed commit: `1e5d44af`
- wallet impact: 0 IOTX
- on-chain impact: none
- `CHAIN_SUBMISSION_PAUSED=true` verified

---

**End of §9.2 schema-name reconciliation proposal draft.**

The drift is named. Three options analyzed. A primary recommendation
given. Operator authorization controls whether the v1.2 amendment
ships (Option C), the v2.0 migration ships (Option B), or no action
is taken (Option D). The recommendation is C; the choice remains
operator-authorized at its own future moment.
