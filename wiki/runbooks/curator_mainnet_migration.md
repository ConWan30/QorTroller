# Curator Mainnet Migration Runbook

> **Status:** RUNBOOK ONLY — execution gated on operator funding the
> mainnet wallet and authorizing AWS KMS HSM provisioning cost.
>
> **Owners:** Operator (authorization) + automation harness (execution).
>
> **Pre-read:** [`project_curator_operator_initiative_continuation.md`](../../memory/project_curator_operator_initiative_continuation.md),
> Phase O0 Stream 2 deploy runbook, Phase O1 C1 anchor commit `a02bcdb3`,
> Sessions 1+2+3 commits `eeeeb366` / `1b2eb037` / `76c92e9b`.

---

## Why this runbook exists

The Curator agent was activated at `O1_SHADOW` on **IoTeX testnet** during
Sessions 1+2+3 (2026-05-09) using a **`MockKMSClient`** for attestation
signing.  That decision was operator-authorized as a wallet-frugal
shortcut: real AWS KMS HSM provisioning costs ~$120/month minimum and
the testnet activation needed to ship before the marketplace
infrastructure (Phase 238 Step H) could begin accumulating real listings
and shadow data.

When the protocol promotes to **mainnet**, three structural facts force
a Cedar bundle re-anchor under a NEW agentId:

1.  **AWS KMS HSM provisioning generates a new public key.**  The agent's
    32-byte `agentId` is derived from the device public key (Phase O0
    Pass 2C Q9 frozen formula).  A new public key → a new agentId.
2.  **Mainnet ioID DID is distinct.**  `did:io:0x…` mainnet identifier
    differs from the testnet one (`did:io:0x7BdB744c…`, tokenId 497).
3.  **The mainnet AgentRegistry contract is a separate deployment.**
    Cross-chain reuse of the testnet agentId would not type-check.

Without this runbook, the mainnet promotion would silently orphan
~30 days of testnet shadow data, FSCA `coherence_id` rows, and Phase
O1 D advancement watcher metrics.

---

## Pre-flight checklist

- [ ] Mainnet wallet funded ≥ 5 IOTX (deploy + dual-anchor + ioID mint
      + ERC-6551 TBA + initial canary).
- [ ] AWS KMS HSM provisioning ticket filed, region selected, and KMS
      key ARN reserved.
- [ ] GitHub App OAuth credentials for the Curator-mainnet identity
      provisioned (NOT shared with testnet identity — clean separation).
- [ ] `bridge/.env.mainnet` template prepared with all *new* mainnet
      addresses for Phase O0 Stream 2 contracts (AgentScope, AgentRegistry,
      AgentAdjudicationRegistry, IoIDStore, ERC-6551 Registry).
- [ ] Phase 238 Step H mainnet redeploy completed:
      `VAPIDataMarketplaceListings` re-deployed; `setCurator(NEW_AGENT_ADDR)`
      reservation hook ready (Phase 238 Step F pattern).
- [ ] Phase O1-FRR (this phase) shipped, validated, and `frr_hex`
      baseline accumulated for ≥ 30 days on testnet.
- [ ] Operator has read [`Phase O0 Stream 2 Deploy Runbook`](../../docs/phase-o0-stream-2-deploy-dryrun.md)
      and the four `8c0c8200`/`fef267e9`/`300c49e4`/`10288cc3`/`a107d404`
      empirical-fix commits (IoTeX testnet quirks recur on mainnet).

---

## Execution sequence

### Step 1 — Reserve mainnet identity slot

1.  Run Phase O0 Pass 2C Block A on mainnet to mint the agent's NFT
    via `VAPIOperatorAgentNFT` (mainnet deploy — separate from testnet
    `0xa0CDD2B3E292c56030185c66a3d423278A4c467b`).
2.  Generate the AWS KMS HSM key pair; capture the public key.
3.  Compute the **new mainnet agentId** via Q9 formula:
    `agent_id_mainnet = sha256(b"VAPI-AGENT-Q9-v1" || pubkey_uncompressed)`.
4.  Verify three sources match byte-for-byte (independent computation +
    NFT contract `agentIdOf()` return + `AgentRegistered` event log).

### Step 2 — Build the agentId-translation table

Capture in `wiki/migrations/curator_testnet_to_mainnet.json`:

```json
{
  "schema_version": 1,
  "migrated_at_iso": "<UTC ISO8601>",
  "operator_authority_hash": "<SHA-256 of authorization signature>",
  "testnet": {
    "agent_id": "0xed6a2df58e5ec50c1f88e127f6982a348f6855202b662b8ad73ffa1c1fda11a8",
    "ioid_did":  "did:io:0x7BdB744c87c8f86e348246557BB58D60641312C2",
    "ioid_token_id": 497,
    "tba": "0x6A385dF2501D42ef2Cf918eE1e3b6011903e418F",
    "kms_client": "MockKMSClient",
    "first_anchored_at": "<UTC ISO8601 from operator_agent_activation_log>",
    "last_observed_phase": "O2_SUGGEST",
    "shadow_evaluations_total": "<int from operator_agent_shadow_log>"
  },
  "mainnet": {
    "agent_id": "<NEW mainnet 0x… 32B>",
    "ioid_did":  "did:io:0x…",
    "ioid_token_id": "<int>",
    "tba": "0x…",
    "kms_client": "AwsKmsHsmClient",
    "kms_key_arn": "arn:aws:kms:<region>:<acct>:key/<id>",
    "github_app_installation_id": "<int>"
  }
}
```

This file is **append-only** in the repo; never delete or rewrite.
Functions as the audit anchor for the migration event.

### Step 3 — FSCA `coherence_id` re-keying

The `coherence_id = "coh_" + sha256(rule_name + sorted_agents + ts_ns)[:16]`
pattern bakes the testnet agentId into every `BUNDLE_HASH_DRIFT_DETECTED`
+ `SCOPE_HASH_GOVERNANCE_DRIFT_DETECTED` row tied to Curator.  Mainnet
promotion would emit NEW `coherence_id` values for the SAME rule + agent
combination, splitting the FSCA contradiction history at promotion time.

Procedure:

1.  Snapshot `fleet_coherence_log` on testnet bridge (read-only):
    `SELECT * FROM fleet_coherence_log WHERE 'curator' IN agents_involved`
    → `wiki/migrations/curator_coherence_history_<ISO>.json` (audit
    artifact; never reused on mainnet).
2.  On mainnet bridge first-boot, FSCA starts fresh — no history copied.
    The testnet history is preserved in the snapshot file for forensic
    purposes only.
3.  If a mainnet contradiction surfaces with the same `rule_name`, FSCA
    will not auto-correlate it with the testnet pattern — operator must
    consult the snapshot manually.  This is **intentional** (clean
    separation), but the snapshot must exist.

### Step 4 — Cedar bundle re-anchor under mainnet agentId

1.  Author `bridge/vapi_bridge/cedar_bundles/curator_o1_shadow_v1_mainnet.json`
    (or whatever phase Curator is at when promotion happens).  Replace
    the `agent_id` field with the new mainnet 32B value.  All policies,
    lane prefixes, and skill grants UNCHANGED — only the `agent_id`
    binding changes.
2.  Validate via `python scripts/cedar_bundle_validate.py validate <new>`.
3.  Run dual-anchor against the **mainnet** AgentScope + AgentRegistry
    contracts via Phase O1 C1 `cedar_bundle_anchor.anchor_bundle()`.
    Expected gas: ~0.04 IOTX × 2 = ~0.08 IOTX (if mainnet gas tracks
    testnet).

### Step 5 — Phase 238 Step F `setCurator()` re-assignment

After step 4 completes:

1.  Operator (mainnet wallet, owner of `VAPIDataMarketplaceListings`)
    calls `setCurator(NEW_CURATOR_ADDR)` on the **mainnet**
    `VAPIDataMarketplaceListings`.  The Phase 238 Step F reservation hook
    accepts any address; this is the act that authorizes the new agent
    to record listing reviews on-chain.
2.  Verify via `getCurator()` view → returns `NEW_CURATOR_ADDR`.

### Step 6 — Phase O1 D advancement watcher reset

The `operator_initiative_advancement_log` table (Phase O1-FRR Stream C)
records testnet history.  On mainnet promotion:

1.  Mainnet bridge boots with a **fresh** `operator_initiative_advancement_log`
    (different DB; testnet rows do not migrate).
2.  Phase O2 SUGGEST `shadow_age_min_hours=504` (3 weeks) **counter
    restarts**.  This is intentional and structurally sound — the new
    mainnet agentId has zero mainnet shadow history.
3.  The most recent `frr_hex` value on testnet is preserved in the
    migration JSON (Step 2) for audit.  No on-chain commitment ports
    forward.

**Operator note:** if the desire is to "carry credit" from testnet
shadow time to satisfy mainnet O2 SUGGEST faster, it requires a separate
governance-event-authorized waiver — same shape as the parallel O2
anchor that this runbook accompanies.  Do NOT modify the
`PHASE_O2_SHADOW_MIN_HOURS = 504` constant; that's FROZEN.

### Step 7 — 30-day post-promotion observability window

After mainnet activation:

- **Day 0**: bridge boots with new agent identity; `frr_hex` recomputes
  against fresh activation_log; one row in `operator_initiative_advancement_log`.
- **Days 1–30**: FSCA in observation mode; any `BUNDLE_HASH_DRIFT_DETECTED`
  or `SCOPE_HASH_GOVERNANCE_DRIFT_DETECTED` is investigated as a *new*
  finding (not a repeat of testnet patterns).
- **Day 30**: operator reviews
  - Wallet spend (expected ≤ 0.50 IOTX maintenance)
  - FSCA contradiction count (expected = 0; > 0 = investigate)
  - Cedar shadow evaluation count (expected ≥ 1000; < 100 = bridge
    not actually exercising Curator)
  - `frr_hex` stability (should change only on legitimate phase
    advancement; spurious changes = bug)

If all four checks pass on day 30, mainnet Curator is considered
production-stable and Phase O2 SUGGEST mainnet anchor can be authorized.

---

## Rollback procedure (if mainnet activation fails)

1.  **Do NOT** un-mint the mainnet NFT (NFTs are soulbound; un-minting
    is not supported).  Operator accepts the wallet cost as sunk.
2.  Revoke `setCurator(NEW_CURATOR_ADDR)` by calling `setCurator(0)`
    on `VAPIDataMarketplaceListings` (mainnet).  This freezes new
    listing reviews from the broken agent identity.
3.  Update `wiki/migrations/curator_testnet_to_mainnet.json` with a
    `rollback_at_iso` field + `rollback_reason` text.
4.  Re-fund the testnet wallet if operator wishes to continue testnet
    operations under the original `0xed6a2df58e5ec50c1f88e127f6982a348f6855202b662b8ad73ffa1c1fda11a8`
    agentId.
5.  Open a new issue in `wiki/what_if/` documenting what failed.

---

## Cross-references

| Topic | Reference |
|-------|-----------|
| Operational FIRST invariant | `INV-OPERATOR-AGENT-001` (PV-CI registry); `bridge/vapi_bridge/cedar_bundle_anchor.py` Step 4-5 sequence |
| FRR baseline reset implication | Phase O1-FRR Stream C — `operator_initiative_advancement_log` does NOT migrate |
| 504h shadow counter restart | `PHASE_O2_SHADOW_MIN_HOURS` constant; `operator_initiative_advancement.py` line 81 |
| Curator avenue divergence (testnet) | CLAUDE.md NOTE 2026-05-09 — "MockKMSClient testnet, no GitHub App, no AWS KMS HSM" |
| Sentry+Guardian original avenue | Phase O0 Stream 2 deploy runbook; `docs/phase-o0-stream-2-deploy-dryrun.md` |
| Cedar bundle FROZEN-v1 schema | `bridge/vapi_bridge/cedar_parser.py` `parse_bundle()` |
| FSCA Curator wiring | `bridge/vapi_bridge/fleet_signal_coherence_agent.py` lines 536–617 (Phase O1-CURATOR-C6 commit `4d0f5519`) |

---

**Document version:** 1.0 (Phase O1-FRR ship)
**Last updated:** 2026-05-10
**Next review:** When operator funds the mainnet wallet and authorizes
HSM provisioning (no scheduled date).
