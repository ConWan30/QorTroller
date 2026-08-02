# Trio-Retina × OBS — Dual-path live sync (v0)

**Status:** DESIGN (CANDIDATE) — **WP-S1 through WP-S6 implemented** (source.kind tagging, dual open, session marker, shared clock, presence-sync activity, non-merge tests)
**Date:** 2026-08-02  
**Parents:**  
- `docs/design/trio-retina-streamer-perception-v0.md` (thin UVC → events → OBS)  
- Dual-lobe research path (`retina_controller_embedder`, `retina_screen_lobe`, `retina_causal_coherence`, `screen_retina_fusion`)  
- Three-plane split (Truth / Observation / Stream-social)  
- Capture-rig eye-check + F-MATCH-2 source-gate discipline  

---

## 1. North star

**Trio-Retina’s true purpose in QorTroller is the model-agnostic observation-plane encoder.**  
It turns heterogeneous inputs (HID controller stream + video/screen) into a single standardized, queryable `WorldState` (symbolic events + optional latent vectors). It **never** asserts humanity, eligibility, or tournament integrity; that remains the exclusive job of the **Truth plane** (PoAC / PITL / FROZEN primitives). Retina only supplies **advisory perception** that can be *causally bound* to the attested controller stream.

Streamer perception v0 is a **thin slice** of that purpose (optical events for OBS). This doc is the **sync ladder**: tight, plane-respecting temporal and source synchronization for live play + OBS-as-UVC — without collapsing observation into truth.

---

## 2. How Retina is currently initialized

### 2.1 Streamer / UVC perception path (v0, thin working prototype)

| Item | Detail |
|------|--------|
| Entry | `scripts/streamer_retina_events.py` |
| Runtime | `PerceptionConfig` + `StreamerPerceptionRuntime` (`bridge/vapi_bridge/streamer_perception.py`) |
| Device | `--device N` or `RETINA_UVC_INDEX` (default 0); backend `auto` / `msmf` / `dshow` |
| Open | OpenCV `VideoCapture` — physical capture card **or** OBS Virtual Camera if enumerated as UVC |
| Session stamp | Optional `session_id` from `VSS_SESSION_ID` / `GRIND_SESSION_ID` / `STREAMER_SESSION_ID` (or `.env`) on every event |
| Events (detector-free) | `session_start`, `frame_stats`, `activity`, `zone`, `heartbeat`, `session_end` |
| Sinks | JSONL + WebSocket (default `ws://127.0.0.1:8765`) for OBS Browser Source |
| Non-claims | Optical events are never PoAC / FROZEN commitments |
| Eye-check | First frames must be **game**, not webcam or black HDCP |

### 2.2 Dual-lobe / causal core path (research, default-OFF)

| Lobe | Role |
|------|------|
| Controller | `retina_controller_embedder.py` — 1 kHz HID → standardized events (`controller.trigger.onset`, sticks, tremor, …) |
| Screen | `retina_screen_lobe.py` + capture — OCR (later YOLO/VLM) → `scene.*`; WGC/DXGI/mss **or** UVC |
| Fusion | `retina_causal_coherence.py` + `screen_retina_fusion.py` — bind screen outcomes to *preceding* controller events by timestamp + causality; verdicts stay `UNCALIBRATED` / advisory |
| State | `retina_state_commitment.py` (v1/v2/v3 tags, Poseidon events_root, DA-witness, optional W3bstream/PDA) — observation-plane only; **never** grows the 228-byte PoAC wire |
| Enable | Flag-driven (`RETINA_GAME_CAPTURE_ENABLED`, `RETINA_PERCEPTION_ENABLED`, daemon env); optional `retina_capture_daemon.py` long-lived process |

### 2.3 Sync today (intentionally loose)

- Optional `session_id` stamping  
- Wall-clock / event-order causality after the fact  
- No shared high-resolution timeline between OBS composition and Retina  
- No automatic awareness of whether UVC is “clean game” vs “OBS-composed scene”  

---

## 3. Novelty: plane-respecting dual-path live sync

High leverage: the **same physical play session** produces three cleanly separated but causally linked views:

| Plane | Source of truth | What Retina should see | Sync mechanism |
|-------|-----------------|------------------------|----------------|
| **Truth** | Certified controller (PoAC / HID) | N/A for optical assert; controller lobe observes only | Existing ~1 kHz chain |
| **Observation (Retina)** | Clean game pixels + optional composed scene | Dual UVC paths | Shared monotonic clock + session bind |
| **Stream / social** | OBS composition | What the audience sees | OBS Virtual Cam + WebSocket / Browser Source |

Controller lobe remains the **exclusive cryptographic anchor**. Screen lobe (clean UVC or OBS Virtual Cam) only ever produces observation-plane `WorldState` that can be causally explained by that anchor.

---

## 4. Concrete enhancement steps (architecture-compatible)

### 4.1 Dual-source UVC initialization

1. **Primary:** direct capture-card index — full-res, eye-checkable, highest causal fidelity for OCR / future detectors.  
2. **Secondary (optional):** OBS Virtual Camera index — Retina can emit “what the stream actually showed.”  
3. **Tagging:** auto-detect device name containing `OBS Virtual Camera` / `obs-virtualcam` (and similar) and set every event’s `source` field accordingly (`card` | `obs_virtual` | raw index).  
4. **Eye-check:** mandatory **per source** (F-MATCH-2 style source gate). Black HDCP / wrong eye → refuse that path, do not invent frames.

### 4.2 Shared timeline + session side-channel

1. Inject a **high-resolution monotonic timestamp** (or QorTroller session clock head) into both the HID/PoAC-adjacent path and the Retina frame path.  
2. Prefer a small **OBS Browser Source or text source** that encodes:
   - current `session_id`
   - short commitment root (or digest prefix)
   - optional lightweight QR-style marker  

   so Retina can OCR/verify it is looking at the **correct live session**.  

3. This is the **internal analogue of QRTuber-style side-channel sync**, but:
   - advisory only  
   - local only  
   - never a Truth-plane proof by itself  

### 4.3 Causal bind at event rate

1. Keep dual-lobe fusion (`retina_causal_coherence` + `screen_retina_fusion`).  
2. Add a real-time **presence-synchronized activity** channel:  
   - emit high-confidence `activity` / zone / scene events **only while** the controller lobe reports recent certified input  
   - gives OBS overlays and bots a clean signal: *human is actively playing and the screen is coherent*  
   - **without** claiming the Truth plane  
3. Machine field discipline: e.g. `presence_sync_ok: true/false` on observation events — never OR-merged into `poep_enabled`, VSS eligibility, or FROZEN gates.

### 4.4 OBS integration points (already fit)

| Surface | Use |
|---------|-----|
| WebSocket fan-out | Keep Browser Source overlay for live advisory state |
| Event bus (optional) | Drive OBS scene switches, text sources, chapter markers — still advisory |
| Forbidden | Optical events OR-merge into `poep_enabled` / FROZEN eligibility |

### 4.5 Operational posture

- Default remains **OFF / research** for dual-lobe and dual-source  
- Eye-check + source-gate stay **mandatory**  
- Performance budget **conservative**: downscaled process resolution, **15–30 fps** target, no GPU required for v0 metrics path so OBS NVENC is not starved  

---

## 5. What this is not

| Non-goal | Why |
|----------|-----|
| Humanity proof from optics | Truth plane only |
| Tournament eligibility from activity | VSS / PoAC / gates stay independent |
| Replacing HID as anchor | Controller remains exclusive cryptographic anchor |
| On-chain spend / new FROZEN family | Out of scope for this sync WP |
| Auto-minting OBS as “clean game” | Virtual Cam is composed; tag + eye-check |

---

## 6. Relationship to streamer perception v0 dogfood

| | Streamer v0 dogfood | This sync design |
|--|---------------------|------------------|
| Scope | Single UVC → events → JSONL/WS → OBS | Dual UVC + shared clock + session marker + presence-sync activity |
| Status | Shipped prototype | Design candidate |
| Proves | Optical advisory path works | Live dual-path, presence-aware loop |

Dogfooding streamer v0 does **not** complete this design. Completing this design does **not** require inventing a new truth plane.

---

## 7. Suggested work packages (when building)

| WP | Acceptance | Status |
|----|------------|--------|
| **WP-S1 Source tag** | Events carry `source.kind` ∈ {`uvc_card`,`obs_virtual`,`unknown`,`synthetic`}; name sniff + CLI/`RETINA_SOURCE_KIND` override | **done** — `classify_source_kind` / `build_source_dict` in `streamer_perception.py`; CLI `--source-kind` / `--device-name` |
| **WP-S2 Dual open** | Runtime can open primary+secondary devices; per-source eye-check fail-closed | **done** — `DualStreamerRuntime` in `streamer_perception.py`; CLI `--secondary-device`/`--secondary-device-name`/`--secondary-source-kind`; per-source `session_start` + `source_secondary_failed` |
| **WP-S3 Session marker** | OBS text/QR encodes `session_id` (+ short root); Retina OCR verify optional, advisory | **done** — `SessionMarker` text + optional QR generation; `decode_session_marker` fail-open (QR→OCR); overlay displays marker; `session_marker` event emitted |
| **WP-S4 Shared clock** | Frame events and controller events share documented clock field (monotonic ns or session head) | **done** — every event carries `clock_ns` (`time.monotonic_ns()`); `session_start` and all events carry `session_head_ns` |
| **WP-S5 Presence-sync activity** | High-confidence optical activity gated on recent controller input; unit tests for no optical-only “playing” claim | **done** — `PresenceProvider` + `TouchFilePresenceProvider`; `activity`/`zone`/`frame_stats` carry `presence_sync_ok`; false when controller not recent |
| **WP-S6 Non-merge tests** | Explicit tests: optical fields never set `poep_enabled` / eligibility | **done** — `test_streamer_perception.py` asserts no `poep_enabled`/`l6b_enabled`/`candidate_ok` in streamer events |

---

## 8. One-sentence seal

Streamer play through OBS-as-UVC and Trio-Retina’s synchronized, queryable perception stream can coexist as **linked views of one session**, with the controller lobe as the only cryptographic anchor and the screen lobe forever limited to observation-plane `WorldState` that can be causally explained — never substituted for truth.

---

**End of trio-retina-obs-sync-v0**
