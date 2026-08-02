# Trio-Retina × Capture Card — Streamer Perception Layer (v0)

**Status:** DESIGN + thin WP (CANDIDATE)  
**Date:** 2026-08-01  
**Parents:** QorTroller retina capture path (`qortroller_retina_capture.py` UVC), VSS three-plane split, capture-rig eye-check  

---

## 1. One-line pitch

A standard capture-card + OBS/Twitch setup already delivers a clean game feed. This layer turns that feed (and optionally a webcam) into a **live stream of structured, advisory events** that OBS, bots, and overlays can react to—without game SDKs, console memory access, or on-chain spend.

---

## 2. Planes (do not conflate)

| Plane | Role | Examples |
|-------|------|----------|
| **Stream / social** | Entertainment automation | OBS overlays, chat bots, clip markers |
| **Observation (Retina)** | Advisory perception | Events: activity, ROI change, (later) detections |
| **Truth (QorTroller)** | Protocol / eligibility | HID, PCC, VSS seat, session_id bind |

Retina **may suggest, never assert** humanity or tournament integrity.  
Buzz/Nostr stay **digest-only** if ever wired; no frames, no full detection dumps.

---

## 3. Capture-card fit

- Capture cards enumerate as **UVC / Video Capture Device**.
- OBS opens them as **Video Capture Device**.
- OpenCV / this WP opens the **same class of device** (`RETINA_UVC_INDEX` or CLI `--device`).
- Optional: OBS **Virtual Camera** if perception should see the *composed* scene (game + facecam + overlays). Default for game analysis: **direct card** (full-res, eye-checkable).

**Eye-check (mandatory):** verify the first frames show the **game**, not a webcam or black HDCP frame, before trusting events.

---

## 4. Event schema (v0)

Wire format: one JSON object per line (JSONL) and the same object over WebSocket.

```jsonc
{
  "v": 0,
  "domain": "QORTROLLER-STREAMER-PERCEPTION-v0",
  "ts_ns": 0,
  "session_id": null,          // optional bind to QorTroller session
  "source": {
    "device": 0,               // UVC index or "obs-virtual"
    "backend": "msmf|dshow|auto",
    "width": 1280,
    "height": 720,
    "fps_target": 30
  },
  "type": "session_start | frame_stats | activity | zone | heartbeat | session_end",
  "payload": { }
}
```

### Event types (v0 — no YOLO required)

| type | Meaning | payload (principal fields) |
|------|---------|----------------------------|
| `session_start` | Observer started | `out_path`, `ws_port` |
| `frame_stats` | Periodic rate/quality | `n`, `fps_meas`, `mean_luma`, `motion` |
| `activity` | Scene activity crossed threshold | `level`: `idle`\|`low`\|`high`, `motion` |
| `zone` | Named ROI changed vs baseline | `zone_id`, `delta`, `state`: `quiet`\|`active` |
| `heartbeat` | Liveness for OBS clients | `uptime_s` |
| `session_end` | Observer stopped | `frames`, `events`, `elapsed_s` |

### Later (not v0)

- Detector boxes / tracks (YOLO, open-vocab, game-tuned)  
- Killfeed / scoreboard OCR (existing retina lanes can attach later)  
- Webcam second pipeline (gestures)  
- Forecast / dynamics  

---

## 5. Technical flow (v0 WP)

```text
Capture card (UVC)
    → OpenCV VideoCapture
    → lightweight metrics (luma, frame-diff motion, ROI delta)
    → EventBus
         ├─ JSONL append (logs/streamer_perception_*.jsonl)
         └─ local WebSocket server (default ws://127.0.0.1:8765)
              → OBS Browser Source (tools/obs_streamer_perception_overlay.html)
              → custom bots / scripts
```

Optional: if bridge is up, stamp `session_id` from env `VSS_SESSION_ID` / `GRIND_SESSION_ID` only—**never invent**.

---

## 6. Non-claims (never-sayable from this layer alone)

- “Humanity proven” / “tournament-grade stream”  
- “Cheating impossible”  
- Optical events as PoAC / FROZEN commitments  
- Population FRR / separation claims  
- That OBS Virtual Cam equals game-native pixels without eye-check  

Allowed (G0-style): “process observed high motion on capture device N,” “zone hud_scoreboard became active.”

---

## 7. Performance budget (guidance)

| Knob | v0 default | Note |
|------|------------|------|
| Resolution | 1280×720 process scale | Full grab optional; process downscale |
| Target FPS | 15–30 | Skip frames under load |
| Detector | none | Motion/ROI only |
| GPU | not required | Leave NVENC for OBS |

---

## 8. Code map

| Path | Role |
|------|------|
| `docs/design/trio-retina-streamer-perception-v0.md` | This scope |
| `bridge/vapi_bridge/streamer_perception.py` | Schema, metrics, bus |
| `scripts/streamer_retina_events.py` | CLI runner |
| `tools/obs_streamer_perception_overlay.html` | OBS Browser Source consumer |
| `docs/runbook/streamer-retina-perception-v0.md` | Operator steps |
| `bridge/tests/test_streamer_perception.py` | Unit tests (no card required) |

---

## 9. Acceptance (v0)

1. With a synthetic or real UVC source, runner emits `session_start` + `heartbeat` + `session_end`.  
2. Motion above threshold produces `activity` transitions (not spam every frame).  
3. JSONL file grows; WebSocket client receives the same events.  
4. OBS Browser Source page updates text from WebSocket (manual OBS config).  
5. PV-CI / FROZEN wire untouched; zero chain spend.

---

## 10. Follow-ons

- Attach killfeed / Visual Oracle as optional event producers  
- VSS seat bind: only OPEN while `activity=high` + eligibility (compose)  
- Trio-Lumen match spans from `activity` / future `match_state`  
- Game-tuned detectors under separate WP with model license discipline  

---

**End of streamer perception scope v0**
