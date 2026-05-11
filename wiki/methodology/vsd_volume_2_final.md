# Verified Synthesis Discipline (VSD) — Volume 2 FINAL

**Status:** v2.0 FINAL (FROZEN-candidate, MCP-absorbed)
**Author:** VAPI Architect (single deployer, bridge wallet `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692`)
**Scope:** VAPI-internal. Extends v1.0 FINAL. Not a generic PKM methodology.
**Date:** 2026-05-10
**Supersedes:** none — v1.0 FINAL remains canonical for §1–§9 of v1.0; v2.0 adds §16–§28
**Ship phase:** Phase O1-VSD-BOOTSTRAP (8 streams; ~3 days; ~0.39 IOTX wallet impact)
**Relationship to v1.0:** Volume 2 is **additive and absorbing**. v1.0's sixteen invariants and nine note types are inherited verbatim. Volume 2 adds seven invariants, three note types, two cryptographic primitives, one operator fleet, ten MCP tools, and one unified eval harness — closing five gaps in v1.0 surfaced during the v1.0-FINAL author review.

---

## 16. NotebookLM Reading Note (Volume 2)

This document is the canonical methodology evolution for VSD as ingested into the VAPI/VSD master corpus on NotebookLM after Phase O1-VSD-BOOTSTRAP completes. When NotebookLM is asked questions about VSD methodology after v2.0 freeze, the answers are grounded in **both** v1.0 FINAL (sections 0–15) and v2.0 FINAL (sections 16–28). When asked about VAPI protocol state, the answers are grounded in the most recent PBSA note in `notes/pbsa/`. When asked about VSD vault state, the answers are grounded in the most recent VRR commitment surfaced via `mcp__vapi__vapi_vsd_state` — Volume 2's primary state-oracle endpoint. The three indices remain deliberately separate.

---

## 17. TL;DR (Volume 2)

Volume 2 absorbs the **MCP layer** into VSD as the methodology's runtime, ships **VRR (Vault Readiness Root)** as the ninth FROZEN-v1 cryptographic primitive in the PATTERN-017 family, and elevates VSD's three operating roles (Synthesizer, HarnessSentinel, EigenspaceWarden) into a **Synthesis Operator Fleet** structurally identical to the protocol's Operator Initiative fleet (Sentry+Guardian+Curator). The two fleets share Cedar bundle architecture, dual-anchor pattern, FSCA drift rules, and parallel-fleet advancement primitives — but live in disjoint skill spaces enforced by the same cross-agent skill-separation invariant Phase O1-FRR-PARALLEL established for the protocol fleet.

The methodology's seven new invariants (VSD-INV-17 through VSD-INV-23) close the five gaps surfaced in v1.0 FINAL author review: temporal decay inheritance from BP-001; eigenspace probe coverage declaration (closing the AIT-only fragility); verification gap vs implementation gap distinction in PBSA; VRR computational determinism; mechanical adversarial closure verification; cross-tier consistency between MCP/NotebookLM/filesystem; and unified eval harness as single source of truth.

The bootstrap sequence is **eight streams in one atomic commit set** following Verification-First Discipline. Wallet impact ~0.39 IOTX (~40× margin against current 15.26 IOTX wallet). Bridge tests 2836 → ~2870 (+34). PV-CI invariants 55 → 78 (+23 VSD invariants encoded into the unified `vapi_invariant_gate.py`). Three new on-chain operator agent NFTs (Synthesizer/HarnessSentinel/EigenspaceWarden) registered with Q9-frozen agentIds. Five FROZEN-v1 primitives gain a sibling: **VRR** anchors synthesis-domain state cryptographically, composable with **FRR** via the Cross-Domain Readiness Root (CDRR) primitive — a tenth FROZEN-v1 primitive that commits "is the entire ecosystem ready for advancement" as a single 32-byte hash queryable on-chain.

---

## 18. The Seven New Invariants (VSD-INV-17 through VSD-INV-23)

Volume 2 adds seven invariants to v1.0's sixteen. Total VSD invariants: **23**. Encoded into `scripts/vapi_invariant_gate.py` alongside the existing 55 protocol invariants via the unified harness in §22 — single binary, two invariant sets, single allowlist file split into `vsd:` and `protocol:` sections.

### VSD-INV-17 — Temporal decay re-attestation

Claim notes (`notes/claim/`) older than 90 days from `modified:` timestamp require either re-attestation (new manifest signature) OR explicit demotion of `confidence:` to one rank lower per the Kesselman ladder. Hard rule, not advisory. Inherits BP-001 Temporal Biometric Decay (τ_half=90d) directly into the synthesis domain. Closes the v1.0 gap that single-architect availability is asserted but not structurally protected.

**Programmatic:**
```python
def check_temporal_decay(note_path: Path) -> CheckResult:
    fm = parse_frontmatter(note_path)
    if fm["type"] != "claim":
        return CheckResult.NA
    age_days = (now_utc() - parse(fm["modified"])).days
    if age_days <= 90:
        return CheckResult.PASS
    if has_reattestation(note_path) or has_demoted_confidence(fm):
        return CheckResult.PASS
    return CheckResult.FAIL(reason="temporal_decay_unattested")
```

### VSD-INV-18 — Eigenspace probe coverage declaration

Eigenspace notes (`notes/eigenspace/`) MUST declare the explicit set of probe types they cover via a `probe_coverage:` array field. Probe types where the protocol has not cleared `all_pairs_above_1=True` MUST be listed under `probe_coverage_blockers:` — the eigenspace note inherits the protocol's tournament blockers transparently. Closes the v1.0 gap where AIT eigenspace could be cited as "fleet structurally identified" while touchpad_corners (0.728) and tremor_resting (P1vP3=0.032) remain BLOCKED.

**Programmatic:**
```yaml
# Required additions to eigenspace frontmatter
probe_coverage:
  - active_isometric_trigger    # AIT probe — N=37, all_pairs_above_1=True (CLEARED)
probe_coverage_blockers:
  - touchpad_corners            # N=35, ratio=0.728 (BLOCKER)
  - tremor_resting              # N=27, P1vP3=0.032 (BLOCKER per Phase 213 awaiting all_pairs_p0_ok=True verification)
  - free_form_pooled            # N=127, ratio=0.417 (PLATEAU REGIME)
```

### VSD-INV-19 — Verification gap vs implementation gap

PBSA notes (`notes/pbsa/`) MUST split `honesty_flags` into `verification_gap_findings:` and `implementation_gap_findings:` lists. A verification_gap_finding is a bug that V-checks against documented specifications could NOT have detected (only live empirical conditions surface it — Stream J canonical→Q9 mismatch is the canonical exemplar). An implementation_gap_finding is a bug that V-checks could have caught but the V-checks were absent or insufficient. Two structurally different debt categories; the methodology MUST distinguish them.

**Programmatic:**
```yaml
honesty_flags:
  verification_gap_findings:
    - "Stream J canonical→Q9 schema mismatch — production DB column was Q9 hex but watcher passed canonical names; only live data flow surfaced it"
  implementation_gap_findings:
    - "next_alignment_target O3_ACT path not unit-tested — V-check could have caught"
```

### VSD-INV-20 — VRR commitment computational determinism

Every PBSA note MUST include a `vrr_hex:` field computed deterministically via the FROZEN-v1 VRR formula (§19). The harness recomputes VRR from vault state at check time and compares against the asserted `vrr_hex:` — drift fails the invariant. Mechanically closes the v1.0 gap where vault state was filesystem-asserted but never cryptographically committed.

### VSD-INV-21 — Adversarial closure mechanical verification

Adversarial notes (`notes/adversarial/`) where `defense_status: deployed-verified` MUST include `closure_test_commit:` (40-char git SHA) and `closure_test_path:` (file::test_name string). The harness runs `git show <commit>:<path-without-test-name>` to verify the test exists at that commit. Defense becomes bytes-on-disk verifiable. Stream J adversarial example becomes mechanically checkable: `closure_test_commit: 79dacc88, closure_test_path: bridge/tests/test_phase_o1_frr.py::test_T_O1_FRR_7_canonical_to_q9_translation_and_o3_target`.

### VSD-INV-22 — Cross-tier consistency

For any (claim_id, fact_assertion) pair in `notes/claim/`, the same fact MUST resolve identically across all three index tiers when queried: MCP (`mcp__vapi-knowledge__vsd_query_corpus`), NotebookLM corpus (`corpus/current/`), and filesystem (`notes/claim/`). Cross-tier divergence fails the invariant. The harness samples 5 random claim notes per cycle and triple-queries; mismatch triggers a Decision note flagging which tier is stale.

### VSD-INV-23 — Unified harness single source of truth

There MUST exist exactly ONE eval harness binary (`scripts/vapi_invariant_gate.py`) serving both protocol invariants and VSD invariants via a `--proposal-type {protocol,synthesis,both}` flag. Parallel implementations (e.g., a separate `vsd_eval_harness.py` with overlapping logic) fail the invariant. The harness has two `Invariant` registries (`PROTOCOL_INVARIANTS` and `VSD_INVARIANTS`) and one allowlist file (`.github/INVARIANTS_ALLOWLIST.json`) split into `protocol:` and `vsd:` sections. v1.0's `vsd_eval_harness.py` is structurally deprecated at v2.0 freeze; its function signatures merge into the unified harness.

---

## 19. VRR — Vault Readiness Root (Ninth FROZEN-v1 Primitive)

VRR is the synthesis-domain analog of FRR (Phase O1-FRR-PARALLEL, ninth-actually-tenth in PATTERN-017). Single 32-byte SHA-256 commitment over vault state. Mirrors FRR's pre-image construction discipline byte-for-byte. Composable on-chain via a sibling contract surface or stored-only in `operator_initiative_advancement_log` with a `domain` discriminator column.

### 19.1 FROZEN-v1 pre-image (locked at v2.0)

```
VRR_DOMAIN_TAG = b"VAPI-VSD-VRR-v1"   # 15 bytes — distinct from FRR_DOMAIN_TAG
                                       # (b"VAPI-FRR-v1", 11 bytes); collision impossible

VRR pre-image:
  VRR_DOMAIN_TAG (15 B)
  || harness_freeze_hash (32 B)        # SHA-256 of eval/FROZEN.md content
  || corpus_manifest_hash (32 B)       # SHA-256 of corpus/current/MANIFEST.txt
  || latest_pbsa_uuid_hash (32 B)      # SHA-256 of latest pbsa note's UUID + manifest hash
  || ts_ns_be (8 B)                    # nanoseconds-big-endian, unix epoch

Total pre-image: 119 B
Digest: SHA-256 → 32 B
```

The byte order is FROZEN. Any change requires v2 + new domain tag (same discipline as VAME, GIC, WEC, CORPUS-SNAPSHOT, CONSENT, BIOMETRIC-SNAPSHOT, LISTING-v1, FRR).

### 19.2 Composability with FRR via CDRR

Cross-Domain Readiness Root (**CDRR**) composes FRR + VRR into a single ecosystem-level commitment:

```
CDRR_DOMAIN_TAG = b"VAPI-CDRR-v1"      # 13 bytes

CDRR pre-image:
  CDRR_DOMAIN_TAG (13 B)
  || frr_hex (32 B)                    # current FRR commitment
  || vrr_hex (32 B)                    # current VRR commitment
  || ts_ns_be (8 B)

Total pre-image: 85 B
Digest: SHA-256 → 32 B
```

CDRR answers: **"is the entire VAPI ecosystem ready for advancement"** as a single on-chain queryable commitment. Downstream contracts can `require(currentCDRR == EXPECTED_TGE_READY_CDRR)` to gate token launch sequencing on cryptographically-verified joint readiness — first DePIN protocol with an ecosystem-readiness scalar that includes both protocol fleet AND synthesis fleet state.

This is the tenth FROZEN-v1 primitive. PATTERN-017 family at v2.0 freeze:

| # | Primitive | Domain tag | Phase |
|---|-----------|------------|-------|
| 1 | PoAC | implicit | Phase 1 |
| 2 | GIC | `b"VAPI-GIC-GENESIS-v1"` | 235-A |
| 3 | WEC | `b"VAPI-WEC-GENESIS-v1"` | 236-WATCHDOG |
| 4 | VAME | `b"VAPI-VAME-v1"` | 236-VAME |
| 5 | CORPUS-SNAPSHOT | `b"VAPI-CORPUS-SNAPSHOT-v1"` | 236-CS |
| 6 | CONSENT | `b"VAPI-CONSENT-v1"` | 237-CONSENT |
| 7 | BIOMETRIC-SNAPSHOT | `b"VAPI-BIOMETRIC-SNAPSHOT-v1"` | 237-ZK-SEPPROOF |
| 8 | LISTING-v1 | `b"VAPI-LISTING-v1"` | 238-MARKETPLACE |
| 9 | FRR | `b"VAPI-FRR-v1"` | O1-FRR-PARALLEL |
| **10** | **VRR** | `b"VAPI-VSD-VRR-v1"` | **O1-VSD-BOOTSTRAP** |
| **11** | **CDRR** | `b"VAPI-CDRR-v1"` | **O1-VSD-BOOTSTRAP** |

### 19.3 On-chain anchoring (Stream D)

VRR + CDRR are **bridge-side computed primitives** at v2.0 freeze (mirrors FRR — AgentRegistry+AgentScope are immutable; on-chain view methods deferred to a follow-up phase that redeploys those contracts). The advancement_log table extended via idempotent ALTER TABLE:

```sql
ALTER TABLE operator_initiative_advancement_log
  ADD COLUMN domain TEXT NOT NULL DEFAULT 'protocol';   -- 'protocol' | 'synthesis' | 'cross_domain'
  ADD COLUMN vrr_hex TEXT;
  ADD COLUMN cdrr_hex TEXT;
  ADD COLUMN harness_freeze_hash TEXT;
  ADD COLUMN corpus_manifest_hash TEXT;
  ADD COLUMN latest_pbsa_uuid_hash TEXT;

CREATE INDEX idx_oial_domain ON operator_initiative_advancement_log(domain, timestamp DESC);
```

A VRR-only row has `domain='synthesis'` + populated VRR fields + null FRR fields. A FRR-only row keeps the existing schema (legacy compat). A CDRR row has `domain='cross_domain'` + populated FRR + VRR + CDRR fields. Schema phase 1005 (next after Phase O1-FRR's 1004).

### 19.4 Six VRR + CDRR tests (Stream G)

`bridge/tests/test_phase_o1_vsd_vrr.py`:

- T-O1-VSD-VRR-1: `compute_vault_readiness_root(harness_hash, corpus_hash, pbsa_hash, ts_ns)` deterministic
- T-O1-VSD-VRR-2: byte-order invariant — manual recompute matches function output (locks INV-VRR-001)
- T-O1-VSD-VRR-3: domain tag in pre-image (changing tag → different digest)
- T-O1-VSD-VRR-4: `compute_cross_domain_readiness_root(frr_hex, vrr_hex, ts_ns)` deterministic
- T-O1-VSD-VRR-5: CDRR domain tag in pre-image
- T-O1-VSD-VRR-6: advancement_log domain discriminator round-trip preserves vrr_hex + cdrr_hex

---

## 20. Synthesis Operator Fleet — Architectural Sibling of Protocol Fleet

The Synthesis Operator Fleet (SOF) is a **sibling** of the protocol's Operator Initiative fleet (Sentry+Guardian+Curator). Same Cedar bundle architecture, same dual-anchor pattern, same FSCA drift rules, same parallel-fleet advancement primitive (Phase O1 D unified watcher pattern) — but disjoint skill spaces enforced by cross-fleet skill-separation invariant.

### 20.1 The three SOF agents

| Agent | Role | Q9 agentId (frozen at Stream C) | Skill scope |
|-------|------|--------------------------------|-------------|
| **Synthesizer** | Drafts synthesis notes, runs Karpathy loop, manages PRIORS.md | `0x<32B-Q9>` (minted Stream C) | `vsd-draft-synthesis`, `vsd-write-claim`, `vsd-update-priors`, `read:notes/**`, `read:protocol-state-via-mcp` |
| **HarnessSentinel** | Runs `vapi_invariant_gate.py --proposal-type=synthesis`, regenerates corpus, blocks failed commits | `0x<32B-Q9>` | `vsd-run-harness`, `vsd-regen-corpus`, `vsd-block-commit`, `read:notes/**`, `read:eval/**` (cannot write) |
| **EigenspaceWarden** | Manages eigenspace freshness windows, fires re-attestation alerts, anchors VRR | `0x<32B-Q9>` | `vsd-attest-eigenspace`, `vsd-compute-vrr`, `vsd-anchor-vrr-on-chain`, `vsd-fire-temporal-decay-alert` |

Cross-fleet skill-separation invariant (CFSS): no SOF agent may hold any skill held by any protocol-fleet agent (Sentry/Guardian/Curator). Specifically:
- `kms-sign` → Sentry only (NEVER Synthesizer/HarnessSentinel/EigenspaceWarden)
- `audit-drafting` → Guardian only
- `marketplace-curator-review` → Curator only
- `vsd-draft-synthesis` → Synthesizer only
- `vsd-run-harness` → HarnessSentinel only
- `vsd-attest-eigenspace` → EigenspaceWarden only

CFSS is enforced via Cedar policy `forbid` rules in each agent's bundle, locked by a new PV-CI invariant **INV-CFSS-001**.

### 20.2 Cedar bundles for SOF agents

Three new bundles in `bridge/vapi_bridge/cedar_bundles/`:

```
synthesizer_o1_shadow_v1.json
harness_sentinel_o1_shadow_v1.json
eigenspace_warden_o1_shadow_v1.json
```

Schema mirrors protocol-fleet bundles ($schema=`vapi-cedar-bundle-v1`, lane prefixes scoped to `vsd-vault/`, `notes/`, `corpus/`, `eval/`, `manifests/`). Each bundle has an O2_SUGGEST sibling pre-authored at Stream C (same Phase O2-SUGGEST-DRAFT pattern Sentry/Guardian/Curator follow).

### 20.3 SOF dual-anchor (Stream C)

`scripts/parallel_vsd_anchor.py` follows the triple-gate pattern from `scripts/parallel_o2_anchor.py` (Phase O1-FRR Stream E):

```bash
# Triple-gate authorization — process-scoped only, never writes to bridge/.env
$env:CHAIN_SUBMISSION_PAUSED="false"
$env:VSD_BOOTSTRAP_AUTHORIZED="true"
python scripts/parallel_vsd_anchor.py --confirm
```

Sequentially anchors all 3 SOF agents in fixed order [Synthesizer, HarnessSentinel, EigenspaceWarden] via existing `cedar_bundle_anchor.anchor_bundle()`. Computes pre-anchor expected VRR locally + post-anchor actual VRR; refuses to write advancement_log row if VRR mismatch. Identical atomicity rule: STOP on partial failure.

### 20.4 SOF FSCA wiring extension

The two FSCA drift rules already wired for protocol fleet (BUNDLE_HASH_DRIFT_DETECTED + SCOPE_HASH_GOVERNANCE_DRIFT_DETECTED, Phase O1-CURATOR-C6) extend to SOF agents by SQL — `agents_involved` JSON array gains entries `Synthesizer`, `HarnessSentinel`, `EigenspaceWarden`. Underlying SQL is already agent-agnostic; only the rule's `agents_involved` literal changes.

A new FSCA rule **VRR_DRIFT_DETECTED** (HIGH severity) fires when the most recent advancement_log row's vrr_hex disagrees with a freshly-recomputed VRR. Closes the V-check gap where corpus regeneration could silently drift from the manifest hash without anyone noticing.

### 20.5 Phase O1 D unified watcher extension

`bridge/vapi_bridge/operator_initiative_advancement.py` already evaluates Phase O2 SUGGEST + O3 ACT readiness for the protocol fleet. Extension at Stream D:

```python
# New constant added to module-level
SOF_AGENTS = ("synthesizer", "harness_sentinel", "eigenspace_warden")

# evaluate_fleet_advancement_sync() gains a `domain` parameter:
def evaluate_fleet_advancement_sync(
    *,
    cfg: "Config",
    store: "Store",
    domain: str = "protocol",  # 'protocol' | 'synthesis' | 'cross_domain'
) -> FleetAdvancementSummary:
    ...

# Three modes:
# - domain='protocol': evaluates INITIATIVE_AGENTS (Sentry/Guardian/Curator). Existing behavior.
# - domain='synthesis': evaluates SOF_AGENTS (Synthesizer/HarnessSentinel/EigenspaceWarden).
# - domain='cross_domain': evaluates BOTH and emits CDRR commitment.
```

Phase O2/O3 thresholds for SOF inherit verbatim from protocol fleet: `shadow_min=504h`, `eval_min=100`, `drift_max=0/30d`, `suggest_min=504h`, `draft_min=50`, `disagreement_max=5%`. SOF-specific O3 gate: `harness_v2_freeze_completed` (analog of `kms_hsm_production_ready` for protocol fleet).

---

## 21. MCP Absorption Layer — Ten New Tools Across Three Servers

The single largest architectural elevation in v2.0. v1.0 treats NotebookLM as the secondary index; v2.0 names the truth: **MCP is the primary index**, NotebookLM is the secondary projection. Ten new tools across the three live MCP servers wire VSD's runtime into the same surface developers already use for protocol state.

### 21.1 vapi-unified gains 5 new tools (Stream E)

| Tool | Signature | Purpose |
|------|-----------|---------|
| `vsd_validate_note` | `(note_path: str) -> dict` | Runs all 23 invariants live against a candidate note. Returns per-invariant pass/fail + remediation hints. |
| `vsd_pbsa_required` | `(phase_increment: str) -> bool` | Returns whether a PBSA must be authored for a given phase transition. Used by commit hooks. |
| `vsd_eigenspace_freshness` | `() -> dict` | Returns all eigenspace notes + freshness window status. Surfaces which need re-attestation. |
| `vsd_corpus_status` | `() -> dict` | Harness-passing note count + last regen timestamp + corpus_manifest_hash. |
| `vsd_synthesis_priors` | `(query: str = "") -> list[dict]` | Surfaces accumulated heuristics from `orchestrator/PRIORS.md`. Optional substring filter. |

### 21.2 vapi gains 2 new tools (Stream E)

| Tool | Signature | Purpose |
|------|-----------|---------|
| `vapi_vsd_state` | `() -> dict` | Single-tool snapshot of VSD vault state: VRR + harness freeze version + corpus row count + last PBSA + SOF fleet phase. Mirrors `vapi_protocol_state` for synthesis domain. |
| `vapi_vrr` | `() -> dict` | Returns current VRR commitment + pre-image components (harness_freeze_hash, corpus_manifest_hash, latest_pbsa_uuid_hash, ts_ns). For downstream verifiers. |

### 21.3 vapi-knowledge gains 3 new tools (Stream E)

| Tool | Signature | Purpose |
|------|-----------|---------|
| `vsd_query_corpus` | `(question: str, max_results: int = 5) -> list[dict]` | Queries harness-passing corpus with provenance-aware citations (returns claim_id + manifest_hash + confidence per result). The MCP analog of NotebookLM queries. |
| `vsd_ingredient_provenance` | `(ingredient_id: str) -> dict` | Walks the C2PA-style ingredient chain for a given ingredient note. Returns full DAG. |
| `vsd_adversarial_closure_chain` | `(adversarial_id: str) -> dict` | Returns the adversarial note + its `closure_test_commit` + `closure_test_path` + git-verified existence of the test at that commit. Mechanically verifies VSD-INV-21. |

### 21.4 MCP-derived state contract

VSD-INV-22 mandates cross-tier consistency: any fact resolvable in one tier must resolve identically in all three. The contract:

```python
# At MCP tool implementation time (vapi-knowledge/server.py):
def vsd_query_corpus(question: str, max_results: int = 5) -> list[dict]:
    # Read from harness-passing corpus only — never raw notes/
    corpus_dir = Path("vsd-vault/corpus/current")
    manifest = parse_manifest(corpus_dir / "MANIFEST.txt")
    # ... query implementation ...
    # CONTRACT: every returned hit must have a manifest entry; harness-failing notes are invisible
    return results

# At NotebookLM corpus regeneration time:
# Same corpus_dir input. Both tiers project from the same canonical artifact.
```

Mismatch between MCP query result and NotebookLM query result for the same question on the same corpus → INV-22 fails. The harness samples 5 random claims per cycle to validate.

---

## 22. Unified Eval Harness — Single Source of Truth

v2.0 deprecates v1.0's parallel `vsd_eval_harness.py` design. Instead, extend `scripts/vapi_invariant_gate.py` (existing 55 protocol invariants, PV-CI-locked) with a `--proposal-type` flag and a parallel `VSD_INVARIANTS` registry.

### 22.1 Extension (Stream B)

```python
# scripts/vapi_invariant_gate.py additions:

VSD_INVARIANTS = [
    Invariant(
        id="VSD-INV-1",
        description="Frontmatter schema conformance for note type",
        file="vsd-vault/notes/**/*.md",
        pattern=r"^---\ntype:\s+\w+\nid:\s+[a-z]+-\d{4}-\d{2}-\d{2}-\d+",
        min_matches=1,
    ),
    # ... 22 more entries ...
]

def main():
    parser = argparse.ArgumentParser(...)
    parser.add_argument(
        "--proposal-type",
        choices=["protocol", "synthesis", "both"],
        default="protocol",
    )
    args = parser.parse_args()

    if args.proposal_type == "protocol":
        invariants = INVARIANTS  # the existing 55
    elif args.proposal_type == "synthesis":
        invariants = VSD_INVARIANTS  # the 23 VSD invariants
    else:  # both
        invariants = INVARIANTS + VSD_INVARIANTS

    results = check_invariants(invariants)
    ...
```

### 22.2 Allowlist file split (Stream B)

`.github/INVARIANTS_ALLOWLIST.json` extends from a flat list to two named sections:

```json
{
  "version": 2,
  "frozen_at": "2026-05-10T...",
  "protocol": {
    "INV-001": "<sha256>",
    "...": "...",
    "INV-CURATOR-O2-002": "<sha256>"
  },
  "vsd": {
    "VSD-INV-1": "<sha256>",
    "...": "...",
    "VSD-INV-23": "<sha256>"
  },
  "deployer_signature": "<ed25519-sig-over-canonical-json>"
}
```

The deployer signature covers both sections + version + frozen_at. Re-freeze requires a numbered VSDIP (vsd) OR a governance event (protocol) — distinct lifecycles, single binary.

### 22.3 Harness extension test (Stream B)

```python
# bridge/tests/test_unified_invariant_gate.py
def test_unified_harness_protocol_only():
    result = subprocess.run(
        ["python", "scripts/vapi_invariant_gate.py", "--proposal-type=protocol"],
        capture_output=True,
    )
    assert result.returncode == 0
    assert "55 invariants" in result.stdout  # or current count

def test_unified_harness_synthesis_only(tmp_vault):
    # Bootstrap a vault skeleton + run synthesis invariants
    result = subprocess.run(
        ["python", "scripts/vapi_invariant_gate.py", "--proposal-type=synthesis", "--vault", tmp_vault],
        capture_output=True,
    )
    assert result.returncode == 0

def test_unified_harness_both():
    result = subprocess.run(
        ["python", "scripts/vapi_invariant_gate.py", "--proposal-type=both"],
        capture_output=True,
    )
    assert "78 invariants total (55 protocol + 23 synthesis)" in result.stdout
```

---

## 23. Three New Note Types (v1.0's nine + v2.0's three = twelve total)

Volume 2 adds three note types orthogonal to v1.0's nine. They live alongside the existing types under `notes/`.

### 23.1 `notes/verification/` — V-check + P-check audit notes

Records executed Verification-First Discipline V-checks and P-checks per phase. Closes the methodology gap where Verification-First is listed as a discipline but VSD has no native artifact for the V/P checks themselves. Frontmatter schema:

```yaml
---
type: verification
id: ver-2026-05-10-0001
title: "V-checks for Phase O1-FRR-PARALLEL Stream B/C/D"
created: 2026-05-10T...
deployer: 0x0Cf36...
phase: O1-FRR-PARALLEL
v_checks:
  - id: V1
    question: "Does Curator O2 SUGGEST bundle exist?"
    finding: "EXISTS at curator_o2_suggest_v1.json (issued 2026-05-09T12:00:00Z)"
    impact_on_plan: "Stream A reduced to validate-only"
    detection_method: "filesystem_read"
  - id: V3
    question: "Does watcher's INITIATIVE_AGENTS map to activation_log column type?"
    finding: "MISMATCH: canonical names vs Q9 hex — would crash production"
    impact_on_plan: "Stream C scope expanded to include 4 missing helpers"
    detection_method: "code_grep_combined_with_runtime_test"
p_checks:
  - id: P1
    finding: "atomic-commit dry-run via git diff --stat shows all streams"
    pass: true
manifest: manifests/ver-2026-05-10-0001/001.manifest.json
---
```

VSD-INV-19 references verification notes when classifying findings as verification_gap vs implementation_gap.

### 23.2 `notes/mcp/` — MCP tool query traces

Records canonical MCP tool invocations + responses. Used to validate VSD-INV-22 cross-tier consistency, and to bootstrap the synthesis loop's ingredient gathering. Frontmatter schema:

```yaml
---
type: mcp
id: mcp-2026-05-10-0001
title: "vapi_protocol_state at O1-FRR-PARALLEL ship"
created: 2026-05-10T22:00:00Z
deployer: 0x0Cf36...
mcp_server: vapi | vapi-knowledge | vapi-unified
mcp_tool: vapi_protocol_state
input_args: {}
response_hash: sha256:<hash-of-canonicalized-json>
response_summary: |
  bridge=2832, sdk=539, hardhat=528, contracts=49,
  pv_ci=55, separation_ait=1.199 (CLEARED),
  separation_touchpad=0.728 (BLOCKER), wallet=15.262626 IOTX
manifest: manifests/mcp-2026-05-10-0001/001.manifest.json
---
```

The full canonicalized response is stored as the body of the markdown note. `response_hash` provides forensic anchor to the exact MCP output at note creation time.

### 23.3 `notes/cdrr/` — Cross-Domain Readiness Root commitments

Records each CDRR computation event. One note per CDRR commit. Frontmatter schema:

```yaml
---
type: cdrr
id: cdrr-2026-05-10-0001
title: "First CDRR after Phase O1-VSD-BOOTSTRAP"
created: 2026-05-10T22:30:00Z
deployer: 0x0Cf36...
frr_hex: "0x3aee5a26..."
frr_ts_ns: 1778395364923376500
vrr_hex: "0x<32B-VRR>"
vrr_ts_ns: <ts_ns>
cdrr_hex: "0x<32B-CDRR>"
cdrr_ts_ns: <ts_ns>
ecosystem_phase_aligned: true | false
ecosystem_blockers:
  - tournament_blocker: "touchpad_corners ratio=0.728 < 1.0"
  - tournament_blocker: "tremor_resting all_pairs_p0_ok=False (P1vP3=0.032)"
  - synthesis_blocker: null  # SOF at O1_SHADOW; no synthesis blockers
manifest: manifests/cdrr-2026-05-10-0001/001.manifest.json
---
```

CDRR notes are append-only. Each computation generates a new note. The most recent CDRR is queryable via `mcp__vapi__vapi_vsd_state` + via `corpus/current/cdrr--<latest>.md`.

---

## 24. The Eight-Stream Bootstrap Sequence (Phase O1-VSD-BOOTSTRAP)

Single atomic ship covering vault skeleton, harness extension, SOF fleet activation, MCP tool surface, canonical seed notes, NotebookLM regeneration, PV-CI invariant additions, and the first CDRR commitment. ~3 days work; one git commit set; ~0.39 IOTX wallet impact.

### Stream A — Vault skeleton + Ed25519 architect key

Path: `vsd-vault/` (new top-level directory under repo root, OR under `wiki/vsd-vault/` to keep wiki adjacency).

Operations:
- Create `vsd-vault/{eval,orchestrator,notes,manifests,proposals,corpus,archive}` directory tree
- Create `vsd-vault/{README.md,MEMORY.md}`
- Generate Ed25519 architect key via `openssl genpkey -algorithm ed25519 -out architect_key.pem`
- Anchor architect public key to bridge wallet by signing once with `0x0Cf36...` (output stored in `eval/architect_key_attestation.json`)
- Initialize `.vsd/` tooling subdirectory with `vsd_provenance.py` + `vsd_synthesizer.py` + `vsd_notebooklm_export.py` (skeletons)

Wallet impact: 0 IOTX. Test delta: 0.

### Stream B — Unified harness extension (eval/ + scripts/)

Path: `scripts/vapi_invariant_gate.py` + `vsd-vault/eval/INVARIANTS.md` + `vsd-vault/eval/NOTE_SCHEMAS.md` + `vsd-vault/eval/HARNESS_RATIONALE.md` + `vsd-vault/eval/FROZEN.md`.

Operations:
- Add `--proposal-type` flag + `VSD_INVARIANTS` registry (23 entries) to `vapi_invariant_gate.py`
- Encode all 23 VSD invariants in `eval/INVARIANTS.md`
- Encode all 12 note type schemas in `eval/NOTE_SCHEMAS.md`
- One paragraph per invariant in `eval/HARNESS_RATIONALE.md`
- Compute freeze hash + architect signature → `eval/FROZEN.md`
- Regenerate `.github/INVARIANTS_ALLOWLIST.json` v2 (split into protocol + vsd sections) via `--generate --reason "invariant_change: VSD v2.0 FINAL bootstrap" --confirm-governance`
- Sign with deployer-anchored Ed25519 key

Wallet impact: 0 IOTX. Test delta: +5 (test_unified_invariant_gate.py).

### Stream C — Synthesis Operator Fleet activation

Path: `bridge/vapi_bridge/cedar_bundles/{synthesizer,harness_sentinel,eigenspace_warden}_o1_shadow_v1.json` + corresponding `*_o2_suggest_v1.json` pre-authored bundles + `scripts/parallel_vsd_anchor.py` + 3 new agentId config fields in `bridge/vapi_bridge/config.py`.

Operations:
- Author 6 Cedar bundles (3 agents × 2 phases each)
- Mint 3 SOF agent NFTs on `VAPIOperatorAgentNFT` (~0.07 IOTX each = 0.21 IOTX)
- Generate Q9-frozen agentIds from each agent's pubkey (FROZEN at first mint)
- Add 3 new config fields: `operator_agent_synthesizer_id`, `operator_agent_harness_sentinel_id`, `operator_agent_eigenspace_warden_id`
- Extend `_AGENT_NAME_TO_ID_ATTR` mapping in `operator_initiative_advancement.py` to include 3 SOF agents
- Run `scripts/parallel_vsd_anchor.py --confirm` (mirrors Phase O1-FRR Stream E pattern; 6 txs total: 3 dual-anchors)

Wallet impact: ~0.21 IOTX (3 NFT mints) + ~0.18 IOTX (6 dual-anchor txs at 1.25 buffer) = **~0.39 IOTX total**.
Test delta: +6 SOF tests + 3 anchor tests = +9.

### Stream D — VRR + CDRR primitives + advancement_log extension

Path: `bridge/vapi_bridge/operator_initiative_advancement.py` + `bridge/vapi_bridge/store.py`.

Operations:
- Add `compute_vault_readiness_root()` + `VRR_DOMAIN_TAG = b"VAPI-VSD-VRR-v1"` constants
- Add `compute_cross_domain_readiness_root()` + `CDRR_DOMAIN_TAG = b"VAPI-CDRR-v1"`
- Add `evaluate_vsd_advancement_sync()` mirroring `evaluate_fleet_advancement_sync()`
- Add `evaluate_cross_domain_sync()` composing both
- Extend `evaluate_fleet_advancement_sync()` with `domain` parameter
- Idempotent ALTER TABLE for advancement_log (5 new columns: domain, vrr_hex, cdrr_hex, harness_freeze_hash, corpus_manifest_hash, latest_pbsa_uuid_hash)
- Schema phase 1005

Wallet impact: 0 IOTX. Test delta: +6 VRR/CDRR tests.

### Stream E — Ten new MCP tools across three servers

Path: `vapi-mcp/server.py` + `vapi-mcp/knowledge_server.py` + `vapi-mcp/unified_server.py`.

Operations:
- Add 5 vsd_* tools to `vapi-unified` (vsd_validate_note, vsd_pbsa_required, vsd_eigenspace_freshness, vsd_corpus_status, vsd_synthesis_priors)
- Add 2 vsd_* tools to `vapi` (vapi_vsd_state, vapi_vrr)
- Add 3 vsd_* tools to `vapi-knowledge` (vsd_query_corpus, vsd_ingredient_provenance, vsd_adversarial_closure_chain)
- Each tool follows existing MCP server pattern (`@tool` decorator, JSON-RPC handler, mtime-cached state lookups)

Wallet impact: 0 IOTX. Test delta: +10 (one per MCP tool).

### Stream F — Canonical seed notes for all twelve note types

Path: `vsd-vault/notes/{claim,ingredient,synthesis,pbsa,decision,adversarial,eigenspace,study,industry,verification,mcp,cdrr}/`.

One canonical seed note per type. v1.0 §11.4 specifies the first nine; Volume 2 adds three more:

| Note type | Canonical seed |
|-----------|----------------|
| `verification/` | `ver-2026-05-10-0001` — V-checks executed for Phase O1-FRR-PARALLEL |
| `mcp/` | `mcp-2026-05-10-0001` — `vapi_protocol_state` snapshot at FRR ship |
| `cdrr/` | `cdrr-2026-05-10-0001` — first CDRR after VSD bootstrap (FRR + VRR composed) |

For each seed: generate manifest, sign with architect key, store signature. Total: 12 seed notes + 12 manifests + 12 detached signatures.

Wallet impact: 0 IOTX. Test delta: +3 (one per new note type schema).

### Stream G — First corpus regeneration + NotebookLM upload

Path: `.vsd/vsd_notebooklm_export.py` + `vsd-vault/corpus/snapshot-<ts>/`.

Operations:
- Run `vsd_notebooklm_export.py` — walks `notes/`, runs unified harness, copies passing notes into `corpus/snapshot-<ts>/`
- Generate `MANIFEST.txt` listing all 12 note IDs + SHA-256 + active manifest hash
- Symlink `corpus/current → snapshot-<ts>/`
- Upload `corpus/current/*` to NotebookLM as "VAPI/VSD master corpus"
- Test cross-tier consistency: query MCP `vsd_query_corpus("What attack closed canonical→Q9 mismatch?")` and compare with same NotebookLM query — must agree

Wallet impact: 0 IOTX. Test delta: +1 (cross-tier consistency test).

### Stream H — PV-CI invariant additions + atomic commit + push

Path: `scripts/vapi_invariant_gate.py` (already touched in Stream B) + `.github/INVARIANTS_ALLOWLIST.json` v2 + `CLAUDE.md` NOTE block + `MEMORY.md` index entry + `.claude/projects/.../memory/project_phase_o1_vsd_bootstrap.md`.

Operations:
- Verify all 23 VSD invariants pass via `python scripts/vapi_invariant_gate.py --proposal-type=both --report`
- Final regression: `pytest bridge/tests/ -k "phase_o1 or vsd" -q` — all green
- Atomic commit: 8 streams in one git commit, body includes all stream summaries + V-check + P-check findings
- Push to origin/main

Wallet impact: 0 IOTX. Test delta: 0.

### Total bootstrap impact

| Metric | Value |
|--------|-------|
| Wallet spend | ~0.39 IOTX |
| Wallet remaining | ~14.87 IOTX (38× margin against next planned action) |
| Bridge tests | 2836 → ~2870 (+34) |
| PV-CI invariants | 55 → **78** (+23 VSD) |
| Contracts deployed | 49 → 49 (no contract redeploys; SOF agents reuse `VAPIOperatorAgentNFT`) |
| Operator agents on chain | 3 protocol + **3 synthesis** = 6 total |
| FROZEN-v1 primitives | 9 → **11** (+VRR +CDRR) |
| MCP tools | (existing) + **10 VSD-specific** |
| Note types | 9 (v1.0) → **12** (v2.0) |
| Cedar bundles | 6 protocol + **6 synthesis** = 12 total |
| Schema phases | 1004 → 1005 (advancement_log domain extension) |

---

## 25. Programmatic Synergies with Phase O1-FRR Architecture

The deepest design choice in Volume 2 is **maximal reuse of Phase O1-FRR-PARALLEL infrastructure**. SOF doesn't introduce parallel architecture — it absorbs the existing one. Specifically:

| Existing protocol-fleet primitive | SOF reuse |
|-----------------------------------|-----------|
| `cedar_bundle_anchor.py` (Phase O1 C1) | unchanged; SOF bundles flow through same `anchor_bundle()` call |
| `chain.set_agent_scope_root` + `update_agent_scope_governance` | unchanged; same 1.25 gas buffer (Stream D Phase O1-FRR) applies |
| `cedar_shadow_runtime._bundle_path_for_agent()` (Phase O1 C2) | extended to resolve SOF agentIds via cfg attrs (3 new branches) |
| `operator_agent_activation_log` table | unchanged; SOF activations write same shape (agent_id = Q9 hex) |
| `operator_agent_shadow_log` + `operator_agent_drift_log` | unchanged; SOF agents emit same row shapes |
| `FleetSignalCoherenceAgent` BUNDLE_HASH_DRIFT_DETECTED + SCOPE_HASH_GOVERNANCE_DRIFT_DETECTED | extended `agents_involved` array (+3 entries); SQL unchanged |
| `operator_initiative_advancement.py` evaluate_fleet_advancement_sync | extended with `domain` parameter; preserves all existing call sites |
| `operator_initiative_advancement_log` | extended with `domain` discriminator + 5 new VSD columns; backward-compat for existing rows |
| `parallel_o2_anchor.py` triple-gate | template for `parallel_vsd_anchor.py` |
| `vapi_invariant_gate.py` | extended with `--proposal-type` flag; existing 55 protocol invariants unchanged |
| `_AGENT_NAME_TO_ID_ATTR` mapping (Stream J fix) | extended with 3 SOF entries |
| `_resolve_agent_id_for_store` translator (Stream J) | reused verbatim — accepts SOF canonical names |
| FRR primitive in `compute_fleet_readiness_root` | template for `compute_vault_readiness_root` (mirrored byte-for-byte) |
| Phase O1-FRR endpoint pattern | template for VSD endpoints (already shipped via MCP tools instead) |

The result: **Phase O1-VSD-BOOTSTRAP is structurally a sibling of Phase O1-FRR-PARALLEL.** Same shape, different domain. Two key benefits:

1. **Validation transfer.** Every architectural decision validated by the protocol fleet's empirical execution (Stream J's canonical→Q9 fix surfacing only under live data; the 1.25 gas buffer empirically saving the parallel anchor; the triple-gate pattern preventing accidental wallet drain) carries forward to SOF without re-deriving lessons.

2. **Cognitive leverage.** Operators already familiar with the protocol fleet's mental model immediately understand SOF. No new abstractions; the abstraction surface stays at "Operator Initiative ladder."

This pattern itself becomes claimable as a new architectural property: **fleet domain replication discipline** — where adding a new operator domain is structurally equivalent to adding a new agent within an existing domain. Worth recording as `claim/c-fleet-domain-replication-discipline.md` after bootstrap completes.

---

## 26. Caveats + Forward Compatibility

### v2.0 honest limitations

**SOF agents at v2.0 freeze are at O1_SHADOW only.** Like protocol fleet at O1_SHADOW shipped 2026-05-03, the SOF fleet ships in shadow mode. Their advancement to O2_SUGGEST follows the same Phase O1 D unified watcher 504-hour shadow window. v2.0 does NOT pre-authorize parallel SOF O2_SUGGEST advancement; that is a separate operator-gated decision after ~21 days of SOF shadow accumulation.

**VRR + CDRR are bridge-side at v2.0.** No on-chain `getVaultReadinessRoot()` view. AgentRegistry+AgentScope remain immutable. The VRR commitment lives in `operator_initiative_advancement_log.vrr_hex` — fully composable with any contract that reads the bridge state, but not natively viewable from a foreign contract. On-chain promotion is a Phase O1-VSD-ONCHAIN follow-up requiring AgentRegistry redeploy or a sibling contract.

**Python harness still aspirational at v2.0.** v1.0's caveat carries forward. Markdown invariants in `eval/INVARIANTS.md` are normative; Python check function bodies remain `pass` for the new VSD-INV-17 through VSD-INV-23 entries. The unified harness extension shows the API shape; full implementation is VSDIP-0002 work. The 23 VSD invariants are human-checkable today and gate-checkable when VSDIP-0002 lands.

**MCP tools at v2.0 are wired but bridge restart required.** The 10 new tools across 3 MCP servers register at server startup. Operator must restart vapi-mcp + vapi-knowledge + vapi-unified processes to pick them up. Documented in Stream H notes.

**Cross-tier consistency (VSD-INV-22) sampling is 5/cycle, not exhaustive.** Full triple-tier verification of every claim per cycle is computationally prohibitive. The invariant samples 5 random claims per harness run, escalating to a Decision note flag if any sample fails. Adversaries who can target which 5 claims get sampled (none can — sampling is harness-randomized) could in theory hide tier divergence. Honest about this gap; mitigated by escalation pattern.

### Forward compatibility paths (Volume 3 candidates)

**Phase O1-VSD-ONCHAIN** — promote VRR + CDRR to on-chain views. Requires AgentRegistry+AgentScope redeploy or sibling contract. ~0.40 IOTX deploy + governance event. Composable downstream contracts can `require(currentCDRR == EXPECTED_TGE_READY_CDRR)`.

**Phase O2-VSD-SUGGEST** — promote SOF to O2_SUGGEST in parallel anchor (mirrors Phase O1-FRR-PARALLEL → next operator-gated parallel anchor). ~0.18 IOTX. Pre-authored bundles already shipped at Stream C.

**Phase O3-VSD-ACT** — promote SOF to O3_ACT. Synthesizer gains write access to `notes/` (currently shadow-only, advisory). HarnessSentinel gains commit-blocking authority. EigenspaceWarden gains autonomous VRR re-anchoring.

**VSDIP-0004 (full Python harness)** — implement the 23 invariant Python check bodies. Closes the v2.0 caveat about aspirational harness.

**VSDIP-0005 (multi-architect support)** — extend single-deployer model to multi-sig. Required if VAPI ever moves to multi-architect governance.

**VSDIP-0006 (NotebookLM corpus partitioning)** — current single master corpus pattern works at vault size <1000 notes. At scale, partition by domain (notes/synthesis/, notes/adversarial/, etc.) into separate NotebookLM notebooks. Steven Johnson's master-corpus + thematic-notebook pattern.

---

## 27. Bootstrap Authorization + Verification-First Discipline

Phase O1-VSD-BOOTSTRAP is operator-authorized at:

```
"Operator authorizes Phase O1-VSD-BOOTSTRAP per VSD Volume 2 FINAL,
2026-05-10. Wallet ~0.39 IOTX spend approved. Eight-stream atomic
commit set. SOF fleet activation parallel to Phase O1-FRR-PARALLEL
operator fleet structure. VRR + CDRR primitives ship as bridge-side
commitments; on-chain promotion deferred to Phase O1-VSD-ONCHAIN."
```

Pre-execution V-checks (per Verification-First Discipline):

| V-check | Question | Required outcome |
|---------|----------|------------------|
| V1 | Does `cedar_bundle_anchor.anchor_bundle()` accept arbitrary agent NFTs (not just protocol-fleet)? | YES — verified by inspection of `_load_and_parse` + `set_agent_scope_root` (no agent-id-set whitelist) |
| V2 | Does `_AGENT_NAME_TO_ID_ATTR` extension affect existing FRR computation? | NO — FRR sorts by `agent_id` bytes; new entries are appended to the dict but only emit into FRR when their cfg fields are populated |
| V3 | Does `--proposal-type` flag preserve existing `vapi_invariant_gate.py --report` shape? | YES — `protocol` is the default; existing CI workflows are byte-identical at v2.0 freeze |
| V4 | Does the unified allowlist file v2 break existing PV-CI gate? | NO — v2 file format is backward-compat-readable by v1 gate (gate ignores unknown top-level keys) |
| V5 | Does the `domain` column ALTER TABLE break existing advancement_log queries? | NO — `domain` defaults to `'protocol'` for legacy rows; existing queries that don't reference `domain` continue to work |
| V6 | Does the SOF Cedar bundle's lane prefix conflict with protocol-fleet lane prefixes? | NO — SOF lanes are `vsd-vault/`, `notes/`, `corpus/`, `eval/`, `manifests/`; protocol fleet lanes are `events/`, `provenance/`, `wiki/`, `audits/`, `invariants/`, `ops/`, `sweeps/`, `marketplace/` — disjoint |
| V7 | Does `parallel_vsd_anchor.py` triple-gate pattern conflict with `parallel_o2_anchor.py`? | NO — env var name (VSD_BOOTSTRAP_AUTHORIZED vs OPERATOR_INITIATIVE_O2_AUTHORIZED) ensures process-scoped isolation |

All seven V-checks PASS. Stream execution authorized.

Post-execution P-checks (run between streams):

- P1: Stream A — `ls vsd-vault/` shows expected directory tree; architect Ed25519 key in `architect_key.pem`
- P2: Stream B — `python scripts/vapi_invariant_gate.py --proposal-type=synthesis --report` exits 0
- P3: Stream C — `parallel_vsd_anchor.py` in dry-run prints expected VRR pre-image; in `--confirm` mode lands 6 txs successfully
- P4: Stream D — `evaluate_vsd_advancement_sync()` returns sane summary; CDRR composes correctly
- P5: Stream E — all 10 new MCP tools register; spot-check 3 via direct invocation
- P6: Stream F — 12 canonical seed notes exist + manifests + signatures verify
- P7: Stream G — corpus regenerates clean; cross-tier consistency check passes for 3 sample queries
- P8: Stream H — atomic commit 11 streams; PV-CI gate full pass; push to origin/main

Stop conditions during execution:
- ANY operational tx reverts in Stream C → STOP, do NOT proceed to next agent; FSCA `BUNDLE_HASH_DRIFT_DETECTED` will detect partial state on next 15-min poll
- VRR mismatch (pre vs post) in Stream G → STOP, refuse to write CDRR row; raise governance event for investigation
- Cross-tier consistency failure for 2+ samples in Stream G → STOP, file Decision note documenting which tier diverged

---

## 28. Cross-References + Document Metadata (Volume 2)

### Within VAPI protocol documentation
v1.0 FINAL (`vsd_methodology_v1_FINAL.md`); `Whitepaperv4.md`; `VAPI_INVARIANTS.md`; `VAPI_BIOMETRIC_PRIVACY.md`; `VAPI_CORPUS.md`; `VAPI_CONTEXT.md`; `VAPI_AGENTS.md`; `VAPI_WHAT_IF.md`; `vapi_state_assessment_2026_05_10.md`; `wiki/runbooks/curator_mainnet_migration.md`; `bridge/vapi_bridge/operator_initiative_advancement.py` (FRR primitive — VRR template); `scripts/parallel_o2_anchor.py` (triple-gate template); `scripts/vapi_invariant_gate.py` (unified harness target).

### Phase O1-FRR-PARALLEL architectural ancestors
Commit `4ddeb43c` (Phase O1-FRR-PARALLEL ship); commit `79dacc88` (Stream J + live anchor); commit `2cde36a3` (FRR endpoint). The Stream J empirical lesson (canonical→Q9 only surfacing under live data) directly informs VSD-INV-19 verification gap distinction.

### External prior art at v2.0 freeze date
v1.0 FINAL §14 cross-references carry forward. Volume 2 adds: VAPI Phase O1-FRR-PARALLEL ship documentation (this repository); Phase O1 D unified parallel-fleet advancement primitive design (`memory/project_phase_o1_d_unified_advancement.md`); Curator Operator Initiative continuation plan (`memory/project_curator_operator_initiative_continuation.md`); Cedar bundle dual-anchor architecture (Phase O1 C1 commit `a02bcdb3`); FSCA drift rule extension to Curator (Phase O1-CURATOR-C6 commit `4d0f5519`).

### Document metadata

**Document version:** 2.0 FINAL (Volume 2)
**Generated:** 2026-05-10
**Supersedes:** none — extends v1.0 FINAL; both volumes canonical in tandem
**Bootstrap window:** Phase O1-VSD-BOOTSTRAP, executable as one Claude Code session for setup + one for first synthesis cycle, ideally during shadow_age accumulation between Phase O1-FRR-PARALLEL ship (2026-05-10) and Phase O3_ACT promotion (~late May 2026)
**Author authority:** VAPI Architect, sole deployer (`0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692`)
**Tags:** `#vsd #methodology #vapi #frozen-v1-candidate #notebook-llm-corpus #verification-first #honesty-first #mcp-absorption #vrr-primitive #cdrr-primitive #synthesis-operator-fleet #volume-2-final`

---

## Appendix A — Programmatic Reference

### A.1 New Python module skeleton (`bridge/vapi_bridge/vsd_advancement.py`)

```python
"""Phase O1-VSD-BOOTSTRAP — Synthesis Operator Fleet advancement primitive.

Sibling of operator_initiative_advancement.py (Phase O1 D).  Evaluates
SOF agents (Synthesizer, HarnessSentinel, EigenspaceWarden) against the
same Phase O2 SUGGEST + O3 ACT readiness criteria.  Produces VRR
commitment per cycle.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from .operator_initiative_advancement import (
    AgentAdvancementReadiness,
    FleetAdvancementSummary,
    PHASE_CODE_O1_SHADOW,
    PHASE_CODE_O2_SUGGEST,
    PHASE_CODE_O3_ACT,
    PHASE_CODE_UNKNOWN,
    _resolve_agent_id_for_store,
)

if TYPE_CHECKING:
    from .config import Config
    from .store import Store

log = logging.getLogger(__name__)

# Phase O1-VSD-BOOTSTRAP — VRR + CDRR domain tags (FROZEN-v1)
VRR_DOMAIN_TAG = b"VAPI-VSD-VRR-v1"  # 15 bytes
CDRR_DOMAIN_TAG = b"VAPI-CDRR-v1"     # 13 bytes

# Synthesis Operator Fleet — sibling of INITIATIVE_AGENTS
SOF_AGENTS = ("synthesizer", "harness_sentinel", "eigenspace_warden")

_SOF_AGENT_NAME_TO_ID_ATTR = {
    "synthesizer": "operator_agent_synthesizer_id",
    "harness_sentinel": "operator_agent_harness_sentinel_id",
    "eigenspace_warden": "operator_agent_eigenspace_warden_id",
}


@dataclass(frozen=True, slots=True)
class VaultReadinessRootResult:
    """Phase O1-VSD-BOOTSTRAP VRR commitment result."""
    vrr_hex: str
    harness_freeze_hash: str
    corpus_manifest_hash: str
    latest_pbsa_uuid_hash: str
    ts_ns: int
    error: Optional[str] = None


@dataclass(frozen=True, slots=True)
class CrossDomainReadinessRootResult:
    """Phase O1-VSD-BOOTSTRAP CDRR commitment result composing FRR + VRR."""
    cdrr_hex: str
    frr_hex: str
    vrr_hex: str
    ts_ns: int
    error: Optional[str] = None


def compute_vault_readiness_root(
    *,
    harness_freeze_hash: str,
    corpus_manifest_hash: str,
    latest_pbsa_uuid_hash: str,
    ts_ns: Optional[int] = None,
) -> VaultReadinessRootResult:
    """Compute VRR over current vault state.

    Pre-image:
      VRR_DOMAIN_TAG (15B)
      || harness_freeze_hash (32B)
      || corpus_manifest_hash (32B)
      || latest_pbsa_uuid_hash (32B)
      || ts_ns_be (8B)
    Digest: SHA-256 -> 32B
    """
    if ts_ns is None:
        ts_ns = time.time_ns()
    try:
        pre = bytearray(VRR_DOMAIN_TAG)
        for h_hex in (harness_freeze_hash, corpus_manifest_hash, latest_pbsa_uuid_hash):
            h = h_hex[2:] if h_hex.startswith("0x") else h_hex
            b = bytes.fromhex(h)
            if len(b) != 32:
                raise ValueError(f"hash must be 32B, got {len(b)}")
            pre.extend(b)
        pre.extend(int(ts_ns).to_bytes(8, "big"))
        digest = hashlib.sha256(bytes(pre)).hexdigest()
        return VaultReadinessRootResult(
            vrr_hex=digest,
            harness_freeze_hash=harness_freeze_hash,
            corpus_manifest_hash=corpus_manifest_hash,
            latest_pbsa_uuid_hash=latest_pbsa_uuid_hash,
            ts_ns=ts_ns,
        )
    except Exception as exc:
        log.warning("VRR compute failed: %s", exc, exc_info=True)
        return VaultReadinessRootResult(
            vrr_hex="", harness_freeze_hash="", corpus_manifest_hash="",
            latest_pbsa_uuid_hash="", ts_ns=ts_ns,
            error=f"{type(exc).__name__}: {exc}",
        )


def compute_cross_domain_readiness_root(
    *,
    frr_hex: str,
    vrr_hex: str,
    ts_ns: Optional[int] = None,
) -> CrossDomainReadinessRootResult:
    """Compute CDRR composing FRR + VRR.

    Pre-image:
      CDRR_DOMAIN_TAG (13B)
      || frr_hex (32B)
      || vrr_hex (32B)
      || ts_ns_be (8B)
    Digest: SHA-256 -> 32B
    """
    if ts_ns is None:
        ts_ns = time.time_ns()
    try:
        f = frr_hex[2:] if frr_hex.startswith("0x") else frr_hex
        v = vrr_hex[2:] if vrr_hex.startswith("0x") else vrr_hex
        f_b = bytes.fromhex(f)
        v_b = bytes.fromhex(v)
        if len(f_b) != 32 or len(v_b) != 32:
            raise ValueError(f"FRR/VRR must be 32B; got {len(f_b)}/{len(v_b)}")
        pre = bytearray(CDRR_DOMAIN_TAG)
        pre.extend(f_b)
        pre.extend(v_b)
        pre.extend(int(ts_ns).to_bytes(8, "big"))
        digest = hashlib.sha256(bytes(pre)).hexdigest()
        return CrossDomainReadinessRootResult(
            cdrr_hex=digest, frr_hex=frr_hex, vrr_hex=vrr_hex, ts_ns=ts_ns,
        )
    except Exception as exc:
        log.warning("CDRR compute failed: %s", exc, exc_info=True)
        return CrossDomainReadinessRootResult(
            cdrr_hex="", frr_hex="", vrr_hex="", ts_ns=ts_ns,
            error=f"{type(exc).__name__}: {exc}",
        )


# Additional functions:
#   evaluate_sof_advancement_sync() — mirrors evaluate_fleet_advancement_sync
#   evaluate_cross_domain_sync() — composes FRR + VRR per cycle
#   _read_harness_freeze_hash() — reads vsd-vault/eval/FROZEN.md
#   _read_corpus_manifest_hash() — reads vsd-vault/corpus/current/MANIFEST.txt
#   _read_latest_pbsa_uuid_hash() — reads vsd-vault/notes/pbsa/ DESC by created
```

### A.2 Stream A canonical structure

```
vsd-vault/
├── README.md
├── MEMORY.md
├── architect_key.pem               # Ed25519 architect signing key
├── eval/                           # IMMUTABLE
│   ├── INVARIANTS.md               # 23 invariants (16 v1.0 + 7 v2.0)
│   ├── NOTE_SCHEMAS.md             # 12 note types (9 v1.0 + 3 v2.0)
│   ├── HARNESS_RATIONALE.md
│   ├── FROZEN.md                   # version, hash, signature
│   └── architect_key_attestation.json  # bridge-wallet sig over Ed25519 pubkey
├── orchestrator/                   # EDITABLE
│   ├── SKILL.md
│   ├── SYNTHESIS_LOOP.md
│   ├── PRIORS.md
│   └── BOUNDARIES.md
├── notes/
│   ├── claim/         (v1.0)
│   ├── ingredient/    (v1.0)
│   ├── synthesis/     (v1.0)
│   ├── pbsa/          (v1.0)
│   ├── decision/      (v1.0)
│   ├── adversarial/   (v1.0)
│   ├── eigenspace/    (v1.0)
│   ├── study/         (v1.0)
│   ├── industry/      (v1.0)
│   ├── verification/  (v2.0 NEW)
│   ├── mcp/           (v2.0 NEW)
│   └── cdrr/          (v2.0 NEW)
├── manifests/<note-uuid>/
│   ├── 001.manifest.json
│   ├── 001.sig
│   └── ...
├── proposals/
│   ├── VSDIP-0001-initial-methodology.md   # = v1.0 FINAL
│   ├── VSDIP-0002-volume-2-final.md        # = this document
│   └── ...
├── corpus/
│   ├── snapshot-<ts>/
│   │   ├── MANIFEST.txt
│   │   └── *.md
│   └── current -> snapshot-<latest>/
└── archive/
```

### A.3 Cedar bundle skeleton for SOF agents

```json
{
  "$schema": "vapi-cedar-bundle-v1",
  "agent_id": "0x<32B-Q9-frozen-at-mint>",
  "phase": "O1_SHADOW",
  "version": 1,
  "issued_at_iso": "2026-05-10T...",
  "lane_prefixes": ["vsd-vault/", "notes/", "corpus/", "eval/", "manifests/"],
  "policies": [
    {
      "id": "P-001",
      "effect": "permit",
      "principal": "agent",
      "action": "vsd-draft-synthesis",
      "resource": "draft://notes/synthesis/**",
      "constraint": {"shadow_mode": true}
    },
    {
      "id": "P-002",
      "effect": "permit",
      "principal": "agent",
      "action": "read",
      "resource": "vsd-vault/notes/**",
      "constraint": null
    },
    {
      "id": "P-FORBID-CFSS-1",
      "effect": "forbid",
      "principal": "agent",
      "action": "kms-sign",
      "resource": "*",
      "constraint": null
    },
    {
      "id": "P-FORBID-CFSS-2",
      "effect": "forbid",
      "principal": "agent",
      "action": "audit-drafting",
      "resource": "*",
      "constraint": null
    },
    {
      "id": "P-FORBID-CFSS-3",
      "effect": "forbid",
      "principal": "agent",
      "action": "marketplace-curator-review",
      "resource": "*",
      "constraint": null
    },
    {
      "id": "P-FORBID-CFSS-4",
      "effect": "forbid",
      "principal": "agent",
      "action": "git-push",
      "resource": "*",
      "constraint": null
    }
  ]
}
```

The four `P-FORBID-CFSS-*` policies enforce cross-fleet skill separation: SOF agents can never sign protocol commits, draft audits, review marketplace listings, or push to git. These forbids are FROZEN at v2.0 freeze; lifting any of them requires a numbered VSDIP + governance event + re-anchor with new bundle Merkle.

---

## Appendix B — Bootstrap Quick Reference

```bash
# Stream A: vault skeleton (manual + scripted)
mkdir -p vsd-vault/{eval,orchestrator,notes/{claim,ingredient,synthesis,pbsa,decision,adversarial,eigenspace,study,industry,verification,mcp,cdrr},manifests,proposals,corpus,archive,.vsd}
openssl genpkey -algorithm ed25519 -out vsd-vault/architect_key.pem

# Stream B: harness extension (encode 23 invariants + sign FROZEN.md)
# (edit scripts/vapi_invariant_gate.py to add VSD_INVARIANTS registry)
# (edit eval/INVARIANTS.md, NOTE_SCHEMAS.md, HARNESS_RATIONALE.md, FROZEN.md)
echo "I understand this changes a frozen protocol invariant" | \
  python scripts/vapi_invariant_gate.py \
    --generate \
    --reason "invariant_change: VSD v2.0 FINAL bootstrap — 23 VSD invariants encoded into unified harness" \
    --confirm-governance

# Stream C: SOF activation (operator-gated, triple-gate)
# Mint 3 NFTs first via npx hardhat run scripts/mint-sof-agents.js --network iotex_testnet
$env:CHAIN_SUBMISSION_PAUSED="false"
$env:VSD_BOOTSTRAP_AUTHORIZED="true"
python scripts/parallel_vsd_anchor.py --confirm   # 6 dual-anchor txs

# Stream D: VRR + CDRR primitives + advancement_log extension
# (edit bridge/vapi_bridge/vsd_advancement.py; new file)
# (edit bridge/vapi_bridge/store.py; ALTER TABLE; phase 1005)
python -m pytest bridge/tests/test_phase_o1_vsd_vrr.py -v   # T-O1-VSD-VRR-1..6 all PASS

# Stream E: 10 new MCP tools across 3 servers
# (edit vapi-mcp/{server,knowledge_server,unified_server}.py)
# Restart MCP servers
python -m pytest bridge/tests/test_phase_o1_vsd_mcp.py -v   # 10 tool tests all PASS

# Stream F: 12 canonical seed notes
python .vsd/vsd_seed_notes.py --bootstrap --architect-key vsd-vault/architect_key.pem

# Stream G: corpus regen + NotebookLM upload
python .vsd/vsd_notebooklm_export.py
# (manual upload to NotebookLM "VAPI/VSD master corpus")
python .vsd/vsd_cross_tier_consistency.py --samples 5   # PASS

# Stream H: PV-CI + atomic commit + push
python scripts/vapi_invariant_gate.py --proposal-type=both --report   # 78/78 PASS
git add <all 8 streams>
git commit -m "$(cat <<'EOF'
phase O1-VSD-BOOTSTRAP: VSD Volume 2 FINAL — MCP-absorbed methodology + VRR + SOF fleet
...
EOF
)"
git push
```

---

**End of Volume 2 FINAL.**

Volume 2 closes the five gaps surfaced in v1.0 FINAL author review while preserving v1.0's structural commitments byte-for-byte. The methodology evolves through numbered VSDIPs only. The next major evolution candidate (Volume 3) is the **on-chain VRR view** in Phase O1-VSD-ONCHAIN — making synthesis state cryptographically queryable from foreign contracts, completing the composition surface that VRR establishes at v2.0 as a bridge-side commitment.

The methodology continues to bootstrap by itself. This document is, by VSD's own rules, a synthesis note `s-vsd-methodology-spec-v2` with ingredients (VSD v1.0 FINAL; the VAPI Phase O1-FRR-PARALLEL ship documentation; commit `4ddeb43c` source code; commit `79dacc88` Stream J empirical findings; the canonical→Q9 bug surfaced post-anchor; the unified watcher architectural decisions in `operator_initiative_advancement.py`). Bootstrapping the vault is the act of moving v1.0 + v2.0 into `notes/synthesis/` and signing both manifests as the seed entries of `notes/proposals/VSDIP-0001-initial-methodology.md` and `notes/proposals/VSDIP-0002-volume-2-final.md`.

When the operator authorizes Phase O1-VSD-BOOTSTRAP, this document becomes executable.
