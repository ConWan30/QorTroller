# VAPIPoEPRegistry (② P4b) — v1 Scope (DRAFT)

**Status:** DRAFT scope · Phase B item ② (P4b composite-key / PoEP-commitment registration) ·
**no code; no FROZEN-v1 tag pinned**. Pre-implementation V-check **APPROVED** (`vapi_validate_proposal`,
0 violations; lone warning = keyword-triggered TGE boilerplate, not about this design, 2026-05-23).
HEAD `5524c70f` (PR#7) / `ffb7178d` (main). Pre-investigation: `wiki/methodology/p4b_registry_pre_investigation.md`.

**Purpose.** A gamer-sovereign, on-chain registry of the device's **composite public key** (①
`encode_pubkey` blob) + **PoEP commitment**, keyed by `(gamer, deviceId)`. It is the **production
source** of the composite pubkey the ③/#8 re-attestation verifier needs — **resolving #8's W-1**
(today `devices.pubkey_hex` holds only a single ECDSA key). ② is **stage 3 of the four-stage
dormant-blind closure path** (③ ✅ → #8 ✅ → **② P4b (active)** → VBDIP-0006 #11 → flip-on) and the
concrete substance behind the IIP-64 PR #72 §4.6 application-layer credential carve-out.

---

## 0. Honesty rails (read first)
- **DRAFT scope.** Not frozen; subject to revision.
- **② resolves W-1, it does NOT close the dormant-blind gap.** After ②, two of three
  operator-internal closure stages are done; **#11 (VBDIP-0006 device firmware signer) + operator
  flip-on remain.** When ② lands, #8's test-fixture key-injection becomes **test-only** and
  production reads the registered composite pubkey from the registry. The gap stays OPEN until
  flip-on (a separate governance event).
- **② adds no new enforcement flag.** ③'s `ipact_renewal_enforcement_enabled` (default-OFF) remains
  the single enforcement gate; ② provides the production composite-key source the gate consumes when
  ON. After ② lands, flipping enforcement ON consumes registered keys instead of injected fixtures.
  ②'s own deployable surface (read endpoint, registration SDK) is simply *available* — not gated by
  any new flag.
- **WALLET-FREE / WALLET-GATED boundary (load-bearing — a future operator firing the deploy must
  know exactly what runs):**
  - **Wallet-free (lands FIRST commit, no IOTX):** `contracts/VAPIPoEPRegistry.sol` source +
    Hardhat unit tests; bridge read-path handler; SDK `build_register_tx` + `get_record`; integration
    tests vs local Hardhat / simulated chain; bridge `_device_pubkey_provider` wired to read the
    registry (test fixture stays for tests; production reads the registry).
  - **Wallet-gated (separate LATER commit, real IOTX, when wallet refills):** testnet **deploy** of
    `VAPIPoEPRegistry` via bridge wallet `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692`; address
    registration in `contracts/deployed-addresses.json`; live E2E vs the deployed contract.
- **No new FROZEN-v1 domain tag** introduced (§6). The registry STORES the existing
  `QORTROLLER-POEP-v0` commitment + ① composite pubkeys; it does not coin a new tag.
- **Novelty claim is conditional** (§8). First application-layer credential registry on IoTeX
  (concrete IIP-64 PR #72 substance), but absence-of-evidence rails apply.
- **Touches no FROZEN-v1 primitive** / 228-byte PoAC wire format / `SHA-256(raw[:164])` chain hash /
  ZK params / existing deployed contract / TGE gate. **Gamer-sovereignty preserved** — the gamer
  (`msg.sender`) registers; the bridge READS via view calls, never writes (W1).

## 1. Adoption & relationships
- **Template = `VAPIConsentRegistry.sol`** (the gamer-sovereign commitment-registration precedent):
  `Ownable` + `ReentrancyGuard`, `msg.sender` = gamer, anti-replay hash set, zero-hash guard,
  view-only bridge reads, events for off-chain indexing, optional `ioidRegistry` reference,
  standalone-operable. ② mirrors this structure exactly.
- **Resolves #8 W-1:** the bridge read path (§3) is the production `_device_pubkey_provider` that
  #8's `_obtain_reattest_proof` consumes. ② is what turns #8's integration-test evidence into a
  production-capable re-attestation verifier (still flip-on-gated).
- **One registry per family (design property, Decision SCOPE).** `VAPIPoEPRegistry` stores
  PoEP-specific data only. Other commitment families needing on-chain registration get their **own**
  registries (not a monolithic device-data store) — each focused, each with its own contract-surface
  PV-CI pins, each free to evolve independently.

## 2. Contract spec — `VAPIPoEPRegistry.sol`
**Naming (Decision NAMING → VAPIPoEPRegistry):** all 70+ existing contracts are `VAPI`-prefixed;
contract code identifiers persist as **Layer-C V.A.P.I.-category technical references** regardless of
the brand of the data they handle (the QRESCE operating mode). Parallel: `bridge/vapi_bridge/` holds
QorTroller-era agents (Guardian/Sentry/Curator) but the path stays VAPI-prefixed because the path is
Layer-C infrastructure. Same here — the registry is Layer-C infra; the PoEP commitments it stores are
QorTroller-branded. Breaking the convention for one contract would create code-identifier
inconsistency more disruptive than the brand-namespace mismatch.
**Event-namespace companion precision:** events emitted by the contract follow the **contract's**
namespace (VAPI-prefixed event signatures). QorTroller-branded data (`poepCommitment`, the
`QORTROLLER-POEP-v0` domain tag) lives **inside the event payload**, not in the signature.

```solidity
contract VAPIPoEPRegistry is Ownable, ReentrancyGuard {
    struct PoEPRecord {
        bytes32 compositePubkeyHash; // SHA-256(① encode_pubkey blob)   (Decision STORAGE)
        bytes32 poepCommitment;      // QORTROLLER-POEP-v0 SHA-256 commitment
        uint64  registeredAt;        // block.timestamp
        uint64  expiresAt;           // v1: ALWAYS 0 — reserved for v2 (FLAG A → Property X)
        bool    revoked;
    }
    mapping(address => mapping(bytes32 => PoEPRecord)) private _records; // gamer => deviceId => rec
    mapping(bytes32 => bool) private _recordedCommitments; // anti-replay on poepCommitment (EDIT 2, Option B)
    address public ioidRegistry;       // optional, like VAPIConsentRegistry
    uint256 public totalRegistrations; // lifetime

    event DeviceRegistered(
        address indexed gamer, bytes32 indexed deviceId,
        bytes32 indexed compositePubkeyHash, bytes32 poepCommitment,
        bytes   compositePubkeyBlob,   // NON-INDEXED: full ① encode_pubkey blob in event DATA
                                       // (event-sourced; not stored). The indexed compositePubkeyHash
                                       // provides on-chain integrity anchoring (EDIT 3).
        uint64  expiresAt, uint256 blockNumber);
    event DeviceRevoked(address indexed gamer, bytes32 indexed deviceId,
        bytes32 priorCompositePubkeyHash, uint256 blockNumber);

    // gamer msg.sender writes:
    function registerDevice(bytes32 deviceId, bytes calldata compositePubkeyBlob,
        bytes32 poepCommitment, uint64 expiresAt) external nonReentrant;
        //  computes compositePubkeyHash = sha256(compositePubkeyBlob) on-chain; zero-hash guard on
        //  the blob AND poepCommitment; anti-replay on poepCommitment; emits the full blob.
        //  (expiresAt accepted but v1 stores 0 — Property X.)
    function revokeDevice(bytes32 deviceId) external nonReentrant;
    // views (bridge read path):
    function getRecord(address gamer, bytes32 deviceId) external view returns (PoEPRecord memory);
    function getCompositePubkeyHash(address gamer, bytes32 deviceId) external view returns (bytes32);
    function isRegistrationValid(address gamer, bytes32 deviceId) external view returns (bool);
        //  v1: returns (record exists AND !revoked) — NO expiry check (Property X; ③ is the
        //  sole lifetime authority via its renewal cadence).
    function isRecorded(bytes32 poepCommitment) external view returns (bool);
    function setIoIDRegistry(address newRegistry) external onlyOwner;
}
```
- **Storage (Decision STORAGE):** on-chain stores **`bytes32 compositePubkeyHash` only**; the full
  152–2058-byte `encode_pubkey` blob is **emitted NON-INDEXED in `DeviceRegistered`** (event data ≫
  cheaper than SSTORE; mirrors the consent registry's bytes32-only storage). `deviceId` =
  `device_id_to_bytes32` (the CONSENT/③ convention — Decision RENEWAL-LINK).
- **Anti-replay (EDIT 2 → Option B, on `poepCommitment`).** Mirrors VAPIConsentRegistry verbatim
  (which records `consentHash`). **Option A (global composite-pubkey uniqueness) is REJECTED:** a
  composite *public* key is public by definition, so global pubkey-uniqueness creates a
  **front-running grief vector** (an attacker who observes a gamer's public key registers it first,
  locking the legitimate owner out). The consent registry avoids this because `consentHash` is a
  commitment, not public; `poepCommitment` is likewise a commitment (not trivially public) →
  recording it is safe. The composite pubkey itself is stored per-`(gamer, deviceId)` and
  re-registration overwrites the gamer's own record (no cross-account collision).
- **expiresAt (FLAG A → Property X):** the registry is **renewal-agnostic** — `expiresAt` is v1-vestigial
  (always 0; reserved for a v2 if a registry-level expiry distinct from ③'s cadence is ever justified).
  ③ is the sole lifetime authority; `isRegistrationValid` checks only `!revoked`. This is the cleanest
  separation: ② = "is this key registered for this gamer/device," ③ = "is this credential valid this epoch."
- **CEI / zero-hash:** mirror VAPIConsentRegistry verbatim (state before emit; zero-hash guard on the
  blob hash + poepCommitment).

## 3. Bridge handler design (READ-only; W1)
- `bridge/vapi_bridge/poep_registry_handler.py` (NEW) + `chain.get_registered_composite_pubkey(
  gamer, device_id)` view wrapper, **fail-open** (returns None when `poep_registry_address == ""` —
  bridge readiness must not depend on deploy, per the CONSENT `is_consent_valid` precedent).
- `GET /operator/poep-registry/{device_id}` (operator_api pattern: doubled `/operator/` prefix +
  `_check_read_key`; Q1 from #8) → returns the composite pubkey blob + validity.
- **INTEGRITY-CHECK STEP (Decision STORAGE companion precision — load-bearing):** the handler
  retrieves the full `compositePubkeyBlob` from the **event log** (event-sourced) and MUST verify
  **`SHA-256(retrieved_blob) == on-chain compositePubkeyHash`** (a fresh `getCompositePubkeyHash`
  view call) **before trusting/returning the blob**. This integrity check is the boundary that makes
  event-sourced storage trustworthy (events are not tamper-evident on their own; the on-chain hash
  is the anchor). A mismatch → reject (treat as no registered key → fail-closed).
- **Two-RPC-call integrity pattern (companion precision — do NOT merge into one):** the check is
  **(1)** fetch the event log carrying `compositePubkeyBlob`, **(2)** call `getCompositePubkeyHash(
  gamer, deviceId)` (view). The handler computes `SHA-256(retrieved_blob)` and compares to the
  view-call result. Merging the two — or trusting the event blob without the view-call comparison —
  would forfeit the integrity guarantee (the event blob alone is not tamper-evident).
- **#8 W-1 wiring:** the production `_device_pubkey_provider(device_id)` calls this handler →
  returns the verified `encode_pubkey` blob → #8's `_obtain_reattest_proof` `decode_pubkey`s it.
  The bridge NEVER submits `registerDevice` (gamer wallet signs); the bridge only reads.

## 4. SDK + implementation file list
- `sdk/vapi_sdk.py` — `VAPIPoEPRegistry` client: `build_register_tx(device_id, compositePubkeyBlob,
  poepCommitment, expiresAt)` + `get_record` / `get_composite_pubkey` (read). Match existing SDK
  result-dataclass + Phase-naming. **SDK no-key-handling property (auditable; capture verbatim in the
  `build_register_tx` docstring):** *"build_register_tx returns an unsigned transaction object
  containing calldata + suggested gas + nonce; the caller (gamer's wallet) is responsible for signing.
  The SDK never holds, accepts, or proxies private keys."* This makes the gamer-sovereignty / W1
  posture structurally auditable at the SDK layer (no signing path exists in the SDK).
- **Wallet-free bundle (first commit):** `contracts/contracts/VAPIPoEPRegistry.sol` ·
  `contracts/test/VAPIPoEPRegistry.test.js` (Hardhat) · `bridge/vapi_bridge/poep_registry_handler.py`
  · `chain.py` view wrapper · `operator_api.py` read endpoint · `vhp_renewal_agent.py`
  `_device_pubkey_provider` production wiring · `sdk/vapi_sdk.py` methods · `bridge/tests/` +
  `sdk/tests/` + this scope doc + pre-investigation note.
- **Wallet-gated bundle (later commit):** deploy script run + `deployed-addresses.json` entry +
  `POEP_REGISTRY_ADDRESS` in `.env` + live E2E.
- **Production + test path coexistence (EDIT 4):** ②'s production wiring reads from the registry
  (`_device_pubkey_provider` → `poep_registry_handler`); #8's test-fixture path **remains** for
  unit-test isolation, behind the same **Option B module-separation guard** (fixture in
  `bridge/tests/fixtures/`, never imported by `bridge/vapi_bridge/`). The constructor-injection seam
  supports both: tests override it with the injected key; production reads the registry. ② does NOT
  delete the fixture — both paths exercise the same downstream verifier, differing only in the key source.

## 5. Test plan
- (a) **Contract unit (Hardhat):** register / revoke / anti-replay (same hash twice rejected,
  cross-gamer front-run blocked) / zero-hash guard / **gamer-sovereign** (a non-owner gamer registers
  their own device; gamer A cannot register for gamer B) / event emits the full blob / `isRegistrationValid`
  expiry+revoke logic. Mirrors the consent-registry suite.
- (b) **Bridge read-path integration:** `get_registered_composite_pubkey` against a mock chain +
  the **integrity check** (tampered event blob whose SHA-256 ≠ on-chain hash → rejected).
- (c) **#8 W-1 resolution (the load-bearing test):** `_device_pubkey_provider` wired to the registry
  read path → a re-attestation through ③'s real renewal path verifies against a **registered** (not
  injected) composite pubkey → commitment chain advances `enforced=1`. Test-fixture path remains for
  unit tests; this proves the production source works.
- (d) **SDK round-trip:** `build_register_tx` encodes the calldata correctly; `get_record` decodes.
  Plus an SDK no-key-handling assertion: `build_register_tx` returns an unsigned tx and the SDK
  exposes no signing/private-key surface (the auditable W1 property).
- (e) **Integrity-check failure mode (explicit fail-closed, EDIT 5):** a tampered event blob whose
  `SHA-256` ≠ the on-chain `compositePubkeyHash` → the handler **returns None (fail-closed); no
  exception leaked**; downstream `_obtain_reattest_proof` treats it as no-pubkey-available → renewal
  skipped. (Strengthens §5(b) with the explicit return-None assertion on the fail branch.)
- Wallet-free CI throughout (Hardhat-local + mock chain); live on-chain E2E is the wallet-gated commit.

## 6. Reservation status
**N/A for a domain tag** — ② is contract + handler code, not a new tagged FROZEN-v1 primitive. No
entry to `_PATTERN_017_FROZEN_TAGS` / `_KNOWN_CAPABILITY_TAGS`. The `VAPIPoEPRegistry` **contract
surface** (storage layout, event schema, the integrity-check invariant) earns PV-CI invariants in a
later step; the deployed **address** is pinned in `deployed-addresses.json` at the wallet-gated
deploy (standard contract-address pinning, like the other 49 live contracts).

## 7. Alignment checklist
| Check | Reference | Status |
|---|---|---|
| Gamer-sovereign registration (msg.sender writes, bridge reads) | VAPIConsentRegistry precedent / W1 | ALIGNED |
| Ownable + ReentrancyGuard + anti-replay + zero-hash | VAPIConsentRegistry pattern | ALIGNED |
| Application-layer credential carve-out | IIP-64 §4.6 / PR #72 engagement | ALIGNED (this is the concrete instance) |
| Resolves #8 W-1 (production composite-pubkey source) | #8 wiring scope | ALIGNED (read path = `_device_pubkey_provider`) |
| Event-sourced blob + on-chain hash integrity check | Decision STORAGE companion | ALIGNED (handler verifies before trust) |
| device_id_to_bytes32 shared with ③ / CONSENT | Decision RENEWAL-LINK | ALIGNED (shared id, no contract coupling) |
| One registry per family | Decision SCOPE companion | ALIGNED (PoEP-only; not monolithic) |
| No change to existing frozen contracts / PoAC / chain hash / ZK / TGE | hard rules | ALIGNED |

## 8. Novelty claim (conditional)
**Claim:** no *known* public production deployment of a **gamer-sovereign on-chain registry of
device-bound hybrid (ECDSA+PQ) composite public keys for application-layer credential attestation,
event-sourced with on-chain hash integrity anchoring**. Each ingredient (key registries, event
sourcing, hybrid keys) has prior art; the *composition* for app-layer device credentials does not, to
our knowledge. **Conditional** — internal corpus + IIP-64/PoEP assessment; absence ≠ evidence of
absence; USPTO+EPO before any external/IP claim. This is the **first application-layer credential
registry on IoTeX** — concrete IIP-64 PR #72 substance.

---

## Resolved decisions (2026-05-23)
- **NAMING** → `VAPIPoEPRegistry` (Layer-C VAPI contract convention; QorTroller data in event payload).
- **WALLET** → wallet-free build first (contract+tests+bridge-read+SDK); deploy/registration/E2E = later wallet-gated commit.
- **STORAGE** → on-chain `bytes32 SHA-256(blob)` + full blob in event; handler verifies hash before trust (two-RPC-call pattern).
- **SCOPE** → composite pubkey + PoEP commitment per `(gamer, deviceId)`; one registry per family.
- **RENEWAL-LINK** → shared `device_id_32B`; no contract-level coupling to ③ in v1.
- **FLAG A → Property X** (renewal-agnostic registry): `expiresAt` v1-vestigial (always 0; v2-reserved); `isRegistrationValid` checks only `!revoked`; ③ is the sole lifetime authority.
- **EDIT 2 → Option B** (anti-replay on `poepCommitment`, matching consent): Option A pubkey-global-uniqueness REJECTED — composite pubkeys are public → global uniqueness is a front-running grief vector.
- **EDITS 1/3/4/5 + §3 two-call precision** applied (enforcement-framing, non-indexed-blob comment, prod+test coexistence, explicit fail-closed test, two-RPC integrity pattern).

## Provenance
Pre-investigation (done) → hold (done) → scope doc (this file) → V-check → **hold** → code + vectors
→ P-check → hold → atomic commit (wallet-free bundle). Wallet-gated deploy is a separate later
commit. Four-stage closure: ③ ✅ → #8 ✅ → ② (this) → #11 → flip-on.
