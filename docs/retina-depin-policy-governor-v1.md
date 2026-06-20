# Retina DePIN Policy Governor v1

**Status:** Architecture specification (Phase 0 blueprint). Governs trio-retina binding on the
DualSense Edge HID path — **not** a parallel perception stack.

**As of:** 2026-06-20

---

## 1. Purpose

Trio-retina (`trio-retina` package) supplies dynamics schema (`WorldState`, `Event`).
QorTroller maps certified HID windows → `VAPI-RETINA-STATE-v1` commitments bound to PoAC
`record_hash`. The **policy governor** decides when that binding may run and how commitments
join IoTeX DePIN rails (store, provenance, FSCA, adjudicator evidence).

Dynamics computation stays in `retina_controller_embedder.py` / `retina_perception.py`.
Enablement, prerequisites, and DePIN routing stay in `retina_depin_policy.py`.

---

## 2. Prerequisite qualification matrix

| ID | Check | Fail posture |
|----|-------|--------------|
| Q-PKG | `import retina` succeeds | UNARMED |
| Q-HW | Real hardware (`_is_sim_mode` false) | UNARMED |
| Q-TRANSPORT | `dualshock_enabled` and transport running | UNARMED |
| Q-VIDPID | Profile resolves Sony HID (`0x054C:0x0DF2`) | UNARMED |
| Q-EDGE | Profile `sony_dualshock_edge_v1` or PHCI ATTESTED (when `RETINA_CERTIFIED_EDGE_ONLY`) | UNARMED |
| Q-PCC | Capture `NOMINAL` or `DEGRADED` (not `DISCONNECTED`) | UNARMED until warmup |
| Q-POLL | `poll_rate_hz >= 900` | UNARMED |
| Q-AUDIT | Fresh cross-oracle audit artifact | WARN-only for v1 auto-arm |

**Auto-arm:** `RETINA_POLICY_AUTO_ARM=true` (default) arms at runtime when all hard qualifiers pass
after Edge USB connect. Does **not** flip `DUALSHOCK_ENABLED` or persist `.env` changes.

**Manual override:** `RETINA_PERCEPTION_ENABLED=true` arms fleet-wide regardless of qualifiers.

---

## 3. Config split

| Env / field | Default | Role |
|-------------|---------|------|
| `RETINA_POLICY_AUTO_ARM` | `true` | Governor may auto-arm on qualified connect |
| `RETINA_PERCEPTION_ENABLED` | `false` | Operator manual fleet-wide override |
| `RETINA_ADJUDICATOR_CONTEXT_ENABLED` | `true` | Inject `evidence_json.retina` when effective |
| `RETINA_FSCA_CROSS_ORACLE_ENABLED` | `true` | FSCA `RETINA_*` rules when effective |
| `RETINA_EXTERNAL_INGEST_ENABLED` | `false` | `POST /operator/retina-event` webhook |
| `RETINA_CERTIFIED_EDGE_ONLY` | `true` | Auto-arm only for Edge / attested profile |

Effective perception = manual OR (auto-armed with qualifiers satisfied).

---

## 4. DualSense Edge interoperability

| Surface | Requirement |
|---------|-------------|
| HID loop | Snap ring fields match embedder `_SnapLike` |
| Device profile | `sony_dualshock_edge_v1` default via `DeviceProfileRegistry` |
| PoAC binding | Same `device_id` + `record_hash_hex` on `retina_event_log` rows |
| PCC | Re-evaluate policy when capture state changes; disarm on `DISCONNECTED` |
| pitl_meta | `retina_policy_armed`, `retina_policy_arm_source`, `retina_source: hid` |
| Webhook | Gated on `RETINA_EXTERNAL_INGEST_ENABLED`; `source=webhook` |
| Provenance | Synchronous `PERCEPTION_BINDING` child at persist (fail-open) |

---

## 5. IoTeX DePIN alignment

1. **Thin wire, thick off-chain** — 32B `VAPI-RETINA-STATE-v1`; bulk in `retina_event_log` / future DA.
2. **Device sovereignty** — `device_id` axis matches ioID / PoAC / consent.
3. **W3bstream** — mechanical commitment validation only (deferred `INV-W3S-006`).
4. **ioSwarm** — unchanged; Retina advisory to adjudicator/FSCA only.
5. **Namespace** — never alias `world_model_hash`, `pq_commitment`, `retina_state_commitment`.

---

## 6. Observability

- `GET /bridge/retina-policy-status` — qualifiers + effective flags
- `GET /player/session-status` — `retina_policy_armed`, `retina_policy_arm_source`, `retina_qualifiers_summary`
- `POST /operator/disarm-retina-policy` — operator disarm (reason ≥10 chars)
- `retina_policy_log` table — arm/disarm audit trail

---

## 7. Verification discipline

1. V-check prerequisites against live HID/PCC state
2. Implement pure governor module first
3. P-check: pytest + `/bridge/retina-policy-status` + 228B PoAC unchanged
4. Hardware smoke: `scripts/verify_retina_policy_arm.py`

---

## 8. Deferred (Phase 2)

- W3bstream `retina_state_commitment` field + PV-CI `INV-RETINA-*`
- DA bulk upload (Arc 7 pattern)
- PDA `RETINA_PERCEPTION_OBSERVATION` attestation type
- Tournament / humanity formula weighting
