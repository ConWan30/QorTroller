# CCO Phase A — Capability Oracle Output Contract v1

**Document ID:** CCO-PHASE-A-CONTRACT-v1  
**Version:** 1.0  
**Date:** 2026-06-19  
**Status:** Scope + V-check specification — **no bridge code in this phase**  
**Parent:** [`CCO_POEP_FUSION_v4.md`](CCO_POEP_FUSION_v4.md) Phase A; [`CCO_T0_POLICY_v1.md`](CCO_T0_POLICY_v1.md) (Option C)  
**Hold:** Implementation deferred until silicon status confirmed or demand-side pilot materializes.

---

## Phase A goal (read-only)

Wrap existing proto-CCO (`controller/profiles/`, `device_registry.py` detection path) in a single pure function:

```
CapabilityOracle.resolve(vendor_id: int, product_id: int, *, device_id_hex: str | None = None) → CapabilityReport
```

**Constraints (non-negotiable):**

- **Read-only** — no HID writes, no PoEP sessions, no L6B probes, no verdict issuance.
- **No PoEP activation** — `poep_enabled` untouched; no `PRESENT` / commitment emission.
- **Fail-open** — unknown VID/PID → `GENERIC` profile shape, never raises.
- **Conservative ceilings** — `presence_ceiling_candidate` is the maximum tier **honestly advertisable** from manifest data; `characterization_status` states whether measurement backs T1+.

---

## `CapabilityReport` output contract

Frozen field set for Phase A v1. JSON-serializable dict mirror for HTTP endpoint (Phase A.2, future).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema` | `str` | yes | Constant `"qortroller-capability-report-v1"` |
| `vendor_id` | `int` | yes | USB VID (16-bit) |
| `product_id` | `int` | yes | USB PID (16-bit) |
| `profile_id` | `str` | yes | Resolved `DeviceProfile.profile_id`, or `"generic_unknown_v1"` |
| `display_name` | `str` | yes | Human label from profile or `"Unknown Controller"` |
| `detection_source` | `str` | yes | `"vid_pid_registry"` \| `"generic_fallback"` |
| `phci_tier` | `str` | yes | `"NONE"` \| `"STANDARD"` \| `"CERTIFIED"` (from `PHCITier`) |
| `capabilities` | `object` | yes | See capability object below |
| `identity_class` | `str` | yes | `"I0_SOFTWARE"` \| `"PATH_B_HOST_KEY"` \| `"I1_SILICON"` \| `"UNKNOWN"` — from optional `device_id_hex` + MFG lookup when wired; Phase A stub: `"UNKNOWN"` unless caller supplies context |
| `presence_ceiling_candidate` | `str` | yes | `"P-T0"` \| `"P-T1"` \| `"P-T2"` \| `"P-T3"` — **candidate only** |
| `characterization_status` | `str` | yes | `"UNCHARACTERIZED"` \| `"PARTIAL_EDGE_ONLY"` \| `"MEASURED"` — Phase A: all registered profiles → `UNCHARACTERIZED` except Edge-class → `PARTIAL_EDGE_ONLY` |
| `challenge_type_candidate` | `str` | yes | See challenge type enum below |
| `t0_engine` | `str` | yes | Constant `"L6B"` per Option C |
| `t2_t3_engine` | `str` | yes | Constant `"POEP"` per Option C |
| `verdict_types_available` | `list[str]` | yes | Phase A: `["REFLEX_OBSERVED"]` only (PoEP `PRESENT` not activatable) |
| `policy_ref` | `str` | yes | `"CCO_T0_POLICY_v1_OPTION_C"` |
| `as_of` | `str` | yes | ISO-8601 date of oracle ruleset |

**Contract addendum (F-PHASE-B-004, 2026-06-20):** `verdict_types_available` names verdict types the CCO *would* deliver on the **P-T0 / L6B policy path** given appropriate hardware — not a guarantee of live delivery on every profile. Actual `REFLEX_OBSERVED` emission is gated at runtime by the applicability predicate in [`CCO_PHASE_B_DESIGN_v1.md`](CCO_PHASE_B_DESIGN_v1.md) (`cco_l6b_wiring.py`: IMU + DualSense haptic path). IMU-less profiles (e.g. Xbox Elite S2) may list `REFLEX_OBSERVED` here while wiring logs `L6B_SKIPPED` / `NO_IMU` — consistent, not contradictory.

### `capabilities` object

| Key | Type | Source |
|-----|------|--------|
| `has_adaptive_triggers` | `bool` | `DeviceProfile.has_adaptive_triggers` |
| `has_gyroscope` | `bool` | `DeviceProfile.has_gyroscope` |
| `has_accelerometer` | `bool` | `DeviceProfile.has_accelerometer` |
| `has_touchpad` | `bool` | `DeviceProfile.has_touchpad` |
| `pitl_layers` | `list[int]` | `DeviceProfile.pitl_layers` |
| `family` | `str` | `ControllerFamily` name |

### `challenge_type_candidate` enum (Phase A rules)

| Value | When |
|-------|------|
| `adaptive_force` | `has_adaptive_triggers == true` |
| `rumble_imu` | IMU present, no adaptive triggers |
| `stick_timing` | Sticks present, no IMU (future **[UNVALIDATED]**) |
| `button_timing` | No sticks / fight-stick class |
| `generic_input_timing` | `generic_unknown_v1` fallback |

### Ceiling derivation rules (conservative, Phase A)

```
if not profile matched:
    presence_ceiling_candidate = "P-T0"
    challenge_type_candidate = "generic_input_timing"
elif has_adaptive_triggers:
    presence_ceiling_candidate = "P-T3"   # candidate — NOT measured claim
    characterization_status = "PARTIAL_EDGE_ONLY"
    challenge_type_candidate = "adaptive_force"
elif has_gyroscope or has_accelerometer:
    presence_ceiling_candidate = "P-T1"   # [UNVALIDATED] if characterized
    challenge_type_candidate = "rumble_imu"
else:
    presence_ceiling_candidate = "P-T0"
    challenge_type_candidate = "button_timing" or "stick_timing" per sticks
```

**Honesty rail:** `presence_ceiling_candidate` > `P-T0` does **not** authorize live `PRESENT` or tournament gating in Phase A.

---

## V-check — six registered profiles (pre-code)

Expected `CapabilityOracle.resolve(vid, pid)` outputs when wired to `controller/profiles.detect_profile()`.

| Profile | VID:PID (primary) | `presence_ceiling_candidate` | `challenge_type_candidate` | `characterization_status` | Notes |
|---------|-------------------|------------------------------|--------------------------|---------------------------|-------|
| `sony_dualshock_edge_v1` | `054C:0DF2` | `P-T3` | `adaptive_force` | `PARTIAL_EDGE_ONLY` | AIT N=37 insufficient for production FAR/FRR |
| `sony_dualsense_v1` | `054C:0CE6` | `P-T1` | `rumble_imu` | `UNCHARACTERIZED` | No adaptive triggers |
| `scuf_reflex_pro_v1` | `2F24:0011` | `P-T1` | `rumble_imu` | `UNCHARACTERIZED` | IMU yes, no adaptive |
| `battle_beaver_dualshock_edge_v1` | `054C:0DF2` | `P-T3`* | `adaptive_force`* | `PARTIAL_EDGE_ONLY`* | *Registry returns `sony_dualshock_edge_v1` first (priority); explicit override via `DEVICE_PROFILE_ID` |
| `hori_fighting_commander_ps5_v1` | `0F0D:0133` | `P-T0` | `button_timing` | `UNCHARACTERIZED` | No sticks/IMU |
| `xbox_elite_s2_v1` | `045E:0B00` | `P-T0` | `button_timing` | `UNCHARACTERIZED` | No IMU — ceiling capped at T0 despite rumble; no IMU for `rumble_imu` path |

**Unknown VID/PID V-check:**

| Input | Expected |
|-------|----------|
| `vid=0xFFFF, pid=0xFFFF` | `profile_id=generic_unknown_v1`, `presence_ceiling_candidate=P-T0`, `detection_source=generic_fallback` |

---

## Phase A deliverables (when unblocked)

| Step | Deliverable | Activation |
|------|-------------|------------|
| A.1 | `bridge/vapi_bridge/capability_oracle.py` — pure `resolve()` | Code |
| A.2 | `GET /bridge/controller-capability-profile` — read-only JSON | Code + test |
| A.3 | V-check unit tests — six profiles + unknown fallback | Code |
| A.4 | Session status field `presence_ceiling_candidate` (optional) | Phase E; not A |

**Explicitly out of Phase A scope:** L6B probe execution, PoEP sessions, CHIA agentic classifier, HID descriptor parser, on-chain tier fields.

---

## Stop condition (current)

Work **stops after this contract** until:

1. **Silicon status** — Path A `SecureElementBackend` hardware gate (ATECC608 + CH341A) clears F-FW-2 / I-1 path, **or**
2. **Demand-side pilot** — tournament/studio operator requires composable presence + identity surface.

No `CapabilityOracle` Python module until hold lifts.

---

## Document history

| Date | Change |
|------|--------|
| 2026-06-20 | F-PHASE-B-004 addendum: `verdict_types_available` vs runtime applicability predicate |
| 2026-06-19 | Initial contract + V-check table; Phase A code explicitly held |
