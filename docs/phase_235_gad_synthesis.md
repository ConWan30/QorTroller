# Phase 235-GAD Synthesis Report: Gameplay Activity Discrimination
**Date:** 2026-04-22  
**Status:** Phase 2 COMPLETE — **AWAITING OPERATOR APPROVAL before Phase 3 implementation**  
**MCP Validation:** APPROVED (13 invariants checked, 0 violations)

---

## WIF-GAD-1 (W1) — Content-Blind Consecutive_Clean Gate

**Failure mechanism (physically grounded):**
The consecutive_clean gate was designed for anti-cheat purposes — it asks "is this human input
with no cheat codes?" It does NOT ask "is this a competitive gameplay session?" Because every
layer of the PITL stack (L2/L3/L4/L5) derives its signals from controller physics and temporal
patterns rather than game-state semantics, there exists no inference code or evidence field that
distinguishes menu navigation from active competitive gameplay.

**Specific exploit path:**
1. Controller connected via USB (PCC: NOMINAL + EXCLUSIVE_USB confirmed)
2. Player navigates NCAA CFB 26 main menu for 5 minutes (no match entered)
3. Operator calls `request_adjudication` → evidence: 20 records, all inference=0x20
4. hard_cheat_codes=[], advisory_codes=[] → fallback_verdict=FLAG(0.05) → divergence=0
5. Session stamped into GIC chain, consecutive_clean += 1
6. Repeat 100× without ever entering a competitive match
7. GIC_100 hash is cryptographically valid — but certifies nothing about gameplay

**Impact on tournament integrity:**
GIC_100 is the headline artifact for Phase 236 (Zenodo deposit + prior-art anchor).
If GIC_100 was generated from menu sessions, it is a cryptographic proof of human presence
in menu navigation — not of competitive gameplay competency. The chain is intact but semantically
void for the stated purpose: "proof that a human played 100 clean competitive sessions."

**Status:** OPEN — addressed by Phase 235-GAD implementation below.

---

## WIF-GAD-2 (W2) — HID Activity Signature as Gameplay Attestation

**Novel mechanism (VAPI-exclusive):**
The BiometricFeatureExtractor already computes `trigger_onset_velocity_L2` and
`trigger_onset_velocity_R2` every session loop iteration (session_adjudicator.py:194;
dualshock_integration.py:357). These are physically grounded: trigger velocity is non-zero
if and only if the player pressed a trigger during the HID capture window. Similarly,
`stick_autocorr_lag1` approaching 1.0 indicates no stick movement.

By storing a lightweight `game_activity_flag` per PoAC record — derived from features already
being computed — and aggregating across the 20-record evidence window at adjudication time,
VAPI can derive a `gameplay_context` classification that is:

- **PCC-attested**: activity is measured only while capture_state=NOMINAL + EXCLUSIVE_USB
- **GIC-chained**: gameplay_context is committed into the ruling_validation_log row that
  the GIC stamps. Tamper-proofing extends to activity classification.
- **Not replicable without PITL**: the activity flag is anchored to 228B PoAC records with
  PoAC chain integrity. No other gaming protocol chains HID activity classification to a
  cryptographic audit trail.

**Phase candidate:** 235-GAD (this phase)

**Connection to grind integrity:** gameplay_context IN ('ACTIVE_GAMEPLAY', 'MIXED') becomes
a 4th condition in the consecutive_clean PCC gate. This closes WIF-GAD-1 without modifying
the GIC formula, the PoAC wire format, or any frozen invariant.

---

## Recommended Implementation: Approach A — HID Activity Threshold

Among the four candidate approaches evaluated, Approach A (HID activity threshold from existing
feature pipeline) is recommended because:

| Approach | VAPI-exclusive | Fail-closed | No wire format change | No new hardware | Retroactive audit |
|----------|----------------|-------------|----------------------|-----------------|-------------------|
| A: HID activity threshold | YES | YES | YES | YES | YES (via game_activity_flag) |
| B: Session duration gate | Partial | Weak | YES | YES | Partial |
| C: GameplayContextOracle (LLM) | YES | NO (LLM fail-open) | YES | YES | NO |
| D: Operator attestation | NO | Manual | YES | YES | YES |

Approach A uses features already being computed. It is deterministic (no LLM dependency),
fail-closed by design, and produces an auditable per-record flag that enables retroactive
re-classification.

---

## Implementation Plan (Phase 3 — requires operator approval)

### Schema changes (idempotent migrations)

**`pitl_session_proofs` table** — new column:
```sql
ALTER TABLE pitl_session_proofs ADD COLUMN game_activity_flag INTEGER DEFAULT 0
-- 0 = no detectable gameplay activity (menu/idle)
-- 1 = trigger OR stick activity detected (gameplay evidence)
```

**`ruling_validation_log` table** — new column:
```sql
ALTER TABLE ruling_validation_log ADD COLUMN gameplay_context TEXT
-- 'ACTIVE_GAMEPLAY': active_fraction >= 0.30 (6+ of last 20 records had activity)
-- 'MIXED':           active_fraction 0.10-0.30
-- 'MENU_DETECTED':   active_fraction < 0.10
-- NULL:              pre-235-GAD row (no flag data available)
```

### Activity threshold definition

At `_session_loop` time, `game_activity_flag = 1` when ANY of:
- `trigger_onset_velocity_L2 > ACTIVITY_TRIGGER_THRESHOLD (default 0.05)`
- `trigger_onset_velocity_R2 > ACTIVITY_TRIGGER_THRESHOLD (default 0.05)`

These features are already computed by BiometricFeatureExtractor. The threshold 0.05 is
intentionally low — any intentional trigger press crosses it; idle resting finger pressure does not.

**Why not stick deflection?** Stick autocorr is a trailing aggregate (ring buffer). Trigger
velocity is a per-press instantaneous signal. For the GAD purpose, trigger activation is the
most unambiguous indicator of in-game action. Menu navigation uses only D-pad and face buttons
(which trigger their own feature flags separately if we needed them), but NCAA CFB 26 competitive
gameplay requires L2/R2 for snap/sprint. This makes trigger velocity the primary discriminator
for this specific game corpus.

### Config fields (3 new)

```python
gameplay_discrimination_enabled: bool = True   # GAMEPLAY_DISCRIMINATION_ENABLED env
activity_trigger_threshold: float = 0.05       # ACTIVITY_TRIGGER_THRESHOLD env
gameplay_active_fraction_min: float = 0.30     # GAMEPLAY_ACTIVE_FRACTION_MIN env
```

`gameplay_discrimination_enabled=True` is the correct default — not a feature flag.
The gap is a correctness issue, not a capability issue.

### consecutive_clean gate extension

```python
# Existing gate (Phase 235-B):
pcc_ok = (pcc_state == "NOMINAL" and pcc_host_state in ("EXCLUSIVE_USB", "UNKNOWN"))

# New gate (Phase 235-GAD):
_gameplay_disc_enabled = bool(getattr(cfg, "gameplay_discrimination_enabled", True))
_gctx = row.get("gameplay_context")
gameplay_ok = (
    not _gameplay_disc_enabled               # gate is off → always allow
    or _gctx in ("ACTIVE_GAMEPLAY", "MIXED") # active evidence
    or _gctx is None                         # pre-235-GAD row → fail-closed
) if _gameplay_disc_enabled else True

session_counts = row["divergence"] == 0 and pcc_ok and gameplay_ok
```

Wait — pre-235-GAD rows with NULL: should they be fail-closed or fail-open?
The grind has NOT started yet. There are zero rows in ruling_validation_log.
Therefore NULL = fail-closed is safe and correct (same precedent as Phase 235-B PCC gate).

```python
gameplay_ok = (
    _gctx in ("ACTIVE_GAMEPLAY", "MIXED")  # explicit active evidence required
) if _gameplay_disc_enabled else True
# NULL → not in ('ACTIVE_GAMEPLAY', 'MIXED') → gameplay_ok=False → fail-closed ✓
# MENU_DETECTED → fail-closed ✓
```

### Operator override (retroactive capability)

```
POST /operator/override-gameplay-context
  params: api_key (required), ruling_validation_log_id (required), reason (≥10 chars)
  action: UPDATE ruling_validation_log SET gameplay_context='ACTIVE_GAMEPLAY' WHERE id=?
  logs: to agent_events (event_type='gameplay_context_override')
  use case: controller analog stick fault caused false MENU_DETECTED classification
```

### Test plan: +4 bridge, +2 SDK

**Bridge tests** (`bridge/tests/test_phase235_gad.py`):
- `test_active_gameplay_context_counts` — game_activity_flag=1 in 8/20 records (0.40 fraction) → ACTIVE_GAMEPLAY → counts
- `test_menu_detected_breaks_streak` — game_activity_flag=0 in all 20 records → MENU_DETECTED → doesn't count
- `test_null_gameplay_context_fails_closed` — NULL gameplay_context (pre-235-GAD) → doesn't count
- `test_operator_override_sets_active` — POST /operator/override-gameplay-context → ACTIVE_GAMEPLAY → counts

**SDK tests** (`sdk/tests/test_phase235_gad_sdk.py`):
- `test_capture_health_includes_gameplay_context` — GET /bridge/capture-health response includes `gameplay_context_enabled` key
- `test_grind_status_gameplay_context_fields` — GET /bridge/grind-chain-status response includes latest `gameplay_context`

### Test count impact

| Suite | Before | After 235-GAD |
|-------|--------|---------------|
| Bridge | 2434 | 2438 (+4) |
| SDK | 525 | 527 (+2) |
| Hardhat | 522 | 522 (unchanged) |

### CLAUDE.md updates required

- `grind_semantics:` — add gameplay_context gate condition
- `gic_invariants:` — note gameplay_context stored alongside GIC-stamped rows
- `gameplay_context_classification:` — new gotcha section

---

## Novel Claim (for Phase 236 prior-art anchor)

> VAPI is the first gaming integrity protocol to derive a cryptographically-anchored
> gameplay activity classification from the same HID feature pipeline used for anti-cheat
> detection, chain it to a GIC audit trail, and require it as a gate condition for grind
> certification. The `game_activity_flag` — derived from controller trigger velocity already
> computed by the PITL stack — closes the semantic gap between "human present" and "human
> playing competitively" without introducing any new hardware requirement or modifying the
> frozen 228-byte PoAC wire format.

---

## Operator Approval Required

The following decisions require explicit operator confirmation before Phase 3 proceeds:

1. **gameplay_discrimination_enabled default = True** — recommended (correctness gate, not
   optional feature). Alternative: default=False + require explicit env var. Tradeoff: True
   is safer for grind integrity; False gives more operator control.

2. **NULL gameplay_context → fail-closed** — recommended (same as PCC gate precedent).
   Since grind hasn't started, zero rows exist. No backward compatibility concern.

3. **Activity threshold = 0.05 trigger velocity** — recommended for NCAA CFB 26 corpus.
   Could be made configurable. Higher threshold = more selective (only strong trigger presses
   count); lower = any incidental pressure counts.

4. **'MIXED' sessions count** — recommended. A session where 15-29% of records had trigger
   activity is likely a transition (loading screen → gameplay). Requiring 100% active is too
   strict. Alternative: only 'ACTIVE_GAMEPLAY' counts (require 30%+).

5. **GameplayContextOracle as agent #39** — the logic can live in the validator (simpler) or
   as a new named fleet agent (more auditable, adds to fleet Merkle). Recommend: validator
   (avoids fleet count drift mid-grind; can be promoted to agent in Phase 236 post-grind).

**To proceed: confirm approved approach or specify changes. Phase 3 implementation will
begin immediately upon operator confirmation.**
