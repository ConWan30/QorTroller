# ② P4b (Composite Key / PoEP Commitment Registration) — Pre-Investigation Note

**Status:** Pre-implementation investigation (Phase B item ②). **Read-only; no code; no scope doc
yet.** HEAD `5524c70f` (PR#7) / `ffb7178d` (main). Held for operator review before a ② scope doc.
Protocol: investigation → **hold** → scope doc → V-check → hold → code + vectors → P-check → hold →
atomic commit.

**Goal of ②:** the production source of the device's **composite public key** (and PoEP
commitment), gamer-sovereign, on-chain — resolving #8's deferred **W-1** (today
`devices.pubkey_hex` holds only a single ECDSA key; the ③/#8 verifier needs the composite
ECDSA+PQ pubkey). ② is **stage 3 of the four-stage dormant-blind closure path**
(③ → #8 → **② P4b** → VBDIP-0006 → flip-on) and the concrete substance behind the IIP-64 PR #72
engagement (§4.6 device-identity).

---

## (a) Registry contract design space
**Template = `VAPIConsentRegistry.sol`** (the gamer-sovereign commitment-registration precedent —
same shape ② needs): `Ownable` + `ReentrancyGuard`; **gamer = `msg.sender`** writes, bridge READS
via view calls and never writes on the gamer's behalf (self-sovereignty); anti-replay hash set
(`_recordedHashes`); zero-hash guard; events for off-chain indexing (`ConsentGranted` w/
indexed gamer/category/hash); standalone-operable with an optional `ioidRegistry` reference.

**②'s registry (`VAPIPoEPRegistry.sol` — naming is Decision NAMING, see below):**
- **Storage:** `mapping(address gamer => mapping(bytes32 deviceId => Record))` where `Record =
  {bytes32 compositePubkeyHash, bytes32 poepCommitment, uint64 registeredAt, uint64 expiresAt,
  bool revoked}`. Anti-replay set over `compositePubkeyHash` / `poepCommitment`.
- **Methods (gamer msg.sender):** `registerDevice(deviceId, compositePubkeyHash, poepCommitment,
  expiresAt)`; `revokeDevice(deviceId)`; view `getRecord(gamer, deviceId)` /
  `getCompositePubkeyHash(gamer, deviceId)` / `isRegistrationValid(...)`.
- **Access control:** `Ownable` (deployer for admin like `setIoIDRegistry`), but registration is
  **permissionless gamer-sovereign** (any msg.sender registers their own device) — matches consent.
- **Events:** `DeviceRegistered(gamer, deviceId, compositePubkeyHash, poepCommitment, block)` — the
  full composite-pubkey BLOB is emitted in the event (see Decision STORAGE), not stored on-chain.
- **Upgrade/immutability:** non-upgradeable (matches all existing registries); a v2 contract if
  the schema changes. Composes with `VHPReenrollmentBadge` / `VAPIConsentRegistry` / ③'s renewal
  cadence (③ governs the lifetime of what ② registers).

## (b) Bridge handler scope — mostly READ (resolves #8 W-1)
**W1 invariant (bridge read-only on registry; msg.sender-signed txns only):** the bridge does NOT
submit registrations — the **gamer's wallet** signs `registerDevice` directly to the contract.
The bridge's role is **read**:
- `GET /operator/poep-registry/{device_id}` → view-call the registry for the composite-pubkey
  hash + the event-indexed blob; returns the `encode_pubkey` blob (operator_api pattern: doubled
  `/operator/` prefix + `_check_read_key`; Q1 handler pattern from #8 reused).
- **This read path IS the production `_device_pubkey_provider`** that #8's `_obtain_reattest_proof`
  consumes (W-1 seam) — when ② lands, #8's test-fixture injection becomes test-only and production
  reads the registered composite pubkey from chain (verified against the on-chain hash).
- Optional `GET /operator/poep-registry-status` (counts, latest) — read-only audit surface.
- A `chain.py` view wrapper `get_registered_composite_pubkey(gamer, device_id)` (read-only, like
  `chain.is_consent_valid`), fail-open (returns None when registry address unset — bridge readiness
  must not depend on deploy, per the CONSENT precedent).

## (c) SDK design
Mirror the existing Python SDK (`sdk/vapi_sdk.py`, OpenAPI-driven). Add: `VAPIPoEPRegistry` client
class — `build_register_tx(...)` (gamer-side, returns an unsigned tx for the gamer's wallet to sign;
the SDK never holds the gamer key) + `get_record(...)` / `get_composite_pubkey(...)` (read). Match
the existing result-dataclass + naming conventions (distinct Phase names per the SDK discipline).

## (d) Test surface (wallet-free for CI; on-chain parts Hardhat-local)
- **Contract unit tests** (Hardhat, local node): register/revoke/anti-replay/zero-hash/gamer-sovereign
  (a non-owner gamer can register; one gamer cannot register for another) — mirrors the consent
  registry test suite.
- **Bridge integration:** the read path (`get_registered_composite_pubkey`) with a mock chain +
  the #8 `_device_pubkey_provider` wired to it → end-to-end re-attestation through ③ with a
  REGISTERED (not injected) key. This is the W-1-resolution evidence.
- **SDK round-trip:** build_register_tx encodes correctly; get_record decodes.
- Wallet-free CI (mock chain); real on-chain registration is gamer-wallet-gated (see Decision WALLET).

## (e) Composite-key storage architecture
The `encode_pubkey` blob is **152–2058 bytes** (SLH-DSA-128s 152 / ML-DSA-44 1418 / ML-DSA-65 2058).
On-chain storage of multi-KB blobs is gas-expensive. **Pattern (Decision STORAGE, recommended):**
store only **`bytes32 compositePubkeyHash = SHA-256(encode_pubkey blob)`** on-chain; **emit the full
blob in the `DeviceRegistered` event** (event data ≫ cheaper than storage). The bridge read path
fetches the blob from the event log (or an off-chain index), verifies `SHA-256(blob) ==
on-chain hash`, then `decode_pubkey(blob)`. This mirrors the consent registry (stores `bytes32`
hashes only). On-chain stays cheap + verifiable; the bulky bytes live in events.

## (f) Scope-doc-time decisions to surface
- **Decision NAMING** — `VAPIPoEPRegistry.sol` vs `QORTROLLERPoEPRegistry.sol`. **All 70+ existing
  contracts are `VAPI`-prefixed** (VAPIConsentRegistry, VAPIVerifiedHumanProof, …); contract code
  identifiers are Layer-C VAPI technical references per QRESCE. **Lean: `VAPIPoEPRegistry`** (match
  the established convention) — but it registers QorTroller-era (QORTROLLER-POEP-v0 / IPACT)
  commitments, so a QorTroller-branded name is arguable. **Operator call** (cf. the FC-(a)
  namespace-separation precedent — though that was for byte-literal domain tags, not contract code
  identifiers; the brand guideline keeps code identifiers VAPI).
- **Decision STORAGE** — on-chain hash + event-emitted blob (recommended, §e) vs full blob on-chain.
- **Decision SCOPE** — ② registers (a) composite pubkey only, (b) PoEP commitment only, or **(c)
  both** (recommended — the composite pubkey resolves W-1/closure; the PoEP commitment is the P4b
  framing + the §4.6 device-identity artifact). Confirm.
- **Decision WALLET** — ②'s on-chain parts (contract deploy + gamer registration) are
  **wallet-gated** (real IOTX): deploy ~one-time operator cost; registration = gamer's own wallet.
  The bridge read path + SDK build-tx + all tests are **wallet-free**. Confirm the split (build
  wallet-free now; deploy/registration when wallet/operator timing permits — matches the Phase 99 /
  Phase 238 deploy posture).
- **Decision RENEWAL-LINK** — how ② registration interacts with ③'s renewal cadence: does a ③
  renewal commitment reference the ② registration record? (Lean: ③'s `device_id_32B` already keys
  both; ② adds the pubkey, ③ governs its renewal lifetime — no contract coupling needed in v1.)

## (g) Q2 (bridge operational state) — RESOLVED (carried from #8)
#8 established the testability story: core logic is unit/integration-testable without a live bridge
(mock chain + fake store + injected seams), HTTP E2E separate/optional. ②'s contract tests are
Hardhat-local; the bridge read path is mock-chain-testable. **No further Q2 resolution needed.**

## Honest scope boundary
② resolves W-1 (production composite-pubkey source) — stage 3 of closure. It does NOT by itself
close the dormant-blind gap: stage 4 (VBDIP-0006 device firmware signer, #11) + operator flip-on
remain. ② is wallet-gated for the on-chain parts; the wallet-free build (contract + bridge read +
SDK + tests) can land first, with deploy/registration gated on wallet/operator timing.

## Cross-refs
`contracts/contracts/VAPIConsentRegistry.sol` (template), `…/TieredDeviceRegistry.sol` /
`DeviceRegistry.sol` (device+pubkey precedent), `bridge/vapi_bridge/chain.py`
(`is_consent_valid`/`get_consent_record` view-call fail-open precedent), `bridge/vapi_bridge/store.py`
(`devices.pubkey_hex` single-ECDSA today), `l9_presence/composite_sig.py` (`encode_pubkey`/`decode_pubkey`
— what ② stores/serves), `bridge/vapi_bridge/vhp_renewal_agent.py` (#8 `_device_pubkey_provider`
seam ② fills). Memory: [[ipact-handshake-wiring-v1-shipped]], [[dormant-blind-closure-path]],
[[composite-sig-v1-shipped]], [[iip64-pr72-engagement]].
