# PoEP Campaign Runbook — single-HID bridge fire+IMU ring (2026-07-25)

> **STATUS:** Campaign procedure guide. This is the companion file referenced by
> `docs/context_note_2026_07_25_gad_apop_three_purposes.md` ("committed in the same
> doc commit"). It is the operational recipe for running a PoEP campaign against
> the bridge's single-HID fire+IMU ring AFTER F-RIG27-1/2 are shipped on main.
>
> **NOT a permission slip.** Every claim ceiling here mirrors the load-bearing
> discipline already in CLAUDE.md and the sealed modules — the BridgeFireCaptureAdapter
> is a CANDIDATE/MECHANISM lane. Running a campaign flips NOTHING: `poep_enabled`
> stays False, `L6B_ENABLED` is unchanged, `L6_CHALLENGES_ENABLED` stays false.

## What this runbook FOR

A campaign is the operator-side execution of the BridgeFireCaptureAdapter code
path to grow the usable-Edge-reflex corpus and produce SYNCHRONIZED_CONTROLLER
session-liveness CANDIDATES. It is NOT a tournament gate, NOT a buyer pilot,
NOT an identity ceremony — it's the bridge firing nonce-bound probes against
its own single reader while the player plays, and the attach CLI honestly
verdicting STUDENT → IDENTITY_ONLY or (under real hardware fire)
SYNCHRONIZED_CONTROLLER for each session.

The honest topology crux (preserved verbatim from the F-RIG27 fix arc — this is
load-bearing; do not edit):
> Candidate=True REQUIRES `activity_source=="bridge"` (bridge UP) but
> exclusive-HID fire refuses while the bridge holds the pad (dual-writer) → the
> BridgeFireCaptureAdapter CANDIDATE/MECHANISM DOES NOT make SYNCHRONIZED
> rig-reachable today under dual-connection, because USB frames carry no live
> input content while the controller is BT-paired to the console.

**The honest SYNCHRONIZED-under-real-play path is the single-HID bridge fire+IMU ring
where ONE bridge reader owns the pad + activity + fire + IMU.** That is what this
runbook runs.

## Three required topology switches BEFORE the campaign can produce SYNCHRONIZED

1. **Break the BT link to the PS5.** The certified DualShock Edge must NOT be
   BT-paired to the PS5 during the campaign. Dual-connection is structurally
   blind: the USB frames the bridge reads carry no live input while the controller
   talks to the console over BT. (Matches 2+3 ran under this topology and could
   not reach SYNCHRONIZED for this reason — F-RIG27 root cause.)
2. **Edge USB-C direct to the PC.** The bridge's single reader must own the
   controller end-to-end.
3. **PS Remote Play carries input to the PS5.** Use Sony's PS Remote Play app
   on the same PC — it forwards Edge input over the network so NCAA CFB 26 still
   receives ball snaps. This is the only supported single-HID topology.

If you skip ANY of those three switches, the campaign is still MECHANISM-only
and the attach CLI will honestly return IDENTITY_ONLY — that is not a bug, it's
the honesty spine doing its job. The run is still useful as corpus growth.

## Pre-flight (operator-side, BEFORE player touches the pad)

```bash
# 1. PV-CI gate green (184 today; if not — STOP, main is broken).
python scripts/vapi_invariant_gate.py                                 # exit 0

# 2. The pre-flight controller gate runs end-to-end on the certified Edge.
#    F-RIG27 fix arc verified TriggerModes.Rigid is the correct enum for the
#    pydualsense version on the rig (Store 3.13 Python where import hid AND
#    import pydualsense both work — see projects docs for the python-venv trap).
python scripts/l6_hardware_check.py                                   # exit 0

# 3. Confirm bridge/.env has the campaign knobs set correctly:
#    - L6B_ENABLED=true                 (the N>=50 usable-Edge gate is MET;
#                                        verified 2026-07-18; 220 usable / 197 independent)
#    - POEP_CAMPAIGN_MODE=true          (process-scoped; never persisted in code)
#    - POEP_LIVE_FIRE_ENABLED=1         (gates the bridge fire endpoint)
#    - GRIND_SESSION_ID=<same id>       (across ALL bridge restarts in the run)
#    - GRIND_MODE=true
#    - GRIND_TARGET=100
#    - GAME_PROFILE_ID=ncaa_cfb_26
#
#    NEVER set POEP_CAMPAIGN_MODE=true while simultaneously changing the sealed
#    modules — campaign mode is a runtime carve-out, not an architecture change.

# 4. Eye-check the capture-card frame BEFORE play (F-RIG27-3 wrong-eye finding).
#    The webcam uvc_index must point at the PLAYER's screen (the screen PS Remote
#    Play is rendering on), NOT the operator's room. Content-verify the first ring
#    crop with your own eyes — do NOT use crop-entropy surrogates.
```

If any of those fail — STOP. The campaign's value is the failure trace, not a re-do.

## The campaign — three shells

### Shell A — start the bridge with campaign knobs

```bash
# From the project root. The bridge owns the single reader + the fire+IMU ring +
# the operator API + the GIC chain. Startup log should show
# "Phase 235-PCC-RATE-FIX: hidapi rate counter live on interface 3" (F-RIG27-1
# evidence) AND "poep_campaign_mode: True" AND "l6b_enabled: True".
python -m bridge.vapi_bridge.main
```

### Shell B — the attach CLI, --live path (the actual campaign loop)

```bash
# This wires the BridgeFireCaptureAdapter as the fire_fn/imu_capture_fn pair.
# It asks the running bridge (Shell A) to fire nonce-bound probes and reads the
# capture-health live_activity_window_n field that F-RIG27-2 stamps (>= 3 window
# + trigger_active_fraction > 0 = ACTIVE_GAMEPLAY). --live IS gated by
# POEP_LIVE_FIRE_ENABLED=1; without it the CLI runs --dry by default and honestly
# returns IDENTITY_ONLY without touching HID.
#
# Optional refinement: pass --context-gate to use APOP's 5-state to prefer
# IN_MATCH_LULL (between-plays) as the probe window — minimizes gameplay
# disruption in football. Default-off; the IMU lull gate alone is fine too.
python scripts/poep_session_identity_attach.py --live --player P2 \
    [--context-gate]
```

### Shell C — verify the session (post-match, before stopping)

```bash
# In a third terminal while the session is still running:
curl -s http://127.0.0.1:8000/operator/bridge/capture-health \
    -H "x-api-key: $OPERATOR_API_KEY" | python -m json.tool
# Look for:
#   capture_state: NOMINAL
#   host_state:    EXCLUSIVE_USB           (single-HID topology — match the switch above)
#   live_activity_window_n: >= 3
#   live_trigger_active_fraction: > 0.0    (F-RIG27-2 fields)
#   poep_campaign_mode: true
#   latest_gameplay_context: ACTIVE_GAMEPLAY (or MATCH_TRANSITION if --context-gate
#                       bound the fire window to between-plays)

# Stop the session and write the identity-attach artifact (Shell B exits on its
# own when the session ends; if you started it with --duration, wait for the
# duration to elapse, then Ctrl-C the CLI, then stop the bridge cleanly).
```

## Honest output of a campaign session

- A session-identity-attach artifact on disk. Its `verdict` field is one of:
  - `IDENTITY_ONLY` — bridges fired dry (no real_hardware fire on every GO);
    this is what `--dry` always returns. Honest, not a regression.
  - `SYNCHRONIZED_CONTROLLER` — every GO had a real single-HID bridge fire AND
    `activity_source=="bridge"` AND PCC NOMINAL AND the ioID identity is bound.
    Candidate only — does NOT flip `poep_enabled` or `L6B_ENABLED`, does NOT
    count toward L6_CHALLENGES.
  - `UNVERIFIABLE` — PCC fail-closed or identity mismatch; honest stop.
- The usable-Edge-reflex corpus grows by the number of real fires recorded.
  Earning-enablement vehicle; the campaign is how the next N-count threshold is
  reached honestly.
- 0 IOTX spent. No `qortroller anchor` is fired by default — that's a separate
  operator-fired ceremony.

## What this runbook explicitly does NOT do

- Does NOT flip `poep_enabled`, `L6_CHALLENGES_ENABLED`, or any FROZEN/PoAC wire.
- Does NOT change the GAD/APOP architecture — three consumers stay; this runbook
  exercises the BridgeFireCaptureAdapter consumer. The probe-timing consumer
  (`presence_challenger --context-gate`) and the telemetry consumer
  (`GET /agent/active-play-occupancy-status`) are exercised in parallel but not
  modified.
- Does NOT produce a "second-human product". The campaign is a corpus-growth +
  candidate-verdict vehicle under the existing four-ceilings freeze.
- Does NOT modify FROZEN invariants. PV-CI stays 184.
- Does NOT auto-anchor. `qortroller anchor` is operator-fired, separate.

## Recovery

- **Port already bound / bridge won't start**: previous bridge didn't release
  :8000. `Stop-Process -Name python -Force` in PowerShell ONLY if you can see
  no other Python work is in flight; otherwise find the PID listening on :8000
  via `netstat -ano | findstr :8000` and kill that single PID.
- **attach CLI returns IDENTITY_ONLY despite --live**: check Shell A's startup
  log for `poep_campaign_mode: True` AND `l6b_enabled: True` AND confirm
  `POEP_LIVE_FIRE_ENABLED=1` is exported in Shell B's env. The CLI fail-closes
  to `--dry` behavior if any of those are missing — honest, not a bug.
- **`host_state=CONTESTED` in Shell C**: you skipped topology switch #1 (still
  BT-paired to PS5). Stop the bridge, unpair, restart. Sessions already counted
  are NOT retroactively removed.
- **`live_activity_window_n=0` in Shell C** after F-RIG27-1/2: the bridge never
  attached its rate counter. Look for the `Phase 235-PCC-RATE-FIX` startup line;
  if absent, the `_pcc_rate_feed` heal path may have hit `_HID_RESTART_CAP=10`
  and given up — the dashboard will honestly show DEGRADED, not fabricated
  NOMINAL. Restart the bridge with a fresh USB enumeration.

## Signed

Operational companion to the APOP/GAD three-purposes context note
(`docs/context_note_2026_07_25_gad_apop_three_purposes.md`). Authored by the
agent (Claude Code session 2026-07-25) after the F-RIG27-1/2 fixes shipped.
The code path is complete; the remaining gates are operator-side topology
switch + execution + eye-check. If those fail, the failure trace tells us
which gate is unreachable under the RP topology specifically.
