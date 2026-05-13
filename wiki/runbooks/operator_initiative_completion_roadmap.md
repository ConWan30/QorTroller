# Operator Initiative Completion Roadmap

**Authoring commit:** to-be-assigned at landing (this commit)
**State anchor:** HEAD `020644ba` (post-E.1 state-file-sync)
**Architecture anchor:** `e81e04aa` (Phase O4-VPM-INTEGRATION close)
**Author:** VAPI Principal Architect, 2026-05-13

This document inventories every operator-runtime step required to advance the Operator Initiative fleet (Sentry / Guardian / Curator) from current state to complete (all three agents at lifecycle `O3_ACT` with live write authority on chain).

**No mainnet deploys are authorized until this roadmap is complete per operator directive 2026-05-13.** This is the gating prerequisite for VAPI's Phase 99 TGE (Token Generation Event), LayerZero VHP cross-chain bridge mainnet activation, and any other mainnet operation.

---

## 1. Current state per HEAD `020644ba`

### Per-agent on-chain identity (FROZEN; INV-OPERATOR-AGENT-001..008 pinned)

| Agent | agentId (Q9 frozen) | ioID DID | tokenId | TBA | Status |
|---|---|---|---|---|---|
| **Sentry** (anchor_sentry) | `0xb21e1ec258d2d381c313f84944bd36fbc63badb2c9a24c2412212d3a27e3e42c` | `did:io:0xeaa6fd569a964c08d541f8e154ab3ac8cd4e2743` | 495 | `0xCc59C57bB7746791Be0945BfB96Be408a73944e4` | O2_SUGGEST since 2026-05-10 (parallel_o2_anchor.py LIVE) |
| **Guardian** | `0xbd8c7fba08815b7ed343973c9c7300c062303b1acd19e8d9847a953ce5fa38d1` | `did:io:0x9c577fb2162824565ef57edd1b55a8ec5f58c181` | 496 | `0xd7aDA37AdFC08Fed43c934aB3b9609697b739092` | O2_SUGGEST since 2026-05-10 |
| **Curator** | `0xed6a2df58e5ec50c1f88e127f6982a348f6855202b662b8ad73ffa1c1fda11a8` | `did:io:0x7BdB744c87c8f86e348246557BB58D60641312C2` | 497 | `0x6A385dF2501D42ef2Cf918eE1e3b6011903e418F` | O1_SHADOW since 2026-05-09 (Session 1 ON-CHAIN ACTIVATION) |

### Cedar bundle on-chain anchored state (Cedar v2; INV-CEDAR-001..003 pinned)

| Agent | Bundle Merkle (Cedar v2) | Anchored on AgentScope | Anchored on AgentRegistry |
|---|---|---|---|
| Sentry | `0x39e8b65f0a87671fc003c28c3f28a7afd7fae41b6c3505d1ddb3d05ff3db1f23` | 2026-05-12 (Track 2 C8 ceremony) | 2026-05-12 |
| Guardian | `0x6818a9ad49dab7898925e530526c50fcce515a889c3666f1434e6470c660a9a0` | 2026-05-12 | 2026-05-12 |
| Curator | `0x0ade0c92cf2aa0c5675701861ed535683f0dfd15873424a9838d402b60a80b3d` | 2026-05-12 | 2026-05-12 |

### Pre-authored O3_ACTING bundles (ready-to-fire)

| Agent | O3_ACTING Bundle Merkle | Location |
|---|---|---|
| Sentry | `0xc0bcdee8576e83f6b80e8c5ac89093cf08f153033037176cd03fc34fcedfd878` | `bridge/vapi_bridge/cedar_bundles/anchor_sentry_o3_acting_v1.json` |
| Guardian | `0x6f0fc77cc1dacaf3f79aeb0f27dd8c7b3d88e95b236f0806ad3588a06bb82225` | `bridge/vapi_bridge/cedar_bundles/guardian_o3_acting_v1.json` |
| Curator | `0xd9d760c8b7b1088f2edd165fbfa6441abcb3bc3f921e8ba75a3339c0825fec24` | `bridge/vapi_bridge/cedar_bundles/curator_o3_acting_v1.json` |

(Pre-authored 2026-05-10 in Phase O3-ACT-DRAFT commit `3cb59f46`. Validated CLEAN via Cedar V&V CLI; pinned by PV-CI INV-O3-WATCHER-003.)

---

## 2. Per-agent advancement requirements

### Sentry (currently at O2_SUGGEST)

To advance Sentry from `O2_SUGGEST` → `O3_ACT`:

| Gate | Requirement | Verification |
|---|---|---|
| 1 | `shadow_age_hours ≥ 504` (3 weeks since Cedar bundle anchor) | `GET /operator/operator-initiative-advancement` → `per_agent[anchor_sentry].shadow_age_hours` |
| 2 | `draft_payload_count ≥ 50` over 30-day window | `bridge/vapi_store.db` table `operator_agent_drafts` WHERE `agent_id=anchor_sentry_q9_hex` AND `created_at >= NOW - 30d` |
| 3 | `disagreement_rate < 0.05` over 30-day window | `compute_operator_agent_disagreement_rate(anchor_sentry, 30*86400)` |
| 4 | `cfg.operator_dual_key_present == True` | bridge/.env config |
| 5 | `cfg.kms_hsm_production_ready == True` | bridge/.env config (Sentry+Guardian only) |
| 6 | `cfg.github_app_oauth_tokens_valid == True` | bridge/.env config (Sentry+Guardian only) |

**Operator-runtime activation step (when all gates clear):**

```powershell
$env:CHAIN_SUBMISSION_PAUSED = "false"
$env:OPERATOR_INITIATIVE_O3_AUTHORIZED = "true"  # distinct from O2 to prevent residual carry-over
python scripts/parallel_o3_act_anchor.py --confirm
```

This advances ALL THREE agents in lockstep per the parallel-fleet invariant established by Phase O1 D. Sentry+Guardian+Curator advance together OR none advance — single-action triple dual-anchor on AgentScope (operational) + AgentRegistry (governance) per INV-OPERATOR-AGENT-001.

### Guardian (currently at O2_SUGGEST)

Mirror of Sentry's gate set. All 6 gates apply identically.

### Curator (currently at O1_SHADOW — requires TWO advancement ceremonies)

#### Phase 1: O1_SHADOW → O2_SUGGEST

Per CLAUDE.md state: Curator's parallel_o2_anchor.py advancement for the Curator-specific bundle was NOT fired alongside Sentry+Guardian on 2026-05-10. The Sessions 1+2+3 arc advanced Curator only to O1_SHADOW. Curator's O2_SUGGEST bundle exists (Merkle `0xeb400a5c9b410c6f3035a595e2c36dee915f6b2447f822c72c46b164ccd5daa9`); the Cedar v2 ceremony 2026-05-12 anchored the O2_SUGGEST bundle to AgentScope but Curator's lifecycle phase field on AgentRegistry may still report O1_SHADOW.

**Verification first:** before firing any Curator advancement, run the consolidated graduation readiness audit:

```bash
python scripts/curator_graduation_readiness_audit.py
```

The audit consolidates G7 acceptance gate + Operator Initiative watcher + CFSS lane authority + on-chain anchor state. If `final_verdict == "READY"`, Curator may advance.

**Curator advancement gates (Phase O1 D):**

| Gate | Requirement | Verification |
|---|---|---|
| O2 advancement | `shadow_age_hours ≥ 504` (3 weeks since 2026-05-09 Session 1 anchor) | `GET /operator/operator-initiative-advancement` |
| O2 advancement | `cedar_eval_count ≥ 100` | `bridge/vapi_store.db` table `cedar_shadow_log` |
| O2 advancement | `bundle_hash_drift + scope_hash_governance_drift = 0` over 30 days | `GET /operator/operator-agent-drift-log?since_minutes=43200` |

#### Phase 2: O2_SUGGEST → O3_ACT (Curator-specific gates)

Curator's O3 graduation has ADDITIONAL constraints beyond Sentry/Guardian's:

| Gate | Requirement | Verification |
|---|---|---|
| 1–4 | Same as Sentry (shadow_age + drafts + disagreement_rate + dual_key) | Same endpoints |
| 5 | `cfg.marketplace_curator_role_assigned == True` | `chain.eth_call(VAPIDataMarketplaceListings.curator()) == curator_tba_address` |
| 6 | `false_positive_rate_30d == 0.0` — **ZERO TOLERANCE** | `compute_operator_agent_false_positive_rate(curator, 30*86400) == 0.0` |
| 7 | **G7 acceptance gate** — `≥9 of last 10 reviewed Curator drafts == accept` over 7-day trailing window | `python scripts/g7_curator_review_readiness_audit.py` → verdict `PASS` |

**Curator does NOT require** `kms_hsm_production_ready` or `github_app_oauth_tokens_valid` (those are Sentry+Guardian only — Curator's testnet activation uses MockKMSClient per Session 1 precedent).

**Mainnet Curator activation** requires `cfg.kms_hsm_production_ready == True` after AWS KMS HSM provisioning per `wiki/runbooks/curator_mainnet_migration.md`. This is separate from testnet O3_ACT graduation and falls under the mainnet-blocked constraint.

---

## 3. Operator-runtime workflow to close the Initiative

### Step 1: Enable Curator polling loops

In `bridge/.env`:

```
OPERATOR_AGENT_CURATOR_MARKETPLACE_TRIGGER_ENABLED=true
OPERATOR_AGENT_CURATOR_ANCHOR_FRESHNESS_TRIGGER_ENABLED=true
OPERATOR_AGENT_CURATOR_PERIODIC_COMPLIANCE_TRIGGER_ENABLED=true
```

Restart bridge. Verify via `GET /operator/operator-agent-drafts?agent_id=curator` — drafts should begin appearing as triggers fire.

### Step 2: Review drafts via Operator Console

Use the DraftReviewDrawer (Phase O2-DRAFT-REVIEW-FRONTEND, commit `3d5923e7`) at `frontend/.../DraftReviewDrawer.jsx`. Each Curator draft displays:

- Action category (skill / tool)
- Action name (marketplace-listing-review / kms-sign-review / operator-notify)
- Draft URI
- Payload hash
- Operator decision buttons: ACCEPT / REJECT / OVERTURN_CURATOR (ZERO TOLERANCE)

**OVERTURN_CURATOR triggers ZERO TOLERANCE blocker** — any single `overturn_curator` decision in the trailing 30-day window blocks Curator O3 graduation per `PHASE_O3_FALSE_POSITIVE_RATE_MAX=0.0`. Use with extreme care; reserved for cases where Curator's verdict was clearly incorrect on review.

### Step 3: Monitor G7 progression

```bash
# At any time, check Curator's G7 state:
python scripts/g7_curator_review_readiness_audit.py

# OR via HTTP (read-key auth):
curl -H "x-api-key: $env:OPERATOR_API_KEY" \
  http://localhost:8081/operator/g7-curator-readiness
```

Expected progression:
- Initial: `NO_CURATOR_DRAFTS` (0 drafts ever; exit 3)
- After polling loops fire + drafts accumulate: `BLOCKED` (insufficient signal; n_reviewed < 10)
- After ≥10 operator reviews: `PASS` if ≥9 accepts in last 10; `FAIL` otherwise

### Step 4: Wait for shadow_age threshold

Curator's shadow_age clock started 2026-05-09 (Session 1 anchor). 504h = 21 days. Threshold cleared approximately 2026-05-30.

Sentry+Guardian's shadow_age clocks started 2026-05-10 (parallel_o2_anchor.py LIVE). 504h cleared approximately 2026-05-31.

### Step 5: Run consolidated readiness audit

```bash
python scripts/curator_graduation_readiness_audit.py
```

When all 5 sections report PASS (verdict=READY exit 0), proceed to Step 6.

### Step 6: Fire the O3 graduation ceremony

```powershell
# Pre-flight verification
python scripts/parallel_o3_act_anchor.py  # without --confirm; runs gates only, no tx

# If pre-flight CLEAN:
$env:CHAIN_SUBMISSION_PAUSED = "false"
$env:OPERATOR_INITIATIVE_O3_AUTHORIZED = "true"
python scripts/parallel_o3_act_anchor.py --confirm
```

Estimated cost: ~0.18–0.23 IOTX (6 dual-anchor txs at current testnet gas; wallet floor 0.5 IOTX provides ~2× margin).

### Step 7: Post-ceremony verification

```bash
python scripts/zkba_post_ceremony_audit.py --include-chain-reads
python scripts/cfss_lane_drift_sweep.py
python scripts/g7_curator_review_readiness_audit.py  # should remain PASS post-ceremony
```

All three audits should report PASS.

### Step 8: Re-engage kill-switch

```powershell
$env:CHAIN_SUBMISSION_PAUSED = "true"
Remove-Item Env:\OPERATOR_INITIATIVE_O3_AUTHORIZED
```

Re-engage process-scoped safety posture. bridge/.env remains pinned at `CHAIN_SUBMISSION_PAUSED=true` since the env var is process-scoped only.

---

## 4. Cost projection (testnet)

| Step | Cost (IOTX) | Notes |
|---|---|---|
| 1 — Enable polling loops | 0 | Configuration change only |
| 2 — Operator review activity | 0 | Off-chain via DraftReviewDrawer |
| 3 — G7 monitoring | 0 | Read-only audit |
| 4 — Shadow_age wait | 0 | Pure time |
| 5 — Readiness audit | 0 | Read-only |
| 6 — O3 graduation ceremony | ~0.18–0.23 | 6 dual-anchor txs at ~0.04 IOTX each + buffer |
| 7 — Post-ceremony verification | 0 | Read-only |
| 8 — Kill-switch re-engage | 0 | Configuration change only |
| **TOTAL** | **~0.18–0.23 IOTX** | 85× margin against current ~15.03 IOTX wallet |

VPMAnchorRegistry deploy (separate from Operator Initiative completion) adds ~0.1 IOTX. Per-VPM anchor adds ~0.05 IOTX.

---

## 5. Risk register

| Risk | Severity | Mitigation |
|---|---|---|
| G7 never reaches PASS due to genuine operator disagreement with Curator | HIGH | Review Curator's verdict logic; may indicate a curator_review.review_listing() bug or a Cedar policy that's too aggressive. Investigate before O3 ceremony. |
| Curator produces zero drafts even after polling loops enabled | HIGH | Verify trigger sources actively firing (commit / poac_chain_head / poad_hash for Sentry; sweep_completed / fsca_finding for Guardian; listing_event / anchor_freshness_alert / periodic_compliance for Curator). |
| Cedar bundle on-chain divergence from local file | CRITICAL | `cfss_lane_drift_sweep.py` should report CFSS_VIOLATION continuously. Investigate before any further ceremony. |
| Wallet balance drops below 0.5 IOTX safety floor | MEDIUM | parallel_o3_act_anchor.py refuses to fire below floor. Refuel via IoTeX testnet faucet. |
| Operator accidentally fires O3 ceremony with O2 env var still set | LOW | INTENTIONAL env var distinction (OPERATOR_INITIATIVE_O2_AUTHORIZED vs OPERATOR_INITIATIVE_O3_AUTHORIZED) prevents this. |
| Mainnet operation attempted before all three agents at O3_ACT | CRITICAL | This roadmap is the gating doc. Confirm all 3 agents at O3_ACT via on-chain state before any mainnet ceremony. |

---

## 6. What this roadmap does NOT authorize

- **Does NOT authorize mainnet operations.** Per operator directive 2026-05-13: "Do not deploy anything to mainnet until the Operators Initiative is totally complete." That state is reached only after Step 7 confirms all 3 agents at O3_ACT.
- **Does NOT bypass any operator gate.** Every ceremony in this roadmap requires the standard three-factor authorization at PowerShell terminal.
- **Does NOT modify the FROZEN PoAC wire format / chain link hash / PATTERN-017 primitive family / cheat code taxonomy.** These remain pinned by PV-CI INV-001..INV-016 + the larger family.
- **Does NOT replace the Curator MockKMSClient on testnet.** Mainnet Curator activation requires AWS KMS HSM provisioning per `wiki/runbooks/curator_mainnet_migration.md` — that is a separate workstream from this roadmap.

---

## 7. Forward dependency map after Operator Initiative completion

Once all three agents are at O3_ACT (Step 7 PASS), the following downstream items unblock:

1. **VPMAnchorRegistry deploy** — `wiki/runbooks/vpm_anchor_registry_deploy_runbook.md` (~0.1 IOTX testnet)
2. **W3bstream applet registration** — operator runtime at console.w3bstream.com (~0.02 IOTX off-chain coordination)
3. **LayerZero VHP testnet deploy** — `wiki/runbooks/layerzero_vhp_mainnet_activation_runbook.md` (testnet only)
4. **Phase 99 TGE consideration** — operator decision; gated by separation_ratio > 1.0 confirmation AND all_pairs_above_1=True (AIT battery currently CLEARED; touchpad_corners 0.728 remains BLOCKER for tournament BLOCK enforcement)
5. **LayerZero VHP mainnet deploy** — only after all of: Operator Initiative complete + separation_ratio invariant cleared on touchpad_corners + third-party audit + mainnet wallet funded ≥10 IOTX + ≥0.05 ETH

Item #5 is the final mainnet gate. No earlier ceremony in this list unlocks mainnet.

---

*— VAPI Principal Architect, 2026-05-13. Current as of HEAD `020644ba`.*
