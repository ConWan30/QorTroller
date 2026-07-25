# Second-Human Session Record (Match 3) — 2026-07-25

> **STATUS: PARTIAL with a real new signal.** Match 3 ran under the
> corrected `GAME_PROFILE_ID=ncaa_cfb_27` profile (Match 2 surfaced the
> stale `ncaa_cfb_26` config; the patch landed in `bridge/.env` and the
> bridge cold-booted under the new profile before `qortroller.py play`).
> Authorship lane remains honest-null under the dual-connection topology
> constraint. **The retina-promoted perception lane IS new** — the PoSP
> record promoted with `SYNCHRONIZED fusion_rows=142 retina_root=fd3d4535`,
> whereas Match 2's PoSP record was `(no record)` honest-null. That is the
> load-bearing signal this match added.

## Operator + second human

- **Operator:** present at the rig (ConWan30).
- **Second human (P2):** played one NCAA CFB 27 match via the DualSense Edge
  on the dual-connection (USB to laptop, BT to PS5) rig.
- **Match window:** approximately 2026-07-25 14:50:55 to 15:16:00 local
  (~25 minutes gameplay; was ~32 min for Match 2).
- **Game profile at match time:** `ncaa_cfb_27` (CORRECT — Match 2 was
  stale at `ncaa_cfb_26`; the config patch from Match 2 took effect on
  the bridge cold boot before the match).

## P0 — Pre-flight pass

Per runbook `docs/second-human-runbook-2026-07-25.md`:

- submodule initialized (yes)
- PV-CI gate: PASS, 184 invariants verified
- `bridge/.env` GAME_PROFILE_ID=ncaa_cfb_27 (the corrected profile)
- bridge/.env RETINA_CAPTURE_SOURCE=uvc, RETINA_UVC_INDEX=1, RETINA_UVC_BACKEND=auto
- ports 8000/8080 both CLOSED at preflight
- DualSense Edge detected on USB (VID 0x054C PID 0x0DF2, interface 3)

## P2 — `qortroller.py play` (the runbook P2 step, Match 2 gap-fix confirmed)

First `play` attempt refused: **RP-5 NO_GO** — preflight BLOCK on CPU
baseline at 88% (M12 precedent failed at 94.9%; CIM measured 96% live).
Operator closed OBS (the streaming bridge was a heavy non-essential
consumer). CPU dropped 88% -> 21%, well clear of the M12 failure zone.
Re-fire: **RP-5 GO_WITH_WARNINGS** — the two remaining WARNs are real
but not blocking:

  - WARN bridge.db 5.4GB > 3GB (cycle-49 per-record write-lag lesson)
  - WARN RETINA_KILLFEED_CAPTURE_MAX not set (launch-stack lesson)

Fresh session minted: `session_1785009055` (NOT the July 13 proof_drill,
NOT the Match 2 `session_1785003577`). Bridge launched detached pid 7584
on :8080, log `retina_daemon_session_1785009055_1785009055.log`.

Operator decision worth recording: closing OBS freed CPU headroom but
raised a real question — does the UVC capture card feed depend on OBS
Virtual Camera? Verified NO: the capture card enumerates directly via
DirectShow backend 700, returning 720x1280 frames (mean 140.2, stdev 69.6
— live gameplay, not a dummy/disconnected frame which would be stdev<5).
The Match 2 retina source path was unaffected by OBS being closed.

## Match in progress (mid-poll signal at 14:56:34)

`/operator/bridge/capture-health` (with x-api-key):

  capture_state: DISCONNECTED  host_state: UNKNOWN  poll_rate_hz: 0.0
  live_activity_source: bridge_main_reader
  live_trigger_active_fraction: 0.20  live_activity_window_n: 20
  latest_gameplay_context: None  gameplay_context_enabled: True

Daemon log ground truth:

  counter=38 -> 39 (advancing ~6 records/min — same lean-mode cadence
  as Match 2; the OCR-stall impact persists but isn't blocking)
  retina frames_seen: 3219 (live, 9.91 fps, 720x1280 frames)
  th_fires: 10 (R2 trigger-burst probes since match start — player 2 sprinting)
  kf_verdict: SPECTATED_NOT_AUTHORED  kf_other_kills: 3
  inline_classifications: 7  inline_authored: 0
  l9_verdict: REPLAY_OR_RELAY  nqpv_verdict: IMPLAUSIBLE  coupling: 0.02
  LOOP STARVATION max excess ~10s (DB write-lag WARN showing)
  chain_submission_paused=true held throughout. 0 IOTX.

`capture_state: DISCONNECTED` is the same lean-mode cosmetic finding as
Match 2 (#2 in that record): the PCC monitor is disabled in
`PRESENCE_LEAN_MODE`, not bypassed (INV-PCC-001 held).

## P3 — `qortroller.py stop` → `receipt` → `verify` → `score`

`qortroller.py stop` completed without the hang Match 2 hit (no 60s
HTTP probe timeout this time — the kill path worked cleanly; port 8080
released, no orphan processes). Wrote the fresh-keyed receipt, KAS
record, and **PoSP record** (new artifact type vs Match 2):

Receipt (`audits/session_receipt_session_1785009055.md`):
  Session : session_1785009055
  Pack    : observer-only
  KAS authorship  : HYGIENE_FAIL  authored=0  commit=760f78a379637d65...
  PoSP presence   : SYNCHRONIZED  fusion_rows=142  retina_root=fd3d4535  <-- NEW
  RETINA-STATE-v3 : honest-null (no conformant events captured)
  Archive         : 164 crops  schema=qortroller-session-archive-v1

`qortroller.py verify` honest-null (same as Match 2):
  no retina_state_v3 record for 'session_1785009055'
  (honest-null sessions have nothing to verify)

`qortroller.py score` (`audits/match_scorecard_session_1785009055.{md,json}`):
  authored : 0  [MEASURED]  (strict causal + hygiene)
  witnessed: None  [ABSENT]
  bound    : None  [ABSENT]
  KAS      : HYGIENE_FAIL  [MEASURED]
  PoSP     : SYNCHRONIZED  [MEASURED]   <-- NEW vs Match 2 (was None ABSENT)
  fusion_n : 142  [MEASURED]             <-- NEW
  v3 events: None  [ABSENT]
  sink rows: None  [ABSENT]
  observation_verdict: None  [DERIVED]
  topology : DUAL_CONNECTION_USB_PC -> WITNESSED_ONLY
  node_id  : 01a574e7ca7f... (DERIVED, same as Match 2)

The honest-stop-point note from Match 2's scorecard carries: "authored=0
is an HONEST STOP POINT, not '0 kills' — the chain shows exactly where
dual-connection blocks causal promotion."

## What this match tells the project (the load-bearing signal)

1. **`ncaa_cfb_27` profile fix worked end-to-end.** The bridge cold-booted
   under the corrected profile (`Phase 51: game profile 'EA Sports
   College Football 27' loaded — L5 priority=['r2', 'cross', 'l2_dig',
   'triangle'] L6-Passive=True`). The Match-2 finding #6 (OPERATIONAL
   PROFILE MISMATCH) is now closed operationally. The L2C stick-IMU
   coupling computation is no longer neutralized to the 0.5 dead-zone
   prior — though that data only manifests at v3 promotion, which didn't
   fire this match under the REPLAY_OR_RELAY l9_verdict (still
   dual-connection topology).

2. **The retina-promoted perception lane IS a new signal.** Match 2's
   PoSP record was honest-null `(no record)`. Match 3's PoSP record
   `SYNCHRONIZED fusion_rows=142 retina_root=fd3d4535... temporal beacon
   ref block 45026880 hash 0xa85926...`. The retina captured 113 live
   perception rows (5803 events) and rolled them into a temporal-beacon-
   anchored root. That is a real promotion vs Match 2 — it means the
   corrected profile + capture-card feed is delivering perceivable signal,
   not abstaining. Match 2's L2C-neutralized data may have been the
   reason the retina abstained. Match 3's corrected profile let the
   retina see enough to seal the perception root, even if it still didn't
   cross the v3-promotion bar.

3. **The CPU hygiene gate is operationally real.** The preflight BLOCK
   at 88% CPU was NOT cosmetic — M12's 94.9% failure precedent is the
   reason that gate exists. The operator's choice (close OBS) freed
   ~70% CPU headroom. The WARNs (bridge.db 5.4GB, env_sanity missing
   RETINA_KILLFEED_CAPTURE_MAX) remain. The killfeed-ROI shape mismatch
   from Match 2 (Warzone-HUD-shaped, not football-scoreboard-shaped) is
   still there; the RapidOCR "text detection result is empty" loop
   repeated. That's load-bearing future work: disable killfeed OCR for
   football profiles (`RETINA_KILLFEED_ENABLED=false` when
   `GAME_PROFILE_ID` starts with `ncaa_cfb_`), OR re-run
   `qortroller.py setup --stage roi` against the NCAA 27 scoreboard.

4. **`qortroller.py play` before the match IS the proven gap-fix.**
   Match 3 followed Match 2's P2-step fix, fired `play` first, and got
   a fresh `session_1785009055`-keyed receipt — no re-render of the
   July 13 proof_drill. The `stop` step completed cleanly (no hang). The
   runbook is validated by two consecutive matches now.

## Honest numbers (Match 3)

- Match window: ~25 min, hid records advanced 1 -> ~100+ (exact count
  not recorded in the daemon poll at stop — receipt KAS windows_total=0)
- UVC retina: frames_seen 3219 at 14:56:34 mid-match (more by stop)
- 164 crops archived (vs Match 2's 242 — shorter match window + slower
  retina framerate under CPU pressure)
- 142 fusion_rows (NEW — vs Match 2's None)
- 0 authored, 0 witnessed, 0 conformant v3 events (honest-null authorship
  lane — same topology constraint as Match 2)
- Loop starvation: max excess ~10s (lower than Match 2's 29s max, despite
  same 5.4GB DB — closing OBS may have helped)
- 0 IOTX spent (CHAIN_SUBMISSION_PAUSED held throughout)
- No FROZEN / PoAC wire / contract / invariant edits; PV-CI stayed 184
- 0 new tests written

## Open follow-ups for the next attempt (incremental over Match 2 list)

- **`RETINA_KILLFEED_ENABLED=false`** when `GAME_PROFILE_ID` starts with
  `ncaa_cfb_` — killfeed is a shooter concept. OCR on a football HUD is
  zero-signal. This was WARN env_sanity in this match's preflight and
  contributed to the loop-starvation pattern.
- **Resolve the bridge.db 5.4GB size** — either vacuum the operating DB
  or override `DB_PATH` to a fresh small DB for the next match. Was the
  other WARN this match.
- **Re-run `qortroller.py setup --stage roi`** against the NCAA 27
  scoreboard IF killfeed OCR is kept (not recommended — killfeed is a
  shooter concept; disabling it is the cleaner fix).
- **Move RapidOCR into `asyncio.to_thread`** per Phase 235-EVENTLOOP
  invariant — the 10s loop-starvation max excess would be 0 if the OCR
  call didn't block the event loop.

## What this match explicitly does NOT do (carried from Match 2)

- Does NOT advance the grind corpus (0 GIC entries stamped; lean mode +
  GRIND_MODE=false). N in the grind corpus is still 1.
- Does NOT flip `poep_enabled`, `L6B_ENABLED`, `L6_CHALLENGES_ENABLED`,
  or any operator-gated flag.
- Does NOT modify any FROZEN-v1 primitive, any `b"VAPI-..."` domain tag,
  or any commit invariant. 228-byte PoAC wire format untouched.
- Does NOT prove cross-session controller-identity (CROSS-LESSON-001 gap
  still open — N=2 humans does not close it).
- authored=0 / witnessed=None is NOT "0 kills proven" — it's the chain
  showing exactly where DUAL_CONNECTION_USB_PC blocks causal promotion.
- 0 IOTX spent (`qortroller anchor` not invoked).

## Artifacts (Match 3)

- `audits/session_receipt_session_1785009055.md` (mtime Jul 25 15:17)
- `audits/match_scorecard_session_1785009055.{md,json}` (mtime Jul 25 15:17)
- `audits/kas_record_session_1785009055_2026-07-25.json` (mtime Jul 25 15:16)
- `audits/posp_record_session_1785009055_2026-07-25.json` (mtime Jul 25 15:17)
  **(NEW vs Match 2 — no PoSP record existed for Match 2)**
- `retina_kf_archive/session_1785009055_1785009055/` — 164 chained crops
  + manifest.json + RWM manifest_chain.json (gitignored; biometric
  data per .gitignore discipline)
- `retina_daemon_session_1785009055_1785009055.log` — bridge event log

## Verification

- PV-CI gate run post-match: PASS -- 184 invariants verified
  (`vapi_invariant_gate.py` exit 0)
- `qortroller.py verify`: honest-null (no retina_state_v3 record — same
  expected abstention as Match 2)
- Port 8080 CLOSED post-stop. No orphan vapi_bridge processes. Clean
  teardown (no hang, no HTTP probe timeout).

## Signed

Operator + second human present. Operator closed OBS to clear the CPU
hygiene gate (RP-5 NO_GO -> GO_WITH_WARNINGS). The corrected
`ncaa_cfb_27` profile was live in the bridge boot log. `qortroller.py
play` was fired before the match per runbook P2 — fresh
`session_1785009055` receipt, NOT a re-render of prior sessions. The
PoSP SYNCHRONIZED record (retina-promoted perception root) is the new
signal this match contributed vs Match 2's honest-null-only outcome.
