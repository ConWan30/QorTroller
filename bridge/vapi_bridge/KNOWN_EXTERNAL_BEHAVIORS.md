# KNOWN EXTERNAL BEHAVIORS — VAPI-EXT Phase 204+

This file documents the authoritative behavior of `VAPIProtocolLens.isFullyEligible(deviceId)`
as seen from an external sub-protocol (PragmaJudge, VAPI_MOBILE, etc.).

PragmaJudge's `PromptCommitmentRegistry.sol` depends on this contract. Behaviors listed here
are confirmed stable and must remain unchanged across VAPI_CORE evolution.

---

## isFullyEligible(deviceId) — Four Device States

### State 1 — Enrolled, credential active, no active BLOCK ruling
**On-chain:** `PHGCredential.hasCredential(deviceId) == True` AND
             `PHGCredential.isSuspended(deviceId) == False` AND
             `RulingRegistry.getActiveRuling(deviceId) != BLOCK`

**Returns:** `True`

**Bridge proxy:** `store.get_enrollment()` not None AND
                 `store.get_credential_mint()` not None AND
                 `store.is_credential_suspended()` == False

**Confirmed:** VAPI-EXT Step 7 test `test_state1_is_eligible` PASSED

**Gas cost note:** Pure view function — no state modifications. Expected gas: ~8,000–15,000
(measured against Hardhat local node; actual IoTeX testnet cost may differ slightly due
to chain-specific opcodes).

---

### State 2 — Credential exists but TTL expired (expiresAt < block.timestamp)
**On-chain:** `VHPToken.expiresAt(tokenId) < block.timestamp`
             OR `PHGCredential.isSuspended(deviceId) == True` (enforcement path)

**Returns:** `False`

**Bridge proxy:** `store.is_credential_suspended()` == True
                (BiometricCredentialTTLAgent, Phase 178, sets suspension when TTL expires)

**Confirmed:** VAPI-EXT Step 7 test `test_state2_not_eligible` PASSED

**Note:** The bridge represents TTL expiry as an active suspension via `credential_enforcement`
table. Clearing the suspension restores eligibility (reinstate path via Phase 186).

---

### State 3 — Credential suspended (active BLOCK ruling via RulingEnforcementAgent)
**On-chain:** `PHGCredential.isSuspended(deviceId) == True`
             (set by `RulingEnforcementAgent.escalate_to_block()` Phase 66)

**Returns:** `False`

**Bridge proxy:** `store.is_credential_suspended()` == True

**Confirmed:** VAPI-EXT Step 7 test `test_state3_not_eligible` PASSED

**Note:** Suspension is cleared by `chain.reinstate_phg_credential()` after
the suspension window expires. The bridge's `_check_expired_suspensions()` loop
auto-reinstates after `suspended_until` passes.

---

### State 4 — Device never enrolled (deviceId not in VAPIioIDRegistry)
**On-chain:** `VAPIioIDRegistry.isRegistered(deviceId) == False` → no enrollment record

**Returns:** `False`

**Bridge proxy:** `store.get_enrollment()` == None (no enrollment row for device)

**Confirmed:** VAPI-EXT Step 7 test `test_state4_not_eligible` PASSED

**Note:** This is the fail-closed default. Any device not in the enrollment system
returns False without errors or reverts. PragmaJudge should expect this as the
common case for new/unknown devices.

---

## Determinism Guarantee

`isFullyEligible()` is a **pure view function** on-chain. For the same block state:
- Same inputs → same output across any number of calls
- No state modifications
- No reverts for valid (properly formatted) device IDs
- Invalid (zero-padded) device IDs return False without revert

**Bridge-level determinism confirmed:** all four state tests include `_deterministic` assertion.

---

## State Isolation Guarantee

Suspending one device does NOT affect any other device's eligibility.
Each device's state is independent in both the on-chain mappings and bridge store.

**Confirmed:** VAPI-EXT Step 7 test `test_eligible_device_unaffected_by_other_suspended_device` PASSED

---

## Reinstatement Path

Clearing a suspension restores eligibility. This is the path taken by:
- `AttestationBoundRenewalAgent` (Phase 186) after renewal attestation
- Operator override via `POST /agent/override`
- TTL expiry handled automatically by `_check_expired_suspensions()` loop

**Confirmed:** VAPI-EXT Step 7 test `test_clearing_suspension_restores_eligibility` PASSED

---

## PragmaJudge Integration Contract

PragmaJudge's `PromptCommitmentRegistry.sol` may safely depend on:

1. `isFullyEligible()` returning `False` (not reverting) for unknown devices
2. `isFullyEligible()` returning `True` only when credential is BOTH minted AND active
3. State changes (enrollment, suspension, reinstatement) taking effect immediately on-chain
4. No gas cost side effects from `isFullyEligible()` calls
5. The function being callable from any external contract without special permissions

Any deviation from these behaviors is a **P0 incident** and must be resolved before
PragmaJudge can accept any adjudication commitment.

---

*Generated: VAPI-EXT Phase 204, 2026-04-12*
*Test file: `bridge/tests/test_isfullyeligible_external.py`*
