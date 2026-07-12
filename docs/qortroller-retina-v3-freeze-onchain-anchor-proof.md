# QorTroller - On-Chain Anchor: VAPI-RETINA-STATE-v3 FROZEN-v1 Freeze

**Claim proven:** the VAPI-RETINA-STATE-v3 governance freeze (TRA-1 T3; PV-CI 182->183) is
recorded **on-chain on IoTeX testnet** - third-party verifiable, reproducible from the committed
allowlist, no bridge or private access required.

**Result: PROVEN**  .  2026-07-12T22:09:46Z

| Field | Value |
|---|---|
| network | IoTeX testnet (chain ID 4690) |
| contract | AdjudicationRegistry `0x44CF981f46a52ADE56476Ce894255954a7776fb4` |
| deviceIdHash attribution | SHA-256(`VAPI_RETINA_STATE_V3_FREEZE_ANCHOR_v1`) |
| tx_hash | `0ecf2824e44feb9289f3be9db780d674c36ae96b37f7ade806ed74286094ec3b` |
| block | 45577740 . status 1 |
| freeze_commitment (isRecorded=True) | `a3697fe775204c6b90c4f43dc35bfae4536f7380bf8fe11624d51cc54992a7c8` |
| allowlist_hash (183 invariants) | `15f29d77f48b7a4c6fc3cf28eba0f1c8e61335bbbcb7e53c4e066e52fe04421e` |
| INV-RETINA-STATE-V3 digest | `b3e5cb6a65c275d8d99fb11fcc597dfa138c872c6544ad716c8c479d79fd23e2` |
| cost | **0.286230 IOTX** (testnet; hard cap 0.3) |
| wallet | `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692` |

## How a third party verifies (no bridge, no private access)
1. `compute_allowlist_hash()` over the committed `.github/INVARIANTS_ALLOWLIST.json` (183 entries) == allowlist_hash above.
2. `freeze_commitment = SHA-256(b"VAPI-RETINA-STATE-v3-FREEZE-v1" || allowlist_hash(32) || INV-RETINA-STATE-V3 digest(32))` == the value above.
3. `AdjudicationRegistry.isRecorded(freeze_commitment) == true` at the tx/block above (IoTeX testnet explorer / eth_call).

## Scope / honesty
Testnet (no real economic value); ONE bounded tx (~0.2862 IOTX, hard-capped 0.3); the kill-switch was lifted process-scoped only (bridge/.env stays paused; restart re-engages it). The CI-authoritative allowlist seal is independent of this anchor; this records tamper-evident on-chain provenance of the freeze via a general commitment registry (AdjudicationRegistry), not the coherence/governance-provenance path.
