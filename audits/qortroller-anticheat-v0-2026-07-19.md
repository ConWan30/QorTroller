# QorTroller anti-cheat detector — v0 · CANDIDATE, ADVISORY (ASM-Loop r02 → r08, 2026-07-19)

**Branch:** `feat/l9-consistency-adversarial-harness` · **Spend:** 0 · **candidate/advisory only** — emits a
verdict, **gates nothing**; `poep_enabled`/`L6B`/`L6_CHALLENGES` stay False; no on-chain, no flag flip.
Composes the session's pieces: read-at-fire C + C-precision (gold t0) → `detect_voluntary_go` (per-fire) →
`detect_session` (multi-challenge aggregator). Revised in r04 after grok's r03 audit (F1–F13, HOLD).

## What it is
`l9_presence/qortroller_anticheat.py::detect_session(recs, k_required=5, rate_min=0.20, isi_ms=3000)`.
Verdict ladder (fail-closed): **SUSPECTED_BOT** (any sub-floor press) → **HUMAN_PRESENT** (`n_go >= threshold`)
→ **DEAD_FEED** (no reaction anywhere) → **INSUFFICIENT**. GO threshold `= max(K=5, ceil(rate_min·N))`.

## Why it works — unobservable-challenge compounding (not consistency)
The adaptive-trigger buzz is a PHYSICAL event a bot's software cannot observe → a fire-time-BLIND bot guesses,
with per-challenge in-band rate `p_go = band/ISI` (2.67% at ISI=3 s). Requiring the GO count above `threshold`
drives the false-accept rate down while a live human — who FEELS each buzz — clears it. σ≈3.7 ms is NOT the
source of strength (a bot can match mean±σ); the unobservability + device-clock + nonce are.

## FAR model — TRUE multinomial vs the loose binomial (r04 fix, F2/F5)
HUMAN_PRESENT requires `n_go >= threshold` **AND** `n_sub_floor == 0` (any sub-floor press → SUSPECTED_BOT).
So the **true** blind-bot false-accept probability is the multinomial `P(>= thr GOs AND 0 sub-floor) =
Σ C(N,i)·p_go^i·p_other^(N-i)`, `p_other = 1 − p_go − p_fast`, `p_fast = GO_LO/ISI`. The raw binomial
`P(Bin(N,p_go) >= thr)` is a **loose UPPER BOUND** — it wrongly counts paths that also contain sub-floor
presses (which the ladder catches). We report BOTH; the true FAR is ~10× lower **at fixed ISI=3 s** (they
COINCIDE at the joint max, where both = 3.2e-4 — the all-GO regime has no sub-floor paths to exclude).

## FAR-vs-N at FIXED ISI=3s (r04-corrected, F1) — worst-in-N at the crossover N≈25 (the JOINT (N,ISI) worst is larger — see §ISI)
| N | threshold | TRUE FAR (multinomial) | binom UPPER BOUND |
|---|---|---|---|
| 20 | 5 | 2.64e-05 | 1.49e-04 |
| **25** | 5 | **4.55e-05 (true peak)** | **4.58e-04 (UB peak)** |
| 26 | 6 | 5.18e-06 | 5.23e-05 |
| 35 | 7 | 1.31e-06 | 3.34e-05 |
| 50 | 10 | 6.86e-09 | 7.03e-07 |
| 100 | 20 | 2.14e-16 | 2.28e-12 |

**The r02 audit was WRONG** to mark N=20 / ~1.5e-4 as the peak. Corrected: the worst case is at the
crossover **N=25** — TRUE FAR **4.55e-05**, binom UB **4.58e-04**. While the K=5 floor binds (N ≲ 25) the FAR
RISES with N; only once the rate term binds (N ≳ 25) does it CONCENTRATE downward.

## Live result (operator-machine evidence, F6 — NOT committed-reproducible)
On this machine, `audits/poep_ring_dump/` (35 gold dumps, gitignored) → `HUMAN_PRESENT`, GO=18 (rate 0.514)
≥ threshold 7, sub_floor=0, **true FAR 1.31e-06** (binom UB 3.34e-05) at assumed ISI=3 s. **The dumps are
gitignored and the detector files are (until the operator commits) untracked — a clean clone CANNOT reproduce
this number.** The committed evidence is the 17 fixture tests, which never touch real dumps. Synthetic controls:
random-timing blind bot → SUSPECTED_BOT/INSUFFICIENT (never HUMAN); all sub-floor → SUSPECTED_BOT; all dead →
DEAD_FEED; fire-time-OBSERVING bot @345 ms → HUMAN_PRESENT (**published residual**).

## ISI dependence — TRUE FAR is NON-monotone in ISI too (F9 + F16)
A rapid cadence raises **both** `p_go = band/ISI` **and** `p_fast = GO_LO/ISI`. Because HUMAN_PRESENT requires
ZERO sub-floor presses, a short ISI makes the sub-floor trap eat the false-accept paths, so it usually
**LOWERS** the TRUE FAR (only the loose binomial UB rises). The r04 claim that a rapid cadence "raises the
FAR / compounding collapses" was true for the binom UB but **FALSE for the TRUE FAR** — corrected here.

Peak-over-N TRUE FAR vs ISI (thr scaled per N):
| ISI (ms) | **400 (=GO_HI)** | 500 | 1000 | 2000 | 3000 | 6000 |
|---|---|---|---|---|---|---|
| TRUE FAR (peak N) | **3.20e-4 @N=5** | 1.43e-4 @N=6 | 8.5e-5 @N=12 | 7.5e-5 @N=25 | 4.55e-5 @N=25 | 5.9e-6 @N=25 |

**JOINT worst-case TRUE FAR over the (N, ISI) domain = `(band/GO_HI)^K` = 3.20e-4 at N=K=5, ISI=GO_HI=400 ms**
(code-derived by `worst_case_true_far`, not a hand-number). At that point p_go is maximal (=band/GO_HI=0.20)
and p_other=0 forces every non-GO press to be sub-floor, so the only HUMAN_PRESENT path is all-K-GO = 0.20^5.
**N-scope caveat (F20):** "short ISI lowers the TRUE FAR" holds only at LARGE fixed N (the sub-floor trap
dominates); the JOINT adversary chooses SMALL N + ISI≈GO_HI, where it RISES to the 3.2e-4 max. Do not read
"short ISI is safer." Mitigation (not built here): raise K, or refuse challenges with ISI < some floor >> GO_HI.

The detector MEASURES `observed_isi_ms` (median `probe_ts_mono` gap; ~6.3 s on the concatenated 35-dump dir —
advisory) and reports the FAR **at the assumed ISI**, explicitly; the runner takes `--isi-ms`. The published
1.31e-06 is "FAR under an assumed 3 s cadence," not enforced geometry; the security bound is the 3.2e-4 joint max.

## Claim ceiling
- **Voluntary-reaction liveness CANDIDATE**, single-operator provisional band ((320,400] ms, N=18 fast). NOT a
  sub-280 ms reflex; NOT a population biometric; NOT tournament-ready / `poep_enabled`.
- **"Exclusive" = HARDWARE-CLASS** to the certified Edge (silicon-clock + adaptive-trigger haptic + device-clock
  binding), NOT a shipped/unbreakable product anti-cheat (F10).
- The FAR is against a **fire-time-BLIND, TIMING-ONLY** adversary that *already produces gold device-clock dumps*
  (a synthetic privilege, F13); a real bot that cannot forge gold dumps is weaker, and a bot that OBSERVES the
  fire time (host APIs / hardware injector) **defeats** the compounding — a **published rig/crypto residual**,
  defended by **HMAC(nonce‖t0‖onset) frame-commitment** (named follow-on), not this module.
- The sub-floor rail is a **heuristic** (F5), not a proof of non-humanity: a population human faster than the
  320 ms provisional floor would false-positive as SUSPECTED_BOT.
- `read_at_fire` proxy (no measured age) counts as "gold" here, not only `read_at_fire_certified` (F4).
- Advisory: the detector emits a verdict and gates nothing.

## Rig/crypto remainder (not proven offline)
Live host-API bot; hardware injector; HMAC frame-commitment; multi-session / multi-person FRR + floor
re-estimation; enforced/observed ISI geometry; a real (non-gold-privileged) bot corpus.

17 fixture tests (CI-safe) + PV-CI 184. Zero spend; sealed FROZEN/PoAC untouched. Files still uncommitted (F12).
