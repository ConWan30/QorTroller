# LayerZero VHP Mainnet Activation Runbook — Phase 99C

**Authoring commit:** to-be-assigned (this commit)
**Ceremony status:** RUNBOOK-ONLY — implementation work pending
**Architecture anchor:** `e81e04aa` (Phase O4-VPM-INTEGRATION close)
**Forward vector:** v4 §15 tier #7 (LayerZero VHP cross-chain bridge mainnet path)

This runbook documents the path from the current testnet stub state of
`VAPIVerifiedHumanProofBridge.sol` (Phase 99C) to production mainnet
activation across IoTeX mainnet (chain ID 4689) ↔ Ethereum mainnet
(chain ID 1) via LayerZero V2 OApp.

**This is NOT a wallet-free ceremony.** This is a multi-step operator
workstream requiring:
- Production wallets on both IoTeX mainnet AND Ethereum mainnet
- LayerZero OApp implementation work (~600 LOC contract refactor)
- ZK ceremony for cross-chain VHP issuance (if scope expanded)
- Significant gas spend on both chains (~estimate below)

The agent's role on tier #4 is bounded to authoring this runbook +
shipping the stub-state audit that verifies the contract's
current-state assumptions. Mainnet activation is operator-authorized.

## Current state (HEAD `e2da3e6c`)

`contracts/contracts/VAPIVerifiedHumanProofBridge.sol` is a **stub** in
the following specific ways:

| Function | Current behavior | Production behavior required |
|---|---|---|
| `send(tokenId, dstEid, recipient, data)` | Emits `VHPSent` event only; no actual cross-chain send | Calls `lzEndpoint.send{value: msg.value}(MessagingParams{...})` with full ABI-encoded payload |
| `lzReceive(...)` | NOT IMPLEMENTED (contract receives nothing) | Mandatory for OApp inheritance: decode incoming payload, mint mirror VHP token on dstEid |
| Inheritance | `Ownable` only | Must inherit `OApp` from `@layerzerolabs/lz-evm-oapp-v2` package + override required hooks |
| `lzEndpoint` constructor arg | Pinned at construction, immutable | Same — but must point to the real LayerZero EndpointV2 address per chain |
| Anti-replay | `sentNonces[tokenId][dstEid]` (sender-side only) | Add `receivedNonces` mapping on the receiver side; reject `nonce <= lastReceived` |

**Testnet deployment status:** the contract is in the registry but
serves as a testbed for the event-emission interface only. No real
LayerZero messages have been sent.

## Mainnet activation prerequisites

### Pre-development gates

- [ ] **Separation gate cleared:** AIT N=37 ratio=1.199 is CLEARED for
      AIT testnet/demo eligibility; touchpad_corners 0.728 remains the
      blocker for tournament BLOCK enforcement. The token launch
      invariant ("no TGE before separation_ratio > 1.0 AND
      all_pairs_above_1=True") remains in force for all mainnet token
      operations including VHP cross-chain mint authority.
- [ ] **VAPIVerifiedHumanProof (VHP) production-issuance pipeline:**
      Phase 99C VHP mint requires:
      - L4 anomaly + continuity per-player thresholds
      - GIC chain integrity (currently GIC_100 anchored on testnet)
      - ZK ceremony verifier (CeremonyRegistry on IoTeX testnet
        only at this commit)
      Mainnet would require re-running the ceremony with mainnet
      contributors + new beacon block, OR formally bridging the
      testnet ceremony hash as an attestation.
- [ ] **Audit:** independent security audit of VAPIVerifiedHumanProof
      + VAPIVerifiedHumanProofBridge by a third party (NOT in scope
      for this protocol's solo-architect mode at testnet).

### Implementation gates

- [ ] Refactor `VAPIVerifiedHumanProofBridge.sol`:
      - Inherit `OApp` from `@layerzerolabs/lz-evm-oapp-v2`
      - Replace stub `send()` event with real `_lzSend` call
      - Implement `_lzReceive(Origin, bytes32, bytes, address, bytes)`
        - Decode payload (uint256 tokenId, address recipient, VHPData)
        - Call `VAPIVerifiedHumanProof.bridgeMint(tokenId, recipient, data)`
      - Add `MessagingFee` quote helper for off-chain cost estimation
      - Add receivedNonces mapping + replay guard
- [ ] Deploy mirror `VAPIVerifiedHumanProof` on Ethereum mainnet
      (contract becomes the "receive" side; needs `bridgeMint`
      function gated to `onlyBridge`)
- [ ] LayerZero endpoint addresses:
      - IoTeX mainnet:  TBD (verify via LayerZero V2 docs)
      - Ethereum mainnet: `0x1a44076050125825900e736c501f859c50fE728c`
        (LayerZero V2 EndpointV2 mainnet)
- [ ] dstEid mapping per LayerZero V2:
      - IoTeX mainnet eid:    TBD
      - Ethereum mainnet eid: 30101

### On-chain deploy gates

- [ ] **IoTeX mainnet wallet funded** with ≥10 IOTX for VHPBridge deploy
      + initial setPeer + buffer
- [ ] **Ethereum mainnet wallet funded** with ≥0.05 ETH for VHP receiver
      deploy + initial setPeer + buffer (current gas conditions; verify
      before fire)
- [ ] LayerZero V2 OApp permissions configured (no per-app credentials
      required for V2; endpoint-based)

### Operator-runtime activation

Once all gates above clear, the activation ceremony itself:

```powershell
# === On IoTeX mainnet wallet ===
$env:CHAIN_SUBMISSION_PAUSED_MAINNET = "false"  # separate kill-switch
$env:OPERATOR_VHP_MAINNET_AUTHORIZED = "true"

# 1. Deploy refactored VHPBridge on IoTeX mainnet
npx hardhat run scripts/deploy-vhp-bridge-mainnet.js --network iotex_mainnet
# Estimated cost: ~5 IOTX (contract size + endpoint binding)

# === On Ethereum mainnet wallet (separate session) ===
# 2. Deploy mirror VHP receiver
npx hardhat run scripts/deploy-vhp-receiver-mainnet.js --network ethereum
# Estimated cost: ~0.03 ETH (similar contract size; mainnet gas)

# === Back to IoTeX mainnet ===
# 3. setPeer(eid_eth=30101, ethereum_receiver_addr_padded)
$IOTEX_BRIDGE=0x...
$ETH_RECEIVER=0x...  # 20-byte right-padded to bytes32
npx hardhat run scripts/setpeer-iotex.js --network iotex_mainnet

# === On Ethereum ===
# 4. setPeer(eid_iotex, iotex_bridge_addr_padded)
npx hardhat run scripts/setpeer-ethereum.js --network ethereum

# 5. Test message: send a test VHP token tokenId=X to a test recipient
#    Quote fee first via the quote helper, then fire send() with msg.value
npx hardhat run scripts/test-vhp-bridge-send.js --network iotex_mainnet
# Estimated cost: ~0.5 IOTX (message gas + LayerZero relay fee)
```

## Cost projection

| Item | Chain | Estimate | Notes |
|---|---|---|---|
| VHPBridge deploy | IoTeX mainnet | ~5 IOTX | OApp contract larger than stub |
| Mirror VHP deploy | Ethereum mainnet | ~0.03 ETH | At current 20-30 gwei conditions |
| setPeer (IoTeX side) | IoTeX mainnet | ~0.02 IOTX | One tx |
| setPeer (Ethereum side) | Ethereum mainnet | ~0.002 ETH | One tx |
| First test send | IoTeX mainnet | ~0.5 IOTX | LayerZero relay fee dominant |
| **Total at fire** | | **~5.5 IOTX + ~0.035 ETH** | + buffer recommended 50% |

Current IoTeX testnet wallet ~15.03 IOTX — **mainnet wallets are
SEPARATE** and must be independently funded. The testnet wallet does
NOT carry to mainnet.

## Risk register

| Risk | Severity | Mitigation |
|---|---|---|
| LayerZero V2 endpoint address changes between testnet and mainnet | MEDIUM | Pin endpoint at construction; immutable post-deploy; verify against LayerZero docs at deploy time |
| Cross-chain replay attack via reordered nonces | HIGH | Both sender and receiver maintain monotonic nonce maps; receiver rejects `nonce <= lastReceived` |
| Mint authority on Ethereum mirror compromised | CRITICAL | `bridgeMint` gated to `onlyBridge` modifier checking msg.sender == VHPBridge address |
| VHP TTL drift between chains | MEDIUM | `expiresAt` is part of bridged payload + checked at receive time; expired tokens rejected by `bridgeMint` |
| Gas-griefing on receiver via large payload | LOW | VHPData struct is fixed-size (no variable-length fields); payload ABI-encoding is bounded |
| Mainnet TGE invariant violation | CRITICAL | Operator MUST verify separation_ratio > 1.0 AND all_pairs_above_1=True BEFORE any mainnet VHP issuance authority; tier-#4 ceremony does NOT bypass this gate |

## What this runbook does NOT authorize

- Does NOT lift the token-launch invariant — VHP bridge activation
  requires separation gate cleared first
- Does NOT replace the testnet VHP infrastructure — testnet remains
  operational for ongoing protocol development
- Does NOT authorize Ethereum mainnet deploy without separate
  three-factor authorization specific to that chain
- Does NOT remove the `_verify_p256_stub()` workaround in the
  W3bstream applet — that's a separate W3bstream applet-pipeline
  workstream (per the W3bstream audit at HEAD `e2da3e6c`)

## Validation surface

The script `scripts/layerzero_vhp_bridge_audit.py` (shipped this
commit) scans the contract source for the specific stub patterns
documented above + reports a readiness verdict:

  - `STUB`         — current state at HEAD `e2da3e6c`
  - `OAPP_WIRED`   — post-refactor; OApp inheritance + _lzSend implemented
  - `MAINNET_READY` — post-deploy on both chains + setPeer fired

The audit is wallet-free + read-only. Run via:

```bash
python scripts/layerzero_vhp_bridge_audit.py
```

## Forward-vector dependency

LayerZero VHP mainnet activation depends on:

1. Token launch invariant cleared (touchpad_corners corpus expansion —
   hardware-required, separate workstream)
2. VHP production-issuance pipeline locked (currently testnet-only)
3. Third-party security audit (recommended; not strictly required for
   testnet-only mainnet bridge)
4. Operator-funded mainnet wallets (IoTeX + Ethereum)
5. LayerZero V2 OApp Solidity refactor (~600 LOC; this commit does
   NOT ship this work — it documents requirements)

When all 5 clear, the operator may execute the ceremony per the
PowerShell commands above.

---

*— VAPI Architect, 2026-05-13*
