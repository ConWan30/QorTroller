# Card Arrival — Live OBSERVATION-Plane Bring-Up (CWL-1 C0 / TRA-1 T6 first light)

**2026-07-12.** First live capture-card session. The OBSERVATION plane went live over real
HDMI video; the ASSERTION plane (the 228-byte PoAC wire) was provably untouched (PV-CI **183**
PASS). This banks what was proven, the load-bearing design correction, and the rig-gated arcs it
surfaced. All rig work this session was **read-only on the card** — zero PoAC / chain / IOTX contact.

## What was proven

### C0 — capture card LIVE (GO)
- Card = **UVC index 1**, delivering **1920×1080@60** (ideal). Laptop built-in webcam = index 0
  (720p). Operative setting: **`RETINA_UVC_INDEX=1`**.
- The daemon's exact open-path (`UvcFrameSource`: `CAP_DSHOW` → MJPG → 1080p60 → prove a frame)
  works on the card. OpenCV **4.13.0** present. Verified visually = the PS5 feed (CoD).
- Physical topology: **PS5 HDMI OUT → card HDMI IN**; **card HDMI OUT → TV** (passthrough,
  lag-free play); **card USB → laptop** (UVC); **DualShock USB-C → laptop** (HID); **DualShock
  BT → PS5** (gameplay). **PS5 HDCP OFF** (Settings → System → HDMI).
- **Kill-check: PV-CI 183 PASS** — the 228-byte PoAC / ASSERTION wire untouched by all rig work.
  The separation law demonstrated on real hardware: *observation observed; assertion stayed frozen.*

### R2 — content-framing PASS
- Retina crops are stored as **fractions (0..1)** → resolution-independent (converted to px at
  runtime by `_roi_px`). WGC → card does **not** shift them by resolution.
- The card feed is full-frame 16:9, **zero letterbox** — the one residual risk R2 exists for
  (aspect/letterbox) is absent. Crops transfer directly.

### Killfeed ROI is game/mode-specific (NOT universal)
- Default (top-right `0.62,0.10,0.36,0.22`) = **Warzone BR** (calibrated from matches M11–M17).
- This session's mode (CoD economy/DMZ: "MAIN STREET", cash roster, Nikolai callouts) puts the
  killfeed **left-middle**. Corrected ROI measured + overlay-verified dead-on:
  **`0.0, 0.45, 0.26, 0.19`** (all feed rows cleanly inside, good margins).

### OCR gate baseline — the Warzone engine abstains on this mode
- Engine: `l9_presence.killfeed_ocr_bootstrap.tight_row_ocr`, `ENGINE_V6 = rapidocr_ppocrv6_small`
  (PP-OCRv6_rec_small.onnx). Installed package is **`rapidocr`** (not `rapidocr_onnxruntime`).
- Baseline over **20 real this-mode killfeed frames**: **matched=0, abstained=20, read_errors=0.**
- Root cause: the authorship engine is Warzone-calibrated on **three** axes — (1) killfeed ROI
  top-right, (2) own-handle template `l9_presence/assets/own_handle_anchor_feed.png` (Qortrola30 as
  rendered in BR), (3) top-feed geometry `feed_region_max_yfrac` ≈ 0.42. This mode differs on all
  three (the G3 finding predicted it: "MP renders the feed lower → the default silently rejects
  every kill row").

### Zero-false-read intent observed holding (with honest caveat)
- The 20 frames captured a **squadmate (FaithBeyond7) 4-kill streak** in the operator's feed.
  Operator gamertag = **always Qortrola30**.
- The engine authored **ZERO** of the squadmate's kills for the operator — correct: **you cannot
  inherit a teammate's kills.**
- **Caveat (no overclaim):** the abstain is *partly* template/geometry mismatch (couldn't read the
  region at all), so **positive recall is UNTESTED** — this burst had no Qortrola30 kills. The
  zero-false-read result is real in intent but partly trivial (it read nothing).

## The load-bearing design correction (operator, 2026-07-12)

**The team roster is NOT stable across matches.** Teammates (FaithBeyond7, JamesBond007, …) are
random and change every match. The **only** constant is **Qortrola30** (the operator's handle).

Therefore:
- **Self-differentiation must key SOLELY on the constant string `Qortrola30`** — never on team
  composition.
- The killfeed shows the whole team's kills; **author a kill iff the KILLER slot reads
  `Qortrola30`.**
- The roster (bottom-left — a stable *location* every match) is a valid place to confirm
  "Qortrola30 is present in this match" (session/presence), but its **contents vary** — never model
  the team.

## UPDATE — live authorship recall PROVEN (same-day Resurgence session)

A second live session (Warzone **Resurgence Casual**) captured real Qortrola30 kills and **proved the
recall the first session couldn't test.**

**Correction to the ROI story:** the kill feed is **left-middle in Resurgence too** — so it is
left-middle across this operator's *entire* setup, not a per-mode quirk. The default top-right ROI was
simply wrong for this config; **`0.0,0.45,0.26,0.19` is the right ROI across modes.**

**The path that works is the operator's own design, not the template.** The legacy template-match
engine (`tight_row_ocr`) abstained even with a left-middle geometry override — the BR-rendered
`own_handle_anchor_feed.png` template doesn't match this rendering. But **raw OCR (RapidOCR
`PP-OCRv6_rec_small`) of the ROI + "is `Qortrola30` the LEFTMOST (killer) token of a feed row?"** reads
the handle cleanly and differentiates. Author a kill iff the killer slot ≈ `Qortrola30` (fuzzy on the
`ortrola` stem for OCR robustness); a teammate killer, or `Qortrola30` in the victim slot, → not
authored.

**Results (3 bursts × 20 frames, live off the card):**

| burst | Qortrola30 kills caught | non-Qortrola killer rows in feed | falsely authored |
|---|---|---|---|
| kill1 | **2** (→KING___2008, →AWOLNoob; 8 frames) | 62 | **0** |
| kill2 | 0 (latency — caught the tail) | 36 | **0** |
| kill3 | 0 (latency — empty feed) | 0 | **0** |

- **Recall PROVEN:** both kill1 kills detected across 8 frames — with teammates rosa sparks +
  Deslayer295 killing in the *same* feed.
- **Zero-false-read PROVEN:** **~98 real non-Qortrola kill rows, ZERO authored to Qortrola30.**

**The capture-cadence limit (why kill2/kill3 missed *your* kills):** the manual "operator says 'kill'
→ Claude fires a burst" loop lags ~10–30 s (message read + grab), which outruns the ~5 s kill feed.
This is a capture-cadence limit, **NOT** an authorship-logic failure (kill1 proves the logic). The
production tool is the **retina daemon** (`qortroller_retina_capture.py`) — continuous per-frame
sampling, independent of turn latency. A full-match daemon run + end-match **scoreboard** cross-check
(its per-player kill total = ground truth) is the proper certification path.

**Match-lifecycle states captured** (for the monitor): menu (PLAY tab; `Qortrola30` in party
top-right) → matchmaking ("THE MATCH IS ABOUT TO BEGIN"; `YOUR SQUAD` top-right, **Qortrola30 row
highlighted**) → in-match (roster **bottom-left**; deployment countdown). **Two roster surfaces:**
pre-match squad top-right, in-match roster bottom-left — both carry the constant `Qortrola30`.
Teammates confirmed varying across three matches (FaithBeyond7/JamesBond007 → rosa
sparks/Deslayer295/Jdastar2 → Efram1/DuneSarcophagus) — the teammates-vary rule, live.

## Scoped next arcs (rig-gated)

### A) Per-mode authorship calibration (this mode)
1. Build a this-mode **Qortrola30-in-feed template** — crop `Qortrola30` as it renders in *this*
   mode's killfeed (different colour/style than BR).
2. **Geometry override** for the left-middle feed: `feed_region_max_yfrac` ≈ 0.64,
   `killer_max_frac` ≈ 0.18 (via the `KILLFEED_CV_FEED_MAX_YFRAC` env path — G3 precedent).
3. Capture a **real Qortrola30 kill** in this mode (RIG-GATED — operator must get kills as
   Qortrola30 in this mode; this session's burst had none).
4. Re-run the OCR gate: verify **recall** (reads Qortrola30's kill) **and** zero-false-read
   (does not author teammates' kills).

### B) Full match-lifecycle monitoring (operator vision)
- Menu → searching → loading → in-match **state detection** (LUMEN-2b match-state adapter).
- Roster-anchored **presence** confirmation (Qortrola30 present; teammates vary).
- Live ASSERTION + OBSERVATION fusion with operator **verbal sync**.
- **HONEST:** the ASSERTION plane (live button HID) is **dual-connection-blind** — while the
  controller is BT-paired to the PS5, the USB HID to the laptop can carry no live input. The
  operator's verbal sync ("pressing R2 now", "sitting still") is the **correlation bridge for the
  study, not the cryptographic button capture** (a separate, harder rung).

## Rails held
- No rig work touched the 228-byte PoAC wire (PV-CI **183** PASS on the C0 kill-check).
  OBSERVATION-plane only; `RETINA_PERCEPTION_ENABLED` stays default-OFF.
- No chain writes; 0 IOTX.
- **Single-committer:** every session artifact was scratchpad / read-only; nothing committed
  autonomously.

## Claim ceiling
- Card + content-framing + killfeed ROI **proven**. Live authorship **recall PROVEN** (kill1: 2 kills
  / 8 frames) and **zero-false-read PROVEN** (~98 non-Qortrola killer rows across 3 bursts, 0 false) —
  via the raw-OCR + killer-slot string match, **NOT** the legacy template engine (which abstains here).
- **Not yet done:** continuous full-match capture (manual bursts miss kills on latency → the daemon is
  the tool), end-match scoreboard-count cross-check, larger N across matches. Recall is proven at the
  *event* level (both kills caught), not certified per-frame.
- Nothing here touches the 228-byte PoAC wire (PV-CI 183) or the Warzone-BR corpus (M11–M17).

---
*CWL-1 C0 / TRA-1 T6 first light. Loops: TRA-1 (retina.event/0.1 adoption) · TRL-1 (card readiness)
· CWL-1 (card orchestration). Operator-paced; per-mode arcs rig-gated; nothing committed here.*
