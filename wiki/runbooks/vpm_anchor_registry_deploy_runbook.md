# VPMAnchorRegistry Deploy Runbook — Phase O4-VPM-ANCHOR

**Authoring commit:** to-be-assigned (this commit)
**Ceremony status:** READY-TO-FIRE pending operator authorization
**Wallet cost projection:** ~0.1 IOTX (testnet) — ~150× margin against current ~15.03 IOTX bridge wallet
**Architecture anchor:** `e81e04aa` (Phase O4-VPM-INTEGRATION close)

This runbook documents the operator-runtime three-factor ceremony to
deploy `VPMAnchorRegistry.sol` to IoTeX testnet (chain ID 4690),
extending the FROZEN quadruple-bind into a quintuple-bind:

```
frozen-primitive  ↔  frozen-compiler  ↔  frozen-visual-grammar
                  ↔  frozen-iframe-sandbox
                  ↔  frozen-on-chain-anchor  ← THIS DEPLOY ADDS
```

The agent CANNOT fire this ceremony. The script `contracts/scripts/
deploy-vpm-anchor-registry.js` enforces three independent gates
(env var + env var + wallet floor) that must be set by the operator at
the PowerShell terminal.

## Pre-flight checklist

Before opening PowerShell:

- [ ] Wallet balance ≥ 0.5 IOTX (script aborts below this floor)
- [ ] AdjudicationRegistry LIVE at `0x44CF981f46a52ADE56476Ce894255954a7776fb4`
      (Phase 111; verify via IoTeX testnet explorer — script binds to
      this address at construction; immutable post-deploy)
- [ ] `contracts/deployed-addresses.json` does NOT already contain a
      `VPMAnchorRegistry` entry (or operator intends to overwrite)
- [ ] `bridge/.env` ready to receive `VPM_ANCHOR_REGISTRY_ADDRESS=<addr>`
      after successful deploy
- [ ] Hardhat node + IoTeX testnet RPC reachable (test connection
      separately with `curl https://babel-api.testnet.iotex.io/...`)

## Three-factor ceremony

Open PowerShell in `C:\Users\Contr\vapi-pebble-prototype\contracts\`.

```powershell
# Factor 1: explicit kill-switch lift (process-scoped; bridge/.env
# remains pinned at CHAIN_SUBMISSION_PAUSED=true after the script exits)
$env:CHAIN_SUBMISSION_PAUSED = "false"

# Factor 2: explicit operator intent (specific to THIS ceremony — does
# NOT carry over to other anchor scripts)
$env:OPERATOR_VPM_ANCHOR_AUTHORIZED = "true"

# Factor 3: fire the deploy
npx hardhat run scripts/deploy-vpm-anchor-registry.js --network iotex_testnet
```

The script self-checks Factor 1 (exits code 2 if missing) and Factor 2
(exits code 3 if missing) before any RPC contact. No wallet impact on
gated abort.

## Successful-deploy verification

The script self-runs 4 smoke tests:

1. `owner() == deployer` — deployer address binds correctly
2. `adjudicationRegistry() == 0x44CF981f...` — composition link pinned
3. `totalAnchored() == 0` — cold-start sanity
4. `isAnchored(0x0) == false` — zero-hash guard

If all 4 pass, the script prints:

```
VPMAnchorRegistry deployed to: 0x<...>
Wallet balance (post-deploy): <...> IOTX
Deploy cost: ~0.1 IOTX
contracts/deployed-addresses.json updated
```

## Post-deploy actions (operator runs at terminal)

```powershell
# 1. Add the deployed address to bridge/.env (next bridge restart picks it up)
echo "VPM_ANCHOR_REGISTRY_ADDRESS=0x<deployed_addr>" >> bridge/.env

# 2. Re-pin CHAIN_SUBMISSION_PAUSED=true in current shell (defense in depth)
$env:CHAIN_SUBMISSION_PAUSED = "true"

# 3. Clear the explicit-intent flag
Remove-Item Env:\OPERATOR_VPM_ANCHOR_AUTHORIZED

# 4. Update CLAUDE.md NOTE entry marking Phase O4-VPM-ANCHOR COMPLETE
#    with deployed address + tx hash + actual wallet cost
```

## On-chain verification

After deploy, verify on the IoTeX testnet explorer
(https://testnet.iotexscan.io/):

- [ ] Contract address resolves to bytecode (not 0x prefix)
- [ ] `owner()` view returns the bridge wallet
      `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692`
- [ ] `adjudicationRegistry()` view returns
      `0x44CF981f46a52ADE56476Ce894255954a7776fb4`
- [ ] `totalAnchored()` view returns 0

## Partial-failure recovery

If the deploy transaction reverts mid-flight (rare but possible on
IoTeX testnet during P256 precompile contention):

1. Check wallet decrement amount via explorer — partial state is
   recoverable via the deployment transaction's revert receipt
2. If contract address never resolved: deploy was atomic-aborted;
   no state created on chain; re-run script after addressing root
   cause (RPC contention / gas estimation drift / wallet balance)
3. If contract address resolved but `totalAnchored` ≠ 0: this is the
   "second deploy over first" scenario — old contract still exists at
   prior address but is no longer the canonical one per
   `deployed-addresses.json`. Pre-existing anchors on the old contract
   are NOT automatically migrated.

## What this ceremony does NOT do

- Does NOT anchor any VPM artifacts (next-step: implement
  `chain.anchor_vpm()` async helper + the
  `parallel_vpm_anchor.py` ceremony script in a follow-up commit)
- Does NOT lift `CHAIN_SUBMISSION_PAUSED` permanently — only for the
  duration of the deploy script's PowerShell session
- Does NOT modify `AdjudicationRegistry` — composition is read-only
  via `isRecorded()`
- Does NOT enable VPM artifact emission — VPM compilers in
  `scripts/vpm_compile_*.py` continue to write filesystem-only HTML;
  on-chain anchoring is a separate operator-authorized step per
  anchor

## Cost projection breakdown

| Item | Hardhat baseline | IoTeX testnet (2.7× multiplier) |
|---|---|---|
| Deployment | ~0.005 IOTX | ~0.014 IOTX |
| Constructor binding | ~0.001 IOTX | ~0.003 IOTX |
| 4 smoke calls | ~0.001 IOTX | ~0.003 IOTX |
| Total + 50% margin | ~0.011 IOTX | ~0.1 IOTX |

Worst case under current 4000-Gwei IoTeX testnet gas conditions: ~0.15
IOTX. Wallet floor 0.5 IOTX provides 3× margin even at worst case.

## Forward-vector connection

This deploy unblocks v4 §15 tier #4 (VPMAnchorRegistry.sol ceremony).
Subsequent follow-up commits enable:

- `chain.anchor_vpm()` async helper in `bridge/vapi_bridge/chain.py`
- `scripts/parallel_vpm_anchor.py` triple-gate per-VPM ceremony script
- `INV-VPM-ANCHOR-001/002/003` PV-CI invariants pinning the
  contract literal + composition link + ceremony script (deferred to
  Phase O5 — requires governance ceremony)

These follow-ups are wallet-free (write-only code changes) but require
this deploy to have completed first.

---

*— VAPI Architect, 2026-05-13*
