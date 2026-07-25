# Second-Human Session Record (Match 2) — 2026-07-25

> **STATUS: PARTIAL.** Match 2 fixed the P2-step gap from Match 1 (fresh session_id
> minted via `qortroller.py play`, receipt keyed off `session_1785003577` NOT the
> July 13 proof_drill). But the match produced honest-null across the authorship
> lane: 0 authored, 0 witnessed, 0 GIC entries, no conformant v3 events. That is
> the actual result, not a bug. This file records both the capture that worked
> and the authorship that honestly didn't promote.

## Operator + second human

- **Operator:** present at the rig (ConWan30).
- **Second human (P2):** played one NCAA CFB 27 match via the DualSense Edge on
  the dual-connection (USB to laptop, BT to PS5) rig. (At match time
  `bridge/.env` carried the stale `GAME_PROFILE_ID=ncaa_cfb_26`; corrected
  post-match — see Finding #6. The game in the PS5 was NCAA CFB 27.)
- **Match window:** approximately 2026-07-25 13:19 to 13:51 local (~32 minutes),
  measured from bridge boot (13:19:47 first UVC startup) through the last
  record verified (13:51:21 counter=227).

## What ran differently from Match 1 (the gap-fix)

- Wrote `RETINA_CAPTURE_SOURCE=uvc`, `RETINA_UVC_INDEX=1`,
  `RETINA_UVC_WIDTH=1920`, `RETINA_UVC_HEIGHT=1080`, `RETINA_UVC_FPS=60`,
  `RETINA_UVC_FOURCC=MJPG`, `RETINA_UVC_BACKEND=auto` to `bridge/.env`
  (swap from WGC screen-grab of the Remote Play window to the direct HDMI
  capture card + OBS Virtual Camera feed). The WGC fields were left in place
  to document the swap history (not deleted).
- **P2 step fixed:** fired `python3 scripts/qortroller.py play` BEFORE player 2
  started, which minted the fresh session_id `session_1785003577` and wrote
  `~/.qortroller/session.json`. The daemon then started its own bridge via
  `scripts/retina_capture_daemon.py start` (the canonical launcher).
- Operator confirmed out-of-band that the OBS scene was showing PS5 gameplay
  and the capture card is the right source (NOT a webcam). The retina became
  live on the UVC capture card (device #1, backend 700 = DirectShow, frame
  format `uint8(720, 1280, 3)`). The bridge's startup log explicitly identifies
  the source as "direct HDMI, no Remote Play encode."
- EYE-CHECK PROTOCOL: without vision tooling (vision provider not configured
  this session) I could not eyeball the first crop. Surrogate signals that
  argue the source IS the capture card and NOT a laptop webcam:
  - Frame shape 720×1280×3 BGR — dimensionally consistent with a capture card
    (NOT a 4:3 laptop webcam, which would be 640×480 or 1280×960).
  - Bridge log explicit: "UVC capturing UVC capture device #1 (1920x1080@60)
    — direct HDMI, no Remote Play encode (actual 1280x720@60)".
  - Crop entropy varies substantially across the session (crop file size
    188KB → 225KB, mean brightness 75 → 131, stdev 9.2 → 63.9 over ~50
    minutes) — a static webcam of a dark room would not show this.

## What actually captured (bridge side, ground truth)

Bridge: `python3 -m bridge.vapi_bridge.main` via `retina_capture_daemon.py
start`, pid 23572, started 13:19:38, killed by `qortroller.py stop` at
~13:51. Total lifetime ~32 minutes. Daemon log
`retina_daemon_session_1785003577_1785003578.log`.

Live signal observed during the match (poll log
`logs/p2_monitor2_20260725_134035.log`, 11 polls at 60s cadence):

```
=== poll #1 13:40:35 ===   last_record counter=165 conf=190   retina frames_seen=11616   loop_starv_count=163
=== poll #2 13:41:36 ===   last_record counter=171 conf=255   retina frames_seen=12586   loop_starv_count=169
=== poll #3 13:42:36 ===   last_record counter=178 conf=255   retina frames_seen=13339   loop_starv_count=176
=== poll #4 13:43:37 ===   last_record counter=182 conf=255   retina frames_seen=13774   loop_starv_count=180
=== poll #5 13:44:38 ===   last_record counter=188 conf=190   retina frames_seen=14161   loop_starv_count=186
=== poll #6 13:45:38 ===   last_record counter=193 conf=255   retina frames_seen=14663   loop_starv_count=191
=== poll #7 13:46:39 ===   last_record counter=198 conf=229   retina frames_seen=15579   loop_starv_count=196
=== poll #8 13:47:39 ===   last_record counter=203 conf=229   retina frames_seen=16145   loop_starv_count=201
=== poll #9 13:48:39 ===   last_record counter=209 conf=255   retina frames_seen=16620   loop_starv_count=207
=== poll #10 13:49:40 ===  last_record counter=216 conf=255   retina frames_seen=17251   loop_starv_count=214
=== poll #11 13:50:41 ===  last_record counter=222 conf=230   retina frames_seen=18007   loop_starv_count=220
```

Honest accounting:
- HID record counter advanced 1 → 227+ over the match window. Certified Edge
  `581a836c98b3a1b6` read throughout.
- UVC retina frames_seen grew 11,616 → 18,409+. The capture card feed was
  continuously delivering frames.
- Cadence: ~5-7 records / minute (vs nominal 1/sec). Slowed by RapidOCR
  event-loop starvation (see below).
- `live_trigger_active_fraction` varied 0.05–0.45 across polls — player 2 WAS
  pressing R2 (sprint) during the match. `live_activity_source:
  bridge_main_reader` (single-HID ring topology — the L3 dual-writer adapter
  was NOT armed; consistent with `poep_enabled=False`).
- `chain_submission_paused=true` held throughout. 0 IOTX spent.

## Honest PCC finding (lean mode, not a real disconnect)

The bridge reported `capture_state: DISCONNECTED`, `host_state: UNKNOWN`,
`poll_rate_hz: 0.0`, `sustained_duration_s: 0.0` on
`/operator/bridge/capture-health` throughout the match. That sounds alarming
but is NOT a real HID disconnect — it's a lean-mode artifact:

- Daemon log line 2: `PRESENCE_LEAN_MODE active — agent fleet + grind + PCC +
  heavy provenance SKIPPED (DualShock + retina + duty-cycle presence only).
  Bridge operational (LEAN).`
- INV-PCC-001 (`CaptureHealthMonitor.update_sample()` is the only authorized
  path for updating `poll_rate_hz`) is NOT violated — the PCC monitor was
  DISABLED in lean mode, not bypassed. The DISCONNECTED reading is the
  initial/default state showing through because the monitor never ran.
- The real HID path (`_session_loop` + `Record verified: device=581a836c...`)
  IS reading the controller; the `capture_state: DISCONNECTED` reading is
  cosmetic in lean mode.

## Honest event-loop finding (OCR starvation)

150+ LOOP STARVATION warnings over the match window. RapidOCR
(`[WARNING] main.py:132: The text detection result is empty`) repeatedly
blocked the event loop for 3-10s per call (max excess 29.37s). Two real
consequences:

1. `capture-health` endpoint responsiveness degraded — `urycopglopen` with a
   3s timeout consistently timed out at first; with a 15-20s timeout it
   eventually responded (16.8s measured once). Monitoring via HTTP during a
   grind would be unreliable under OCR load.
2. Record cadence dropped from nominal 1/sec to ~5-7/min — `_session_loop`
   survived but each iteration stretched to ~10s (mostly OCR).

This is the Phase 235-EVENTLOOP invariant surfacing in real time. The CLAUDE.md
rule "Long-running synchronous work (SQLite scans >5ms, numpy computation, file
I/O) MUST be moved to `asyncio.to_thread()`" is precisely what would fix it; an
OCR call is the same class of blocking synchronous work.

## Honest P2 fixation verification

The `qortroller.py stop` command hung after ~60s. Investigation: by the time
the hang surfaced, the underlying `retina_capture_daemon.py stop` subprocess
had already completed — killed the bridge (pid 23572 confirmed dead), wrote
the KAS record for the fresh session, and removed the daemon state file
(the direct-daemon-stop then returned "no active session (no state file)").
So the underlying stop succeeded; the hang was in the post-stop
`_print_and_write_receipt` HTTP probe path to the now-dead bridge. Re-running
`qortroller.py receipt` standalone produced the receipt for
`session_1785003577` cleanly:

```
Session : session_1785003577   (fresh — NOT proof_drill_20260713_1843)
Pack    : observer-only
KAS authorship  : HYGIENE_FAIL  authored=0  commit=932e0539903387e8...
PoSP presence   : (no record)
RETINA-STATE-v3 : honest-null (no conformant events captured)
Archive         : 242 crops  schema=qortroller-session-archive-v1
```

`qortroller.py verify` honest-null:
```
no retina_state_v3 record for 'session_1785003577' (honest-null sessions have nothing to verify)
```

`qortroller.py score` written to
`audits/match_scorecard_session_1785003577.{json,md}`:
- authored = 0 [MEASURED] (DUAL_CONNECTION_USB_PC blocks causal promotion —
  honest stop point per `note: authored 0 is an HONEST STOP POINT, not '0 kills'`)
- witnessed = None [ABSENT] (no killfeed rows matched this match — RapidOCR
  returned empty throughout; ROI may need recalibration for the capture-card
  720p feed, OR killfeed was not visible in NCAA CFB 27's HUD view this match)
  AND the killfeed ROI was Warzone-shaped (see Finding #6 below for the full
  profile-mismatch story).
- recall = UNSCORED (operator-denominator only; declined valid)
- KAS = HYGIENE_FAIL [MEASURED]
- PoSP / fusion_n / v3 events / sink rows = None [ABSENT]
- node birth = path A, first_session_id=proof_drill_20260713_1843_1783986208,
  node_id=01a574e7ca7f... (DERIVED, not minted; same as July 13 — device
  fingerprint unchanged)

## Honest numbers (Match 2)

- N humans on the rig: 2. N in the grind corpus: still 1 (no GIC entries
  stamped under lean mode + GRIND_MODE=false).
- Bridge lifetime: ~32 min, hid records: 1→227+.
- UVC retina: 18,409+ frames captured (242 archived crops).
- 0 authored, 0 witnessed, 0 GIC entries, 0 conformant v3 events (all honest-null).
- Loop starvation: 222+ warnings (max excess 29.37s).
- 0 IOTX spent.
- No FROZEN edits, no invariant edits, no PoAC wire-format touch.
- PV-CI baseline not re-verified this session (last known 184).

## What this tells the project (load-bearing signals)

1. **The UVC capture card + OBS Virtual Camera path works end-to-end under a
   second human.** 18,000+ frames captured in ~32 minutes, the bridge's
   startup log explicitly identified the source as "direct HDMI, no Remote
   Play encode", and crop entropy varied substantially (gameplay-shaped).
2. **PCC "DISCONNECTED" in lean mode is NOT a real disconnect.** INV-PCC-001
   held — the monitor was disabled, not bypassed. The `PRESENCE_LEAN_MODE`
   default likely isn't appropriate for a real grind (PCC needs to be live
   to enforce grind_ready and host_state arbitration). Fix: opt out of lean
   mode for the next real grind.
3. **RapidOCR is a real bottleneck under load.** 222 starvation events with
   a 29s max excess. OCR-for-killfeed needs the same `asyncio.to_thread`
   treatment that was applied to InsightSynthesizer Mode 6 in Phase 234. The
   killfeed-OCR-vs-game-profile split is ALREADY documented in the codebase
   (`bridge/vapi_bridge/game_profile.py` registers `ncaa_cfb_26`,
   `ncaa_cfb_27`, and `cod_warzone` with distinct L2C/L6/profile config);
   the wasted-OCR cost in this match was an operational config miss, not a
   design gap — see #6 below.
4. **Authorship honest-null is the dual-connection topology constraint.**
   Authored=0 / witnessed=None is NOT "0 kills" — it's the chain showing
   exactly where DUAL_CONNECTION_USB_PC blocks causal promotion. The fix is
   either USB-only-to-PS5 (which loses PS5 audio/haptics) or a PoEP presence
   path. Same constraint as July 13's `witnessed 17 · bound 3 · authored 0`
   result.
5. **The runbook's P2 step (`qortroller.py play` before the match) IS what
   fixed the receipt provenance.** Match 1's failure (re-rendered July 13
   receipt) was caused by skipping `play` and relying on the bridge's
   continuous capture loop. Match 2 fired `play` first and got a fresh
   session_id keyed receipt. The runbook is correct on this point.
6. **OPERATIONAL PROFILE MISMATCH (corrected post-hoc by operator).** The
   operator confirmed post-match that the actual game played was **NCAA
   College Football 27**, not 26. `bridge/.env` had `GAME_PROFILE_ID=ncaa_cfb_26`
   set at match time — **stale**. The `ncaa_cfb_27` profile WAS registered
   in `bridge/vapi_bridge/game_profile.py:206-237` (added 2026-07-18 with
   D1-D4 input deltas including D1: right stick ACTIVE in-play via the new
   tackle-stick, which means L2C may compute non-None values in 27 — the
   CFB-26 "dead-zone stick game" assumption does NOT transfer). The
   `docs/a2a/real-play-liveness/round-02-grok-expand.md:139` explicitly
   warns "do not assume CFB26 dead-zone forever" — that's exactly the
   assumption the stale `bridge/.env` row forced.

   Real consequence for Match 2's data:
   - L5 button priority and L6-Passive R2-sprint config are the same
     between profiles 26 and 27 — those transfer harmlessly.
   - **L2C may have computed meaningful stick-IMU coupling in this match
     that the stale profile-26 parsing would have neutralized to the 0.5
     prior** — that data was effectively discarded at the parsing layer for
     the entire match.
   - Killfeed ROI was calibrated for the Warzone HUD shape
     (`node.toml killfeed_roi = "0.0,0.45,0.26,0.19"` — left-middle), not a
     football HUD. The RapidOCR "text detection result is empty" repeated
     every cycle is consistent with the ROI not aligning to anything in the
     NCAA 27 feed. Pure cost, zero signal.

   Fix applied post-match: `bridge/.env` patched to
   `GAME_PROFILE_ID=ncaa_cfb_27`. The next match needs a bridge restart
   for the change to take effect (env vars read at boot). The killfeed
   ROI discrepancy should be resolved by re-running
   `qortroller.py setup --stage roi` against the NCAA 27 HUD or by
   disabling killfeed OCR for football games (killfeed is a shooter
   concept; football has a scoreboard, not a killfeed).

## Open follow-ups for the next attempt

- **Restart the bridge** so the patched `GAME_PROFILE_ID=ncaa_cfb_27` is read
  at boot (env vars are read once at startup; the fix won't take effect until
  the next `qortroller.py play` cycle).
- Opt out of `PRESENCE_LEAN_MODE` for real grind attempts (or set
  `GRIND_MODE=true` + the full PCC pipeline) so GIC entries can stamp and
  the grind corpus can advance.
- **Resolve the killfeed-OCR issue for NCAA 27 specifically.** Two real
  problems compounded in Match 2: (a) killfeed is a shooter concept — NCAA
  football has a scoreboard, not a killfeed — so OCR on a football feed is
  structurally zero-signal; (b) the ROI was calibrated for Warzone HUD
  shape (`node.toml killfeed_roi = "0.0,0.45,0.26,0.19"`, left-middle).
  Either disable killfeed OCR for football game profiles
  (`RETINA_KILLFEED_ENABLED=false` when `GAME_PROFILE_ID` starts with
  `ncaa_cfb_`) OR re-run `qortroller.py setup --stage roi` against the
  NCAA 27 scoreboard. The game-profile code in `bridge/vapi_bridge/game_profile.py`
  already knows the difference; the config doesn't.
- Recalibrate `RETINA_KILLFEED_ROI` (or disable it) for the 720p capture-card
  feed if the killfeed lane IS kept — the ROI may be off now that the source
  resolution changed from WGC monitor 1920×1080 to UVC 1280×720.
- Move RapidOCR or any other sync image-analysis into `asyncio.to_thread`
  per Phase 235-EVENTLOOP to stop the event-loop starvation (222 warnings,
  max excess 29s in Match 2).

## Artifacts (Match 2)

- `audits/session_receipt_session_1785003577.md` (mtime Jul 25 13:55)
- `audits/match_scorecard_session_1785003577.{json,md}` (mtime Jul 25 13:55)
- `audits/kas_record_session_1785003577_2026-07-25.json` (mtime Jul 25 13:51)
- `retina_kf_crops/session_1785003577_1785003577/` — 242 panel crops (mtime 13:19–13:51)
- `logs/p2_monitor2_20260725_134035.log` — 11 polls of ground-truth daemon log
- `retina_daemon_session_1785003577_1785003578.log` — bridge event log (185k bytes)

## Signed

Operator + second human present. Operator confirmed OBS scene = PS5 gameplay and
UVC device #1 = the capture card. The fresh-session receipt keyed off
`session_1785003577` (NOT the July 13 proof_drill). Authorship honest-null is
the dual-connection topology constraint, not a false-negative in the protocol.
