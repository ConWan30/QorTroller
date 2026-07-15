# POEP-LIVE-1 — first live nonce-challenge capture on the registered Edge (2026-07-15)

**Summary only (aggregates + verdicts). The per-challenge reaction-time scalars live in the
gitignored `audits/poep_live_capture_P1_2026-07-15.json` — operator behavioral biometric, public repo,
kept local. Never bank the raw scalars here.**

## What ran
`scripts/poep_live_capture.py` (`ffdfc769`) — the live nonce-scheduled reflex capture. Same
`_fire_probe_sync` primitive that recorded the N=52 usable-reflex corpus, but the challenge fires at an
**unpredictable, nonce-derived random moment** (no ENTER cue) and the response is bound to a **fresh
per-challenge nonce**, then audited by `l9_presence.poep_live_verify.verify_live_response`.

- Device: registered Edge `581a836c…` · `policy_ref=edge_operator_reflex_v1` · 8 challenges.
- Fire delays: nonce-derived, scattered **3.3 s → 11.4 s** (genuinely unanticipatable).
- `r2_at_probe = 0` on all 8 — pure involuntary reflex, R2 never pressed.

## Result: 8/8 LIVE-VERIFY PASS
First live nonce-challenge evidence on the certified device. Every response landed after its challenge,
in the `[80,300] ms` reaction band, above the 1000 LSB IMU floor, with a commitment that recomputes
from the stored scalars. **The crypto binding + verify path ran end-to-end on real reflexes for the
first time.**

## The finding (load-bearing): surprise reflexes run slower than primed
| | This session (live surprise) | Calibration corpus (ENTER-primed) |
|---|---|---|
| Mean latency | **253 ms** | 177.6 ms (RBM-v0 `mu_latency`) |
| Latency range | 213 – 286 ms | — |
| Mean peak | ~3162 LSB (min 1773, all ≥ floor) | 1564.8 (`mu_peak`) |

Surprise-mode reflexes ran **~75 ms slower** than the primed corpus — exactly the expected priming
effect, and evidence the protocol measures a harder thing than the ENTER-cued corpus ever did. But
**2 of 8 (286, 281 ms) sit within ~15 ms of the 300 ms band ceiling.** The `[80,300]` band and the
RBM-v0 params were calibrated on *primed* reflexes; a live-surprise protocol lives higher in the band.

**Implication:** any future presence model must **recalibrate on surprise-mode captures, not the primed
corpus.** This session seeds that corpus. (Shape note: challenge #6 `precursor_gap` 25 ms vs ~250 ms for
the rest — different reflex shape, verify-irrelevant, worth a later look.)

## Claim ceiling (unchanged)
Candidate live evidence. Each PASS = a reflex causally bound to a live unpredictable stimulus — defeats
**replay + pre-scheduled macro by construction**, NOT yet a reactive bot (waveform-shape + Stage-A
gated). `poep_enabled` / `L6B_ENABLED` / `L6_CHALLENGES_ENABLED` stay **False**. No chain write, no
FROZEN/PoAC/Solidity edit, PV-CI 183.
