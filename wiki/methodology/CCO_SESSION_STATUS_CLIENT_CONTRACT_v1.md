# CCO Session-Status Client Contract — what a presence consumer reads v1

| Field | Value |
|---|---|
| Status | **Tier 3 DRAFT** — documents the post-Gate-1 read surface; no behavior change |
| Date | 2026-06-20 |
| Parent | `CCO_PHASE_B_DESIGN_v1.md` §B.2; `CCO_T0_POLICY_v1.md`; `L6B_DESK_CALIBRATION_ANALYZER_v1.md` |
| Code | `bridge/vapi_bridge/operator_api/_app.py` (`GET /player/session-status`); `bridge/vapi_bridge/cco_l6b_wiring.py`; `bridge/vapi_bridge/store/calibration.py` |
| Tests | `bridge/tests/test_player_session_status.py` (T-PSS-1..10); `bridge/tests/test_cco_l6b_wiring.py`; `bridge/tests/test_cco_composability.py`; `bridge/tests/test_cco_controller_class_research.py` |

---

## 0. Purpose

Gate 1 (N≥50 L6B calibration) closed 2026-06-20 (`audits/l6b-operator-attestation-2026-06-20.md`). This document makes the close **legible to a presence consumer** — an AGaaS integrator or tournament operator — by tracing exactly what a client reads from the presence layer and, critically, **which fields are authoritative vs advisory**.

The load-bearing distinction this contract exists to enforce: **`reflex_verdict` is advisory telemetry, never an authorization input.** Tournament eligibility is gated on `is_fully_eligible` / `path_a_eligible` (on-chain VIEW), which sit as *siblings* of — not contributors to — the L6B `cco` block.

This is read-only documentation. It introduces no code, no behavior change, no activation.

---

## 1. Endpoint contract

```text
GET /player/session-status
Header: x-api-key: <read key>          # _check_read_key(x_api_key)
Query:  device_id (optional)           # defaults to the most-recent record's device
```

- **Auth:** read-key gated (`_check_read_key`, `_app.py:685`). Not the operator write key.
- **Safety:** read-only composition over existing surfaces; adds NO capture/adjudication authority. Every chain call is a pure VIEW — kill-switch safe (on-chain failure → `onchain=null`, HTTP 200, never 500; T-PSS-5).
- **The presence-relevant blocks in the response:**
  - `cco` — CCO Phase B T0/L6B telemetry (this document's focus)
  - `presence.poep` / `presence.bcc` — PoEP / BCC presence status (dormant by default)
  - `identity_grid` — identity class × presence-ceiling grid; includes `composability` (Phase F) and `controller_class_research` (Phase G, default-OFF)
  - `is_fully_eligible`, `path_a_eligible` — **the authoritative eligibility fields**
  - `humanity_prob`, `pitl_layers` — PITL biometric snapshot

---

## 2. The `cco` block (what `reflex_verdict` lives in)

`assemble_cco_session_status()` (`cco_l6b_wiring.py:228-300`) returns exactly:

```jsonc
"cco": {
  "t0_engine": "L6B",                       // from CapabilityReport; null when oracle unresolved
  "presence_ceiling_candidate": "P-T0",     // honest ceiling for this controller class
  "identity_class": "I0",                   // I0 / Path B / I1
  "profile_id": "dualsense_edge",
  "challenge_type_candidate": "reflex",
  "policy_ref": "CCO_T0_POLICY_v1",
  "reflex_verdict": "REFLEX_OBSERVED",       // or null — ADVISORY telemetry, see §4
  "l6b_enabled": false,                      // default-false activation gate
  "l6b_applicable": false,                   // check_l6b_applicability predicate
  "l6b_skip": null,                          // skip reason when not applicable
  "calibration": {
    "probe_count": 59,
    "target_n": 50,
    "gate_reached": true,
    "reflex_verdict_distribution": { "REFLEX_OBSERVED": 38, "(null)": 21 }
  }
}
```

The `cco` block carries **no eligibility and no humanity probability**. Those are top-level siblings. A consumer cannot read a presence authorization out of `cco`.

---

## 3. Data path: write → aggregate → assemble → serve

| Stage | Code | Result |
|-------|------|--------|
| **Write** | `L6bReflexAnalyzer.analyze()` (`bridge/controller/l6b_reflex_analyzer.py`) → `classification ∈ {HUMAN, BOT, INCONCLUSIVE, NO_RESPONSE}`; `map_l6b_classification_to_reflex_verdict()` (`cco_l6b_wiring.py:64-68`) maps **HUMAN → `REFLEX_OBSERVED`, all else → `null`**; `store.insert_l6b_probe(reflex_verdict=...)` → `l6b_probe_log` | one probe row |
| **Aggregate** | `store.get_l6b_calibration_progress(device_id)` (`store/calibration.py:130-167`) | `{probe_count, reflex_verdict_distribution, latest_probe, target_n:50, gate_reached}` |
| **Assemble** | `assemble_cco_session_status(capability_report, l6b_calibration_progress, l6b_enabled, controller_connected)` (`cco_l6b_wiring.py:228-300`) — `reflex_verdict` = `latest_probe.reflex_verdict` else re-derived from `latest_probe.classification` via the same HUMAN→REFLEX_OBSERVED map | `cco` dict |
| **Serve** | `GET /player/session-status` (`_app.py:680-987`) → returns `"cco": _cco` alongside the authoritative fields | HTTP 200 JSON |

Two write paths feed `l6b_probe_log`, both using the identical map: the bridge auto-probe loop (`dualshock_integration.py`) and the operator desk session (`l6b_desk_session.py::persist_desk_probe`).

---

## 4. Honesty boundaries (the part a partner must understand)

1. **`reflex_verdict` ∈ {`"REFLEX_OBSERVED"`, `null`} — advisory only.** It is *not* a presence verdict and *not* tournament eligibility. It records that the latest L6B probe observed a human-band involuntary reflex; nothing more.
2. **Authoritative eligibility is elsewhere.** `is_fully_eligible.onchain` and `path_a_eligible` are the on-chain VIEW reads a tournament gate consumes. They are structurally separate top-level fields; `reflex_verdict` never feeds them.
3. **The map is conservative.** Only `HUMAN` → `REFLEX_OBSERVED`. `BOT` / `INCONCLUSIVE` / `NO_RESPONSE` → `null`. The surface never emits a "bot detected" claim — it surfaces *presence of an observed reflex* or its absence, not an accusation.
4. **Three default-false activation gates** stand between "validated" and "live":
   - `l6b_enabled` (default false; CI false) — when false, `l6b_applicable=false` and the block is dormant-advisory
   - `poep_enabled` (false) — no PoEP presence claim
   - `REFLEX_OBSERVED` is advisory — confers no tournament eligibility
   Gate 1 validated the *mechanism*; it did not make it *authoritative*. Those are separate states with separate gates.
5. **Band-posture caveat.** `reflex_verdict_distribution` reflects the corpus classified at the **desk** posture (`human_max_ms=350`, USB-jitter accommodation). The **production / tournament** band is `human_max_ms=280` (`Config.l6b_human_max_ms`, `config.py:797`). A distribution shown in the calibration block is a *calibration-posture* count, not a production guarantee. See §5.

---

## 5. Band-split structural note (desk-350 vs production-280)

The desk and production bands are **default-separated on distinct config objects**, but share one override seam:

- Production / CI: `Config.l6b_human_max_ms`, env `L6B_HUMAN_MAX_MS`, **default `280`** (`config.py:797-799`); consumed by `dualshock_integration.py:519`.
- Desk: `DeskProbeConfig.human_max_ms = 350.0`, a frozen dataclass, **script-only, ignores the env** (`l6b_desk_session.py:45`).

`DeskProbeConfig` (350) cannot leak into `Config` (280) and vice-versa — they are different objects on different code paths. The remaining seam is the shared env key `L6B_HUMAN_MAX_MS`: the desk script ignores it, but the live bridge reads it, and **no code clamp rejects a production value `> 280`**. "Production stays 280" therefore rests on:

1. env default `280` when unset (CI + fresh deploys safe) — *structural*
2. `DeskProbeConfig` separation — *structural*
3. "separate operator GO" to widen production — *process gate, not a code clamp*

**Watch point:** widening production `human_max` is not blocked in code; it is blocked by the operator-GO discipline plus the env default. A future hardening option is a `Config.__post_init__` guard rejecting `l6b_human_max_ms > 280` unless an explicit desk-posture flag is set — converting gate (3) from process to code. Not implemented; flagged.

---

## 6. The `identity_grid.composability` block (Phase F — read-only, deploy-hold)

When `CCO_COMPOSABILITY_ENABLED=true` (default **false**), `assemble_composability_status()` (`cco_composability.py`) adds:

```jsonc
"identity_grid": {
  "composability": {
    "schema": "qortroller-composable-claim-v1",
    "option": "F1",
    "readiness": "off_chain_verifiable",   // or prep_only | registry_unreachable
    "composable_claim_hash": "0x…",        // SHA-256(VAPI-COMPOSABLE-CLAIM-v1 || …)
    "poep_commitment": "0x…",
    "poep_recorded": true,
    "mfg_identity_present": true,
    "honesty_rail": "…"
  }
}
```

**Readiness honesty (F-COMPOSE-2):**

| `readiness` | Meaning for integrators |
|-------------|-------------------------|
| `off_chain_verifiable` | Latest `DeviceRegistered` log found; `isRegistrationValid` + `isRecorded` both true; commitment binds to live registry |
| `prep_only` | Registry deployed but scan completed with **zero** matching logs — honest empty, not a failure |
| `registry_unreachable` | Chunked `eth_getLogs` scan failed (RPC/timeout) — **never** masquerades as `prep_only` |

**Authorize on:** still `is_fully_eligible` / `path_a_eligible` only. Composability is enrichment for demand-side integrators building `isFullyEligible()`-style checks off-chain.

Reference device `581a836c…` (DualShock Edge) is the worked **I1 × off_chain_verifiable** example — MFG identity and PoEP registration both present.

---

## 7. The `identity_grid.controller_class_research` block (Phase G — default-OFF)

When `CCO_RESEARCH_SURFACE_ENABLED=true` (default **false**), `assemble_controller_class_research()` (`cco_controller_class_research.py`) adds:

```jsonc
"identity_grid": {
  "controller_class_research": {
    "schema": "qortroller-controller-class-research-v1",
    "enabled": true,
    "grade": "PARTIAL",                    // UNVALIDATED | PARTIAL | VALIDATED | DISABLED
    "controller_class_tier": "PREMIUM_EDGE", // MINIMAL_PAD | MID_TIER | PREMIUM_EDGE
    "profile_id": "sony_dualshock_edge_v1",
    "characterization_status": "PARTIAL_EDGE_ONLY",
    "partner_claim_ceiling": "P-T3",
    "measurement_gates_pending": ["…"],
    "policy_ref": "CCO_POEP_FUSION_v4_PHASE_G",
    "honesty_rail": "…"
  }
}
```

**Honesty rail:** `UNVALIDATED` means no corpus-backed claim for that controller class — not "broken." `PARTIAL` on `PREMIUM_EDGE` reflects Edge-only measurement debt. No automatic promotion to `VALIDATED`; operator-fired only per `CCO_PHASE_G_RESEARCH_v1.md` §4.

---

## 8. What an AGaaS consumer integrates against (the Gate 3 bridge)

For a demand-side pilot (a tournament operator querying the presence layer):

- **Authorize on:** `is_fully_eligible.onchain` (and/or `path_a_eligible` for silicon-rooted Path A). These are the on-chain VIEW reads; they are the gate.
- **Enrich/contextualize with (never authorize on):** `cco.presence_ceiling_candidate` (honest ceiling for the controller class), `cco.reflex_verdict` (latest reflex telemetry), `cco.calibration.gate_reached` (calibration maturity), `presence.poep`, `identity_grid`, `identity_grid.composability` (when enabled), `identity_grid.controller_class_research` (when enabled).
- **Expect honest dormancy:** with `l6b_enabled=false` / `poep_enabled=false` (defaults), the `cco` and `presence` blocks return well-formed dormant values, not fabricated passes.

This is the bridge between "Gate 1 closed internally" and "here is what a tournament operator would query" — the consumer reads a rich advisory context block (`cco`) and a separate authoritative eligibility field (`is_fully_eligible`), and the two never cross.

---

## 9. Citation

`CCO_SESSION_STATUS_CLIENT_CONTRACT_v1 §X [Tier 3 DRAFT; read-surface documentation 2026-06-20]`
