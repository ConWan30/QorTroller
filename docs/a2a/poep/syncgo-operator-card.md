# SYNC-GO operator card — first GOs under ACTIVE_GAMEPLAY

**Goal:** mid-drive attach that issues real-hardware GOs (`n_go_issued >= 2`), not a cold
`IDENTITY_ONLY` with `n_go=0`. Zero spend; do **not** flip `L6B_ENABLED` / `poep_enabled`.

## 1. Topology
- Edge USB → **this PC** as active host (break BT→console dual-connect).
- PS Remote Play carries input to the console.
- Hold **R2 lightly** during play so trigger fraction > 0 (amp 60–80 is easy to miss if R2 is idle).

## 2. Shell A — bridge (LEAN + campaign)
Process-scoped only (never edit `bridge/.env`). See `docs/poep-campaign-runbook.md`:
```powershell
$env:POEP_CAMPAIGN_MODE = "true"
$env:POEP_LIVE_FIRE_ENABLED = "1"
$env:GAME_PROFILE_ID = "ncaa_cfb_27"   # optional CFB 27
python -m bridge.vapi_bridge.main
```
Expect: `POEP-CAMPAIGN: L6b analyzer initialized for RING CAPTURE ONLY`.

## 3. Shell B — preflight + attach
```powershell
$env:POEP_LIVE_FIRE_ENABLED = "1"
# optional eye-check:
#   curl -H "x-api-key: $env:OPERATOR_API_KEY" http://127.0.0.1:8080/operator/bridge/capture-health
python scripts/poep_session_identity_attach.py --live `
  --api-key $env:OPERATOR_API_KEY `
  --fire-timeout 25 `
  --wait-active-s 45 `
  --amplitude 80 `
  --challenges 2
```

Preflight polls capture-health until `window_n>=3`, `live_trigger_active_fraction>0`, and PCC
(`NOMINAL` + `EXCLUSIVE_USB|UNKNOWN`). Timeout → **exit 3** (no attach, no silent `n_go=0`).

## 4. Success signals
- Feel R2 tugs (amp 80).
- Artifact `audits/poep_session_identity_attach_<sid>.json`: `n_go_issued >= 2`, preferably
  `n_go_verify_pass >= 1`.
- Verdict: `SYNCHRONIZED_CONTROLLER` **or** honest `IDENTITY_ONLY` with non-zero GO evidence
  (next gap = verify/clock, not “never fired”).

## 5. Fail-closed (expected, not a forge path)
- Menu / cold window / DEGRADED capture → wait lines, then exit 3 or sealed `refused_activity` /
  `refused_pcc` — never free-fire.
