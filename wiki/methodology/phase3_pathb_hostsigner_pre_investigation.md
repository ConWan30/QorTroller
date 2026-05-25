# Phase 3 (Path B — host-side SDK signer) — Pre-Implementation Findings

**Status:** FINDINGS ONLY — read-only investigation, no code. Held for operator review before any
code. This is the **dormant-blind closure** (stage 4 of the four-stage path: ③ ✅ → #8 ✅ → ② P4b ✅ →
**host-held signer (this) → flip-on**).

**Date:** 2026-05-24 · **Goal:** wire `_reattest_signer` to `composite_sig.sign()` with a host-held
keypair, then flip enforcement ON.

---

## Q0 — "Can the DualShock Edge be utilized?" — YES (and Path B is exactly how)

The DualShock Edge (Sony CFI-ZCP1) is the certified device, already integrated:
`controller/dualshock_integration.py` + `bridge/.../dualshock_integration.py` (HID VID=0x054C
PID=0x0DF2, ~1002 Hz USB). Under **Path B**, the **Edge is the physical-input + sensor source**, and
the **host (the laptop running the bridge) holds the composite keypair and signs** the challenge nonce —
paired with the Edge's live sensor stream. The Edge silicon does **not** sign (that's Path A firmware).
This is the tractable path: **no controller firmware required.**

**Security-model honesty (load-bearing for what the closure claims):** with a host-held key, the
re-attestation proves *"the host holding this key signed a fresh bridge challenge, while the certified
Edge's sensor stream was live"* — **not** *"the controller silicon cryptographically proved its own
presence"* (Path A). Path B closes the dormant-blind gap against **remote/dormant auto-renewal** (a
renewal now requires a live signer + a fresh challenge response), but the key's security rests on the
**host**, not controller hardware. This is the deliberate Path-B tradeoff; the dormant-blind closure
should be described accordingly (presence of a live host-signer + live sensor stream, not hardware-root).

---

## Point 1 — `_obtain_reattest_proof` current state

**Finding: it is NOT a `return None` stub.** #8 (`48879281`) already wired the **full handshake**.
Two corrections to the task brief (anti-staleness):

1. **Signature is `def _obtain_reattest_proof(self, vhp: dict) -> bytes | None`** — *synchronous*, takes a
   `vhp` dict (not `async (device_id, token_id)`). `device_id = vhp["device_id"]`.
2. **The challenge is IN-PROCESS** (`self._challenge_store = ipact_challenge.ChallengeStore()`), not an
   HTTP call to `POST /operator/ipact-challenge`. The HTTP endpoint exists for *external/device-initiated*
   challenges; the renewal agent's internal handshake uses its own store directly.
3. **`SHA-256(challenge ‖ sig)` is already computed inside `compute_reattest_proof(nonce, sig)`** (wired
   at vhp_renewal_agent.py:105) — the signer does NOT compute it.

Wired logic (vhp_renewal_agent.py:61-108): `pubkey_provider(device_id)` → `challenge =
_challenge_store.issue(device_id)` → `blob = signer(challenge.nonce)` → lazy-import composite_sig →
`decode_pubkey(pubkey_blob)` → `verify(pub, CHALLENGE_TAG, nonce, blob)` → `consume()` (single-use) →
`compute_reattest_proof(nonce, blob)`. Fail-closed on any miss.

**The pubkey provider is ALREADY production-wired** (vhp_renewal_agent.py:82-86): when no provider is
injected, it defaults to `make_chain_backed_provider(self._chain)` → reads the registered composite
pubkey from the **live VAPIPoEPRegistry `0x4Dcfa11d…`**. So ② P4b is fully connected.

**⇒ The ONLY missing production piece is `_reattest_signer`** — a callable `nonce -> composite_sig_blob`.
Everything else (challenge, verify, proof, pubkey source) is wired. Path B is a *small* seam-fill +
keypair provisioning + flip, not a rebuild.

---

## Point 2 — composite keypair availability

- **PQ backends are INSTALLED and working NOW:** `quantcrypt` + `slhdsa` + `cryptography 46.0.3`.
  Verified live: `generate_keypair(ALG_MLDSA44_ECDSA_P256_SHA256)` → `sign` → `verify` = True (sig
  **2531 B**, encode_pubkey blob **1418 B**). **No dependency install needed** — the Step-1 prerequisite
  is already met.
- **No composite keypair is currently held by the bridge.** vhp_renewal_agent comment is explicit: *"No
  key→signer factory exists in vapi_bridge; the seam carries a callable, never a key."* The `devices`
  table has a single ECDSA `pubkey_hex` (the PoAC key), not a composite key.
- **Tier:** ML-DSA-44 + ECDSA-P256 (`ALG_MLDSA44_ECDSA_P256_SHA256`, the device-user tier) is the
  natural choice (smallest, OID-registered, sig 2531 B). ML-DSA-65 (device-identity) is the heavier
  alternative; SLH-DSA-128s is the device tier but largest (sig ~7856 B).
- **Where the private key should live (Step 1 decision for operator):** a host-side key file (e.g.
  `~/.vapi/keys/device_composite_<tier>.json` or a `.keys/` dir, 0600 perms) loaded at bridge startup —
  stable across restarts (it IS the device identity; never regenerated). NOT in SQLite unencrypted. The
  **public** blob goes on-chain (VAPIPoEPRegistry); the **private** key never leaves the host.

**Sovereignty note:** the `registerDevice` tx is `msg.sender = gamer`. On single-operator testnet the
bridge wallet acts as the gamer (as in the ② P4b E2E). In a real multi-gamer deployment each gamer's own
wallet registers their device. The host-held private key is the Path-B trust assumption (see Q0).

---

## Point 3 — challenge source

In-process `ipact_challenge.ChallengeStore` (already instantiated in the agent). `issue(device_id)` mints
a **32-byte CSPRNG nonce** (`secrets.token_bytes(32)`, prefix-byte 0x20 per ③ §2), `challenge_id =
token_hex(16)`, single-use + TTL. The 32-byte length satisfies `build_message_representative`'s
`len(commitment)==32` requirement — the signer must sign exactly this nonce as the commitment. **Operational, no new endpoint needed.**

---

## Point 4 — the enforcement flip

- **Flag:** `ipact_renewal_enforcement_enabled` (config.py:1151), env `IPACT_RENEWAL_ENFORCEMENT_ENABLED`,
  **default False** (config-scoped — set in `.env`, persists across restarts).
- **Mechanism** (vhp_renewal_agent.py:169-180): **ON** → `_proof = _obtain_reattest_proof(vhp)`; if None
  → `continue` (skip renewal, the "dormant-blind gate"); else use the proof in the commitment. **OFF** →
  `_reattest_proof = NO_REATTEST_PROOF` sentinel; the commitment chain still accumulates but renewals are
  NOT gated (byte-identical to pre-③).
- **Flip = set `IPACT_RENEWAL_ENFORCEMENT_ENABLED=true` in `.env`.** This is the governance event.
- **⚠️ Scope of the flip:** it is GLOBAL — every expiring VHP then requires a valid re-attestation. A
  device without (a) a registered composite pubkey on the live registry AND (b) a wired host-signer will
  have its renewal **skipped** (fail-closed). So the flip should follow Steps 1-2 (keypair registered +
  signer wired) for the device(s) we intend to keep renewing. (Currently the agent renews only
  `get_expiring_vhps()` — likely few/none in dry-run testnet, so the blast radius is small, but the
  semantics matter.)

---

## Point 5 — gameplay workflow assessment

**What EXISTS (the substrate is real):**
- **Capture flow:** `dualshock_integration.py` `run()` → `_session_loop()` — controller connection drives
  the PITL capture loop → PoAC records generated → chain advances. This is the core player-side flow.
- **Eligibility infrastructure (operator/tournament-facing):** `isFullyEligible()` on-chain;
  tournament-readiness scorecard, tournament-preflight, HMAC eligibility endpoint for tournament
  operators (operator_api.py — extensive). These VERIFY a device/player is eligible.
- **Presence channel:** `live_presence_signaling_enabled` / `live_presence_haptic_enabled` config — a
  bidirectional LED+haptic presence channel exists (default-off).
- **PoEP (presence) arc:** `l9_presence/` — built, `poep_enabled=False` (L6B N≥50 gate unmet).

**What appears to NEED a build arc (Phase 4, for operator confirmation — NOT asserted):**
- A **player-facing casual remote-mode session orchestration** — "connect Edge → matchmade/credentialed
  session → play → AGaaS delivery" as a *casual-player* flow. The existing surface is **capture-facing**
  (PITL loop) + **operator/tournament-facing** (eligibility queries), not a casual-player session
  orchestrator. Whether this is "built and waiting" or "needs its own arc" is the **Phase 4 operator
  question** — I'm describing what's there, not building speculatively.

---

## Implementation scope under Path B (for operator review — NOT yet executed)

Given #8 pre-wired the handshake, Path B is small:

- **Step 1 (on-chain spend — operator-authorized):** generate an ML-DSA-44+ECDSA-P256 composite keypair;
  store the private key host-side (key file, 0600); register the `encode_pubkey` blob on the live
  VAPIPoEPRegistry `0x4Dcfa11d…` via `registerDevice` (gamer wallet = bridge wallet on testnet). Est cost
  ~register tx (≈0.15 IOTX class, per the ② E2E). This makes the chain-backed pubkey provider resolve a
  real registered key for this device.
- **Step 2 (code):** add a host-signer module that loads the keypair and exposes
  `signer(nonce) = composite_sig.sign(keypair, ipact_challenge.CHALLENGE_TAG, nonce)`; wire it as
  `_reattest_signer` when constructing `VHPRenewalAgent` in `main.py` (gated on a config flag so it only
  activates with a keypair present). Lazy-import preserved (W-3). Plus a new test
  `test_integration_enforced_renewal_with_registered_keypair` (real keypair, not the #8 fixture).
- **Step 3 (flip):** `IPACT_RENEWAL_ENFORCEMENT_ENABLED=true`.

**Hold points:** this findings note (now) → operator review → Step 1 (on-chain spend, operator-authorized
+ estimate-first) → Step 2 code + P-check → hold (code review) → Step 3 flip → commit. Step 4 (gameplay
workflow) assessed at the post-Step-3 hold (operator decides scope).

**No FROZEN change** (① wire format is frozen + sealed; this consumes it). No new on-chain contract.
