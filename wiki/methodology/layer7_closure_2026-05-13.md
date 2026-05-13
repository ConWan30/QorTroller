---
title: "Layer 7 7-of-7 ZKBA Artifact Coverage Closure — 2026-05-13"
date: 2026-05-13
type: coverage_closure_summary
status: shipped
anchor_commit: ece17f4f
authority: VAPI Architect (bridge wallet 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692)
relates_to: METHODOLOGY_LAYER_INTEGRATION_MAP.md
relates_to_phase: Phase O3-ZKBA-TRACK1 Track 2 follow-up arc
forward_pointer: wiki/proposals/Phase_O4_VPM_Integration_Plan.md
---

# Layer 7 7-of-7 ZKBA Artifact Coverage Closure

> **What this document is.** The closure summary for the seven-commit
> Track 2 follow-up arc that shipped one concrete ZKBA artifact per
> `ZKBAClass` value in the FROZEN-v1 enum. After commit `ece17f4f`
> (HARDWARE Participation Card), the Methodology Layer (Layer 7) is
> empirically validated across **all 7 of 7** artifact classes — the
> external-reviewer exception clause "all classes except HARDWARE" is
> retired.
>
> **What it is not.** A re-derivation of the per-artifact byte layouts
> or composition rationale. Those live in the per-artifact ship commits
> and `CLAUDE.md` NOTE blocks. This document is the index over the seven
> ships plus the architectural firsts each one contributed.

---

## 1. The 7-of-7 Class Table

| Class       | Value | Commit     | Proof Weight             | Audience      | CFSS Lane | Composition Depth |
|-------------|-------|------------|--------------------------|---------------|-----------|-------------------|
| AIT         | 1     | `bdbcf67f` | CALIBRATION_PLUS_CONTEXT | operator      | sentry    | 1-primitive       |
| GIC         | 2     | `3b3081d3` | CHAIN_ONLY               | operator      | sentry    | 1-primitive       |
| VHP         | 3     | `4f399282` | CHAIN_ONLY               | operator      | sentry    | 1-primitive       |
| HARDWARE    | 4     | `ece17f4f` | CHAIN_ONLY               | manufacturer  | sentry    | 1-primitive       |
| CONSENT     | 5     | `9bfa981e` | CHAIN_ONLY               | gamer         | guardian  | 1-primitive       |
| TOURNAMENT  | 6     | `25e7f8f2` | CHAIN_ONLY               | operator      | sentry    | 3-primitive       |
| MARKET      | 7     | `269e439c` | MARKETPLACE_DERIVED      | buyer         | curator   | 2-primitive       |

Per-axis distribution (verified mechanically by
`scripts/layer7_coverage_audit.py`):

- **Proof weights exercised:** 3 of 6 ProofWeightClass values
  (`CHAIN_ONLY` ×5, `CALIBRATION_PLUS_CONTEXT` ×1,
  `MARKETPLACE_DERIVED` ×1). The remaining three (`DIRECT_HID`, `DEMO`,
  `FROZEN_DISABLED`) are unexercised by the current artifact set;
  exercising them is a Phase O4 candidate and is **not** a Layer 7
  closure prerequisite.
- **Audiences covered:** 4 of 4 — gamer, operator, buyer, manufacturer.
  Layer 7's audience-coverage axis is now closed.
- **CFSS lanes utilized:** 3 of 3 — `sentry` (5), `guardian` (1),
  `curator` (1). All three Operator Initiative agents have empirical
  artifact-emission utilization, not just policy-level authority.
- **Composition depths:** 3 distinct values (1-primitive, 2-primitive,
  3-primitive). PATTERN-017 has been empirically proven to compose
  primitives at depth.

---

## 2. HARDWARE Participation Card — Byte Layout

Verbatim from `scripts/zkba_compile_hardware_card.py`:

```
Single 32-byte component hash composed from:
    SHA-256(
        profile_hash(32)          # keccak256(mfr || model || firmwareVersion)
        || device_id_hash(32)     # SHA-256(canonical device name UTF-8 bytes)
        || cert_level_be(1)       # uint8 (1=controller, 2=controller+GSR)
        || manufacturer_addr(20)  # 20-byte Ethereum address (certifying)
        || is_certified_byte(1)   # 0x01 if active, 0x00 if revoked
    )                             # = 86 bytes preimage → 32 bytes
```

The 32-byte component is then composed into the canonical ZKBA
commitment per FROZEN-v1 (`b"VAPI-ZKBA-ARTIFACT-v1" || class || weight
|| n || sorted_components || ts_ns`) producing a single canonical
artifact commitment with `ZKBAClass.HARDWARE = 4` and
`ProofWeightClass.CHAIN_ONLY = 3`.

---

## 3. Manufacturer-Address Design Rationale

The HARDWARE Participation Card binds the certifying manufacturer's
**20-byte Ethereum address directly into the preimage** — *not* hashed.
This is a deliberate inversion of the CONSENT v1 (`9bfa981e`) gamer-
address-hashing decision. The semantic difference is load-bearing for
both privacy and audit:

- CONSENT v1 binds a **gamer**'s address, hashed via SHA-256 inside the
  preimage. A gamer's consent state is private to that gamer; the
  artifact identifies *that* a consent grant exists for *some* gamer
  without doxxing which gamer. Pseudonymous-by-design.
- HARDWARE v1 binds a **manufacturer**'s address as raw 20 bytes inside
  the preimage. A manufacturer's certification act is publicly
  attributable: third parties auditing the certification chain should
  be able to read the manufacturer's identity directly from the
  preimage, without an off-protocol address registry. Publicly-
  attributable-by-design.

Either decision is structurally valid; the protocol does not pick one
default. The choice is per-artifact-class and follows the audience: when
the audience is the gamer themselves, address-hashing is preferable;
when the audience is partner-program enrollment and external auditors,
raw-address binding is preferable. Future artifact classes follow the
same rule of thumb.

---

## 4. Three Architectural Firsts (HARDWARE Card)

1. **First manufacturer-bound audience artifact.** Prior six artifacts
   targeted gamers (CONSENT), operators (AIT/GIC/VHP/TOURNAMENT), or
   buyers (MARKET). HARDWARE introduces the manufacturer as a distinct
   audience tier — useful for partner programs (Sony Partner, GuliKit
   aftermarket, etc.) where the manufacturer needs an auditable
   cryptographic surface for certifications they perform.
2. **Closes the 3-agent CFSS coverage triangle at the Cedar policy
   level.** The test `T-ZKBA-HW-9` mirrors the `MARKET-9` (Curator-
   exclusive) and `CONSENT-9` (Guardian-exclusive) Cedar-policy
   assertions for Sentry. CFSS is now empirically verified for *all
   three* Operator Initiative agents at the Cedar policy level — not
   just in audit-matrix rows.
3. **Layer 7 7-of-7 closure invariant.** Test `T-ZKBA-HW-10` asserts
   `HARDWARE = ZKBAClass(4)`, that cross-class commitment collision
   does not occur with otherwise-identical inputs, and that the
   manufacturer address bit is independently load-bearing. The seventh
   row of the seven-row Layer 7 invariant table is now in place.

---

## 5. The 3-Agent CFSS Triangle at the Cedar Policy Level

The Cedar v2 lane authority matrix (anchored on IoTeX 2026-05-12,
commit `ad0f7d11`, dual-anchor ceremony `755fac33` → `2a91c564`)
encodes the 12 invariant rows that operationalize cross-fleet skill
separation across the three ZKBA lanes. Sourced verbatim from
`scripts/zkba_post_ceremony_audit.EXPECTED_LANE_MATRIX`:

| Agent          | Action                          | Resource prefix                | Effect  |
|----------------|---------------------------------|--------------------------------|---------|
| anchor_sentry  | tool:zk-artifact-anchor         | draft://zk_artifacts/*         | permit  |
| anchor_sentry  | skill:read                      | lane://zk_artifacts/**         | permit  |
| anchor_sentry  | tool:zk-audit-trail             | (any)                          | forbid  |
| anchor_sentry  | tool:zk-marketplace-listing     | (any)                          | forbid  |
| guardian       | tool:zk-audit-trail             | draft://zk_verifications/*     | permit  |
| guardian       | skill:read                      | lane://zk_verifications/**     | permit  |
| guardian       | tool:zk-artifact-anchor         | (any)                          | forbid  |
| guardian       | tool:zk-marketplace-listing     | (any)                          | forbid  |
| curator        | tool:zk-marketplace-listing     | draft://zk_listings/*          | permit  |
| curator        | skill:read                      | lane://zk_listings/**          | permit  |
| curator        | tool:zk-artifact-anchor         | (any)                          | forbid  |
| curator        | tool:zk-audit-trail             | (any)                          | forbid  |

Per-agent shape: each ZKBA lane has exactly one `permit` (the owning
agent) and exactly two `forbid` rows (the other two agents). The
seventh-artifact tests `T-ZKBA-HW-9`, `T-ZKBA-MARKET-9`, and
`T-ZKBA-CONSENT-9` collectively pin this invariant at the Cedar policy
level — not just at the audit-matrix level.

---

## 6. Forward Pointer — Phase O4

The natural follow-up work is the Phase O4 plan at
`wiki/proposals/Phase_O4_VPM_Integration_Plan.md`. That plan is
currently untracked in this worktree, awaiting operator review. The
stream A.4 of that plan introduces `scripts/vpm_audit.py` as the
canonical VPM-wrapper observability surface; `layer7_coverage_audit.py`
shipped here is its **upstream precursor** — same wallet-free contract,
same section shape, complementary scope (artifact-emission surface
where `vpm_audit` will cover the wrapper-emission surface).

The remaining three `ProofWeightClass` values (`DIRECT_HID`, `DEMO`,
`FROZEN_DISABLED`) are explicit Phase O4 candidates for future artifact
classes; exercising them is **not** a Layer 7 closure prerequisite per
the rationale in §1.

---

## 7. Verification

The mechanical verification surface is:

```
python scripts/layer7_coverage_audit.py --report
```

Expected output: all five sections OK, OVERALL PASS, exit code 0.

The test suite at `bridge/tests/test_phase_o3_layer7_coverage_audit.py`
(`T-L7-AUDIT-1` through `T-L7-AUDIT-6`) locks the audit's invariants
against drift: enum membership, compiler-script presence, proof-weight
distribution, audience coverage, and CFSS lane distribution. Any
future change that breaks Layer 7 7-of-7 closure trips at least one
test before reaching production.
