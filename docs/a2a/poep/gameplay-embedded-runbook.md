# Gameplay-embedded PoEP session — operator runbook

**Scope:** sparse, activity-gated, in-play presence challenges joined to a `session_id`. Candidate
(FLIP-A host-trusted session liveness) — NOT identity, NOT anti-compromised-PC. `poep_enabled` stays
**False**. Dry path needs no hardware; live HID fire is a later increment.

## Topology (live path, when wired)

Dual-connect (operator standard): **USB → PC** carries the adaptive-trigger challenge + IMU capture;
**BT → console** carries gameplay. The **bridge must be UP** for the live path (unlike the desk path,
where the bridge is often DOWN for HID-exclusive capture). Document honestly if v1 live is
"bridge-orchestrated USB challenge while BT plays."

## Amplitude (LOAD-BEARING)

In-game challenge force stays **LOW** so play remains usable — default **60**, hard ceiling **80**
(`LOW_AMPLITUDE_FORCE_MAX`). The desk `force=255` default is **never** used mid-game; the CLI clamps any
higher value down to 80.

## Dry run (no HID, no chain, 0 IOTX)

```
python scripts/poep_gameplay_session.py start --player P1 --device-id <device_id_hex>
python scripts/poep_gameplay_session.py tick  --activity-json '{"gameplay_context":"ACTIVE_GAMEPLAY"}'
python scripts/poep_gameplay_session.py tick  --activity-json '{"trigger_active_fraction":0.4}'
python scripts/poep_gameplay_session.py challenge-dry --kind GO    --outcome pass
python scripts/poep_gameplay_session.py challenge-dry --kind NO_GO --outcome pass
python scripts/poep_gameplay_session.py stop --out audits/poep_gameplay_session_P1.json
```

- `challenge-dry` injects a SYNTHETIC outcome but runs the REAL `verify_live_response` + catch scoring —
  the plumbing is genuine; `live_hardware=False` on every dry event. **The CLI enforces the activity
  gate** (round-04): a challenge is REFUSED (exit 3) unless the latest `tick` was `ACTIVE_GAMEPLAY`
  (`--ignore-gate` bypasses it as loud plumbing-only).
- The summary reports **two distinct booleans** (round-04): `dry_plumbing_ok` (the gates fired — a
  harness result) and `presence_session_candidate_ok` (a real candidate — **requires `mode="live"` +
  all-GO-live + bridge-attested activity**). A DRY CLI session can reach `dry_plumbing_ok=True` but
  **NEVER** `presence_session_candidate_ok=True`; the name can no longer be read as a verdict. The
  floor is `MIN_GO_VERIFY_PASS=2` (a single pass is not a session).

## Live run (NOT wired this increment)

`challenge-live` is a `LIVE_TODO` stub — it refuses (exit 3). Wiring the real HID fire (bridge UP +
dual-connect + low amplitude, reusing the live fire primitive) is a later PR; ship dry first.

## Activity gate

`classify_activity(sample)`: `gameplay_context` (ACTIVE_GAMEPLAY / MENU_DETECTED) →
`trigger_active_fraction` (>0 active) → `trigger_active`/`stick_active` bools → else **UNKNOWN**
(fail-closed: no challenge on UNKNOWN or MENU). The **CLI enforces this gate** (round-04 F-GP-1):
`challenge-dry` refuses unless the latest tick was ACTIVE_GAMEPLAY. The sparse CSPRNG delay (90–300 s
default) is enforced by the live scheduler; CLI-inject activity is UNTRUSTED (`activity_source=
cli_inject`) and can never mint a presence candidate — only bridge-attested activity in a live session can.

## Rails

`poep_enabled`/`L6B`/`L6_CHALLENGES` False · staged-only · operator sole committer · no FROZEN/PoAC/chain ·
desk capture scripts unchanged (calibration-only). The session summary is one artifact per session — not
40 desk-JSON overwrites.
