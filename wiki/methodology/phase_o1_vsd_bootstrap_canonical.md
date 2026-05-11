# Phase O1-VSD-BOOTSTRAP — Canonical Execution Prompt

**Status:** v1.0 CANONICAL (sole in-tree execution target)
**Authored:** 2026-05-10
**Author authority:** VAPI Architect, sole deployer (`0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692`)
**Methodology source pair:** `C:\Users\Contr\Downloads\vsd_methodology_v1_FINAL.md` (v1.0 FINAL) + `wiki/methodology/vsd_volume_2_final.md` (v2.0 FINAL)
**Supersedes:** none in-tree. Any out-of-tree bootstrap prompt drafts (browser-session artifacts at `/mnt/user-data/outputs/` or similar) are reference-only; this document is the sole execution target.
**Execution mode:** `/vapi` skill, technical operator-collaboration register
**Bootstrap structure:** v2.0 FINAL eight streams with **Stream C (irreversible) staged behind explicit operator gate as Atomic Commit 2** after Atomic Commit 1 validates empirically

---

## 1. Authorization context

This prompt is the canonical execution target for Phase O1-VSD-BOOTSTRAP. Future-Claude reading this document executes the bootstrap as specified. State references are authoritative-as-of 2026-05-10 and ground-truth from `CLAUDE.md` + on-chain reads, not from any earlier prompt's stale snapshot.

**Current protocol state (verify via `mcp__vapi__vapi_protocol_state` at execution time):**

- Phase O1-FRR-PARALLEL ship complete; commits `4ddeb43c`, `79dacc88`, `2cde36a3` on `origin/main`
- All three Operator Initiative agents (Sentry + Guardian + Curator) at `O2_SUGGEST` on chain (verified via `chain.get_agent_scope_root()` direct reads 2026-05-10)
- Phase O0 ON-CHAIN REGISTRATION COMPLETE 2026-05-03 (commit `44c26ce0`); pause-point `f8c577ab` is historical, not active
- 49 contracts LIVE on IoTeX testnet
- 55 PV-CI invariants (will become 78 if v2.0 SOF fleet ships at Stream H)
- Bridge tests 2836 passing
- Wallet `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692` balance ~15.262626 IOTX (38× margin against 0.39 IOTX bootstrap impact)
- Nine FROZEN-v1 cryptographic primitives in PATTERN-017 family; v2.0 ships VRR + CDRR as #10 + #11
- Three live MCP servers (`vapi`, `vapi-knowledge`, `vapi-unified`); v2.0 §21 adds 10 new VSD tools

**Authorization commit boundary:** Phase O1-VSD-BOOTSTRAP is a parallel architectural workstream. It does not modify any FROZEN-v1 primitive (v2.0's VRR + CDRR are NEW primitives, not modifications of existing). It does not modify the existing 55 PV-CI invariants (v2.0 ADDS 23 VSD invariants). It does not redeploy any of the 49 LIVE contracts. It mints THREE new operator agent NFTs on existing `VAPIOperatorAgentNFT` (no new contract deploy required). It extends `bridge/vapi_bridge/operator_initiative_advancement.py`, `bridge/vapi_bridge/store.py`, `bridge/vapi_bridge/chain.py` (already extended Phase O1-FRR Stream J), `scripts/vapi_invariant_gate.py`, and the three MCP server files.

The bootstrap proceeds in parallel to protocol-fleet shadow_age accumulation: Sentry/Guardian shadow_age 152.13h of 504h (~14.6 days remaining); Curator shadow_age 6.79h of 504h (~21 days remaining). SOF fleet shadow_age accumulates from Stream C completion forward.

---

## 2. Decisions resolved (V1 through V6)

These decisions were surfaced and resolved in the session that produced this prompt. Future-Claude does NOT re-litigate; executes against the resolved choices.

| ID | Decision | Resolution | Rationale |
|----|----------|------------|-----------|
| V1 | Vault location | `vsd-vault/` at repo root (NOT `wiki/vsd-vault/`) | VSD-INV-23 unified harness requires co-location with `scripts/vapi_invariant_gate.py`; wiki path conflates governance surfaces with SOF Cedar bundle lane prefixes (Volume 2 §20.4) |
| V2 | Bridge-wallet attestation of architect Ed25519 key | YES, off-chain message signature only | Bridge wallet signs a JSON envelope `{"architect_pubkey_ed25519": "<32B>", "attested_at": "<ISO>", "purpose": "vsd-architect-key-anchor-v1"}` via `web3.py sign_message`. ZERO gas. Stored at `vsd-vault/eval/architect_key_attestation.json`. The peer's earlier "consumes gas" framing was incorrect; corrected. On-chain anchoring of the attestation digest is a Phase O1-VSD-ONCHAIN candidate, NOT required at bootstrap. |
| V3 | F1–F5 enhancements | MOOT under v2.0 | v1.0 FINAL absorbed F1/F2/F4/F5; F3 promoted to §12. v2.0 adds three more note types (verification, mcp, cdrr). |
| V4 | `eval/` storage | git-tracked + freeze-signature | Matches existing PV-CI pattern (`.github/INVARIANTS_ALLOWLIST.json`). Single audit trail. v2.0 §22 unified harness assumes git-tracked allowlist. IPFS would require unified-harness redesign for no cryptographic gain. |
| V5 | Methodology version | **v2.0 FINAL with staged Stream C** | v2.0 in single session is cleaner architecturally. Staging Stream C (irreversible NFT mints) behind explicit gate after Atomic Commit 1 validates honors Stream J's lesson: bugs invisible to specification-level verification need live empirical conditions to surface. Ships as Atomic Commit 1 (Streams A, A.5, B, D, E, F, G, partial H — filesystem-only + DB migration only) THEN Atomic Commit 2 (Stream C — SOF NFT mint + dual-anchor + parallel_vsd_anchor.py). Total session: ~3 hours. |
| V6 | Stale-state references | Proceed against current authoritative state from CLAUDE.md | PBSA seed from `wiki/assessments/vapi_state_assessment_2026_05_10.md`, NOT from `f8c577ab` pause snapshot. Treat any prior stale references as historical context only. |

---

## 3. The 11 V-checks (pre-execution discipline, run silently before each stream)

V1 through V7 are inherited from Volume 2 §27. V8 through V11 surfaced from this conversation's drift-finding work.

**V1.** Does `cedar_bundle_anchor.anchor_bundle()` accept arbitrary agent NFTs? Verify by inspection of `_load_and_parse` + `set_agent_scope_root` — confirm no agent-id-set whitelist. Required outcome: YES.

**V2.** Does `_AGENT_NAME_TO_ID_ATTR` extension affect existing FRR computation? Verify by reading `compute_fleet_readiness_root` sort key — confirm sort by `agent_id` bytes; new entries only emit into FRR when cfg fields populated. Required outcome: NO.

**V3.** Does `--proposal-type` flag preserve existing `vapi_invariant_gate.py --report` shape? Verify `protocol` is the default; existing CI workflows byte-identical at v2.0 freeze. Required outcome: YES.

**V4.** Does the unified allowlist file v2 break existing PV-CI gate? Verify v2 file format is backward-compat-readable by v1 gate (gate ignores unknown top-level keys). Required outcome: NO.

**V5.** Does the `domain` column ALTER TABLE break existing advancement_log queries? Verify default `'protocol'` for legacy rows; existing queries unaffected. Required outcome: NO.

**V6.** Does the SOF Cedar bundle's lane prefix conflict with protocol-fleet lane prefixes? Verify SOF lanes (`vsd-vault/`, `notes/`, `corpus/`, `eval/`, `manifests/`) disjoint from protocol lanes (`events/`, `provenance/`, `wiki/`, `audits/`, `invariants/`, `ops/`, `sweeps/`, `marketplace/`). Required outcome: DISJOINT.

**V7.** Does `parallel_vsd_anchor.py` triple-gate pattern conflict with `parallel_o2_anchor.py`? Verify env var name (`VSD_BOOTSTRAP_AUTHORIZED` vs `OPERATOR_INITIATIVE_O2_AUTHORIZED`) ensures process-scoped isolation. Required outcome: ISOLATED.

**V8 (drift-surfaced).** Bridge-wallet attestation of architect Ed25519 key is OFF-CHAIN (web3.py `sign_message`) NOT ON-CHAIN. Verify Stream A executes attestation as off-chain signature only; zero gas consumed. Required outcome: ZERO GAS.

**V9 (drift-surfaced).** This canonical prompt is the SOLE in-tree execution target. Verify no other `phase_o1_vsd_bootstrap*.md` exists at `wiki/methodology/` or repo root. If found, archive with `[SUPERSEDED by phase_o1_vsd_bootstrap_canonical.md, 2026-05-10]` header. Required outcome: SOLE TARGET.

**V10 (drift-surfaced).** Vault location is `vsd-vault/` at repo root, NOT under `wiki/`. Verify `vsd-vault/` does not pre-exist; verify `wiki/vsd-vault/` is NOT created. Required outcome: REPO ROOT.

**V11 (drift-surfaced).** PBSA seed sources current authoritative state. Verify Stream F PBSA seed reads `wiki/assessments/vapi_state_assessment_2026_05_10.md`, NOT any pre-Phase-O1-FRR snapshot. Verify PBSA `phase_from` and `phase_to` fields reference current phase boundaries (`O1-FRR-PARALLEL-SHIPPED` → `O1-VSD-BOOTSTRAP-IN-FLIGHT`), NOT historical Phase O0 boundaries. Required outcome: CURRENT STATE.

---

## 4. The 9 P-checks (post-execution discipline, run between streams)

P1 through P8 are inherited from Volume 2 §27. P9 is the gating P-check between Atomic Commit 1 and Atomic Commit 2.

**P1.** Stream A — `ls vsd-vault/` shows expected directory tree; architect Ed25519 key in `vsd-vault/architect_key.pem`; bridge-wallet attestation signature in `vsd-vault/eval/architect_key_attestation.json`.

**P2.** Stream A.5 — VSDIP-0003 strengthenings encoded into `vsd-vault/eval/INVARIANTS.md` v2.1 + `vsd-vault/eval/PROCEDURES.md` v1.0 + `vsd-vault/proposals/VSDIP-0003-pre-bootstrap-strengthening.md`. Verify all 7 candidate strengthenings landed (see §6 below).

**P3.** Stream B — `python scripts/vapi_invariant_gate.py --proposal-type=synthesis --report` exits 0; harness reports 23 VSD invariants pass against the seeded vault (after Stream F seeds notes); `python scripts/vapi_invariant_gate.py --proposal-type=both --report` exits 0 reporting "78 invariants total (55 protocol + 23 synthesis)".

**P4.** Stream D — `evaluate_vsd_advancement_sync()` returns sane summary against an empty SOF fleet (all phases `O0`, all blockers fired); `compute_vault_readiness_root()` produces a deterministic 64-char hex digest; `compute_cross_domain_readiness_root()` composes correctly against current FRR (`0x3aee5a26...`); idempotent ALTER TABLE ran cleanly (schema phase 1005 logged).

**P5.** Stream E — all 10 new MCP tools register at server startup; spot-check 3 via direct invocation: `mcp__vapi__vapi_vsd_state` returns vault metadata; `mcp__vapi-unified__vsd_validate_note` validates a seed note; `mcp__vapi-knowledge__vsd_query_corpus` returns provenance-aware results.

**P6.** Stream F — 12 canonical seed notes exist at `vsd-vault/notes/{claim,ingredient,synthesis,pbsa,decision,adversarial,eigenspace,study,industry,verification,mcp,cdrr}/<seed-id>.md`; manifests + Ed25519 signatures verify; `s-purpose-of-vapi.md` and `pbsa-O1-FRR-to-VSD-bootstrap.md` (NOT `pbsa-O0-to-O1.md` — that boundary closed weeks ago) ship as required seeds.

**P7.** Stream G — corpus regenerates clean; `vsd-vault/corpus/current → snapshot-<ts>/` symlink resolved; `MANIFEST.txt` lists 12 note IDs + SHA-256 + active manifest hash; cross-tier consistency check passes for 3 sample queries (one each from claim, synthesis, pbsa categories) across MCP / NotebookLM-staged-corpus / filesystem.

**P8.** Stream H Atomic Commit 1 — `git status` shows ALL of Streams A/A.5/B/D/E/F/G present; `pytest bridge/tests/ -k "phase_o1 or vsd" -q` 60+ tests pass; PV-CI gate `--proposal-type=both` reports 78/78; commit body documents resolved Decisions V1–V6 + V/P-check execution log + drift findings.

**P9 (gating P-check between Atomic Commit 1 and Atomic Commit 2).** Before Stream C fires:
- Atomic Commit 1 lands successfully on `origin/main`
- First synthesis cycle produces both required seed notes (`s-purpose-of-vapi.md` + `pbsa-O1-FRR-to-VSD-bootstrap.md`) AND both pass all 23 VSD invariants
- Cross-tier consistency check (VSD-INV-22) passes for 5 random claim notes
- Wallet balance verified ≥ 0.50 IOTX (safety floor for 6 dual-anchor txs at 1.25 buffer + ~0.21 IOTX NFT mints = ~0.39 IOTX expected, 0.50 is 28% margin)
- VRR baseline computed and matches expected pre-image (deterministic given vault state)

If P9 fails on any sub-check, Stream C does NOT fire. Vault remains operational at v2.0-minus-SOF scope. Operator decides whether to re-attempt P9 or defer Stream C indefinitely.

---

## 5. The 5 stop conditions (during execution)

**S1.** Any operational tx reverts in Stream C → STOP, do NOT proceed to next agent. FSCA `BUNDLE_HASH_DRIFT_DETECTED` will detect partial state on next 15-min poll. Operator inspects `operator_agent_activation_log` for partial state; recovery path documented in v2.0 §27.

**S2.** Any governance tx reverts after operational tx succeeds in Stream C → STOP, do NOT proceed to next agent. FSCA `SCOPE_HASH_GOVERNANCE_DRIFT_DETECTED` will fire as expected. Re-fire just the governance leg via dedicated repair endpoint (v2.0 deferred to follow-up phase).

**S3.** VRR mismatch (pre vs post) in Stream C → STOP, refuse to write CDRR row to advancement_log. Raise governance event for investigation. Vault state diverges from expected; do NOT compose into CDRR.

**S4.** Cross-tier consistency failure for 2+ samples (VSD-INV-22) in Stream G → STOP, file Decision note `d-cross-tier-divergence-<date>` documenting which tier diverged + harness output. Atomic Commit 1 does NOT ship until divergence resolved.

**S5 (drift-surfaced).** Any seed note in Stream F fails any of the 23 VSD invariants → STOP, do NOT proceed to Stream G corpus regeneration. Fix the seed note; re-run `--proposal-type=synthesis` until all 23 pass; re-attempt Stream G.

---

## 6. Stream A.5 — Seven VSDIP-0003 strengthenings (pre-harness-freeze)

Inserted between Stream A (vault skeleton) and Stream B (harness encoding). These strengthenings land in `vsd-vault/eval/INVARIANTS.md` v2.1 + `vsd-vault/eval/PROCEDURES.md` v1.0 + `vsd-vault/proposals/VSDIP-0003-pre-bootstrap-strengthening.md` BEFORE the harness freezes, so v2.0 ships with the strengthened forms rather than requiring a v2.1 release immediately after bootstrap.

**A.5.1.** Stream C ordering — chicken-and-egg between NFT mint and bundle Merkle. Bundle's `agent_id` field is Q9 hex derived from device pubkey at NFT mint time (Phase O0 Pass 2C Q9 formula). Bundle Merkle root includes `agent_id` in leaves. Therefore bundle CANNOT be authored with concrete `agent_id` until after mint. Strengthening: split Stream C into C.0 (mint 3 NFTs + capture Q9 IDs + populate cfg fields), C.1 (author 6 bundles with concrete agentIds), C.2 (run `parallel_vsd_anchor.py`). Phase 238 Step I-FINAL placeholder pattern is the precedent.

**A.5.2.** VSD-INV-21 needs HEAD-time check, not just commit-time. Adversary closes attack at commit T (test exists), then in commit T+10 silently deletes the test. Defense's mechanical evidence verifies (test existed when adversarial note authored) but defense no longer in place at HEAD. Strengthening: harness must verify BOTH `git show <commit>:<path>` succeeds AND `git ls-files <path>` includes the path at HEAD. For legitimate test renames, allow `closure_test_path_history:` array; harness checks any one path exists at HEAD.

**A.5.3.** VSD-INV-22 sampling adversarial weakness at scale. 5 random claims/cycle on N=1000 corpus = ~0.5% per-cycle coverage; full sweep = 200 cycles = 8.3 days at 1h cadence. Strengthening: (a) weighted sampling — claims modified within last 7 days get 3× weight; (b) weekly exhaustive sweep — every 168h, harness checks ALL claims; (c) sampling seed unpredictability — derive selection from `latest_pbsa_uuid_hash + ts_ns` so adversary cannot pre-compute which claims will be sampled. Combined: adversarial window compresses from 8.3 days to <168 hours; selection unpredictable.

**A.5.4.** CFSS forbid coverage exhaustive against protocol-fleet skill registry. Volume 2 Appendix A.3 names 4 CFSS forbids (`kms-sign`, `audit-drafting`, `marketplace-curator-review`, `git-push`) but protocol fleet has more skills: `provenance-recording`, `event-correlation`, `operational-diagnostic`, `pda-attestation-anchor`, `ipfs-pin`, `git-commit`, `git-pr`. Strengthening: Stream C bundle authoring enumerates against live protocol-fleet skill registry at bootstrap time, generating CFSS forbids exhaustively rather than from hand-coded list. Add INV-CFSS-002: harness periodically re-enumerates and flags drift.

**A.5.5.** Architect Ed25519 key rotation procedure — formalize as Procedure-VSD-K1 in `vsd-vault/eval/PROCEDURES.md`: (a) generate new Ed25519 key; (b) sign new pubkey with bridge wallet `0x0Cf36...` producing `architect_key_rotation_attestation.json`; (c) re-sign every manifest under new key as `<rev+1>.manifest.json` (old retained for forensic); (d) bump `eval/FROZEN.md` rotation_version field; (e) trigger corpus regeneration; (f) file Decision note `d-key-rotation-<date>` + VSDIP documenting rotation.

**A.5.6.** Bootstrap idempotency on Stream C re-run. Stream C NFT mint is NOT idempotent — running twice mints duplicate NFTs producing ambiguous Q9 IDs. Strengthening: Stream C.0 pre-flight check — if `cfg.operator_agent_synthesizer_id` (and analogues) populated with non-empty 32-byte hex in `bridge/.env`, skip mint and use existing. The mint script refuses to mint when target cfg fields populated, raising explicit error rather than silently double-minting.

**A.5.7.** CDRR ts_ns semantics across three timestamps. CDRR pre-image includes (CDRR_DOMAIN_TAG, frr_hex, vrr_hex, ts_ns); FRR has its own ts_ns embedded in `frr_hex` derivation; VRR has its own embedded in `vrr_hex` derivation. Strengthening: explicitly mirror FRR's pattern — CDRR's ts_ns is fresh-at-compute time; `frr_ts_ns_input` and `vrr_ts_ns_input` recoverable from input commitments but are NOT the CDRR's own ts_ns. Schema: CDRR commitment record stores `cdrr_ts_ns` + `frr_ts_ns_input` + `vrr_ts_ns_input` as three distinct fields; queryable via `mcp__vapi__vapi_vrr` extended for CDRR returns.

These seven strengthenings are non-blocking for Atomic Commit 1's filesystem streams BUT must land before Stream B harness freeze so the harness ships with strengthened forms. Two of seven (A.5.1 Stream C ordering + A.5.4 CFSS exhaustiveness) are protocol-correctness issues — bootstrap will fail or produce silently-wrong state without them.

---

## 7. The atomic commit structure

### Atomic Commit 1 (filesystem-only + DB migration only; reversible)

**Streams included:** A, A.5, B, D, E, F, G, partial H (excluding push)
**Wallet impact:** 0 IOTX
**Reversibility:** full — `rm -rf vsd-vault/` + `git revert <commit>` returns to pre-bootstrap state
**Test delta:** +25 (5 unified harness + 6 VRR/CDRR + 10 MCP + 3 new note type schemas + 1 cross-tier consistency)
**PV-CI delta:** 55 → 78 (+23 VSD invariants encoded into `vapi_invariant_gate.py` + new allowlist v2 split)

After Atomic Commit 1 lands on `origin/main`:
1. Run first synthesis cycle (executes from `orchestrator/SKILL.md`)
2. Produce `s-purpose-of-vapi.md` + `pbsa-O1-FRR-to-VSD-bootstrap.md` as required
3. Run P9 gating P-check (see §4)
4. Hold for explicit operator authorization to fire Stream C

### Atomic Commit 2 (Stream C — irreversible NFT mints + 6 dual-anchor txs)

**Streams included:** C.0 (NFT mint), C.1 (Cedar bundle authoring against live protocol-fleet skill registry), C.2 (`parallel_vsd_anchor.py --confirm`), final H (push of both commits)
**Wallet impact:** ~0.39 IOTX (3 NFT mints @ ~0.07 + 6 dual-anchor txs @ ~0.18 with 1.25 buffer)
**Reversibility:** PARTIAL — NFTs are soulbound; activation_log rows can be marked superseded but not deleted; on-chain scopeRoots persist
**Test delta:** +9 (6 SOF advancement + 3 anchor flow tests)
**PV-CI delta:** 78 → 79 (+INV-CFSS-001)

Stream C.2 fires `parallel_vsd_anchor.py --confirm` only after operator triple-gate (per v2.0 §27 stop conditions S1/S2/S3 enforced). Total session wall-clock: Atomic Commit 1 ~2 hours; gating window for first synthesis cycle + P9 ~30 min; Atomic Commit 2 ~30 min.

---

## 8. Execution sequence (operator-readable run order)

Future-Claude executes the following in order. Each stream is its own pre-implementation V-checks → hold → implementation → post-implementation P-check → hold → atomic-commit-eligible cycle.

### Stream A — Vault skeleton + Ed25519 architect key (filesystem only)

```bash
# Path: vsd-vault/ at repo root (V10 verified)
mkdir -p vsd-vault/{eval,orchestrator,manifests,proposals,corpus,archive,.vsd}
mkdir -p vsd-vault/notes/{claim,ingredient,synthesis,pbsa,decision,adversarial,eigenspace,study,industry,verification,mcp,cdrr}
echo "# VSD Vault" > vsd-vault/README.md
echo "# VSD Vault MEMORY (separate from protocol MEMORY.md)" > vsd-vault/MEMORY.md
openssl genpkey -algorithm ed25519 -out vsd-vault/architect_key.pem
# V8 verified: bridge-wallet attestation is OFF-CHAIN (web3.py sign_message), zero gas
python .vsd/vsd_attest_architect_key.py \
  --pubkey vsd-vault/architect_key.pem \
  --bridge-wallet 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692 \
  --output vsd-vault/eval/architect_key_attestation.json
```

P1 verifies; hold for review.

### Stream A.5 — VSDIP-0003 strengthenings (pre-harness-freeze)

Author `vsd-vault/eval/INVARIANTS.md` v2.1 (incorporates 7 strengthenings into VSD-INV-21 + VSD-INV-22 amendments + PROCEDURES.md cross-references). Author `vsd-vault/eval/PROCEDURES.md` v1.0 (Procedure-VSD-K1 key rotation + Stream C ordering procedure). Author `vsd-vault/proposals/VSDIP-0003-pre-bootstrap-strengthening.md` documenting the 7 candidates and their resolutions.

P2 verifies; hold for review.

### Stream B — Unified harness extension

```bash
# Edit scripts/vapi_invariant_gate.py: add VSD_INVARIANTS registry (23 entries) +
# --proposal-type flag dispatcher
# Edit vsd-vault/eval/NOTE_SCHEMAS.md: 12 note type schemas (9 v1.0 + 3 v2.0)
# Edit vsd-vault/eval/HARNESS_RATIONALE.md: paragraph per invariant
# Compute freeze hash + sign with architect Ed25519 key → vsd-vault/eval/FROZEN.md

echo "I understand this changes a frozen protocol invariant" | \
  python scripts/vapi_invariant_gate.py \
    --generate \
    --reason "invariant_change: VSD v2.0 FINAL bootstrap — 23 VSD invariants encoded into unified harness alongside 55 protocol invariants" \
    --confirm-governance
```

P3 verifies (78/78 pass); hold for review.

### Stream D — VRR + CDRR primitives + advancement_log extension

```bash
# Create bridge/vapi_bridge/vsd_advancement.py per Volume 2 Appendix A.1
# Edit bridge/vapi_bridge/store.py: idempotent ALTER TABLE for advancement_log
# (5 new columns: domain, vrr_hex, cdrr_hex, harness_freeze_hash, corpus_manifest_hash, latest_pbsa_uuid_hash)
# Schema phase 1005

python -m pytest bridge/tests/test_phase_o1_vsd_vrr.py -v   # T-O1-VSD-VRR-1..6 PASS
```

P4 verifies; hold for review.

### Stream E — Ten new MCP tools

Edit `vapi-mcp/server.py` (add `vapi_vsd_state`, `vapi_vrr`); `vapi-mcp/knowledge_server.py` (add `vsd_query_corpus`, `vsd_ingredient_provenance`, `vsd_adversarial_closure_chain`); `vapi-mcp/unified_server.py` (add `vsd_validate_note`, `vsd_pbsa_required`, `vsd_eigenspace_freshness`, `vsd_corpus_status`, `vsd_synthesis_priors`).

```bash
python -m pytest bridge/tests/test_phase_o1_vsd_mcp.py -v   # 10 MCP tool tests PASS
```

P5 verifies; hold for review.

### Stream F — 12 canonical seed notes

Author one seed per note type:
- `notes/decision/d-2026-05-10-bootstrap-authorization.md`
- `notes/ingredient/i-2026-05-10-c2pa-active-manifest.md` (verbatim quote from C2PA spec §2.3.7)
- `notes/claim/c-2026-05-10-battery-stratified-separation-ratio.md`
- `notes/synthesis/s-vsd-c2pa-active-manifest-port.md`
- `notes/synthesis/s-purpose-of-vapi.md` ← **REQUIRED canonical seed**
- `notes/pbsa/pbsa-O1-FRR-to-VSD-bootstrap.md` ← **REQUIRED canonical seed** (NOT `pbsa-O0-to-O1.md`; the O0→O1 boundary closed 2026-05-03; current boundary is O1-FRR-PARALLEL-shipped → O1-VSD-BOOTSTRAP-in-flight)
- `notes/adversarial/adv-2026-05-10-stream-j-canonical-q9-mismatch.md` (with `closure_test_commit: 79dacc88` + `closure_test_path: bridge/tests/test_phase_o1_frr.py::test_T_O1_FRR_7_canonical_to_q9_translation_and_o3_target` per VSD-INV-21 strengthened form)
- `notes/eigenspace/eig-2026-05-10-ait-n37.md` (with `probe_coverage: [active_isometric_trigger]` + `probe_coverage_blockers: [touchpad_corners, tremor_resting]` per VSD-INV-18)
- `notes/eigenspace/eig-2026-05-10-frr-structural.md` (Sentry/Guardian/Curator scopeRoots from Phase O1-FRR-PARALLEL anchor)
- `notes/study/study-2026-05-10-tremor-resting-fft-remeasure.md` (with `result_summary: null` + `preregistration_hash` locked)
- `notes/industry/ind-2026-05-10-remote-proctored-exams.md`
- `notes/verification/ver-2026-05-10-phase-o1-frr-parallel.md` (the V/P checks from today's Phase O1-FRR-PARALLEL ship)
- `notes/mcp/mcp-2026-05-10-vapi-protocol-state-snapshot.md` (canonicalized JSON of `vapi_protocol_state` at FRR ship)
- `notes/cdrr/cdrr-2026-05-10-bootstrap-cycle-1.md` (placeholder until VRR computed Stream G)

For each: generate manifest, sign with architect Ed25519 key, store signature.

P6 verifies; hold for review.

### Stream G — Corpus regeneration + first cross-tier consistency check

```bash
python .vsd/vsd_notebooklm_export.py
# walks notes/, runs unified harness, copies passing notes into vsd-vault/corpus/snapshot-<ts>/
# generates MANIFEST.txt
# symlinks vsd-vault/corpus/current → snapshot-<ts>

python .vsd/vsd_cross_tier_consistency.py --samples 5
# samples 5 random claim notes, queries MCP + corpus + filesystem, asserts identity
# VSD-INV-22 strengthened form per A.5.3 — weighted sampling + unpredictable seed
```

V11 verifies (PBSA seed sources current state per §3); P7 verifies (cross-tier 5/5 identical); hold for review.

### Stream H part 1 (Atomic Commit 1) — PV-CI gate + commit (no push)

```bash
python scripts/vapi_invariant_gate.py --proposal-type=both --report
# expects: 78/78 PASS

python -m pytest bridge/tests/ -k "phase_o1 or vsd" -q
# expects: 60+ PASS (FRR + VSD)

git add vsd-vault/ scripts/vapi_invariant_gate.py .github/INVARIANTS_ALLOWLIST.json \
  bridge/vapi_bridge/{vsd_advancement.py,store.py} \
  bridge/tests/test_phase_o1_vsd_*.py \
  vapi-mcp/{server,knowledge_server,unified_server}.py \
  CLAUDE.md MEMORY.md \
  .claude/projects/.../memory/project_phase_o1_vsd_bootstrap.md

git commit -m "phase O1-VSD-BOOTSTRAP atomic commit 1: filesystem + DB migration + harness extension"
# DO NOT push yet — push happens at end of Atomic Commit 2
```

P8 verifies; **hold for explicit operator authorization to fire Stream C**.

### Gating window: First synthesis cycle + P9 gate

After Atomic Commit 1 lands locally:
- Operator runs first synthesis cycle from `orchestrator/SKILL.md`
- Confirms `s-purpose-of-vapi.md` + `pbsa-O1-FRR-to-VSD-bootstrap.md` produced and harness-passing
- Runs P9 gating P-check (§4)
- If P9 PASS: explicit operator authorization to fire Stream C
- If P9 FAIL: vault remains at v2.0-minus-SOF scope; Stream C deferred indefinitely; Atomic Commit 1 ALONE pushes to origin/main

### Stream C (Atomic Commit 2 — only fires on P9 pass + explicit authorization)

```bash
# Stream C.0 — Mint 3 NFTs
cd contracts && npx hardhat run scripts/mint-sof-agents.js --network iotex_testnet
# Captures Q9 agentIds for synthesizer + harness_sentinel + eigenspace_warden
# Populates bridge/.env with operator_agent_*_id fields
# A.5.6 idempotency check: refuses if cfg fields already populated

# Stream C.1 — Author 6 Cedar bundles with concrete agentIds
# (3 agents × 2 phases each: O1_SHADOW + O2_SUGGEST)
# A.5.4 CFSS exhaustive forbids generated against live protocol-fleet skill registry

# Stream C.2 — Triple-gate live anchor
$env:CHAIN_SUBMISSION_PAUSED="false"
$env:VSD_BOOTSTRAP_AUTHORIZED="true"
python scripts/parallel_vsd_anchor.py --confirm
# 6 sequential dual-anchor txs in fixed order [Synthesizer, HarnessSentinel, EigenspaceWarden]
# Pre-anchor + post-anchor VRR verification (S3 stop condition active)
# Atomicity stop on partial failure (S1/S2 active)
```

### Stream H part 2 (final commit + push)

```bash
git add bridge/vapi_bridge/cedar_bundles/{synthesizer,harness_sentinel,eigenspace_warden}_*.json \
  scripts/parallel_vsd_anchor.py scripts/mint-sof-agents.js \
  bridge/.env.template  # NOT bridge/.env — that holds private state
git commit -m "phase O1-VSD-BOOTSTRAP atomic commit 2: SOF fleet activation + 6 dual-anchor live"
git push origin main
```

---

## 9. Required final report (operator-readable)

After Atomic Commit 1 ships (and Atomic Commit 2 if P9 passes), report:

| Field | Value |
|-------|-------|
| Decisions resolved | V1 (vsd-vault/ at root) / V2 (off-chain attestation, zero gas) / V3 (moot under v2.0) / V4 (git-tracked) / V5 (v2.0 staged) / V6 (current authoritative state) |
| Streams completed | A, A.5, B, D, E, F, G, H part 1 — Atomic Commit 1; C.0/C.1/C.2, H part 2 — Atomic Commit 2 (only if P9 passed) |
| Invariants pass | 78/78 (55 protocol + 23 VSD) on `--proposal-type=both` |
| corpus/current/ location | `vsd-vault/corpus/snapshot-<ts>/` symlinked from `vsd-vault/corpus/current/` |
| Notes by type | 12 seed notes (1 per note type at minimum); first-synthesis-cycle output if P9 ran |
| Wallet impact | 0 IOTX (Atomic Commit 1) or ~0.39 IOTX (both commits if P9 passed) |
| SOF fleet status | NOT YET ACTIVATED (Atomic Commit 1 only) or O1_SHADOW LIVE (Atomic Commit 2) |
| Cross-tier consistency | 5/5 samples PASS at last regen |
| Drift findings surfaced | enumerate any methodology-vs-implementation drift surfaced during execution |
| Recommended next synthesis cycle target | one open question — e.g., "Which industries beyond competitive gaming have strongest VAPI primitive applicability given current empirical anchors" or "How should the AccelTremorFFT P1vP3 bin aliasing residual interact with the BIOMETRIC-SNAPSHOT primitive's freshness window" |

Do NOT propose protocol-side work. The protocol is not paused (Phase O1-FRR-PARALLEL shipped today; agents at O2_SUGGEST on chain) but Phase O1-VSD-BOOTSTRAP is a separate ship. Future protocol-side phases (O3_ACT advancement, mainnet TGE preparation, BT calibration corpus) remain on their existing roadmap independent of VSD vault state.

---

## 10. Drift surfacing discipline

Surface as findings (not silent corrections) any drift between this canonical prompt and what becomes implementable in practice. Drift is information; the methodology evolves through the VSDIP process.

Specific drift classes to watch for:
- v2.0 §24 stream sequencing vs actual implementation order required
- VSDIP-0003 candidate strengthenings revealing additional weaknesses on second-pass review
- MCP tool registration friction (server restart timing, JSON-RPC handler boilerplate)
- Stream C dual-anchor gas estimates diverging from observed (current testnet ~1000 Gwei; 1.25 buffer should hold)
- Cross-tier consistency edge cases (e.g., NotebookLM caching vs fresh corpus regen)
- Ed25519 key rotation procedure execution (Procedure-VSD-K1 v1.0 should be tested at vault setup time)

Each drift finding lands as either a Decision note (if operator must resolve) or a verification note `notes/verification/ver-<date>-bootstrap-drift-<n>.md` (if architectural fact discovered during execution).

---

## 11. Rollback procedure

If Atomic Commit 1 fails any P-check or any V-check rejects a stream, rollback is:

```bash
git reset --hard HEAD~1   # undoes the local commit (only if not pushed)
rm -rf vsd-vault/         # removes the vault skeleton
# Optional: revert scripts/vapi_invariant_gate.py if it changed
git checkout HEAD -- scripts/vapi_invariant_gate.py .github/INVARIANTS_ALLOWLIST.json
# Optional: ALTER TABLE rollback if Stream D's schema phase 1005 ran:
#   sqlite3 bridge/vapi_store.db "ALTER TABLE operator_initiative_advancement_log DROP COLUMN domain"
#   (and similar for vrr_hex, cdrr_hex, harness_freeze_hash, corpus_manifest_hash, latest_pbsa_uuid_hash)
#   SQLite < 3.35 doesn't support DROP COLUMN; alternative is dump/recreate
```

After Atomic Commit 1 pushes to origin/main, rollback requires a `git revert` commit (preserves history). After Atomic Commit 2's NFT mints + dual-anchor txs land on chain, rollback is partial — NFTs are soulbound (cannot un-mint); on-chain scopeRoots persist; activation_log rows can be marked superseded but not deleted. The bridge wallet's IOTX spend is not recoverable.

The reversibility-by-stream property is the structural reason Stream C is staged: if P9 catches a structural defect, rollback is `rm -rf vsd-vault/` + `git revert <atomic commit 1>` and the wallet remains at 15.262626 IOTX.

---

## 12. Document metadata

**Document version:** 1.0 CANONICAL
**Generated:** 2026-05-10
**Methodology source pair:**
- v1.0 FINAL — `C:\Users\Contr\Downloads\vsd_methodology_v1_FINAL.md`
- v2.0 FINAL — `wiki/methodology/vsd_volume_2_final.md`
**Supersedes:** none in-tree. Out-of-tree drafts (browser-session sandboxes, peer-Claude artifacts) are reference-only.
**Authorization model:** single architect (`0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692`); single Ed25519 architect key generated at Stream A; bridge-wallet off-chain attestation establishes the deployer-anchored signing chain.
**Execution mode:** `/vapi` skill, technical operator-collaboration register, Verification-First Discipline throughout.
**Tags:** `#vsd #methodology #phase-o1-vsd-bootstrap #canonical-execution-prompt #v2-staged #verification-first #atomic-commits #stream-j-lessons-applied`

---

**End of canonical execution prompt.**

When operator authorizes Phase O1-VSD-BOOTSTRAP, future-Claude reads this document as the sole in-tree execution target, runs the 11 V-checks pre-execution, executes Atomic Commit 1 with hold-for-review at each stream boundary, fires the gating window for first synthesis cycle, and only fires Atomic Commit 2 (Stream C) on explicit operator authorization following P9 pass. Stream J's lesson — that bugs invisible to specification-level verification need live empirical conditions to surface — is applied prophylactically: the irreversible work is gated on the reversible work's empirical success.
