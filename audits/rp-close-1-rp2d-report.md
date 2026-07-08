# RP-2d + RP-2c + LUMEN-1 — Card-Free Arc Report (2026-07-07)

Executes the approved card-free plan: the deferred-attestation tier (RP-2d), the LUMEN-1
game-state buffer, and the RP-2c window-gated densification code. Zero new hardware.

## RP-2d — Deferred Attestation: the card-free RP authorship figure

`l9_presence/kas_deferred.py` (schema `qortroller-kas-deferred-v0`, REFERENCE-AND-BIND —
no new domain tag; integrity = manifest per-crop SHA-256s + live KAS commitment +
session_id). The conjunction semantics are preserved post-hoc: `DEFERRED_AUTHORED`
requires a K≥3 archive cluster whose span intersects a **live R2 window**; a cluster
outside every window is honestly `DEFERRED_OBSERVED` (input conjunction not established).
The live verdict string is never emitted (pinned by test).

### Match 14 (Remote Play) — the headline figure

| Metric | Value |
|---|---|
| Session verdict | **DEFERRED_AUTHORED_SESSION** |
| DEFERRED_AUTHORED (K=3 + window conjunction) | **3** (of 11 operator kills = 27%) |
| DEFERRED_OBSERVED (K=3, no window) | 1 |
| Un-promotable (below K=3) | 11 |
| Live windows joined | 7 |
| Verifier | OK — 20 checks (crop re-hash + arithmetic) |

Live KAS said `INSUFFICIENT_KILLS 0/11`; the sealed archive + window join attests 3 with
the same conjunction the live claim makes. **QorTroller now has an RP authorship figure
on hardware in hand: 3 kills deferred-attested, precision 1.0.**

### Match 13 (HDMI) — ground-truth cross-check: PASSED

Deferred=9 ≥ live=8, and every live-authored kill is in the deferred set — the deferred
tier found one MORE window-conjoined kill than live promotion (the archive stream is
denser than the live classify stream; the expected relationship, now measured).
Verifier OK — 59 checks. Zero-false-read bar re-held on both re-scans (0 suspects/937 crops).

### Scan v2

`rp_ocr_precision_scan.py` now emits per-read `{file, ts_ns, sha256, text, conf, slot}`
(`scan_version: rp-ocr-precision-v2`) — the join fodder RP-2d and LUMEN-1 consume.

## LUMEN-1 — Game-State Buffer (the meaning-plane seed)

`l9_presence/game_state_buffer.py` (+ runner): session-id-joined `SceneEventStream` —
SCENE_CHANGE / SCENE_STABLE_SEGMENT (offline twin of the live fresh-row gate) +
KILL_ROW_CLUSTER (lifted from v2 scans, never re-running OCR) + INPUT_WINDOW overlays.
Commitment-referenced (crop SHAs), advisory, `verify_stream_references` = the LUMEN-2
join check.

| Session | Events | Join |
|---|---|---|
| M14 (RP) | 403 (381 change / 15 clusters / 7 windows) | OK — all refs resolve |
| M13 (HDMI) | 484 (425 change / 2 stable / 27 clusters / 30 windows) | OK |

**Honest calibration note (F-LUMEN-1):** at panel scale the 6.0 fresh-diff threshold
(tuned for the killer-slot region) classifies almost every frame-pair as SCENE_CHANGE
(381/412 on M14) — Warzone's HUD panel is nearly always changing. Segment-level scene
structure needs a panel-scale threshold study; that is a LUMEN-2 refinement, not a bug
in the buffer (events are honest at the declared threshold).

## RP-2c — Window-Gated Densification (code shipped, default-OFF; live validation rig-gated)

**3a verification REFUTED Fix A:** the live inline classify worker reads `_panel_bgr`,
which is cropped from the FULL-RES frame (line ~474) — the live path was never
downscale-degraded (F-RP2C-1). The downscaled `_kf_bgr` feeds a non-certificate consumer.
The live-vs-archive gap is sampling count, confirming F-RP2-1 as stated.

**Fix B shipped:** `RETINA_KF_EVERY_BURST` (env, default 0=OFF, byte-identical when off):
inside a live R2 window the panel stash cadence drops 20→N frames AND the ring flushes
from the burst thread on every NEW stash (de-dup by stash ts) instead of only the ~1Hz
tune() tick (M14's measured 0.93 crops/s ceiling). Expected in-window density at N=5,
~30fps, 0.15s burst ticks: ~5-6 crops/s (≈5x) exactly where kills happen; ~zero cost
elsewhere. The dense window opens ONLY via `mark_r2_onset` (input side) — screen content
never reaches the cadence decision (anti-splice rail, pinned; the pinned test caught a
real never-armed-sentinel boundary bug on first run, fixed before landing).

**Live validation (rig-gated):** next announced RP match with `RETINA_KF_EVERY_BURST=5`;
success bar in-window reads-per-cluster ≥ 2.5 (M14 baseline 1.93); then RP-2d re-runs on
its archive — the live-vs-deferred gap should close. Doubles as the ES-P0/P2 session.

## Verification summary

- 95/95 tests green (12 kas_deferred + 9 game_state_buffer + 9 rp2c + adjacent
  killfeed_inline/posp/KAS/preflight suites untouched-green); PV-CI **182 PASS**.
- M13 cross-check passed (deferred ⊇ live); both verifier mirrors OK (20 + 59 checks).
- Zero-false-read bar re-held across the 937-crop v2 re-scan.
- Flags default-OFF; no FROZEN edit; no chain write; 0 IOTX.

## Files

Records: `audits/kas_deferred_record_match14_*.json`, `audits/kas_deferred_record_match13_*.json`
Streams: `audits/scene_stream_match14_*.jsonl`, `audits/scene_stream_match13_*.jsonl`
Scan: `audits/rp_ocr_precision_scan_v2_m14_m13.json`
