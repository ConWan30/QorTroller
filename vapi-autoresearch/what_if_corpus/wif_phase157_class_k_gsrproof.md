# WHAT_IF Entry — AutoResearch Cycle 5 (2026-04-04)

**Source**: AutoResearch cycle 5, score=1.000
**Phase**: 156 → 158 candidates

---

## WIF-014 — Class K Synthetic EDA Generator: Feature-Level Bypass of L7 GSR (Phase 158 candidate)

**W1 — Failure mode**: Adversary injects synthetic EDA signals into the BLE GSR packet stream, producing plausible SCR morphology that passes all four L7 feature checks — L7 advisory code 0x33 GSR_CORRELATION_ABSENT never fires because correlation IS present (with synthetic data).

**Implication**: `sympathetic_arousal_index`, `gsr_game_event_correlation`, `baseline_conductance_drift`, and `cognitive_load_variance` all land in human-normal ranges. The Class K adversary uses MockGSRGrip source code as a reference implementation — a $15 ESP32-S3 with BLE advertisement injection capability is sufficient. Current 48-byte GSR packet format (magic 0x47535201 + arousal_millis + correlation_millis + ts_ns) contains no HMAC field; BLE broadcast is unauthenticated. The adversary is economically motivated by VHP mint access → tournament entry → prize eligibility.

**Cryptographic grounding**: Packet injection requires only BLE advertisement spoofing + knowledge of the open MockGSRGrip morphology parameters. No cryptographic commitment exists on the current GSR packet.

**Mitigation**: Phase 99B+/Phase 158 — extend GSR packet format from 48B to 80B (+32B HMAC-SHA256). ESP32-S3 generates per-packet HMAC using device private key from ATECC608A secure element. `certLevel=2` in VAPIHardwareCertRegistry records HMAC public key. Bridge validates HMAC before L7 feature extraction; rejects unsigned packets with 0x33 GSR_CORRELATION_ABSENT advisory at WARNING severity.

**Status**: OPEN — Phase 158 candidate

---

## WIF-015 — Hardware-Bound GSR Proof (PoHBG) as Fourth Composable Proof Primitive (Phase 158 candidate)

**W2 — Opportunity**: Extend the PoAC + PoAd + PoFC composable triple to a **quadruple** by adding Proof of Hardware-Bound GSR (PoHBG).

**Mechanism**:
1. ESP32-S3 signs each GSR sample batch: `PoHBG_hash = SHA-256(sorted_samples + ts_ns + device_pubkey_hash_bytes32)`
2. Bridge validates PoHBG against `certLevel=2` pubkey in VAPIHardwareCertRegistry.sol
3. VAPIGSRRegistry.recordSample gains `hmac_hash bytes32` field (non-breaking extension)
4. On-chain commitment: `PoHBG` hash anchored in VAPIGSRRegistry
5. Composable quadruple: **PoAC** (physiological, 228B, ECDSA-P256) + **PoAd** (adjudication registry) + **PoFC** (fleet consensus, Phase 157) + **PoHBG** (hardware-bound GSR, Phase 158)

**Why it works**: Shifts GSR from advisory signal (0x33, purely software-based) to cryptographically hardware-bound proof primitive. Physical device ownership is required to generate valid PoHBG — Class K synthetic EDA generators cannot forge it without ATECC608A key material.

**Exclusive because**:
- Requires VAPIHardwareCertRegistry.sol `certLevel=2` (Phase 99A LIVE)
- Requires GSRRegistryAgent on-chain pipeline (Phase 99B)
- Requires 20-agent fleet + PoAC + PoAd + PoFC already deployed
- No competing gaming DePIN protocol has hardware-attested biometric composable proof

**Phase candidate**: Phase 158 (~4h effort) — VAPIGSRRegistry.sol 80B packet extension + ATECC608A firmware + bridge HMAC validation + certLevel=2 enforcement

**Status**: NEW — Phase 158 candidate
