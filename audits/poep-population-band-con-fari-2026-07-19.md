# POEP population reaction-time band — FIRST MEASURED (Con + Fari) · 2026-07-19

**Candidate / advisory — gates nothing.** `poep_enabled` / `L6B` / `L6_CHALLENGES` stay **False**; zero spend;
no chain; no flag flip. This is the first time the `l9_presence.population_band` estimator crossed from
**PROVISIONAL** (framework + prior) to **measured** on real hardware — two genuinely different people reacting
to a live nonce-bound haptic R2 challenge on the registered Edge (`581a836c…`).

## Result (window [120, 450] ms — clean voluntary-reaction cluster)
- **Band: (202, 410] ms** · `degenerate_band: False` · **`PROVISIONAL: False`** (2 operators ≥ the
  `MIN_OPERATORS_FOR_POPULATION=2` gate, each ≥ 20 samples).
- **Per-operator FRR: Con 0.0 / Fari 0.0** (see in-sample caveat below).
- Joint worst-case single-shot blind-bot FAR (sub_floor = 120 ms anticipation): **0.060** vs the
  single-operator-band reference **3.2e-4**. A wider population band RAISES the single-shot FAR (F4); the
  anti-cheat strength is the **K=5 multi-challenge compounding**, not one shot.

| operator | n (windowed) | min | median | max |
|---|---|---|---|---|
| Con  | 41 | 228 | 295 | 405 |
| Fari | 25 | 213 | 263 | 365 |

Total 66 pooled reactions, 2 operators.

## Held-out validation (the real generalization tests) — BOTH PASSED
Scored via `poep_population_band.py --players <label> --min-ms 120 --score-band 202,410` (held-out mode:
`frr_for_band` against the FROZEN band, NOT a re-fit). Held-out numbers, unlike the in-sample FRR above —
the scored reactions never touched the fit.

1. **Cross-session (Con):** a fresh `ConHeldout` run (25/25 PASS, 202–305 ms) → **in-band 25/25, FRR 0.0**
   (below=0 above=0). The band is not overfit to Con's first session.
2. **Cross-person (Khamari) — the TRUE population test:** a THIRD person never used to fit (`Khamari`, 25/25
   PASS, 203–346 ms) → **in-band 25/25, FRR 0.0** (below=0 above=0). Identical against the precise
   (202.4, 409.6]. The band **generalizes to a new person** — it is a genuine population band, not a
   Con+Fari artifact.

**What is now proven:** cross-session stability + cross-person generalization across **3 distinct people**.
**What is STILL open — population BREADTH:** all three sampled people are **fast reactors** (medians 254–295;
all reactions inside 202–365 ms). The band has not yet seen a **slow** reactor — someone at ~400–600 ms would
land above the 410 ms ceiling. Generalization is validated *within the fast-reactor cluster*, not across the
full human reaction range. Widening to cover slower players requires capturing a slower reactor and re-fitting.

## Provenance
- Live capture: `scripts/poep_live_capture.py --player <Con|Fari> --count 25 --mode pulse --no-store` on the
  registered Edge over USB (silent, nonce-scheduled unpredictable R2 **pulse** buzz; react → grip/R2 tap;
  read-at-fire gold device-clock t0).
- Con's clean run: **25/25 LIVE-VERIFY PASS**, all `class=HUMAN`, 227–339 ms. Fari's run: **25/25 PASS**,
  213–365 ms. Con's pooled n=41 also includes windowed in-band reactions from his earlier warm-up sessions.
- Pooled via `scripts/poep_population_band.py --players Con,Fari --min-ms 120 --max-ms 450`.
- Raw capture files (`audits/poep_live_capture_*.json`) are **gitignored** (biometric-adjacent, public repo)
  and are **NOT** committed — only these derived latency statistics are.

## Honest ceiling (load-bearing)
- **N=2 is the MINIMUM** — a *minimal* population sample, not a robust one. Both Con and Fari are **fast
  reactors** (medians 263 / 295 ms); the band may not generalize to slower players until more operators are
  added. It widens/validates as N grows.
- The **120 ms anticipation sub-floor is a conservative UNCITED prior**, not a measured floor.
- **FRR here is IN-SAMPLE**, not held-out: it is the fraction of the *same* pooled reactions that defined the
  band (p1–p99) falling outside it — so ≈0 partly by construction. A real generalization test scores a *new*
  capture against this frozen band. Not done yet.
- The pre-technique warm-up misses (470–694 ms LIVE-VERIFY FAILs) were **excluded by the [120,450] window** —
  they are "missed the buzz, reacted to the tail," not clean voluntary reactions; letting them define the
  band inflated the ceiling to 678 ms and the FAR to 0.24 (the untightened [120,800] pool).
- Candidate/advisory: emits a band, **gates nothing**.

## Field note (why the buzz was "dead" for an hour)
The actuator was fine the whole time. Two things: (1) **use `--mode pulse`, not rigid** — pulse *vibrates*
(felt at rest, like rumble); rigid resistance is only felt on a hard R2 pull and reads as "dead." (2) Keep
**light pressure on R2** so the pulse transmits through the trigger. A lightbar+rumble+trigger probe confirmed
the output path was healthy and isolated it to the mode. See `docs/poep-population-band-rig-runbook.md`.
