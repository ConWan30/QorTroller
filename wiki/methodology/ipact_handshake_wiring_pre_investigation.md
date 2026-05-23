# iPACT Renewal Handshake Wiring — Pre-Investigation Note (Backlog #8)

**Status:** Pre-implementation investigation (Phase B backlog #8 — `ipact-renewal-handshake-wiring`).
**Read-only; no code; no scope doc yet.** HEAD `75f9e3fb` (feature) / `84a101bb` (main). Held for
operator review of these findings before a wiring scope doc. Protocol: investigation → **hold** →
scope doc → V-check → hold → code + vectors → P-check → hold → atomic commit.

**Goal of #8:** wire `VHPRenewalAgent._obtain_reattest_proof` (currently returns `None`) to actually
obtain a re-attestation proof: (a) bridge issues a fresh challenge, (b) the device composite-signs
it (①), (c) the bridge verifies + computes `reattest_proof = SHA-256(challenge_bytes ‖
composite_sig_bytes)` per ③ §2. This makes ③ the first real consumer of ① → the post-consumer
evidence that unlocks BOTH freeze ceremonies (#6 ①, and ③'s).

---

## (a) Current bridge challenge-issuance surface
There is **no general-purpose "issue a 32-byte CSPRNG challenge to a device for crypto-signing"
endpoint.** What exists:
- **`ChallengeSequencer`** (`bridge/controller/l6_trigger_driver.py:46`) — the L6 **haptic**
  challenge issuer: selects a random trigger profile + generates a **4-byte** anti-replay nonce.
  L6-specific (motor challenge, not crypto-sign), **default-OFF** (`L6_CHALLENGES_ENABLED=false`),
  4-byte nonce ≠ ③'s 32-byte CSPRNG requirement. **Not reusable as-is**, but it is the conceptual
  precedent (challenge + anti-replay nonce + response window).
- **HMAC auth nonces** (`NonceDedupTracker`, `nonce_tracker.check_and_register`, `x-nonce` header) —
  anti-replay for **agent auth**; these *consume/dedup* nonces, they don't *issue* device challenges.
  But `NonceDedupTracker` is the **right anti-replay primitive to reuse** for single-use challenge
  enforcement.
- **On-chain nonces** (`ioIDRegistry.nonces`, `chain._next_nonce`) — EVM permit/tx nonces; unrelated.

→ **The wiring ADDS a new challenge-issuance endpoint.** It becomes the **canonical pattern** for
device crypto-challenges (answers deferred-② **Q1**: the handler-extension pattern — see (d)).

## (b) Current device-side composite-sig signing path
**None exists in production.** `l9_presence/composite_sig.sign()` is only called from ①'s tests.
`composite_sig.sign(keypair, ctx, commitment)` needs the **device's private keys** (ECDSA-P256 +
ML-DSA/SLH-DSA). **The bridge does NOT and MUST NOT hold the device's PQ private key**
(gamer-sovereignty — INV-CONSENT-003 family). So the signer is **device-side**:
- **Production** signer = controller firmware / device SDK (VBDIP-0006 "at-source signing"
  territory) — **does not exist yet**; deferred.
- **v1 wiring** signer = **simulated** (the integration test holds a keypair and signs), exercising
  the *real* `composite_sig.sign`/`verify` code path through ③'s hook. This is the realistic v1 bar.

**Gap surfaced in ①:** `composite_sig.py` serializes *signatures* (`encode_composite`) but has **no
public-key serialization** (no `encode_pubkey`/`decode_pubkey`). The verifier (c) must reconstruct a
`CompositePublicKey` (ec_public + pq_public) from stored bytes → the wiring (or ②) needs a composite
**public-key wire format**. New work item, see Open Decisions.

## (c) Verifier integration
**Bridge-side, off-chain `composite_sig.verify` is the natural verifier** (the bridge holds the
device's *public* key and checks the composite-sig over the challenge). On-chain verify via the
`0x0B` precompile is **deferred** (IIP-64 Phase 1 / 2027 Q3) — NOT needed here.
- Mechanism: device signs with `commitment = nonce` (the 32-byte challenge *is* the 32-byte
  commitment slot ① already accepts) + a challenge `ctx` (e.g. `b"QORTROLLER-IPACT-RENEWAL-v1"`).
  Bridge calls `composite_sig.verify(device_composite_pubkey, ctx, nonce, sig)`; iff valid →
  `reattest_proof = ipact_renewal.compute_reattest_proof(nonce, sig)`. (③'s `compute_reattest_proof`
  only *hashes*; the **verify must happen first**, inside the wired `_obtain_reattest_proof`.)
- **Dependency surfaced — the device's composite pubkey source.** `devices.pubkey_hex` stores only
  the **single ECDSA-P256 PoAC key**; there is **no composite (ECDSA+PQ) pubkey storage**. Composite
  pubkey registration is **② P4b** (PoEP commitment / key registration). → see Open Decision W-1.
- **bridge↔l9_presence dependency:** importing `composite_sig.verify` pulls `quantcrypt` + `slh-dsa`
  + `cryptography` into the bridge runtime (currently `l9_presence/requirements.txt` only). The
  bridge IS launched from repo-root (`python -m bridge.vapi_bridge.main`), so `import
  l9_presence.composite_sig` resolves — but adding it to the always-on import path hard-requires the
  PQ libs. → see Open Decision W-3 (lazy import).

## (d) Q1 (handler pattern) + Q2 (bridge state) — pulled forward from the deferred ② investigation
- **Q1 — bridge handler-extension pattern.** New endpoints follow the `operator_api.py` convention:
  the doubled `/operator/...` prefix (per `feedback_operator_route_doubled_prefix`), `_check_key` /
  `_check_read_key` auth, rate-limit budget. The challenge-issuance endpoint is the **first device
  crypto-challenge endpoint** → its shape sets the canonical pattern future device challenges follow
  (and informs ②'s registration endpoints). Anti-replay via the existing `NonceDedupTracker`.
- **Q2 — bridge operational state.** Core wiring logic (challenge issue + verify + proof) is
  **unit/integration-testable WITHOUT a live bridge** (test the functions directly + the
  `_obtain_reattest_proof` path with an injected keypair + a fake store, exactly as ③'s agent tests
  did). Full HTTP E2E needs the bridge running; that is a separate, optional E2E test (kept out of
  the default CI suite, like the existing E2E gating).

## (e) Proposed wiring architecture (for operator review)
A **mechanism-complete, production-deferred** v1:
1. **New challenge-issuance endpoint** (operator_api pattern): issues a 32-byte CSPRNG nonce, stores
   it device-bound with a short TTL + single-use flag (reuse `NonceDedupTracker` semantics).
   Canonical device-crypto-challenge pattern (Q1).
2. **Composite public-key wire format** added to ① (`encode_pubkey`/`decode_pubkey`) — the minimal
   ① extension the verifier needs (closes the (b) gap). Byte-pinned + tested.
3. **Wire `_obtain_reattest_proof`**: request challenge → obtain device composite-sig (v1: pluggable
   signer; **simulated** in integration tests) → `composite_sig.verify` (lazy-imported) → on success
   `compute_reattest_proof(nonce, sig)`; on failure return `None` (fail-closed, unchanged).
4. **Integration test**: end-to-end through ③'s real renewal path with enforcement ON + a simulated
   device keypair → proves ① + ③ compose (the freeze-unlock evidence). Enforcement stays
   **DEFAULT-OFF** in config; the test flips it locally.
5. **Composite pubkey source** for production = **② P4b** (deferred); v1 injects/​configures a test
   key. Production flip-on still needs ② (registered keys) + a firmware/SDK signer (VBDIP-0006).

**Honest scope boundary:** this wiring produces **integration-test evidence** that ① and ③ compose
correctly through real `sign`/`verify` — which is the correct bar for the freeze ceremonies (freeze
is about wire-format/construction correctness being exercised, not production deployment). It does
**NOT** by itself enable production flip-on (that needs ② key registration + a real device signer).
The dormant-blind gap remains OPEN until production flip-on; #8 moves the option from "exists in
code" to "exercised + freeze-ready," not to "closed."

---

## Open decisions for the wiring scope doc (operator calls)
- **W-1 — composite pubkey source.** (a) pull ② P4b key-registration forward (scope creep; operator
  sequenced ② after) vs **(b, rec)** wire the mechanism + integration-test with an injected/test key;
  defer production key-source to ② P4b. (b) keeps the ordering and still unlocks the freeze ceremonies.
- **W-2 — device signer for v1.** Production firmware/SDK signer is VBDIP-0006/deferred. **Rec:** v1
  ships a **pluggable signer interface**, integration-tested with a simulated in-test signer; real
  firmware deferred. (Mirrors ③'s `_obtain_reattest_proof` being a hook.)
- **W-3 — bridge↔① dependency.** **Rec:** **lazy-import** `composite_sig` inside `_obtain_reattest_proof`
  (only when enforcement ON) so the bridge does not hard-require `quantcrypt`/`slh-dsa` for normal
  (enforcement-OFF) operation. Add them to bridge deps as **optional/enforcement-gated**.
- **W-4 — composite pubkey wire format (the ① gap).** Add `encode_pubkey`/`decode_pubkey` to ①
  (`l9_presence/composite_sig.py`). **Question:** does this ① extension land in #8's commit, or as a
  small ① follow-up before #8? (Rec: in #8's bundle, since #8 is the consumer that needs it — but it
  touches ①, so it must be re-validated and is relevant to ①'s freeze ceremony scope.)
- **W-5 — challenge `ctx` value.** What `ctx` does the device sign under? (Rec:
  `b"QORTROLLER-IPACT-RENEWAL-v1"` — binds the challenge to the renewal family; or a dedicated
  `b"QORTROLLER-IPACT-CHALLENGE-v1"`.) Lock in the scope doc.

## Cross-refs
`bridge/vapi_bridge/vhp_renewal_agent.py` (`_obtain_reattest_proof` hook), `bridge/vapi_bridge/ipact_renewal.py`
(`compute_reattest_proof`), `l9_presence/composite_sig.py` (① — needs pubkey wire format), `bridge/controller/l6_trigger_driver.py`
(`ChallengeSequencer` precedent), `bridge/vapi_bridge/operator_api.py` (handler pattern + `NonceDedupTracker`),
`bridge/vapi_bridge/store.py` (`devices.pubkey_hex` — single ECDSA key only). Memory:
[[ipact-renewal-cadence-v1-shipped]], [[composite-sig-v1-shipped]], [[operator-route-doubled-prefix]].
