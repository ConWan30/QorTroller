# QorTroller — The Honest State of the Protocol (Genesis → Now)

*A candid, no-gloss accounting as of 2026-05-20. Where a claim is a cryptographic
guarantee, an empirical inference, a documented limitation, or an uncalibrated/
aspirational target, this document says which.*

---

## 1. What QorTroller is (and what it is not, yet)

**Is:** a working **prototype** of *Verifiable Autonomous Physical Intelligence (V.A.P.I.)* — a
self-coined DePIN sub-category in which the physical-input source (a gamer + controller) is also
the cryptographic owner of the data it produces. It runs on real hardware (a DualShock Edge),
generates cryptographically-signed input records, anchors continuity proofs on IoTeX testnet,
and runs an autonomous agent fleet behind a single composable gate, `isFullyEligible()`.

**Is not (yet):** a mainnet protocol, a launched token, an audited system, a multi-user network,
or a statistically-validated biometric identity system. It is a single-developer,
AI-assisted prototype with a 3-person calibration corpus, running in dry-run on testnet.

## 2. Genesis → now (the honest arc)

- **Genesis:** an anti-cheat idea reframed into a sovereignty thesis — instead of *punishing*
  cheating, make it *impossible* by proving humanity at the controller and giving the gamer
  ownership of the resulting data. The V.A.P.I. category and the 228-byte PoAC wire format were
  coined/frozen early and have not changed since.
- **Build-out:** ~240 phases of incremental work — the PITL sensor stack, the bridge service,
  the smart-contract suite, the ZK circuit, the agent fleet, and a family of FROZEN-v1
  cryptographic commitment primitives.
- **On-chain milestones (testnet):** Operator-agent registration → O1_SHADOW → O2_SUGGEST →
  O3_ACTING; GIC_100 continuity milestone anchored; 49 contracts deployed on IoTeX testnet.
- **Now:** stability-hardened bridge, a steward-absorption fleet reorganization, a frontend
  remodel, and an honest reconciliation pass on the documentation. Real controller capture
  confirmed working this session.

## 3. What is genuinely built and proven

- **Real, signed physical capture.** A certified DualShock Edge produces 228-byte PoAC records
  (164-byte body + 64-byte ECDSA-P256 signature), `record_hash = SHA-256(body)`,
  `device_id = keccak256(pubkey)`. Verified live this session: `sim_mode=False`, real records
  flowing, `EXCLUSIVE_USB` host arbitration, `NOMINAL` capture-health, grind-ready. *(cryptographic
  guarantee + verified-on-hardware)*
- **A 9-layer PITL detection stack** (HID presence, PoAC chain integrity, IMU/HID discrepancy,
  TinyML behavioral classifier, biometric Mahalanobis fingerprint, temporal rhythm, optional
  haptic challenge-response).
- **FROZEN-v1 cryptographic primitive family** (GIC, WEC, VAME, CORPUS-SNAPSHOT, CONSENT,
  BIOMETRIC-SNAPSHOT, LISTING, FRR, ZKBA, POSEIDON-AS, O3-SUPERSEDE) — deterministic, byte-frozen
  commitment schemes; GIC_100 is permanently anchored on IoTeX testnet. *(cryptographic guarantee)*
- **Gamer-held consent.** On-chain consent is granted/revoked by the gamer's own wallet
  (`msg.sender == gamer`); the bridge can only *read* consent. *(cryptographic guarantee /
  sovereignty enforced procedurally)*
- **Self-verifying proof artifacts (VPM).** Self-contained HTML certificates the protocol
  compiles, hashes, and serves; the UI recomputes the SHA-256 in-browser. *(verifiable)*

## 4. The agent fleet — the real picture

A registered roster of **38 agent IDs** (the on-chain coherence Merkle set). Post-STABILITY-9
**steward absorption**, **9** formerly-standalone agents now run as steward-invoked skills inside
**3 cryptographically-attested Operator Initiative stewards** (Sentry / Guardian / Curator), so
the operational fleet is **standalone agents + 3 stewards**. All three stewards reached
`O3_ACTING` on-chain (testnet) and are running live (verified this session).

**Honest caveats:** the fleet runs in **`dry_run=True`** — it drafts/observes, it does not take
autonomous real-world actions by default. `CHAIN_SUBMISSION_PAUSED=true` is held (a kill-switch).
ioSwarm is **emulator-only** (no live external nodes). The Curator steward's O3 activation used a
**MockKMSClient** (testnet-only; mainnet would require real HSM provisioning).

## 5. The biometric reality — what's proven vs. the core blocker

- **Proven (empirical):** human-vs-bot *presence* discrimination. Physiological texture
  (micro-tremor, grip asymmetry, trigger-onset velocity, IMU gravity) is hard for translator
  hardware/macros to synthesize. This is the genuine strength.
- **NOT yet proven (the documented tournament blocker):** *which* human. Inter-person separation
  is **`touchpad_corners = 0.728`** (N=35) — **below the 1.0 gate**. The AIT probe clears
  **1.199** (N=37) but not on all player pairs; tremor_resting is 1.177 (N=27) but
  `all_pairs_p0_ok = False` (P1 vs P3 = 0.032). **Cross-person biometric identity is uncalibrated
  / unproven across all pairs.** The `separation_ratio > 1.0` token-launch gate remains in force,
  permanently and non-negotiably.
- **Corpus:** **3 players** (a 4th was eliminated as a duplicate of player 3), ~267 terminal +
  ~74 hardware sessions. This is a small, single-environment dataset — not a population study.
- **Disabled by default (N=0 calibration):** GSR grip (L7), active haptic challenge (L6),
  neuromuscular reflex (L6B). These are designed, not validated.

## 6. On-chain reality

- **Network:** IoTeX **testnet** (chain ID 4690). No mainnet deployment. No real economic value.
- **Contracts:** 49 deployed on testnet. **No third-party security audit** has been performed.
- **Wallet:** the deployer/bridge wallet (~15 IOTX testnet) is the operator's own; it is the
  signer for the "live" activity. This is a single-operator demonstration, not a decentralized
  network.

## 7. Brand & legal reality

The name **QorTroller** (V.A.P.I. category) is the v0.5 outcome of a 4-iteration brand cycle
(Qoresence → Qorsence → QorSense → QorTroller). It is **codebase-locked but not legally secured**:
trademark clearance, domain purchases, and the R0 prerequisite certificate are operator-side
actions still pending. The code-level rename (Layer A) is gated on that R0 signature; all
cryptographic byte-literals stay `VAPI-` under FROZEN-v1 preservation.

## 8. What's deferred / aspirational (clearly not shipped)

Adaptive-trigger force-curve discrimination, L6 reflex proofs, L8 Bluetooth co-presence,
lightbar optical witness, the data marketplace flywheel at scale, and any horizontal use of the
proof-of-human primitive (Sybil resistance, airdrops, governance, AI-training-data provenance)
are **roadmap, not implemented.** They are credible *because* the capture→proof→ownership rail
already exists — but they are not built.

## 9. Bottom line

QorTroller is a **real, working, honestly-scoped prototype** with a genuinely novel core: signed
proof-of-human at the input layer, gamer-held data sovereignty, and on-chain continuity proofs on
IoTeX. Its hardest unsolved problem — telling individual humans apart biometrically (separation
ratio > 1.0 on all pairs) — is openly tracked as the blocker it is, not papered over. Everything
"live" is testnet + dry-run + single-operator + N=3. The architecture is sound and extensible;
the empirical validation and the path to mainnet/economic reality are the work ahead.

---
*Status: testnet (IoTeX 4690), dry-run, pre-mainnet, single-developer prototype, N=3 calibration
corpus, no smart-contract audit, brand not yet legally secured. Test counts and ratios are
point-in-time snapshots. Generated 2026-05-20.*
