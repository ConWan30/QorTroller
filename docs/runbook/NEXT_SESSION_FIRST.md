# NEXT SESSION — do this first

**Status:** locked 2026-08-02 after live NCAA Football 27 dogfood  
**Purpose:** so neither you nor any agent re-discovers camera indices.

Read this before starting any capture. Then run the default recipe.

---

## 0. Hardware preflight (operator hands)

1. DualShock Edge: **USB-C to laptop + Bluetooth to PS5** (dual-connection).
2. PS5 → capture card HDMI live; game running (NCAA Football preferred).
3. OBS open with the capture card as a Video Capture Device.
4. OBS → **Start Virtual Camera**.
5. Confirm you are *not* pointing anything at the house webcam on purpose.

---

## 1. Device map (THIS RIG — do not guess)

| OpenCV / daemon index | Device name (dshow) | Role |
|-----------------------|---------------------|------|
| **0** | `720p HD Camera` | **HOUSE WEBCAM — never use for grind** |
| **1** | `USB3.0 Video` (capture card path) | **Bridge** `--uvc-index 1` |
| **2** | `OBS Virtual Camera` | **Streamer** `--streamer-device 2` (backend `dshow`) |

If indices shift after a USB re-plug, re-probe with:

```powershell
ffmpeg -list_devices true -f dshow -i dummy
```

Then eye-check stills before trusting a session.

---

## 2. Default one-command start (copy/paste)

```powershell
cd C:\Users\Contr\vapi-pebble-prototype

python scripts/retina_capture_daemon.py start --label ncaa27 `
  --uvc-index 1 `
  --streamer --streamer-device 2 --streamer-fps 15
```

That command is enough. The daemon now auto-passes:

- streamer `--backend dshow`
- `--device-name "OBS Virtual Camera"`
- `--source-kind obs_virtual`
- first-frame eye-check snapshot → `logs/eye_check_streamer_<label>_<stamp>.png`
- shared `session_id` to bridge + streamer children

Shortcut (same recipe):

```powershell
.\scripts\start_ncaa27_dual_path.ps1
# or: scripts\start_ncaa27_dual_path.bat
```

---

## 3. Eye-check (mandatory before trusting the session)

1. Open `logs/eye_check_streamer_<label>_<stamp>.png`.
2. It must show **NCAA / game frames**, not desk/webcam, not black HDCP.
3. If wrong: `python scripts/retina_capture_daemon.py stop` and fix OBS / indices.

Also skim bridge log for:

- `RetinaGameCapture: UVC device #1 up`
- `DualSense Edge connected`
- `frames_seen` climbing

---

## 4. While playing

- Bridge = controller truth plane (HID / records).
- Streamer = observation plane only (activity/zone/events).
- **Never** treat streamer `activity=high` as `poep_enabled` / eligibility.
- Optional OBS Browser Source overlay:  
  `tools/obs_streamer_perception_overlay.html?ws=ws://127.0.0.1:8765`

---

## 5. Stop + harvest

```powershell
python scripts/retina_capture_daemon.py stop
```

Keep:

- bridge corpus / log named in the stop summary
- `logs/streamer_perception_<label>_<stamp>.jsonl`
- eye-check PNG(s)

---

## 6. Next engineering follow-ups (not required to play)

1. Bridge writes / touches `logs/streamer_presence.touch` on recent HID → streamer `presence_sync_ok=true`.
2. Join bridge corpus + streamer JSONL on shared `session_id` + `clock_ns` for archive/binder.
3. Optional session marker QR/text in OBS if you want visual bind.

Leave sealed: no optical → `poep_enabled` merge, no chain unpause, no FROZEN edits from this path.

---

## Non-claims

Optical streamer events are advisory. Controller remains the only cryptographic anchor.
