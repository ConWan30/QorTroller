# First CFB 27 rig session — 2026-07-18 (campaign mode, RP topology)

**Setup:** bridge under `POEP_CAMPAIGN_MODE=true` + `POEP_LIVE_FIRE_ENABLED=1` + `GAME_PROFILE_ID=
ncaa_cfb_27` (process-scoped; `.env` untouched); Edge `581a836c…` USB->PC as ACTIVE host; PS Remote
Play carrying input to the PS5; CFB 27 live. Session span 02:57->03:15 local (~18 min). Zero spend;
no flag flips; `L6B_ENABLED`/`poep_enabled` stayed False; kill-switch verified suppressing a tx live.

## Banked wins
- **The RP topology re-validated on CFB 27** — the dual-connection capture blind was re-confirmed
  live (dual-connect: full poll rate, ZERO records), then broken by the switch to Remote Play:
  **448 verified PoAC records in 18 min** with REAL content (R2=255 sprint pulls seen; conf 190-230).
  The first CFB 27 controller corpus.
- **Campaign carve-out engaged exactly as designed:** startup log `POEP-CAMPAIGN: L6b analyzer
  initialized for RING CAPTURE ONLY (l6b_enabled stays False; scoring + auto-tick stay gated)`.
- **Live coupling evidence:** 27 presence bursts (16 COUPLED_CLEAN, coupling ~0.17); trigger-HUD
  coupling `th_fires=5`, `th2_coupling≈0.27`; `Retina combat-trigger: R2 fire -> auto presence burst`.
- **Honest telemetry observations:** L9 video lobe read `REPLAY_OR_RELAY` — correctly detecting that
  Remote Play IS a relay (advisory); killfeed OCR `NO_KILL_EVENTS` (Warzone grammar on a football
  game — the scoreboard-OCR arc's job); RGC governor `unsteady_fps` on WGC monitor capture.

## Findings (all live-diagnosed)
- **F-RIG27-1 — PCC rate-counter starvation (false-negative attestation):** the side hidapi thread
  feeding `capture_state`/`poll_rate_hz` never attached in this run (`rate=0.0` -> DISCONNECTED)
  while the main reader minted 448 records with real content. The attach CLI's PCC gate reads that
  surface -> would refuse fires. Fix candidate: rate-counter re-attach/retry, or a PCC source that
  reads the main reader's frame cadence.
- **F-RIG27-2 — no adjudicator => `latest_gameplay_context` never stamps:** the GAD/APOP context
  only stamps at session adjudication; no adjudication ran in this (non-grind) bridge config, so the
  activity gate could never green regardless of play. Fix candidate: a LIVE activity surface on
  capture-health (e.g. trigger_active fraction over the last evidence window) for the attach CLI's
  fetcher, or adjudicator enablement in campaign sessions.
- **F-RIG27-3 — wrong-eye AGAIN, caught by the protocol:** video idx 1 was a WEBCAM (operator's room
  + person); the HDMI capture card was NOT enumerated at all. All 18 dumped files PURGED immediately
  (never committed, dir untracked). The EYE-CHECK content-verify caught it on the FIRST frame —
  second live validation of the F-MATCH-2 protocol. Scoreboard ROI dumps deferred until the card is
  present (verify by in-memory stats THEN one eye-checked frame).
- **F-RIG27-4 — env-convention trap (fixed pre-session):** `POEP_CAMPAIGN_MODE="1"` does NOT
  activate (Config booleans parse `"true"`; `POEP_LIVE_FIRE_ENABLED` parses `"1"` — legacy split).
  Runbook corrected before launch; caught by preflight.
- **F-RIG27-5 — operator-API doubled prefix (fixed pre-session):** the fire endpoint's real external
  path is `/operator/operator/poep/fire` (sub-app mounted at `/operator` + in-app routes carry their
  own `/operator/`), and capture-health is `/operator/bridge/capture-health`. Client adapter + attach
  CLI URLs corrected; verified live via status codes (403-with-bad-key = alive + auth-gated).

## Eye-check sheet (CFB 27 addendum)
1. Capture-card content check — **FAIL/N-A** (card absent; webcam caught + purged; F-RIG27-3).
2. `latest_gameplay_context==ACTIVE_GAMEPLAY` mid-drive — **NOT STAMPED** (F-RIG27-2), but the
   UNDERLYING assumption CONTENT-CONFIRMED: R2 sprint pulls (255/255) seen throughout play.
3. R2-quiet windows between plays — **OBSERVED** (R2 values 32<->255 alternating with play cadence).
4. L2C non-None under Tackle Stick — **NOT CAPTURED** (needs a longer session + telemetry pull).
5. AIT RS-neutral discipline — N/A (no still-hold capture this session).
6. Scoreboard ROI dumps — **DEFERRED** (card absent).

## Shell B / SYNCHRONIZED status
NOT attempted — F-RIG27-1/2 mean the sealed gates would honestly refuse (the rails worked as
designed against false-negative attestation). The fires + candidate artifact wait for the two
attestation-feed fixes; the corpus + coupling evidence banked regardless.

## Session fixes staged in this commit
`poep_bridge_fire_adapter.py` + `poep_session_identity_attach.py` (real external paths),
`poep-campaign-runbook.md` (env `"true"` + RP-topology correction + eye-check wording).

**Next arc:** F-RIG27-1 + F-RIG27-2 (the two attestation feeds) via the A2A loop -> Shell B green
next session; scoreboard ROI dumps when the card returns.
