# Match 17 — Live RP Authorship Achieved (RP-2/A2 CLOSED; Fix B VALIDATED)

**2026-07-08. Controller USB to laptop, Remote Play, link-guard active. Operator: 18
kills. Session `match17_rp_fixb3_1783550435`, 12.6-min match, 908 crops.**

## The headline

**KAS: AUTHORED_SESSION authored=17/18 (94.4%) — live kill authorship under Remote Play
at the conservative K=3 floor.** Three days ago this figure was 0/11 (Match 14). The
gap F-RP2-1 named — crops-per-kill density — closed with software on the same laptop.

| Metric | M14 (pre-Fix-B) | **M17 (Fix B on)** |
|---|---|---|
| Live authored | 0/11 (0%) | **17/18 (94.4%)** |
| Windows / composites | 7 / 7 | **31 / 31** |
| Crops archived | 413 | **908** |
| Reads per cluster | 1.93 | **7.50** (2.6× even the HDMI baseline's 2.85) |
| In-window crop density | ~0.93/s | **2.08/s** (vs 0.53/s outside — 3.9× window-gated) |
| False reads | 0 | **0 (largest test yet: 908 crops, 0 suspects)** |
| Hygiene | clean | clean (0 errs, 0.0s stall) |

**Fix B (RETINA_KF_EVERY_BURST=5) VALIDATED** — window-gated densification concentrated
532 of 908 crops inside the 256s of trigger windows, exactly where kills happen; K=3
promotion completed live on 17 kills. The RP archive is now denser per kill than direct
HDMI ever was. (F-FIXB-1 stands: flush is classify-thread-bound at ~2/s vs ~5/s
theoretical — didn't matter tonight; a dedicated flush timer remains a small follow-up.)

## The tiers converge

Session report (`session_report_match17_*.md`) — **zero GAPs, first time**:
- PoSP **VERIFIED 7/7** (fully rooted: perception root `758fe8c9…` from 58,358 events
  with recompute = **MATCH**; beacon ref present)
- Match-state: one 14.7-min match, containment 24/24 anchors + 30/30 windows
- **Deferred = 17 authored = live 17** — the live and post-hoc tiers agree exactly
- Ground truth: 210 own-handle reads / 28 clusters / **0 suspects**; 17 K≥3 clusters ↔
  17 attested ↔ 18 operator kills (one kill under-sampled — honest residual)

## The link-guard worked

Pre-queue onset check (5 test onsets confirmed on the replugged controller before
queueing) + live verdict-transition monitor. The M15 failure mode was made survivable:
one guarded relaunch after the M16 unplug, and M17 ran clean end-to-end.

## Session sequence tonight (M15 → M16 → M17)

- M15: accidental TRUE-NEGATIVE (link flip; 0/13 attested; system honest) + ES-P0 closed
- M16: unplug mid-session → HYGIENE_FAIL (78.3s stall; every tier refused — honest) +
  Fix B first density signal (1.19/s in-window)
- M17: everything working at once — the match this project will cite

## ES-P2 (partial, banked during the scan window)

Segments 1 (idle grip floor) + 2 (continuous fire haptics) captured at **999.6Hz**
(~150k reports each) to `sessions/` (gitignored — biometric data never leaves the rig).
Segment 3 (damage rumble) DEFERRED — piggybacks on any future match's natural damage.
ES-P3's pre-registered spectral study (≥10× band-power bar, zero false events on idle)
runs offline next session on the banked captures.

## Files
- KAS: `audits/kas_record_match17_rp_fixb3_2026-07-08.json` (commit `4b453dd8…`)
- PoSP: `audits/posp_record_match17_rp_fixb3_2026-07-08.json` (VERIFIED, fully rooted)
- Scan: `audits/rp_ocr_precision_scan_v2_m17.json` · Session report: `audits/session_report_match17_*.md`
- Archive: `retina_kf_archive/match17_rp_fixb3_1783550435/` (908 crops, manifest-committed)
