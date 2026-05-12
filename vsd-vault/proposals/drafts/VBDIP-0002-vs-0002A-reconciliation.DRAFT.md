---
title: "VBDIP-0002 vs VBDIP-0002A — Reconciliation Plan"
date: 2026-05-12
proposal_type: VBDIP-RECONCILIATION
proposal_number: "0002R"
status: "DRAFT / PARALLEL DEVELOPMENT"
scope: "Documentation-only. No new authority granted. No PV-CI mutation. No code change."
parent_documents:
  - "wiki/methodology/VBDIP-0002-zkba-visual-projections.md"
  - "vsd-vault/proposals/drafts/VBDIP-0002A-verified-projection-media.DRAFT.md"
depends_on:
  - "VBDIP-0001-vad-framework-introduction.md"
authority: "VAPI Architect; bridge wallet 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692"
wallet_impact: "0 IOTX"
chain_impact: "none"
---

# VBDIP-0002 vs VBDIP-0002A — Reconciliation Plan

## 0. Reading Note

This document is a plan, not a proposal. It does not author new methodology. It
arranges existing methodology into a reconciliation surface so that a future
operator-authorized commit can land VBDIP-0002A content into VBDIP-0002 (or
preserve it as a sidecar lineage member) without re-deriving the per-section
decisions every time.

The reconciliation plan is a Lane A docs-only artifact. It is not a Lane B
implementation plan and not a Lane C activation authorization.

VBDIP-0001 is FROZEN. VBDIP-0002 is FROZEN-SPEC v1.0. VBDIP-0002A is DRAFT.
This plan changes none of those states.

---

## 1. Reconciliation Question

VBDIP-0002A (`vsd-vault/proposals/drafts/VBDIP-0002A-verified-projection-media.DRAFT.md`)
introduces the **Verified Projection Media (VPM)** wrapper category that
generalizes VBDIP-0002's ZKBA projections (HTML-only at v1) into a broader
deterministic-projection family with audience-specific surfaces (QR pass,
wallet card, hardware certificate, broadcast overlay, dispute packet,
marketplace card, dev sandbox, honesty board, agent review card).

The architectural relationship is settled (VBDIP-0002 §1.4 already states it
explicitly): VPM is a future wrapper layer over ZKBA. The question this plan
answers is not "should VPM exist" — it is "how does VPM content land in the
numbered-proposal record."

Three possible dispositions for the VBDIP-0002A content set:

- **D-MERGE** — Sections flow into VBDIP-0002 as new chapters (§17+, after the
  current §16 activation gates), preserving VBDIP-0002 as the single
  authoritative sidecar.
- **D-SIDECAR** — VBDIP-0002A stays as a sidecar lineage member alongside
  VBDIP-0002, with its own numbering (VBDIP-0002A as a letter-suffixed
  sub-proposal) that VBDIP-0002 references.
- **D-DEFER** — VBDIP-0002A becomes a downstream numbered proposal
  (VBDIP-0002B or VBDIP-0004+) that depends on VBDIP-0002 but stands on its
  own.

Each VBDIP-0002A section receives a per-section disposition in §3 below. The
overall recommendation in §5 is D-MERGE-SELECTIVE — high-stakes definition
material flows into VBDIP-0002; per-audience registry detail stays in
VBDIP-0002A; activation-gate adjustments land in VBDIP-0002.

---

## 2. Numbering Decision Surface

VBDIP-0002 §16 G2 + G9 explicitly hold the numbering decision open. The N1 /
N2' / N3 surface is:

- **N1** — This proposal claims `VBDIP-0002` permanently.
- **N2'** — Renumber to `VBDIP-0004+` because VBDIP-0001 reserves 0002 and
  0003 in its lineage.
- **N3** — Remain indefinite sidecar; never claim a numbered slot.

VBDIP-0002A is downstream of this decision. Its own activation gate G1 cites
VBDIP-0001 FROZEN as satisfied; it does not claim a number, only a letter
suffix `A` indicating relationship to whatever VBDIP-0002 becomes.

**This plan does not resolve N1/N2'/N3.** It captures the decision-shape so
that whichever number lands, the reconciliation procedure is the same.

If N1 is chosen: VBDIP-0002A absorption produces `VBDIP-0002` v2 OR a
companion `VBDIP-0002A` proposal that stays sidecar.

If N2' is chosen: VBDIP-0002 becomes `VBDIP-0004` (or later). VBDIP-0002A
absorption produces `VBDIP-0004A`. The letter-suffix lineage moves with the
parent.

If N3 is chosen: both stay indefinite-sidecar with VBDIP-0002A referencing
VBDIP-0002 by relative path rather than canonical number.

---

## 3. Per-Section Disposition

The table below maps each VBDIP-0002A section to its reconciliation
disposition. Sections marked **D-MERGE** become target candidates for new
VBDIP-0002 chapters or amendments to existing chapters. Sections marked
**D-SIDECAR** remain in VBDIP-0002A by design — they describe stakeholder
surfaces, registries, and audience-specific framing that does not belong in
the core ZKBA primitive document. Sections marked **D-DEFER** are candidates
for a future downstream proposal once Lane B implementation work begins.

| 0002A § | Title | Disposition | Target / Reason |
|---------|-------|-------------|-----------------|
| 1 | VPM Definition and Protocol Purpose | **D-MERGE** | Adds to VBDIP-0002 §2 "Architectural Pivot and Projection Boundary" — VPM as broader projection-media category extending HTML/ZKBA. Establishes the protocol equation `Canonical Truth → Deterministic Proof Media → Audience-Specific Trust` which belongs in the primitive document. |
| 2 | Non-Authority Clause | **D-MERGE** | Adds to VBDIP-0002 §12 "Category Distinction and AI Role Constraint". Explicitly enumerates what the wrapper does NOT authorize (IPFS pinning, on-chain anchoring, marketplace mutation, etc.). Critical safety clause; belongs in the master document. |
| 3 | VPM Lifecycle | **D-MERGE** | Adds to VBDIP-0002 §4 "ZKBA Artifact Stack" as a new §4.x subsection. The lifecycle (Canonical State → Wrapper Manifest → Deterministic Compile → Integrity Label → Stakeholder Surface → Expiry/Revocation) is core protocol shape, not stakeholder content. |
| 4 | VPM Wrapper Manifest Schema | **D-MERGE** | Adds to VBDIP-0002 §9 "UI Compiler Directives" as new §9.x. The schema `vapi-vpm-manifest-v1` is a wrapper schema that references the existing FROZEN-v1 `vapi-zkba-manifest-v1`; the wrapper definition belongs alongside the wrapped definition. |
| 5 | Visual Honesty Grammar (VPM-HONESTY-001) | **D-MERGE** | Adds to VBDIP-0002 §15 "Security, Privacy, and Misrepresentation Risks" as new §15.x. The visual-state vocabulary (live/dry-run/emulated/frozen-disabled/revoked/unverified) is risk-mitigation shape. **VPM-HONESTY-001 stays a methodology-doc identifier, NOT a PV-CI invariant** (see §4 below). |
| 6 | Stakeholder Utility Layer | **D-SIDECAR** | Audience-specific framing (gamers / developers / manufacturers / tournament organizers / marketplace buyers / governance). Belongs in a sidecar that can grow as audiences land; VBDIP-0002 is a primitive document, not a deployment-shape document. |
| 7 | Failure-State Rules | **D-MERGE** | Adds to VBDIP-0002 §15 as new §15.x. Failure visibility is risk-mitigation discipline; lives next to the misrepresentation risk catalogue. |
| 8 | Curator Marketplace Lane | **D-SIDECAR** | Curator agent-specific behavior. Belongs in operator-agent-skill documentation or in the Curator-specific sidecar. The VBDIP-0002 master document references Curator at the lane-prefix level (zk_listings) but does not own per-agent behavioral detail. |
| 9 | AI Role Constraint | **D-MERGE** | Adds to VBDIP-0002 §12. The "AI agents do not create protocol truth" clause is a category constraint that belongs in the master document. |
| 10 | VPM Projection Registry | **D-SIDECAR** | Ten Reserved VPM IDs (`PROOF-TRAILER-v1` through `AGENT-REVIEW-v1`). Registry maintenance is sidecar discipline; VBDIP-0002 references the registry by URI but does not embed the table. Registry grows as IDs transition `Reserved → Draft Manifest → Compiler Target → Test Fixture → Active`. |
| 11 | Activation Gates (G1-G6) | **D-MERGE** | VBDIP-0002A G1-G6 mostly duplicate or refine VBDIP-0002 G1, G3, G5, G6. **Net additions:** G4 (VPM wrapper manifest + Integrity Label implemented) and G5 (Anti-Hype Visual Grammar tests passing). These become new sub-gates under VBDIP-0002 G5 ("VPM Wrapper / Integrity Label Reconciled"). See §5 below for explicit gate-mapping. |
| 12 | Decision Blocks (L1-L7) | **D-MERGE** | VBDIP-0002A L1-L7 belong appended to VBDIP-0002 §17 "Decision Blocks (K1-K7)" as new K8-K14 entries. The K-prefix convention is preserved; decision blocks are the central operator-resolution surface and must live in one place. |

---

## 4. VPM-HONESTY-001 Namespace Lock-In

VBDIP-0002A §5 deliberately uses the identifier `VPM-HONESTY-001` rather than
`VED-INV-N` or `VBD-INV-N`. The text explains the choice: the next available
`VED-INV-N` slot (VED-INV-010) already aliases `INV-010` (`L6B_ENABLED
default=False`) per VEDIP-0001 Appendix A; collision would corrupt the
mapping.

**This plan locks the namespace decision:**

- **`VPM-HONESTY-001` is a methodology-document identifier, not a PV-CI
  invariant.** It does NOT enter `.github/INVARIANTS_ALLOWLIST.json`. It does
  NOT enter `scripts/vapi_invariant_gate.py`. It is referenced from
  VBDIP-0002A §5 and (post-D-MERGE) VBDIP-0002 §15.x, by name, as a
  documentation-only visual-honesty constraint.

- **If/when visual honesty becomes programmatically enforceable**, the
  enforcement ships as a new PV-CI invariant under the existing native naming
  convention (next available `INV-NNN` numeric, e.g. `INV-VPM-VISUAL-001`),
  authored by a future VBDIP-0002 update or downstream VEDIP. The methodology
  alias `VED-INV-N` for that future entry would be assigned at the same time
  per VEDIP-0001 Appendix A append discipline.

- **VPM-HONESTY-001 is not retroactively renamed to a PV-CI ID even if
  programmatic enforcement later lands.** The methodology-doc identifier and
  the source-code identifier serve different audiences and persist
  independently.

This matches the VED-INV-N pattern locked by VEDIP-0001: documentation
aliases over source identifiers, never source-identifier renames.

---

## 5. Activation-Gate Mapping (VBDIP-0002A G1-G6 → VBDIP-0002 G1-G9)

VBDIP-0002A activation gates G1-G6 map to VBDIP-0002 §16 gates G1-G9 as
follows. Per-gate disposition determines whether VBDIP-0002A gate text
absorbs into the parent gate, splits the parent gate into sub-gates, or
introduces a new gate at the parent level.

| 0002A gate | 0002A text | 0002 gate | Mapping disposition |
|------------|-----------|-----------|---------------------|
| G1 | VBDIP-0001 FROZEN | G1 | **MERGE-EQUIVALENT** — same gate; satisfied. |
| G2 | VBDIP-0002 reconciled with VBDIP-0002A | (new) | **NEW SUB-GATE** under VBDIP-0002 G5. This reconciliation plan is the artifact that resolves G2 when an operator-authorized commit lands the D-MERGE/D-SIDECAR decisions in §3. |
| G3 | `vsd_ui_compiler.py` deterministic harness passing | G3 | **MERGE-EQUIVALENT** — same gate; partially satisfied for Track 1 (GIC Continuity Ledger). |
| G4 | VPM wrapper manifest schema + Integrity Label implemented | G5 | **NEW SUB-GATE** under VBDIP-0002 G5. VBDIP-0002 G5 says "If VBDIP-0002A is adopted, VPM wrapper schema … must exist before any artifact is called an active VPM." VBDIP-0002A G4 names the deliverable concretely: `vapi-vpm-manifest-v1` schema + Integrity Label fields per VBDIP-0002A §4. |
| G5 | Anti-Hype Visual Grammar tests passing | G5 | **NEW SUB-GATE** under VBDIP-0002 G5. The visual-state vocabulary in VBDIP-0002A §5 + failure-state rules in VBDIP-0002A §7 must have passing test fixtures before any VPM artifact renders to a stakeholder. This is Lane B implementation work; the gate is named here so that Lane B has a target. |
| G6 | Cedar / AgentScope authority for any runtime use | G6 | **MERGE-EQUIVALENT** — same gate; both documents converge on this requirement. |

Net activation-gate result after D-MERGE: VBDIP-0002 §16 grows from 9 gates
to 11 gates (G5 splits into G5a "schema reconciliation," G5b "wrapper
manifest + Integrity Label implemented," G5c "Anti-Hype Visual Grammar tests
passing").

VBDIP-0002 §16 G7 (Curator Review Readiness) and G8 (Internal Projection
First) carry forward unchanged. G9 (Numbering Decision Applied) stays the
terminal gate.

---

## 6. Implementation Surface (Lane B Scope Pointer)

This plan does not author Lane B implementation. It captures the
implementation surface so that a future Lane B planning document does not
re-derive scope.

Lane B deliverables, at minimum:

1. **VPM wrapper manifest schema** (`vapi-vpm-manifest-v1`) — Python/JSON
   schema validation; sits alongside the existing FROZEN
   `vapi-zkba-manifest-v1` constants in `scripts/vsd_ui_compiler.py`. Wraps
   ZKBA manifests rather than replacing them.
2. **Integrity Label rendering** — visible UI element (HTML, QR pass surface,
   PDF block, etc.) with 9 required fields per VBDIP-0002A §5: Proof Type,
   Capture Mode, Raw Biometrics Exposed, Consent Active, ZK Verified,
   On-Chain Anchor, Proof Weight, Revocation Status, Limitations.
3. **Visual grammar tests** — per VBDIP-0002A §5 + §7 fixture set
   establishing that each visual-state literal (`live`, `dry-run`,
   `emulated`, `frozen-disabled`, `revoked`, `unverified`) renders
   distinguishably, and that each failure-state rule (missing manifest /
   compiler hash mismatch / proof-weight omission / revoked consent / stale
   verification key / absent anchor / DEMO / FROZEN_DISABLED) produces the
   correct visible degraded state.
4. **Registry compiler-target lifecycle** — for each VPM ID that transitions
   `Reserved → Compiler Target`, a compiler entry in `scripts/` analogous to
   `scripts/zkba_compile_gic_ledger.py`; for each `Compiler Target → Test
   Fixture` transition, a corresponding test file.
5. **No Cedar mutation, no chain call, no signature, no key generation.**

Lane B work remains wallet-free and authority-neutral. It does not require
Track 2 activation gates. The only constraint is that Lane B implementations
not be called "active VPM" or "production" until VBDIP-0002 G7 (Curator
Review Readiness) and G8 (Internal Projection First) also clear.

---

## 7. Per-Disposition Drift Findings

V-check findings captured during reconciliation drafting:

- **VBDIP-0002 §1.4 already references VBDIP-0002A** (Codex commit
  `c4abe1d5`). The relationship note is present; D-MERGE work converts that
  forward-reference into in-line content.
- **VBDIP-0002 §16 G5 already conditional on "If VBDIP-0002A is adopted"**
  (Codex commit `c4abe1d5`). The conditional drops once D-MERGE lands; G5
  becomes unconditional.
- **VBDIP-0002A activation gates use single G1-G6 numbering**; VBDIP-0002
  uses G1-G9. D-MERGE renumbering produces an 11-gate set; no gate
  semantically deletes.
- **Decision block lettering**: VBDIP-0002 uses K1-K7; VBDIP-0002A uses
  L1-L7. D-MERGE-SELECTIVE per §3 maps L1-L7 to K8-K14 (sequential append).
  No K1-K7 displacement.
- **CLAUDE.md NOTE entries** for the eventual D-MERGE commit should
  reference both the parent VBDIP-0002 sidecar and the absorbed VBDIP-0002A
  draft path, preserving append-only audit trail.
- **VEDIP-0001 Appendix A** does not need amendment under this plan — the
  reconciliation produces no new PV-CI invariants and no new VED aliases.
  Future PV-CI additions for visual-grammar enforcement (if/when Lane B
  produces them) would prompt a VEDIP-0001 Appendix A append, not a
  reconciliation revision.

---

## 8. Recommended Disposition

**Primary recommendation: D-MERGE-SELECTIVE** per §3 disposition table.

- Sections 1, 2, 3, 4, 5, 7, 9, 11, 12 of VBDIP-0002A → flow into
  VBDIP-0002 as named new chapters or extensions to existing chapters.
- Sections 6, 8, 10 of VBDIP-0002A → stay in VBDIP-0002A as sidecar
  content. VBDIP-0002 references VBDIP-0002A by relative path.

This produces a VBDIP-0002 v2 (with VBDIP-0002A absorbed selectively) and
keeps VBDIP-0002A as a narrower sidecar (registry maintenance + stakeholder
detail + Curator marketplace lane). The numbered-proposal lineage
discipline tolerates either a single document grown by D-MERGE or a parent
+ sidecar relationship; both are valid VBDIP-class patterns.

**Alternative: D-SIDECAR** (no merge, VBDIP-0002A stays full).

Acceptable but creates two sidecars that must be kept consistent. Higher
maintenance cost; lower ambiguity at decision boundaries (anything in
VBDIP-0002A is sidecar-only authority).

**Not recommended: D-DEFER** (VBDIP-0002A becomes numbered downstream
proposal).

Premature; numbering N1/N2'/N3 is not resolved. VBDIP-0002A is not yet
operationally important enough to claim a numbered slot.

---

## 9. Acceptance Criteria

This reconciliation plan is complete when:

1. The reconciliation question is named (§1).
2. Numbering decision surface is captured without resolving (§2).
3. Each VBDIP-0002A section receives a per-section disposition (§3).
4. VPM-HONESTY-001 namespace is locked as methodology-doc identifier (§4).
5. Activation-gate mapping from VBDIP-0002A G1-G6 to VBDIP-0002 G1-G11 is
   captured (§5).
6. Lane B implementation surface is pointed at without scoping it (§6).
7. Drift findings during plan drafting are recorded (§7).
8. A primary recommendation exists, with alternatives named (§8).
9. Wallet impact is zero; chain impact is zero;
   `CHAIN_SUBMISSION_PAUSED=true` remains unchanged.

This plan is not signed. The architect signing chain (VBDIP-0001 Step 4) is
available for any future operator-authorized D-MERGE commit that ships
under this plan's recommendation.

---

## 10. What This Plan Does Not Do

- Does not change VBDIP-0001 status (FROZEN).
- Does not change VBDIP-0002 status (FROZEN-SPEC v1.0).
- Does not change VBDIP-0002A status (DRAFT / PARALLEL DEVELOPMENT).
- Does not resolve N1 / N2' / N3 numbering.
- Does not author the D-MERGE commit. The D-MERGE commit, when an operator
  authorizes it, is a follow-up that reads this plan as scope.
- Does not regenerate `.github/INVARIANTS_ALLOWLIST.json`.
- Does not add or remove any PV-CI invariant.
- Does not author Lane B implementation work.
- Does not authorize Lane C Track 2 activation.

---

## 11. Cross-References

Within VAPI methodology documents:

- `wiki/methodology/VBDIP-0001-vad-framework-introduction.md`
- `wiki/methodology/VBDIP-0002-zkba-visual-projections.md`
- `wiki/methodology/VEDIP-0001-engineering-discipline-retrospective.md`
- `vsd-vault/proposals/drafts/VBDIP-0002A-verified-projection-media.DRAFT.md`
- `vsd-vault/README.md`
- `vsd-vault/manifests/proposals-VBDIP-0001/001.manifest.json`
- `vsd-vault/eval/architect_key_attestation.json`

Within VAPI protocol artifacts referenced by VBDIP-0002 / VBDIP-0002A:

- `bridge/vapi_bridge/zkba_artifact.py` (ZKBA primitive)
- `scripts/vsd_ui_compiler.py` (deterministic UI compiler, manifest schema
  `vapi-zkba-manifest-v1` FROZEN)
- `scripts/zkba_compile_gic_ledger.py` (first ZKBA artifact target)
- `frontend/src/artifacts/gic_continuity_ledger/` (compiler output sink)
- `.github/INVARIANTS_ALLOWLIST.json` (69 entries; unchanged by this plan)

Authoring boundary:

- repository branch: `main`
- preceding pushed commit: `c4abe1d5`
- wallet impact: 0 IOTX
- on-chain impact: none
- `CHAIN_SUBMISSION_PAUSED=true` verified

---

**End of reconciliation plan draft.**

The reconciliation surface is now arranged. The decisions remain
operator-authorized at their own future moments. The plan is ready to be
referenced when a D-MERGE commit lands or when VBDIP-0002A graduates to a
numbered lineage successor under whichever N decision the operator resolves.
