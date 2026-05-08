# Phase 99 Token-Launch Deploy Runbook

**Status:** DRY-RUN VERIFIED 2026-05-07. Ready for IoTeX testnet/mainnet execution when wallet refilled.
**Verification:** All 6 contracts deployed cleanly on local Hardhat with all sanity checks PASS.

## Wallet pre-flight

- **Required deployer:** `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692`
- **Estimated cost:** **~0.022 IOTX** (Hardhat: 0.008032 IOTX × 2.7 IoTeX multiplier per Phase O0 finding)
- **Recommended balance buffer:** ≥0.5 IOTX (margin for retries + Phase 99-RELATED follow-on calls)
- **Current wallet balance:** 0.13 IOTX (insufficient — refill required before run)

## Deploy sequence

Three scripts must run in order. **Each saves env vars + updates `contracts/deployed-addresses.json`.**

### Step 1 — Phase 99A (Foundation token + registries)

```bash
cd contracts
npx hardhat run scripts/deploy-phase99a.js --network iotex_testnet
```

Deploys:
- `VAPIToken` — ERC20Pausable, MAX_SUPPLY=1,000,000,000 VAPI, `tgeComplete=false`
- `VAPIOperatorRegistry` — staking + slashing, MIN_STAKE=10,000 VAPI, COOLDOWN=30 days
- `VAPIHardwareCertRegistry` — hardware cert (auto-certifies DualShock Edge)

**Hardhat dry-run cost:** 0.004832 IOTX
**IoTeX testnet estimate:** ~0.013 IOTX

**Sanity checks:** MAX_SUPPLY=1B ✓, tgeComplete=false ✓, MIN_STAKE=10000 ✓, COOLDOWN=30d ✓, DualShock Edge `isCertified()=true` ✓

**Output:** `bridge/.env.phase99a` contains:
```
VAPI_TOKEN_ADDRESS=0x...
OPERATOR_REGISTRY_ADDRESS=0x...
HARDWARE_CERT_REGISTRY_ADDRESS=0x...
```

### Step 2 — Phase 99B (GSR registry)

```bash
npx hardhat run scripts/deploy-phase99b.js --network iotex_testnet
```

Deploys:
- `VAPIGSRRegistry` — on-chain anchor for GSR biometric samples (independent of 99A; doesn't need token addr)

**Hardhat dry-run cost:** 0.001013 IOTX
**IoTeX testnet estimate:** ~0.003 IOTX

**Sanity check:** `recordSample()` + `getSampleCount()=1` ✓

**Output:** `bridge/.env.phase99b` with `GSR_REGISTRY_ADDRESS`

### Step 3 — Phase 99C (VHP soulbound + LayerZero bridge)

```bash
# Optional: set LZ_ENDPOINT env var for real LayerZero V2 endpoint
# Default: 0x0000000000000000000000000000000000000001 (stub)
npx hardhat run scripts/deploy-phase99c.js --network iotex_testnet
```

Deploys:
- `VAPIVerifiedHumanProof` — ERC-4671 soulbound VHP token
- `VAPIVerifiedHumanProofBridge` — LayerZero V2 OApp (stub mode without real endpoint)

**Hardhat dry-run cost:** 0.002186 IOTX
**IoTeX testnet estimate:** ~0.006 IOTX

**Sanity checks:** `mint()` + `isValid()` + `totalSupply()=1` ✓, `setPeer()` ✓

**Output:** `bridge/.env.phase99c` with `VHP_CONTRACT_ADDRESS` + `LAYERZERO_BRIDGE_ADDRESS`

## Post-deploy actions

After all 3 scripts succeed:

1. **Merge env vars** into `bridge/.env.testnet`:
   ```bash
   cat bridge/.env.phase99a bridge/.env.phase99b bridge/.env.phase99c >> bridge/.env.testnet
   ```

2. **Verify on IoTeX testnet explorer**:
   - All 6 addresses appear at https://testnet.iotexscan.io/address/{addr}
   - `eth_call` returns expected values (test via `cast call` or web3.py)

3. **Update CLAUDE.md** Phase 99 NOTE entry with the 6 LIVE addresses + tx hashes

4. **Commit `contracts/deployed-addresses.json`** with the new entries

## Token launch sequencing — DO NOT execute before:

Per CLAUDE.md hard rules:
- ✅ Separation ratio > 1.0 confirmed empirically (CLEARED via AIT N=37 ratio=1.199)
- ✅ N≥100 live non-dry-run adjudications, zero false positives (Phase 235-A GIC_100 reached)
- ⏳ Phase 239 closure (G2 7/9 P0 — G4 needed; Option A: declare AIT canonical)
- ⏳ VHP end-to-end demonstrated on testnet (this runbook)
- ⏳ TGE consideration (post all above)

**Phase 99 is INFRASTRUCTURE deploy only. `tgeComplete()` MUST remain `false`. No token mint until TGE consideration.**

## Empirical findings from dry-run

| Finding | Detail |
|---------|--------|
| All sanity checks pass | 6/6 contracts deployed without revert |
| Compilation clean | 54 Solidity files compiled without warning |
| Total Hardhat gas | 0.008032 IOTX |
| IoTeX testnet estimate | ~0.022 IOTX (2.7× multiplier per Phase O0 empirical) |
| Mainnet estimate | TBD — check IoTeX mainnet gas price at deploy time |
| Test artifacts cleaned | `bridge/.env.phase99a/b/c` deleted; `deployed-addresses.json` reverted |

## Risk register

| Risk | Mitigation |
|------|-----------|
| Wallet runs out mid-deploy | Fund ≥0.5 IOTX (22× margin over estimate) |
| LayerZero endpoint changes | Update `LZ_ENDPOINT` env before 99C; stub mode is safe fallback |
| IoTeX P256 precompile reverts | Phase 99 contracts don't use P256 — safe |
| `deployed-addresses.json` merge conflict | Run all 3 in sequence on same machine; commit atomically |
| Phase O1 + main protocol track interleaving | Phase 99 is independent; can run between O1 phases |

## Cross-references

- Dry-run verification: bridge/.env.phase99a/b/c outputs verified PASS on Hardhat 2026-05-07
- Phase O0 IoTeX gas multiplier: see memory `feedback_iotex_deployment_quirks.md`
- Token launch sequencing: CLAUDE.md hard rules + Phase 99-PREP commit
