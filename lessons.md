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
