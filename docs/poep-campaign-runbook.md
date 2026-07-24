# POEP Campaign Runbook — the no-scoring capture rig session (operator-fired)

**What this is:** the sanctioned capture path while `L6B_ENABLED` stays false (CLAUDE.md campaign
exception, operator-sealed; grok campaign-r02 pick 1b+1c). Every nonce-bound fire is simultaneously a
SYNCHRONIZED-candidate challenge AND a usable-reflex corpus row (`policy_ref=edge_operator_reflex_v1`).
**Corpus status 2026-07-18: the N>=50 gate is already MET on the Edge (usable 220 / independent 197,
canonical-gate verified)** — so this runbook's purpose is the honest ring session + continued corpus
growth, and enabling `L6B_ENABLED` is now an UNBLOCKED separate operator decision. Nothing here flips
`l6b_enabled` / `poep_enabled`; `bridge/.env` is never edited — the lift is process-scoped env, the
`CHAIN_SUBMISSION_PAUSED` pattern.

## Preconditions
- **TOPOLOGY (corrected 2026-07-18, first CFB 27 rig session — the dual-connection capture blind):**
  the pad's ACTIVE host must be THIS PC. Edge `581a836c…` USB->PC ONLY (break the BT link to the
  console) + **PS Remote Play** carries input to the PS5. Dual-connect (BT->PS5 + USB->PC) polls at
  full rate but the USB frames carry NO live input content (2026-06-26 finding, re-confirmed live
  2026-07-18: zero records dual-connect -> 448 records w/ real content in 18 min under RP).
- `bridge/vapi_bridge/qortroller_retina_capture.py` imports clean (the denser-sampling stash is
  reverted; the WIP lives in `stash@{0}` for later validation).
- `OPERATOR_API_KEY` at hand (the fire endpoint requires the full key).

## CFB 27 session addendum (2026-07-18; grok cfb27-r02 — first rig = truth-gathering, no novel claims)
Set the profile in Shell A alongside the campaign env (process-scoped, like everything else):
```powershell
$env:GAME_PROFILE_ID = "ncaa_cfb_27"     # R2-sprint config transfers from 26; D1-D4 annotated in-profile
```
**First-minutes EYE-CHECK (fill pass/fail; no shame on early unknowns):**
1. Capture card UVC live + EYE-CHECK the first crop CONTENT (game frame, not the room).
2. `GET /bridge/capture-health` -> `latest_gameplay_context == ACTIVE_GAMEPLAY` mid-drive
   (R2 sprint should keep it green — the load-bearing 26 assumption, TO RE-VERIFY on 27 here).
3. R2-quiet windows still exist between plays (probe timing viability).
4. L2C sanity (D1): note whether stick-IMU correlation goes non-None during Tackle Stick /
   ball-carrier sequences — telemetry observation only, NOT a gate.
5. AIT discipline: any still-hold capture needs RS neutral (Tackle Stick fidget risk).
6. **Scoreboard ROI dumps (offline OCR prep):** save a handful of full frames + top-strip
   (~y 0-0.12) and bottom-strip (~y 0.85-1.0) crops during dead time — ROI fractions get MEASURED
   from these 27 frames (never guessed from Warzone habits). No live OCR this session.

## The session (two shells)

**Shell A — the bridge (process-scoped campaign env):**
```powershell
$env:POEP_CAMPAIGN_MODE = "true"     # ring prerequisites only; scoring/auto-tick stay gated
                                     # (Config booleans parse "true" — "1" does NOT activate)
$env:POEP_LIVE_FIRE_ENABLED = "1"    # the fire gate (this one parses "1" — legacy convention)
python -m bridge.vapi_bridge.main
```
Startup log must show: `POEP-CAMPAIGN: L6b analyzer initialized for RING CAPTURE ONLY`.

**Shell B — the one-command capture (after the bridge is up + you are playing):**
```powershell
$env:POEP_LIVE_FIRE_ENABLED = "1"
python scripts/poep_session_identity_attach.py --live --api-key $env:OPERATOR_API_KEY `
  --fire-timeout 25 --wait-active-s 45 --amplitude 80 --challenges 2
```
Fires sparse nonce-bound low-amp R2 challenges during active play; react the instant you feel the
buzz. The artifact lands in `audits/poep_session_identity_attach_<sid>.json` (gitignored).
**SYNC-GO (2026-07-18):** `--wait-active-s` blocks until ACTIVE_GAMEPLAY (warm window + frac>0 +
PCC); timeout exits 3 so cold attach never looks like a silent `n_go=0` success. Full checklist:
`docs/a2a/poep/syncgo-operator-card.md`.

## Honest outcomes (all are wins)
- `SYNCHRONIZED_CONTROLLER` — identity bound + real fires verified during bridge-attested play.
- `IDENTITY_ONLY` — any gate closed / no clean reflexes: still an honest artifact; campaign rows with
  clean physics still grow N.
- Every completed probe with `REFLEX_OBSERVED` + clean IMU physics counts toward N>=50 via
  `is_usable_reflex` (`edge_operator_reflex_v1`). Check progress:
  `GET /player/session-status` -> the L6b calibration block (usable count), or the reflex DB.

## What this does NOT do
- Does NOT flip `L6B_ENABLED` (the humanity-formula 0.14 L6b weight stays quarantined — pins V1/V3).
- Does NOT enable auto-tick probes (strictly `l6b_enabled`-gated — pin V4).
- Does NOT flip `poep_enabled` / advance the presence candidate semantics.
- The N>=50 gate is already MET (2026-07-18 verify) — enabling `L6B_ENABLED` is an UNBLOCKED but
  SEPARATE operator decision + seal; campaign mode stays the no-scoring capture path either way.
