# Node birth + first anchored contribution — 2026-07-13

**The DEPIN-1 program's live completion: QorTroller node #1 was born and put its first verifiable
contribution on IoTeX — all through the product path, operator-fired at the only spend.**

## The birth ceremony (Path A Proof Drill)
- Stage 4: the REGISTERED DualSense Edge (054C:0DF2) found + operator-acked — the ceremony
  correctly REFUSED a standard DualSense (0CE6) plugged in first (identity strictness proven live:
  the birth binds only the on-chain-registered device, VMDR tx `0x68f6cf49`).
- Proof Drill `proof_drill_20260713_1843`: ~90s scripted session → auto-stop → receipt (PoSP
  **SYNCHRONIZED** even in the drill; v3 present n=10; KAS HYGIENE_FAIL rendered AS-IS — honest
  verdicts pass the birth).
- **`node_id = 01a574e7ca7f…`** (domain `QORTROLLER-NODE-v0`, DERIVED from device_id `581a836c…` +
  first_session_id; not minted, not on-chain — the device is).

## The first ledger contribution (the 17-kill match)
- The ledger REFUSED the pre-birth scorecard (node_id null) — honest rail; re-scored post-birth
  (same match, same operator-reported 17) → entry #000:
  `entry_hash 146a649041c3fef1…`, posp=SYNCHRONIZED, w3s_attested=False (mechanical only), chain INTACT.

## The anchor (operator-fired, triple-gated + authorization gate)
```
tx     0xb985f035ab24819d0513325c253683b02c0b8fe784ccdefa1995fc84b1440eb6
block  45613440 · status 1 · to AdjudicationRegistry 0x44CF981f46a52ADE…
cost   0.143115 IOTX measured (est 0.1789, cap 0.5) · wallet 28.584589 → 28.441474 IOTX (eth_getBalance)
```
- Fired BY THE OPERATOR in their own PowerShell (agent execution was declined — the "chain writes
  are operator-fired" rail held down to the human finger). Gates crossed: process-scoped
  `CHAIN_SUBMISSION_PAUSED=false` + `NODE_LEDGER_ANCHOR_AUTHORIZED=true` + `--execute --confirm` +
  hard cap + estimate_gas revert guard.
- Ledger flipped PENDING → **ANCHORED** only after the real receipt; `entry_hash` unchanged (anchor
  fields deliberately outside the preimage). Independently re-verified via `eth_getTransactionReceipt`.

## What now exists
A gamer's node with: an identity derived from an on-chain-registered controller · a tamper-evident
local contribution ledger · its first entry (a real 17-kill match, PoSP SYNCHRONIZED, ~17/17
witnessed kills) anchored on IoTeX testnet — re-verifiable by any stranger from the tx hash + the
committed artifacts. `bridge/.env` kill-switch untouched (process-scoped lifts only).
