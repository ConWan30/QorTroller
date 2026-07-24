# ioID Controller Registration — Ceremony Scope (2026-07-17)

**Status:** SCOPE (not a build; not a GO). Grounds what a real gamer-owned ioID registration for the
certified controller (`581a836c`) concretely requires, mirroring the agent fleet's PROVEN ioID ceremony.

## What it delivers (and the honest ceiling)

The physical controller gets a gamer-owned **ioID DID** (`did:io:{device_id}`) + an **ERC-6551
Token-Bound Account**, minted by the gamer's own signature and bound to the HSM-VALID birth cert
(`581a836c`). This is the on-chain expression of "the gamer owns their controller identity."

**Ceiling:** testnet, no token; first-run is **developer-self** (the "gamer" = the operator's bridge
wallet). It proves the sovereign flow end-to-end; it is not a third-party onboarding.

## The proof this works: the agent fleet already did it

Every IoTeX ioID system contract is live and **agent-proven**: `ProjectRegistry`
(`0x060581AA…`), `ioIDRegistry` permit registry (`0x0A7e595C…`, F-T3-1), `ioIDStore`
(`0x60cac5CE…`), `ioID` (`0x45Ce3E6f…`). The agents ran the identical ceremony — Curator holds
`did:io:0x7BdB744c…`, tokenId 497, a live TBA. **The controller path is a mirror** with a new NFT +
project. `VAPIGamerControllerNFT.sol` source already exists (canonical DeviceNFT: `initialize` /
`configureMinter` / `mint`).

## The five prerequisites, decomposed

| # | Prereq | State | Build | Cost | Auth |
|---|--------|-------|-------|------|------|
| 1 | `VAPIGamerControllerNFT` deploy | source exists, not deployed | mirror `deploy-vapi-operator-agent-nft.js` (deploy → `initialize(name,symbol)` → `configureMinter(bridge, N)`) | **~2.37 IOTX** (measured on the agent NFT — Hardhat under-estimates upgradeable ops ~3-4×; budget 3.0) | bridge wallet |
| 2 | "QorTroller Controllers" project | agents have a project; controllers need a **separate** one (1:1 project↔deviceContract) | `ProjectRegistry.register(name, 0)` — `agent_registration.register_project` precedent; yields a `projectTokenId` | ~0.2–0.4 IOTX (est.) | bridge wallet |
| 3 | `ioIDStore.setDeviceContract(projectTokenId, NFT)` | not done | one call, agent precedent | ~0.1–0.2 IOTX (est.) | project owner |
| 4 | mint controller tokenId | not done | `NFT.mint(gamer)` (bridge = configured minter); yields the `tokenId` the register call consumes | ~0.1 IOTX (est.) | minter |
| 5 | gamer EIP-712 permit + `register` | permit assembly wired (Inc-3); **real broadcast NOT wired + Option-A `device` arg is wrong** | the real gap — see below | ioID fee **~0.1 IOTX/device** (`ioIDStore.price()`; `applyIoIDs` optional — pay-as-you-go `value=price` also works) + gas | gamer wallet signs |

### The load-bearing code gap (inside #5) — BIGGER than "just send" (grok r01 F2)
Inc-3 shipped the honest `NotImplementedError` on non-dry-run, but grok's consult found the gap is more
than broadcast. Under Option A the register verifies `ecrecover(Permit_digest, v,r,s) == device`, so the
register's **`device` arg must be the GAMER EOA**, not the truncated `device_id_hex` the Inc-3 dry-run
assembles (`581a836c…`[-40:] is a fake ETH address → `ecrecover` fails). The physical Edge identity is
the **DID content + birth cert / VMDR**, not the `device` slot. Full deliverable:
1. Option-A register args: `device = gamer`, `user = msg.sender = gamer` (dev-self: bridge).
2. Real `device_contract` (deployed NFT) + minted `token_id` (not zeros).
3. Content hash = keccak of the DID **JSON** (agent style), not keccak of the CID string.
4. Real Pinata (the CLI still has `_StubPinata`).
5. `send_raw_transaction` + `value = price` (or a prepaid `applyIoIDs` balance).
6. Readback: ioID tokenId via `tokenOfOwnerByIndex` on the ioID contract, then `ioID.wallet(id)` — **never**
   equate the DeviceNFT tokenId with the ioID tokenId (an agent bug already fixed in step-7).

Precedent for the send: `operator_session_register_agents.py` `_submit_transaction` + step-7 readback +
receipt-status/gasLimit discipline. **Not a new invention.**

## Sequencing + total cost (corrected per grok r01)

Deploy NFT (1) + register project (2) [either order] → setDeviceContract (3) → mint tokenId (4) →
gamer-signed register (5). Deploy↔project can swap; hard constraints: both exist before
`setDeviceContract`; mint before register; mapping before register. **Total ~3.0–3.5 IOTX** (NFT ~2.4 +
project+map+mint ~0.5 + register ~0.1 fee + gas), operator-fired, against a 27.75 IOTX wallet.

## Honesty ceilings (grok r01 F4 — pin BEFORE any live ceremony)

**May claim:** testnet (4690) Edge `581a836c` registered as an **ioID device** with a gamer-controlled
permit; explorer tx + `ioID.wallet(tokenId)` TBA + resolvable DID CID; on-chain device key = gamer
secp256k1 (Option A); "gamer-sovereign controller identity path proven end-to-end (developer-self)."
**Must NOT claim:** third-party gamer onboarding (dev-self = the operator wallet); mainnet/production;
silicon-signed permit (the P-256 silicon is still external, linked via birth cert). **Over-claim traps:**
(1) marketing `did:io:{device_id}` as if the ioID `device` slot were the 32-byte canon id — the SYSTEM
identity is the gamer device **address** (agent pattern: Curator `did:io:0x7BdB…`); (2) "sovereign gamer"
without saying first-run = operator-as-gamer.

## Increment plan (grok r01 — 4 commits, one operator GO per spend)

| Inc | Name | Spend | Exit |
|-----|------|-------|------|
| **A** | `deploy-vapi-gamer-controller-nft.js` (estimate-first, explicit gasLimits, `status===1n`, write on success) | 0 default; ~2.4–3.0 IOTX on `--execute` | dry/estimate green; live owner/minter smoke |
| **B** | Option-A wire-up (NO chain): `device=gamer`, real NFT/tokenId, DID-JSON keccak content hash, ecrecover test | 0 | pytest green; dry-run stays honest until addresses supplied |
| **C** | `operator_session_register_controller.py`: project → setDeviceContract → (opt applyIoIDs) → mint(to=gamer); one step per invoke | ~0.4–0.7 IOTX | mapping + mint Transfer + allowance decrement |
| **D** | real register send: pin DID → permit → `register` value=price → `tokenOfOwnerByIndex` → `wallet` → real ids; triple-gate + `IOID_CONTROLLER_REGISTER_CONFIRM=1` | ~0.1 fee + gas (cap 0.75) | explorer status 1; non-zero TBA; DID CID resolvable |

**Never** merge an A spend with a D spend; **never** collapse C+D. A+B (no-spend) can share a PR.
grok's soft rec: build **Inc-A + Inc-B (no spend) soon**; fire spends only when the explorer artifact is
wanted. Consult transcript: `docs/a2a/ioid/round-01-grok-consult-ceremony-scope.txt`.

## Decision points (operator, before any build)

1. **Developer-self or real gamer?** First run = operator wallet as gamer (honest demo, like the WMP
   first bundle). *Recommend developer-self.*
2. **One controller or a batch?** `configureMinter` allowance = 1 (just `581a836c`) or N.
3. **Now or defer?** No dependency forces it — the interface is proven live (Inc-3). A "make the DePIN
   identity real end-to-end" milestone, not a blocker.

## Non-blocker (settled)

The old **D-IOID-P256** concern is moot: the gamer wallet signs secp256k1 (works with `ioIDRegistry`'s
EIP-712); the controller's P-256 silicon links via the now-HSM-VALID birth cert + VMDR. Option A
(gamer-signs) is the locked, working path — `VAPIGamerControllerNFT.sol` NatSpec confirms it.

## Empirical cost findings preserved (from the agent NFT deploy)

- Deploy upgradeable contract: ~2.17 IOTX; `initialize`: ~0.13; `configureMinter`: ~0.07 (Hardhat
  under-estimates ~3-4× on IoTeX for upgradeable ops — use explicit gasLimit overrides: init 500000,
  configureMinter 200000). Check `receipt.status === 1n` after each tx (a mined-but-reverted tx returns
  a receipt). `ioIDStore.price()` = **0.1 IOTX per device** (grok r01 F1 — my earlier "0.2/ioID" was
  2 agents × 0.1, not the unit price). `applyIoIDs(projectTokenId, N) {value: N × 0.1}` OPTIONALLY
  pre-pays; otherwise the register carries `value = price` (pay-as-you-go, the agent path's default).

## Recommendation

A clean, precedent-backed ceremony worth doing when the gamer-sovereign controller identity should be
*real* rather than *wired*. Next: grok forward-consult (pressure-test the sequence + the step-5 real-send
build), then build the deploy/ceremony scripts increment-by-increment (grok-verified, operator fires each
spend). No chain write / no spend in scope until the operator GOes.
