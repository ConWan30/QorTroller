# Lessons Learned

- Always run the full test suite (`pytest` for bridge, `npx hardhat test` for contracts) before committing changes.
- The PoAC wire format is 228 bytes EXACTLY. Any change breaks firmware↔contract↔bridge compatibility.
- Biometric thresholds (Mahalanobis 3.0 anomaly, 2.0 continuity) are calibration-dependent — never hardcode without documenting the source.
- The bridge SQLite schema uses migrations tracked in `schema_versions` table — always add a migration, never alter tables directly.
- Groth16 proofs require a trusted setup ceremony — `run-ceremony.js` handles dev setup, but production requires multi-party MPC.
- When editing Solidity contracts, check gas costs with `hardhat test --gas-reporter`. The P256 precompile staticcall pattern must stay under 100K gas per individual verification.
- DualShock Edge sensor commitment schema v2 is DIFFERENT from Pebble Tracker schema v1 — the hash includes stick axes, trigger resistance state, gyro, accelerometer.
- The `OPERATOR_API_KEY` env var must be set for the gate API to function — it returns 503 otherwise (intentional graceful degradation).
- BridgeAgent `_execute_tool()` uses `inputs` dict (not `args`) — consistent across all 18 tools.
- `create_operator_app()` is a factory — rate limiter, agent, all state lives in the closure, not globally.
- InsightSynthesizer Mode 5 (Phase 37): evidence hash is `SHA-256(f"{device_id}:{digest_id}")` referencing immutable `insight_digests` row, not ephemeral `detection_policies`.
- PHGCredential suspension is exponential: `base_s * 2^(consecutive - min)`, capped at max_s (28d). Duration is consequence-graduated.
- AlertRouter polls every 30s, tracks `_last_id`, dispatches via `urllib.request.urlopen` in executor — zero new dependencies.
- FederationBus privacy: cluster fingerprint is `SHA-256("|".join(sorted(device_ids)))[:16]` — 16-char hex prefix. If device population is small (<10K), brute-force is feasible. Document as known limitation.
- Batcher bounded queue maxsize=1000: overflow raises `asyncio.QueueFull` — currently not caught, records are dropped. Add counter metric.
- Synthetic test data produces 100% detection / 0% false positives — meaningless without real-world calibration. Never report this without the "synthetic" caveat.
- Windows: always use `tempfile.mkdtemp()` for SQLite test fixtures (not `TemporaryDirectory`) due to WAL PermissionError on cleanup.
- Operator endpoint auth pattern (Phase 58): always check `cfg.operator_api_key` BEFORE parsing the JSON body — auth rejection before body parse avoids reading attacker-controlled data on 401/503 responses. Guard order: rate limit → auth → body parse.
- Sliding-window rate limiter (Phase 58): `_rate_buckets` defaultdict in-process works correctly for asyncio (single-threaded) — no locks needed. Eviction is lazy (happens on next request after window expiry). Safe for dev/testnet; for multi-process production, replace with Redis.
- BridgeAgent tool `_execute_tool()` uses `self._store._conn()` directly for ad-hoc queries not covered by the public store API (e.g. raw `SELECT pitl_l4_distance FROM records`). This is acceptable and consistent with existing Phase 50 tools. Document as internal pattern.
- R3F/Rapier pattern (Phase 59): import Physics from `@react-three/rapier` without `useSphericalJoint` (unused). Rapier WASM loads async — wrap Controller3D in `<Suspense fallback={null}>` inside `<Physics>`. Physics component accepts `gravity={[0,0,0]}` to disable gravity for the floating controller.
- IBI data flow (Phase 59): raw IBI sequences live only in-memory in `BiometricFeatureExtractor` deques — NOT stored to DB. Exposed via `get_ibi_snapshot()` method, passed through `pitl_meta["ibi_snapshot"]`, broadcast on `/ws/records` and `/ws/twin/{device_id}`. IBI data is ephemeral; only `press_timing_jitter_variance` scalar is persisted.
- `/ws/twin/{device_id}` device isolation (Phase 59): `_ws_twin_clients: dict[str, set]` keyed by device_id. `ws_twin_broadcast_frame` and `ws_twin_broadcast_record` each check the exact device_id key — cross-device bleed is impossible without a broadcast-all call. Avoids per-record device_id filtering overhead.
- Sparkles threshold (Phase 59): always use `snap?.calibration?.anomaly_threshold ?? 6.726` — never hardcode 7.009. The per-player calibrated threshold from the REST snapshot is the correct comparison point.
- BiometricRadar BIO_NORM (Phase 60): normalization max per feature — [1, 5000, 5000, 600000, 1, 1, 1, 50, 1, 9, 1, 0.06]. Indices 0 and 10 (structurally zero) render as empty spokes. `vals[i] / BIO_NORM[i]` clamped to [0,1]; use `Math.abs()` before dividing (negative correlations are valid).
- QRCode npm in Vite (Phase 60): `import QRCode from 'qrcode'` works in ESM. Use `QRCode.toDataURL(url, { color: { dark, light } })` inside useEffect with `showQR` dep. Generate once per open, not on every render.
- L5 WS field names (Phase 60): `pitl_l5_cv` (scalar or dict keyed by button), `pitl_l5_entropy` (bits), `pitl_l5_quant` (bool/score), `l5_rhythm_humanity` (float). CV may be scalar in current bridge — guard with `typeof l5Cv === 'object'` before indexing as dict.
- BiometricScatter (Phase 60): use feature indices 3 (micro_tremor_accel_variance, max ~600k LSB²) and 11 (press_timing_jitter_variance, human max ~0.06 s²) for the most discriminative 2D cross-section. Bot zone is near (0, 0) on both axes. Human 2σ ellipse centered at ~(43%, 38%) of axis range based on N=74 hardware calibration. Separation ratio 0.362 disclaimer is mandatory in this view.
- Session replay ring buffer (Phase 61): `_replay_ring = collections.deque(maxlen=60)` holds up to 60 downsampled (~20 Hz) InputSnapshot dicts. Populated by `_replay_ring.extend(_out)` inside the frame broadcast try/except. Snapshot taken after `_dispatch()` via `list(self._replay_ring)`. At 1 Hz record rate, ring holds 60 seconds of frames. ring.extend() is safe in asyncio (single thread). `store_frame_checkpoint` uses `INSERT OR IGNORE` for idempotency on record_hash (unique index) — NOT for FK violations.
- frame_checkpoints FK constraint (Phase 61): FOREIGN KEY (record_hash) REFERENCES records(record_hash) with foreign_keys=ON. In production, checkpoint is stored after `_dispatch()` → `_on_record()` stores the record first. In tests, pre-seed the parent record before calling `store_frame_checkpoint` — the `INSERT OR IGNORE` does NOT suppress FK violations (only uniqueness conflicts).
- /features endpoint (Phase 61): reads `pitl_l4_features` (JSON TEXT) from records table; only returns rows where `pitl_l4_features IS NOT NULL`. Feature vectors are list[float] len=12. Limit capped at 200. Use indices 3 and 11 for BiometricScatter (tremor × jitter cross-section). Returns empty list [] if no warmed L4 records exist.
- Track C testnet deployment (Phase 61): wallet 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692 depleted to 0.43 IOTX after prior deployments. VAPIioIDRegistry and PITLTournamentPassport deployments blocked. Need testnet IOTX top-up via IoTeX faucet before proceeding.
- **BT-CALIB-LESSON-001** (Active, load-bearing): Transport-layer ground truth must be verified against authoritative sources (upstream OS driver + reverse-engineering project + field confirmation, three independent classes minimum) before deriving protocol-layer features for any wireless or wired controller transport. Marketing-tier "wireless Bluetooth" descriptions are insufficient — BR/EDR and BLE are structurally different stacks with non-overlapping primitive sets. Established 2026-05-10 after methodology-research falsified three of four proposed L4 features in the v1.0 BT calibration architectural proposal (BLE primitives named for a controller that runs BR/EDR with HIDP). Full lesson detail in section "BT-CALIB-LESSON-001" below.
- **TRACK1-LESSON-002** (Active, load-bearing): Single-channel reality must be confirmed before multi-channel literature transfers. When the literature anchor for a sensor surface assumes a multi-channel input (multi-mic beam-forming, multi-camera triangulation, multi-IMU fusion) and the actual hardware exposes a single channel post-DSP, the literature does not transfer and any feature derivation against the multi-channel assumption is structurally invalid. Established 2026-05-10 after Track 1 sensor-stack research falsified the multi-mic acoustic-fingerprinting position against the DualSense's single mono UAC1 stream (the on-controller back-mic sound-cancelling DSP destroys per-mic phase information before the audio reaches the host). The verification-block discipline must include channel-count confirmation against vendor-spec sources, not just signal-existence confirmation. Full lesson detail in section "TRACK1-LESSON-002" below.
- **TRACK1-LESSON-003** (Active, load-bearing): Privacy-jurisdiction analysis must precede biometric capture surface inclusion. Any sensor surface that captures audio, video, or biometric-identifiable signal in regions where consent regimes attach (BIPA in Illinois, GDPR Art. 9 in EU, CIPA in California / Florida / Pennsylvania / Illinois) is structurally falsified if it has non-consenting-third-party exposure (household members, roommates, spectators at tournament-from-home). Established 2026-05-10 after Track 1 sensor-stack research falsified the microphone-array surface on privacy grounds. The controlling case is Cruz v. Fireflies AI Corp. (No. 3:25-cv-03399 C.D. Ill.) — non-account-holding meeting participants whose voice was captured without consent maps directly onto household third parties at a tournament-from-home participant. Statutory damages $1,000-$5,000 per scan per BIPA negligent-versus-intentional violation; concrete settlement anchor Beil v. Petco at $445,000 / 445 class members. The verification-block discipline must include privacy-jurisdiction analysis as a feasibility gate, not a downstream check. Full lesson detail in section "TRACK1-LESSON-003" below.
- **CROSS-LESSON-001** (Active, load-bearing, applies to L8 BT + L4 v2 + all future): Same-controller-population separability constraint — any feature claim against a controller-internal physical fingerprint must explicitly distinguish session-bound presence attestation from cross-session controller identity, because surfaces whose discriminative variance is dominated by inter-unit manufacturing tolerance collapse in same-model same-batch populations. First established against L8 BT (Givehchian's intra-Apple FPR 1.91% vs 0.62% heterogeneous baseline) per `bt_calibration_v1_1_architectural_revision.md`; applied verbatim against Hall-effect stick fingerprinting per `sensor_stack_v2_1_architectural_revision.md`. Promoted to cross-surface global rule 2026-05-10 after the constraint bit on two independent sensor-stack analyses. Cross-session identity claims for any controller-internal physical fingerprint require a same-model separability study for N≥20 stock units + N≥20 batched-aftermarket units in tournament-realistic conditions; until completed, the surface is session-bound presence only. Full rule detail in section "CROSS-LESSON-001" below.

---

## BT-CALIB-LESSON-001: Transport-Layer Ground Truth Must Precede Feature Derivation

**Status:** Active. Load-bearing for all future VAPI connectivity-option work.
**Established:** 2026-05-10, after a methodology-research verification pass falsified three of four proposed L4 features in the v1.0 BT calibration architectural proposal.
**Cross-reference:** Canonical anchor — `wiki/assessments/VAPI Bluetooth Calibration_ Architectural Prerequisites and Threat Model Analysis.pdf`. Architectural revision — `wiki/methodology/bt_calibration_v1_1_architectural_revision.md`. Superseded artifact — v1.0 BT calibration architectural proposal (chat-session, marked [SUPERSEDED-BT-CALIB-LESSON-001]).

### Lesson statement

Before deriving protocol-layer features from any wireless or wired controller transport, verify the actual transport profile against authoritative sources. Marketing-tier descriptions of "wireless Bluetooth" are insufficient because Bluetooth Classic (BR/EDR) and Bluetooth Low Energy (BLE) are structurally different stacks with non-overlapping primitive sets. Features named in one transport (advertising interval, connection events, GATT, advDelay) do not exist in the other (where the analogs are page-scan repetition with R0/R1/R2 modes, Tpoll variance, sniff-mode Tsniff drift, and L2CAP HID PSMs 0x11 and 0x13). Feature derivation against the wrong transport produces an architectural proposal that is structurally invalid rather than merely suboptimal — the primitives the features assume do not exist on the wire.

### What happened

The v1.0 BT calibration architectural proposal named four L4 features: `connection_interval_jitter`, `advertisement_period_drift`, `retransmission_rate` in its BLE-specific reading, and `rssi_variance_normalized`. The DualSense and DualSense Edge use Bluetooth Classic BR/EDR with HID-over-L2CAP (HIDP), not BLE with HID-over-GATT (HOGP). Three of four features were structurally invalid; their underlying BLE primitives do not exist on the actual transport the controller runs. The published BT-fingerprinting and BT-attack literature most relevant to the proposal (Givehchian et al. S&P 2022, BlueShield RAID 2020, BLESA WOOT 2020, SweynTooth USENIX Sec 2020, KNOB USENIX Sec 2019) overwhelmingly targets BLE; their empirical anchors do not transfer cleanly to BR/EDR. The error was caught only on a literature-verification pass two architectural turns later. This is precisely the failure mode VSD-INV-19 was written to prevent.

### Verification sources of record (DualSense / DualSense Edge transport)

The transport profile for the DualSense and DualSense Edge is Bluetooth Classic BR/EDR with HIDP, confirmed by:

1. **Upstream OS driver:** Linux mainline kernel `drivers/hid/hid-playstation.c` by Roderick Colenbrander (Sony Interactive Entertainment), mainlined in Linux 5.12 (April 2021). Devices register via the `HID_BLUETOOTH_DEVICE(...)` macro, which is used for BR/EDR HIDP transport, not BLE/HOGP.
2. **Reverse-engineering project (general controller stack):** Bluepad32 FAQ at bluepad32.readthedocs.io — "Controllers like Switch, Wii, DualSense, DualShock, etc. only talk 'BR/EDR' (as opposed to BLE)."
3. **Reverse-engineering project (PS5-specific):** BlueRetro project, Hackaday.io project 170365 (darthcloud) — "PS5 Dual Sense is still BR/EDR (aka. BT classic)."
4. **Vendor/wiki documentation:** PCGamingWiki Controller:DualSense Edge — "Bluetooth 2.1 + EDR or higher required for wireless connection."
5. **Field confirmation:** FreeBSD Forums thread 80786 — pairing fails on a BLE-only BCM920702MD board and succeeds on a BT 2.1+EDR BCM92046MD board.

A verification block is considered complete only when at least three independent classes of source agree: the upstream OS driver, at least one reverse-engineering project, and at least one field-confirmation source. Vendor marketing pages do not count toward the verification block.

### Application rule

Any future VAPI architectural proposal that names protocol-layer features for a controller transport must include a transport-verification block citing sources from at least three independent classes (upstream OS driver, reverse-engineering project, field confirmation) before the proposal exits draft state. The verification block is part of the proposal, not a downstream check. If the verification block cannot be assembled — because the controller is too new, the driver is closed-source, or no reverse-engineering project exists — the proposal must explicitly mark the transport claim as "unverified" and the proposal cannot proceed to feature derivation until verification is obtained. This rule applies to USB-C-with-Power-Delivery, 2.4 GHz proprietary RF, future console controllers (PS6, next-gen Xbox), and any wired or wireless transport VAPI extends to.

### Anti-pattern to recognize

The error pattern that produced this lesson: deriving features from the *intended use case* (low-latency wireless input over Bluetooth) rather than from the *actual wire format* (BR/EDR with HIDP versus BLE with HOGP). Use cases describe what the system does; wire formats describe what the system emits. Features must be derived from wire formats, not from use cases. When a future architectural proposal starts to feel like it's progressing without a verification block in hand, that is the signal to halt and assemble the block before continuing.

---

## TRACK1-LESSON-002: Single-Channel Reality Must Be Confirmed Before Multi-Channel Literature Transfers

**Status:** Active. Load-bearing for all future VAPI sensor-surface work.
**Established:** 2026-05-10, after a Track 1 sensor-stack verification pass falsified the microphone-array surface against the DualSense's single mono UAC1 stream.
**Cross-reference:** Canonical anchor — `wiki/assessments/DualSense Edge Sensor-Stack Characterization for VAPI Track-1 Anti-Cheat Feature Architecture.pdf`. Architectural revision — `wiki/methodology/sensor_stack_v2_1_architectural_revision.md`. Companion lesson — `BT-CALIB-LESSON-001` (the same verification-discipline pattern applied at the transport layer; TRACK1-LESSON-002 is the sensor-channel-layer analog).

### Lesson statement

When the literature anchor for a sensor surface assumes a multi-channel input (multi-mic beam-forming, multi-camera triangulation, multi-IMU fusion, multi-collector physical-layer fingerprinting) and the actual hardware exposes a single channel after on-device DSP, the multi-channel literature does not transfer and any feature derivation built on it is structurally invalid. The verification-block discipline (BT-CALIB-LESSON-001 application rule) must include channel-count confirmation against vendor-spec sources, not just signal-existence confirmation. A sensor surface that is "present" is not the same as a sensor surface that exposes the channels the literature requires.

### What happened

The v2.0 sensor-stack ideation proposed the DualSense microphone array as a passive presence-attestation surface, with the literature anchor leaning on multi-mic beam-forming and room-impulse-response work (Roger-Lombard 2022 passive acoustic localization, Gabbrielli 2021 multi-channel indoor person localization). The DualSense Game Controller Collective Wiki entry describes the controller's microphone path as "Mono Body Mic with Back Mic sound canceling" — only a single mono channel is exposed to the host over UAC1, despite the on-controller multi-mic noise-cancelling DSP (Realtek ALC5524 codec, Sony codename "Venom"). The on-controller DSP destroys per-mic phase information before the audio reaches the host. The multi-mic literature does not transfer to a single mono channel post-DSP. The single-mic passive acoustic literature (Xue 2026 Sensors smartphone-as-receiver) requires controlled active anchors emitting near-ultrasonic signals, which a DualSense controller does not provide. The error was caught only on the Track 1 verification pass.

### Verification sources of record (DualSense single-channel audio path)

The single-channel mono UAC1 audio path is confirmed by:

1. **Upstream OS driver:** ALSA usb-audio quirk patch series by Cristian Ciocaltea (Collabora, LWN.net 1022523, May 2025): "the controller complies with v1.0 of the USB Audio Class spec (UAC1)." On Linux, surfaces as `alsa_card.usb-Sony_Interactive_Entertainment_DualSense_Wireless_Controller-00` with input and output PCM endpoints.
2. **Vendor/wiki documentation:** Game Controller Collective Wiki — "Mono Body Mic with Back Mic sound canceling." Only a single mono channel is exposed to the host over UAC1 despite the on-controller multi-mic DSP.
3. **Field confirmation:** PCGamingWiki + BoilingSteam first-look review confirm mic only available over USB; built-in microphone is unsupported over BT.

The verification block is complete (three independent classes agree).

### Application rule

Any future VAPI architectural proposal that names a sensor surface where the published literature assumes multi-channel input must include a channel-count confirmation block citing vendor-spec sources (upstream OS driver registration, reverse-engineering corpus, vendor/wiki documentation) before the proposal exits draft state. If the hardware exposes fewer channels than the literature requires, the proposal must either (a) restrict the literature anchor to single-channel methods that genuinely apply (e.g., room-fingerprint envelope features that work on mono input), or (b) explicitly drop the surface from the L4 critical path. The rule applies to microphone arrays, camera arrays, IMU clusters, and any other multi-sensor surface where on-device DSP may collapse channels before exposing them to the host.

### Anti-pattern to recognize

The error pattern that produced this lesson: assuming the literature anchor's input format matches the controller's output format because both are named "microphone array" or "multi-mic." Named equivalence is not channel-count equivalence; on-device DSP can transform a multi-mic input into a single-channel output, and the literature anchored on the multi-mic input does not generalize. When a sensor surface's literature anchor specifically requires per-channel data (phase information, time-difference-of-arrival, beam-forming weights), confirm the channel exposure before drafting features. The L8 BT lesson's "transport-layer ground truth" framing extends to "sensor-channel ground truth" — verify the wire format, not the use case.

---

## TRACK1-LESSON-003: Privacy-Jurisdiction Analysis Must Precede Biometric Capture Surface Inclusion

**Status:** Active. Load-bearing for all future VAPI biometric-capture work.
**Established:** 2026-05-10, after a Track 1 sensor-stack verification pass falsified the microphone-array surface on privacy grounds with concrete BIPA / GDPR / CIPA litigation anchors.
**Cross-reference:** Canonical anchor — `wiki/assessments/DualSense Edge Sensor-Stack Characterization for VAPI Track-1 Anti-Cheat Feature Architecture.pdf`. Architectural revision — `wiki/methodology/sensor_stack_v2_1_architectural_revision.md`.

### Lesson statement

Any sensor surface that captures audio, video, or biometric-identifiable signal in regions where consent regimes attach is structurally falsified if it has non-consenting-third-party exposure (household members, roommates, spectators at tournament-from-home). The privacy-jurisdiction analysis is a feasibility gate, not a downstream check. Per-scan statutory damages under BIPA ($1,000 negligent / $5,000 intentional per scan), GDPR Art. 9 (biometric data prohibition without narrow lawful basis), and state two-party consent regimes (CIPA in California / Florida / Pennsylvania / Illinois) make any biometric-capture surface a litigation magnet if the consent envelope does not reach all incidentally-captured parties.

### What happened

The v2.0 sensor-stack ideation proposed the DualSense microphone array as a passive presence-attestation surface, framing the privacy question as "narrow non-speech features can preserve privacy." The Track 1 verification pass anchored the question against concrete 2024-2025 litigation:

- **Beil v. Petco Animal Supplies Stores, Inc.**, Case No. 1:22-cv-06455 (N.D. Ill.) — Judge Sunil Harjani granted preliminary approval March 14, 2024, to a $445,000 settlement covering 445 warehouse workers who used a Honeywell Vocollect voice order-picking system. That is $1,000 per class member, the BIPA negligent-violation floor.
- **Parker et al. v. Verizon Communications Inc.**, Case No. 1:24-cv-08436 (N.D. Ill. Eastern Division), filed September 18, 2024 — targets Verizon's Voice ID program; Judge Jorge Alonso ordered arbitration May 30, 2025.
- **Cruz v. Fireflies.AI Corp.**, No. 3:25-cv-03399 (C.D. Ill.), filed December 18, 2025 — plaintiff Katelin Cruz; targets Fireflies' "Speaker Recognition" feature which generates voiceprints of *non-account-holding* meeting participants. **The non-account-holding-third-party theory is directly analogous to a household member whose audio is incidentally captured by a DualSense mic in a tournament-from-home configuration.**

Even framing the capture as "presence attestation, not voice ID" does not avoid BIPA: the trigger is the capture and storage of biometrically-identifiable audio, regardless of downstream use. Tournament terms-of-service consent does not necessarily reach household third parties whose audio is incidentally captured.

### Verification sources of record (privacy jurisdictions)

1. **Statutory:** Illinois BIPA (740 ILCS 14); EU GDPR Article 9; EU AI Act biometric-categorization rules; US Federal Wiretap Act; CIPA (Cal. Penal Code §§ 631-637.2); Illinois 720 ILCS 5/14-2; Pennsylvania 18 Pa. C.S. § 5703; Florida § 934.03.
2. **Concrete litigation:** Beil v. Petco (preliminary approval March 14, 2024 — Bloomberg Law coverage); Parker v. Verizon (arbitration order May 30, 2025); Cruz v. Fireflies AI (filed December 18, 2025 — National Law Review / Workplace Privacy Report coverage).
3. **Independent analysis:** The Lyon Firm BIPA tracking, UMEVO statutory damages summary.

### Application rule

Any future VAPI architectural proposal that names a sensor surface capturing audio, video, or biometric-identifiable signal must include a privacy-jurisdiction analysis block before the proposal exits draft state. The block enumerates: (a) which biometric-identifier statutes (BIPA, GDPR Art. 9, CCPA biometric provisions, state-specific) plausibly attach to the captured signal; (b) what the consent envelope is (account holder only? all household members? all parties present in the recording space?); (c) whether incidentally-captured non-consenting third parties have a viable claim; (d) per-scan statutory damages floor in the most permissive plausible jurisdiction; (e) whether on-device or tightly-bounded-enclave processing is available to avoid raw biometric signal crossing infrastructure where consent regimes attach. **If the consent envelope does not cover all incidentally-captured parties, the surface is structurally falsified regardless of engineering merit.**

### Anti-pattern to recognize

The error pattern that produced this lesson: assuming "narrow non-speech features" or "we don't use it for voice ID" avoids privacy attachment. The trigger for BIPA is the *capture and storage* of biometrically-identifiable audio, not the downstream use; for CIPA it is the *recording of oral communications* without consent. Downstream framing does not avoid upstream capture liability. When a sensor surface captures audio of any humans (even passively, even as "room fingerprint"), the privacy-jurisdiction analysis is a Stage 1 feasibility gate, not a Stage 3 compliance review.

---

## CROSS-LESSON-001: Same-Controller-Population Separability Constraint

**Status:** Active. Load-bearing. Applies cross-surface to L8 BT (BT calibration), L4 v2 (sensor stack), and all future VAPI controller-internal-physical-fingerprint claims.
**Established:** 2026-05-10 against L8 BT (Givehchian's intra-Apple FPR 1.91% vs 0.62% heterogeneous baseline) per `bt_calibration_v1_1_architectural_revision.md`. Promoted to cross-surface global rule 2026-05-10 after the constraint bit on a second independent sensor-stack analysis (Hall-effect stick fingerprinting per `sensor_stack_v2_1_architectural_revision.md`).
**Cross-reference:** `bt_calibration_v1_1_architectural_revision.md` §6; `sensor_stack_v2_1_architectural_revision.md` §6; canonical anchors `wiki/assessments/VAPI Bluetooth Calibration_*.pdf` and `wiki/assessments/DualSense Edge Sensor-Stack Characterization_*.pdf`.

### Rule statement

Any feature claim against a controller-internal physical fingerprint (radio-physical-layer, sensor-hardware, actuator-hardware, manufacturing-tolerance-driven) must explicitly distinguish:

- **Session-bound presence attestation** (the surface confirms the controller is held and active in the current session) — generally feasible at session-internal scale.
- **Cross-session controller identity** (the surface confirms this is the same controller as in a prior session) — requires a same-model separability study and is structurally constrained.

Cross-session identity claims require a same-model separability study for N≥20 stock units + N≥20 batched-aftermarket units in tournament-realistic conditions, with decision threshold > 20% unit-level rank-1 discrimination on same-model same-batch population. Until completed, the surface is **session-bound presence only**. Any architectural proposal that relies on a controller-internal physical fingerprint as a cross-session identity anchor without the separability study is structurally suspended.

### Why the constraint matters (two independent confirmations)

**L8 BT (Givehchian 2022):** The published baseline shows 1.21% FPR on a 162-device heterogeneous BLE population using combined CFO + IQ-offset + IQ-imbalance features. But same-manufacturer separability is materially worse: FPR for Apple devices comparing to other Apple devices is 1.91% versus 0.62% across all devices. Temperature drift compounds: a +10°C internal rise during GPU-intensive use produces a 7 kHz CFO shift, larger than the 9.12 kHz cross-population σ. A corpus of identical DualSense Edges in the same RF environment sits closer in physical-layer feature space than a heterogeneous BLE device population.

**L4 v2 (Hall-effect stick aftermarket):** Givehchian et al. IEEE S&P 2022 achieves 40-47% unique identification on a heterogeneous mobile population from radio physical-layer features. The Hall-effect stick analog (per-unit response curve, deadzone shape, return-to-center bias) carries manufacturing-tolerance variation that could constitute a hardware fingerprint. But N≈50 identical DualSense Edge units in a tournament hall, particularly if all running an aftermarket TMR module batch from the same supplier (MODDEDZONE, Battle Beaver, XP Controllers — very common in competitive Edge scene), will sit closer in Hall-stick response-curve feature space than a heterogeneous public population. The hardware variance budget collapses by an order of magnitude or more.

### Per-surface application matrix (as of 2026-05-10)

| Surface | Variance source | Constraint bites? | Disposition |
|---------|-----------------|-------------------|-------------|
| L8 BT physical layer (CFO/IQ/RSSI) | radio manufacturing tolerance | YES | Session-bound presence only; cross-session identity blocked until separability study |
| L4 v2 trigger force-curve | player biomechanics | NO | Cross-session feature reuse permitted |
| L4 v2 touchpad swipe dynamics | player swipe/tap behavior | NO | Cross-session feature reuse permitted |
| L4 v2 stick Hall fingerprint | manufacturing tolerance | YES | Session-bound presence only; cross-session identity blocked until separability study |
| L4 v2 stick noise floor (tremor) | player physiological tremor | NO | Cross-session feature reuse permitted |
| L4 v2 battery drain | insufficient resolution regardless of population | N/A | Advisory only |

### Application rule

Any future VAPI architectural proposal that names a controller-internal physical fingerprint feature must, before the proposal exits draft state, complete the following triage:

1. **Identify the dominant variance source.** Is the discriminative signal driven by *player behavior/biomechanics* (does not bite) or by *unit hardware manufacturing tolerance* (bites)?
2. **If the variance source is manufacturing tolerance**, classify the feature as session-bound presence only by default. Cross-session identity claims require a same-model separability study (N≥20 stock + N≥20 batched-aftermarket units in tournament-realistic conditions; decision threshold > 20% unit-level rank-1 on same-model same-batch).
3. **If the same-model separability study has not been completed**, the feature is suspended from cross-session-identity use until the study lands. Session-bound presence use is permitted in the interim.

### Anti-pattern to recognize

The error pattern that produced this lesson (twice independently): conflating "this signal class shows good separability in the published literature" with "this signal class will show good separability in our deployment." Published BLE physical-layer fingerprinting work uses heterogeneous device populations (162-device studies with multiple manufacturers, multiple SoCs, multiple firmware versions). Tournament deployments use same-model same-batch populations (50 identical DualSense Edges, possibly all from the same aftermarket TMR supplier). The published separability numbers are an upper bound on a heterogeneous population, not a transferable estimate for a same-model deployment. When the architectural plan involves "fingerprinting" any controller-internal physical surface in a tournament context, the same-model question is the binding constraint, not the published heterogeneous-population number.


---

# MLGA-LESSON-001: Dual-Connection Topology Routes Around Calibration-Capture Bottleneck

**Status:** Active. Authored 2026-05-15. Load-bearing for Phase O5-MLGA architectural decisions + all future "calibration corpus growth via ambient capture" proposals.
**Cross-reference:** Canonical anchor — `wiki/methodology/mlga_architectural_proposal_v1.md` v1.0. Companion lesson — `BT-CALIB-LESSON-001` (transport verification rule that MLGA's Section 1 applies). Companion lesson — `CROSS-LESSON-001` (same-model separability constraint that MLGA does NOT violate because MLGA claims session-bound passive capture only, not cross-session identity).

## Lesson statement

When a hardware target supports simultaneous dual-channel transport (USB to one host + Bluetooth to another), and one channel has independent calibration-grade observability (1000 Hz HID via USB to bridge laptop), the dedicated-capture-session bottleneck for calibration corpus growth can be partially routed around by capturing during ambient real-use sessions. The structural premise is: ambient real-use exercises the relevant feature surfaces at higher volume than dedicated capture sessions can practically schedule.

This is NOT a substitute for lab-controlled measurements where lab control matters (e.g., σ_RSSI held-vs-placed requires controlled low-WiFi-interference environment per the v1.1 BT calibration anchor §5 Empirical Unknown #1). But it IS a substitute for raw-volume-bound capture targets where the controlled-environment constraint is weaker (e.g., N=100 trigger pulls × 3 game contexts for Phase 243-SS2 Stage-A; the game contexts are themselves "controlled" by the player's actual game).

## What happened

Three Phase 243-SS2 Stage-A + Phase 242-BT Stage 2 + Phase 229 AIT corpus-growth campaigns were sized for dedicated-capture-session pace: N=10 players × 100 trigger pulls × 3 contexts ≈ 15 hours of staged work. The schedule cost was treated as fixed engineering overhead. Operator directive 2026-05-15 reframed the question: if a player is playing NCAA CFB 26 on the PS5 with DualSense Edge USB-C plugged into the bridge laptop AND BT-paired to the PS5, the bridge sees 1000 Hz HID for free. The same NCAA CFB 26 sprint mechanic (R2 hold) produces dozens to hundreds of trigger force-curve readouts per session organically. The dedicated-capture overhead was real but had been treated as the only path.

The miss: "calibration capture" was being scoped against "lab session" semantics by default, even though VAPI's bridge already had the full 1000 Hz HID capture pipeline (Phase 49 onward) wired against organic gameplay (Phase 235-A GIC chain runs against ambient gameplay; Phase 241-APOP classifier runs against ambient gameplay). The bottleneck was scheduling, not engineering.

## Application rule

Before designing a new dedicated capture-session campaign for VAPI calibration corpus growth, the proposal must answer:

1. **Does the target feature surface exercise during ambient real-use of the target hardware?** If YES, ambient-capture supplementation should be in scope.
2. **What is the controlled-environment requirement for the feature?** If lab-controlled is binding (σ_RSSI, σ_CFO, temperature-controlled benchmarks), dedicated capture is the load-bearing path and ambient is opt-in supplement. If controlled-environment is not binding (raw trigger pull count, raw R2 onset velocity samples, raw IMU windows during natural hold), ambient-capture can be the load-bearing path with dedicated capture as the verification supplement.
3. **What is the ambient-real-use rate of the feature exercise?** Cite the empirical-unknown number explicitly. Don't assume; measure.
4. **What is the cryptographic-dataproof discipline for ambient captures?** Lab captures have known provenance + controlled metadata. Ambient captures need explicit provenance commitment (MLGA dataproof) to be treated as protocol-grade corpus entries.

## Anti-pattern to recognize

The error pattern that produced this lesson: treating "calibration corpus growth = lab session" as a structural identity rather than as a default. Dedicated lab sessions are one capture modality. Ambient-capture during real-use is another. Both can produce calibration-grade data; the relevant question is whether the controlled-environment constraint binds the feature, not whether the capture session was labeled "lab" or "ambient." Whenever a calibration campaign feels expensive in operator-runtime, ask whether the controlled-environment constraint is actually binding for the target feature OR whether it's being applied by default.

## Constraint envelope

MLGA-LESSON-001 establishes that ambient-capture is a viable supplementation path for non-controlled-environment-binding features. It does NOT establish that ambient-capture replaces lab capture where lab control matters. Specifically:

- Phase 242-BT Stage 2 σ_held-vs-placed: lab-controlled REQUIRED (low-WiFi-interference RF environment is binding); ambient supplementation valuable for breadth-of-condition coverage but NOT a substitute.
- Phase 243-SS2 Stage-A trigger force-curve: ambient supplementation viable for raw N (player IS firing R2 during gameplay); dedicated capture remains valuable for cross-game-context controlled comparison.
- Phase 229 AIT corpus: ambient supplementation viable for raw N (still-hold during gameplay pauses + menu screens produces AIT-quality windows); dedicated capture remains the canonical baseline.

The application rule: classify each capture target as "controlled-environment-binding" or "raw-volume-binding" before proposing the campaign structure. Mixed-binding targets (e.g., L4 v2 trigger force-curve where both controlled context AND raw N matter) need both modalities in the campaign.
