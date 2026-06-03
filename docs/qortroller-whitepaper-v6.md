# QorTroller — Whitepaper v6.1

**Title**: QorTroller: Verifiable Autonomous Physical Intelligence (V.A.P.I.) — A Reference Implementation for Gamer-Sovereign Anti-Cheat on IoTeX

**Version**: 6.1 (grant-tailored; supersedes v6 §4, v5, v4)
**Date**: 2026-05-19 · **v6.1 §4 reconciliation**: 2026-05-24
**v6.1 revision note**: reconciles §4.1/§4.2 to the canonical **12-family** PATTERN-017 frozenset (v6's §4 undercounted — it miscounted PoAC as a family and omitted the already-frozen AGENT-COMMIT-v1 + PHYSICAL-DATA-ATTESTATION-v1). Documentation-only correction; no FROZEN value changed; PoAC (228-byte wire format) unchanged and carved out as wire format, not a family. Filename retained as `qortroller-whitepaper-v6.md` to preserve cross-references.
**Brand-lock**: QRESCE-0001 v0.5 (`2c762835`)
**Protocol-state HEAD** (last source-code commit; bridge test counts measured here): `4f8068e9`
**Documentation HEAD at v6 drafting time**: `aeb6db58` after WP v6 commit; this version supersedes any earlier draft `39f7d26d` state-document parallel reference
**Canonical repo**: https://github.com/ConWan30/QorTroller
**Verification discipline**: every load-bearing claim has a verifiable evidence anchor; no flat first-of-its-kind claims; empirical figures paired with their limits

---

## Abstract

Competitive console gaming faces a structural cheating crisis. Traditional anti-cheat protocols — BattlEye, EAC, VAC, RICOCHET — operate defensively: detect cheaters via behavioral pattern matching or kernel-level snooping, then punish via ban or kick. The defensive posture inherits two flaws by design: (1) it produces no durable cryptographic evidence (decisions are platform-internal); (2) it treats the gamer as the target of surveillance rather than the cryptographic agency-holder over their own input data.

We coin **Verifiable Autonomous Physical Intelligence (V.A.P.I.)** as a Decentralized Physical Infrastructure (DePIN) sub-category for protocols where the physical-input source is also the cryptographic agency-holder over the data those physical interactions generate. **QorTroller** is the reference implementation of V.A.P.I. for competitive console gaming, built native to IoTeX. The protocol inverts traditional anti-cheat: instead of detecting cheaters and punishing them, QorTroller cryptographically proves humanity continuously during play — so cheating produces evidence that cannot pass verification, while the gamer retains full cryptographic sovereignty over their session data.

The architectural commitments are portable. The V.A.P.I. category is intended to host future implementations beyond QorTroller — other physical-input modalities (steering wheels, flight sticks, motion controllers, biometric peripherals) under the same cryptographic-sovereignty discipline.

This whitepaper documents QorTroller's current state at v6: 49 contracts deployed on IoTeX testnet, three autonomous Operator Initiative agents at terminal O3_ACTING phase under six-layer default-deny posture, 12 commitment-family FROZEN-v1 cryptographic primitives plus the POSEIDON-BN254-AS hash capability, 4377 passing bridge tests, 128/128 PV-CI invariants, 14 Mythos audit guardrails, and the GIC_100 chain head permanently anchored at `0x0e9d453d…1ab48da` (block 43348052, tx `0xe807347eb…`, 2026-05-06). Honest gaps — the touchpad_corners separation ratio remaining below 1.0 as the tournament BLOCK enforcement gate, Curator's direct-O3 anchoring bypass of the formal review-pace graduation, the limited 3-player calibration corpus — are explicitly surfaced rather than narrated past.

---

## 1. The V.A.P.I. Category

### 1.1 Coining the category

DePIN as it currently exists in the IoTeX ecosystem (Helium, Hivemapper, IoTeX itself) encompasses protocols where physical infrastructure (wireless nodes, dashcams, sensors) reports verifiable data to a decentralized network. The infrastructure is the noun; the data flow is from infrastructure to network.

V.A.P.I. names a more specific configuration: protocols where the physical infrastructure is **a human-operated input device** AND the cryptographic agency over the data those interactions generate **resides with the human**, not the device manufacturer or the platform operator. The data flow is human → device → cryptographic commitments held by the human.

This configuration has four defining criteria:

1. **The physical-input source is identifiable** as a specific class of human-operated device — gaming controller, steering wheel, flight stick, motion peripheral, biometric sensor
2. **The cryptographic agency-holder is the human** whose interactions produce the data — verified at protocol layer (e.g., `msg.sender == gamer` checks; per-category consent revocation; gamer-held credentials)
3. **Verification is cryptographic** — biometric continuity, behavioral fingerprints, hardware attestations all rendered as cryptographic commitments anchored on a public ledger
4. **Autonomy is bounded** — autonomous agent fleets operate with explicit scope policies anchored on chain, not as opaque background services

### 1.2 Distinction from adjacent categories

| Adjacent category | Distinction from V.A.P.I. |
|---|---|
| **Generic DePIN** | The agency-holder is the network operator; data flows toward the network. In V.A.P.I., the agency-holder is the data subject; data flows toward the human's cryptographic possession. |
| **Generic anti-cheat** | Verification produces ephemeral pass/fail signals consumed internally. In V.A.P.I., verification produces durable cryptographic commitments anchored on a public ledger. |
| **Generic biometric authentication** | The biometric is a separate enrollment ritual (fingerprint, face scan, voice sample). In V.A.P.I., the biometric IS the gameplay — there is no separate enrollment. |
| **Generic gamer-sovereignty narrative** | Marketing claims around "you own your data" without protocol enforcement. In V.A.P.I., sovereignty is enforced at the smart contract layer (consent registry, marketplace consent bit, FSCA contradiction rules detecting GDPR Art. 17 violations within ≤5 minutes). |

### 1.3 Why V.A.P.I. needs to exist as a named category

The architectural commitments are portable. The V.A.P.I. discipline can host future protocols:
- A racing-sim ecosystem using V.A.P.I. for steering-wheel + pedal biometric attestation
- A flight-sim ecosystem using V.A.P.I. for control-stick + rudder-pedal continuity proofs
- A fitness-gaming ecosystem using V.A.P.I. for motion-controller + biometric-peripheral verification
- A music-rhythm-gaming ecosystem using V.A.P.I. for keyboard / drum-pad latency-coherence proofs

The category framing creates ecosystem space. By coining V.A.P.I. as a distinct DePIN sub-category, QorTroller establishes the discipline (FROZEN-v1 primitives, Cedar policy bundles, bounded autonomous agents, gamer-sovereign consent registries) for future implementations to inherit rather than redesign from scratch.

### 1.4 Honest scope note on V.A.P.I. positioning

V.A.P.I. as a named category is operator-coined. It does not yet have external adoption or other implementations. This whitepaper treats V.A.P.I. as the conceptual framing under which QorTroller's design choices make architectural sense, not as a claim of category leadership. The grant submission requests support for both QorTroller's mainnet readiness AND the V.A.P.I. category's ecosystem space — a category establishes itself through implementations, and additional V.A.P.I.-compliant projects emerging from the grant ecosystem would be the strongest possible validation of the category framing.

### 1.5 What is portable and what is not — why fund QorTroller specifically

A reasonable evaluator response to §1.3 (portability invitation) and §1.4 (operator-coined disclosure) is: if the category is open and the discipline is portable, why fund QorTroller rather than wait for a later entrant to inherit the work? The honest distinction:

**What is portable by design** (and intentionally so — this is the V.A.P.I. category's pitch, not its weakness):
- The FROZEN-v1 byte-domain discipline + the 12 commitment-family preimage structures + the POSEIDON-AS hash capability
- The Cedar policy bundle pattern + the four-rung agent ladder (O0 → O1_SHADOW → O2_SUGGEST → O3_ACTING) + the six-layer default-deny posture
- The 14 Mythos audit guardrails as an operational discipline template
- The composability invariant `isFullyEligible(deviceId)` as a single view call
- The smart contract architecture as a reference set (49 contract source files; deployment scripts; testnet ABIs)
- The gamer-sovereignty enforcement primitives — per-category consent registry, `msg.sender == gamer` invariants, FSCA contradiction rules detecting GDPR Art. 17 violations

**What is not portable** — QorTroller's position rests on three hardware-and-time-bound assets that a later V.A.P.I.-compliant entrant cannot clone:

1. **The calibration corpus** — **267 physical terminal sessions** on real DualShock Edge CFI-ZCP1 hardware (P1=98, P2=86, P3=83), with three distinct humans across multiple probe types (AIT, touchpad_corners, touchpad_freeform, touchpad_swipes, tremor_resting); verified at `sessions/human/terminal_cal_P{1,2,3}/` on 2026-05-19. A competing implementation starts at N=0; reaching N=37 AIT corpus with all-pairs > 1.0 separation ratio requires real hardware time with real humans, which neither the FROZEN-v1 byte specifications nor a code fork can shortcut. The grant submission's Track A explicitly funds scaling this corpus from 3-player → 10+ player; that scaling is the most valuable asset the grant produces, because it cannot be cloned ex post by anyone reading the published architecture.

2. **The dated frozen-primitive lineage with on-chain anchoring history** — the FROZEN-v1 primitives were anchored on IoTeX testnet starting from Phase O0 (2026-05-03) through the present, with specific transaction hashes timestamping each ceremony. A later entrant can adopt the byte-domain specification but cannot retroactively produce the on-chain commitment history. The 6 ceremony transactions of 2026-05-17 (Sentry + Guardian + Curator op_tx + gov_tx pairs) at IoTeX testnet block timestamps are singular historical facts.

3. **The GIC_100 chain head as a singular on-chain historical fact** — head `0x0e9d453d…1ab48da` anchored at IoTeX testnet block 43348052 (tx `0xe807347eb…`, 2026-05-06). This is the cryptographic record of 100 consecutive clean gaming sessions under the dual-connection EXCLUSIVE_USB capture posture. No later V.A.P.I.-compliant project can produce a competing GIC_100 head at an earlier block; this is the strongest single piece of empirical evidence the protocol has.

**Strategic framing**: V.A.P.I.'s category openness is the pitch — additional implementations validate the category, not threaten QorTroller's position. QorTroller is the proven reference seed for V.A.P.I. Its lead is measured in sessions and on-chain facts, not in code that can be forked. The grant accelerates the assets that cannot be cloned (Track A: corpus scaling; Track B: same-controller separability; Track C: L8 BT witness; Track D: mainnet deploy) — each grant deliverable widens the moat QorTroller has built since Phase O0, in a way no later entrant can match without putting the same hardware time + on-chain time on the clock.

---

## 2. The problem QorTroller addresses

### 2.1 The cheating crisis in competitive console gaming

Modern competitive console games face four distinct adversarial classes:

| Class | Threat | Existing anti-cheat response |
|---|---|---|
| **Software cheats** (aimbots, wallhacks, ESP) | Modified game client or kernel-level injection | Kernel-level scanners (BattlEye, EAC); platform bans; HWID lockouts |
| **Hardware translators** (Cronus Zen, XIM Apex, reWASD) | Insert between controller and console; transform input macros at firmware level | Input-pattern detection (Activision RICOCHET Season 02); detection accuracy varies; hardware re-flashable to evade |
| **Cloud-gaming bots** (WormVision Lite MAX 2024-12-26; GeForce NOW unintended use) | Run bots in cloud gaming session; physical controller never touches the data path | Largely unsolved at platform layer (NVIDIA GeForce NOW concedes this gap in their anti-cheat compatibility guide) |
| **Account sharing / boosting** | Single account passed between players (skill manipulation) | Per-region IP heuristics; behavioral session-pattern analysis; limited cryptographic enforcement |

All four classes share a structural deficiency: existing anti-cheat operates defensively (detect → punish), producing ephemeral pass/fail signals. There is no durable cryptographic record that proves a given gameplay session was legitimate. Tournament organizers, scholarship programs, esports leagues, and skill-rating systems all lack a verifiable trust anchor.

### 2.2 The DePIN-native opportunity

IoTeX's Internet of Trusted Things foundation is structurally suited to the V.A.P.I. response. Specifically:

- **ioID** provides cryptographic device identity (DIDs with TBA — Token-Bound Accounts) that can bind specific hardware (a particular DualShock Edge by serial + biometric fingerprint) to a verified human
- **W3bstream applets** provide off-chain compute pipelines that validate biometric records before they hit chain, preserving the EVM gas economy
- **IoTeX EVM** provides cheap (sub-cent per transaction) on-chain anchoring for biometric continuity commitments
- **LayerZero V2 OApp** provides cross-chain bridge primitives for VHP (Verified Human Proof) credential portability
- **AssemblyScript W3bstream applets** enable WASM-compiled ECDSA-P256 signature validation in the applet layer

QorTroller leverages all five primitives in a single integrated DePIN architecture. The result: a 228-byte cryptographic record per cognition cycle, validated in a W3bstream applet, anchored on IoTeX L1, composable from any consuming smart contract via a single view call (`isFullyEligible(deviceId)`).

---

## 3. QorTroller architecture overview

QorTroller spans eight architectural layers, each with distinct responsibilities and verifiable evidence surfaces.

```
┌──────────────────────────────────────────────────────────────────┐
│ Frontend SPA (React/R3F/Vitest)                                  │
│   6 tabs: Gamer · Developer · Manufacturer · BRP · Marketplace · │
│   VPM + Evidence OS forensic replay workspace                    │
├──────────────────────────────────────────────────────────────────┤
│ Bridge service (Python asyncio · 29+3 agents · ~1.3GB SQLite)    │
│   - PITL Nine-Level Stack (L0-L6 + L2B/L2C)                      │
│   - PoAC record emission per cognition cycle                     │
│   - Operator Initiative live-write executor (PATH-B v2)          │
│   - 14 Mythos audit guardrails                                   │
├──────────────────────────────────────────────────────────────────┤
│ IoTeX L1 smart contracts (49 deployed at chain ID 4690)          │
│   - PITLSessionRegistry · AdjudicationRegistry · AgentScope ·    │
│     SeparationRatioRegistry · VAPIDataMarketplaceListings ·      │
│     Groth16VerifierZKSepProof + 43 more                          │
├──────────────────────────────────────────────────────────────────┤
│ W3bstream applets (AssemblyScript → WASM)                        │
│   - validate_poac_record (ECDSA-P256 + chain submission)         │
│   - process_gsr_packet (deferred — gated on N≥30 calibration)    │
├──────────────────────────────────────────────────────────────────┤
│ Hardware layer (Sony DualShock Edge CFI-ZCP1)                    │
│   - USB-C dual-connection (bridge laptop + PS5 BT)               │
│   - 1000 Hz HID polling on Edge over USB                         │
│   - Adaptive trigger force curves (PRIMARY discriminator)        │
│   - Touchpad capacitive · stick noise · IMU · lightbar           │
└──────────────────────────────────────────────────────────────────┘
```

The data flow per cognition cycle:

1. Controller emits HID + IMU + trigger curve data at ~1 kHz
2. Bridge `dualshock_integration` module reads HID; runs PITL Nine-Level Stack
3. PoAC record generated: 164-byte signed body + 64-byte ECDSA-P256 signature = 228 bytes total
4. Record_hash = SHA-256(raw[0:164]) — body only, NOT 228 bytes — anchored as chain link
5. GIC chain link computed from session adjudication output, appended to grind chain
6. Spending log (if executor authorized) records any chain operations fired
7. Frontend SPA queries bridge HTTP endpoints (localhost:8080) for live state visualization

This whitepaper details each layer in §4–§11.

---

## 4. Cryptographic primitives — FROZEN-v1 family

QorTroller publishes a family of cryptographic primitives under FROZEN-v1 discipline. Each primitive has a byte-domain tag, defined preimage structure, and immutable on-disk + on-chain location. The discipline ensures that any change to a primitive's byte layout requires an explicit v2 migration with a new domain tag and operator authorization.

### 4.1 Precise primitive count

The protocol publishes **13 commitment-family FROZEN-v1 cryptographic primitives plus one hash-function capability** (POSEIDON-BN254-AS) as of 2026-05-30 (Arc 6 PoSR freezing the 13th family `VAPI-TEMPORAL-BEACON-v1`). The commitment-family primitives produce 32-byte SHA-256 commitments over structured byte-domain preimages; the hash capability is a Poseidon-over-BN254 hash function used inside ZK circuit composition. (Two further byte-tagged *capabilities* — BT-WITNESS-v1 and its reserved BLE variant — are likewise not commitment families.)

A flat statement of "14 primitives" would conflate commitment families with the hash capability. A grant evaluator with a cryptographer on staff should read the precise distinction: **13 commitment-family + 1 hash capability**. This follows the operator's R3 refinement of the POSEIDON-AS framing (family vs capability). **v6.1 reconciles the family count from 11 to 12 to match the canonical PATTERN-017 frozenset; v6.2 (2026-05-30) adds VAPI-TEMPORAL-BEACON-v1 as the 13th family** (§4.2 row 13), enabling Arc 6 Proof of Session Recency without modifying any prior frozen family. **PoAC is the 228-byte wire-format record (§4.5), the substrate these families commit over — not itself a PATTERN-017 commitment family.**

### 4.2 Commitment-family primitives — detailed

> **Note:** PoAC (the 228-byte wire-format record, §4.5) is the substrate these families commit over — it is **not** a PATTERN-017 commitment family and is not counted among the 12 below. The table is ordered to match the canonical `_PATTERN_017_FROZEN_TAGS` frozenset (the audit's source-of-truth).

| # | Primitive | Domain tag | Preimage structure | Output |
|---|---|---|---|---|
| 1 | **GIC** (Grind Integrity Chain) | `VAPI-GIC-GENESIS-v1` | `prev_gic[32] ‖ commitment[32] ‖ verdict[1] ‖ host[1] ‖ ts_ns_be[8]` (74B) | SHA-256 → 32B |
| 2 | **WEC** (Watchdog Event Chain) | `VAPI-WEC-GENESIS-v1` | `prev[32] ‖ code[1] ‖ pid[4] ‖ sid_hash[16] ‖ ts_ns_be[8]` (61B) | SHA-256 → 32B |
| 3 | **VAME** (Agent Mid-cycle Evidence) | `VAPI-VAME-v1` | `tag[12] ‖ chain_head[16] ‖ ts_ns_be[8] ‖ endpoint ‖ body_bytes` | SHA-256 → 32B |
| 4 | **CORPUS-SNAPSHOT-v1** | `VAPI-CORPUS-SNAPSHOT-v1` | `tag[24] ‖ wiki_hash[32] ‖ agent_root[32] ‖ ratio_milli_be[8] ‖ corpus_n_be[8] ‖ ts_ns_be[8]` | SHA-256 → 32B |
| 5 | **CONSENT-v1** | `VAPI-CONSENT-v1` | `tag[15] ‖ device_id_b32 ‖ category_bitmask_be[4] ‖ expires_at_be[8] ‖ ts_ns_be[8]` | SHA-256 → 32B |
| 6 | **BIOMETRIC-SNAPSHOT-v1** | `VAPI-BIOMETRIC-SNAPSHOT-v1` (26B) | `tag[26] ‖ feature_dim_be[1] ‖ n_players_be[1] ‖ sorted_player_ids[N] ‖ centroids_scaled_be[N×F×8] ‖ cov_inv_scaled_be[F×F×8] ‖ ts_ns_be[8]` (scale factor 1e9 FROZEN; for AIT F=4 N=3 → 263B) | SHA-256 → 32B |
| 7 | **LISTING-v1** (Phase 238 PALL) | `VAPI-LISTING-v1` (15B; source self-documents the original 16B design approximation — 15B is the correct count) | `tag[15] ‖ sepproof_commitment[32] ‖ biometric_snapshot_hash[32] ‖ corpus_snapshot_hash[32] ‖ gic_hash[32] ‖ consent_bitmask_be[4] ‖ data_class_be[1] ‖ price_micro_iotx_be[8] ‖ ipfs_cid_hash[32] ‖ ts_ns_be[8]` (229B; MARKETPLACE consent bit MUST be set) | SHA-256 → 32B |
| 8 | **FRR** (Fleet Readiness Root) | `VAPI-FRR-v1` (11B) | `tag[11] ‖ sorted_by_agent_id(agent_id_be[32] ‖ phase_code[1]) for each agent ‖ ts_ns_be[8]` (phase codes FROZEN: O0=0x00, O1_SHADOW=0x01, O2_SUGGEST=0x02, O3_ACT=0x03, UNKNOWN=0xFF; for 3 agents → 118B) | SHA-256 → 32B |
| 9 | **ZKBA-ARTIFACT-v1** | `VAPI-ZKBA-ARTIFACT-v1` (21B) | `tag[21] ‖ zkba_class_byte[1] ‖ proof_weight_byte[1] ‖ n_components_byte[1] ‖ sorted_component_hashes[n×32] ‖ ts_ns_be[8]` (ZKBAClass FROZEN enum: AIT=1, GIC=2, VHP=3, HARDWARE=4, CONSENT=5, TOURNAMENT=6, MARKET=7; total 24 + n×32 bytes) | SHA-256 → 32B |
| 10 | **AGENT-COMMIT-v1** | `VAPI-AGENT-COMMIT-v1` (20B) | `tag[20] ‖ agent_id[32] ‖ commit_sha[20] ‖ prev_commit_hash[32] ‖ repo_uri_sha[32] ‖ ts_ns_be[8]` (144B; agent_id = bytes32 of ioID DID + TBA binding; commit_sha = git SHA-1; 32 zero bytes for genesis prev) | SHA-256 → 32B |
| 11 | **VAPI-O3-SUPERSEDE-v1** | `VAPI-O3-SUPERSEDE-v1` | `tag[20] ‖ agent_id[32] ‖ draft_count[8] ‖ disagreement_milli[4] ‖ bundle_drift_30d[4] ‖ scope_drift_30d[4] ‖ dual_key[1] ‖ kms_hsm[1] ‖ github_oauth[1] ‖ marketplace_role[1] ‖ fp_milli[4] ‖ shadow_age_hours[4] ‖ ts_ns_be[8]` (92B) | SHA-256 → 32B |
| 12 | **PHYSICAL-DATA-ATTESTATION-v1** | `VAPI-PHYSICAL-DATA-ATTESTATION-v1` (33B) | `tag[33] ‖ hardware_data_hash[32] ‖ agent_id[32] ‖ attestation_type_hash[32] (keccak256 of canonical type string) ‖ ts_ns_be[8]` (137B; inner type-hash uses keccak256, outer hash SHA-256 — both part of the v1 freeze) | SHA-256 → 32B |
| 13 | **TEMPORAL-BEACON-v1** (Arc 6 PoSR, FROZEN 2026-05-30) | `VAPI-TEMPORAL-BEACON-v1` (23B) | **Open commitment:** `tag[23] ‖ open_block_be[8] ‖ open_block_hash[32] ‖ device_id_32[32] ‖ poac_genesis_link[32]` (127B). **Close commitment:** `tag[23] ‖ close_block_be[8] ‖ close_block_hash[32] ‖ open_beacon_commitment[32] ‖ poac_final_link[32]` (127B); close chains to open via `open_beacon_commitment` (INSEPARABILITY claim, INV-POSR-002). On-chain anchor via `VAPITemporalBeaconRegistry` (FROZEN BEACON_DOMAIN = keccak256("VAPI-TEMPORAL-BEACON-v1"), ANCHOR_CADENCE=64 blocks) closes the BLOCKHASH-window gap (~11 min empirical on IoTeX testnet). | SHA-256 → 32B |

### 4.3 The capability primitive

**POSEIDON-BN254-AS** is a hash function capability (Poseidon hash over the BN254 elliptic curve) used inside Groth16 ZK circuit composition. It is not a commitment-family primitive — there is no preimage with a domain tag prefix. Its role is to enable circuit-internal hashing during ZK proof generation. The W3bstream applets relay (not compute) the resulting circuit-bound commitments.

### 4.4 FROZEN-v1 discipline

Each primitive is committed under FROZEN-v1 discipline:

- **Byte layout immutable**: changing the preimage structure requires v2 migration with new domain tag
- **Domain tag prefixed**: all commitment-family primitives use the `VAPI-<name>-v<n>` byte-prefix convention; even after the QorTroller rename, these byte literals stay `VAPI-` as Layer C technical infrastructure for the V.A.P.I. category
- **Sanity self-checks**: byte-length checks at preimage-construction sites guard against silent byte-layout drift
- **Sibling cross-checks**: each primitive's byte-construction code has a parallel sibling check that catches a typo before it lands on chain

### 4.5 The PoAC wire format — load-bearing

The 228-byte PoAC record is the load-bearing cryptographic primitive that all higher layers build on. The byte layout:

```
Offset  Length  Field
0       16      Magic + version + counter (anti-replay)
16      4       Cheat code byte + reserved
20      32      Device ID hash (keccak256(pubkey))
52      32      Session ID
84      40      Biometric feature vector (5 × float64 normalized to 8B fixed-point)
124     8       Timestamp (nanoseconds, big-endian)
132     32      Previous chain link hash
                                                ↑ end of body (164B)
164     64      ECDSA-P256 signature over SHA-256(body[0:164])
                                                ↑ end of record (228B)
```

This format has been FROZEN since the foundational Phases (17 through ~60). The chain link hash is `SHA-256(raw[0:164])` — body bytes only, NOT 228 bytes. This subtle invariant has been preserved across every protocol revision because changing it would require atomic migration of every consuming smart contract.

### 4.6 QorTroller-namespace frozen families (FC-(a); v6.1)

Distinct from the 12 VAPI Layer-C commitment families (§4.2), the protocol publishes a **QorTroller-branded namespace** (QRESCE-0001) for QorTroller-era primitives, frozen 2026-05-24 in the Phase B freeze ceremony. Per **Decision FC-(a)** the two namespaces are tracked **separately**: the VAPI Layer-C `frozen_v1_commitment_family_count` stays **12**, and a separate **`qortroller_commitment_family_count` = 1** tracks frozen QorTroller-branded commitment families. (The `VAPI-` prefix on the 12 Layer-C families is permanent technical infrastructure under brand-lock discipline; the QorTroller namespace uses the `QORTROLLER-` prefix.) A parallel `mythos_qortroller_crypto_drift` scanner audits this namespace, leaving the VAPI `mythos_crypto_drift` byte-identical.

| QorTroller commitment family | Domain tag | Preimage structure | Output |
|---|---|---|---|
| **iPACT renewal cadence (③)** | `QORTROLLER-IPACT-RENEWAL-v1` (27B) + genesis `QORTROLLER-IPACT-RENEWAL-GENESIS-v1` (35B) | `tag[27] ‖ device_id[32] ‖ token_id[8] ‖ prev_commitment[32] ‖ epoch_index[8] ‖ reattest_proof[32] ‖ ts_ns[8]` (147B; `IPACT_RENEWAL_EPOCH_DAYS=90`) | SHA-256 → 32B |

Two further QorTroller-namespace primitives are frozen (PV-CI-pinned) but are **not** commitment families, so they do **not** count toward `qortroller_commitment_family_count`:
- **Composite-sig v1.1 (①)** — a *signature* primitive (ECDSA-P256 + ML-DSA / SLH-DSA, draft-ietf-lamps-pq-composite-sigs-16). Its wire format is pinned: `PREFIX` (32B), the 3 `COMPSIG-*` labels, the length-prefixed envelope, and the v1.1 public-key format. Like the PoAC record (§4.5), it is a signature, not a commitment family.
- **iPACT challenge (CHALLENGE)** — `QORTROLLER-IPACT-CHALLENGE-v1` (29B), a capability tag for the challenge protocol step (mirrors POSEIDON-BN254-AS §4.3 / BT-WITNESS being capabilities, not families).

---

## 5. PITL Nine-Level Stack — anti-cheat verification

The Player-in-the-Loop (PITL) stack runs nine independent verification layers per session. Each layer produces a structured event with a code byte; humanity probability is computed by weighted combination.

### 5.1 Layer-by-layer

| Layer | Code | Type | Signal | Status |
|---|---|---|---|---|
| L0 | — | Structural | HID device presence (DualShock connected?) | Always-on |
| L1 | — | Structural | PoAC chain integrity (records form valid prev_hash chain?) | Always-on |
| L2 | 0x28 | Hard cheat | IMU gravity vector vs HID/XInput discrepancy detector | Always-on; tournament-block |
| L3 | 0x29/0x2A | Hard cheat | TinyML behavioral classifier (wallhack/aimbot signatures) | Always-on; tournament-block |
| L2B | 0x31 | Advisory | IMU-button causal latency coherence | Always-on; humanity-prob contributor |
| L2C | 0x32 | Advisory | Stick-IMU cross-correlation (inactive in dead-zone games) | Always-on; resolves to 0.5 neutral prior in NCAA CFB 26 |
| L4 | 0x30 | Advisory | 12-feature Mahalanobis biometric fingerprint | Always-on; humanity-prob contributor |
| L5 | 0x2B | Advisory | Temporal rhythm (CV, entropy, quantization in IBI patterns) | Always-on; humanity-prob contributor |
| L6 | — | Advisory | Active haptic challenge-response (stimulus-response timing) | DISABLED by default — gated on N≥50 stimulus-response calibration |

**Hard cheat codes** `{0x28, 0x29, 0x2A}` block tournament eligibility unconditionally. Advisory layers contribute to humanity probability without blocking. **L6 is explicitly disabled by default** — activating earlier than N≥50 calibration produces unstable per-player baselines that would generate false-positive blocks against legitimate players.

### 5.2 Humanity probability formula

```
Without L6 (default operational mode):
  humanity_probability = 0.28·p_L4 + 0.27·p_L5 + 0.20·p_E4 + 0.15·p_L2B + 0.10·p_L2C

Note: p_L2C resolves to 0.5 neutral prior in dead-zone stick games (NCAA CFB 26 baseline).
The formula effectively runs as 4-signal in practice for the current game corpus.
```

The weight assignment is calibrated against the 3-player N=37 AIT corpus + the broader terminal calibration session pool (267 sessions on disk as of 2026-05-19; weights were originally derived at an earlier corpus stage and remain stable across corpus growth). Weights can be re-tuned with additional players + new game corpora; the formula is configurable in `bridge/vapi_bridge/insight_synthesizer.py`.

### 5.3 L4 calibration state (Phase 57, N=74 — distinct from current separation corpus)

The N=74 cited in this section header is the **Phase 57 hardware threshold calibration corpus** — the older `sessions/human/hw_*.json` set (74 JSON files at the root of `sessions/human/`), distinct from the current 267-session separation corpus at `sessions/human/terminal_cal_P{1,2,3}/` referenced in §5.4. The hw_* corpus established the L4 anomaly + continuity thresholds at Phase 57; subsequent terminal_cal corpus growth produced the separation ratios cited in §5.4.

The L4 layer's 12-feature Mahalanobis distance computation uses 10 active features (2 structurally zero / excluded):

| Feature | Source |
|---|---|
| trigger_resistance_change_rate (excluded; structurally zero) | L6 — disabled |
| trigger_onset_velocity_L2 / trigger_onset_velocity_R2 | trigger kinematics |
| micro_tremor_accel_variance | IMU 16-Hz band variance |
| grip_asymmetry | left-right press differential |
| stick_autocorr_lag1 / stick_autocorr_lag5 | stick analog noise floor autocorrelation |
| tremor_peak_hz / tremor_band_power | accelerometer FFT (4-15 Hz band) |
| accel_magnitude_spectral_entropy | Shannon entropy of 0-500 Hz power spectrum |
| touch_position_variance (excluded; structurally zero in gameplay) | touchpad capacitive |
| press_timing_jitter_variance | normalised inter-button-press interval variance |

**L4 thresholds** (Phase 57, N=74):
- Anomaly threshold: 7.009 (mean + 3σ)
- Continuity threshold: 5.367 (mean + 2σ)
- Inter-person separation ratio (this metric only): 0.362

These thresholds were calibrated on the foundational 74-session corpus and are configurable per-battery (touchpad / trigger / button / gameplay / resting_grip) via the Phase 124 threshold-track registry. Per-player thresholds can only tighten, never loosen — a security invariant enforced by `min()` in the calibration intelligence agent.

### 5.4 Honest calibration corpus state

QorTroller's biometric calibration is currently a **3-player corpus of 267 terminal sessions** as of 2026-05-19, verified at `sessions/human/terminal_cal_P{1,2,3}/`. A prior Player 4 designation was eliminated 2026-04-02 after confirmation that the captured sessions were the same person as Player 3; provenance anchored at `VAPI_CORPUS.md:53` ("P4 ELIMINATED — confirmed same person as P3 (2026-04-02)") with the disposition retained in `CLAUDE.md:84`. Live disk distribution:

| Player | Total terminal sessions | AIT | touchpad_corners | touchpad_freeform | touchpad_swipes | tremor_resting |
|---|---|---|---|---|---|---|
| P1 | **98** | 13 | 12 | 12 | 13 | 14 |
| P2 | **86** | 10 | 12 | 12 | 13 | 14 |
| P3 | **83** | 14 | 11 | 11 | 11 | 14 |
| **Total** | **267** | **37** | **35** | **35** | **37** | **42** |

**Reconciliation note** (surfaces drift rather than burying it): earlier internal narrative documents (e.g., `CLAUDE.md` Phase-143-era snapshot at L84-90; `VAPI_CORPUS.md` corpus table) describe smaller per-player totals reflecting older corpus growth points. The disk counts above are the ground truth as of this whitepaper's drafting and what a grant evaluator running `scripts/analyze_interperson_separation.py` against `sessions/human/terminal_cal_P{1,2,3}/` will find.

The separation ratio per probe type — the load-bearing cross-player discriminability metric. Note that each `N` below is the **separation analysis baseline** at the time the ratio was measured (Phase 229 for AIT; Phase 202 for tremor_resting; Phase 121 for touchpad_corners). The disk corpus has grown beyond those analysis-time N values for some probe types; the ratios remain honest empirical evidence at the analysis baseline, but a re-run analysis against today's larger corpus would produce updated figures:

| Probe type | N | Ratio | Status |
|---|---|---|---|
| AIT (Active Isometric Trigger) | 37 (P1=13/P2=10/P3=14) | **1.199** (all-pairs cleared) | ✓ first probe type to clear all-pairs > 1.0; meaningful empirical evidence the biometric layer discriminates |
| touchpad_corners | 35 | **0.728** | ⚠ Tournament BLOCKER — required > 1.0 before BLOCK enforcement |
| tremor_resting *(under recapture — not cleared)* | 27 | 1.177 (excludes P1vP3 — all_pairs_p0_ok=False, P1vP3=0.032 corpus-specific issue) | Excluded from the readiness surface pending P1vP3 corpus recapture; mainnet TGE invariant remains in force |
| Pooled free-form | 127 | 0.417 | Expected/known — free-form gameplay doesn't separate players (WIF-009 plateau regime); never used as tournament gate |

**Honest framing for grant evaluation**: AIT clearing all-pairs > 1.0 at ratio 1.199 is real empirical evidence that the biometric layer CAN discriminate human players at the per-trigger level. The touchpad_corners ratio at 0.728 remains the tournament BLOCK enforcement gate. The mainnet TGE invariant "no token launch before separation_ratio > 1.0 confirmed" remains in force for token-issuance economic defensibility, distinct from the development-stage progress gate.

**The honest gap**: a 3-player corpus is not a production-scale biometric calibration. Scaling to N=10+ players × 100+ sessions each — Empirical Unknown #1 from the canonical sensor-stack v2.1 anchor — is the load-bearing measurement gate that must complete before the v2 L4 architecture exits draft state. Grant funding accelerates this work directly.

---

## 6. Smart contract architecture

### 6.1 53 contracts deployed at IoTeX testnet (chain ID 4690)

The full address inventory is `contracts/deployed-addresses.json` (53 substantive contracts as of 2026-05-30; +4 from the Arc 5 + Arc 6 deploy day documented in `docs/data-economy-deploy-hold-and-arc5-readiness.md` and the Arc 5 ceremony transcript at `docs/data-economy-arc5-ceremony-transcript.md`). Key contracts grouped by function:

**Core verification + composability:**
| Contract | Address | Role |
|---|---|---|
| `PITLSessionRegistry` | `0x8da0A497234C57914a46279A8F938C07D3Eb5f12` | Per-session ZK proof + chain link anchoring |
| `PitlSessionProofVerifier` | `0x07D3ca1548678410edC505406f022399920d4072` | Groth16 verifier (~1820 constraints; BN254; 2^11 powers of tau) |
| `Groth16VerifierZKSepProof` | `0xD63EEf1372Cb496071bf963bEE395F7e0A3f2Ab6` | ZK-SEPPROOF biometric continuity verifier |
| `ZKSepProofVerifier` | `0xd51a21E234a800a6621f4c23a8fcA44e3bF01002` | ZK-SEPPROOF wrapper interface |
| `VAPIProtocolLens` | (FROZEN-v1 Layer C name) | Single composable `isFullyEligible()` view call |
| `VAPIDualPrimitiveGate` | `0xd7b1465Aad8F815C67b24681c9c022CED24FB876` | Combined isFullyEligible + PoAd composability |
| `AdjudicationRegistry` | `0x44CF981f46a52ADE56476Ce894255954a7776fb4` | PoAd hash anchoring (anti-replay UNIQUE poadHash) |

**Operator Initiative + Cedar policy:**
| Contract | Address | Role |
|---|---|---|
| `AgentScope` | `0xc694692a69bbf1cDAda87d5bc43D345C4579FF13` | Operational scope_root storage (agentId → scopeRoot) |
| `AgentRegistry` | `0x9548E9d17c2d40350629b1b88ff1D2c01B0414a4` | Governance-layer scope commitment |
| `VAPISwarmOperatorGate` | `0x969c0F1EFb28504a95Acf14331A59FBCb2944F98` | Multi-signer operator gate for ioSwarm (min 3 distinct stakers) |
| `CeremonyAuditRegistry` | `0xb9164E6d74Dde1508df2a39b01d3702ACC8230C2` | ZK ceremony participant audit trail |

**Biometric + identity:**
| Contract | Address | Role |
|---|---|---|
| `SeparationRatioRegistry` | `0xB39CeE732cf91c93539Bd064D9426642a095a026` | On-chain proof of biometric calibration commitment |
| `VHPReenrollmentBadge` | `0x42E7A25d0E5667BBae45e5cF33a6e2CC6E42d45C` | Soulbound re-enrollment credential |
| `ProtocolCoherenceRegistry` | `0xfAfe4E8BEE45be22836b90D542045510dDd927Dd` | agent-fleet Merkle root anchoring |
| `VAPIBiometricGovernance` | `0x06782293F1CFC1AA30C0Baee0437c2B336796A00` | VHP-gated proposal contract |

**Marketplace + economic:**
| Contract | Address | Role |
|---|---|---|
| `VAPIDataMarketplaceListings` | `0x78Df84Cc512EdCaC0e58a03e4852627E2F62E3bC` | Curator-suspended marketplace per LISTING-v1 |
| `VAPIBuyerCategoryVerifier` | `0x7EEc6B7Eb843532227528F63a0bC95D6cc537E53` | **Arc 2 (Data Economy) — deployed 2026-05-30.** ZK buyer-category proof (Groth16); buyer proves "I am authorized in category X" without revealing DID |
| `VAPIConsentManifestRegistry` | `0x5F7c8068D0e61818FCD613D47e68a9Ea906a2743` | **Arc 4 (Data Economy) — deployed 2026-05-30.** Gamer-self-sovereign structured consent manifest (15 v1 fields + 4 Dimension 8 fields for Arc 5 VHR consent). Solidity invariant: `msg.sender == gamer`; bridge process can never write consent on a gamer's behalf. First gamer-self-sovereign manifest written from a real wallet 2026-05-30 |

**Data Economy Arc 5 + Arc 6 — Verified Human Replay + Proof of Session Recency:**
| Contract | Address | Role |
|---|---|---|
| `Groth16VerifierVAPIReplayProof` | `0xcE56404CB2e49C3D68ABc72d2941A508Cbe75608` | **Arc 5 — deployed 2026-05-30.** snarkjs-exported Groth16 verifier from the 2026-05-30 trusted-setup ceremony (2 contributors + IoTeX block-44188831 beacon; transcript at `docs/data-economy-arc5-ceremony-transcript.md`) |
| `VAPIReplayProofVerifier` | `0x5182372d1D033db0c9230843DFDE606733D5F91B` | **Arc 5 — deployed 2026-05-30.** PROOF_TYPE = keccak256("VAPI-REPLAY-PROOF-v1"); on-chain anchor for VHR proofs binding sanitized gameplay matrix root + consent policy hash + humanity threshold + VHP commitment |
| `VAPITemporalBeaconRegistry` (PoSR + Arc 7 PQ sidecar) | Deploy held pending operator GO + multi-contributor mainnet re-ceremony | **Arc 6 — built 2026-05-30, FROZEN-v1 #14.** BEACON_DOMAIN = keccak256("VAPI-TEMPORAL-BEACON-v1"), ANCHOR_CADENCE=64 blocks (~2.8 min empirical on IoTeX testnet). Closes the ~11-min BLOCKHASH window for VHR session-recency binding. Arc 7 PQ sidecar: `verifyBeacon(block, hash, pqCommitment)` requires non-zero PQ commitment, forward-compatible with ML-DSA / SLH-DSA / hybrid composites |
| `VAPIReplayProofVerifier_v2` (PoSR wrapper) | Deploy held pending Arc 6 inner Groth16 ceremony | **Arc 6 — built 2026-05-30.** PROOF_TYPE = keccak256("VAPI-REPLAY-PROOF-v2"); coexists with v1; recency opt-in for marketplace listings until tournament operator requires |

The remaining contracts cover device registries, threat federations, PHG credentials, identity continuity, progress attestation, skill oracles, and federated threat registration. Full architectural detail at `contracts/`.

### 6.2 Composability — the single-call invariant

QorTroller is designed for protocol composability via a single on-chain view call:

```solidity
// Any consuming contract can call this to gate any action:
bool eligible = VAPIProtocolLens.isFullyEligible(deviceId);
```

The view call internally checks: VHP credential validity, PoAC chain integrity, manufacturer certification status, no active adjudication block, biometric staleness within tolerance. A consuming dApp (a tournament smart contract, a leaderboard, a staking pool gating reward distribution) only needs this single view call to decide whether to permit an action.

### 6.3 LayerZero V2 OApp — VHP cross-chain portability

The `VAPIVerifiedHumanProofBridge` enables VHP credential portability across L1 endpoints via LayerZero V2's OApp pattern. `abi.encode` for message encoding; `setPeer()` trust model; explicit nonce anti-replay. Currently single-direction (IoTeX → other L1 endpoints); reverse path reserved for v2.

---

## 7. The Operator Initiative — bounded autonomous agents

### 7.1 The 4-rung ladder

QorTroller's autonomous-agent layer progresses through four phases of bounded autonomy:

```
Phase O0 (DORMANT) → O1_SHADOW → O2_SUGGEST → O3_ACTING
       ↓                ↓             ↓             ↓
   no authority     read-only     drafts only   bounded write authority
   on chain         observation   for operator  per Cedar policy
                                  review
```

**Current state**: all three agents (Sentry, Guardian, Curator) at **O3_ACTING** on IoTeX testnet, anchored 2026-05-17 via the operator-authorized `parallel_o3_act_anchor` ceremony.

### 7.2 Agent-specific authority

| Agent | Q9 agent_id | O3 capability | Cedar lane | Per-op cost |
|---|---|---|---|---|
| **Sentry** | `0xb21e1ec2…3a27e3e42c` | `pda-attestation-anchor` | `lane://provenance/**` | ~0.0008 IOTX per anchor |
| **Guardian** | `0xbd8c7fba…3ce5fa38d1` | `audit-drafting` | `lane://audits/**` | 0 IOTX (LOCAL writes only) |
| **Curator** | `0xed6a2df5…1fda11a8` | `marketplace-listing-suspend` | `chain://iotex-testnet` | ~0.001 IOTX per suspension (reversible) |

### 7.3 Six-layer defense-in-depth

QorTroller's autonomous-agent design enforces six independent default-deny safety layers. Each layer is independently lift-able by the operator; chain operations require all six to permit:

| # | Layer | Type | Current state |
|---|---|---|---|
| 1 | `CHAIN_SUBMISSION_PAUSED=true` | Bridge final defense | held |
| 2 | `PHASE_O3_EXECUTOR_AUTOLOOP_ENABLED` | v2 master wire | true (activated 2026-05-19) |
| 3a | `PHASE_O3_ANCHOR_SENTRY_LIVE_WRITES_ENABLED` | Sentry per-agent flag | false (default) |
| 3b | `PHASE_O3_GUARDIAN_LIVE_WRITES_ENABLED` | Guardian per-agent flag | true (intentional baseline; LOCAL writes only) |
| 3c | `PHASE_O3_CURATOR_LIVE_WRITES_ENABLED` | Curator per-agent flag | false (default) |
| 4 | `PHASE_O3_EXECUTOR_KILL_ALL` | Emergency hatch | false |
| 5 | Per-agent daily IOTX budgets | Cost cap | 0.05 each (10× tighter than 0.5 architectural default) |
| 6 | `mythos_spending_log_drift` | Runtime guardrail | active (MCP Tool #29) |

**Zero IOTX has been spent autonomously.** This is the protocol's deliberate operational posture: agents have on-chain attested O3_ACTING authority with Cedar-policy-bounded write scopes, behind six independent default-deny gates, with kill-all kept disengaged. The protocol is production-ready; autonomous chain activity remains structurally prevented until each layer is explicitly lifted.

### 7.4 The 2026-05-17 ceremony evidence

Operator-authorized `parallel_o3_act_anchor.py --confirm` fired at 15:27:19Z UTC on 2026-05-17 after quadruple-gate verification. Six transactions landed on IoTeX testnet:

| Agent | Operational tx | Governance tx | Block timestamp |
|---|---|---|---|
| Sentry | `0xd07492fb6fdc4e735c02…` | `0x8ebef76b6fd773116d9c…` | 15:27:19Z |
| Guardian | `0x3678e71c32b0435e1a51…` | `0xdd4c8154019a4ccbb484…` | 15:27:35Z |
| Curator | `0xdbd13ca1d100cc320363…` | `0x2644949ffcf6d5e18df0…` | 15:27:49Z |

**Fleet Readiness Root** permanently committed: `0x54b4b698e9a81415034bfa72d82517f78343447e364f5ee5071f4898ce8bca37`

**Cost**: 15.083226 → 14.903826 IOTX (0.179400 IOTX total — 16× under the 3.0 IOTX budget cap).

**Cryptographic justification chain**: the 504-hour shadow_age calendar gate was empirically superseded by `VAPI-O3-SUPERSEDE-v1` attestations (rows 4–6 in `operator_initiative_auto_supersede_log`). Each attestation cryptographically commits to the gate-state values such that any third party with the gate values can recompute and verify the attestation hash byte-identically.

### 7.5 Curator graduation — honest transparency

Curator was anchored directly at O3_ACTING via the 2026-05-17 ceremony, bypassing the formal O2_SUGGEST graduation gate (criteria: N≥50 reviews + 0 false-positive rate per the pre-authored `curator_o2_suggest_v1.json` Cedar bundle). The direct anchoring is a legitimate operator-authority pathway; the **Mythos-Curator-Graduation-Audit variant** (13th variant, shipped 2026-05-19 commit `4f8068e9`) surfaces this transparently:

- `CURATOR_DIRECT_O3_BYPASS_DOCUMENTED` — fires while Curator is at O3_ACTING; honest disclosure of the bypass
- `CURATOR_GRADUATION_BACKFILLED` — would fire when N≥50 reviews accumulate (direct-O3 then post-hoc justified by empirical evidence)
- `CURATOR_GRADUATION_PENDING` — currently fires (N=0 reviews because chain_writes_enabled=False)

This whitepaper explicitly does NOT claim Curator graduated through the formal review-pace gate. The honest framing: "Curator anchored at O3_ACTING via operator-authorized 2026-05-17 ceremony; formal review-pace gate empirical validation pending operational activity."

---

## 8. Mythos audit framework — 14 guardrails

QorTroller publishes 14 Mythos audit variants that monitor specific drift surfaces continuously. Each variant is a deterministic, fail-open async function. Findings with `frozen_region=True` automatically force tier-3 (read-only) at the store layer per `INV-MYTHOS-FROZEN-PROTECTION-001` — Mythos NEVER auto-fixes FROZEN material.

| # | Variant | Surface | Primary severity |
|---|---|---|---|
| 1 | `mythos_frozen_drift` | PV-CI invariant gate output | HIGH (frozen) |
| 2 | `mythos_stability_sweep` | Async hazard patterns | HIGH/MEDIUM |
| 3 | `mythos_operator_initiative_audit` | Cedar bundles + Q9 hex + Merkle sync + parallel scripts | CRITICAL/HIGH |
| 4 | `mythos_crypto_drift` | Cryptographic primitive byte-domain integrity | HIGH (frozen) |
| 5 | `mythos_methodology_drift` | Methodology layer artifacts | HIGH/MEDIUM |
| 6 | `mythos_ceremony_drift` | Ceremony attestation integrity | HIGH (frozen) |
| 7 | `mythos_live_gameplay_audit` | Real-time gameplay session integrity | HIGH/MEDIUM |
| 8 | `mythos_post_o3_ceremony_audit` | activation_log + on-chain scopeRoot + OpInit cross-ref | CRITICAL/HIGH |
| 9 | `mythos_corpus_drift` | Separation ratio + GIC chain + AIT defensibility | LOW informational |
| 10 | `mythos_claude_md_curation` | Documentation staleness + size + superseded NOTEs | LOW/MEDIUM |
| 11 | `mythos_frontend_brand_drift` | JSX/HTML display VAPI strings vs QorTroller brand | MEDIUM |
| 12 | `mythos_spending_log_drift` | PATH-B v2 spending_log runtime audit | CRITICAL/HIGH/MEDIUM |
| 13 | `mythos_curator_graduation_audit` | Curator O2 graduation criteria + direct-O3 transparency | LOW informational |

All 13 are invokable via MCP tools (Tool #18 through Tool #30 in `vapi-mcp/unified_server.py`). The Mythos cadence engine auto-fires them on schedule when the bridge runs. The framework constitutes the protocol's self-verification surface: any drift in any surface auto-surfaces without manual audit work.

---

## 9. Honest threat model

### 9.1 What the protocol defends against

**Adversarial class 1 — software cheats**: aimbots, wallhacks, ESP. The PITL stack's hard-cheat layers L2 + L3 detect at L2 (IMU/HID divergence) and L3 (TinyML behavioral classifier output). Both produce hard codes `{0x28, 0x29, 0x2A}` that block tournament eligibility unconditionally. Evidence is cryptographically anchored in the PoAC record's cheat code field.

**Adversarial class 2 — hardware translators** (Cronus Zen, XIM Apex, reWASD): the adaptive-trigger primary discriminator (per the sensor-stack v2.1 canonical anchor) is the strongest defense. Translator-class hardware does not synthesize biomechanically-structured continuous force curves; per-trigger biometric fingerprinting via L4 + AIT separation discriminates legitimate human force-curve patterns. Inter-subject EER 1-15% lab-to-field per the literature anchor (Saevanee 2009 / Antal 2015 / Wakita 2006 / Miyajima 2007 / Van Vugt 2013).

**Adversarial class 3 — cloud-gaming bots**: this is the structural gap NVIDIA GeForce NOW's anti-cheat compatibility guide concedes. QorTroller's response is the optical witness channel (Surface 4 in the sensor-stack v2.1 anchor): a tournament-station camera observes host-issued 3-color lightbar symbol streams at 5–15 symbols/second producing 25–75 bits over a 5-second authentication window. This is a passive presence-attestation analog to the LAN-tower BlueZ BT witness, with the advantage of fully-passive camera observation (no physical infrastructure in the gamer's home).

**Adversarial class 4 — account sharing / boosting**: the biometric layer detects per-player fingerprint divergence within sessions. L4 + L5 + AIT separation produce strong evidence when a session's biometric vector drifts from the registered VHP holder's calibration. The current 3-player N=37 corpus produces ratio 1.199 (all-pairs > 1.0 for AIT), demonstrating the discriminator works empirically.

### 9.2 What the protocol does NOT defend against

This whitepaper explicitly names what is OUT of scope:

**Out of scope — replay attacks on biometric records**: prevented at protocol layer by per-record counter + chain link prev_hash; not a threat the biometric layer addresses, but a primitive guarantee of the PoAC format.

**Out of scope — non-DualShock-Edge controllers** at v6: only DualShock Edge CFI-ZCP1 is certified. Generic Xbox / Switch / Standard PS5 controllers fall into the Phase 155 Standard tier with reduced biometric depth (L0-L5 only; no L6 + adaptive trigger force curve). Other Edge-class controllers (steering wheels, flight sticks) require V.A.P.I.-compliant project extensions in the ecosystem.

**Out of scope — N≥3 same-model controller separability**: cross-tournament VHP portability requires demonstrating that two different DualShock Edge units of the same Sony manufacture batch can be biometrically distinguished from each other. This is the canonical Empirical Unknown #4 from the sensor-stack v2.1 anchor; the study does not exist in public literature and is gated behind explicit pre-corpus measurement work. Until completed, VHP claims are session-bound presence only.

**Out of scope — sub-perceptual L6 challenges**: L6 is disabled by default. Activating earlier than N≥50 per-player stimulus-response calibration produces false-positive blocks. The protocol does NOT claim L6 anti-cheat capability at v6; this is explicitly deferred per the calibration-gate discipline.

**Out of scope — non-IoTeX chain anchoring**: VHP credential portability via LayerZero V2 is single-direction (IoTeX → other L1s) at v6. The reverse path (returning to IoTeX with cross-chain attestations) is reserved for v2 of the bridge.

**Out of scope — formal trademark protection**: USPTO TESS clearance was self-conducted by the operator (5/5 queries clean across exact + phonetic + space + hyphen + stem wildcard + Q-prefix in classes 9/38/42). Attorney clearance opinion deferred per pre-revenue project policy. USPTO TEAS Plus filing ($750 estimated for 3 classes) deferred until revenue or external funding event. This is a known operator-side gap; not a protocol-layer threat.

### 9.3 Privacy + GDPR Art. 17 enforcement

QorTroller's gamer-sovereignty discipline is enforced at the smart contract layer, not just narrative:

- **Per-category consent** via `VAPIConsentRegistry` — gamers grant consent per category (TOURNAMENT_GATE / ANONYMIZED_RESEARCH / MANUFACTURER_CERT / MARKETPLACE) independently
- **`msg.sender == gamer` enforcement** — consent grant/revoke must be called by the gamer's own wallet; the bridge can read consent state via view calls but cannot grant/revoke on behalf of the gamer (this is the gamer-self-sovereignty invariant)
- **FSCA contradiction rule `CONSENT_REVOKED_BUT_DATA_FLOWING`** — detects within ≤5 minutes if data continues flowing after gamer revokes consent; this is the GDPR Art. 17 ("right to erasure") enforcement primitive
- **FSCA contradiction rule `CONSENT_REVOKED_LISTING_ACTIVE`** — Phase 238 critical rule: detects marketplace listings that should be suspended because the underlying consent was revoked

These primitives are FROZEN-v1 at the byte layer (CONSENT-v1 commitment); the discipline holds across protocol upgrades.

---

## 10. Tokenomics (deferred per separation ratio gate)

### 10.1 Token launch sequencing — non-negotiable invariant

QorTroller's mainnet TGE (Token Generation Event) is **explicitly gated** behind the load-bearing biometric defensibility metric:

> **Hard rule from `CLAUDE.md`**: "no TGE before separation_ratio > 1.0 confirmed"

The current touchpad_corners separation ratio at 0.728 is below this threshold. Until hardware-recapture work brings touchpad_corners > 1.0 (or another probe type meets the all-pairs > 1.0 criterion), the protocol does not launch its token. This is for **legal/economic defensibility of token issuance** — the token's utility claim requires the underlying biometric layer to actually discriminate, and the separation ratio is the load-bearing empirical evidence of that discrimination.

The mainnet TGE invariant is enforced at the FSCA contradiction-rule layer; any attempt to call the TGE-related contract function while separation_ratio < 1.0 produces an immediate contradiction event.

### 10.2 Token utility design (architecturally specified; mainnet deploy gated)

The `VAPIToken` contract (architecturally specified; mainnet deploy gated on TGE invariant) is designed as utility, not speculation:

| Mechanism | Direction |
|---|---|
| Operator staking | Stake VAPIToken → run W3bstream applet → earn rewards per validated record |
| Hardware certification | Pay VAPIToken to register certified device under manufacturer credential |
| Data marketplace | Pay VAPIToken (or receive) for VAPI-verified gameplay data (consent-bound; per LISTING-v1) |
| Reward multiplier | Higher tier (verified-LISTING-v1 with provenance recording) → multiplier 1× / 1.5× / 2.0× / 3.0× per `getMarketplaceTier()` cryptographic check |
| Slashing | Misbehaving operators (validation errors, attestation forgery attempts) → slashed VAPIToken |

### 10.3 Mainnet deploy package (Phase 99; smoke-tested clean)

The Phase 99 deploy package — 6 contracts (`VAPIToken`, `VAPIOperatorRegistry`, `VAPIHardwareCertRegistry`, `VAPIGSRRegistry`, `VAPIVerifiedHumanProof`, `VAPIVerifiedHumanProofBridge`) — is smoke-tested clean on local Hardhat (commit `d58cbfb9`). Estimated mainnet deploy cost: ~0.022 IOTX testnet equivalent → ~5-20 IOTX mainnet depending on gas conditions. **Hard prerequisite**: separation_ratio > 1.0 confirmed on the load-bearing probe type.

---

## 11. Roadmap and grant deliverables

### 11.1 What an IoTeX grant directly enables

Grant funding accelerates four specific tracks:

**Track A — Biometric calibration scaling (Empirical Unknown #1)**: scale from 3-player N=37 corpus to N=10+ players × 100+ sessions × 3 game contexts. This is the load-bearing measurement work that brings touchpad_corners > 1.0 and unblocks the mainnet TGE invariant. Estimated cost: hardware (one DualShock Edge per player ~$200 × 10 = $2000); player honoraria + recruitment ($25/session × 100 × 10 = $25,000); ~6-week measurement window with calibration intelligence agent automation.

**Track B — Hall-effect stick separability study (Empirical Unknown #4)**: N=20 stock + N=20 batched-aftermarket Edge units; resolves whether cross-session VHP claims are defensible at controller-identity level. Estimated cost: 20 stock + 20 aftermarket Edge units ($200 × 40 = $8000); 1 month measurement.

**Track C — L8 BT Calibration v1**: ship the LAN-tower-only Bluetooth Classic BR/EDR witness device per the canonical anchor at `wiki/assessments/VAPI Bluetooth Calibration_ Architectural Prerequisites and Threat Model Analysis.pdf`. Estimated cost: ~1 week engineering on the BlueZ + USB BT dongle + Python wrapper architectural prerequisite; produces the tournament-station witness device for the cloud-gaming-bot detection class.

**Track D — Mainnet deployment + sustained operation**: Phase 99 mainnet deploy (~5-20 IOTX); sustained operator funding for at least 6 months of mainnet activity; W3bstream applet production registration. Total: ~$30k-50k for the full mainnet ramp-up.

**Total grant ask**: ~$60-90k across Tracks A-D, enabling QorTroller to move from a 3-player testnet protocol to a 10+ player mainnet-deployed protocol with the separation_ratio gate cleared.

### 11.2 V.A.P.I. category ecosystem (post-grant)

Beyond QorTroller-specific deliverables, the V.A.P.I. category itself is the load-bearing strategic asset. The grant supports establishing the V.A.P.I. category as an IoTeX-ecosystem-internal DePIN sub-category with documented architectural commitments, FROZEN-v1 primitive specifications, and developer onboarding documentation. Future V.A.P.I.-compliant projects emerging from the IoTeX grant ecosystem would inherit the discipline established here.

This is the larger ecosystem play: not just QorTroller as a protocol, but V.A.P.I. as a category that QorTroller seeds.

### 11.3 Near-term post-grant priorities (operator-time)

| Priority | Item | Status |
|---|---|---|
| 1 | Self-sign R0 prereq certificate (USPTO TESS + brand-virginity evidence base sufficient) | Pending operator action |
| 2 | Domain registration (qortroller.com + .io + .ai + .network) | ~$25-50 |
| 3 | GitHub `qortroller` org reservation | Free |
| 4 | Public landing page at qortroller.io | ~$0-12/mo Vercel |
| 5 | Phase 99 mainnet deploy | Wallet refill + ~5-20 IOTX |
| 6 | IoTeX grant submission | Free |

---

## 12. Verification trail

Every load-bearing claim in this whitepaper has a verifiable evidence anchor. The cross-reference table:

| Claim category | Primary evidence anchor | Verification command |
|---|---|---|
| Test counts | Bridge tests at HEAD `4f8068e9` | `python -m pytest bridge/tests/ -q` (~10 min; expected 4377 pass) |
| PV-CI invariants | 128/128 PASS | `python scripts/vapi_invariant_gate.py` |
| Cryptographic primitives | `bridge/vapi_bridge/grind_chain.py` (GIC) + sibling primitive modules | `python -m pytest bridge/tests/test_grind_chain.py` |
| On-chain scope_roots | IoTeX testnet AgentScope contract | `python scripts/_verify_operator_initiative_chain_state.py` |
| Mythos audit cleanliness | All 14 variants returning honest findings | `python -c "import asyncio; from vapi_bridge.mythos_variants import *; ..."` |
| Brand-discipline evidence | `vsd-vault/proposals/drafts/qresce-0001-r0-artifacts/trademark_clearance_evidence.md` | Read document; verify USPTO TESS screenshots in `uspto_tess_screenshots/` |
| Calibration corpus — separation analysis | `sessions/human/terminal_cal_P{1,2,3}/` — 267 JSON files (live disk count 2026-05-19; P1=98 / P2=86 / P3=83) | `ls sessions/human/terminal_cal_P{1,2,3}/*.json \| wc -l`; run `python scripts/analyze_interperson_separation.py` |
| Calibration corpus — L4 threshold baseline | `sessions/human/hw_*.json` — 74 JSON files (Phase 57 hardware corpus, distinct from separation corpus above) | `ls sessions/human/hw_*.json \| wc -l` |
| Operator Initiative ceremony | CLAUDE.md L39 NOTE + 6 IoTeX testnet tx hashes | `eth_getTransactionReceipt` for each tx hash |
| GIC_100 chain head | On-chain at IoTeX testnet block 43348052 | `eth_getTransactionByHash(0xe807347eb…)` |
| Six-layer defense-in-depth | `bridge/.env` posture + Config field defaults | `python -c "from vapi_bridge.config import Config; ..."` |

---

## 13. References

**Terminology note — V acronym evolution**: This whitepaper standardizes on **Verifiable** Autonomous Physical Intelligence (V.A.P.I.) as the precise term for the coined DePIN sub-category. Whitepaper versions v1–v5 and the Zenodo DOI v3 historical deposit use **Verified** Autonomous Physical Intelligence; v6 changes this to **Verifiable** because verification is a continuous protocol-layer property of the data (cryptographic commitments + chain anchoring make data verifiable by any third party at any future time), whereas "Verified" implies a pass/fail state at a single moment. An evaluator pulling the v3 Zenodo DOI should expect to see "Verified"; v6 onward uses "Verifiable" — the change is named here rather than left to surprise.

[Industry anti-cheat]
- BattlEye documentation, behavioral pattern matching protocols
- EAC (Easy Anti-Cheat) kernel-level scanner specifications
- Activision RICOCHET Season 02 input-pattern detection rollout announcements (cloud-gaming-bot detection)
- NVIDIA GeForce NOW anti-cheat compatibility guide (cloud-gaming-bot stealth gap concession)

[DualSense Edge hardware]
- Sony CFI-ZCP1 product specifications
- `hid-playstation.c` (Linux kernel driver source)
- PSDevWiki — DualSense protocol reverse-engineering
- SensePost research on DualSense haptic packet structure
- DualSense-Windows + pydualsense Python wrappers

[Biometric literature]
- Saevanee 2009 — typing-pattern inter-subject EER
- Antal 2015 — controller biometric discrimination
- Wakita 2006 — temporal rhythm in human input
- Miyajima 2007 — autoregressive identification
- Van Vugt 2013 — biomechanical force-curve discrimination

[BT Calibration]
- Wu et al. RAID 2020 (BlueShield) — CFO 5.84% / RSSI 8.72% / combined 2.37% FP for BlueTooth Classic detection
- WormVision Lite MAX userscript (published 2024-12-26) — cloud-gaming bot attack instance
- BlueZ open-source Bluetooth stack documentation

[Privacy + GDPR]
- Cruz v. Fireflies AI (BIPA litigation analog)
- Beil v. Petco (capture-and-storage privacy litigation)
- GDPR Article 17 — right to erasure
- CIPA (California Invasion of Privacy Act) two-party-consent regimes

[IoTeX]
- IoTeX whitepaper + ioID DID specification
- W3bstream applet documentation + AssemblyScript bindings
- LayerZero V2 OApp specification
- QuickSilver liquid staking documentation

[Internal evidence anchors]
- `docs/qortroller-state-of-the-protocol-2026-05-19.md` — comprehensive state document (this WP v6's parallel reference)
- `docs/qortroller-brand-guidelines.md` — QRESCE-0001 v0.5 brand discipline
- `docs/qortroller-whitepaper-v5.md` — light revamp baseline
- `docs/path_b_v2_activation_runbook.md` — operator activation procedure
- `wiki/methodology/sensor_stack_v2_1_architectural_revision.md` — canonical sensor-stack anchor
- `wiki/methodology/bt_calibration_v1_1_architectural_revision.md` — canonical BT calibration anchor
- `vsd-vault/proposals/drafts/qresce-0001-r0-artifacts/trademark_clearance_evidence.md` — USPTO TESS clearance evidence

---

## BibTeX citation

```bibtex
@misc{qortroller_2026,
  title  = {QorTroller: Verifiable Autonomous Physical Intelligence (V.A.P.I.) — A Reference Implementation for Gamer-Sovereign Anti-Cheat on IoTeX},
  author = {ConWan30 (operator)},
  year   = {2026},
  month  = {May},
  note   = {Whitepaper v6 — grant-tailored.
            Brand-lock QRESCE-0001 v0.5 (commit 2c762835, 2026-05-18).
            HEAD 39f7d26d; comprehensive verification trail at \S 12.},
  url    = {https://github.com/ConWan30/QorTroller}
}
```

---

## 14. License + brand notice

**License**: TBD per repo settings; expected MIT or Apache-2.0 for code; CC BY-SA 4.0 for documentation. Current repo is private pending public launch.

**Brand notice**:
- **QorTroller** is the project name (medial-cap T; never "Qortroller" / "QORTROLLER" / "Qor Troller"). Pronunciation: **KOR-TROLL-er** (IPA `/ˈkɔːrˌtroʊlər/`).
- **V.A.P.I.** (with periods) is the coined DePIN sub-category. The variant **VAPI** (without periods) is preserved as the technical-context byte-domain prefix for FROZEN-v1 cryptographic primitives under Layer C discipline.
- Tagline: **"QorTroller — Core Controllers of their gaming data."**
- Full brand discipline: `docs/qortroller-brand-guidelines.md`

---

*Whitepaper v6 — drafted 2026-05-19 at HEAD `39f7d26d`. Supersedes v5 (light revamp) + v4 (technical baseline). Operator-curated under verification-first discipline: every load-bearing claim has a verifiable evidence anchor; no flat first-of-its-kind claims; empirical figures paired with their limits; honest gaps explicitly named. Update only when material architectural state evolves.*

*Brand-lock per QRESCE-0001 v0.5 (commit `2c762835`). Canonical repo: `https://github.com/ConWan30/QorTroller`.*
