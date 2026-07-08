# Match 15 — The Accidental True-Negative (RP-2/A2 partial; ES-P0 CLOSED)

**2026-07-08. Setup: controller USB to laptop, Remote Play, operator played and got
13 kills, felt all fire haptics. Session `match15_rp_fixb_1783548472`, 413 crops,
first PoSP minted with BOTH named roots + beacon ref at issuance.**

## What happened

~25 seconds after launch the controller silently flipped its ACTIVE INPUT LINK to
BT-PS5 (the known dual-connection mode: USB stays enumerated and streaming frames, but
stick/trigger fields carry no live input). The operator could not have noticed — game,
haptics, and stream feel identical. Timeline: COUPLED_CLEAN 17:08:14→17:08:30, then
IMPLAUSIBLE / REPLAY_OR_RELAY for the entire match. Zero raw R2 onsets, zero windows,
zero live classifications — while 413 PoAC records + 413 fusion rows kept flowing.

## F-M15-1 — the live true-negative demonstration

A real match was visibly played (archive scan: the operator's kills in the killfeed,
12 own-handle reads / 8 clusters, 0 false reads) — and the system, presented with
gameplay NOT driven by the certified input path, refused to attest ANY of it:

| Surface | Verdict |
|---|---|
| Presence (NQPV) | IMPLAUSIBLE all match |
| KAS | INSUFFICIENT_KILLS authored=0/13 |
| Windows / classifications | 0 / 0 |
| PoSP join | SYNCHRONIZED (identity join held — the QUALITY verdicts inside carry the refusal) |

**Kills on screen; no certified hands on the attested path; nothing certified.** This is
the exact session class the anti-cheat exists to refuse, caught live and by accident —
the strongest kind of validation, because nobody staged it.

## F-M15-2 — the haptic echo observed (ES-P0 CLOSED, ES-P2 partially answered)

Operator felt all fire haptics (ES-P0: Remote Play DOES forward game haptics — premise
CONFIRMED). And the IMU measured them: in-match records show median `tremor_peak_hz`
= **48.94** (the haptic-motor band) across 342 records vs **0.00** pre-match — the
accelerometer feeling game-driven rumble THROUGH the USB stream. Bonus discovery: the
IMU channel stays live on USB even when the input link flips — **the EDGE-SENSE echo
lobe works in exactly the failure mode that blinds the input lobe.** (Spectral detail
still wants the 1000Hz ES-P2 capture; the 120Hz-band evidence is already unambiguous.)

## F-M15-3 — first-ever suspect read: ADJUDICATED GENUINE

`Qortroia30` (l→i OCR confusable of the operator's own handle, killer slot, conf 94).
`canon()` correctly normalizes confusables; the scan's plain-substring audit flag is
deliberately stricter and surfaced it for human adjudication — working as designed.
**Zero-false-read bar HOLDS** (0 non-own-handle reads across 977 RP-era crops total).

## Also proven this session (the wiring from yesterday, live)

- First PoSP with `retina_perception_root` minted AT ISSUANCE: `a5957a7c…` from
  413 live perception rows / **119,928 events** (LUMEN-4b).
- First PoSP with `temporal_beacon` ref at issuance (A3-b; block 45026880 — the
  keeper-cadence staleness note KC-A3b-1 applies, visible and honest).
- Live match-state watcher ran; honestly emitted zero transitions (no input signals
  ever arrived — correct behavior on this session's data).

## Open

- **Fix B UNTESTED** (no windows → burst densification never armed). Rerun required.
- **Link-guard protocol for the rerun:** (1) pre-queue: operator fires 2 test shots,
  Claude confirms raw onsets landing before the match starts; (2) in-match: Claude
  tails the daemon diag; if COUPLED flips IMPLAUSIBLE while playing -> say so
  immediately; operator unplug/replugs USB (hot-plug auto-reconnect is built).
- Root-cause question (why did the link flip at match start?) stays open — candidates:
  PS-button press at match start, console-side re-grab. The guard makes it survivable
  regardless of cause.

## Files
- KAS: `audits/kas_record_match15_rp_fixb_2026-07-08.json`
- PoSP (first fully-rooted): `audits/posp_record_match15_rp_fixb_2026-07-08.json`
- Scan: `audits/rp_ocr_precision_scan_v2_m15.json`
- Archive: `retina_kf_archive/match15_rp_fixb_1783548472/`
