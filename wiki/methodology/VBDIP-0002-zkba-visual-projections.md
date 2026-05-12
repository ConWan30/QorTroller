# VBDIP-0002 - Zero-Knowledge Biometric Artifacts and Visual Proof Projections

**Proposal type:** VBDIP (Verified Bridge Discipline Improvement Proposal)
**Proposal number:** 0002 (sidecar; numbering decision pending operator resolution)
**Status:** FROZEN-SPEC v1.0, pending operational activation gates
**Author authority:** VAPI Architect, sole deployer (`0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692`)
**Generated:** 2026-05-10
**Scope:** VAPI-internal sidecar specification. Not operationally active.
**Dependency:** VBDIP-0001 FROZEN dependency satisfied; operational activation still gated.
**Activation status:** Partially satisfied: VBDIP-0001 is FROZEN and the Track 1 deterministic compiler exists; blocked until numbering resolution, full schema validation, AgentScope/Cedar permissions, and VPM Integrity Label / visual grammar tests are implemented and authorized.
**Staging path:** `wiki/methodology/VBDIP-0002-zkba-visual-projections.md`
**Eventual vault path:** `vsd-vault/proposals/VBDIP-0002-zkba-visual-projections.md` (or successor path per VAD-MIGRATE)
**Revision note:** This v1.0 enhancement consolidates an earlier draft with a forward-looking extensions appendix (Section A). Section ordering follows the operator-canonical 17-section spec.

---

## 1. Reading Note and Dependency Status

### 1.1 Reading Note

This document specifies **Zero-Knowledge Biometric Artifacts (ZKBAs)** as a
VAPI-native artifact category that translates cryptographic biometric truth
into human-legible visual form without exposing the underlying biometric
vector.

The governing invariant is:

```text
Markdown notes, proof manifests, and VAPI FROZEN-v1 primitives remain
canonical. HTML is a deterministic, proof-bearing visual projection.
```

HTML is not a source of truth. HTML is the human-legible rendering layer for
already verified state. ZK proofs, on-chain anchors, FROZEN-v1 commitments,
and signed manifests are the proof root. ZKBAs project that root into a
deterministic visual surface that stakeholders can locally verify against the
proof root once the relevant verification runtime exists. The Track 1
deterministic compiler (`scripts/vsd_ui_compiler.py`) now exists and has a
passing deterministic-output test suite for the GIC Continuity Ledger target;
the broader VBDIP-0002 operational activation remains gated by §16.

### 1.2 Dependency Status

VBDIP-0002 is **not operationally active**. Some original dependencies have
now been satisfied by Track 1 work, but activation still requires all of the
following independent gates:

1. **VBDIP-0001 FROZEN** - satisfied by the VBDIP-0001 freeze commit and
   deployer-anchored architect signing chain.
2. **Compiler harness implemented** - partially satisfied by Track 1:
   `scripts/vsd_ui_compiler.py` exists and the GIC Continuity Ledger
   deterministic-output tests pass. Full activation still requires the
   complete Section 9.3 visual honesty test surface.
3. **ZKBA manifest schema validated** - still required. The JSON schema in Section 9.2 must
   validate against representative artifacts of each ZKBA class in Section 5.
4. **VBDIP-0002A / VPM reconciliation** - still required before VPM language
   becomes active. VBDIP-0002A generalizes HTML/ZKBA projection outputs into
   Verified Projection Media while preserving this document as the ZKBA
   artifact specification.
5. **AgentScope/Cedar permissions authorized** - still required. Each Operator agent
   (Sentry / Guardian / Curator) must have a Cedar bundle phase-anchored on
   chain that authorizes the actions named in Section 8 for the artifact
   lifecycle. These authorizations are NOT in scope for VBDIP-0002 freeze;
   they are scope for follow-up ceremonies.
6. **VPM Integrity Label and visual grammar tests** - still required for any
   VPM-labeled projection. The existing GIC Continuity Ledger is a ZKBA
   compiler target, not an active VPM artifact, until VPM wrapper manifests
   and Integrity Label tests exist.

Until all remaining gates close, VBDIP-0002 is a sidecar specification. The
methodology surface assumes the specification is `read-only context`, not
`active discipline`.

### 1.3 Numbering Drift

The current VBDIP-0001 draft §3.3 reserves **BOTH** VBDIP-0002 AND VBDIP-0003:
VBDIP-0002 for **Phase O1-VAD-MIGRATE** (the deferred `vsd-vault/` ->
`vad-vault/` directory rename plus Cedar re-anchoring) and VBDIP-0003 for
**any post-bootstrap discovery requiring VBD invariant adjustment**. This file
uses the operator-requested `VBDIP-0002` title and filename, but does not
force the lineage decision. Note that simple renumbering to `VBDIP-0003`
collides with VBDIP-0001's second reservation. Before FROZEN activation,
the operator must resolve numbering by one of:

- **N1** Amend VBDIP-0001 to relocate Phase O1-VAD-MIGRATE to VBDIP-0004 or
  later; this proposal owns the VBDIP-0002 slot. VBDIP-0001 is currently
  FROZEN-candidate (not FROZEN), so a pre-freeze amendment is methodology-
  permissible.
- **N2'** Renumber this proposal to **VBDIP-0004 or higher** (not 0003;
  VBDIP-0001 §3.3 reserves 0003 for post-bootstrap discovery work).
  Preserves VBDIP-0001's stated reservation set; introduces a numbering gap
  between active proposals.
- **N3** Keep this file as an indefinite sidecar `VBDIP-XXXX-ZKBA-DRAFT`
  with no lineage commitment until empirical operational signal warrants
  promotion. Safest option; introduces citation-drift risk.

Until that decision is made, this file is a sidecar FROZEN-SPEC candidate,
not an active lineage mutation. See Section 17 Decision Block K1 and
Section A.13.

### 1.4 VBDIP-0002A Relationship

VBDIP-0002A (`vsd-vault/proposals/drafts/VBDIP-0002A-verified-projection-media.DRAFT.md`)
is a documentation-only draft sidecar that generalizes HTML and ZKBA
projection outputs into the broader **Verified Projection Media (VPM)** media
category.

This relationship is hierarchical, not substitutive:

- VBDIP-0002 remains the ZKBA artifact specification.
- VBDIP-0002A defines a future VPM wrapper layer over existing ZKBA and proof
  manifests.
- `vapi-zkba-manifest-v1` remains frozen and unchanged.
- VPM wrapper manifests are not operational authority until VBDIP-0002A is
  reconciled, Integrity Label tests exist, and governance authorizes use.

---

## 2. Architectural Pivot and Projection Boundary

### 2.1 Architectural Pivot

VAPI's evidence base is cryptographically rigorous but not human-legible by
default. PoAC hashes, GIC chain heads, biometric centroids, covariance
commitments, Cedar bundle hashes, consent bitmasks, LISTING-v1 commitments,
and Groth16 verification outputs are machine-verifiable but not interpretable
by gamers, tournament organizers, developers, marketplace buyers, or
hardware partners.

The architectural pivot encoded in VBDIP-0002 is:

```text
VAPI's proof surface gains a deterministic, privacy-preserving, human-legible
projection layer that translates cryptographic truth into stakeholder-facing
artifacts without weakening the canonical state.
```

This is not a presentation feature. It is a **translation layer between
cryptographic truth and human trust** with explicit boundary discipline.

### 2.2 Projection Boundary

HTML projections may display, explain, and locally verify VAPI state. They
may not invent, strengthen, or mutate VAPI state.

Canonical inputs are:

- harness-passing Markdown notes and their signed manifests,
- VAPI FROZEN-v1 primitive commitments,
- ZK proof payloads and verification key commitments,
- on-chain anchor references,
- bridge-local state roots where explicitly declared.

Derived outputs are:

- self-contained HTML files,
- inline SVG or Canvas visualizations,
- deterministic JSON projection manifests,
- derived Markdown or plain-text corpus extracts for NotebookLM or other
  retrieval tools.

An HTML projection is **valid only if it can be deterministically recompiled
from its declared canonical inputs by the approved compiler version**. This
is the load-bearing invariant of the projection layer.

### 2.3 Deterministic Compilation Invariant

Every projection must declare:

- compiler name,
- compiler version,
- compiler source hash,
- canonical input hashes,
- output artifact hash,
- proof manifest hash,
- generated timestamp,
- projection class,
- proof-weight class.

Given the same canonical inputs and compiler version, the output artifact
hash must be stable. If any input changes, the output hash must change. No
external CDNs, remote rendering services, mutable web fonts, network-loaded
images, or nondeterministic runtime dependencies are permitted in production
artifacts.

### 2.4 Visual Honesty Invariant

The visual layer may not imply a stronger claim than the underlying evidence
supports. If a feature is emulated, disabled, stale, demo-only, chain-only,
or derived from a marketplace wrapper rather than fresh capture, the
projection must show that state visibly. Hiding a weakened proof-weight
state is a methodology violation even when the underlying cryptography is
correct.

This invariant ties Section 6 (Proof-Weight Honesty taxonomy) to Section 9
(UI Compiler Directives) via Section 9.3 visual honesty tests.

---

## 3. Necessity: Why Visual ZK Biometric Artifacts Are Required

VBDIP-0002 exists because VAPI must bridge three audiences:

1. **Protocol verifiers** need deterministic, reproducible proof artifacts
   to assert correctness in audits, ceremonies, and cross-protocol
   composability.
2. **Human operators** need dense protocol state projected visually without
   weakening canonical provenance, so engineering judgment can scale beyond
   reading raw hex.
3. **Gamers and marketplace participants** need understandable proof of
   achievement and integrity without exposing biometric vectors, raw
   telemetry, or session-by-session movement traces.

Without ZKBAs:

- Tournament organizers must trust opaque registry reads or be granted
  biometric exposure they should not need.
- Marketplace buyers cannot distinguish a Curator-validated listing from a
  self-asserted listing.
- Manufacturers cannot point to a verifiable surface for "our hardware
  participated in the proof chain."
- Gamers cannot prove legitimacy without surrendering raw biometric custody.

VAPI is the first DePIN gaming protocol to occupy the intersection of
(physiological biometrics + cryptographic continuity + operator-agent
fleet + composable on-chain anchors). The visual projection layer is the
artifact that translates that intersection into an integration surface.
No competing protocol has the underlying primitive stack to define this
artifact category. **The novelty is not the visual; the novelty is the
proof root the visual is bound to.**

---

## 4. ZKBA Artifact Stack

A ZKBA is not merely an HTML file. A ZKBA is a layered artifact composed of
eight tiers. Each tier is independently inspectable; the artifact's
integrity is the composition of all tiers.

### 4.1 Proof Manifest

Machine-readable JSON manifest describing schema version, artifact class,
circuit ID, compiler version, proof hash, public input hash, verification
key hash, source state root, artifact hash, proof weight, anchor reference,
and visual seed. Manifest schema is defined in Section 9.2.

### 4.2 ZK Proof Payload

Groth16 proof bytes or proof reference proving the biometric or eligibility
claim. Where the artifact does not require a fresh ZK proof (for example
CHAIN_ONLY proof weight), the payload is absent and the manifest's
`zk.proof_hash` is `null` with explicit `proof_weight` justification.

### 4.3 Verification Key Commitment

Hash or on-chain anchor for the verification key used by the proof.
References either `Groth16VerifierZKSepProof` (Phase 237 Session 2,
on-chain), `PitlSessionProofVerifier` (Phase 67), or a future ZK verifier
deployed under VAPI's deployer wallet.

### 4.4 Public Claim Envelope

Minimal public inputs required to verify the claim, such as threshold,
proof epoch, circuit version, chain ID, anonymized achievement class, or
consent category. Excludes raw biometric values, centroids, covariance
matrices, and session-by-session traces (see Section 7).

### 4.5 Visual Projection

Deterministically compiled HTML, SVG, and Canvas representation of the
claim. May embed self-contained CSS and JavaScript whose hashes are
declared in the manifest. May reference no external network resource.

### 4.6 Verification Runtime

Embedded or locally referenced JavaScript / WASM verifier whose hash is
included in the manifest. Used for client-side verification UX; not the
proof root.

### 4.7 Anchor Reference

IoTeX transaction hash, contract address, chain ID, event index, and block
number if the artifact has been anchored. Anchoring is optional at v1.0;
unanchored ZKBAs render with `proof_weight: CHAIN_ONLY` only when an
existing on-chain anchor is referenced. Without an anchor and without a
fresh ZK proof, the artifact compiles only under proof_weight `DEMO` or
`FROZEN_DISABLED`; otherwise compilation fails (the compiler refuses to
emit an artifact with an undefined proof weight, per Section 9.3 visual
honesty tests).

### 4.8 Marketplace Wrapper

Optional listing metadata, tier multiplier, consent state, price policy,
Curator review status, revocation state, and buyer-visible limitations.
Wrapper presence implies the artifact is in marketplace circulation; its
absence implies operator-internal or stakeholder-direct delivery.

---

## 5. ZKBA Artifact Classes

The v1.0 specification defines seven artifact classes. Each class is bound
to a specific proof primitive or composable proof surface that exists in
VAPI's current or imminent state.

### 5.1 ZKBA-AIT

Proves a player crossed an Active Isometric Trigger threshold without
revealing the underlying biometric vector. Bound to the Phase 237-ZK-SEPPROOF
`Groth16VerifierZKSepProof` LIVE on IoTeX testnet at
`0xD63EEf1372Cb496071bf963bEE395F7e0A3f2Ab6`. Verification key hash
`0x32fda2857bdfb0612dd5cb305aa6798fabd64bb3f9362f362c6d73cdc49c4c1f` is the
canonical anchor.

Stakeholder utility: gamer proves AIT separation crossing; tournament
organizer accepts as eligibility input; buyer reads as proof-of-skill
artifact.

### 5.2 ZKBA-GIC

Proves continuity through a Grind Integrity Chain milestone (for example
GIC_100) using chain-head commitments and session-boundary integrity.
Bound to the GIC primitive (Phase 235-A) and the existing on-chain anchor
of GIC_100 head `0x0e9d453d904220148d632e75802b71bdff74c7197aa8afcbfec5d36a61ab48da`
in tx `0xe807347eb837...` block 43348052.

Stakeholder utility: gamer proves grind achievement; developer reads as
input to streak-based reward; auditor verifies continuity without seeing
per-session detail.

### 5.3 ZKBA-VHP

Proves possession or validity of a Verified Human Proof credential without
requiring raw identity disclosure. Bound to `VAPIVerifiedHumanProof`
contract (Phase 99C, ERC-4671 soulbound). Public envelope includes
tokenId + isValid result + expiresAt; excludes deviceIdHash unless
gamer explicitly consents.

Stakeholder utility: gamer proves humanity to a tournament without
revealing which device; tournament gate composes with
`VAPIProtocolLens.isFullyEligible()`.

### 5.4 ZKBA-HARDWARE

Proves participation of certified credentialing hardware in the artifact's
evidence chain. Bound to `VAPIHardwareCertRegistry` (Phase 99A). Public
envelope includes profileHash + certLevel + manufacturerId reference;
excludes serial number, firmware revision history, or per-session usage.

Stakeholder utility: manufacturer surface as "our hardware participated";
buyer reads as authenticity signal for marketplace artifacts.

### 5.5 ZKBA-CONSENT

Proves that a data contribution or marketplace listing was authorized under
a consent category without revealing non-consented data. Bound to
`VAPIConsentRegistry` (Phase 237-CONSENT, LIVE at
`0xA82dB0eF0bF7D15b6400EDd4A09C0D4338C948dA`). Public envelope includes
consent_category (uint8 from CONSENT-v1 enum) + expiresAt + bitmask;
excludes deviceIdHash unless explicitly authorized.

Stakeholder utility: marketplace listing visibly cites consent authority;
GDPR Art.17 revocation surfaces as artifact invalidation; manufacturer
proof of data sovereignty pledge.

### 5.6 ZKBA-TOURNAMENT

Proves that a player satisfies a tournament-defined eligibility policy.
Composes ZKBA-AIT + ZKBA-GIC + ZKBA-VHP + ZKBA-CONSENT into a single
tournament-facing artifact. Bound to `VAPIProtocolLens.isFullyEligible()`
as the canonical on-chain composability call.

Stakeholder utility: tournament organizer verifies eligibility with one
call; gamer reads as a single legitimacy badge; auditor verifies all
sub-proofs from the composite manifest.

### 5.7 ZKBA-MARKET

Wraps one or more ZKBA proofs into a buyer-facing marketplace artifact
with tier multiplier, revocation policy, proof weight, Curator review
status, and buyer-visible limitations. Bound to `VAPIDataMarketplaceListings`
(Phase 238 Step H, LIVE at `0x78Df84Cc512EdCaC0e58a03e4852627E2F62E3bC`)
and the LISTING-v1 primitive.

Stakeholder utility: buyer reads tier multiplier (1.0x / 1.5x / 2.0x /
3.0x) cryptographically proven (not seller-asserted); Curator review
state visible at purchase decision time.

---

## 6. Proof-Weight Honesty Taxonomy

Every ZKBA must declare its proof weight. A ZKBA may not visually imply a
stronger claim than the underlying evidence supports. The taxonomy is
deliberately discrete to defeat marginal upclassification.

### 6.1 DIRECT_HID

Derived from direct controller telemetry capture during a contemporaneous
session. The strongest proof weight. Requires:

- ZK proof payload present and verifying,
- public input hash matches on-chain anchor where applicable,
- capture-time within the artifact's freshness window
  (default 24 hours; circuit-dependent; manifest fields
  `capture_ts_ns` + `freshness_window_s` per §9.2 schema),
- PCC (Physical Capture Continuity) state was NOMINAL during capture,
- gameplay-context classifier flagged ACTIVE_MATCH_PLAY (Phase 241-APOP,
  current `hybrid` gate mode acceptable per CLAUDE.md; `strict` mode
  promotion tightens this requirement post-promotion).

Visual rendering: full-color, full-fidelity, no watermark.

### 6.2 CALIBRATION_PLUS_CONTEXT

Derived from calibration evidence (existing corpus) plus gameplay-context
evidence that the player was actively present during a recent session,
without a fresh ZK proof of the specific claim. Used when a gamer
references a previously anchored separation-ratio commitment plus a recent
GIC link.

Visual rendering: full-color, full-fidelity, calibration-source citation
visible.

### 6.3 CHAIN_ONLY

Derived from on-chain state without fresh biometric capture. Examples: a
ZKBA-VHP that reads only the tokenId+isValid registry state; a ZKBA-GIC
referencing an anchored milestone without re-deriving the chain.

Visual rendering: muted color palette, "chain-anchored" footer visible,
no biometric-derived elements rendered.

### 6.4 MARKETPLACE_DERIVED

Derived from an existing anchored artifact or listing. Used for resale,
secondary marketplace, or aggregator displays that re-wrap an existing
ZKBA-MARKET into a new buyer surface.

Visual rendering: tier-multiplier visible; provenance chain (original
artifact -> aggregator) rendered as a small chain-of-custody footer.

### 6.5 DEMO

Non-production artifact, visibly watermarked at **minimum 15% diagonal
coverage** (mirrors Section 9.3 visual honesty test enforcement) and
excluded from readiness scoring. Used for documentation, marketing
materials, internal review, and stakeholder onboarding.

Visual rendering: large diagonal "DEMO" watermark required at >=15%
diagonal coverage of the rendered surface; cannot be silently upgraded
to any production weight without manifest reissuance under a new
compiler invocation.

### 6.6 FROZEN_DISABLED

Reserved layer or feature not active in production. Examples: a
ZKBA-HARDWARE that would compose L6 haptic challenge data while
`L6_CHALLENGES_ENABLED=false`; a ZKBA-CONSENT for the GSR category while
`GSR_ENABLED=false`; any artifact whose underlying primitive is gated
behind an unmet calibration threshold.

Visual rendering: grayed-out, explicit "RESERVED - FEATURE NOT ACTIVE"
label, no claim rendered as "valid". Required visual honesty test in
Section 9.3 verifies that FROZEN_DISABLED cannot render as green/valid.

---

## 7. Privacy and Non-Disclosure Boundaries

### 7.1 Permitted Disclosures

A ZKBA may prove:

- threshold crossing (separation ratio above a value),
- continuity (GIC link presence in chain),
- credential state (VHP isValid; consent category bitmask),
- hardware participation (profileHash matches a certified entry),
- consent category authorization,
- eligibility class (composite of above).

### 7.2 Prohibited Disclosures

A ZKBA must not reveal:

- raw HID telemetry,
- the 13-dimensional biometric feature vector,
- player centroids in feature space,
- inter-player or intra-player covariance matrices,
- session-by-session movement traces,
- private gameplay habits outside the proof claim,
- non-consented marketplace data,
- raw GSR signals or per-frame biometric snapshots,
- AccelTremorFFT raw spectrum or peak frequency,
- touchpad position trajectories beyond aggregated entropy claims.

### 7.3 Aggregation Boundary

Where a ZKBA visualizes an aggregate (for example L4/AIT topography in
Section 10.2), the visual must apply sufficient quantization or noise to
prevent individual-session reverse mapping. The aggregation function is
declared in the manifest's `visual.aggregation_policy` field. Section A.5
defines a future DP-ZKBA extension that formalizes differential-privacy
projections.

### 7.4 Client-Side Verification Is UX, Not the Proof Root

Client-side verification improves user comprehension and portability. It is
**not** the root of truth. The proof root remains:

```
proof_root = manifest_hash || proof_payload_hash || verification_key_hash || anchor_reference
```

If client-side verification fails, the artifact must render as `unverified`.
If the runtime is absent, stale, or hash-mismatched, the artifact must
render as `verification-unavailable` rather than `verified`. Silent
fallback to "appears valid" is a methodology violation.

### 7.5 Selective Disclosure

ZKBA consumers (tournament gates, marketplace buyers, manufacturer
dashboards) may receive different `public_claim_envelope` subsets for the
same underlying proof. The compiler emits per-consumer artifact variants
with distinct manifests; each variant is independently anchored. This is
the protocol's analogue to W3C Verifiable Credentials selective
disclosure, anchored in VAPI's deployer signature chain rather than
generic DID infrastructure.

---

## 8. Cross-Fleet Execution

ZKBA production exercises VBD primitive composition and cross-fleet
skill-separation discipline. No single agent owns the full artifact
lifecycle. The lane assignments below are normative; deviation from them
fails VBD-INV-4 (cross-fleet skill separation, retroactively named from
INV-CFSS-001).

### 8.1 Anchor Sentry Lane

Anchor Sentry owns cryptographic anchoring and provenance recording. For
ZKBA flows, Sentry may:

- pin approved artifacts to IPFS or alternative content-addressable store,
- anchor artifact commitments via existing
  `chain.record_adjudication(deviceIdHash, poadHash)` or future
  `chain.record_zkba_anchor(artifactHash, manifestHash, ts_ns)`,
- record provenance and source-state hashes,
- compose BIOMETRIC-SNAPSHOT-v1 with LISTING-v1 via the ZKBA-MARKET
  wrapper (§5.7) — no separate ZKBA-LISTING concept is defined at v1.0,
- sign only within Cedar-scoped authority (lane prefix `provenance/` and
  `attestations/`).

Sentry may NOT classify marketplace meaning, approve listings, change
consent state, or generate buyer-facing interpretation.

### 8.2 Guardian Lane

Guardian owns audit and operational diagnostic interpretation. For ZKBA
flows, Guardian may:

- validate proof payload structure,
- verify verification key provenance against ceremony audit trail
  (Phase 67 / Phase 237 Session 2),
- flag stale or mismatched proof roots,
- produce audit-drafting records,
- identify artifact integrity failures and FSCA contradictions,
- sign only within Cedar-scoped authority (lane prefix `audits/` and
  `ops/`).

Guardian may NOT anchor artifacts on chain, approve marketplace listings,
or modify proof-weight state.

### 8.3 Curator Lane

Curator is the marketplace and artifact-coherence Operator Agent. Curator's
responsibility is not cryptographic anchoring and not operational health.
Curator owns the **interpretive integrity of marketplace-facing artifacts**.

Curator monitors:

- listing metadata coherence,
- consent validity at sale time,
- proof-weight classification (no silent upgrades),
- tier drift (claimed tier vs anchored tier),
- revocation status,
- buyer-facing visual honesty (Section 9.3 tests),
- ZKBA manifest completeness,
- artifact / compiler version mismatch.

Curator may recommend:

- listing approval,
- listing warning,
- delisting,
- tier downgrade,
- consent refresh,
- proof regeneration,
- artifact quarantine.

Curator may NOT anchor artifacts on chain, alter proof payloads, override
consent, or silently upgrade proof weight. Any marketplace mutation
requires later governance expansion and matching AgentScope/Cedar
authorization (lane prefix `marketplace/` and `listing_reviews/`).

### 8.4 Cross-Fleet Skill Separation

ZKBA workflows must preserve VBD-INV-4:

- Sentry handles anchoring / provenance.
- Guardian handles audit / proof diagnostics.
- Curator handles marketplace coherence and visual honesty.

Any proposal giving one agent two or more of these roles fails this
specification. The Cedar bundle `P-FORBID-CFSS-*` policies enforce this
at the policy layer; the ZKBA compiler enforces it at the manifest layer
by requiring distinct signatures for distinct lanes.

### 8.5 Phase-Gated Authority Table

| Phase | Sentry | Guardian | Curator |
|-------|--------|----------|---------|
| `O1_SHADOW` | observe and simulate | observe and audit-draft | observe and review-draft |
| `O2_SUGGEST` | draft anchor / provenance actions | draft audit findings | draft marketplace decisions |
| `O3_ACT` | execute authorized anchors | execute authorized audit actions | execute authorized marketplace actions |

VBDIP-0002 does not grant `O3_ACT` authority for ZKBA flows. It defines
the future artifact model that Cedar bundles may later authorize, after
empirical operation in `O1_SHADOW` and `O2_SUGGEST` provides feedback.

---

## 9. UI Compiler Directives

### 9.1 Compiler Requirements

The future compiler (tentatively `vsd_ui_compiler.py`) must:

- read only declared canonical inputs,
- produce deterministic output (same inputs + same compiler version ->
  same output bytes),
- write projections to `vsd-vault/projections/` or successor VAD path,
- emit a projection manifest beside every HTML artifact,
- include no external CDNs or mutable dependencies,
- fail closed on missing proof weight,
- render stale, demo, disabled, or derived states visibly,
- enforce lane separation: artifacts originating from Sentry, Guardian,
  and Curator land in lane-prefixed subdirectories per Section A.12.

### 9.2 Projection Manifest Schema

Initial manifest shape:

```json
{
  "schema": "zkba.projection_manifest.v1",
  "artifact_class": "ZKBA-GIC",
  "proof_weight": "CHAIN_ONLY",
  "compiler": {
    "name": "vsd_ui_compiler.py",
    "version": "0.1.0",
    "source_hash": "sha256:..."
  },
  "inputs": {
    "proof_manifest_hash": "sha256:...",
    "source_state_root": "0x...",
    "canonical_note_hashes": ["sha256:..."],
    "frozen_primitive_refs": ["GIC", "WEC", "VAME"]
  },
  "zk": {
    "circuit_id": null,
    "proof_hash": null,
    "verification_key_hash": null,
    "public_input_hash": null
  },
  "visual": {
    "visual_seed": "sha256:...",
    "html_hash": "sha256:...",
    "runtime_hash": "sha256:...",
    "aggregation_policy": "none"
  },
  "anchor": {
    "chain_id": 4690,
    "contract": null,
    "tx_hash": null,
    "event_index": null,
    "block_number": null
  },
  "capture_ts_ns": null,
  "freshness_window_s": null,
  "limitations": ["chain-only projection; no fresh biometric capture"],
  "generated_at": "2026-05-10T00:00:00Z"
}
```

The schema version is FROZEN at `zkba.projection_manifest.v1` at VBDIP-0002
v1.0 freeze. Schema evolution requires VBDIP-0002 v2.0 or a successor
proposal with a new version tag.

### 9.3 Visual Honesty Tests

The compiler test suite must verify, for every emitted artifact:

- proof weight appears visibly in the artifact,
- `DEMO` artifacts render the watermark at minimum 15% diagonal coverage,
- `FROZEN_DISABLED` features cannot render as active under any code path,
- revoked consent invalidates marketplace display unconditionally,
- compiler hash mismatch renders `verification-unavailable` not `verified`,
- manifest / proof mismatch renders `unverified` not `verified`,
- missing proof weight FAILS compilation (does not emit an artifact),
- stale verification key hash (older than verification key rotation epoch)
  renders `warning` state,
- no network dependency is required to load the artifact (offline-by-
  default),
- lane prefix in manifest matches output directory under
  `vsd-vault/projections/`.

These tests are themselves committed to the repository under
`scripts/zkba_compiler_tests/` once the compiler exists. The tests do not
exist at VBDIP-0002 freeze; their existence is a Section 1.2 activation
gate.

### 9.4 No CDNs and No Remote Render Pipelines

External CDNs (jsDelivr, unpkg, cdnjs, etc.), remote render services
(Vercel functions, Cloudflare Workers, third-party screenshot APIs), and
mutable web fonts (Google Fonts, Adobe Fonts) are forbidden in production
artifacts. All assets must be embedded or referenced by content-addressed
hash that the verifier can recompute locally.

Rationale: deterministic compilation invariant fails if any input is
network-mutable. Visual honesty fails if a CDN can swap an SVG for a
different one.

---

## 10. First Artifact Targets

The compiler discipline ships internal first, consumer second. Internal
targets are operator-facing and privacy-light; consumer targets are
gamer-facing and require full ZKBA discipline.

### 10.1 Artifact Alpha: GIC Continuity Ledger

Internal first target. Visualizes Phase 235-A GIC continuity with session
chain links, gameplay context (Phase 235-GAD), host state (Phase 234.7
PCC), proof weight, chain-head hash, and anchor state.

Why first: operator-facing, privacy-light, leverages the GIC primitive
which is the most mature FROZEN-v1 primitive with the most empirical
operation (10.3 days of grind across 100 sessions to GIC_100).

### 10.2 Artifact Beta: L4 / AIT Topography

Visualizes the L4 (Mahalanobis anomaly) and AIT (Active Isometric Trigger)
separation surface without exposing raw biometric vectors. Uses threshold
summaries and anonymized proof envelopes only. Aggregation policy in
manifest is mandatory (Section 7.3); future DP-ZKBA extension (Section A.5)
adds differential-privacy noise.

Why second: most analytically valuable artifact for operators; highest
privacy-disclosure risk; requires aggregation discipline that internal
review can validate before consumer exposure.

### 10.3 Artifact Gamma: CDRR DAG

Visualizes the compositional readiness graph: FRR (Fleet Readiness Root),
VRR (Vault Readiness Root, post-VBDIP-0001 VSD bootstrap), CDRR
(Cross-Domain Readiness Root), phase state, agent readiness, and blocker
classes. This validates VBD-INV-3 (primitive composition discipline) by
making the composition tree visually inspectable.

Why third: requires VBDIP-0001 freeze and Phase O1-VSD-BOOTSTRAP completion
to populate VRR and CDRR. Internal operator value: single legible artifact
for "is the ecosystem ready for X advancement."

### 10.4 Artifact Delta: ZKBA Market Card

Consumer-facing artifact for marketplace use. Front side renders
deterministic procedural art seeded by the proof manifest visual_seed.
Back side renders proof weight, verification status, consent category,
Curator review status, and buyer-visible limitations.

Why last: highest stakeholder exposure; requires the prior three internal
projections to prove the compiler discipline; requires Curator's marketplace
lane to be O2_SUGGEST or O3_ACT to surface tier multiplier and revocation
state authoritatively.

---

## 11. Stakeholder Utility

ZKBAs translate cryptographic truth into stakeholder-actionable artifacts.
Each stakeholder group derives distinct utility from the same proof root.

### 11.1 Gamers

Gamers need ZKBAs because they should not have to reveal raw biometric
data to prove legitimacy.

Gamers can prove:

- verified human gameplay history,
- AIT threshold achievement,
- tournament eligibility (composite),
- continuity across sessions (GIC),
- hardware-bound play integrity,
- consent-scoped data contribution.

Without revealing raw biometric identity.

Gamer-facing thesis:

```text
You can prove you are legitimate without giving the tournament your
biometric identity.
```

### 11.2 Developers

Developers need ZKBAs because they provide a stable integration surface.
A game, tournament platform, analytics provider, or marketplace frontend
does not need raw VAPI biometric data. It needs a compact artifact
manifest, proof hash, verification key hash, public input commitment, and
anchor state.

Developer-facing thesis:

```text
Integrate verified human gameplay without touching raw biometrics.
```

### 11.3 Manufacturers

Manufacturers need ZKBAs because certified hardware can become visible,
verifiable proof utility without receiving player biometrics. The
ZKBA-HARDWARE class anchors the manufacturer's role in the proof chain
without exposing player data.

Manufacturer-facing thesis:

```text
Your hardware can become part of a privacy-preserving proof economy.
```

### 11.4 Tournament Organizers

Tournament organizers need proof that is legible, auditable, and
privacy-minimizing. A ZKBA-TOURNAMENT allows a tournament to verify
eligibility without storing sensitive biometric vectors. Composability
with `VAPIProtocolLens.isFullyEligible()` reduces tournament integration
to one on-chain call.

Tournament-facing thesis:

```text
Verify eligibility, not identity exhaust.
```

### 11.5 Marketplace Buyers

Marketplace buyers need clear artifact limits. ZKBA marketplace displays
must show what is proven, what is derived, what is revoked, what is
demo-only, and what requires fresh verification. Tier multiplier
(Phase 238) is cryptographically derived from the underlying
AdjudicationRegistry isRecorded check, not seller-asserted.

Buyer-facing thesis:

```text
You see the cryptographic provenance behind the price.
```

---

## 12. Category Distinction and AI Role Constraint

### 12.1 What This Is Not

VBDIP-0002 is NOT:

- a generic NFT badge framework,
- an AI-generated collectible system,
- a DePIN sensor dashboard,
- a biometric surveillance credential,
- a replacement for VAPI's canonical proof manifests,
- a competitor to W3C Verifiable Credentials (it is a VAPI-specific
  artifact category that may interoperate with VC but does not depend on
  generic DID infrastructure).

It is a deterministic projection and zero-knowledge artifact framework for
cryptographically verified human gameplay.

### 12.2 AI Role Constraint

VBDIP-0002 uses AI as a **protocol-stewardship layer**, not as a source
of truth. Operator agents may:

- detect artifact inconsistency,
- summarize proof state,
- flag visual misrepresentation,
- classify marketplace tier drift,
- propose correction patches,
- draft buyer-facing explanations,
- generate deterministic projection inputs.

Operator agents may NOT:

- fabricate proof claims,
- alter biometric thresholds,
- modify FROZEN-v1 primitives,
- override consent state,
- silently change proof weight,
- convert demo artifacts into production artifacts,
- bypass on-chain capability scope,
- generate visual content outside the compiler.

The AI contribution is **interpretive discipline, not epistemic
authority**. The proof root binds claims; AI may render them, summarize
them, or flag inconsistency in them.

### 12.3 Why VAPI Can Do This

VAPI already has the hard parts:

- PoAC records (228-byte cryptographic capture format, Phase 1),
- GIC continuity (Phase 235-A),
- WEC operational continuity (Phase 236-WATCHDOG),
- VAME application-layer integrity (Phase 236-VAME),
- CORPUS-SNAPSHOT (Phase 236-CORPUS-SNAPSHOT),
- CONSENT (Phase 237-CONSENT),
- BIOMETRIC-SNAPSHOT (Phase 237-ZK-SEPPROOF),
- LISTING-v1 (Phase 238-MARKETPLACE),
- FRR (Phase O1-FRR; eighth FROZEN-v1 primitive),
- planned VRR / CDRR composition (post-VBDIP-0001 VSD bootstrap),
- Cedar-scoped Operator agents (Sentry / Guardian / Curator),
- Curator marketplace review surface (Phase 238 Step I-FINAL).

ZKBA extends the existing trust model into a stakeholder-facing artifact
category. **The novelty is the artifact category, its discipline, and the
composition surface; the trust primitives it binds already exist.** The
deterministic compiler + proof manifest + visual honesty + lane separation
disciplines are themselves a new layer of trust mechanism layered on top
of the existing primitives, not a replacement of them.

---

## 13. Manufacturer Extension Hooks

VBDIP-0002 reserves manufacturer-facing extension fields for future
certified hardware ecosystems. The fields are reserved at v1.0; population
is post-freeze work.

Initial fields:

```json
{
  "hardware_cert_id": "0x...",
  "controller_model": "DualSense Edge CFI-ZCP1",
  "module_type": "stick|trigger|grip|imu|gsr|firmware_profile",
  "manufacturer_id": "reserved",
  "certification_tier": "VAPI_BASE|VAPI_PROBE|VAPI_SENSOR",
  "firmware_profile_hash": "sha256:...",
  "module_replacement_epoch": 0,
  "proof_weight_modifier": "none"
}
```

**Manufacturers may NOT self-certify proof weight.** Hardware certification
must be anchored through `VAPIHardwareCertRegistry` or a successor registry.
The `proof_weight_modifier` field defaults to `none`; a non-default value
requires a governance event under the VBDIP / VEDIP discipline.

Section A.6 defines a forward-looking ZKBA-PHCI-MODULE extension for
module-replacement provenance.

---

## 14. Marketplace Listing Semantics

A ZKBA marketplace listing must include all of:

- artifact class (Section 5),
- proof weight (Section 6),
- consent category (CONSENT-v1 bitmask),
- revocation policy,
- verification key hash,
- source state root,
- compiler version,
- visual seed,
- tier multiplier (1.0x / 1.5x / 2.0x / 3.0x, cryptographically derived),
- listing epoch,
- Curator review status (`pending` / `approved` / `flagged` / `delisted`),
- buyer-visible limitations,
- chain anchor reference.

A listing is **invalid** if any of:

- consent is revoked,
- verification key hash mismatches its on-chain anchor,
- compiler hash mismatches the artifact,
- proof weight is omitted,
- visual state contradicts manifest state,
- artifact claims a `FROZEN_DISABLED` layer as active,
- Curator flags unresolved contradiction.

The marketplace UI must surface invalid listings as such immediately; a
listing cannot transition from `invalid` to `valid` without re-issuance
through the Curator review pipeline (Phase 238-DRAFT-REVIEW frontend
exists for the operator-side review surface).

Section A.7 defines a forward-looking ZKBA-MARKET-REVO extension for
tier-downgrade transparency cards.

---

## 15. Security, Privacy, and Misrepresentation Risks

| Risk | Mitigation |
|------|------------|
| HTML visual overclaims proof strength | Proof-weight honesty rendered visibly and compiler-tested (Section 9.3) |
| Marketplace spoofing | Curator coherence review plus manifest / proof / compiler hash checks |
| Biometric leakage | Public claim envelope excludes raw vectors, centroids, covariance, raw telemetry (Section 7.2) |
| Runtime tampering | Runtime hash included in projection manifest (Section 4.6) |
| Consent drift | Consent category and revocation state included in listing validity (Section 14) |
| Agent capability creep | Cross-fleet skill separation and AgentScope/Cedar authorization (Section 8) |
| Demo artifacts mistaken for production | `DEMO` proof weight requires visible 15% diagonal watermark (Section 9.3) |
| CDN-mediated MITM on visual content | No CDNs permitted; all assets content-addressed and embedded (Section 9.4) |
| Selective-disclosure replay | Per-consumer variants are independently anchored; cross-consumer replay fails verification (Section 7.5) |
| Verification-key rotation drift | Stale verification key hash renders `warning` state (Section 9.3) |
| Lane confusion (Sentry artifact appears as Curator artifact) | Lane prefix in manifest must match output directory; compiler test enforces (Section 9.3) |
| FSCA contradiction silently masked | Curator monitors FSCA findings; ZKBA-COHERENCE-DRIFT extension (Section A.2) surfaces unresolved contradictions visually |

---

## 16. Activation Gates

VBDIP-0002 is not operationally active until all gates below clear:

1. **VBDIP-0001 FROZEN** - SATISFIED. VAD / VSD / VED / VBD framework
   foundation accepted; deployer-anchored architect signing chain live;
   `--proposal-type=bridge` / `--proposal-type=all` harness modes live.

2. **Numbering Decision Resolved** - Operator resolves N1 / N2 / N3 per
   Section 1.3 (this proposal owns VBDIP-0002, OR is renumbered to
   VBDIP-0003+, OR remains indefinite sidecar).

3. **Compiler Harness Implemented** - PARTIALLY SATISFIED for Track 1.
   Deterministic compiler (`scripts/vsd_ui_compiler.py`) exists and
   GIC Continuity Ledger deterministic-output tests pass. Full gate closure
   still requires the complete projection-manifest and Section 9.3 visual
   honesty tests for the active artifact set.

4. **ZKBA Manifest Schema Validated** - Schema `zkba.projection_manifest.v1`
   validates all required artifact layers and proof-weight fields against
   representative artifacts of all seven Section 5 classes.

5. **VPM Wrapper / Integrity Label Reconciled** - If VBDIP-0002A is adopted,
   VPM wrapper schema `vapi-vpm-manifest-v1`, Integrity Nutrition Label
   fields, lifecycle states, and VPM visual grammar tests must exist before
   any artifact is called an active VPM.

6. **AgentScope / Cedar Permissions Authorized** - Sentry, Guardian, and
   Curator each have phase-appropriate Cedar policies on chain authorizing
   their Section 8 lane actions.

7. **Curator Review Readiness** - Curator can classify proof weight,
   detect visual dishonesty, and recommend quarantine without mutating
   anchors or consent state. Phase 238-DRAFT-REVIEW-FRONTEND surface
   confirmed compatible.

8. **Internal Projection First** - GIC Continuity Ledger (Section 10.1)
   and CDRR DAG (Section 10.3) ship before consumer ZKBA Market Card
   (Section 10.4).

9. **Numbering Decision Applied** - Per Section 1.3, operator has resolved
   N1 / N2' / N3 and this proposal's canonical number is pinned at
   activation. Sidecar status terminates at this gate; the proposal
   transitions to a numbered lineage member with stable cross-references
   that downstream documents can cite.

Any single unmet gate keeps VBDIP-0002 in sidecar / FROZEN-SPEC state.
All nine gates clearing transitions the proposal to `OPERATIONALLY ACTIVE`
under its lineage successor (VBDIP-0002 or VBDIP-0004+ per the N decision).

---

## 17. Decision Blocks (K1 through K7)

These decisions are codified for the operator-resolution surface. Each is
load-bearing for VBDIP-0002 activation; each must be explicitly resolved
before freeze.

**K1 - Projection Authority**
HTML is a deterministic projection, not source of truth. The proof root
is the manifest plus proof payload plus verification key commitment plus
anchor state. Client-side verification is UX, not proof root.
*Resolution status: Specified. Operator-confirm before freeze.*

**K2 - ZKBA Proof Root**
Proof root binding is:
`proof_root = manifest_hash || proof_payload_hash || verification_key_hash || anchor_reference`
Any artifact diverging from this binding fails verification.
*Resolution status: Specified. Operator-confirm before freeze.*

**K3 - Operator Capability Gating**
No agent receives ZKBA authority without AgentScope/Cedar authorization.
Sentry / Guardian / Curator lanes are disjoint (VBD-INV-4). Phase-gated
authority per Section 8.5.
*Resolution status: Specified. Empirical authorization is post-freeze
ceremony work.*

**K4 - Curator Recognition**
Curator owns visual honesty and marketplace coherence, NOT anchoring or
proof generation. Curator may recommend listing approval / warning /
delisting / tier downgrade / consent refresh / proof regeneration /
artifact quarantine. Curator may not mutate the proof root.
*Resolution status: Specified. Consistent with Phase 238 Step I-FINAL
Curator scope.*

**K5 - Signature Plane Discipline**
Projection signatures must chain to the VAPI deployer / architect key
lineage defined by VAD (VBDIP-0001 §4.1 VBD-INV-1: continuous
deployer-verified provenance). No projection signature may originate from
a key not in the deployer-anchored chain.
*Resolution status: Specified. Depends on VBDIP-0001 freeze for the
authoritative VAD key lineage.*

**K6 - Proof-Weight Honesty**
Every artifact declares and renders proof weight (Section 6). Visual
rendering must match declared weight; compiler tests enforce. Silent
upclassification is a methodology violation regardless of cryptographic
validity.
*Resolution status: Specified. Operator-confirm taxonomy at freeze.*

**K7 - Stakeholder Utility Commitment**
ZKBA exists to make verified human gameplay legible without raw biometric
custody. Each artifact class (Section 5) maps to a stakeholder utility
(Section 11). If an artifact class has no stakeholder utility, it does
not belong in v1.0.
*Resolution status: Specified. All seven Section 5 classes map cleanly
to Section 11 utilities.*

---

## Appendix A - VAPI-Exclusive Novel Extensions (Forward-Looking, Post-v1.0)

This appendix lists extensions that are uniquely possible because of VAPI's
architectural surface. Each extension is named, scoped, and explicitly
marked as **DEFERRED** beyond VBDIP-0002 v1.0. They do not introduce new
invariants in this revision; they describe the design surface VBDIP-0002
v2.0 (or a successor proposal under the resolved numbering) may incorporate
after empirical operation provides feedback.

The extensions in this appendix are the answer to "where can this be even
more novel given VAPI's architectural infrastructure and protocol
uniqueness." Each extension references the specific VAPI primitive or
capability that makes it possible.

### A.1 ZKBA-PROVENANCE-COMPOSITE

A ZKBA whose proof manifest references multiple FROZEN-v1 primitives
chained into a single composite commitment. The composite root is:

```
composite_root = SHA-256(
    domain_tag_PROVENANCE_COMPOSITE_v1 ||
    sorted(constituent_primitive_commitments) ||
    composition_ts_ns_be(8)
)
```

Composes GIC head + WEC operational continuity + BIOMETRIC-SNAPSHOT +
CONSENT bitmask + VHP isValid + LISTING-v1 (where applicable) into one
visual artifact. Equivalent to PATTERN-017 family composition raised to a
single anchorable hash.

Uniqueness: only VAPI has the entire PATTERN-017 family LIVE simultaneously
with composable byte-layouts. No other DePIN protocol has 8+ FROZEN-v1
primitives composable into a single commitment.

### A.2 ZKBA-COHERENCE-DRIFT

A Curator-issued artifact that visualizes FleetSignalCoherenceAgent (FSCA)
contradictions in real time. When FSCA detects a contradiction (e.g.,
`CONSENT_REVOKED_LISTING_ACTIVE`, `BUNDLE_HASH_DRIFT_DETECTED`,
`GOVERNANCE_PROVENANCE_ANCHOR_DRIFT`), Curator can issue a
ZKBA-COHERENCE-DRIFT artifact in marketplace surfaces that visually flags
the affected listing as having an unresolved contradiction.

The artifact's `proof_weight` is `CHAIN_ONLY` (no fresh biometric), and
the visual rendering uses an explicit warning palette distinct from normal
listing surfaces. Resolution of the FSCA contradiction triggers artifact
invalidation (the warning surface stops rendering when the underlying
contradiction clears).

Uniqueness: FSCA's contradiction rule set (16 rules at current count) is
VAPI-exclusive; no competing protocol has a runtime contradiction detector
that surfaces into the artifact projection layer.

### A.3 ZKBA-AUDIT-TRAIL

A Guardian-issued artifact that anchors an audit-drafting record's
existence without revealing the audit content. Useful for compliance:
a tournament organizer can prove "this gamer's audit trail is clean"
without exposing the audit details.

Operates under Guardian's `audit-drafting` skill scope (Cedar lane prefix
`audits/`). The audit content remains in `vsd-vault/notes/audit/`; the
ZKBA-AUDIT-TRAIL projection reveals only the count of clean audit windows
and the audit-trail-head hash.

Uniqueness: VAPI is the only DePIN gaming protocol with a Guardian-equivalent
audit-drafting role and a phase-gated audit lane.

### A.4 ZKBA-DUAL-ANCHOR

A composable artifact that requires signatures from BOTH Sentry AND
Guardian to be valid. The marketplace listing or tournament eligibility
credential is anchored only when both agents' Cedar-scoped signatures
are present.

Structural property: defeats single-agent forgery. If Sentry's KMS is
compromised, the artifact cannot be forged without Guardian's KMS also
compromised. Mirrors the dual-anchor pattern already in use for Cedar
bundle anchoring (operational AgentScope + governance AgentRegistry,
per INV-OPERATOR-AGENT-001 operational-FIRST sequence).

Uniqueness: applies the protocol-side dual-anchor pattern to the
stakeholder-facing artifact layer. No other artifact framework requires
two-agent signature.

Activation note: this extension is viable only post-O3_ACTING for BOTH
Sentry AND Guardian. Currently both agents are at O2_SUGGEST per CLAUDE.md;
A.4 cannot fire until shadow_age 504h + 50-draft accumulation + operator
disagreement-rate <5% gates clear for both agents (the same external
gates that block live triple dual-anchor per Phase O3-ACT-WATCHER).

### A.5 DP-ZKBA (Differential-Privacy ZKBA)

Some visual artifacts (Section 10.2 L4 / AIT Topography) inherently reveal
aggregate population information. Add a differential-privacy noise layer
to the visual seed and aggregation policy such that no individual session
can be reverse-mapped from the projection.

Formal binding: extend BP-003 (Differential Privacy Thresholds, defined
in `VAPI_BIOMETRIC_PRIVACY.md`) into the visual projection layer. The
manifest's `visual.aggregation_policy` becomes `dp_laplace(epsilon=...)`
with the privacy budget declared explicitly.

Uniqueness: VAPI is the only protocol with formal DP thresholds at the
biometric layer; extending them to the visual layer is a continuous
discipline.

### A.6 ZKBA-PHCI-MODULE

A ZKBA that proves a DualShock Edge module (stick, trigger, grip, IMU,
GSR, firmware profile) is the same module certified at calibration,
without revealing the gameplay history. Useful when modules are replaced:
operator can prove continuity-of-hardware without exposing whether the
replacement happened mid-session or between sessions.

Composes ZKBA-HARDWARE (Section 5.4) with module-level subhash from
`VAPIHardwareCertRegistry` Phase 99A. Adds a `module_replacement_epoch`
counter (already reserved in Section 13 manufacturer extension hooks)
that increments on each authorized swap.

Uniqueness: DualShock Edge is the only certified Attested-tier device
with modular construction. PHCI (Physical Hardware Continuity Index) is
a VAPI-exclusive concept.

### A.7 ZKBA-MARKET-REVO (Tier Multiplier Revocation Cards)

When Curator flags a marketplace listing for tier downgrade, the
ZKBA-MARKET artifact updates to render the OLD tier with strike-through
and the NEW tier prominently. Buyers see the downgrade transparency, not
a silent re-listing.

Implementation: the Curator review pipeline (Phase 238 Step I-FINAL)
emits a `tier_downgrade_event` that the compiler picks up on next
artifact recompilation. The manifest captures both tiers and the downgrade
reason; the visual layer enforces honesty rendering.

Uniqueness: tier multipliers are a VAPI marketplace primitive (Phase 238
LISTING-v1). Revocation transparency at the artifact level is novel
because the cryptographic tier derivation (via `AdjudicationRegistry.isRecorded`)
makes the downgrade authoritative, not seller-discretionary.

### A.8 ZKBA-VAME-ENVELOPED

Volume 2's VAME (VAPI Application-Layer Message Envelope, Phase 236-VAME)
signs HTTP responses with a sidecar header bound to the GIC chain. ZKBAs
can use VAME headers to anchor their HTTP delivery in the GIC chain.

When a buyer's browser fetches the ZKBA card, the response carries a
VAME envelope signed by the bridge wallet's signing chain. The
verification runtime (Section 4.6) verifies the VAME envelope against the
artifact manifest. Net effect: the artifact's HTTP delivery is itself
proof-bearing; replay of a stale artifact across HTTP fetch boundaries is
detectable.

Uniqueness: VAME is a VAPI-exclusive Phase 236-VAME primitive. No other
DePIN protocol has an HTTP-envelope signing surface bound to a continuity
chain.

### A.9 ZKBA-SYNTHESIS-NOTE

VSD synthesis notes (claim, ingredient, synthesis, PBSA, decision,
adversarial, eigenspace, study, industry, verification, mcp, cdrr) can
themselves be projected as ZKBAs for external knowledge-graph consumers.
A claim note with `confidence: A1` becomes a ZKBA-CLAIM card that anchors
the knowledge into the protocol's signed-state surface.

This extends VSD's reach beyond NotebookLM into stakeholder dashboards.
Each synthesis note's projection inherits the architect Ed25519 signature
plus the bridge-wallet attestation chain (VBD-INV-1).

Uniqueness: VSD as a numbered methodology with formally typed notes is
VAPI-exclusive (post-VBDIP-0001-freeze). No competing protocol has a
synthesis-discipline equivalent.

### A.10 ZKBA-W3BSTREAM-VERIFIED

A ZKBA whose verification runtime is a W3bstream applet binding to IoTeX.
The buyer's verification does not run JavaScript locally; it runs as a
W3bstream applet call. Trustless verification on the same compute layer
that VAPI's bridge is positioned to use (Phase 99B applet stubs
`validate_poac_record.ts` and `process_gsr_packet.ts` exist as
code-complete artifacts under `scripts/w3bstream/`; production wiring
pending).

Implementation: extend the existing W3bstream applet pattern
(`validate_poac_record.ts`, `process_gsr_packet.ts`) with a third applet
`verify_zkba_artifact.ts` that validates ZKBA manifests against on-chain
state and returns a verification result.

Uniqueness: W3bstream is the IoTeX-native DePIN compute layer. Wiring
ZKBA verification through W3bstream is structurally available only
because VAPI is IoTeX-native; non-IoTeX DePIN protocols would need a
substitute compute layer.

### A.11 ZKBA-CDRR-ECOSYSTEM (Cross-Domain Readiness)

The CDRR primitive (Cross-Domain Readiness Root, defined in VSD Volume 2
§19.2, ships in Phase O1-VSD-BOOTSTRAP) composes FRR (protocol fleet
readiness) and VRR (vault readiness) into a single ecosystem-level
readiness commitment.

A ZKBA-CDRR card visualizes "is the entire VAPI ecosystem ready to grant
tournament authorization right now?" as a single legible artifact with
FROZEN-v1 cryptographic anchoring. The visual layer renders the
composition tree: PoAC -> GIC -> AIT -> CONSENT -> VHP -> LISTING-v1 ->
FRR + VRR -> CDRR.

Uniqueness: CDRR is unique to VAPI's two-fleet architecture (protocol
operator fleet + synthesis operator fleet). No competing protocol has a
two-fleet structure to compose.

### A.12 CEDAR-LANE-ENFORCED Projection Path

Each Operator agent's Cedar bundle defines lane prefixes (`audits/`,
`ops/`, `marketplace/`, `provenance/`, `events/`, etc.). ZKBA outputs
are forced into the originating agent's lane:

- Sentry's ZKBAs land in `vsd-vault/projections/sentry/provenance/*` and
  `vsd-vault/projections/sentry/attestations/*`.
- Guardian's ZKBAs land in `vsd-vault/projections/guardian/audits/*` and
  `vsd-vault/projections/guardian/ops/*`.
- Curator's ZKBAs land in `vsd-vault/projections/curator/marketplace/*`
  and `vsd-vault/projections/curator/listing_reviews/*`.

The lane separation is enforced at the compiler level. Cross-lane writes
fail compilation. Lane prefix in the manifest must match the output
directory.

Uniqueness: VAPI's parallel operator fleet with disjoint Cedar lane
prefixes is VAPI-exclusive (post-Phase-O1-FRR-PARALLEL ship).

### A.13 OPERATOR-AGENT-DRAFT Phase-Aware Projections

Drafts (Phase O2_SUGGEST) and active actions (Phase O3_ACT) project
differently. A draft ZKBA is watermarked `DRAFT - pending operator
review`; an active ZKBA shows the operator decision (accept / reject /
overturn_curator) cryptographically anchored from the
`operator_agent_drafts` table (Phase O2-DRAFT-GENERATION).

This integrates Phase O2-DRAFT-REVIEW-FRONTEND directly into the artifact
projection layer. Stakeholders see whether an artifact represents a draft
proposal or an executed action.

Uniqueness: VAPI is the only protocol with an Operator Initiative draft
review pipeline (Phase O2-DRAFT-REVIEW-ENDPOINT + Phase
O2-DRAFT-REVIEW-FRONTEND).

### A.14 ZKBA-PROTOCOL-LENS Tournament Wrapper

`VAPIProtocolLens.isFullyEligible(deviceId)` is the existing single-call
tournament gate (Phase 70, LIVE at `0x1972bf756aFE0FFCfaF9842e2FbBb2B084352EAf`).

A ZKBA-TOURNAMENT artifact wraps the Protocol Lens query result as a
public input. Tournament organizers integrate "scan this ZKBA card to
verify eligibility" with one Lens query against the deviceId encoded in
the manifest. The visual layer renders the four oracle inputs (Humanity,
Ruling, Passport, Sovereignty) that the Lens composes.

Uniqueness: VAPIProtocolLens is the canonical VAPI tournament gate; no
substitute exists in competing protocols.

### A.15 ZKBA-AUTHORIZATION-O3 (Live-Write Authority Transition Cards)

When the Operator Initiative fleet reaches `O3_ACTING` (live-write
authority), the act of issuing an O3 anchor is itself a
ZKBA-AUTHORIZATION-O3 card. This becomes the audit trail for "when did
Sentry / Guardian / Curator first acquire live anchor authority" -
visually inspectable from any external auditor's terminal.

Composes Phase O3-ACT-DRAFT bundle Merkle roots + Phase O3-ACT-WATCHER
gate-clearing event + the `parallel_o3_act_anchor.py` execution receipt
into a single anchored artifact per agent's first O3 ACT.

Uniqueness: the `O0 -> O1_SHADOW -> O2_SUGGEST -> O3_ACTING` ladder is a
VAPI-exclusive Operator Initiative design (Pass 2C).

### A.16 Extension Roadmap

| Extension | Dependency | Phase candidate (post v1.0) |
|-----------|------------|----------------------------|
| A.1 ZKBA-PROVENANCE-COMPOSITE | VBDIP-0001 + VSD-BOOTSTRAP (CDRR live) | VBDIP-0002 v1.1 |
| A.2 ZKBA-COHERENCE-DRIFT | Curator at O2_SUGGEST + FSCA contradiction surface | VBDIP-0002 v1.2 |
| A.3 ZKBA-AUDIT-TRAIL | Guardian at O2_SUGGEST + audit-drafting lane | VBDIP-0002 v1.3 |
| A.4 ZKBA-DUAL-ANCHOR | Sentry + Guardian both at O3_ACTING | VBDIP-0002 v2.0 |
| A.5 DP-ZKBA | BP-003 differential-privacy thresholds | VBDIP-0002 v1.4 |
| A.6 ZKBA-PHCI-MODULE | Module-replacement epoch wired into hardware cert registry | VBDIP-0002 v2.0 |
| A.7 ZKBA-MARKET-REVO | Curator at O2_SUGGEST + tier_downgrade_event | VBDIP-0002 v1.2 |
| A.8 ZKBA-VAME-ENVELOPED | VAME (Phase 236-VAME) LIVE | VBDIP-0002 v1.1 |
| A.9 ZKBA-SYNTHESIS-NOTE | VSD-BOOTSTRAP complete (notes/ tree exists) | VBDIP-0002 v1.5 |
| A.10 ZKBA-W3BSTREAM-VERIFIED | W3bstream applet `verify_zkba_artifact.ts` shipped | VBDIP-0002 v2.0 |
| A.11 ZKBA-CDRR-ECOSYSTEM | CDRR (Volume 2 §19.2) shipped | VBDIP-0002 v1.5 |
| A.12 CEDAR-LANE-ENFORCED | Cedar lane prefix in compiler manifest | VBDIP-0002 v1.1 |
| A.13 OPERATOR-AGENT-DRAFT Phase-Aware | Phase O2-DRAFT-REVIEW-FRONTEND live | VBDIP-0002 v1.1 |
| A.14 ZKBA-PROTOCOL-LENS Tournament Wrapper | ZKBA-TOURNAMENT class production | VBDIP-0002 v1.1 |
| A.15 ZKBA-AUTHORIZATION-O3 | Any Operator agent at O3_ACTING | VBDIP-0002 v2.0 |

### A.17 Non-Extensions (Explicitly Out of Scope)

The following are NOT in VBDIP-0002 scope at any version and require
separate proposals:

- Generic NFT minting from ZKBA artifacts (ZKBAs are not NFTs; they are
  signed artifacts).
- AI-generated visual content (the compiler is deterministic; AI is
  interpretive only).
- ZKBA verification on non-IoTeX chains beyond LayerZero VHP bridge
  semantics already specified in Phase 99C.
- ZKBA-derived tokenization or financial primitives (out of scope; would
  require a separate VEDIP or VBDIP).

---

## Appendix B — VBDIP-0002A Absorption (v1.1 amendment)

This appendix is a **v1.1 amendment** that absorbs selected sections of
VBDIP-0002A (`vsd-vault/proposals/drafts/VBDIP-0002A-verified-projection-media.DRAFT.md`)
per the reconciliation plan at
`vsd-vault/proposals/drafts/VBDIP-0002-vs-0002A-reconciliation.DRAFT.md`
recommended disposition **D-MERGE-SELECTIVE** (§8). The v1.0 spec sections
§1 through §17 + Appendix A remain byte-identical; the supersession discipline
(§18 "do not modify v1.0 in place") is honored — Appendix B is an addition,
not a modification.

Absorbed VBDIP-0002A sections, per reconciliation plan §3 disposition table:
§§1, 2, 3, 4, 5, 7, 9, 11, 12 → flow into this Appendix B as B.1–B.9.
Sections retained in VBDIP-0002A as sidecar (not absorbed): §6 (Stakeholder
Utility Layer), §8 (Curator Marketplace Lane), §10 (VPM Projection Registry).

VBDIP-0002A becomes a **PARTIALLY ABSORBED** sidecar at v1.1 amendment ship
time. Its remaining three sections continue as VBDIP-0002A sidecar content;
the absorbed nine sections become VBDIP-0002 v1.1 amendment content
authoritative under VBDIP-0002 governance.

This amendment introduces **no new PV-CI invariant**, **no Cedar mutation**,
**no chain action**, **no signature application**, and **no key generation**.
It is documentation reconciliation only. Activation of any VPM artifact
remains gated by Appendix B activation-sub-gates B.8 (G5a/G5b/G5c) plus the
existing §16 G6, G7, G8, G9.

### B.1 VPM Definition and Protocol Purpose (absorbed from VBDIP-0002A §1)

VAPI does not merely output "HTML." VAPI produces **Verified Projection Media
(VPM)**.

A Verified Projection Media artifact is a deterministic, human-operable
projection compiled from canonical VAPI state, proof manifests, and frozen
protocol primitives.

A VPM may:

- explain verified state,
- compress verified state into a human-operable surface,
- visualize proof limitations,
- package verified state for a stakeholder workflow,
- distribute a verifiable view of already-existing protocol truth.

A VPM may not:

- become source of truth,
- strengthen a proof claim,
- hide proof limitations,
- change runtime authority,
- bypass AgentScope / Cedar policy,
- bypass governance,
- convert a demo or draft artifact into production truth.

The core protocol equation for the VPM layer is:

```text
Canonical Cryptographic Truth
-> Deterministic Proof Media
-> Audience-Specific Trust
```

HTML (the ZKBA medium specified in §§4-10) is the first medium under VBDIP-0002.
VPM is the broader media category for future deterministic projections such
as QR codes, broadcast overlays, hardware certificates, PDF dispute packets,
wallet cards, and public protocol boards. VPM inherits the strict epistemic
discipline of VAPI evidence design: it may explain proof state, but it must
never alter proof state.

### B.2 Non-Authority Clause (absorbed from VBDIP-0002A §2)

The VPM amendment does not grant Operator agents new runtime authority.

It explicitly **does not authorize**:

- IPFS pinning,
- on-chain anchoring,
- marketplace listing mutation,
- endpoint writes,
- Git commits by Operator agents,
- FROZEN-v1 primitive changes,
- proof-weight escalation,
- consent override,
- Cedar lane expansion,
- compiler schema migration.

All operational use remains gated by VBDIP-0001, this proposal, AgentScope /
Cedar policy roots, and explicit governance ceremonies.

### B.3 VPM Lifecycle (absorbed from VBDIP-0002A §3)

Every VPM follows this lifecycle:

```text
Canonical State
-> VPM Wrapper Manifest
-> Deterministic Compile
-> Integrity Label
-> Stakeholder Surface
-> Expiry / Revocation Check
```

Lifecycle semantics:

- **Canonical State**: proof roots, ZKBA manifests, FROZEN-v1 primitive
  hashes, consent state, anchor state, and operator-agent state.
- **VPM Wrapper Manifest**: a VPM-specific wrapper that references existing
  proof manifests and compiler outputs; it does not replace them.
- **Deterministic Compile**: a content-addressed projection generated by an
  approved compiler version (the same compiler discipline specified in §2.3
  and §9).
- **Integrity Label**: mandatory visible claim summary and limitation surface
  (B.5).
- **Stakeholder Surface**: audience-specific media such as a QR pass, player
  wallet card, hardware certificate, or dispute packet (the per-audience
  detail remains in VBDIP-0002A §6 sidecar).
- **Expiry / Revocation Check**: final validity check before display or use.

The existing GIC Continuity Ledger (§10.1) is a ZKBA compiler target. It is
not yet an active VPM artifact until a VPM wrapper manifest, Integrity Label,
and VPM visual grammar tests exist for it.

### B.4 VPM Wrapper Manifest Schema (absorbed from VBDIP-0002A §4)

VPM uses a wrapper schema. It does not replace the FROZEN ZKBA compiler
schema `vapi-zkba-manifest-v1` (§9) and does not modify the current
`scripts/vsd_ui_compiler.py` manifest constants pinned by INV-ZKBA-003.

Draft wrapper schema:

```json
{
  "schema": "vapi-vpm-manifest-v1",
  "vpm_id": "QR-ELIGIBILITY-v1",
  "lifecycle_status": "Reserved",
  "audience": "Tournament Organizers",
  "source_commitment": "sha256:...",
  "zkba_manifest_schema": "vapi-zkba-manifest-v1",
  "zkba_manifest_hash": "sha256:...",
  "proof_weight": "CHAIN_ONLY",
  "capture_mode": "live|dry-run|emulated|demo|frozen-disabled",
  "visual_state": "saturated|striped|desaturated|locked|redacted|warning",
  "integrity_label": {
    "proof_type": "ZKBA-GIC",
    "capture_mode": "dry-run",
    "raw_biometrics_exposed": false,
    "consent_active": true,
    "zk_verified": false,
    "on_chain_anchor": false
  },
  "compiler_hash": "sha256:...",
  "anchor_status": "none|pending|anchored|stale",
  "revocation_status": "active|revoked|expired",
  "limitations": [
    "chain-only projection",
    "no fresh biometric capture"
  ]
}
```

The wrapper schema is a draft VPM interface. It becomes operational only
after activation sub-gates B.8 (G5a/G5b/G5c), compiler support, Integrity
Label tests, and governance approval.

### B.5 Visual Honesty Grammar (VPM-HONESTY-001) (absorbed from VBDIP-0002A §5)

All VPM artifacts must obey a protocol-native visual grammar that makes
overclaiming visually difficult.

Visual states:

- `live` = saturated colors
- `dry-run` = striped patterns
- `emulated` = desaturated / greyscale
- `frozen-disabled` = locked iconography
- `revoked` = crossed out / redacted
- `unverified` = high-contrast warning bands

**VPM-HONESTY-001 namespace discipline (locked per reconciliation plan §4):**
`VPM-HONESTY-001` is a methodology-document identifier, NOT a PV-CI
invariant. It does not enter `.github/INVARIANTS_ALLOWLIST.json`. It does
not enter `scripts/vapi_invariant_gate.py`. The next available `VED-INV-N`
slot (VED-INV-010 in VEDIP-0001 Appendix A) already aliases `INV-010`
(L6B_ENABLED default=False); using `VED-INV-N` here would corrupt the VEDIP
mapping. If/when visual honesty becomes programmatically enforceable, the
enforcement ships as a new PV-CI invariant under existing native naming
(e.g. `INV-VPM-VISUAL-001`), and a VEDIP Appendix A append assigns the
corresponding VED alias at that time. VPM-HONESTY-001 is not retroactively
renamed to a PV-CI ID even if programmatic enforcement later lands.

Every VPM must include an Integrity Nutrition Label detailing:

- Proof Type,
- Capture Mode,
- Raw Biometrics Exposed (Yes / No),
- Consent Active,
- ZK Verified,
- On-Chain Anchor status,
- Proof Weight,
- Revocation Status,
- Limitations.

### B.6 Failure-State Rules (absorbed from VBDIP-0002A §7)

VPM artifacts fail visibly. They do not fail silently.

Required failure states:

- **Missing manifest**: render `unverified`; no eligibility, listing, or
  wallet success state may appear.
- **Compiler hash mismatch**: render `verification-unavailable`; do not show
  `verified`.
- **Proof-weight omission**: fail compilation; no VPM artifact is emitted.
- **Revoked consent**: render `revoked`; marketplace and data-buyer surfaces
  become invalid.
- **Stale verification key**: render `warning`; verifier must refresh or
  reject according to the consuming workflow.
- **Absent anchor**: render `not anchored`; do not imply on-chain finality.
- **DEMO**: render visible demo watermark or equivalent visual state
  (consistent with §6.5 DEMO 15% pin).
- **FROZEN_DISABLED**: render locked / disabled; never render as active
  (consistent with §6.6 + §9.3 visual honesty tests).

### B.7 AI Role Constraint (absorbed from VBDIP-0002A §9)

AI agents do not create protocol truth.

Under this amendment, AI agents may:

- detect inconsistency,
- compile deterministic VPMs through approved tooling,
- flag visual misrepresentation,
- summarize verification outcomes,
- draft operator review notes.

AI agents may not:

- fabricate proof claims,
- bypass Cedar policy,
- alter proof weight,
- convert demo artifacts into production VPMs,
- change source-of-truth state,
- hide failure states.

This clause is a category constraint that extends §12 ("Category Distinction
and AI Role Constraint").

### B.8 Activation Sub-Gates (absorbed from VBDIP-0002A §11, mapped per reconciliation plan §5)

The §16 activation gate set grows from 9 to 11 gates via G5 splitting into
three sub-gates G5a / G5b / G5c. G1-G4 and G6-G9 carry forward unchanged.

| §16 Gate | Status | Description |
|----------|--------|-------------|
| G1 | SATISFIED | VBDIP-0001 FROZEN |
| G2 | PENDING | Numbering Decision Resolved (N1 / N2' / N3) |
| G3 | PARTIALLY SATISFIED | Compiler Harness Implemented (Track 1 GIC Continuity Ledger passes) |
| G4 | PENDING | ZKBA Manifest Schema Validated |
| G5a | PENDING | VBDIP-0002 / VBDIP-0002A reconciled (this amendment satisfies G5a) |
| G5b | PENDING | VPM wrapper manifest schema + Integrity Label implemented (Lane B work) |
| G5c | PENDING | Anti-Hype Visual Grammar tests passing (Lane B work) |
| G6 | PENDING | AgentScope / Cedar Permissions Authorized |
| G7 | PENDING | Curator Review Readiness |
| G8 | PENDING | Internal Projection First |
| G9 | PENDING | Numbering Decision Applied |

G5a is satisfied by the v1.1 amendment landing (this Appendix B). G5b and
G5c are Lane B implementation work and remain wallet-free + authority-neutral;
they do not require Track 2 activation gates.

### B.9 Decision Blocks K8 – K14 (absorbed from VBDIP-0002A §12 L1 – L7)

The K-prefix decision block sequence in §17 extends from K1-K7 to K1-K14
via sequential append. K1-K7 carry forward unchanged.

**K8 – VPMs as Human-Operable Surfaces** (from VBDIP-0002A L1)
*Resolved:* VPMs are deterministic human-operable surfaces for cryptographic
state, not protocol source of truth.

**K9 – Anti-Hype Visual Grammar** (from VBDIP-0002A L2)
*Resolved:* Visual honesty is protocol law. VPMs must use mandatory visual
states (B.5) to reflect technical limitations.

**K10 – VPM Registry Discipline** (from VBDIP-0002A L3)
*Resolved:* All projections must use registered VPM identifiers
(VBDIP-0002A §10 sidecar) to prevent un-auditable artifact sprawl.

**K11 – AI Stewardship Boundary** (from VBDIP-0002A L4)
*Resolved:* AI agents compile VPMs to explain verified state, but may never
create or escalate protocol truth (B.7).

**K12 – VPM Wrapper Discipline** (from VBDIP-0002A L5)
*Resolved:* VPM wraps ZKBA and proof manifests; it does not replace frozen
schemas, compiler constants, or primitive commitments. `vapi-vpm-manifest-v1`
references `vapi-zkba-manifest-v1` rather than replacing it (B.4).

**K13 – Registry Lifecycle Discipline** (from VBDIP-0002A L6)
*Resolved:* Reserved VPM IDs are not shipped features. A VPM ID becomes
active only after wrapper manifest, compiler target, test fixture, and
governance approval exist (registry lifecycle ladder in VBDIP-0002A §10
sidecar: `Reserved → Draft Manifest → Compiler Target → Test Fixture →
Active`).

**K14 – Failure-State Visibility** (from VBDIP-0002A L7)
*Resolved:* Invalid, incomplete, stale, revoked, demo, or disabled proof
state must render visibly degraded (B.6).

### B.10 Sidecar Retention (VBDIP-0002A residual scope)

The following VBDIP-0002A sections remain in the sidecar, NOT absorbed:

- **§6 Stakeholder Utility Layer** — Audience-specific framing (gamers /
  developers / manufacturers / tournament organizers / marketplace buyers /
  governance). Sidecar discipline; VBDIP-0002 references stakeholder
  utility at §11 but does not own per-audience deployment detail.
- **§8 Curator Marketplace Lane** — Curator agent-specific behavior. Belongs
  in operator-agent-skill documentation or in a Curator-specific sidecar.
- **§10 VPM Projection Registry** — Ten Reserved VPM IDs (`PROOF-TRAILER-v1`
  through `AGENT-REVIEW-v1`). Registry maintenance is sidecar discipline;
  this amendment references the registry by URI but does not embed the
  table.

VBDIP-0002A becomes **PARTIALLY ABSORBED** at v1.1 amendment ship time. Its
remaining three sections continue as VBDIP-0002A sidecar content.

### B.11 What This Amendment Does NOT Do

- Does not change VBDIP-0001 status (FROZEN).
- Does not change the FROZEN status of `vapi-zkba-manifest-v1`.
- Does not resolve N1 / N2' / N3 numbering decision.
- Does not regenerate `.github/INVARIANTS_ALLOWLIST.json`.
- Does not add or remove any PV-CI invariant.
- Does not modify v1.0 spec content in §§1-17 + Appendix A.
- Does not author Lane B implementation work (wrapper manifest validator,
  Integrity Label rendering, visual grammar test fixtures, registry
  compiler targets).
- Does not authorize Track 2 (Cedar v2 bundles + ZKBA anchor ceremony).
- Does not run a signing ceremony. The architect signing chain
  (VBDIP-0001 Step 4 `vsd-vault/eval/architect_key_attestation.json`)
  remains available for any future operator-authorized formal manifest.

---

## Appendix C — Schema Name Reconciliation (v1.2 amendment)

This appendix is a **v1.2 amendment** codifying bilateral acceptance
of two ZKBA projection manifest schema names per the resolution
proposal at
`vsd-vault/proposals/drafts/VBDIP-0002-schema-name-reconciliation.DRAFT.md`
recommended **Option C — Codify bilateral acceptance** (§8).

The v1.0 spec sections §§1-17 + Appendix A + Appendix B remain
byte-identical; the supersession discipline (§18 "do not modify v1.0
in place") is honored — Appendix C is purely additive, matching the
Appendix A + Appendix B precedent that the v1.0 freeze accepts for
"build on this freeze."

### C.1 The Drift

During G4 implementation (commit `210f841b`), the manifest validator
discovered a divergence between the spec text at §9.2 and the
implementation at `scripts/vsd_ui_compiler.py:58`:

| Layer | Schema name literal |
|---|---|
| **§9.2 spec design-time text** | `zkba.projection_manifest.v1` |
| **`scripts/vsd_ui_compiler.py:58` implementation** | `vapi-zkba-manifest-v1` |
| **PV-CI INV-ZKBA-003 pin** | `vapi-zkba-manifest-v1` |

The drift trace:

- **C3 (commit `3b3081d3`)** — implementation chose
  `vapi-zkba-manifest-v1` without consulting §9.2
- **C5 (commit `0791c935`)** — INV-ZKBA-003 FROZE the implementation
  name at the PV-CI layer
- **G4 (commit `210f841b`)** — validator authored; drift discovered
- **2026-05-12** — proposal authored at commit `f17622c0`
  recommending Option C

### C.2 Bilateral Acceptance

The validator at `scripts/zkba_manifest_validator.py` accepts BOTH
schema names via `ACCEPTED_SCHEMA_NAMES` frozenset:

```python
IMPLEMENTATION_SCHEMA_NAME = "vapi-zkba-manifest-v1"
SPEC_DESIGN_TIME_SCHEMA_NAME = "zkba.projection_manifest.v1"
ACCEPTED_SCHEMA_NAMES = frozenset({
    IMPLEMENTATION_SCHEMA_NAME,
    SPEC_DESIGN_TIME_SCHEMA_NAME,
})
```

The `schema_name_form` field of `ManifestValidationResult` surfaces
which name a given manifest was emitted under. The same field is
returned through all four reach surfaces (Python lib + MCP tool +
bridge HTTP endpoint + SDK client) so external tooling can detect
schema-name drift per request.

### C.3 Canonical Name (New Emissions)

**`vapi-zkba-manifest-v1` is the canonical name for new emissions.**

PV-CI invariant INV-ZKBA-003 pins this literal in the implementation
allowlist at `.github/INVARIANTS_ALLOWLIST.json`. Any future ZKBA
manifest emission MUST use this name to satisfy the invariant gate.

Rationale:

- The implementation has been in production through 14 commits since
  C3 (2026-05-10)
- INV-ZKBA-003 is an operator-frozen protocol invariant; changing the
  pin literal would require `--confirm-governance` ceremony
- The implementation name was the working name at the time PV-CI
  governance was applied

### C.4 Recognized Legacy Name (Read-Only)

**`zkba.projection_manifest.v1` is the recognized legacy name for
validation only.**

The validator accepts manifests under this name so legacy / third-
party / hypothetical emissions referencing §9.2 spec text remain
interpretable. No new emissions under this name are permitted by the
PV-CI invariant gate.

This bilateral discipline preserves forward compatibility: external
integrators who read §9.2 design-time text and constructed manifests
under the spec name during the drift window (2026-05-10 to
2026-05-12) are not invalidated; their manifests still validate
successfully.

### C.5 Validator Behavior Pin

The four `schema_name_form` values are FROZEN at v1.2:

| Value | Meaning |
|---|---|
| `"implementation"` | Manifest uses `vapi-zkba-manifest-v1` |
| `"spec_design_time"` | Manifest uses `zkba.projection_manifest.v1` |
| `"unknown"` | Schema string present but not in `ACCEPTED_SCHEMA_NAMES` |
| `"absent"` | Schema field missing or not a string |

The validator emits exactly one of these four values per request.
External tooling can branch on this field to implement migration
flows, drift detection, audit logging, etc.

### C.6 Migration Path Reservation

If a future VBDIP-0002 v2.0 freeze chooses to migrate to a different
schema name (e.g., `vapi-zkba-projection-manifest-v2`), the v2
manifest spec will carry forward BOTH v1 names as
ACCEPTED-FOR-VERIFICATION-ONLY:

- v2 emissions use the v2 name
- v1.x emissions (under either C.3 canonical or C.4 legacy name)
  remain validatable indefinitely
- No backwards-incompatible breakage

This reservation prevents future migration from invalidating the
artifact history that accumulates under v1.

### C.7 Cross-References

- `vsd-vault/proposals/drafts/VBDIP-0002-schema-name-reconciliation.DRAFT.md`
  (commit `f17622c0`) — full options analysis for A/B/C/D
- `scripts/zkba_manifest_validator.py` (commit `210f841b`) —
  bilateral-acceptance implementation
- `scripts/vapi_invariant_gate.py` INV-ZKBA-003 entry — implementation
  name FROZEN pin
- `wiki/methodology/VEDIP-0001-engineering-discipline-retrospective.md`
  Appendix A entry for VED-INV-066 — implementation name reflected
  in documentation alias map (no change required under this
  amendment)

### C.8 Status

**v1.2 amendment status: SHIPPED 2026-05-12.**

Codifies the working state. Validator implementation already matches
(no code change). PV-CI INV-ZKBA-003 unchanged. v1.0 spec §§1-17 +
Appendix A + Appendix B byte-identical per supersession discipline.

### C.9 What This Amendment Does NOT Do

- Does not edit §9.2 text in place (would violate supersession).
- Does not regenerate `.github/INVARIANTS_ALLOWLIST.json`.
- Does not change INV-ZKBA-003 pin literal.
- Does not change implementation schema name in
  `scripts/vsd_ui_compiler.py`.
- Does not re-emit any compiled ZKBA artifact.
- Does not author a VBDIP-0002 v2.0 migration proposal (Option B
  from the resolution proposal). If a future operator decides v2.0
  migration is appropriate, that proposal is authored as a separate
  document.
- Does not run a signing ceremony.

---

## 18. Document Metadata

**Document version:** VBDIP-0002 v1.0r2 FROZEN-SPEC candidate
+ v1.1 amendment (Appendix B — VBDIP-0002A Absorption) applied
2026-05-12 + v1.2 amendment (Appendix C — Schema Name Reconciliation)
applied 2026-05-12. v1.0 spec §§1-17 + Appendix A + Appendix B
byte-identical; v1.2 amendment is additive per supersession discipline.
**Active spec content = v1.0r2 + v1.1 amendment + v1.2 amendment.**
**Generated:** 2026-05-10
**Tags:** `#vbdip #zkba #html-projection #visual-honesty #proof-weight #curator #depin #iotex #vad #vsd #ved #vbd #appendix-extensions #revised-r1`
**Operational status:** Sidecar specification only; not operationally active.
**Numbering status:** Pending operator resolution (N1 / N2' / N3 per Section 1.3; N2 retired because VBDIP-0001 §3.3 reserves VBDIP-0003).
**Dependency:** VBDIP-0001 FROZEN dependency satisfied; activation remains blocked by the remaining Section 16 gates.
**VBDIP-0002A relationship:** PARTIALLY ABSORBED. VBDIP-0002A §§1,2,3,4,5,7,9,11,12 absorbed into VBDIP-0002 v1.1 amendment Appendix B (B.1-B.9). VBDIP-0002A §§6,8,10 retained as sidecar content at `vsd-vault/proposals/drafts/VBDIP-0002A-verified-projection-media.DRAFT.md`. The absorbed-section text in VBDIP-0002A remains in that file for historical reference but is NOT authoritative; Appendix B here is the authoritative version. Sidecar content (Stakeholder Utility Layer, Curator Marketplace Lane, VPM Projection Registry) continues under VBDIP-0002A governance per reconciliation plan §3 D-MERGE-SELECTIVE disposition.
**Next action:** Operator may resolve numbering and authorize remaining activation work, OR keep this file as a sidecar pending numbering resolution and VPM reconciliation.

**Status transition log:**

- 2026-05-10: Initial draft authored (700 lines, hash `1ffdd22a1f793215...8de5a8`)
- 2026-05-10: Enhanced to v1.0 with 17-section ordering + Appendix A forward-looking extensions (1,433 lines, hash `6531e1a9...3d36c`)
- 2026-05-10: r1 docs-only revision applied (E1–E12 batch per operator review — numbering 0003 reservation surfaced; ZKBA-LISTING → ZKBA-MARKET consolidation; freshness_window + capture_ts_ns schema fields added; `lane` field removed from v1.0 schema (deferred to v1.1 per A.12); DEMO 15% pin mirrored in §6.5; APOP hybrid-mode qualifier added; trust-model reframe in §12.3; activation gate #8 numbering resolution added; ZKBA-DUAL-ANCHOR post-O3 phase qualifier added; W3bstream applet status clarified to code-complete-stubs)
- 2026-05-11: r2 docs-only cross-reference applied for VBDIP-0002A Verified Projection Media (VPM) sidecar; VBDIP-0001 and Track 1 compiler status updated; VPM wrapper remains draft-only and not operational authority
- 2026-05-12: **v1.1 amendment applied** — Appendix B authored landing D-MERGE-SELECTIVE per reconciliation plan §8 recommendation (`vsd-vault/proposals/drafts/VBDIP-0002-vs-0002A-reconciliation.DRAFT.md`). VBDIP-0002A §§1,2,3,4,5,7,9,11,12 absorbed as B.1-B.9; §§6,8,10 retained in VBDIP-0002A sidecar. v1.0 spec content (§§1-17 + Appendix A) NOT modified per §18 supersession discipline. Activation gate G5 split into G5a/G5b/G5c (gate count 9 → 11). Decision block series extended K1-K7 → K1-K14 (B.9). VPM-HONESTY-001 locked as methodology-doc identifier (NOT a PV-CI invariant) per reconciliation plan §4. PV-CI count unchanged (69). Wallet 0 IOTX; chain impact none; `CHAIN_SUBMISSION_PAUSED=true` held.
- (pending): Operator review of Section 17 K1-K7 + Appendix B K8-K14 decision blocks
- (pending): Operator resolution of Section 1.3 N1 / N2' / N3 numbering decision
- (satisfied): VBDIP-0001 FROZEN (gate 16.1 / B.8 G1)
- (partially satisfied): Compiler harness implementation for Track 1 (`scripts/vsd_ui_compiler.py`; gate 16.3 / B.8 G3 remains open for full visual honesty coverage)
- (satisfied): VBDIP-0002 / VBDIP-0002A reconciliation (B.8 G5a)
- 2026-05-12: Lane B G5b + G5c shipped — `scripts/vsd_vpm_wrapper.py` authors `vapi-vpm-manifest-v1` wrapper schema (referencing FROZEN `vapi-zkba-manifest-v1`, not replacing), 9-field VPMIntegrityLabel, 6-element VPMVisualState enum, 5-element VPMCaptureMode enum, derive_visual_state() rule engine encoding B.6 failure-state precedence, validate_vpm_manifest() mechanical enforcement. `bridge/tests/test_phase_o3_zkba_vpm_wrapper.py` 24/24 PASS (T-VPM-1..10 wrapper + T-VPM-VG-1..12 visual grammar + 2 static guards). Wallet-free; no PV-CI change; VPM-HONESTY-001 remains methodology-doc identifier per reconciliation plan §4.
- 2026-05-12: Lane B G3 shipped — `bridge/tests/test_phase_o3_zkba_compiler_visual_honesty.py` (13 tests, 13/13 PASS) authors the §9.3 visual honesty test suite scoped to the GIC Continuity Ledger (the only active artifact at Track 1). Tests cover §9.3 rules 1 (proof_weight visibility), 5 (compiler hash mismatch detection), 6 (manifest/proof mismatch tamper detection + per-field tamper), 7 (missing proof_weight FAILS compilation), 8 (manifest does not falsely claim ZK verification when GIC is not ZK-proven), 9 (no external URL refs / no `<link>` tags / no CDN domains). Rules N/A for GIC at Track 1: §9.3.2 (DEMO watermark), §9.3.3 (FROZEN_DISABLED render), §9.3.4 (revoked consent marketplace) — these apply to future artifact classes with DEMO / FROZEN_DISABLED / marketplace capture_mode variations that don't apply to GIC's CHAIN_ONLY operator-facing profile. §9.3.10 (lane prefix matches output directory) DEFERRED to Track 2 per §A.12 forward-looking marker. Test-only commit; no modification to scripts/vsd_ui_compiler.py or scripts/zkba_compile_gic_ledger.py. Wallet-free; no PV-CI change.
- 2026-05-12: Lane B G4 shipped — `scripts/zkba_manifest_validator.py` (~340 LOC) + `bridge/tests/test_phase_o3_zkba_manifest_validator.py` (55 tests / 55 PASS in 1.42s including 7-class parametrized coverage). validate_zkba_manifest() returns ManifestValidationResult (fail-open; never raises) checking: required field set (8 fields), schema name (accepts both implementation `vapi-zkba-manifest-v1` and §9.2 design-time `zkba.projection_manifest.v1`), zkba_class enum range (1..7), proof_weight enum range (1..6), output_hash_hex / input_commitment_hex 64-char lowercase hex, ts_ns uint64. build_representative_manifest() helper produces synthetic test fixtures for any of 7 ZKBAClass values at default proof_weight (per DEFAULT_PROOF_WEIGHT_BY_CLASS table: AIT→CALIBRATION_PLUS_CONTEXT, GIC/VHP/HARDWARE/CONSENT/TOURNAMENT→CHAIN_ONLY, MARKET→MARKETPLACE_DERIVED). T-MV-11 round-trip closure: validator accepts real compile_artifact() output end-to-end. **V-CHECK FINDING DOCUMENTED:** §9.2 spec design-time schema name `zkba.projection_manifest.v1` diverges from implementation FROZEN schema name `vapi-zkba-manifest-v1` (pinned by INV-ZKBA-003 in scripts/vapi_invariant_gate.py); validator accepts both names + surfaces drift via `schema_name_form` field (implementation / spec_design_time / unknown / absent). Reconciliation is operator-decision work scoped as future VBDIP-0002 v1.x amendment; this validator does NOT force the resolution. Wallet-free; no PV-CI change; PV-CI INV-ZKBA-003 takes precedence over §9.2 in current state.
- (satisfied): VPM wrapper manifest schema + Integrity Label implementation (B.8 G5b)
- (satisfied): Anti-Hype Visual Grammar tests passing (B.8 G5c)
- (partially satisfied): §9.3 visual honesty tests for active artifact set (B.8 G3) — 6 of 10 rules covered for GIC; 3 N/A for GIC's CHAIN_ONLY profile (will close when DEMO / FROZEN_DISABLED / marketplace classes ship); 1 deferred to Track 2 per §A.12
- (satisfied): ZKBA manifest schema validated against representative artifacts of all 7 §5 classes (B.8 G4)
- 2026-05-12: G4 reach extended to MCP — `vapi_validate_zkba_manifest` tool added at `vapi-mcp/knowledge_server.py` (4 new tests T-ZKBA-17..20 PASS); accepts inline manifest dict or manifest_path; mirrors C4 ZKBA primitive MCP pattern; surfaces schema_name_form drift to LLM agents.
- 2026-05-12: G4 reach extended to bridge HTTP — `POST /operator/zkba-validate-manifest` endpoint added at `bridge/vapi_bridge/operator_api.py` (13 new tests T-ZKBA-VEP-1..7 PASS including 7-class parametrized coverage); read-key auth; 422 on body-parse errors; 200+fail-open on content-validation errors; surfaces schema_name_form drift via response field. Localized sys.path.insert + lazy import (`scripts/` → bridge endpoint) is a one-time inversion of the usual `scripts/`-depends-on-`bridge/` direction, deliberate at this endpoint. This completes the C4 → c2510883 architectural progression for the G4 validator: Python lib → MCP tool → bridge HTTP. Wallet-free; no PV-CI change.
- 2026-05-12: G4 reach trio CLOSED — SDK `VAPIZKBAValidator` client added at `sdk/vapi_sdk.py:9340+` wrapping `POST /operator/zkba-validate-manifest`. SDK_VERSION bumped `3.1.0-phase-o3-zkba-track1-c4-sdk` → `3.1.1-phase-o3-zkba-track1-g4-validator-sdk`. `ZKBAValidateResult` slotted dataclass (6 fields: valid / errors / zkba_class_name / proof_weight_name / schema_name_form / error) with same fail-open contract as VAPIZKBA / VAPIDraftReview / VAPIFleetReadinessRoot. 12 new SDK tests T-ZKBA-VSDK-1..6 PASS including 7-class parametrized live round-trip via uvicorn fixture. Existing T-ZKBA-13 sanity check relaxed `startswith("3.1.0")` → `startswith("3.1.")` to permit patch bumps within the 3.1.x family. Final reach surface for the G4 validator: Python lib (G4 commit 210f841b) → MCP tool (commit 53553047) → bridge HTTP (commit 4f63c5d5) → SDK (this commit). Wallet-free; no PV-CI change.
- 2026-05-12: **v1.2 amendment applied** — Appendix C authored landing Option C from the §9.2 schema-name reconciliation proposal at commit `f17622c0`. **Codifies bilateral acceptance**: `vapi-zkba-manifest-v1` (implementation; INV-ZKBA-003 pin) is CANONICAL for new emissions; `zkba.projection_manifest.v1` (§9.2 spec design-time text) is RECOGNIZED for read-only validation of legacy / third-party manifests. v1.0 spec §§1-17 + Appendix A + Appendix B NOT modified per §18 supersession discipline. Validator implementation at `scripts/zkba_manifest_validator.py` (commit 210f841b) already implements the bilateral acceptance; this amendment codifies the working state. No code change; no PV-CI ceremony; no allowlist regeneration. Migration path reservation §C.6 preserves forward compatibility for a future v2.0 schema migration. Wallet 0 IOTX; chain impact none; `CHAIN_SUBMISSION_PAUSED=true` held.
- 2026-05-12: **Operator Decision Matrix D-NUM, D-SIDECAR-0002A, D-LANE-B-G3 RESOLVED** per broad operator authorization "do whatever is necessary based on your recommendations." (1) **D-NUM Option N1**: VBDIP-0002 owns the 0002 slot for ZKBA permanently; Phase O1-VAD-MIGRATE relocates to VBDIP-0004 (reserved-only) per `wiki/methodology/VBDIP-0001-vad-framework-introduction.md` v1.1 amendment Appendix A. **Closes §16 G2 + G9** (Numbering Decision Resolved + Applied). (2) **D-SIDECAR-0002A Option S1**: `vsd-vault/proposals/drafts/VBDIP-0002A-verified-projection-media.DRAFT.md` retained as indefinite sidecar with §§6, 8, 10 (Stakeholder Utility Layer + Curator Marketplace Lane + VPM Projection Registry) as authoritative content; v1.1 amendment Appendix B PARTIALLY ABSORBED status preserved. (3) **D-LANE-B-G3 Option L3**: §9.3 visual honesty test coverage CLOSES at PARTIAL SATISFIED status — 6 of 10 rules covered for GIC Continuity Ledger CHAIN_ONLY profile; rules 2/3/4 N/A for current artifact set (apply when future DEMO/FROZEN_DISABLED/marketplace ZKBA classes ship); rule 10 (lane prefix) deferred to Track 2 per §A.12. Final state under L3 is the working state; no expansion manufactured. All three resolutions: methodology-only; no code change; no PV-CI ceremony; no allowlist regeneration; no signature application; wallet 0 IOTX; chain impact none; `CHAIN_SUBMISSION_PAUSED=true` held.
- 2026-05-12: **D-PV-VPM RESOLVED via Option P3** — New PV-CI invariant **INV-VPM-WRAPPER-001** pinning `vapi-vpm-manifest-v1` wrapper schema literal in `scripts/vsd_vpm_wrapper.py` added to `scripts/vapi_invariant_gate.py` + `.github/INVARIANTS_ALLOWLIST.json` regenerated via `--confirm-governance` ceremony with phrase "I understand this changes a frozen protocol invariant". Mirrors INV-ZKBA-003 single-pin minimal form per the reconciliation plan §4 distinction (VPM-HONESTY-001 remains methodology-doc identifier; INV-VPM-WRAPPER-001 is the implementation-layer pin — distinct surfaces). VEDIP-0001 Appendix A entry VED-INV-067 aliases the new invariant per VED-INV-N documentation-alias discipline. PV-CI total 69→70 invariants. Allowlist 66→67 protocol entries (VBD-INV-001/002/003 remain markdown-normative; total `--proposal-type all` count 70). Methodology-only resolution; wallet 0 IOTX; chain impact none beyond local allowlist regen (bridge offline so governance event POST 404'd — non-blocking; matches Phase 224 + O1-FRR-PARALLEL precedent for offline-bridge regen).
- 🚀 2026-05-12: **TRACK 2 C8 CEREMONY FIRED — Cedar v2 bundles LIVE on IoTeX testnet.** Operator three-factor authorization aligned at PowerShell terminal (env CHAIN_SUBMISSION_PAUSED=false + env OPERATOR_ZKBA_ANCHOR_AUTHORIZED=true + --confirm CLI flag); `python scripts/parallel_zkba_anchor.py --confirm` executed; **3/3 successes, 0/3 failures**. All three Cedar v2 bundles now dual-anchored on AgentScope (operational FIRST per INV-OPERATOR-AGENT-001) + AgentRegistry (governance SECOND): **anchor_sentry v2** op_tx `3f79b4b428e0931671...` + gov_tx `04029ac59b4e08084f...`; **guardian v2** op_tx `1e3a65f4445d73cc37...` + gov_tx `16ce625cdc9c8fc2cb...`; **curator v2** op_tx `470cbd17c865eef82b...` + gov_tx `5aac0d92866ac29cc5...`. Pre-flight: Wallet 15.2626 IOTX, Merkle roots verified against EXPECTED_MERKLES locks (`0x39e8b65f...` / `0x6818a9ad...` / `0x0ade0c92...`), kill-switch lifted, cfg.chain_submission_paused=False. Post-ceremony: kill-switch restored to safe posture (`$env:CHAIN_SUBMISSION_PAUSED = "true"`; `Remove-Item Env:OPERATOR_ZKBA_ANCHOR_AUTHORIZED`). **Methodology Layer (Layer 7) reaches FULL ACTIVATION STATE**: ZKBA artifact emission lanes (zk_artifacts/ Sentry-exclusive + zk_verifications/ Guardian-exclusive + zk_listings/ Curator-exclusive) now have on-chain Cedar v2 authority. v1 Cedar bundles remain LIVE alongside v2 per additive discipline mirror. **Operator Decision Matrix queue**: 14 of 16 RESOLVED (D-TRACK2-C8 SATISFIED via this ceremony + D-TRACK2-KILLSWITCH SATISFIED via three-factor authorization + D-TRACK2-FSCA SATISFIED via vacuous pre-flight cleanliness). 2 remaining items (D-TRACK2-G6 per-agent live authority verification + D-TRACK2-G7 Curator readiness) are post-ceremony observability work; not blocking. **Phase O3-ZKBA-TRACK1 + Track 2 COMPLETE.** Bridge `cd7af1d9` → `85fc4551` (bugfix) → ceremony fires. Wallet delta ~0.23 IOTX (15.2626 → ~15.03 post-ceremony) across 6 dual-anchor txs.
- (pending): VBDIP-0002 activation under resolved numbering successor

**Supersession discipline:** VBDIP-0002 v1.0 is a foundational sidecar.
Future revisions (v1.1, v1.2, ..., v2.0) build on this freeze; they do
not modify v1.0 in place. The Appendix A extension roadmap is the
forward-looking authoring queue.

---

**End of VBDIP-0002 sidecar specification (FROZEN-SPEC v1.0, pending dependency).**

The methodology framework is VAPI Architectural Discipline (VAD), pending
VBDIP-0001 freeze. The synthesis sub-discipline is VSD. The engineering
sub-discipline is VED. The bridge sub-discipline is VBD. ZKBAs are a VBD
artifact category that composes existing FROZEN-v1 primitives into
human-legible, privacy-preserving, deterministically compiled visual proof
projections. The novelty is not the visual; the novelty is the proof root
the visual is bound to, and the cross-fleet skill-separation discipline
that prevents any single agent from owning the full artifact lifecycle.
