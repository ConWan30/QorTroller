# A2A ioID-CEREMONY r03 — CLAUDE BUILD Inc-C (prereq-tx ceremony)

**Charter ruling (a):** Claude built; grok verifies before the operator's commit.
**Envelope:** inc-c-prereq-ceremony-r03
**Spend:** ZERO in this build. Every step is operator-fired later (estimate-first + triple-gate).

## What Inc-C is

`scripts/operator_session_register_controller.py` — the prerequisite transactions that make the
deployed `VAPIGamerControllerNFT` registerable as an ioID device, **one step per invoke** so each
spend is a separate explicit operator decision:

| subcommand | call | readback | cap |
|---|---|---|---|
| `register-project` | `ProjectRegistry.register("QorTroller Controllers", 0)` | `PROJECT_TOKEN_ID` from the IProject Transfer log | 0.75 |
| `set-device-contract --project-token-id N` | `ioIDStore.setDeviceContract(N, NFT)` | `deviceContractProject(NFT)==N` | 0.50 |
| `apply-ioids --project-token-id N --amount M` *(optional)* | `ioIDStore.applyIoIDs(N, M){value:M*price}` | — | 1.00 |
| `mint --to <gamer>` | `VAPIGamerControllerNFT.mint(gamer)` | `CONTROLLER_TOKEN_ID` from Transfer log + `balanceOf` delta | 0.50 |

Pure testable core in `bridge/vapi_bridge/controller_ceremony.py` (guards + constants + least-privilege
NFT ABI). System addresses + ABIs (`ProjectRegistry`/`ioIDStore`/`IProject`) **imported** from
`agent_registration` (canonical b94ad092) — never re-hardcoded.

## Design decisions

1. **Estimate-first + triple-gate**, mirroring `scripts/provision_device_mfg.py` verbatim:
   (1) caller == bridge wallet, (2) buffered cost <= per-step cap, (3) `--execute` AND
   `IOID_CONTROLLER_CEREMONY_CONFIRM=1`. Default = estimate-only STOP. `estimate_gas` doubles as the
   pre-send revert guard; `receipt.status != 1` exits nonzero.
2. **Fail-honest sequencing:** `assert_nft_deployed` raises with an Inc-A pointer if
   `VAPIGamerControllerNFT` isn't in deployed-addresses.json yet (it isn't — Inc-A unfired). `set-device-contract`
   preflights `deviceContractProject(NFT)` (already-mapped → no-op; mapped-elsewhere → refuse). `mint`
   preflights `isMinter(bridge)` + `minterAllowance>=1`.
3. **Unambiguous readback:** project + controller tokenIds parsed from the ERC-721 `Transfer(0x0→to,id)`
   log (topic0 pinned), never inferred from enumeration ordering (enumeration is only a labelled fallback).

## Verification done
- `bridge/tests/test_controller_ceremony.py` — **29 tests** green (guards, fail-honest Inc-A-unfired
  against the real deployed-addresses.json, ABI least-privilege, canonical Transfer topic).
- Sibling `test_controller_ioid_registration.py` 17 green (no regression). **PV-CI PASS 184.**
- CLI parses; guard trips (e.g. `--project-token-id 0`) fire BEFORE any RPC contact. Pure ASCII.

## Hammer questions for grok
- **V1 — spend posture:** any accidental-broadcast path? Is a per-step cap + confirm-env + `--execute`
  sufficient, or should register-project's cap account for a possible `ProjectRegistry.register` FEE
  (ABI is `payable`; I pass `value=0` — does IoTeX's ProjectRegistry require a msg.value? estimate_gas
  would revert-guard it, but confirm)?
- **V2 — readback correctness:** Transfer-log parse (`topics[2]`=to, `topics[3]`=tokenId); the
  `.hex()`-no-`0x` handling (the Inc-B F1 lesson) — is `_minted_token_id_from_logs` robust to both
  prefixed/bare topic encodings across web3.py versions?
- **V3 — mapping preflight:** already-mapped/mapped-elsewhere branches on `deviceContractProject` — correct
  and safe?
- **V4 — mint auth:** `isMinter`+`minterAllowance` preflight + `balanceOf` delta==1 — correct?
- **V5 — sequencing fail-honest:** NFT-deployed-before-map/mint + project-before-map — any gap where a
  step could half-run?
- **V6 — commit grain:** one commit for Inc-C (no-spend build)? Spends stay operator-fired (Inc-C run +
  Inc-D). Anything to split?

Files: `bridge/vapi_bridge/controller_ceremony.py`, `scripts/operator_session_register_controller.py`,
`bridge/tests/test_controller_ceremony.py`; precedents `scripts/provision_device_mfg.py`,
`bridge/vapi_bridge/agent_registration.py`; scope `docs/ioid-controller-ceremony-scope-2026-07-17.md`.
