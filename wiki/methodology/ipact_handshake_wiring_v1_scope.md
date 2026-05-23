# iPACT Renewal Handshake Wiring — v1 Scope (DRAFT)

**Status:** DRAFT scope · Phase B backlog #8 (`ipact-renewal-handshake-wiring`) · **no code, no
FROZEN-v1 tag pinned**. Pre-implementation V-check **APPROVED** (`vapi_validate_proposal`, 0
violations; lone warning = keyword-triggered TGE boilerplate, not about this design, 2026-05-23;
§2.2 byte-precision added post-V-check is a refinement of the already-validated capability
extension, non-material to invariants). HEAD `75f9e3fb` (feature) / `84a101bb` (main).
Pre-investigation: `wiki/methodology/ipact_handshake_wiring_pre_investigation.md`.

**Purpose.** Wire `VHPRenewalAgent._obtain_reattest_proof` (today returns `None`) to a real
challenge↔sign↔verify loop: the bridge issues a fresh challenge, the device composite-signs it (①),
the bridge verifies and computes `reattest_proof = SHA-256(challenge_bytes ‖ composite_sig_bytes)`
per ③ §2. This makes **③ the first real consumer of ①**, producing the integration-test evidence
that **unlocks the ① (#6) and ③ (#10) freeze ceremonies**.

---

## 0. Honesty rails (read first)
- **DRAFT scope.** Not frozen; subject to revision before any freeze ceremony.
- **#8 unlocks FREEZE-READINESS, it does NOT close the dormant-blind gap.** Closure is a
  **four-stage path** (corrected protocol fact): **③ landed (option) → #8 wiring (freeze-readiness)
  → ② P4b composite-key registration → VBDIP-0006 device firmware signer → operator flip-on.** #8
  produces *integration-test* evidence that ①+③ compose (the correct freeze bar); it does NOT enable
  production flip-on (that needs ②'s registered keys + a real device signer). The gap stays **OPEN**
  until flip-on, which is itself a separate governance event. This doc must never be read as "#8
  closed the gap."
- **TEST-KEY-MUST-BE-TEST-ONLY (load-bearing security constraint).** v1 injects a composite keypair
  for integration testing (W-1). That injection **MUST NOT be reachable from a production deployment**
  — if it were, it would be a **credential-spoofing vector** (anyone could mint a valid re-attestation).
  Enforcement: the test key lives **only in test fixtures**, never in the production agent code path;
  the production `_obtain_reattest_proof` path has **no branch** that reads an injected/static key.
  The pluggable signer seam (W-2) is overridden **only** by tests (monkeypatch/subclass), never by a
  runtime config flag. See §4.
- **No FROZEN-v1 tag pinned this step.** #8 touches ① (adds a pubkey wire format — a **v1.1
  capability extension**, not a spec change) and ③ (wires the hook). Neither ①'s nor ③'s freeze
  ceremony happens here; both become *defensible* after #8's integration evidence lands.
- **Novelty claim is conditional** (§8).
- **Touches no FROZEN-v1 primitive** / 228-byte PoAC wire format / `SHA-256(raw[:164])` chain hash /
  ZK params / deployed contract / TGE gate. `renew_vhp` stays kill-switch-gated. Gamer-sovereignty
  preserved — the **device** signs; the bridge issues the challenge + verifies, never signs.

## 1. Adoption & binding language
The wiring adopts a **challenge-response re-attestation** protocol over ①'s composite signature:
- **Challenge** = a bridge-issued 32-byte CSPRNG nonce, single-use, device-bound, short-TTL.
- **Response** = the device's ① composite-sig over the challenge (`commitment = nonce`, signed under
  a dedicated challenge domain tag, §2/W-5).
- **Proof** = `reattest_proof = SHA-256(challenge_bytes ‖ composite_sig_bytes)` per ③ §2, computed
  **only after** the bridge verifies the composite-sig via `composite_sig.verify`.
- **AND over ①'s AND-composition:** the response is valid iff ①'s composite verifies (both ECDSA and
  PQ halves) AND the challenge is fresh/single-use/unexpired. No fallback.

## 2. Wire formats
### 2.1 Challenge endpoint
New endpoint issues `{challenge_id, nonce_hex (32B), expires_at, device_id}`. The nonce is
`secrets.token_bytes(32)`. Single-use + TTL enforced via the existing `NonceDedupTracker` semantics
(`bridge/vapi_bridge/operator_api.py`). Handler follows the operator_api pattern (Q1, §7).

### 2.2 Composite public-key wire format (① v1.1 extension — W-4) — BYTE-PINNED
`l9_presence/composite_sig.py` gains `encode_pubkey` / `decode_pubkey` (the verifier reconstructs a
`CompositePublicKey` from stored bytes — ① v1 serializes *signatures* only). All field sizes below
are **empirically verified against the live backends 2026-05-23** (cryptography 46 / quantcrypt 1.0.1
PQClean / slh-dsa 0.2.2), the same discipline as ①'s signature wire format.

**Envelope (length-prefixed, self-describing — mirrors `encode_composite` exactly):**
```
pubkey_blob = version(1)            # 0x01
            || label_len(1) || label            # ASCII tier Label (COMPSIG-…); selects PQ backend on decode
            || ec_len(2, BE) || ec_point        # ec_len == 65; ec_point = SEC1 uncompressed
            || pq_len(4, BE) || pq_pubkey_raw    # pq_len per tier (1952 / 1312 / 32)
```
Explicit length prefixes (not implicit per-algorithm lengths) — gives the same self-describing,
width-validated framing as the signature blob; the **Label** tells `decode_pubkey` which backend to
reconstruct. `decode_pubkey` rejects truncation / trailing bytes / unknown version / unknown label /
wrong-width fields (same `decode_composite` discipline).

**1. ECDSA-P256 half — `ec_point` = SEC1 UNCOMPRESSED point, 65 bytes** = `0x04 || X(32) || Y(32)`
(`cryptography` `public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)`). **Why uncompressed
(not 33-byte compressed):** the verifier reconstructs on every renewal; uncompressed avoids a
point-decompression step + matches the existing PoAC/on-chain uncompressed convention. Pubkeys are
stored once, so the 32-byte size saving of compressed is not the binding constraint. `ec_len` is
still emitted (==65) for envelope uniformity + width validation.

**2. ML-DSA half — `pq_pubkey_raw` = raw FIPS-204 public key bytes**, length per tier:
   - ML-DSA-65 → **1952 bytes** (FIPS 204) · ML-DSA-44 → **1312 bytes** (FIPS 204).
   - quantcrypt's `keygen()` returns the public key as a raw `bytes` object already in the FIPS-204
     byte encoding — stored verbatim; no byte-order transform. `decode_pubkey` passes it straight to
     `MLDSA_44/65().verify(...)`.

**3. SLH-DSA-128s half — `pq_pubkey_raw` = raw FIPS-205 public key, 32 bytes, FIPS-205-aligned**.
The `slh-dsa` lib exposes the public key as a **2-tuple of two 16-byte halves**, and **tuple order ==
`(PK.seed, PK.root)`** — i.e. `key[0] = pk_seed16`, `key[1] = pk_root16`. `encode_pubkey` concatenates
`key[0] || key[1]` → 32 B, which is **FIPS 205 §10 canonical `pk = PK.seed || PK.root`** (seed first).
`decode_pubkey` reconstructs via `slhdsa.PublicKey((raw[:16], raw[16:]), sha2_128s)`.
**Tuple order verified 2026-05-23 two ways:** (i) source — `SecretKey.pubkey()` builds
`PublicKey((sk.key[2], sk.key[3]))` and FIPS 205 secret key is `SK = (SK.seed, SK.prf, PK.seed,
PK.root)` → `[2]=PK.seed, [3]=PK.root`; `PublicKey.digest() == key[0]||key[1]`; (ii) empirical — a
NIST ACVP SLH-DSA-SHA2-128s `pk` (which is FIPS canonical `seed||root`) split as `raw[:16]||raw[16:]`
and fed as `PublicKey((seed, root))` verifies True. **The wire bytes are therefore interoperable with
any FIPS-205 implementation** (future `0x0B` precompile, external auditor, IETF LAMPS submission) —
not library-specific tuple order.

**Byte-pinned KATs** for `decode_pubkey(encode_pubkey(pk)) == pk` per pairing + the exact blob hex,
plus malformed-blob rejection (§5a). **This is a capability extension — ①'s M' construction, tier
table, OID provenance, and divergence statements all remain UNTOUCHED** (documented in ①'s scope as a
v1.1 paragraph, W-4).

### 2.3 Challenge domain tag (W-5)
Dedicated tag **`b"QORTROLLER-IPACT-CHALLENGE-v1"`** — used as the ① `ctx` the device signs under,
**NOT** the family tag `b"QORTROLLER-IPACT-RENEWAL-v1"`. **Why dedicated-vs-family:** the family tag
identifies the *commitment family*; the challenge tag identifies the *protocol step*. Distinct domain
separation prevents **cross-protocol signature-reuse attacks** (a signature gathered for a renewal
commitment cannot be replayed as a challenge response, or vice versa). Width-asserted at module
import per ①'s pattern.

## 3. Components
1. **Challenge issuer** — endpoint + nonce store (NonceDedupTracker-backed single-use + TTL).
2. **Pluggable signer seam** (W-2) — the device-side signer behind `_obtain_reattest_proof`. v1: a
   **test-fixture signer** exercising real `composite_sig.sign`; production: VBDIP-0006 firmware/SDK
   (deferred). The seam (hook signature) is stable; the signer is replaceable.
3. **Verifier** — bridge-side `composite_sig.verify(device_pubkey, ctx, nonce, sig)` (off-chain;
   `0x0B` precompile deferred). Lazy-imported (W-3).
4. **Proof computer** — `ipact_renewal.compute_reattest_proof(nonce, sig)` (③, already shipped),
   called only on successful verify.
5. **① v1.1 pubkey wire format** — `encode_pubkey`/`decode_pubkey` (§2.2).

## 4. Implementation reference
- **`l9_presence/composite_sig.py`** — add `encode_pubkey`/`decode_pubkey` (§2.2). No change to
  existing functions.
- **`bridge/vapi_bridge/ipact_challenge.py`** (NEW, or operator_api block) — challenge issuance +
  `b"QORTROLLER-IPACT-CHALLENGE-v1"` tag + nonce store.
- **`bridge/vapi_bridge/operator_api.py`** — new challenge endpoint (doubled `/operator/` prefix +
  `_check_key` auth + NonceDedupTracker), Q1 pattern.
- **`bridge/vapi_bridge/vhp_renewal_agent.py`** — wire `_obtain_reattest_proof`: request challenge →
  signer-seam produces composite-sig → **lazy-import** `composite_sig` → `verify` → on success
  `compute_reattest_proof`; on any failure return `None` (fail-closed, unchanged). **Lazy-import
  discipline (W-3):** `composite_sig` is imported *inside* the method, reached only when enforcement
  is ON — the bridge does not hard-require `quantcrypt`/`slh-dsa` for enforcement-OFF operation.
- **`bridge/requirements-enforcement.txt`** (NEW, W-3) — `quantcrypt==1.0.1`, `slh-dsa==0.2.2`,
  `cryptography>=46`; installed only for enforcement-ON deployments. Bridge startup unaffected otherwise.
- **`bridge/tests/fixtures/ipact_signer_fixture.py`** (NEW, EDIT 2) — the test-fixture composite
  signer (holds a test keypair, produces a real `composite_sig.sign` blob); imported **only** by
  tests, never by `bridge/vapi_bridge/`.
- **TEST-KEY isolation (§0 constraint):** the injected composite keypair exists **only** in
  `bridge/tests/` fixtures. The production `_obtain_reattest_proof` has **no static/injected-key
  branch**; the signer seam is overridden only by test monkeypatch/subclass.

**Structural guard for test-key isolation (EDIT 2 — Option B: module separation + injection-only seam).**
The §5(f) runtime check is defense-in-depth; the **primary** line of defense is structural, so an
injected-key branch is *hard to introduce*, not merely *detected after the fact*:
1. **Module separation.** The test-fixture composite signer lives in `bridge/tests/fixtures/ipact_signer_fixture.py`
   and is imported **only** by tests. **No `bridge/vapi_bridge/` module imports it** — enforced by a
   static guard (a grep-style assertion in the test suite + the convention that `vapi_bridge` never
   imports from `bridge/tests/`). A production import of the fixture would be visible immediately.
2. **Injection-only seam.** The signer is a **constructor-injected optional callable** with the type
   `Optional[Callable[[bytes], bytes]]` (`challenge_bytes -> composite_sig_blob`), defaulting to
   `None`. The production `VHPRenewalAgent` is constructed with **no signer** → `_obtain_reattest_proof`
   reaches a signer only if one was injected; with `None` it returns `None` (fail-closed). **There is
   no factory in `vapi_bridge` that constructs a signer from key material** — the only way a real
   signer enters is (a) a test injecting the fixture, or (b) the future VBDIP-0006 device/SDK path
   (which signs device-side and never hands the bridge a private key). The seam carries a *callable*,
   never a key.
This makes the credential-spoofing vector (§0) structurally absent in production: no key material and
no fixture import are reachable from the `vapi_bridge` package; §5(f) asserts both as a regression net.

## 5. Test plan
- (a) **① pubkey round-trip KATs** — `decode_pubkey(encode_pubkey(pk)) == pk` per pairing
  (ML-DSA-65+ECDSA-P256, ML-DSA-44+ECDSA-P256, SLH-DSA-128s+ECDSA-P256); byte-pinned blobs; malformed
  blobs rejected. Same KAT discipline as ①'s suite (W-4).
- (b) **Challenge issuance** — fresh 32-B nonce per call (distinct); single-use (second use of a
  nonce rejected); TTL expiry rejected.
- (c) **Challenge domain separation** — a composite-sig made under the RENEWAL family tag does NOT
  verify as a CHALLENGE response (and vice versa) — proves the dedicated-tag anti-reuse property (W-5).
- (d) **Integration: ① ↔ ③ compose (the freeze-unlock evidence)** — end-to-end through ③'s real
  renewal path with enforcement ON + a **test-fixture** device keypair: challenge issued → device
  composite-signs (real `composite_sig.sign`) → bridge verifies (real `composite_sig.verify`) →
  `compute_reattest_proof` → commitment chain advances with `enforced=1`. A tampered/forged sig →
  `_obtain_reattest_proof` returns None → renewal SKIPPED (dormant-blind gate).
- (e) **Lazy-import / enforcement-OFF** — with enforcement OFF, `_obtain_reattest_proof` is not
  reached and `composite_sig` is not imported (bridge runs without PQ libs); renewal path
  byte-identical to ③-shipped.
- (f) **Test-key-not-in-production guard (defense-in-depth for EDIT 2)** — assert (i) **no
  `bridge/vapi_bridge/` module imports** `bridge/tests/fixtures/ipact_signer_fixture` (static
  import-graph grep), and (ii) the production `VHPRenewalAgent` constructed with no injected signer
  has a `None` signer → `_obtain_reattest_proof` is fail-closed. Backs the structural guard (§4).
- (g) **① regression re-run (W-4 P-check)** — `l9_presence/tests/test_composite_sig.py` passes
  unchanged (no regression on pre-existing ① surface from the v1.1 pubkey extension).

## 6. Tag reservation status
The challenge tag `b"QORTROLLER-IPACT-CHALLENGE-v1"` is a **capability tag** (protocol-step domain
separator, like MLGA), **not** a PATTERN-017 commitment family — it is **RESERVED** (scope-doc only),
NOT in `_KNOWN_CAPABILITY_TAGS` or the PV-CI allowlist this step. ①'s pubkey wire format is a v1.1
capability extension (no new tag). The freeze ceremonies for ① (now v1.1) and ③ remain **separate
later steps**, defensible after #8's integration evidence lands.

## 7. Alignment checklist
| Check | Reference | Status |
|---|---|---|
| Challenge-response over ①'s AND-composition | ① composite-sig | ALIGNED |
| Dedicated challenge tag (anti-reuse) | W-5 | ALIGNED (distinct from family tag) |
| Handler pattern (doubled /operator/ + _check_key + NonceDedupTracker) | Q1 (pre-inv §d) | ALIGNED |
| Testable without live bridge | Q2 (pre-inv §d) | ALIGNED (inject keypair + fake store; HTTP E2E separate) |
| Lazy-import; PQ libs enforcement-gated | W-3 | ALIGNED (bridge startup unaffected OFF) |
| Test key not production-reachable | §0 constraint / W-1 | ALIGNED (fixtures only; no prod branch) |
| Gamer-sovereignty (device signs, bridge verifies) | sovereignty invariant | ALIGNED |
| ① v1.1 pubkey ext is capability, not spec change | W-4 | ALIGNED (M'/tiers/OID/divergence untouched) |
| No PoAC/chain-hash/ZK/contract/TGE change | hard rules | ALIGNED |

## 8. Novelty claim (conditional)
**Claim:** no *known* public production deployment of a **bridge-issued challenge / device-composite-
signed (hybrid ECDSA+PQ) re-attestation gating a soulbound-credential renewal cadence**. Each
ingredient (challenge-response, hybrid sig, soulbound TTL) has prior art; the *composition* gating
renewal does not, to our knowledge. **Conditional** — rests on the internal corpus + the IIP-64/PoEP
assessment; absence of evidence ≠ evidence of absence; USPTO+EPO search before any external/IP claim.

---

## Resolved decisions (W-1 … W-5, 2026-05-23)
- **W-1** composite pubkey source → inject **test-only** key for v1 (NOT production-reachable — §0
  constraint); production source deferred to ② P4b (#12).
- **W-2** device signer → pluggable signer seam; test-fixture signer v1; firmware/SDK = VBDIP-0006 (#11).
- **W-3** bridge↔① dep → lazy-import inside `_obtain_reattest_proof`; PQ libs in
  `bridge/requirements-enforcement.txt`; bridge startup unaffected when OFF.
- **W-4** ① pubkey wire format lands in #8's commit (`encode_pubkey`/`decode_pubkey`) + ① scope v1.1
  paragraph + ① round-trip KATs + ① regression re-run in P-check. Capability extension, not spec change.
- **W-5** dedicated challenge tag `b"QORTROLLER-IPACT-CHALLENGE-v1"` (≠ family tag) for cross-protocol
  reuse resistance; width-asserted at import.

## Dependencies & relationships
- **Extends ①** (v1.1 pubkey wire format) and **③** (wires `_obtain_reattest_proof`).
- **Unlocks** #6 (① freeze ceremony) + #10 (③ freeze ceremony) via integration evidence.
- **Production flip-on still needs** #12 (② P4b key registration) + #11 (VBDIP-0006 firmware signer).
- Cross-refs: `l9_presence/composite_sig.py`, `bridge/vapi_bridge/{vhp_renewal_agent,ipact_renewal,operator_api}.py`,
  `bridge/controller/l6_trigger_driver.py` (ChallengeSequencer precedent). Memory:
  [[dormant-blind-closure-path]], [[ipact-renewal-cadence-v1-shipped]], [[composite-sig-v1-shipped]].

## Provenance
DRAFT scope held for operator review before V-check + code. Protocol: investigation (done) → hold
(done) → scope doc (this file) → V-check → **hold** → code + vectors → P-check (incl. ① regression
re-run, W-4) → hold → atomic commit. Freeze ceremonies for ① (v1.1) and ③ remain separate later steps.
