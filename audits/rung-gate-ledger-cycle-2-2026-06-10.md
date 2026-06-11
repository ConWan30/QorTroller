# Sensor C — Rung-Gate Readiness Ledger (Cycle 2, 2026-06-10)

HWFL-1 Sensor C v0.1 — machine-checkable snapshot of every gate across Rungs 1-4 of the QorTroller manufacturing staircase. Honest weighting: nothing LIVE that isn't verifiable now. Generated `2026-06-11T00:01:12+00:00` by `scripts/run_sensor_c.py`. Machine-readable companion: `audits/rung-gate-ledger-latest.json`.


## Standing OPERATOR-ACTION box (loop never auto-touches)

- [ ] **OA-1** Back up `~/.vapi/qortroller_foundation_mfg_ca.json` (517 B) — F-DECON-3.2 interim. Highest-leverage 5-min action.
- [ ] **OA-2** Create `docs/disaster-recovery-runbook.private.md` with full AWS KMS ARNs.
- [ ] **OA-3** IAM scope-down on bridge/.env AWS keys → `KMS:Sign` + `KMS:GetPublicKey` on the two specific key ARNs.
- [ ] **OA-4** Long-term: HSM-backed ManufacturerRootCA + device re-issuance.


## State summary

| State | Count |
|---|---|
| LIVE | 4 |
| DORMANT | 13 |
| HARDWARE-GATED | 3 |
| BLOCKED-ON-SENSOR-B | 1 |
| BLOCKED-ON-EXTERNAL | 1 |
| **Total** | **22** |


## Rung 1

| Gate | Name | State | Evidence |
|---|---|---|---|
| `G1.1` | DualSense Edge physically connected | `HARDWARE-GATED` | intrinsic state (HARDWARE-GATED); see spec_ref |
| `G1.2` | ATECC608A breakout physically connected | `HARDWARE-GATED` | intrinsic state (HARDWARE-GATED); see spec_ref |
| `G1.3` | CH341A USB-I2C bridge present | `HARDWARE-GATED` | intrinsic state (HARDWARE-GATED); see spec_ref |
| `G1.4` | VAPIManufacturerDeviceRegistry deployed on IoTeX testnet | `LIVE` | VMDR @ 0x2e5B5FB110890f498e289E3045d0f54Cfb0F91b0 (IoTeX testnet chainId 4690) |
| `G1.5` | First reference device registered on-chain | `LIVE` | registration tx 0x68f6cf49…ac9c0 cited in CLAUDE.md (block 44028531) |
| `G1.6` | ManufacturerRootCA file present at canonical path | `LIVE` | ~/.vapi/qortroller_foundation_mfg_ca.json present (SINGLE-COPY per F-DECON-3.2 — see OA-1 in OPERATOR-ACTION box) |
| `G1.7` | SecureElementBackend honesty rail intact | `LIVE` | SecureElementBackend raises NotImplementedError (blocks silent host-key fallback; Arc 2 hardware-gated) |


## Rung 2

| Gate | Name | State | Evidence |
|---|---|---|---|
| `G2.1` | Dev-kit BOM document exists (two suppliers per critical part) | `DORMANT` | intrinsic state (DORMANT); see spec_ref |
| `G2.2` | Zephyr firmware target for QorTroller controller | `DORMANT` | intrinsic state (DORMANT); see spec_ref |
| `G2.3` | Thread-C-equivalent isolation statement in firmware spec | `DORMANT` | intrinsic state (DORMANT); see spec_ref |
| `G2.4` | φ sanitization device-residency design | `DORMANT` | intrinsic state (DORMANT); see spec_ref |
| `G2.5` | Hall/TMR stick module selection finalized | `DORMANT` | intrinsic state (DORMANT); see spec_ref |
| `G2.6` | IMU module selection finalized | `DORMANT` | intrinsic state (DORMANT); see spec_ref |
| `G2.7` | ESP32-class module cert status known | `BLOCKED-ON-SENSOR-B` | intrinsic state (BLOCKED-ON-SENSOR-B); see spec_ref |


## Rung 3

| Gate | Name | State | Evidence |
|---|---|---|---|
| `G3.1` | Partner-handoff package assembler | `DORMANT` | intrinsic state (DORMANT); see spec_ref |
| `G3.2` | TrustFLEX provisioning path amendment to spec | `DORMANT` | intrinsic state (DORMANT); see spec_ref |
| `G3.3` | Manufacturer CA chained to reference root — design | `DORMANT` | intrinsic state (DORMANT); see spec_ref |
| `G3.4` | Per-batch slot-config audit checklist | `DORMANT` | intrinsic state (DORMANT); see spec_ref |
| `G3.5` | Two-supplier cost model for critical parts | `DORMANT` | intrinsic state (DORMANT); see spec_ref |


## Rung 4

| Gate | Name | State | Evidence |
|---|---|---|---|
| `G4.1` | IIP-64 PR #72 movement / merge | `BLOCKED-ON-EXTERNAL` | intrinsic state (BLOCKED-ON-EXTERNAL); see spec_ref |
| `G4.2` | Spec-as-compliance-standard formalized | `DORMANT` | intrinsic state (DORMANT); see spec_ref |
| `G4.3` | Device-identity registry interop spec | `DORMANT` | intrinsic state (DORMANT); see spec_ref |


## Provenance

- Canonical gate registry: `bridge/vapi_bridge/sensor_c_rung_ledger.py::_CANONICAL_GATES` (22 gates, FROZEN per cycle)
- Verifier functions: `bridge/vapi_bridge/sensor_c_rung_ledger.py::_VERIFIERS` (4 active)
- Schema: `vapi-rung-gate-ledger-v1` (JSON companion artifact)
- Rung definitions: HWFL-1 master prompt + `docs/path-a-manufacturing-spec.md`
