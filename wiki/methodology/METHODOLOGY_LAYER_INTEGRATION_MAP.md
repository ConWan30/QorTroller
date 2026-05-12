---
title: "VAPI Methodology Layer — Integration Map"
date: 2026-05-12
proposal_type: ARCHITECTURE-MAP
status: "v1.0 / OPERATIONAL"
scope: "Documentation-only. Architectural reference. No PV-CI mutation. No code change."
authority: "VAPI Architect; bridge wallet 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692"
wallet_impact: "0 IOTX"
chain_impact: "none"
---

# VAPI Methodology Layer — Integration Map

## 0. Purpose

This document captures the **Methodology Layer** as a distinct
architectural element of the VAPI protocol. Through Phase O3-ZKBA-TRACK1
(2026-05-10 through 2026-05-12), the methodology surface grew from
single-discipline VSD ("VAPI Synthesis Discipline") into a three-sub-
discipline framework (VAD) with its own primitive, wrapper layer,
validator, reach surfaces, signing chain, and PV-CI invariant set.

The Methodology Layer now sits alongside the protocol's other
architectural layers as a peer, not a side-document collection. This
integration map names the layer's components, their inter-relationships,
and how the layer interfaces with the rest of the protocol.

This is a v1.0 OPERATIONAL document. No future amendments by-default;
revisions ship as separately-numbered integration maps if the layer's
shape changes meaningfully.

---

## 1. Protocol Layer Stack

VAPI's complete architectural stack as of 2026-05-12:

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 7: Methodology (VAD framework)                       │
│           VSD | VED | VBD sub-disciplines                   │
│           ZKBA primitive | VPM wrapper                      │
│           Validator | Reach trio (Python/MCP/HTTP/SDK)      │
├─────────────────────────────────────────────────────────────┤
│  Layer 6: Smart Contracts (Solidity on IoTeX testnet 4690)  │
│           49 LIVE contracts (PHGCredential, VAPIProtocolLens,│
│           AdjudicationRegistry, VAPIDataMarketplaceListings,│
│           Groth16VerifierZKSepProof, ZKSepProofVerifier,    │
│           ProtocolCoherenceRegistry, VAPIBiometricGovernance│
│           etc.)                                             │
├─────────────────────────────────────────────────────────────┤
│  Layer 5: ZK Proof System (Groth16, BN254, Powers-of-Tau)   │
│           PitlSessionProofVerifier circuit                  │
│           ZKSepProof circuit (3-contributor ceremony LIVE)  │
├─────────────────────────────────────────────────────────────┤
│  Layer 4: Bridge Service (Python asyncio)                   │
│           3051 passing tests; Operator Initiative agents    │
│           (Sentry/Guardian/Curator at O1_SHADOW);           │
│           FSCA + ProtocolCoherenceAgent + 38 total          │
│           autonomous agents                                 │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: SDK (Python)                                      │
│           562 tests; 14 client classes wrapping bridge      │
│           HTTP endpoints + fail-open contract               │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: Hardware (DualShock Edge CFI-ZCP1)                │
│           1000 Hz USB HID polling                           │
│           12-feature biometric pipeline (L4 fingerprint)    │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: Cryptographic Primitives (FROZEN-v1 PATTERN-017)  │
│           10 primitives: PoAC, GIC, WEC, VAME,              │
│           CORPUS-SNAPSHOT, CONSENT, BIOMETRIC-SNAPSHOT,     │
│           LISTING-v1, FRR, ZKBA                             │
└─────────────────────────────────────────────────────────────┘
```

**Layer 7 is new as of Phase O3-ZKBA-TRACK1.** Pre-2026-05-10, methodology
documents existed as `wiki/methodology/` content without architectural
integration. The Phase O3-ZKBA-TRACK1 arc + VBDIP-0001 freeze + VBDIP-0002
sidecar + VEDIP-0001 retrospective + this integration map elevate the
methodology surface to a proper architectural layer.

---

## 2. Methodology Layer Components

### 2.1 The VAD Framework (VBDIP-0001 FROZEN at commit `d6830525`)

**VAPI Architectural Discipline (VAD)** is the top-level framework name.
Three sub-disciplines:

| Sub-discipline | Scope | Governance |
|---|---|---|
| **VSD** (Synthesis) | Methodology authoring; novelty claims; theoretical surface | VSDIP-NNN proposals |
| **VED** (Engineering) | Protocol-side engineering execution; V-checks; P-checks; atomic commits; PV-CI freezes | VEDIP-NNN proposals |
| **VBD** (Bridge) | Composition between VSD and VED domains; primitive-composition discipline; CFSS (cross-fleet skill separation) | VBDIP-NNN proposals |

VBDIP-0001 §11 metadata establishes the framework name, three sub-disciplines,
and the architect Ed25519 signing chain anchored to the bridge wallet via
EIP-191 attestation.

### 2.2 PATTERN-017 Primitive Family

Ten FROZEN-v1 cryptographic primitives constitute the protocol's
content-addressable state surface. Each primitive:

- Has a 21-byte domain tag literal (`b"VAPI-X-v1"` shape)
- Computes a 32-byte SHA-256 commitment over a pre-image with frozen byte layout
- Has at least one PV-CI invariant pinning its FROZEN constants

| # | Primitive | Domain tag | Where shipped |
|---|---|---|---|
| 1 | PoAC | `b"VAPI-PoAC-v1"` | Phase 17 (controller) |
| 2 | GIC | `b"VAPI-GIC-v1"` | Phase 235-A (commit `4ddebba5`) |
| 3 | WEC | `b"VAPI-WEC-v1"` | Phase 236-WATCHDOG |
| 4 | VAME | `b"VAPI-VAME-v1"` | Phase 236-VAME |
| 5 | CORPUS-SNAPSHOT | `b"VAPI-CORPUS-SNAPSHOT-v1"` | Phase 237.5 |
| 6 | CONSENT | `b"VAPI-CONSENT-v1"` | Phase 237-CONSENT |
| 7 | BIOMETRIC-SNAPSHOT | `b"VAPI-BIOMETRIC-SNAPSHOT-v1"` | Phase 237-ZK-SEPPROOF |
| 8 | LISTING-v1 | `b"VAPI-LISTING-v1"` | Phase 238 |
| 9 | FRR | `b"VAPI-FRR-v1"` | Phase O1-FRR-PARALLEL |
| **10** | **ZKBA** | `b"VAPI-ZKBA-ARTIFACT-v1"` | **Phase O3-ZKBA-TRACK1 C2 (commit `625007ab`)** |

Two additional primitives are reserved post-bootstrap (VRR + CDRR;
Phase O1-VSD-BOOTSTRAP work). The methodology layer's contribution is
**primitive #10 ZKBA** — the 10th FROZEN-v1 element.

### 2.3 VPM Wrapper Layer (VBDIP-0002 Appendix B v1.1 amendment)

**Verified Projection Media (VPM)** is a wrapper category that composes
over ZKBA artifacts to produce stakeholder-facing surfaces. VPM does
NOT replace ZKBA — it references it through a wrapper schema.

```
ZKBA artifact (FROZEN-v1 primitive)
  └─ wrapped by VPM manifest (vapi-vpm-manifest-v1 schema)
       ├─ Integrity Label (9 required fields per B.5)
       ├─ Visual state (FROZEN 6-element enum)
       ├─ Capture mode (FROZEN 5-element enum)
       ├─ Revocation status (FROZEN 3-element enum)
       ├─ Anchor status (FROZEN 4-element enum)
       └─ Lifecycle status (FROZEN 5-element enum)
```

Wrapper implementation: `scripts/vsd_vpm_wrapper.py` (~510 LOC; commit
`72b056e8`). Wrapper validator: `validate_vpm_manifest()` returns list of
error strings; mechanical enforcement of B.6 failure-state rules
(revoked consent → REVOKED visual state; FROZEN_DISABLED never renders
LIVE; etc.).

### 2.4 Manifest Validator (Lane B G4 commit `210f841b`)

**ZKBA Manifest Validator** at `scripts/zkba_manifest_validator.py` (~340
LOC) ships the §9.2 schema validation primitive.

Public API:
```python
result: ManifestValidationResult = validate_zkba_manifest(manifest_dict)
# result.valid (bool)
# result.errors (tuple of human-readable error strings)
# result.zkba_class_name + result.proof_weight_name
# result.schema_name_form ("implementation" / "spec_design_time" / "unknown" / "absent")
```

Fail-open contract: never raises. `build_representative_manifest(zkba_class)`
helper produces synthetic test fixtures for all 7 ZKBA classes at
default proof_weight per the DEFAULT_PROOF_WEIGHT_BY_CLASS table:

| ZKBAClass | Default proof_weight |
|---|---|
| AIT | CALIBRATION_PLUS_CONTEXT |
| GIC | CHAIN_ONLY |
| VHP | CHAIN_ONLY |
| HARDWARE | CHAIN_ONLY |
| CONSENT | CHAIN_ONLY |
| TOURNAMENT | CHAIN_ONLY |
| MARKET | MARKETPLACE_DERIVED |

### 2.5 Reach Trio — How External Tooling Touches the Layer

The validator is accessible from FOUR surfaces:

| Surface | Module | Test count | Commit |
|---|---|---|---|
| Python library | `scripts/zkba_manifest_validator.py` | 55 | `210f841b` |
| MCP tool | `vapi-mcp/knowledge_server.py:vapi_validate_zkba_manifest` | 4 | `53553047` |
| Bridge HTTP | `bridge/vapi_bridge/operator_api.py:POST /operator/zkba-validate-manifest` | 13 | `4f63c5d5` |
| SDK | `sdk/vapi_sdk.py:VAPIZKBAValidator` | 12 | `e4ad7cde` |

All four surfaces return the SAME `ManifestValidationResult` shape.

### 2.6 Architect Signing Chain (VBDIP-0001 Step 4 commit `8b95d5bc`)

The Methodology Layer has its own cryptographic signing chain anchored
to the bridge wallet:

```
Architect Ed25519 key (056e695f...8ca8)
  └─ EIP-191 attestation by bridge wallet (0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692)
       └─ Signature 0xb21a94de...3731b
            └─ Attestation file: vsd-vault/eval/architect_key_attestation.json
                 └─ Architect-signed methodology proposals:
                     ├─ VBDIP-0001 (FROZEN; signed at commit d6830525)
                     └─ Future architect-signed manifests inherit trust
```

Private key (`vsd-vault/architect_key.pem`) gitignored at
`vsd-vault/.gitignore:12`; NEVER committed.

The signing chain enables operator-authorized methodology artifacts to
carry deployer-verified provenance per VBD-INV-001 (continuous
deployer-verified provenance under fleet expansion).

### 2.7 PV-CI Invariant Coverage (Methodology Layer entries)

The Methodology Layer contributes 6 PV-CI invariants to the protocol's
allowlist (69 total entries):

| Invariant | Pins | Where |
|---|---|---|
| INV-ZKBA-001 | `compute_zkba_commitment` function existence | `bridge/vapi_bridge/zkba_artifact.py` |
| INV-ZKBA-002 | `b"VAPI-ZKBA-ARTIFACT-v1"` domain tag literal | `bridge/vapi_bridge/zkba_artifact.py` |
| INV-ZKBA-003 | `"vapi-zkba-manifest-v1"` manifest schema literal | `scripts/vsd_ui_compiler.py` |
| VBD-INV-001 | Continuous deployer-verified provenance under fleet expansion | VBDIP-0001 §4.1 |
| VBD-INV-002 | Fleet-domain replication discipline | VBDIP-0001 §4.2 |
| VBD-INV-003 | Primitive composition discipline | VBDIP-0001 §4.3 |

VEDIP-0001 Appendix A maps engineering/protocol PV-CI entries 1-66 to
documentation aliases `VED-INV-001..066`. VBD-INV-001/002/003 are
VBD-native, NOT VED aliases.

### 2.8 Methodology Document Corpus

```
wiki/methodology/
├─ VBDIP-0001-vad-framework-introduction.md         (FROZEN)
├─ VBDIP-0002-zkba-visual-projections.md            (FROZEN-SPEC + v1.1 + v1.2)
├─ VEDIP-0001-engineering-discipline-retrospective.md  (RETROSPECTIVE-SPEC v1.0)
├─ INTEGRATION_PROVENANCE_2026-05-10.md             (deferral-boundary witness)
├─ METHODOLOGY_LAYER_INTEGRATION_MAP.md             (this document)
├─ vsd_methodology_v1_FINAL.md                      (VSD origin v1.0)
├─ vsd_volume_2_final.md                            (VSD v2.0)
├─ claude_code_master_resumption_prompt.md          (bootstrap procedure)
├─ phase_o1_vsd_bootstrap_canonical.md              (Phase O1 bootstrap)
├─ bt_calibration_v1_1_architectural_revision.md
└─ sensor_stack_v2_1_architectural_revision.md

vsd-vault/proposals/drafts/
├─ VBDIP-0002A-verified-projection-media.DRAFT.md      (PARTIALLY ABSORBED)
├─ VBDIP-0002-vs-0002A-reconciliation.DRAFT.md         (precedent reconciliation plan)
├─ VBDIP-0002-schema-name-reconciliation.DRAFT.md      (§9.2 drift resolution; Option C shipped)
└─ OPERATOR-DECISION-MATRIX.DRAFT.md                   (16-decision consolidated index)

vsd-vault/manifests/
└─ proposals-VBDIP-0001/001.manifest.json              (architect Ed25519 signature)

vsd-vault/eval/
└─ architect_key_attestation.json                       (bridge wallet EIP-191 attestation)
```

---

## 3. Inter-Layer Interfaces

### 3.1 Methodology Layer → Bridge Service (Layer 4)

| Interface | Surface | Used by |
|---|---|---|
| ZKBA primitive import | `bridge/vapi_bridge/zkba_artifact.py` | Bridge runtime + tests + scripts/ |
| ZKBA store schema | `bridge/vapi_bridge/store.py:zkba_artifact_log` | Bridge persistence |
| Validator endpoint | `bridge/vapi_bridge/operator_api.py:POST /operator/zkba-validate-manifest` | External HTTP clients |
| ZKBA query endpoints | `bridge/vapi_bridge/operator_api.py:GET /operator/zkba-{status,artifact,history}` | External HTTP clients |

### 3.2 Methodology Layer → SDK (Layer 3)

| Interface | Surface |
|---|---|
| ZKBA artifact reader | `sdk/vapi_sdk.py:VAPIZKBA` + 3 Result dataclasses |
| ZKBA validator | `sdk/vapi_sdk.py:VAPIZKBAValidator` + `ZKBAValidateResult` |
| OpenAPI spec | `sdk/openapi.yaml` schemas + paths |

### 3.3 Methodology Layer → MCP (peer)

Three MCP tools exposed at `vapi-mcp/knowledge_server.py`:

- `vapi_zkba_status` (commit `8d2dc87e`)
- `vapi_compile_zkba_artifact` (commit `8d2dc87e`)
- `vapi_zkba_projection_manifest` (commit `8d2dc87e`)
- `vapi_validate_zkba_manifest` (commit `53553047`)

### 3.4 Methodology Layer → Cryptographic Primitives (Layer 1)

The Methodology Layer's ZKBA primitive COMPOSES existing PATTERN-017
primitives. Each ZKBA artifact references one or more upstream
primitives:

| ZKBA class | Composed primitives |
|---|---|
| AIT | BIOMETRIC-SNAPSHOT (calibration corpus) |
| GIC | GIC chain head (Phase 235-A) |
| VHP | VHP token state (on-chain VAPIVerifiedHumanProof) |
| HARDWARE | Hardware cert (on-chain) |
| CONSENT | CONSENT primitive |
| TOURNAMENT | Composite: VHP + isFullyEligible |
| MARKET | LISTING-v1 primitive |

### 3.5 Methodology Layer → Smart Contracts (Layer 6)

Methodology Layer is NOT YET on-chain. Track 2 activation
(C6/C7/C8 from the i-authorize-yours-to-precious-scone plan §6) ships:

- Cedar v2 bundles adding `zk_artifacts/`, `zk_verifications/`,
  `zk_listings/` lane prefixes
- FSCA contradiction rules for ZKBA artifacts
- Parallel ZKBA anchor script with triple-gate authorization
- Bundle re-anchoring ceremony (~0.18 IOTX)

This Track 2 work remains operator-gated. The Methodology Layer is
**Track 1 COMPLETE** as of 2026-05-12; Track 2 awaits operator
authorization.

---

## 4. Track 1 Completion Status

Phase O3-ZKBA-TRACK1 closure as of 2026-05-12:

| Sub-gate | Status | Source commit |
|---|---|---|
| G1 (VBDIP-0001 FROZEN) | SATISFIED | `d6830525` |
| G2 (numbering N1/N2'/N3) | PENDING | operator-decision |
| G3 (§9.3 visual honesty) | PARTIALLY SATISFIED | `aaaa1653` (active artifact set covered) |
| G4 (manifest schema validation 7-class) | SATISFIED | `210f841b` (+ reach trio at `53553047`/`4f63c5d5`/`e4ad7cde`) |
| G5a (VBDIP-0002A reconciliation) | SATISFIED | `3461b636` |
| G5b (VPM wrapper + Integrity Label) | SATISFIED | `72b056e8` |
| G5c (Anti-Hype Visual Grammar tests) | SATISFIED | `72b056e8` |
| G6 (AgentScope/Cedar authority) | PENDING | operator gate-by-gate |
| G7 (Curator review readiness) | PENDING | operator-decision |
| G8 (Internal Projection First) | PARTIALLY SATISFIED | GIC ledger ships; CDRR DAG post-bootstrap |
| G9 (numbering applied) | PENDING | depends on G2 |
| §9.2 schema-name drift | RESOLVED via Option C | `a501d6f1` (v1.2 amendment) |

**Track 1 wallet-free + authority-neutral envelope CLOSED.**

All non-gated, non-PV-CI-ceremony work that can be done without
operator authorization beyond "proceed in sequential order" has been
shipped.

---

## 5. Layer Invariants (Methodology-Level)

In addition to the 6 PV-CI invariants listed in §2.7, the Methodology
Layer enforces FIVE layer-level invariants that are NOT in the PV-CI
allowlist but ARE load-bearing for layer integrity:

| Layer invariant | Where enforced |
|---|---|
| Supersession discipline | VBDIP-0002 §18 metadata clause |
| VPM-HONESTY-001 (methodology-doc identifier; NOT PV-CI) | VBDIP-0002 Appendix B B.5 + reconciliation plan §4 |
| VED-INV-N documentation-only aliasing | VEDIP-0001 Appendix A + reconciliation plan §4 |
| Wallet-risk separation (filesystem vs chain) | VEDIP-0001 §3.5 |
| Drift preservation (V-check findings remain) | VEDIP-0001 §3.4 K4 |

These five invariants are MARKDOWN-NORMATIVE — they are discipline
rules enforced by operator review during commits, not by automated
gates. Future VEDIPs may elevate any of them to programmatic PV-CI
invariants if operator authorizes governance ceremony.

---

## 6. Methodology Layer Integration Timeline

| Date | Phase / Event | Outcome |
|---|---|---|
| 2026-05-09 | Sessions 1+2+3 | Curator agent LIVE at O1_SHADOW; ZK-SEPPROOF verifiers LIVE; VHP demo mint |
| 2026-05-10 | Phase O3-ZKBA-TRACK1 C1-C5 + VBDIP-0001 Steps 1-5 | ZKBA primitive landed; VBDIP-0001 FROZEN; architect signing chain LIVE |
| 2026-05-11 | VEDIP-0001 retrospective + VBDIP-0002A draft | VED named retroactively; VPM concept introduced |
| 2026-05-12 | Lane B G3/G4/G5b/G5c + reach trio + Option C v1.2 amendment + layer map (this commit) | Methodology Layer architecturally complete (Track 1) |

The layer crystallized over a 3-day arc. Track 2 activation (on-chain
ceremony) remains operator-gated for future operator-authorized
session.

---

## 7. What This Map Does NOT Do

- Does not change any FROZEN methodology document.
- Does not propose new PV-CI invariants.
- Does not authorize Track 2 activation.
- Does not resolve any of the 16 decisions in OPERATOR-DECISION-MATRIX.
- Does not extend the methodology surface — only DESCRIBES the
  existing extension.

The map's value is consolidation: future operators reading any single
methodology document now have a single integration-level reference
showing how their document fits into the broader layer.

---

## 8. Cross-References

Within Methodology Layer:
- All documents listed in §2.8

Within VAPI protocol:
- `bridge/vapi_bridge/zkba_artifact.py` (ZKBA primitive module)
- `bridge/vapi_bridge/store.py` (zkba_artifact_log table)
- `bridge/vapi_bridge/operator_api.py` (ZKBA endpoints)
- `scripts/vsd_ui_compiler.py` (deterministic UI compiler)
- `scripts/vsd_vpm_wrapper.py` (VPM wrapper module)
- `scripts/zkba_manifest_validator.py` (G4 validator)
- `scripts/zkba_compile_gic_ledger.py` (GIC Continuity Ledger artifact)
- `sdk/vapi_sdk.py` (VAPIZKBA + VAPIZKBAValidator)
- `vapi-mcp/knowledge_server.py` (4 ZKBA MCP tools)
- `scripts/vapi_invariant_gate.py` (PV-CI gate)
- `.github/INVARIANTS_ALLOWLIST.json` (69 entries; 6 methodology-layer)

External:
- IoTeX testnet (chain ID 4690; bridge wallet 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692)

Authoring boundary:
- repository branch: `main`
- preceding pushed commit: `a501d6f1` (Option C v1.2 amendment)
- bridge tests at boundary: 3051
- SDK tests at boundary: 562
- Hardhat tests at boundary: 528
- PV-CI entries at boundary: 69
- wallet impact: 0 IOTX
- on-chain impact: none
- `CHAIN_SUBMISSION_PAUSED=true` verified

---

**End of Methodology Layer Integration Map v1.0.**

The Methodology Layer is now a peer architectural element of VAPI,
not a side collection of methodology notes. Its components are
named, their relationships are mapped, and its boundary with the
rest of the protocol is explicit. Future methodology work ships
within this layer's discipline; future protocol work consumes the
layer through its four reach surfaces.
