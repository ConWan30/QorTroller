# Phase O0 Stream 2-Deploy — Local Hardhat Dry-Run Runbook

**Date executed**: 2026-04-28
**Executed by**: Phase O0 implementation session (Claude Opus 4.7)
**Wallet state at execution**: 0.5525 IOTX (below 3 IOTX threshold; Stream 2-deploy on IoTeX testnet remains gated)
**Repository commit**: `7ad1b5ad` (Stream 5-prep Session 2 — final source-and-tests commit)

## Purpose

Verify the five Phase O0 deploy scripts execute end-to-end against a clean
EVM chain with cross-contract dependencies wiring correctly. Catches bugs
before they consume real testnet IOTX. Produces the canonical deploy
sequence so Stream 2-deploy on IoTeX testnet can run as a confident sweep
when the wallet refills.

## Scripts executed (deploy ordering FROZEN)

```
1. contracts/scripts/deploy-agent-registry.js              (no upstream deps)
2. contracts/scripts/deploy-agent-scope.js                 (reads AgentRegistry)
3. contracts/scripts/deploy-audit-log.js                   (no upstream deps)
4. contracts/scripts/deploy-agent-slashing.js              (reads AgentRegistry)
5. contracts/scripts/deploy-agent-adjudication-registry.js (reads AgentRegistry + AgentScope)
```

Steps 1, 3 are independent. Steps 2, 4, 5 depend on Step 1's output via
`contracts/deployed-addresses.json`. Step 5 requires Step 2's output too.

The dependency chain enforces ordering: AgentRegistry MUST be the first
contract deployed; AgentAdjudicationRegistry MUST be the last (it has
two upstream dependencies). Steps 2, 3, 4 can run in any order between
those endpoints.

## Dry-run setup

```
# Backup production deployed-addresses.json (the dry-run scripts overwrite it)
cp contracts/deployed-addresses.json contracts/deployed-addresses.json.dryrun-backup

# Start a clean Hardhat node (chain ID 31337, port 8545) in background
cd contracts && npx hardhat node &

# Wait for JSON-RPC readiness
until curl -sX POST http://127.0.0.1:8545 -H 'Content-Type: application/json' \
  --data '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}' \
  | grep -q '0x7a69'; do sleep 1; done
```

After verifying, restore the backup:

```
cp contracts/deployed-addresses.json.dryrun-backup contracts/deployed-addresses.json
rm contracts/deployed-addresses.json.dryrun-backup
# Stop the Hardhat node (Ctrl+C or kill the background pid)
```

## Results — all five scripts succeeded with clean smoke tests

| # | Contract | Hardhat address (LOCAL ONLY) | Smoke tests |
|---|---|---|---|
| 1 | AgentRegistry | `0x5FbDB2315678afecb367f032d93F642f64180aa3` | owner, totalAgents=0, status enums |
| 2 | AgentScope | `0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512` | owner, agentRegistry=Step 1 addr, getScopeRoot returns bytes32(0) |
| 3 | AuditLog | `0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0` | owner, totalCheckpoints=0, MAX_TIMESTAMP_AGE=3600, sentinel-zero getLatestCheckpoint |
| 4 | AgentSlashing | `0xCf7Ed3AccA5a467e9e704C703E8D87F634fB0Fc9` | owner, agentRegistry, vetoWindowSeconds=86400, totalProposals=0, BURN_ADDRESS |
| 5 | AgentAdjudicationRegistry | `0xDc64a140Aa3E981100a9becA4E685f962f0cF6C9` | getAnchorCount=0, agentRegistry+agentScope wired correctly |

The Hardhat addresses are deterministic given the same deployer
(account #0 at index 0) and clean chain state — they will be identical
on any Hardhat node started from a fresh state. **They are NOT the
addresses these contracts will receive on IoTeX testnet** — those are
determined by the bridge wallet's nonce + the testnet's contract
creation address derivation. Do not record the Hardhat addresses in
`bridge/.env.testnet` or `contracts/deployed-addresses.json`.

## Gas-cost caveat

The Hardhat-localhost runs reported gas costs in the range of
0.0003 – 0.0007 IOTX-equivalent per deploy. **These numbers are
NOT representative of IoTeX testnet costs** because Hardhat's default
gasPrice differs from IoTeX testnet's 1000 Gwei (`hardhat.config.js`
declares `gasPrice: 1000000000000` for `iotex_testnet` network only;
the default `hardhat` network uses Hardhat's own gas dynamics).

Pass 2C Section 3.x estimates (per-contract):

| # | Contract | Pass 2C estimate |
|---|---|---|
| 1 | AgentRegistry | ~0.06 IOTX |
| 2 | AgentScope | ~0.05 IOTX |
| 3 | AuditLog | ~0.05 IOTX |
| 4 | AgentSlashing | ~0.06 IOTX |
| 5 | AgentAdjudicationRegistry | ~0.08 IOTX |
| | **Sweep total** | **~0.30 IOTX** |

To get accurate testnet-IOTX cost predictions before paying real gas,
re-run the dry-run with `--network iotex_testnet` only AFTER wallet
refill (the script's `< 3.0 IOTX` abort gate prevents running before
funding). Alternatively, set Hardhat's gasPrice override to 1000 Gwei
in `hardhat.config.js` `hardhat` block and re-run; the resulting IOTX
numbers will then be directly comparable.

## Cross-contract dependency wiring — VERIFIED

The most architecturally-sensitive deploy is AgentAdjudicationRegistry
because it has TWO upstream dependencies. The dry run confirmed:

- The constructor accepts `(deployer, agentRegistryAddr, agentScopeAddr)`
  in that order.
- The script correctly reads both addresses from
  `deployed-addresses.json` and refuses to proceed if either is missing
  (the `process.exit(1)` ABORT guards fire as designed).
- Post-deploy smoke tests confirmed the immutable `agentRegistry()` and
  `agentScope()` view functions return the addresses set at deploy time.
- `getAnchorCount()` returns 0 on a fresh deploy (sentinel state).

This validates the UNION storage decision from Stream 2-prep Session 5
(commit `7a4ae0d8`): Anchor[] _anchors + per-agent index +
_anchorIdByHash anti-replay tracker all initialize cleanly.

## Live IoTeX-testnet deploy command sequence (FOR USE WHEN WALLET REFILLS)

When the bridge wallet (`0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692`)
holds ≥3 IOTX (target 5 IOTX per Pass 2A V8), execute in order:

```bash
# Pre-flight
cd contracts
npx hardhat compile

# Verify wallet balance is above threshold (each script self-verifies but
# fail-fast at the start saves time)
npx hardhat run --network iotex_testnet scripts/wallet_balance.js  # if exists,
# else use cast call or eth_getBalance via curl

# Sweep: 5 deploys in dependency order. Each script self-aborts on
# failure and the next will not run because the addresses chain.
npx hardhat run --network iotex_testnet scripts/deploy-agent-registry.js
npx hardhat run --network iotex_testnet scripts/deploy-agent-scope.js
npx hardhat run --network iotex_testnet scripts/deploy-audit-log.js
npx hardhat run --network iotex_testnet scripts/deploy-agent-slashing.js
npx hardhat run --network iotex_testnet scripts/deploy-agent-adjudication-registry.js

# After all five succeed, deployed-addresses.json contains the live
# IoTeX testnet addresses. Update bridge/.env.testnet with each:
#   AGENT_REGISTRY_ADDRESS=...
#   AGENT_SCOPE_ADDRESS=...
#   AUDIT_LOG_ADDRESS=...
#   AGENT_SLASHING_ADDRESS=...
#   AGENT_ADJUDICATION_REGISTRY_ADDRESS=...
```

The bridge's chain wrappers (`anchor_agent_commit`,
`anchor_pda_attestation`, etc.) read these env vars at construction
time. Once set, the deferred-activation pattern in Stream 3-prep
Session 1/2 chain wrappers transitions from `(None, False)` returns to
live anchoring.

## Ordering rationale (why this sequence)

- **AgentRegistry first** — every other contract reads from it; it has
  no upstream deps. Single-point-of-failure: if this deploy fails, the
  sweep halts before any other script runs (each downstream script's
  `addresses["AgentRegistry"]` check fires `process.exit(1)`).

- **AgentScope second** — needed by AgentAdjudicationRegistry. Independent
  of AuditLog and AgentSlashing, but doing it second keeps the
  dependency-needers grouped before the dependency-roots.

- **AuditLog third** — independent. Could also run first or second; placed
  third for canonical-ordering stability across runs (matches Stream
  2-prep Session 3 commit ordering).

- **AgentSlashing fourth** — depends only on AgentRegistry; placed before
  AgentAdjudicationRegistry to defer the most-complex deploy to last.

- **AgentAdjudicationRegistry last** — has two upstream deps. Failing
  here doesn't strand any subsequent contracts (none depend on it
  within Phase O0; that comes in P1+).

## Open items

- **Section 6.2 GitHub Apps**: Apps must be registered before agents
  can commit (currently dormant — Phase O0 ships definitions but no
  active agents). Independent of wallet refill; runnable now.

- **Section 6.3 KMS provisioning**: AWS KMS keys per agent. Independent
  of wallet refill; runnable now. Public keys feed into ioID DID
  minting during Section 6.4.

- **Section 6.4 agent registration**: Gated on Stream 2-deploy
  (AgentRegistry must be live to call `registerAgent`).

- **Section 8 exit criteria** (24 testable): Gated on Stream 2-deploy
  for the on-chain criteria; off-chain criteria runnable now.

## Verification artifacts

- `deployed-addresses.json.dryrun-backup`: created at runbook start,
  removed at end. Restoration verified — production
  `deployed-addresses.json` returns to its pre-dry-run state with
  zero Phase O0 entries (consistent with Stream 2-deploy still being
  gated).

- Hardhat node task ID: `b59hwzkcv` (stopped post-sweep).

- This runbook's existence is the canonical artifact: future operators
  can re-run the dry-run sequence by following the steps above against
  any future contract source revision.
