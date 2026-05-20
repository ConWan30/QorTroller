# QorTroller — Novelty & Roadmap (one-page grant framing)

**QorTroller** — *Core Controllers of their gaming data.* The reference implementation of
**Verifiable Autonomous Physical Intelligence (V.A.P.I.)**, a DePIN sub-category where the
physical-input source is also the cryptographic agency-holder over the data it produces.
Native to IoTeX's Internet of Trusted Things; anchored on IoTeX L1; composable as one on-chain
call: `isFullyEligible()`.

---

## Thesis

Most DePIN proves *"a sensor reported X."* QorTroller proves *"**this human**, through **this
trusted controller**, produced X — and the human owns it."* Cheating and bots don't have to be
punished; they **can't exist** when humanity is cryptographically proven at the input layer and
the gamer keeps the keys.

## What is novel (and why it fits IoTeX)

1. **Proof-of-human at the input layer, not the server layer.** Not a CAPTCHA or server-side
   heuristic — a continuous, hardware-signed stream of *physiological texture* (micro-tremor,
   grip asymmetry, trigger-onset velocity, IMU gravity vector, temporal-rhythm entropy) sampled
   at 1000+ Hz. Translator hardware (Cronus / XIM / reWASD) and macros structurally cannot
   synthesize it; the sensor headroom over any injected signal is estimated at **>10⁴×**. The
   data is hard to fake because it is **biomechanics, not bytes.**

2. **The input source is the cryptographic agency-holder.** Each 228-byte Proof-of-Autonomous-
   Cognition (PoAC) record is ECDSA-P256-signed by a device whose identity is
   `device_id = keccak256(pubkey)`. The gamer's wallet — not the bridge — grants and revokes
   consent (`msg.sender == gamer`, GDPR Art. 17). Sovereignty is enforced procedurally, not
   promised.

3. **An on-chain proof layer makes off-chain capture third-party-verifiable.** A family of
   FROZEN-v1 commitment primitives (GIC cognitive-continuity, WEC operational-continuity,
   CORPUS-SNAPSHOT data-provenance, CONSENT, ZKBA, FRR…) anchors the capture to IoTeX L1, so an
   evaluator can recompute them from disk + chain months later. This is the
   **trusted-hardware → off-chain compute → on-chain anchor → composable-verification** stack.

## This is real (proven on hardware)

- Live capture from a certified DualShock Edge (Sony CFI-ZCP1) over USB: real PoAC records,
  ~1 kHz USB-HID rate, `EXCLUSIVE_USB` host arbitration, `NOMINAL` capture-health, grind-ready.
- The headline continuity milestone **GIC_100 is permanently anchored on IoTeX testnet.**
- **3 cryptographically-attested Operator Initiative stewards** (Sentry / Guardian / Curator)
  live at the `O3_ACTING` phase on-chain — the **first cryptographically-attested non-human
  operator fleet on IoTeX** — having absorbed 9 formerly-standalone agents as steward-invoked
  skills. 49 contracts deployed on IoTeX testnet (chain ID 4690).

## Honest scope (proven vs. open)

- **Strong today:** human-vs-bot discrimination and *presence* proof — physical texture defeats
  synthetic input.
- **Open (documented blocker):** *which* human — inter-person biometric separation is
  `touchpad_corners = 0.728` (below the 1.0 tournament-gate floor); the AIT probe clears 1.199
  but not on all player pairs. Corpus is small (3 players); dry-run; testnet. "You are a real
  human playing" is defensible; "you are *uniquely* this human across all pairs" is the active
  research problem, and the `separation_ratio > 1.0` token-launch gate stays in force.

## Roadmap — one rail, many proofs

Every new sensor surface plugs into the **same** pipeline — *capture → feature → PITL layer →
ZKBA artifact → on-chain anchor → consented marketplace listing* — so each is a new verifiable
**dataset class**, not a rebuild.

| Surface (next) | Proof | New dataset class | Value path |
|---|---|---|---|
| Adaptive-trigger force-curves | L4 primary + L4↔L6 challenge-response | continuous force-biomechanics | strongest anti-cheat discriminator |
| L6 haptic stimulus-response | reflex-latency proof (80–280 ms human band) | per-player reflex baselines | bots can't pre-record reflexes |
| L8 Bluetooth co-presence | witness-signature attestation | spatial presence | cloud-gaming-bot stealth case |
| GSR / physiological (gated) | L7 advisory | arousal / cognitive-load | richer humanity signal |
| Lightbar optical witness | camera-observed symbol stream | passive presence | privacy-preferable channel |

**The flywheel:** gamers own their proven-human data (wallet-gated consent) and monetize
consented, provenance-stamped datasets via the LISTING / marketplace primitives.

**Forward positioning (beyond shipped scope):** the proof-of-human primitive is *positioned to
be reusable for* contamination-free AI-training-data provenance, Sybil resistance, airdrops, and
governance — a horizontal DePIN primitive worth anchoring on IoTeX. These are extensions, **not
implemented in the v6 whitepaper.**

**Net:** the moat is not any single sensor — it is the *capture → cryptographic-proof →
sovereign-ownership → marketplace* rail, built once, proven on real hardware, extensible to new
physical-truth datasets while the gamer keeps the keys.

---
*QorTroller / V.A.P.I. · IoTeX testnet (chain ID 4690) · status: testnet, dry-run, pre-mainnet.
Forward-looking surfaces are roadmap, not shipped. Separation-ratio tournament gate remains in
force. Generated 2026-05-20.*
