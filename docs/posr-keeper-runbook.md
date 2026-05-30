# PoSR Keeper Runbook — Data Economy Arc 6

**Operator-fired cron** (Decision T1 → Option B). Single-developer testnet
posture: the bridge wallet is the keeper. Future migration to Curator
under expanded O3 scope is a governance proposal, not part of v1.

---

## What this does

Every ~3 minutes, calls `VAPITemporalBeaconRegistry.anchorBeacon(blockNumber)`
where `blockNumber` is the most recent cadence-aligned (multiple of 64)
IoTeX testnet block within the 256-block BLOCKHASH window. This durably
anchors the block hash so any VHR PoSR proof listed later (even hours/days
later) can have its open/close beacon hashes verified against the registry
via `verifyBeacon(block, hash)`.

Without this keeper, the BLOCKHASH window (~11 minutes empirical on IoTeX
testnet) closes and `verifyWithRecency` can no longer confirm session-recency
claims.

---

## Cost reality

| | |
|---|---|
| Empirical block cadence (2026-05-30) | 2.616 s/block |
| Anchor cadence (FROZEN INV-TBR-002) | 64 blocks ≈ 2.8 min/anchor |
| Anchors/day | ~516 |
| Cost/anchor (gas-only) | ~0.0005 IOTX |
| Daily cost | **~0.258 IOTX/day** |
| Monthly cost | **~7.7 IOTX/month** |

Bridge wallet refill cycle becomes operational reality. A keeper-dedicated
wallet (separately funded) is a reasonable future move.

---

## Pre-flight

**Required env (in `contracts/.env` or operator shell):**

```
TEMPORAL_BEACON_REGISTRY_ADDRESS=<post-deploy address>
DEPLOYER_PRIVATE_KEY=<bridge wallet key>
ANCHOR_BEACON_CONFIRM=1
```

**On-chain setup (one-time, operator-fired):**

1. Deploy `VAPITemporalBeaconRegistry` via `scripts/deploy-vapi-temporal-beacon-registry.js` (estimate-only by default; `VAPI_TBR_DEPLOY_CONFIRM=1` to broadcast). Record address.
2. From the owner wallet (bridge wallet), call `setKeeper(0x0Cf36dB57f…)` — sets the bridge wallet as the keeper.
3. Set `TEMPORAL_BEACON_REGISTRY_ADDRESS` in env.

---

## Running

**Single-shot (one anchor, then exit):**

```bash
ANCHOR_BEACON_CONFIRM=1 python scripts/anchor_beacon.py
```

**Dry-run (no broadcast):**

```bash
python scripts/anchor_beacon.py     # ANCHOR_BEACON_CONFIRM defaults to 0
```

**Loop mode (operator-supervised daemon):**

```bash
ANCHOR_BEACON_CONFIRM=1 python scripts/anchor_beacon.py --loop --sleep-s 170
```

Sleep interval `170s` matches the ~64-block cadence. The script is
idempotent: if the candidate cadence block is already anchored, it skips
without spending gas.

---

## Health checks

**Latest anchored block (off-chain RPC view, gas-free):**

```bash
# Read from any explorer or via cast/web3:
cast call $TEMPORAL_BEACON_REGISTRY_ADDRESS "latestAnchoredBlock()(uint256)" --rpc-url https://babel-api.testnet.iotex.io
```

**Or via the bridge's own chain helper (in a Python subprocess):**

```python
from bridge.vapi_bridge.config import Config
from bridge.vapi_bridge.chain import ChainClient
import asyncio
async def go():
    c = ChainClient(Config())
    block, hash_ = await c.get_latest_temporal_beacon()
    print(f"latest anchored block: {block}, hash: 0x{hash_.hex()}")
asyncio.run(go())
```

---

## Honesty rails (script-side)

- Skips if candidate cadence block is already anchored (idempotent)
- Refuses to spend > **0.005 IOTX** per anchor (gas-price safety hard-cap)
- Pre-send `estimate_gas` revert-guard (catches "outside BLOCKHASH window"
  if the chain has progressed past 256 blocks since startup)
- Verifies that the registry's `keeper()` matches the configured wallet
  before any broadcast — refuses if not
- Logs every action to stderr; emits one machine-readable
  `ANCHOR_RESULT_JSON {...}` line per anchor

---

## Failure modes + recovery

| | |
|---|---|
| RPC unreachable | Script exits with `outcome=rpc_down`. No retry inside the script; cron will retry on next interval. |
| Keeper mismatch | `outcome=keeper_mismatch`. Operator calls `setKeeper(<correct>)` from owner. |
| Candidate already anchored | `outcome=already_anchored`. No-op. |
| `estimate_gas` revert | `outcome=estimate_failed`. Usually means the candidate cadence block fell out of the 256-block window between picking and sending — cron self-corrects next interval. |
| Hard-cap exceeded | `outcome=hard_cap_exceeded`. IoTeX gas price spike — investigate. |
| Tx fails on-chain | `outcome=failed` with `status=0`. Investigate explorer trace. |

---

## Operational note

The bridge itself does not run this keeper — the keeper is a separate
operator-fired process. This is deliberate: the bridge's `CHAIN_SUBMISSION_PAUSED=true`
kill-switch should never be circumvented for keeper duty. If the bridge
crashes, the keeper continues. If the keeper crashes, the bridge continues
serving v1 (Arc 5) proofs while v2 PoSR-bound proofs degrade gracefully
(`PoSRBeaconBinder.fetch_latest_beacon` returns the stale anchor or None;
orchestrator falls back to v1).
