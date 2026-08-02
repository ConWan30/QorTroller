# Streamer perception v0 — operator runbook

Design: `docs/design/trio-retina-streamer-perception-v0.md`

## Prerequisites

- Capture card installed; OBS can see it as **Video Capture Device**
- Python with `opencv-python` (and optional `websockets` for OBS overlay)
- **Eye-check:** first frames must be the **game**, not webcam / black HDCP

## Install optional WS dep

```powershell
pip install websockets
```

## Run event producer

```powershell
cd C:\Users\Contr\vapi-pebble-prototype

# Synthetic (no card) — validates schema + JSONL
python scripts/streamer_retina_events.py --synthetic --max-frames 90 --no-ws

# Live capture card (index usually 0; try 1 if OBS/webcam conflict)
python scripts/streamer_retina_events.py --device 0 --fps 15

# WP-S1: tag source.kind (or let name sniff decide)
python scripts/streamer_retina_events.py --device 0 --device-name "OBS Virtual Camera"
python scripts/streamer_retina_events.py --device 0 --source-kind uvc_card

# Match bridge session id if set
$env:VSS_SESSION_ID = "grind_phase235_v1"
python scripts/streamer_retina_events.py --device 0
```

Events include `source.kind` ∈ `uvc_card` | `obs_virtual` | `unknown` | `synthetic`.  
Kind tags are **not** eye-check; still confirm first frames are the game.

JSONL default: `logs/streamer_perception_<ts>.jsonl`  
WebSocket default: `ws://127.0.0.1:8765`

If the card fails to open: set `RETINA_UVC_BACKEND=msmf` or `dshow`, or free the device from OBS exclusive use (OBS can share many cards; some cannot).

## OBS Browser Source

1. Start `streamer_retina_events.py` (with WS enabled).  
2. OBS → **Sources → Browser**  
3. Local file:  
   `C:/Users/Contr/vapi-pebble-prototype/tools/obs_streamer_perception_overlay.html`  
4. Width ~540, height ~220, **Shutdown source when not visible** off while testing.  
5. Optional URL query: `...overlay.html?ws=ws://127.0.0.1:8765`

Overlay shows activity, motion, FPS, zones — **advisory only**.

## Event types (v0)

`session_start` · `frame_stats` · `activity` · `zone` · `heartbeat` · `session_end`

## Non-claims

Do not say humanity-proven, tournament-grade, or cheating-proof from this layer.  
Optical events are **not** PoAC / FROZEN commitments.

## Autonomous mode (via `retina_capture_daemon.py`)

Use this when you want the streamer perception to start/stop with a rig session:

```powershell
# Start the bridge AND the streamer pipeline in one command
# --uvc-index is the bridge's HDMI capture source.
# --streamer-device should be a different UVC, e.g. the OBS Virtual Camera, to avoid conflict.
python scripts/retina_capture_daemon.py start --label grind_235 `
  --uvc-index 0 --streamer --streamer-device 1 --streamer-no-ws

# Stop both the bridge and the streamer
python scripts/retina_capture_daemon.py stop
```

The streamer JSONL/stdout are written to `logs/streamer_perception_<label>_<stamp>.jsonl/.log` and the `session_id` is bound to the daemon session. The daemon records the child pid in `retina_daemon.state.json` and kills it on `stop`.

## Compose with QorTroller truth plane (optional)

- Run bridge separately for HID / VSS eligibility.  
- Stamp `session_id` via env for later bind.  
- Do not OR-merge optical “high activity” into `poep_enabled`.
