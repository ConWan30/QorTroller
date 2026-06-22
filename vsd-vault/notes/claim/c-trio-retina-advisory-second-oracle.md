---
type: claim
id: c-trio-retina-advisory-second-oracle
created: 2026-06-22T00:00:00Z
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
confidence: highly-likely
effort: 45
refs: ["i-trio-retina-main-protocol-docs"]
---

**Claim:** On `main`, Trio-Retina is an **advisory second oracle** on certified controller HID dynamics (sticks, triggers, IMU trajectory events). It is **not** a replacement for L4/L5 Mahalanobis/rhythm or the 228-byte PoAC wire, and it is **not** a tournament P0 gate unless separately wired.

**Claim:** The `trio-retina` package supplies dynamics schema (`WorldState`, `Event`); QorTroller maps HID windows via `retina_controller_embedder` and does **not** run full Trio-Retina training inside the bridge.

**Claim:** `retina_state_commitment` binds an off-chain event slice to PoAC `record_hash`; bulk events live in `retina_event_log` with optional W3bstream validation, DA upload, and PDA attestation — the same decoupled-pointer pattern as Arc 7 PQ.

**Claim:** Three commitment axes remain distinct: PoAC `world_model_hash` (EWC/TinyML), `pq_commitment` (ML-DSA sidecar), `retina_state_commitment` (Trio-Retina event slice).

**Claim:** Default posture is **OFF** (`RETINA_PERCEPTION_ENABLED=false`); `RETINA_POLICY_AUTO_ARM=true` may arm at runtime on qualified DualShock Edge USB connect without editing `.env`.

**Claim:** Session adjudicator enrichment is read-only (`evidence_json.retina`); FSCA cross-oracle rules (e.g. `RETINA_TRAJECTORY_WITHOUT_L4_ANOMALY`) are MEDIUM advisory, not P0 blockers.
