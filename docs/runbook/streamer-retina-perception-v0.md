# Streamer perception v0 — operator runbook

Design: `docs/design/trio-retina-streamer-perception-v0.md`  
**Next session first-step:** `docs/runbook/NEXT_SESSION_FIRST.md` ← start there.

## Prerequisites

- Capture card installed; OBS can see it as **Video Capture Device**
- OBS **Virtual Camera** started
- DualShock Edge dual-connection (USB-C laptop + BT PS5)
- Python with `opencv-python` (and optional `websockets` for OBS overlay)
- **Eye-check:** first frames must be the **game**, not webcam / black HDCP

## THIS RIG — locked device map (2026-08-02)

| Index | Name | Use |
|------:|------|-----|
| 0 | `720p HD Camera` | House webcam — **never** for grind |
| 1 | capture card path (`USB3.0 Video`) | Bridge `--uvc-index 1` |
| 2 | `OBS Virtual Camera` | Streamer `--streamer-device 2` + backend `dshow` |

Re-probe if USB topology changes:

```powershell
ffmpeg -list_devices true -f dshow -i dummy
```

## Default dual-path start (preferred)

```powershell
cd C:\Users\Contr\vapi-pebble-prototype

# One-shot shortcut
.\scripts\start_ncaa27_dual_path.ps1

# Equivalent explicit daemon command
python scripts/retina_capture_daemon.py start --label ncaa27 `
  --uvc-index 1 `
  --streamer --streamer-device 2 --streamer-fps 15
```

Daemon auto-passes streamer flags proven on this rig:

- `--backend dshow`
- `--device-name "OBS Virtual Camera"`
- `--source-kind obs_virtual`
- eye-check snapshot under `logs/eye_check_streamer_<label>_<stamp>.png`
- shared `session_id` on bridge + streamer

Stop:

```powershell
python scripts/retina_capture_daemon.py stop
```

## Install optional WS dep

```powershell
pip install websockets
```

## Manual streamer-only (debug)

```powershell
cd C:\Users\Contr\vapi-pebble-prototype

# Synthetic (no card) — validates schema + JSONL
python scripts/streamer_retina_events.py --synthetic --max-frames 90 --no-ws

# Live OBS Virtual Camera (this rig)
python scripts/streamer_retina_events.py `
  --device 2 --backend dshow `
  --device-name "OBS Virtual Camera" --source-kind obs_virtual `
  --fps 15 --snapshot logs/eye_check_manual.png

# WP-S2 dual open inside the streamer process itself
python scripts/streamer_retina_events.py `
  --device 1 --device-name "USB3.0 Video" --source-kind uvc_card `
  --secondary-device 2 --secondary-device-name "OBS Virtual Camera" `
  --secondary-source-kind obs_virtual --fps 15

# WP-S3 text / QR session marker
$env:RETINA_SESSION_MARKER = "text"
python scripts/streamer_retina_events.py --device 2 --backend dshow --session-id grind_235_v1
# QR needs: pip install "qrcode[pil]"
python scripts/streamer_retina_events.py --device 2 --backend dshow --session-id grind_235_v1 --session-marker qr

# WP-S5 presence-sync (touch-file updated by bridge/tool on recent controller input)
$env:RETINA_PRESENCE_TOUCH_FILE = "C:/Users/Contr/vapi-pebble-prototype/logs/streamer_presence.touch"
python scripts/streamer_retina_events.py --device 2 --backend dshow --presence-touch-file $env:RETINA_PRESENCE_TOUCH_FILE
```

Events include `source.kind` ∈ `uvc_card` | `obs_virtual` | `unknown` | `synthetic`.  
Kind tags are **not** eye-check; still confirm first frames are the game.

JSONL default: `logs/streamer_perception_<ts>.jsonl`  
WebSocket default: `ws://127.0.0.1:8765`

If open fails: try `RETINA_UVC_BACKEND=msmf` / `dshow`, free exclusive holders, or re-check indices.

## OBS Browser Source

1. Start daemon/streamer (WS enabled).  
2. OBS → **Sources → Browser**  
3. Local file:  
   `C:/Users/Contr/vapi-pebble-prototype/tools/obs_streamer_perception_overlay.html`  
4. Width ~540, height ~280, **Shutdown source when not visible** off while testing.  
5. Optional URL query: `...overlay.html?ws=ws://127.0.0.1:8765`

Overlay shows activity, motion, FPS, zones, presence, session marker — **advisory only**.

## Event types (v0)

`session_start` · `frame_stats` · `activity` · `zone` · `session_marker` · `source_secondary_failed` · `heartbeat` · `session_end`

Every event carries `clock_ns` (monotonic) and `session_head_ns`.  
`activity` / `zone` / `frame_stats` carry `presence_sync_ok` (false unless recent controller input via touch-file).

## Non-claims

Do not say humanity-proven, tournament-grade, or cheating-proof from this layer.  
Optical events are **not** PoAC / FROZEN commitments.  
Do **not** OR-merge optical “high activity” into `poep_enabled`.

## Compose with QorTroller truth plane

- Bridge = HID / controller truth.
- Streamer = observation plane, same `session_id`.
- Join later on `session_id` + `clock_ns` / `session_head_ns`.
