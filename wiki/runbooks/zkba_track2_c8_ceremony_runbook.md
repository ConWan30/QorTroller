---
title: "ZKBA Track 2 C8 Ceremony — Operator Runbook"
date: 2026-05-12
proposal_type: OPERATOR-RUNBOOK
status: "🚀 FIRED 2026-05-12 — Cedar v2 bundles LIVE on IoTeX testnet (3/3 successes; 6 dual-anchor txs)"
scope: "Operator-runtime ceremony procedure. Wallet-spending (~0.23 IOTX projected)."
authority: "VAPI Architect; bridge wallet 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692"
ships_under: "Track 2 gate-by-gate authorization 2026-05-12"
related_commits:
  - "755fac33" # C6 Cedar v2 bundles + FSCA rules
  - "531dbc6b" # C7 anchor script + chain method
---

# ZKBA Track 2 C8 Ceremony — Operator Runbook

## 0. Reading note

**🚀 STATUS UPDATE 2026-05-12: CEREMONY FIRED. 3/3 successes.**

Cedar v2 bundles are LIVE on IoTeX testnet via 6 dual-anchor txs:

| Agent | Operational tx | Governance tx |
|---|---|---|
| anchor_sentry v2 | `3f79b4b428e0931671...` | `04029ac59b4e08084f...` |
| guardian v2 | `1e3a65f4445d73cc37...` | `16ce625cdc9c8fc2cb...` |
| curator v2 | `470cbd17c865eef82b...` | `5aac0d92866ac29cc5...` |

Operator wallet pre-ceremony: 15.2626 IOTX. Post-ceremony delta ~0.23 IOTX
across 6 dual-anchor txs. Kill-switch restored to safe posture immediately
after ceremony.

The original procedure below is retained for historical reference + as
the template for future re-anchoring (e.g., Cedar v3 bundles if a future
operator-authorized methodology amendment requires it).

This runbook was originally **OPERATIONAL** and **READY-TO-FIRE**. It documents
the operator three-factor authorization procedure for executing the
Cedar v2 bundle re-anchoring ceremony (plan §6 A4) shipped under
Track 2 gate-by-gate authorization.

C6 (commit `755fac33`) shipped the three Cedar v2 bundles + FSCA
contradiction rules. C7 (commit `531dbc6b`) shipped the
`scripts/parallel_zkba_anchor.py` triple-gate script + the
`chain.anchor_zkba_artifact()` method. This runbook is **C8** — the
ceremony that fires the script when operator three-factor
authorization aligns.

**Wallet impact:** ~0.23 IOTX (6 dual-anchor txs × ~0.04 IOTX each
at current testnet gas; +25% safety margin = 0.30 IOTX). Wallet at
~15.44 IOTX provides 67× margin.

**Chain impact:** 6 transactions on IoTeX testnet (chain ID 4690):
3 operational anchors via `AgentScope.setAgentScopeRoot()` + 3
governance anchors via `AgentRegistry.updateAgentScope()`. Each
dual-anchor pair is atomic per the `cedar_bundle_anchor.anchor_bundle()`
implementation — operational FIRST, governance SECOND, per
INV-OPERATOR-AGENT-001.

---

## 1. Pre-Flight Checklist (5 items)

Before running the ceremony, the operator verifies the following five
conditions:

### 1.1 Wallet balance ≥ 1.0 IOTX

```powershell
# PowerShell — check bridge wallet balance via Etherscan-equivalent or
# direct RPC. Bridge wallet: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
# Current expected balance: ~15.44 IOTX (per CLAUDE.md top-of-file as of
# 2026-05-12).
```

**Status:** SATISFIED at 15.44 IOTX per CLAUDE.md.

### 1.2 No HIGH/CRITICAL FSCA contradictions

```powershell
# Query the FSCA contradiction log for active HIGH/CRITICAL events
# in the last hour:
curl -H "x-api-key: $env:OPERATOR_API_KEY" `
     "http://localhost:8081/operator/fsca/contradictions?severity=HIGH,CRITICAL"
```

Expected response: `row_count: 0`. If any HIGH/CRITICAL contradictions
are active at ceremony moment, operator MUST investigate and resolve
before proceeding — per the discipline I've maintained throughout the
session.

**Status:** OPERATOR-VERIFICATION required at ceremony moment.

### 1.3 v2 bundle Merkle roots match C6 ship state

```powershell
python scripts/cedar_bundle_validate.py validate `
    bridge/vapi_bridge/cedar_bundles/anchor_sentry_o2_suggest_v2.json

python scripts/cedar_bundle_validate.py validate `
    bridge/vapi_bridge/cedar_bundles/guardian_o2_suggest_v2.json

python scripts/cedar_bundle_validate.py validate `
    bridge/vapi_bridge/cedar_bundles/curator_o2_suggest_v2.json
```

Expected Merkle roots (C6 ship state; locked at commit `755fac33`):

| Agent | Expected Merkle root |
|---|---|
| Sentry v2 | `0x39e8b65f0a87671fc003c28c3f28a7afd7fae41b6c3505d1ddb3d05ff3db1f23` |
| Guardian v2 | `0x6818a9ad49dab7898925e530526c50fcce515a889c3666f1434e6470c660a9a0` |
| Curator v2 | `0x0ade0c92cf2aa0c5675701861ed535683f0dfd15873424a9838d402b60a80b3d` |

Any Merkle drift indicates a bundle file was modified post-C6 ship —
operator MUST investigate before firing.

**Status:** SATISFIED at C7 ship time per T-ZKBA-T2-C7-6 test;
re-verify at ceremony moment.

### 1.4 Operator Decision Matrix dependencies SATISFIED

The C8 ceremony depends on:

| Dependency | Status |
|---|---|
| D-NUM resolved (V8DIP-0002 owns 0002 slot for ZKBA) | ✅ SATISFIED at `40d22598` (Option N1) |
| D-TRACK2-G9 (numbering applied) | ✅ SATISFIED via D-NUM resolution |
| D-TRACK2-C6 (v2 bundles + FSCA rules) | ✅ SATISFIED at `755fac33` |
| D-TRACK2-C7 (anchor script + chain method) | ✅ SATISFIED at `531dbc6b` |
| D-TRACK2-WALLET (≥1.0 IOTX) | ✅ SATISFIED at 15.44 IOTX |
| D-TRACK2-FSCA (no HIGH/CRITICAL) | ⏳ Operator-verification at ceremony moment |
| D-TRACK2-KILLSWITCH (3-factor) | ⏳ Operator three-factor authorization at ceremony moment |
| D-TRACK2-G6 (AgentScope/Cedar authority) | ⏳ Operator authorization per agent |
| D-TRACK2-G7 (Curator review readiness) | ⏳ Operator verification |
| D-TRACK2-G8 (Internal Projection First) | ✅ PARTIAL via GIC ledger; CDRR DAG post-bootstrap |

### 1.5 Dry-run verification

```powershell
# Dry-run: verifies gates + Merkle roots + wallet balance without
# firing any anchor tx. Safe to run repeatedly.
python scripts/parallel_zkba_anchor.py --dry-run
```

Expected: gates fail (env vars not set), exit 1. This is the correct
behavior — dry-run is for the verification path, not the firing path.

To dry-run the firing path with env vars set:

```powershell
$env:CHAIN_SUBMISSION_PAUSED = "false"
$env:OPERATOR_ZKBA_ANCHOR_AUTHORIZED = "true"
python scripts/parallel_zkba_anchor.py --dry-run
# Should print "DRY-RUN MODE — would fire 6 anchor txs (3 bundles × dual)"
# and exit 0 WITHOUT making any chain RPC call.
```

---

## 2. Three-Factor Authorization Sequence

When all pre-flight items are SATISFIED and operator decides to fire:

```powershell
# Factor 1 — kill-switch lift in process env (NOT bridge/.env)
$env:CHAIN_SUBMISSION_PAUSED = "false"

# Factor 2 — affirmative intent flag in process env (DIFFERENT
# env-var name from O2_AUTHORIZED to prevent residual cross-context
# carry-over — defense-in-depth pattern)
$env:OPERATOR_ZKBA_ANCHOR_AUTHORIZED = "true"

# Factor 3 — --confirm CLI flag fires the ceremony
python scripts/parallel_zkba_anchor.py --confirm
```

### 2.1 Expected output during firing

```
==============================================================================
Phase O3-ZKBA-TRACK1 Track 2 — Parallel ZKBA Cedar v2 Bundle Anchor
==============================================================================

  Gates 1 + 2: Gates 1 + 2 aligned
  Gate 3: --confirm CLI flag present
  Pre-flight Merkle verification: All three Merkle roots match EXPECTED_MERKLES
    anchor_sentry   0x39e8b65f0a87671f...db1f23
    guardian        0x6818a9ad49dab789...0a9a0
    curator         0x0ade0c92cf2aa0c5...60a80b3d
  cfg.chain_submission_paused = False (kill-switch lifted)
  Wallet balance: 15.4234 IOTX

  → Firing parallel ZKBA Cedar v2 ceremony (6 dual-anchor txs)

  [anchor_sentry] anchoring v2 bundle anchor_sentry_o2_suggest_v2.json
    op_tx:  0x...
    gov_tx: 0x...
  [guardian] anchoring v2 bundle guardian_o2_suggest_v2.json
    op_tx:  0x...
    gov_tx: 0x...
  [curator] anchoring v2 bundle curator_o2_suggest_v2.json
    op_tx:  0x...
    gov_tx: 0x...

  Ceremony result: 3/3 successes, 0/3 failures
  All three Cedar v2 bundles dual-anchored.
  ZKBA Track 2 C8 ceremony COMPLETE.
```

### 2.2 Partial-failure recovery

If the script reports `failures` > 0, atomic-stop is in effect:

1. **DO NOT re-run immediately.** The script will refuse to re-anchor
   the same bundles (cedar_bundle_anchor enforces anti-replay at the
   AgentScope/AgentRegistry contract level).
2. **Inspect activation_log** via:
   ```sql
   SELECT * FROM operator_agent_activation_log
   WHERE phase = 'O2_SUGGEST' AND created_at >= datetime('now', '-1 hour')
   ORDER BY created_at DESC;
   ```
3. **Determine which dual-anchor pairs landed:** each successful pair
   has BOTH `op_tx_hash` and `gov_tx_hash` populated. Partial pairs
   (operational landed but governance reverted, or vice versa) are
   the recovery scope.
4. **For partial pairs:** the recovery procedure depends on which leg
   landed. Operational-landed-only requires governance follow-up via
   direct AgentRegistry.updateAgentScope() call (cedar_bundle_anchor
   helper). Governance-landed-only is the irrecoverable case (would
   require operational also landed first per
   INV-OPERATOR-AGENT-001) — investigate.

---

## 3. Post-Ceremony Verification

After the ceremony reports SUCCESS:

### 3.1 Verify on-chain scope roots match v2 bundles

```python
# From a bridge-aware Python shell:
from bridge.vapi_bridge.config import Config
from bridge.vapi_bridge.store import Store
from bridge.vapi_bridge.chain import ChainClient
import asyncio

cfg = Config()
chain = ChainClient(cfg, Store(cfg.db_path))

# Sentry v2 expected: 0x39e8b65f...
print("Sentry scope:", asyncio.run(chain.get_agent_scope_root(cfg.operator_agent_anchor_sentry_id)))

# Guardian v2 expected: 0x6818a9ad...
print("Guardian scope:", asyncio.run(chain.get_agent_scope_root(cfg.operator_agent_guardian_id)))

# Curator v2 expected: 0x0ade0c92...
print("Curator scope:", asyncio.run(chain.get_agent_scope_root(cfg.operator_agent_curator_id)))
```

Each on-chain scope root MUST match the corresponding v2 bundle's
Merkle root listed in §1.3.

### 3.2 Verify FSCA cleanliness post-ceremony

```powershell
# Expected: row_count=0 immediately post-ceremony. If
# BUNDLE_HASH_DRIFT_DETECTED fires within the cedar_drift_sweeper's
# next poll cycle (default 60s), there's a problem — the on-chain
# scope root doesn't match the local file. Investigate.
curl -H "x-api-key: $env:OPERATOR_API_KEY" `
     "http://localhost:8081/operator/operator-agent-drift-log?since_minutes=5"
```

### 3.3 Restore kill-switch

```powershell
# After ceremony complete, return to safe posture
$env:CHAIN_SUBMISSION_PAUSED = "true"
Remove-Item Env:OPERATOR_ZKBA_ANCHOR_AUTHORIZED
```

---

## 4. Methodology Layer Completion State (Post-C8)

Once C8 ceremony fires successfully, the Methodology Layer (Layer 7)
reaches its **full activation state**:

| Component | Pre-C8 | Post-C8 |
|---|---|---|
| VAD framework (VBDIP-0001) | FROZEN | FROZEN |
| ZKBA primitive (#10 in PATTERN-017) | Implementation only | Implementation + on-chain Cedar v2 authority |
| VPM wrapper layer | Implementation only | Implementation + on-chain Cedar v2 authority |
| G4 manifest validator | 4-surface reach trio | Same (unchanged by C8) |
| Architect Ed25519 signing chain | LIVE | LIVE (unchanged) |
| PV-CI methodology-layer invariants | 7 entries | Same (unchanged by C8) |
| Cedar v1 bundles on-chain | LIVE | LIVE (preserved) |
| Cedar v2 bundles on-chain | UN-ANCHORED | LIVE (ceremony fires) |
| Agent authority to write ZKBA artifacts | FORBIDDEN by current bundles | PERMITTED per v2 lane prefixes |
| Operator Decision Matrix queue | 6 of 16 RESOLVED | 13 of 16 RESOLVED (+G6/C8/KILLSWITCH/FSCA) |

The Methodology Layer's Track 2 activation completes the multi-day
arc from `f47763fe` (reconciliation plan, 2026-05-12) through C8
ceremony.

---

## 5. What This Runbook Does NOT Authorize

- Does NOT fire any chain transaction from this document.
- Does NOT bypass any of the three authorization factors.
- Does NOT extend ceremony scope beyond the 3 Cedar v2 bundles
  + 6 dual-anchor txs.
- Does NOT authorize Track 3 (post-Track-2 work that may include
  Cedar v3 + ZKBA artifact draft generators going LIVE on
  zk_artifacts/ / zk_verifications/ / zk_listings/ lanes).
- Does NOT modify v1 bundles (they remain LIVE alongside v2;
  operator may choose to deprecate v1 in a future operator-authorized
  follow-up).

---

## 6. Cross-References

- `scripts/parallel_zkba_anchor.py` (commit `531dbc6b`) — script
- `bridge/vapi_bridge/chain.py` `anchor_zkba_artifact` method
  (commit `531dbc6b`)
- `bridge/vapi_bridge/cedar_bundles/anchor_sentry_o2_suggest_v2.json`
  (commit `755fac33`)
- `bridge/vapi_bridge/cedar_bundles/guardian_o2_suggest_v2.json`
  (commit `755fac33`)
- `bridge/vapi_bridge/cedar_bundles/curator_o2_suggest_v2.json`
  (commit `755fac33`)
- `bridge/vapi_bridge/fleet_signal_coherence_agent.py` FSCA rules
  (commit `755fac33`)
- `vsd-vault/proposals/drafts/OPERATOR-DECISION-MATRIX.DRAFT.md`
  cluster E
- `wiki/methodology/METHODOLOGY_LAYER_INTEGRATION_MAP.md` Layer 7
  description
- `wiki/methodology/VBDIP-0002-zkba-visual-projections.md` §16
  activation gates

---

**End of Track 2 C8 ceremony runbook v1.0.**

The ceremony is READY-TO-FIRE under operator three-factor
authorization at ceremony moment. This runbook documents the
procedure; it does NOT execute the procedure. Operator authorization
controls whether C8 fires.
