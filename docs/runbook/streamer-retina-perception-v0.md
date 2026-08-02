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

# Match bridge session id if set
$env:VSS_SESSION_ID = "grind_phase235_v1"
python scripts/streamer_retina_events.py --device 0
```

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

## Compose with QorTroller truth plane (optional)

- Run bridge separately for HID / VSS eligibility.  
- Stamp `session_id` via env for later bind.  
- Do not OR-merge optical “high activity” into `poep_enabled`.
