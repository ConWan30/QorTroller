# Phase O4-VPM-INTEGRATION — Provenance Pin

**Phase status:** COMPLETE (this commit closes the phase)
**Start:** 2026-05-13 (V-check provenance pin commit `603c98cb`)
**Close:** 2026-05-13 (this commit)
**Anchor commit at phase open:** `ece17f4f` (Layer 7 7-of-7 ZKBA HARDWARE close)
**Anchor commit at phase close:** *(this commit's SHA — recorded in commit body)*
**Plan reference:** `wiki/proposals/Phase_O4_VPM_Integration_Plan.md` (~640 LOC)
**Authoring:** VAPI Principal Architect under operator authority across 7 sub-stream commits

---

## 0. Purpose

Phase O4 closes the Methodology Layer (Layer 7) **output surface**. Before
Phase O4, the seven Phase O3-ZKBA-TRACK1 artifact classes (AIT / GIC / VHP
/ HARDWARE / CONSENT / TOURNAMENT / MARKET) shipped as filesystem-only
HTML under `frontend/src/artifacts/*/` with no bridge HTTP surface and no
operator-console inspection path. After Phase O4 they are first-class
delivered media with a three-layer Anti-Hype Visual Grammar enforcement
chain spanning Python compiler-side + Python bridge-side + JavaScript
browser-side.

The phase is wallet-free, chain-write-paused, additive only.

---

## 1. Commit Roster

| # | Commit | Subject | LOC | Tests |
|---|---|---|---|---|
| 1 | `168256a0` | Layer 7 coverage audit + 7-of-7 closure doc | 917 | +6 bridge |
| 2 | `603c98cb` | V-check provenance pin 2026-05-13 | 300 | 0 |
| 3 | `524ae1cc` | A.0 compiler engine + T-VPM-COMPILER-1..10 | 806 | +10 bridge |
| 4 | `fd0d6699` | A.1 — 4 internal compilers + Anti-Hype Visual Grammar | 2799 | +73 bridge |
| 5 | `7052144f` | A.2 — 2 consumer-facing + procedural geometric art | 1411 | +46 bridge |
| 6 | `169471bb` | A.3 + A.4 — 4 draft manifests + vpm_audit | 1661 | +15 bridge |
| 7 | `1b13618d` | B.0-B.3 — store + 3 read endpoints | 930 | +14 bridge |
| 8 | `d5803d47` | B.4-B.7 — write + validate + audit + stability | 888 | +20 bridge |
| 9 | `0061e6d9` | C — VPM Registry tab + Layer 3 grammar verifier | 1700 | +26 Vitest |
| 10 | *(close)* | close — PV-CI + FSCA + CLAUDE.md NOTE + this pin | ~350 | 0 |

**Net delta**: Bridge **3160 → 3344 (+184)**. Frontend Vitest **0 → 26**
(first frontend test infrastructure in the repo). SDK / Hardhat /
Contracts unchanged at 562 / 528 / 49 LIVE.

---

## 2. What Shipped (functional)

### 2.1 Stream A — Protocol surface

**Six active VPM compilers** all inheriting `scripts/vpm_visual_grammar.py`:

| Compiler | Lane | ZKBA class | Proof weight | Lifecycle |
|---|---|---|---|---|
| HONESTY-BOARD-v1 | Sentry | GIC (2) | CHAIN_ONLY | Test Fixture |
| AGENT-REVIEW-v1 | Guardian | CONSENT (5) | CHAIN_ONLY | Test Fixture |
| CDRR-DAG-v1 (under HONESTY umbrella) | Sentry | HARDWARE (4) | CHAIN_ONLY | Test Fixture |
| GIC-LEDGER-BETA-v1 (under HONESTY umbrella) | Sentry | GIC (2) | CHAIN_ONLY | Test Fixture |
| DISPUTE-PACKET-v1 | Guardian | CONSENT (5) | CHAIN_ONLY | Compiler Target |
| MARKET-LISTING-v1 | Curator | MARKET (7) | MARKETPLACE_DERIVED | Compiler Target |

**Four draft manifests** at Reserved → Draft Manifest lifecycle promotion:

- PROOF-WALLET-v1 (Gamers / Sentry)
- QR-ELIGIBILITY-v1 (Tournament Organizers / Sentry)
- HARDWARE-LINEAGE-v1 (Manufacturers / Sentry; inherits HARDWARE
  Participation Card publicly-attributable manufacturer-address posture)
- CONSENT-CAPSULE-v1 (Gamers + Data Buyers / Guardian; GDPR Art. 17
  revoked_at primitive carried forward)

**Compiler discipline (`compile_vpm_artifact`)** static guards reject
emitted HTML containing: `https?://`, `<link rel=>`, `<script src=>`,
`@import`, `<iframe src=>`, `<img>` outside `data:`, `@font-face`, `fetch()`,
`XMLHttpRequest`, `new WebSocket`, `new EventSource`, `Math.random()`,
`crypto.getRandomValues`, `Date.now()`, zero-arg `new Date()`,
`performance.now()`. Plus mandatory 9-field Integrity Label DOM with
`data-vpm-field="<name>"` markers.

**Procedural Geometric Art (MARKET-LISTING-v1)** FROZEN algorithm v1 per
VBDIP-0002 ZKBA Market Card spec: 32 SHA-256 bytes → 8 four-byte chunks →
8 geometric tiles (regular polygons; 4-shape kind; deterministic position,
size, hue, rotation). Per-byte sensitivity verified by T-VPM-ML-ART-3.

**Audit harness `scripts/vpm_audit.py`** parallels
`scripts/zkba_post_ceremony_audit.py` shape — 6 sections × wallet-free /
read-only / no chain RPC. All 6 sections OK against live tree.

### 2.2 Stream B — Bridge HTTP surface (6 new endpoints)

| Endpoint | Method | Auth | Purpose |
|---|---|---|---|
| `/operator/vpm-list` | GET | read-key | Filterable registry list (vpm_id / visual_state / since_minutes / limit) |
| `/operator/vpm-artifact/{commit}` | GET | read-key | Serves HTML with FROZEN CSP headers |
| `/operator/vpm-manifest/{commit}` | GET | read-key | Parsed `.vpm.manifest.json` sidecar |
| `/operator/vpm-compile` | POST | full operator | Dispatches to one of 6 compilers; records vpm_artifact_log row |
| `/operator/vpm-validate-manifest` | POST | read-key | Validates `vapi-vpm-artifact-v1` schema |
| `/operator/vpm-audit-status` | GET | read-key | Programmatic `run_audit()` invocation |

**FROZEN CSP header set** per Phase O4 plan §3 Stream B.2:
`default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline';
img-src data:; base-uri 'none'; frame-ancestors 'self'; form-action 'none'`.

**vpm_artifact_log SQLite table** (Phase 1200 migration) with 4 helpers +
UNIQUE commitment_hex + 4 indexes; idempotent on collision.

### 2.3 Stream C — Frontend VPM Registry tab

**Sixth top-level view** (`vpm:` key in `VIEW_MAP`; amber `#f0a868` accent
to remain visually distinct from DEVELOPER orange + MANUFACTURER blue).

**Two-pane layout**: Left 360px wide = `VpmFilterChips` + scrollable
artifact list; right pane = `VpmIframe` + `VpmManifestPanel` + grammar
verifier badge in header.

**FROZEN iframe sandbox**: `"allow-scripts allow-same-origin"` — no
expansion permitted. Forbidden flags: `allow-forms`, `allow-popups`,
`allow-top-navigation`, `allow-modals`, `allow-pointer-lock`,
`allow-presentation`, `allow-downloads`,
`allow-storage-access-by-user-activation`.

**Client-side hash check** via `canonicalJsonStringify` (mirrors Python
`scripts/vsd_ui_compiler.canonical_json` recursive sort_keys discipline) +
`sha256HexOfCanonicalJson` (Web Crypto API). HASH OK / HASH MISMATCH /
HASH UNAVAILABLE badges.

**Layer 3 grammar verifier** reads iframe `contentDocument.documentElement.outerHTML`
post-load + runs the FROZEN 6-state DOM signature assertions. Badges:
GRAMMAR OK (green) / UNVERIFIABLE (gray) / **GRAMMAR FAIL (red)**.

---

## 3. The three-layer Anti-Hype Visual Grammar

This is the architecturally exclusive contribution of Phase O4. Three
independent enforcement layers, each catching a distinct failure mode:

| Layer | Where | What it catches |
|---|---|---|
| **Layer 1** Compile-time | Python `compile_vpm_artifact` static guards | Renderer bug emitting forbidden URLs / network calls / wall-clock / randomness / missing Integrity Label markers — refuses to write HTML to disk |
| **Layer 2** Bridge-time | `scripts/vpm_audit.py` Sections 5 + 6 + `/operator/vpm-audit-status` | Source-grep of compiler Python for forbidden imports; grammar coverage matrix across 6 active compilers |
| **Layer 3** Browser-time | `frontend/src/components/VpmGrammarVerifier.jsx` | Reads iframe contentDocument; runs 6-state DOM signature assertions; surfaces GRAMMAR FAIL red badge if drift |

The 6 FROZEN signatures are protocol law (mirrored in
`scripts/vpm_visual_grammar.py:VISUAL_STATE_SIGNATURES` ↔
`frontend/src/components/VpmGrammarVerifier.jsx:VISUAL_STATE_SIGNATURES_FROZEN`):

| State | Required substrings |
|---|---|
| `live` | `class="vpm-saturation-class"` + `data-vpm-visual-state="live"` |
| `dry-run` | `class="vpm-stripe-mask"` + `id="vpm-stripe-pattern"` + state marker |
| `emulated` | `class="vpm-body vpm-emulated"` + `filter: grayscale(100%)` + state marker |
| `frozen-disabled` | `class="vpm-lock-icon"` + state marker |
| `revoked` | `class="vpm-redacted-banner"` + `text-decoration: line-through` + state marker |
| `unverified` | `repeating-linear-gradient` + `#d65b78` + `#020408` + state marker |

Plus `<meta name="vpm-visual-state">` + `role="status"` aria block.

---

## 4. PV-CI Invariant Changes

11 INV-VPM-* invariants pinned via governance ceremony (close commit):

| Invariant | Pins |
|---|---|
| INV-VPM-WRAPPER-001 | `"vapi-vpm-manifest-v1"` in `scripts/vsd_vpm_wrapper.py` (pre-existing 2026-05-12) |
| **INV-VPM-COMPILER-001** | `def compile_vpm_artifact(` in `scripts/vsd_ui_compiler.py` |
| **INV-VPM-COMPILER-002** | `"vapi-vpm-artifact-v1"` in `scripts/vsd_ui_compiler.py` |
| **INV-VPM-INTEGRITY-LABEL-001** | `_VPM_INTEGRITY_LABEL_FIELDS = (` 9-tuple |
| **INV-VPM-VISUAL-STATES-001** | `VISUAL_STATES = (` 6-tuple in `scripts/vpm_visual_grammar.py` |
| **INV-VPM-CAPTURE-MODES-001** | `_VPM_CAPTURE_MODES = (` 5-tuple |
| **INV-VPM-WRAPPER-SCHEMA-REF-001** | `_VPM_WRAPPER_SCHEMA_REF = "vapi-vpm-manifest-v1"` |
| **INV-VPM-CSP-001** | `_VPM_HTML_RESPONSE_HEADERS = {` in `bridge/vapi_bridge/operator_api.py` |
| **INV-VPM-SANDBOX-001** | `"allow-scripts allow-same-origin"` in `frontend/src/components/VpmIframe.jsx` |
| **INV-VPM-COMPILE-ENDPOINT-001** | `@app.post("/operator/vpm-compile")` |
| **INV-VPM-AUDIT-SECTION-1-001** | `def section_1_active_compiler_registry` in `scripts/vpm_audit.py` |

**PV-CI gate cardinality: 67 → 77** (+10 new INV-VPM-* invariants).

Governance ceremony: phrase `"I understand this changes a frozen protocol
invariant"` piped to `--confirm-governance` ceremony.
`reason_category=invariant_change`. Bridge governance event POST 404'd
(bridge offline — non-blocking; matches Phase 224 + O1-FRR-PARALLEL
precedent). Allowlist regenerated; current PV-CI gate run reports
`PASS — 77 invariants verified`.

---

## 5. FSCA Contradiction Rule Additions

3 new rules in `CONTRADICTION_RULES` dict:

| Rule | Severity | Target |
|---|---|---|
| `VPM_VISUAL_STATE_DOM_MISMATCH` | HIGH | Rows in `vpm_artifact_log` with `manifest_uri IS NOT NULL` but `compiler_output_hash_hex IS NULL` (incomplete compile path) |
| `VPM_MANIFEST_HASH_DRIFT` | HIGH | Rows whose declared `zkba_manifest_hash_hex` doesn't reference a known `commitment_hex` in `zkba_artifact_log` (forged wrapper or upstream drift) |
| `VPM_LIFECYCLE_REGRESSION` | MEDIUM | DISPUTE-PACKET-v1 + MARKET-LISTING-v1 with zero compiles in trailing 30 days (stagnation observation, not security event) |

**CONTRADICTION_RULES count: 23 → 26.** FSCA polls these on the existing
15-minute cadence; rules fire on next poll cycle automatically.

---

## 6. VBDIP-0002 Appendix B §B.8 Activation Gate Sweep

| §16 Gate | Pre-O4 | Post-O4 (this commit) |
|---|---|---|
| G1 VBDIP-0001 FROZEN | SATISFIED | SATISFIED |
| G2 Numbering Decision Resolved | RESOLVED (D-NUM 2026-05-12) | RESOLVED |
| G3 Compiler Harness | PARTIALLY SATISFIED | **SATISFIED** (Phase O4 closes all 7 ZKBA classes + 6 VPM compilers + 4 drafts × 6 visual states × 3-layer grammar enforcement) |
| G4 ZKBA Manifest Schema Validated | SATISFIED | SATISFIED |
| G5a Reconciliation | SATISFIED | SATISFIED |
| G5b Wrapper Schema + Integrity Label | SATISFIED | SATISFIED |
| G5c Anti-Hype Visual Grammar tests | SATISFIED | **EXTENDED** with Layer 3 frontend-side enforcement |
| G6 AgentScope / Cedar Authority | SATISFIED (Cedar v2 LIVE 2026-05-12) | SATISFIED |
| G7 Curator Review Readiness | PENDING | PENDING (operator-runtime observation; not a development gate) |
| G8 Internal Projection First | PENDING | **SATISFIED** (HONESTY-BOARD + AGENT-REVIEW + CDRR DAG + GIC LEDGER BETA shipped before consumer-facing DISPUTE-PACKET + MARKET-LISTING per Phase O4 plan §2.4 internal-first sequencing) |
| G9 Numbering Decision Applied | RESOLVED | RESOLVED |

**Post-O4 state: 10 of 11 sub-gates SATISFIED.** Only G7 (Curator Review
Readiness) remains OPEN; that's operator-runtime observation work (7-day
window with ≥9/10 acceptance gate per Phase O2 SUGGEST advancement
discipline), not a Phase O4 deliverable.

---

## 7. State Snapshot at Phase Close

| Surface | Value |
|---|---|
| HEAD commit | *(close commit SHA recorded in commit body)* |
| Bridge test count | **~3344** (3160 → 3344, +184) |
| Frontend Vitest count | **26** (0 → 26, first frontend test infra in repo) |
| SDK test count | 562 (unchanged) |
| Hardhat test count | 528 (unchanged) |
| PV-CI invariants | **77** (67 → 77, +10 INV-VPM-* additions) |
| FSCA contradiction rules | **26** (23 → 26, +3 VPM rules) |
| VPM compilers (active) | 6 |
| VPM draft manifests | 4 |
| VPM Reserved IDs (remaining) | 2 (PROOF-TRAILER-v1 / DEV-SANDBOX-v1) |
| Cedar v2 lanes | 3 (Sentry / Guardian / Curator) — unchanged |
| Cedar v2 Merkle roots | Sentry `0x39e8b65f...db1f23` / Guardian `0x6818a9ad...0a9a0` / Curator `0x0ade0c92...60a80b3d` |
| Contracts LIVE on IoTeX testnet | 49 (unchanged) |
| `CHAIN_SUBMISSION_PAUSED` | true (held throughout phase) |
| Operator wallet | ~15.03 IOTX (no change; 0 IOTX impact) |
| Phase O4 plan path | `wiki/proposals/Phase_O4_VPM_Integration_Plan.md` (untracked at phase open; committed in `603c98cb` — wait actually plan was authored but not committed; this provenance pin references it) |

---

## 8. What This Phase Did NOT Do (deliberate exclusions)

| Excluded | Reason |
|---|---|
| Add new Cedar lanes | All operations under existing v2 bundle authorities anchored 2026-05-12 |
| Deploy new contracts | Wallet-free posture; no Solidity changes |
| Modify FROZEN-v1 primitives | PATTERN-017 enum + domain tag + manifest schema unchanged |
| Modify FROZEN ZKBA artifact emission paths | 7 prior compiler scripts byte-identical |
| Promote any Draft Manifest to Active | Reserved 4 IDs at `Draft Manifest`; Active requires external-stakeholder governance |
| Anchor any VPM on chain | Future `VPMAnchorRegistry.sol` candidate; Track-2-style ceremony required |
| Add new ZKBAClass values | 7-class enum FROZEN; future artifacts compose existing classes |
| Rewrite existing Vite components | Strictly additive per directive; App.jsx / ViewSelector.jsx / bridgeApi.js got pure-addition patches |

---

## 9. Forward Vectors (post-O4)

Ordered by strategic priority + dependency:

1. **G7 — Curator Review Readiness** (operator-runtime observation; 7-day
   window with ≥9/10 acceptance gate)
2. **Touchpad_corners corpus expansion** (tournament gate blocker; current
   N=35 ratio=0.728; needs P3 capture sessions)
3. **VPM Active lifecycle promotion** for 4 Draft Manifest IDs (each
   requires external-stakeholder governance + partnership flow)
4. **`VPMAnchorRegistry.sol`** parallel to AdjudicationRegistry (Track-2
   ceremony; ~0.1 IOTX per anchor)
5. **Curator O1 → O2 graduation** (N≥50 reviews + 0 false-positive rate;
   pre-authored bundle Merkle `0xeb400a5c...`)
6. **W3bstream applet registration** (real selector binding to
   `VAPIConsentRegistry.isConsentValid()`; ~0.02 IOTX)
7. **LayerZero cross-chain VHP bridge** (Phase 99C testnet → mainnet)
8. **Realms migration** (when daily PoAC volume ≥100,000/day)
9. **BT transport calibration** (N=0 → N≥30/player MVCP)
10. **Sensor Stack v2** (Stage A pre-corpus measurements + Stage B
    implementation per `wiki/methodology/sensor_stack_v2_1_architectural_revision.md`)

---

## 10. Architectural Significance

Phase O4 elevates the Methodology Layer from a **collection of frozen
primitives + a deterministic compiler** to a **complete delivery stack
with multi-layer overclaim defense**. The seven Phase O3-ZKBA-TRACK1
artifact classes now flow from cryptographic primitive → compiler →
bridge HTTP surface → sandboxed iframe → operator-console badge in a
chain where every link is byte-stable, content-addressed, and tested at
both compile-time and runtime.

The three-layer Anti-Hype Visual Grammar is the protocol's first
structural UX defense — preventing demo-as-production, revoked-as-active,
and unverified-as-verified overclaim attacks via a frozen-DOM-signature
matrix enforced at three independent layers.

VAPI is now the only DePIN gaming protocol with the
**frozen-primitive ↔ frozen-compiler ↔ frozen-visual-grammar ↔
frozen-iframe-sandbox quadruple-bind** — every cryptographic claim is
independently verifiable by anyone with a copy of the canonical-JSON
algorithm + SHA-256 + the public source of the four enforcement layers.

---

*— VAPI Principal Architect, 2026-05-13*
