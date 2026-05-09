# Phase O1 D — Minimal-Runtime Shadow Accumulation Procedure

**Goal.** Accumulate Cedar evaluation + drift-detection entries in
`operator_agent_shadow_log` and `operator_agent_drift_log` over a multi-
week calendar window, **without** running the DualShock biometric pipeline
that drains laptop batteries.

**Why this works.** Operator-track agents (Sentry, Guardian, Cedar
drift sweeper, FSCA) are independent of the PoAC capture stack. Cedar
evaluations fire on bundle/scope state and on operator-triggered
`POST /operator/evaluate-agent-action` calls. None of them need
controller frames.

**Battery cost.** With `DUALSHOCK_ENABLED=false`, bridge CPU usage drops
to background-task baseline: drift sweeper (60s/600s polls), FSCA
(900s polls), watchdog (10s `/health` polls). No USB charging current,
no biometric FFTs, no per-record SQLite writes.

## One-time setup

Edit `bridge/.env` to set the minimal-runtime config block. Preserve
existing entries that aren't listed here.

```env
# --- Phase O1 D minimal-runtime block ---

# Disable DualShock transport (the heavy CPU + battery drain)
DUALSHOCK_ENABLED=false

# Keep operator-track agents enabled (these are what we're observing)
CEDAR_DRIFT_SWEEP_ENABLED=true
FLEET_COHERENCE_ENABLED=true   # default true; explicit for clarity
LOOP_HEALTH_MONITOR_ENABLED=true

# Wallet kill-switch stays on — Phase O1 D does not require chain submission
CHAIN_SUBMISSION_PAUSED=true

# Grind state — leave as-is since GIC_100 is already on-chain
# (GRIND_MODE has no effect when DUALSHOCK_ENABLED=false; harmless)

# Operator API key is still needed for shadow eval requests
OPERATOR_API_KEY=vapi-dev-local
```

## Daily run procedure

Start bridge (one terminal):

```bash
python scripts/bridge_watchdog.py
```

Watchdog spawns the bridge subprocess, supervises it, writes WEC events
to `watchdog_event_log`. With `DUALSHOCK_ENABLED=false` the bridge boots
cleanly without controller-detection retries (no "DualShock not found"
warnings).

Verify operator agents are alive:

```bash
curl -s -H "x-api-key: vapi-dev-local" \
  http://127.0.0.1:8080/operator/operator/operator-agent-activation-log \
  | jq '.entries | length'
# Expect: 2 (Sentry + Guardian, anchored 2026-05-03)

curl -s -H "x-api-key: vapi-dev-local" \
  http://127.0.0.1:8080/operator/operator/operator-agent-shadow-log \
  | jq '.entries | length'
# Returns count; grows over time as evaluations fire
```

Bridge can run for as long as your laptop is on. Stop it with `Ctrl-C`
on the watchdog terminal — watchdog will SIGTERM the bridge subprocess
cleanly, append a `BRIDGE_HALT` WEC event, and exit.

## What "accumulation" actually produces

Two tables grow over the window:

| Table | Source of entries | Cadence |
|---|---|---|
| `operator_agent_shadow_log` | `evaluate_agent_action()` calls (operator-triggered POST or future agent-driven) | sporadic, on-demand |
| `operator_agent_drift_log` | `detect_bundle_hash_drift` (60s sweep) + `detect_scope_hash_governance_drift` (600s sweep) when changes detected | only when bundle/scope state actually drifts |

In practice: drift events only fire when something changes (bundle file
edited, on-chain scope updated). If nothing changes during the window,
the drift_log stays small. **That's expected.** The shadow_log accrues
when you intentionally exercise Cedar evaluations against the deployed
bundles.

## Synthetic exercise (optional, recommended for Phase O1 D)

To produce non-zero shadow_log entries during the window, fire periodic
evaluations against canonical actions. Example one-off:

```bash
curl -X POST -H "x-api-key: vapi-dev-local" -H "Content-Type: application/json" \
  http://127.0.0.1:8080/operator/operator/evaluate-agent-action \
  -d '{
    "agent_id": "0xb21e1ec258d2d381c313f84944bd36fbc63badb2c9a24c2412212d3a27e3e42c",
    "skill": "skill:read-wiki",
    "resource": "lane://events/test",
    "context": {"shadow_mode": true}
  }'
```

For sustained accumulation you can wrap this in a cron / Task Scheduler
job that fires once per hour. Record the response (`decision` field) so
you can verify shadow_log entries afterward.

## Intermittent operation is fine

Phase O1 D doesn't require continuous uptime. Calendar duration matters
for collecting natural events; total bridge-running hours don't have a
hard floor. Reasonable patterns:

- **Run during normal laptop use.** Bridge starts when you start work,
  stops when you close the laptop. Calendar 3 weeks ≈ ~150 wall-hours
  of bridge runtime, which is plenty for shadow accumulation given the
  near-zero CPU cost in this mode.
- **Run on a dedicated machine.** If you have a desktop or always-on
  device, bridge can run there 24/7 with the same `bridge/.env` config.
  Battery is no longer a concern.

The 3-week target itself is a calendar-window convention, not an
empirically-derived minimum. Earlier promotion to O2 SUGGEST is
defensible if shadow_log + drift_log show the policy bundles are
behaving as designed.

## Validation checklist before promoting to O2 SUGGEST

When you decide the window has produced enough data, verify:

```bash
# 1. Shadow log has decisions across all expected outcomes
curl -s -H "x-api-key: vapi-dev-local" \
  http://127.0.0.1:8080/operator/operator/operator-agent-shadow-log?limit=1000 \
  | jq '.entries | group_by(.decision) | map({decision: .[0].decision, count: length})'

# 2. Drift log shows zero unresolved BUNDLE_HASH_DRIFT findings
#    (any drift events should have been investigated + acknowledged)
curl -s -H "x-api-key: vapi-dev-local" \
  "http://127.0.0.1:8080/operator/operator/operator-agent-drift-log?since_minutes=43200" \
  | jq '.entries | length'

# 3. FSCA has no active CRITICAL contradictions involving operator agents
curl -s -H "x-api-key: vapi-dev-local" \
  http://127.0.0.1:8080/agent/fleet-coherence-summary \
  | jq '.by_severity.CRITICAL'

# 4. Bridge stayed under 3-restart-per-hour ceiling for the window
#    (check watchdog_event_log for WATCHDOG_HALT events)
```

If all four check, Phase O1 D is satisfied and operator-track is ready
for Phase O2 SUGGEST anchor (which requires wallet refill — bundles are
pre-authored in commit `9bdb61c5`).

## Rollback to full bridge runtime

When you want the DualShock pipeline back (frontend testing, future
grind sessions):

```env
# bridge/.env
DUALSHOCK_ENABLED=true
```

Restart bridge. STABILITY-3/4/5 fixes ensure the PoAC pipeline runs
without the catastrophic event-loop starvation that motivated the
operator-track separation in the first place.

## Wallet considerations

Throughout Phase O1 D minimal-runtime, `CHAIN_SUBMISSION_PAUSED=true`
holds. No on-chain submissions, no wallet drain. Wallet at 0.132 IOTX
(2026-05-08) is sufficient — Phase O1 D shadow accumulation is entirely
local SQLite. O2 SUGGEST anchor is the next chain interaction; estimated
~0.32 IOTX, deferred until wallet refill.
