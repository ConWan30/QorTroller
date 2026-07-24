# (ii) R2-onset — ADVERSARIAL harness v0 (2026-07-19)

**Branch:** `feat/l9-consistency-adversarial-harness` · **Spend:** 0 · no flag flips
(`poep_enabled`/`L6B`/`L6_CHALLENGES` stay False) · candidate/instrument only · no presence verdict emitted.
grok charter-(a) adversarial-consult → build. Operator decisions (2026-07-19): GO band **(320, 400] ms
fast-only**; the un-beatable-single-shot attack → **publish residual FAR** (multi-challenge is the follow-on).

## What it is
`scripts/poep_r2onset_adversarial.py` — an OFFLINE harness that stress-tests the R2-onset voluntary-reaction
liveness primitive against a threat model, using the existing dumps + the study verifier. `detect_voluntary_go`
GOes only on a **GOLD read-at-fire t0** + a **real R2 reaction** + `lat in (320, 400] ms`. 9 fixture tests
(CI-safe, no gitignored dumps).

## Results (real N=35 gold dumps + synthetic attacks)
| Attack | Verdict | Note |
|---|---|---|
| **A1 naive replay** (captured response → fresh nonce/t0) | **REJECT** | the unrelated fresh t0 fails gold-window acceptance → non-gold (uncertain) reference → detector REJECTs. Defeated by construction (nonce + device clock). |
| **A2 sub-floor bot** (~150 ms) | **REJECT_TOO_FAST** | below the human floor. |
| **A3 dead feed** (flat R2) | **REJECT_NO_REACTION** | no reaction on the channel. |
| **A4 absurd t0** (out of window) | **REJECT** | no valid gold reference. |
| **A5 fixed-delay in-band bot** (~345 ms) | **GO** | **RESIDUAL, FAR = 1.00 single-shot** — published. |
| **A6 random-timing bot** (ISI 3 s) | — | **FAR = 0.028 ≈ band_width/ISI (0.0267)** — matches analytic. |

**Human:** fast-cluster (≤400 ms) **GO-rate 18/18 = 100%**; the slow tail (12) → **SOFT (retry)**, never a bot
flag; flat-R2 gold dumps from the topology-blind period → correctly REJECT_NO_REACTION.

## Honest claim ceiling — what a PASS means (and only means)
- **Construction attacks (A1/A2/A3/A4) REJECT by design** — naive replay, sub-floor, dead-feed, absurd-t0
  cannot produce an in-band GO.
- **Human fast cluster GOes** (low FRR on that subset); slow honest taps are SOFT, not accused.
- **A5/A6 residual FAR is MEASURED and PUBLISHED**, not waved away.
- Stays a **voluntary-reaction liveness CANDIDATE** on a **single-operator provisional band**.

**A PASS does NOT mean:** a sub-280 ms reflex; a population biometric; tournament-ready `poep_enabled`;
defeat of a fixed-delay bot on a SINGLE challenge (A5 passes — that's the honest residual); or defeat of a
bot that learns the fire time from host APIs / a hardware injector. σ≈3.7 ms is anti-*random*/anti-*sloppy-
macro*, NOT anti-bot by itself (a good bot matches mean±σ). The 339 ms floor is from N=18/one operator/one
night — the (320, 400] band uses a soft margin to avoid overfitting; it is provisional.

## What offline CANNOT prove (rig/crypto remainder)
- A live bot that reads the fire time from host APIs / HID echo / the RP path (needs a live host-API bot, no human).
- A hardware injector (Cronus/XIM) — needs a physical macro box on a second pad.
- Cryptographic challenge authenticity — the dump field is a *nonce-labeled record*, not a crypto bind;
  upgrade = **HMAC(nonce‖t0‖onset)** committed at fire, frames stream-bound before the dump is written.
- Multi-session / multi-person FRR — grow N across sessions and operators; re-estimate the floor.

## Next (flagged, not built here)
1. **Multi-challenge variance** — the A5 defense: require the human's natural cross-challenge variance over
   several fires (a fixed-delay bot has near-zero variance → flagged). Turns FAR=1.0 single-shot into a
   low multi-shot FAR.
2. Rig-gated live-bot + hardware-injector tests.
3. HMAC frame-commitment at fire (cryptographic nonce/response binding).
4. Population band (cross-session/operator N).

9 fixture tests + PV-CI 184. Zero spend; sealed `l9_presence` byte-untouched; no PoAC/FROZEN edit.
