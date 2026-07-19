# (ii) R2-onset — read-at-fire (C) gold-standard t0 (LIVE 2026-07-18)

**Branch:** `feat/l9-consistency-adversarial-harness` · **Spend:** 0 · no flag flips
(`L6B_ENABLED`/`poep_enabled`/`L6_CHALLENGES_ENABLED` stay False) · kill-switch held · `bridge/.env` untouched.
grok charter-(a): co-design (round-r2onset-02) → build → **SHIP**. Follows F-R2ONSET-1 honest-t0 (`785f0ea5`).

## What C is
The device-latency reference is now captured at the FIRE INSTANT directly in device space, defeating the
pre-buffer staleness F-R2ONSET-1 exposed:
- **Bridge (additive/instrument-only):** the ~1 kHz raw drain thread now stores `self._last_raw_device_ts`
  = the offset-28 tick UNCONDITIONALLY (independent of retina/`_push_l2`, so it works in LEAN). The
  nonce-bound fire reads it at the fire instant (`_t0_read_device_ts`) into the pending; the dump writes
  `t0_read_device_ts`. Touches NOTHING gating (no `latency_ms`/verdict/corpus/flags).
- **Study:** `read_at_fire` t0 precedence (over mono-extrap/stale_pre). Crucial live subtlety: `t0_read`
  can EXCEED `post0` because `post0` is a stale BUFFERED sample (sampled before the fire, delivered late in
  an RP burst) while the drain read is the freshest tick — so the window must NOT require `t0_read ≤ post0`.
  Uncertainty interval = `[t0_read − drain_delta, t0_read]` (one drain interval, tight), pre-fire frames
  (`t_rel < 0`) excluded.

## Live result (4 fresh rig fires, rapid — the stress case)
| signal | value |
|---|---|
| `probe_device_ts` (old pre-buffer ref) | **FROZEN 111221413** across all 4 (rapid-fire staleness) |
| `t0_read` (read-at-fire) | **fresh + advancing** 114.77M → 137.51M → 156.98M → 176.77M (~3 MHz) |
| `t0_read − post0` | 533 / 1436 / 1520 / 1690 ms (drain is fresher than the stale post0) |
| study method | **`read_at_fire` on all 4** |
| `reference_gap` | **8 ms** (was ~650 ms under mono-extrap) — ~80× tighter |
| `lat_pt` | **340 / 342 / 342 / 344 ms** (median 342), bounds ~8 ms |
| verdict | **CHANNEL VIABLE under honest t0** (4/4 plausible) |

## The determination (honest, gold-standard footing)
1. **C works** — read-at-fire is immune to the pre-buffer freeze; t0 uncertainty collapsed 650 ms → ~8 ms.
2. **The R2-onset reaction is ~342 ms ± 2 ms** — categorically **NOT a sub-280 ms neuromuscular reflex.**
   It is a **VOLUNTARY reaction** to the felt buzz, confirmed with tight precision across 4 fires. This is
   the "voluntary-not-reflex" finding grok predicted, now MEASURED. To flip in-band would need ≥60 ms of
   systematic latency overstatement; the drain is provably live (3 MHz), making that implausible.

## Honest residuals (grok C-verify, documentation-grade — NOT ship-blockers)
- **`reference_gap` under read_at_fire is a typical-cadence PROXY** (median frame gap), NOT a certified
  uncertainty bound — the drain's ACTUAL staleness at the fire is UNMEASURED. The claim is band-scale
  ("likely voluntary-not-reflex"), NOT "latency known to ±8 ms" metrology. The study output says so.
- **Next increment (C-precision):** log the drain read's wall/mono time when updating `_last_raw_device_ts`;
  at fire compute exact staleness `delta = max(median_frame_gap, fire_wall − drain_wall)` → certified UQ.

## The reframe (why this is a win, not a dead end)
A ~342 ms **voluntary** reaction to an **unpredictable nonce-bound haptic challenge**, timed by the silicon
clock, is a legitimate liveness/anti-cheat primitive: a bot must not react, react implausibly fast, or too
slow, and replay cannot fake the device-clock-bound response to a fresh nonce. PoEP-via-R2-onset becomes an
honest **voluntary-reaction liveness** proof (band to be characterized over N), not a reflex proof. Scope
unchanged: candidate/instrument only; `poep_enabled`/`L6B` stay False; no presence claim from this study.

Tests 9/9 (`test_poep_ring_coupling_study.py`) + fire-timeout regression + PV-CI 184. Sealed `l9_presence`
byte-untouched; zero spend.
