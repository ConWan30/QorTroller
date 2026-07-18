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
- Edge `581a836c…` connected USB (dual-connect: BT->PS5 for play, USB->PC for the ring).
- `bridge/vapi_bridge/qortroller_retina_capture.py` imports clean (the denser-sampling stash is
  reverted; the WIP lives in `stash@{0}` for later validation).
- `OPERATOR_API_KEY` at hand (the fire endpoint requires the full key).

## The session (two shells)

**Shell A — the bridge (process-scoped campaign env):**
```powershell
$env:POEP_CAMPAIGN_MODE = "1"        # ring prerequisites only; scoring/auto-tick stay gated
$env:POEP_LIVE_FIRE_ENABLED = "1"    # the fire gate (never CI)
python -m bridge.vapi_bridge.main
```
Startup log must show: `POEP-CAMPAIGN: L6b analyzer initialized for RING CAPTURE ONLY`.

**Shell B — the one-command capture (after the bridge is up + you are playing):**
```powershell
$env:POEP_LIVE_FIRE_ENABLED = "1"
python scripts/poep_session_identity_attach.py --live --api-key $env:OPERATOR_API_KEY
```
Fires sparse nonce-bound low-amp R2 challenges during active play; react the instant you feel the
buzz. The artifact lands in `audits/poep_session_identity_attach_<sid>.json` (gitignored).

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
