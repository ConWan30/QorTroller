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

## The finding (provisional, directional — NOT a closed result)
| | This session (live surprise) | Calibration corpus (ENTER-primed) |
|---|---|---|
| Mean latency | **253 ms** | 177.6 ms (RBM-v0 `mu_latency`) |
| Latency range | 213 – 286 ms | — |
| Mean peak | ~3162 LSB (min 1773, all ≥ floor) | 1564.8 (`mu_peak`) |

Live-surprise reflexes sat higher in the band (mean 253 vs ~178). The likely mechanism is a
foreperiod/readiness effect (long unknown 3–12 s wait vs operator-initiated ENTER arm), but this is
**provisional, not proven**: N=8; a foreperiod claim is confounded by session/fatigue/attention; and
**both arms share the same ~400 ms baseline tail** (the ENTER corpus was not pure-primed and the live
run is not pure-surprise for its final ~400 ms — see F-POEP-LIVE-1 below). The direction (surprise ≥
primed) is credible; the *magnitude as clean priming* is not established from N=8.

Band pressure is real: **1 of 8 (286 ms) is within ~14 ms of the 300 ms ceiling, a 2nd (281 ms) within
~19 ms.** The `[80,300]` band and RBM-v0 params were calibrated on *primed* reflexes, so a live-surprise
protocol risks false FAIL near 300. **Safe default (not a mandate): recalibrate any future presence
model on surprise-mode captures; this session seeds that corpus.** (Shape note: challenge #6
`precursor_gap` 25 ms vs ~250 ms for the rest — different reflex shape, verify-irrelevant, later look.)

## F-POEP-LIVE-1 (grok round-17 red-team + round-18 forward roadmap)
`docs/a2a/poep/round-17-grok-livecapture-redteam.txt` (verdict: **OVER-CLAIMED** — corrected above) and
`docs/a2a/poep/round-18-grok-forward-roadmap.txt` (the reconciled next-tier plan, consulted **before** the
correction commit per the new pre-commit-verify discipline).

**The weakness:** the shared `_fire_probe_sync` prints `"Baseline IMU…"` then collects a **fixed ~400 ms**
window then fires. Also the commitment binds `(device_id, nonce, feature_digest, t_response)` but **not**
`delay_s`/arm-time, so the auditor does not prove the fire matched the nonce-derived schedule (docstring
softened). Anti-replay / anti-preschedule still hold via the long secret delay.

**The crux — two attack classes, do not conflate:**
- **A-PRE-TELL** — the ~400 ms free arm from the stdout print + fixed pre-window. **Closeable by silence.
  This is the bankable next tier.**
- **A-REACTIVE** — a bot watching the HID **output** report (the R2 force command the host sends) fires at
  the *true* challenge instant. **Fundamentally uncloseable for any host-timed proof** (the host commands
  the force → any co-resident process sees it). Closing it needs controller-firmware force-timestamp / SE
  attestation, or actuator↔IMU physics (waveform + Stage-A = the flip gate), or an external witness.
  **Deferred** — P-LIVE-0 never claimed it. Honest language: *"unpredictable to pre-arm macros; not
  anti-reactive-host."*

**Fix arc (operator-GO):**
1. **(FIRST, highest leverage)** remove the pre-fire I/O tell + silent continuous IMU ring / no fixed
   pre-window boundary; `t_challenge` = force-write instant only.
2. **(same milestone, small)** independent CSPRNG `delay_s` + nonce-for-binding-only (ends bit
   double-duty) + bind `H(nonce‖delay_s‖t_arm_ns‖t_challenge_ns)` so the schedule **becomes** provable.
3. **(next PR)** catch trials (go/no-go): 4:1 go:no-go, ≤5% human false-alarm budget, ≥90% always-fire
   bot catch, joint fail-condition so a twitchy human is not failed on tremor alone.

**The test that makes it a proof** (not "we deleted a print"): a `TellWatcherBot` adversary harness
(`test_f_poep_live_1_tell_watcher.py`) — watches stdout/pre-window, arms, injects a canned in-band IMU
pulse — run against BOTH paths, same bot code, only the capture path swaps.
**PASS condition (this tier's "successful proof"):** *on the certified Edge, the tell-watcher macro's
`verify_live_response` FAR drops from ≥0.90 (old path) to ≤ random-onset chance (~≤0.15, silent + CSPRNG
path), with the schedule bound in `H(nonce‖delay‖t_arm‖t_challenge)`, while `poep_enabled` stays False and
A-REACTIVE remains explicitly out of claim.*

**Surprise-mode corpus (before any presence model):** ≥50 usable surprise captures on the certified Edge
(≥2 operators preferred; N=30 min to call it a "calibrated surprise band," not an identity model);
re-estimate latency μ/σ + measure P95 before freezing the 300 ms ceiling (slow surprise tails may clip);
re-run the 5-class adversarial gate (`adversarial_nulls_rbm_v0.py`) against the surprise-recalibrated
accept region. Do **not** train a model until the (i)+(ii) harness is green — else it's a recalibrated
band check. `poep_enabled` stays False throughout.

## Claim ceiling (unchanged)
Candidate live evidence. Each PASS = a reflex causally bound to a live unpredictable stimulus — defeats
**replay + pre-scheduled macro by construction**, NOT yet a reactive bot (waveform-shape + Stage-A
gated). `poep_enabled` / `L6B_ENABLED` / `L6_CHALLENGES_ENABLED` stay **False**. No chain write, no
FROZEN/PoAC/Solidity edit, PV-CI 183.
