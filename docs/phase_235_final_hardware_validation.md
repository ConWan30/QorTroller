# Phase 235-FINAL Hardware Validation Report

**Date:** 2026-04-22  
**Protocol version:** Phase 235-GAD (Bridge 2444 / SDK 527)  
**Purpose:** Empirical validation of PCC + GAD behavior on real DualSense Edge hardware before the 100-session grind begins.  
**Status:** PENDING OPERATOR EXECUTION

---

## Pre-Validation Setup Checklist

Before beginning, confirm all of the following:

| # | Check | Status |
|---|-------|--------|
| 1 | Bridge installed: `python -m bridge.vapi_bridge.main --help` succeeds | [ ] |
| 2 | `bridge/.env` has `GRIND_SESSION_ID=grind_test_20260422` | [ ] |
| 3 | `bridge/.env` has `GRIND_MODE=true` | [ ] |
| 4 | `bridge/.env` has `GRIND_TARGET=5` (5 target for test, not 100) | [ ] |
| 5 | DualSense Edge controller fully charged | [ ] |
| 6 | PS5 is completely OFF (not standby) | [ ] |
| 7 | No other USB devices contesting HID bus | [ ] |

---

## Phase A — Bridge Startup and PCC Warmup (5 min)

**Operator procedure:**

1. Connect DualSense Edge via USB-C directly to laptop (no hub)
2. Start bridge: `cd C:\Users\Contr\vapi-pebble-prototype && python -m bridge.vapi_bridge.main`
3. Observe startup log for grind header block

**Expected startup log:**
```
============================
GRIND SESSION ID : grind_test_20260422
GRIND MODE       : ACTIVE
GRIND TARGET     : 5
============================
```

**Checkpoint A.1 — Startup log observed:**
```
[paste actual startup log here]
```
- PASS / FAIL: ___

**Checkpoint A.2 — GET /bridge/capture-health initial state:**
```json
[paste response here]
```
Expected:
- `capture_state`: NOMINAL
- `host_state`: EXCLUSIVE_USB
- `grind_ready`: true (after 30s warmup)
- `session_counting_paused`: false

Observed `grind_ready` transition time: ___ seconds  
- PASS / FAIL: ___

**Checkpoint A.3 — GET /bridge/grind-chain-status initial state:**
```json
[paste response here]
```
Expected: `chain_length: 0`, `chain_intact: true`  
- PASS / FAIL: ___

---

## Phase B — Competitive Gameplay (10 min)

**Operator procedure:**

1. Launch NCAA CFB 26
2. Start a Play Now or Exhibition game (CPU vs CPU or vs CPU)
3. Play through at least 2 full drives (~5 minutes game clock)
4. Ensure you are snapping the ball with R2 (this is what GAD measures)
5. Return to NCAA main menu when done (controller still USB-connected)

**Checkpoint B.1 — GET /bridge/capture-health after gameplay:**
```json
[paste response here]
```

| Field | Expected | Observed | Pass? |
|-------|----------|----------|-------|
| `consecutive_clean_toward_target` | ≥ 1 | ___ | ___ |
| `latest_gameplay_context` | ACTIVE_GAMEPLAY | ___ | ___ |
| `capture_state` | NOMINAL | ___ | ___ |
| `host_state` | EXCLUSIVE_USB | ___ | ___ |
| `grind_ready` | true | ___ | ___ |

**Checkpoint B.2 — GET /bridge/grind-chain-status after gameplay:**
```json
[paste response here]
```

| Field | Expected | Observed | Pass? |
|-------|----------|----------|-------|
| `chain_length` | ≥ 1 | ___ | ___ |
| `chain_intact` | true | ___ | ___ |
| `latest_gic_hash` | 64-char hex | ___ | ___ |
| `latest_gameplay_context` | ACTIVE_GAMEPLAY | ___ | ___ |

**Phase B overall: PASS / FAIL / AMBIGUOUS**

---

## Phase C — Menu Navigation (8 min)

**Operator procedure:**

1. From NCAA main menu, enter Dynasty mode
2. Spend 5–6 minutes navigating recruiting screens, roster management, weekly menus
3. Do NOT enter any actual game — do not snap the ball
4. Exit back to main menu

**Checkpoint C.1 — GET /bridge/capture-health after menu navigation:**
```json
[paste response here]
```

| Field | Expected | Observed | Pass? |
|-------|----------|----------|-------|
| `consecutive_clean_toward_target` | UNCHANGED from Phase B | ___ | ___ |
| `latest_gameplay_context` | MENU_DETECTED (or NULL if no new adjudication cycle) | ___ | ___ |

**Checkpoint C.2 — GET /bridge/grind-chain-status after menu navigation:**
```json
[paste response here]
```

| Field | Expected | Observed | Pass? |
|-------|----------|----------|-------|
| `chain_length` | UNCHANGED from Phase B | ___ | ___ |
| `chain_intact` | true | ___ | ___ |

**Note on Phase C:** If the adjudication cycle has not fired since Phase B ended, `latest_gameplay_context` may still read ACTIVE_GAMEPLAY. This is not a failure — it means no new ruling was processed during the menu session. The key signal is that `consecutive_clean_toward_target` did not advance.

**Phase C overall: PASS / FAIL / AMBIGUOUS**

---

## Phase D — PS5 Interference / CONTESTED State (8 min)

**Operator procedure:**

1. With bridge still running and controller USB-connected to laptop
2. Power ON PS5 using console power button (NOT the controller)
3. Wait 30 seconds for PS5 to attempt to claim the controller
4. Query GET /bridge/capture-health — observe host_state
5. If controller stays connected: attempt to play NCAA for 3–4 min during contested period
6. Power PS5 OFF
7. Wait 45 seconds for bridge to return to NOMINAL + EXCLUSIVE_USB
8. Query both endpoints

**Checkpoint D.1 — GET /bridge/capture-health during PS5 interference:**
```json
[paste response here]
```

| Field | Expected | Observed | Pass? |
|-------|----------|----------|-------|
| `host_state` | CONTESTED or DEGRADED or DISCONNECTED | ___ | ___ |
| `grind_ready` | false | ___ | ___ |
| `session_counting_paused` | true | ___ | ___ |
| `consecutive_clean_toward_target` | did not advance | ___ | ___ |

**Checkpoint D.2 — GET /bridge/capture-health after PS5 OFF + 45s:**
```json
[paste response here]
```

| Field | Expected | Observed | Pass? |
|-------|----------|----------|-------|
| `host_state` | EXCLUSIVE_USB | ___ | ___ |
| `grind_ready` | true | ___ | ___ |
| `session_counting_paused` | false | ___ | ___ |

**Checkpoint D.3 — GET /bridge/grind-chain-status after recovery:**
```json
[paste response here]
```

| Field | Expected | Observed | Pass? |
|-------|----------|----------|-------|
| `chain_intact` | true | ___ | ___ |
| `chain_length` | UNCHANGED from Phase B (CONTESTED sessions do not stamp GIC) | ___ | ___ |

**Phase D overall: PASS / FAIL / AMBIGUOUS**

---

## Phase E — Data Export and Teardown (4 min)

**Operator procedure:**

1. Stop bridge (Ctrl+C)
2. Export test data: `python scripts/grind_test_tools.py export grind_test_20260422`
3. Paste the JSON output below
4. Purge test data: `python scripts/grind_test_tools.py purge grind_test_20260422`
5. Confirm no rows remain: `python scripts/grind_test_tools.py verify-empty grind_test_20260422`

**Phase E export output (paste here for Claude Code analysis):**
```json
[paste grind-export-test JSON output here]
```

---

## Claude Code Analysis (completed after operator paste)

*This section will be filled in by Claude Code after the operator pastes the Phase E export.*

### Phase B analysis
- consecutive_clean_toward_target: ___
- trigger_active_fraction values: ___
- grind_chain_hash present: ___
- Verdict: PASS / FAIL / AMBIGUOUS

### Phase C analysis
- MENU_DETECTED rows: ___ (grind_chain_hash should be NULL for all)
- Streak did not advance: ___
- Verdict: PASS / FAIL / AMBIGUOUS

### Phase D analysis
- CONTESTED/DEGRADED rows during PS5 active: ___
- grind_chain_hash on contested rows: NULL (expected)
- Chain length unchanged after recovery: ___
- Verdict: PASS / FAIL / AMBIGUOUS

### Summary

| Phase | Result | Notes |
|-------|--------|-------|
| A | ___ | |
| B | ___ | |
| C | ___ | |
| D | ___ | |

**Overall validation: PASS / FAIL / AMBIGUOUS**

---

## Sign-Off

Operator sign-off: ___  
Date/time: ___  
Grind environment confirmed clean for GRIND_SESSION_ID=grind_phase235_v1: ___

*After PASS on all four phases, reset bridge/.env to:*
```
GRIND_SESSION_ID=grind_phase235_v1
GRIND_MODE=true
GRIND_TARGET=100
```
*and begin session one of the real grind.*
