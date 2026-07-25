# Context Note — GAD/APOP Serve Three Purposes + F-RIG27-1/2 Scoping (2026-07-25)

> **STATUS:** Scoping note from the second half of Match 3's arc, after operator
> asked "do GAD/APOP both only serve a purpose in regard to GIC adjudication?"
> The honest answer is NO — they serve three distinct purposes, and the
> F-RIG27-2 fix I described in the prior context note only addressed ONE
> consumer. This file captures that distinction so the next session doesn't
> re-scope the same code paths.

## What GAD (Phase 235-GAD) and APOP (Phase 241-APOP) actually do

### 1. GIC adjudication — the role I implicitly assumed was the only one

- `bridge/vapi_bridge/active_play_occupancy.py:95` `resolve_gic_gameplay()`:
  resolves APOP state + legacy GAD into a single gameplay-eligible boolean for
  the GIC consecutive_clean streak. When APOP gate mode = `strict`, only
  `ACTIVE_MATCH_PLAY` / `COMPETITIVE_CONTROL` / `MATCH_TRANSITION` count as
  GIC-eligible. In `shadow` mode (default), legacy GAD's `MENU_DETECTED`
  break is preserved; APOP is logged but non-blocking.

### 2. PoEP probe-timing window — the role I missed

- `bridge/controller/probe_context.py:36` maps `MATCH_TRANSITION` (APOP's
  "between-plays state") → `ContextVerdict.IN_MATCH_LULL` = "ideal probe
  window for the consistency experiment."
- `scripts/presence_challenger.py:491` consumes this via
  `clear_to_fire_context()` as the `--context-gate`: defer firing PoEP
  probes when the player is in ACTIVE match play (don't disturb them
  mid-snap), fire only when between plays. **Completely separate from GIC** —
  it's the live PoEP-ring probe-timing policy.

### 3. Live operator API surface

- `bridge/vapi_bridge/operator_api/agent_grind.py:229` exposes
  `GET /agent/active-play-occupancy-status` (5-state distribution, session
  duration, total sessions). Operational telemetry for the dashboard /
  agent stream, independent of both GIC and probe timing.

## Scope of the F-RIG27-1 + F-RIG27-2 fixes that are SHIPPED

### F-RIG27-1 — PCC rate-counter starvation: FIXED

At `bridge/vapi_bridge/dualshock_integration.py:3288-3349` (`_pcc_rate_feed`):

- Silent-detect: `_PCC_STALL_ITERS=3` consecutive zero-delta iterations WHILE
  frames flow → stall confirmed.
- Healing: `_hid_counter_force_reopen=True` triggers the existing self-healing
  re-open (capped at `_HID_RESTART_CAP=10` to avoid thrashing).
- Honest fallback: while stalled, feed `len(frames)` (main reader's honest
  ~120Hz cadence, never a fabricated 0). Yields DEGRADED, not DISCONNECTED.
- Fail-closed preserved: the sealed PCC gate still refuses fires until the
  true rate recovers.

### F-RIG27-2 — `latest_gameplay_context` never stamped: FIXED (for the attach CLI consumer)

At `bridge/vapi_bridge/dualshock_integration.py:598-607, 1905-1908, 3309`:

- Live activity window: `self._live_activity_window` rolling deque appended
  every iteration with `1 if spc_kwargs.get("trigger_active") else 0` (or `0`
  on no-frames, the fabrication pin at `:1905-1907`).
- **The attach CLI (`scripts/poep_session_identity_attach.py:112-120`)** now
  reads `live_activity_window_n` + `live_trigger_active_fraction` from
  `/operator/bridge/capture-health` instead of `latest_gameplay_context`. Gate:
  `live_activity_window_n >= 3` AND `live_trigger_active_fraction > 0` →
  ACTIVE_GAMEPLAY.

This fix decoupled the attach CLI from the adjudicator-stamped context field
(consumer path #1 — the GIC consumer). The other two APOP consumers
(probe timing + telemetry) are NOT affected by the fix and don't need to be
— they read APOP directly from `active_play_occupancy.py`'s classifier, not
via the adjudicator-stamped `latest_gameplay_context` field.

## Verification

- `bridge/tests/test_attest_feeds.py` — **10/10 PASS** under rig-Python 3.13
  with env cleared (the env contamination fact is in memory).
- The bridge startup log in Match 3 carried `Phase 235-PCC-RATE-FIX: hidapi
  rate counter live on interface 3` — the rate counter IS attaching now.
- Match 3's `/operator/bridge/capture-health` returned
  `live_activity_window_n: 20, live_trigger_active_fraction: 0.20` — exactly
  the fields the attach CLI's gate reads.

## What's actually load-bearing NOW

The code path between "BridgeFireCaptureAdapter is built" and
"SYNCHRONIZED_CONTROLLER receipt against a second human" is complete:
- Both attestation-feed blockers are fixed + tested
- The BridgeFireCaptureAdapter + bridge endpoint is shipped
- The N>=50 usable-Edge-reflex gate is MET (verified 2026-07-18; usable 220,
  independent 197)
- The campaign carve-out is wired (`_poep_campaign_mode` OR `l6b_enabled`)

The load-bearing remaining items are NOT code — they are operator-side execution:

1. **Topology switch** — break the BT link to the PS5, connect the Edge
   USB-to-PC-only, run PS Remote Play to carry input to the PS5. Matches 2+3
   ran under dual-connection which is structurally blind (USB frames carry no
   live input content while the controller is BT-paired to the console).
2. **Run the documented campaign procedure** (three shells — see the runbook
   guide that follows this context note).
3. **Eye-check the capture-card frame** (F-RIG27-3 wrong-eye finding: webcam
   was wrongly enumerated; the EYE-CHECK PROTOCOL caught it; must be re-run
   live, not via crop-entropy surrogates).

## Optional: probe-timing via the `--context-gate` flag

`presence_challenger.py` has an optional `--context-gate` flag that uses
APOP's 5-state to gate PoEP probe fires on `IN_MATCH_LULL` (between-plays).
The current campaign runbook does NOT explicitly call this flag — it runs
default-off, under the IMU lull gate alone. If you want probes to fire
preferentially during between-plays lulls (minimizing gameplay disruption
in football), add `--context-gate` to the shell B invocation. This is an
optional refinement, not a blocker — the probes will fire fine under IMU
lull alone; context_gate just makes them fire at better moments.

## What this note explicitly does NOT do

- Does NOT modify FROZEN invariants, PoAC wire format, or the 228-byte record.
- Does NOT change the GAD/APOP architecture. Three consumers stay; the fix
  decoupled only the attach-CLI's consumer from the adjudicator-stamped
  field.
- Does NOT assert the campaign will succeed. The code-path is complete; the
  remaining gates are operator-side (topology switch + execution + eye-check).
  If those fail, the failure trace tells us which gate is unreachable under
  the RP topology specifically.
- Does NOT push the campaign runbook guide that follows — that's a separate
  file committed in the same doc commit.

## Signed

Authored by the agent (Claude Code session 2026-07-25) after operator
question prompted the scope check. The operator's exact words:
"so these GAD/APOP both only serves a purpose in regard to GIC adjudication?"
Honest answer: no, three purposes, only one of which the F-RIG27-2 fix
addressed. The other two APOP consumers (probe-timing + operator telemetry)
are intact and don't need anything fixed.
