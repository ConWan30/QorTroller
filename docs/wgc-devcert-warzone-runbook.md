# Dev-Cert + WGC Live-Validation + Latency Calibration Runbook (Warzone / PS Remote Play)

Operator runbook for the tests that require **playing Warzone** — validating the WGC capture enhancements
(commit `3f1854e6`) on real frames, and capturing the cross-channel latency-invariant calibration corpus.
Advisory presence layer only; no FROZEN-v1 / 228B PoAC / chain / IOTX. Keep `CHAIN_SUBMISSION_PAUSED=true`.

## Setup (both parts)

- DualShock Edge: **USB-C → laptop** (HID/R2 + right-stick source) **AND** BT-paired → PS5 (to play). Dual-connection.
- Warzone running on PS5, streamed to the laptop via **PS Remote Play, FULLSCREEN** on the laptop display.
- The capture window is `"Remote Play"` (the default) or use the monitor index of the laptop display.

---

## Part A — WGC enhancement live validation (standalone probe, ~30s)

Validates #1 (presentation timestamps) + #2 (ROI-crop convert) on real WGC frames. No bridge needed.

```
python scripts/validate_wgc_standalone_fps.py --monitor 1 --seconds 30
```
(While it runs, play / move the screen so frames flow. `--monitor 1` = laptop display; use `--monitor 0 --window "Remote Play"` to target the window.)

**Acceptance criteria:**
1. On the first frame, the log prints **`WGC presentation timestamp ACTIVE — raw timespan=… -> … ms; epoch offset=…`**.
   - **Verify the units**: the printed ms should be a sane wall-time-scale number and subsequent samples should
     advance ~per-frame. If the ms looks absurd (e.g. 1000× off), the `_TIMESPAN_TICKS_PER_MS = 10_000` constant
     in `qortroller_retina_capture.py` is wrong for this `windows_capture` build — that's the one-constant fix.
2. Each line shows **`ts_source=timespan`** (not `wall_fallback`) and a stable `ts_offset_ms`.
3. `frames_seen` advances; `~fps` is DELIVERY-BOUND (≥30 SDR, lower under HDR). `fmt=` shows the WGC buffer
   format (e.g. `uint8(...,4)` SDR or a wider HDR dtype) — confirms the ROI-crop convert handled it without errors.
4. No `frame processing error` spam (the ROI-crop convert is HDR-safe).

If `ts_source=wall_fallback` persists, the lib isn't surfacing `frame.timespan` on this build → #1 falls back
safely (no harm), but the jitter win is unavailable; report it.

---

## Part B — Dev-cert + latency calibration capture (bridge + play)

### B.1 Configure `bridge/.env` (machine-local; not committed)
```
RETINA_GAME_CAPTURE_ENABLED=true
RETINA_GAME_CAPTURE_WINDOW=Remote Play
RETINA_BURST_COMBAT_TRIGGER_ENABLED=true     # auto-fire a burst when you start shooting (R2)
DEVELOPER_SELF_CERT_ENABLED=true             # dev-cert presence verdict (cert_scope=developer_self)
PRESENCE_LEAN_MODE=true                       # gate the ~30-agent fleet/grind -> less CPU/observer-effect
NQPV_COCAPTURE_ENABLED=true                   # REQUIRED with lean mode, else coupling resolves to None
GRIND_MODE=false
CHAIN_SUBMISSION_PAUSED=true                  # keep the kill-switch on — calibration writes nothing on-chain
```

### B.2 Launch the bridge, capturing its log
The cross-channel lags are emitted as `RGC diag:` lines in the bridge log.
- PowerShell: `python -m bridge.vapi_bridge.main *>&1 | Tee-Object bridge_warzone.log`
- bash:       `python -m bridge.vapi_bridge.main > bridge_warzone.log 2>&1`

Confirm startup, then check capture is live (separate shell):
`curl -s localhost:8000/bridge/capture-health` → `poll_rate_hz ≈ 1000`, `host_state=EXCLUSIVE_USB`.

### B.3 Capture GENUINE sessions (you playing)
Play normally — get into **real gunfights** (the combat-trigger fires bursts; B1 flash + B2 kill-marker +
geometric pan all couple to YOUR input). Aim for several minutes of active combat. The bridge logs
`RGC diag:` (per-tune) + `trigger-hud burst:` (per burst).

### B.4 Capture FORGED negatives (the FAR side)
**Spectate** a teammate's POV during active combat and **fire along** (this is the attack the latency
invariant must reject — your trigger isn't driving that screen). A few minutes, logged the same way.
Use a separate log file (e.g. `spectate_warzone.log`).

### B.5 Harvest + calibrate
```
python scripts/capture_latency_calibration.py --log bridge_warzone.log   --out genuine.jsonl
python scripts/capture_latency_calibration.py --log spectate_warzone.log --out forged.jsonl
python scripts/capture_latency_calibration.py --calibrate --genuine genuine.jsonl --forged forged.jsonl
```

**Acceptance / reading the verdict** (`l9_presence/cross_channel_latency.calibrate_tau_lag`):
- `INSUFFICIENT_DATA` → fewer than **10 sessions/class**; play/spectate more (target ≥30/class for `CALIBRATED`).
- `CALIBRATED` / `CALIBRATED_PROVISIONAL` with `far == 0` and a low `frr` → the invariant separates genuine
  (shared clock) from spectate (scattered lags) — a real, measured FAR-safe `tau_lag_ms`. This is the result
  that promotes the product thesis from `likely` to certified.
- `NO_SAFE_THRESHOLD` → genuine and spectate overlap at this regime; capture more, or the 2-channel weak spot
  is biting (ensure gunfights produce all 3 channels — B1 flash + B2 kill + geometric pan).

Dev-cert verdict during play: watch the bridge log for `developer-self-cert LIVE` (the signaling agent fires
on a PRESENT verdict). `python scripts/record_devcert_session.py --interval 20 --out devcert.jsonl` samples it.

---

## Honest notes
- The WGC `timespan` units (`/1e4`) are assumed until Part A confirms them on a live frame.
- B2 needs real **kills/downs** (red marker) to couple — a no-kill fight gives B1+geometric only (still 2
  channels; B2 adds the strongest channel when you score).
- Observer effect: capturing during a gunfight slightly lags the stream; the ROI-crop convert reduced this
  (+55% on HDR), but the lag-free production answer remains the off-device HDMI sidecar (future work).
- Everything here is advisory/default-off and writes only local files (`*.jsonl`, the bridge log).
