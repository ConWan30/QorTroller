# POEP population reaction-time band — MEASURED, N=5 (Con+Fari+Khamari+Roy+Pookie) · 2026-07-19/20

**Candidate / advisory — gates nothing.** `poep_enabled` / `L6B` / `L6_CHALLENGES` stay **False**; zero spend;
no chain; no flag flip. The `l9_presence.population_band` estimator crossed from **PROVISIONAL** to **measured**
on real hardware — genuinely different people reacting to a live nonce-bound haptic R2 challenge on the
registered Edge (`581a836c…`). **This band is now the DETECTOR DEFAULT** (`GO_LO_MS=195`, `GO_HI_MS=416`,
`SUB_FLOOR_MS=120` in `scripts/poep_r2onset_adversarial.py`); the old single-operator `(320,400]`/sub=320
default flagged all five real players (medians 254–295 ms) as bots — see the FAR tradeoff below.

## Result — CURRENT band, N=5 (window [120, 450] ms — clean voluntary-reaction cluster)
- **Band: (195, 416] ms** · `degenerate_band: False` · **`PROVISIONAL: False`** (5 operators, each ≥ 20 samples).
- **Per-operator FRR (IN-SAMPLE): Con 0.0 / Fari 0.0 / Khamari 0.0 / Pookie 0.0 / Roy 0.043** (Roy's single
  431 ms kept sample sits just above the 416 ceiling — a p99 boundary effect on the moderate reactor).
- Joint (N,ISI) worst-case blind-bot FAR at the **default** (sub_floor = 120 ms anticipation): **≈0.069**
  (`worst_case_true_far()`); the single-op reference on the SAME band (sub = go_lo) is **≈0.042**. A wider band
  + a lower sub-floor RAISE the single-shot FAR (F4); K-compounding + more challenges LOWER the per-session
  FAR below this single-shot worst case, but the residual stays well above the strict single-op FAR — the
  honest cost of not false-rejecting fast humans.

| operator | n (windowed) | min | median | max | note |
|---|---|---|---|---|---|
| Con     | 41 | 228 | 295 | 405 | fast |
| Fari    | 25 | 213 | 263 | 365 | fast |
| Khamari | 25 | 203 | 254 | 346 | fast |
| Pookie  | 25 | 228 | 272 | 349 | fast |
| Roy     | 23 | 246 | 288 | 432 | **moderate** — one 457 ms reaction dropped by the [120,450] window (live-verify itself flagged it too-slow); the kept 431 ms is above the 416 ceiling → Roy in-sample FRR 0.043 |

Total 139 pooled reactions, 5 operators. `poep_population_band.py --players Con,Fari,Khamari,Roy,Pookie --min-ms 120 --max-ms 450`.

**Fit history (all stable — folding new people in barely moved it):** N=2 (Con+Fari) (202,410] 66 samples
FAR 0.060 → N=3 (+Khamari) (192,404] 91 samples → N=5 (+Roy moderate +Pookie fast) **(195,416]** 139 samples.
Roy raised the ceiling (his 431 ms > the N=3 404). Each person folded in was scored held-out first (below;
3 clean passes + Roy a partial miss), then became in-sample.

## Held-out validation (the real generalization tests) — 4 EXERCISES (3 clean passes + Roy a partial miss)
Scored via `poep_population_band.py --players <label> --min-ms 120 --score-band <frozen band>` (held-out mode:
`frr_for_band` against the FROZEN band, NOT a re-fit). Held-out numbers, unlike the in-sample FRR above —
the scored reactions never touched the fit.

Each was scored held-out FIRST (against the then-frozen band), which justified folding them in; they are then
**in-sample** on the current N=5 fit (do not read the N=5 in-sample FRR as held-out).
1. **Cross-session (Con):** fresh `ConHeldout` (25/25 PASS, 202–305 ms) vs the frozen N=2 (202,410] → **25/25
   in-band, FRR 0.0**. Not overfit to Con's first session.
2. **Cross-person (Khamari):** a person never used to fit (25/25 PASS, 203–346 ms) vs (202,410] → **25/25
   in-band, FRR 0.0**. Generalizes to a new person.
3. **Cross-person (Pookie):** a new person never used to fit (25/25 PASS, 227–349 ms) vs the frozen N=3
   (192,404] → **25/25 in-band, FRR 0.0**. Another fast reactor, fully covered.
4. **Cross-person (Roy) — the FIRST partial miss (breadth signal):** a moderate reactor (23/25 PASS after
   dropping a 16.6 ms false-start, 246–457 ms) vs the frozen N=3 (192,404] → **22/24 in-band, FRR 0.083**
   (below=0, **above=2**: his 431 and 457 ms both exceed 404). Folding Roy in raised the ceiling 404→416 to
   cover most of him; his 457 ms (a live-verify-flagged too-slow) stays out, leaving in-sample FRR 0.043.

**What is now proven:** **4 held-out exercises across 4 people** (ConHeldout cross-session + Khamari + Pookie
+ Roy cross-person) on the N=5 fit; the ceiling **stretched** to a moderate reactor (Roy). (Fari has no
separate held-out score as a new person — she is in-sample only; do not count her as a held-out person.)
**Scope (operator decision 2026-07-20):** the target population is **competitive players**, who are
fast-to-moderate reactors (reaction time is a selected trait in competitive play) — so the (195,416] band
**targets the intended population, not a convenient subset.** A genuinely **slow** reactor (~450–600 ms) is
**out of scope by design**; if one plays they are handled gracefully — `SOFT_TOO_SLOW` (retry), **never
false-flagged as a bot** (FRR-safe by construction). The one honest coverage note: a reactor whose reactions
*all* exceed 416 ms would be *un-verifiable* (stuck `INSUFFICIENT`, not falsely-bot) — accepted, as they are
outside the competitive-player scope. **Still true within scope:** N=5 is a *small* sample of competitive-class
reactors; the band widens/re-fits if that scope's distribution is later found broader.

## Provenance
- Live capture: `scripts/poep_live_capture.py --player <Con|Fari> --count 25 --mode pulse --no-store` on the
  registered Edge over USB (silent, nonce-scheduled unpredictable R2 **pulse** buzz; react → grip/R2 tap;
  read-at-fire gold device-clock t0).
- Con's clean run: **25/25 LIVE-VERIFY PASS**, all `class=HUMAN`, 227–339 ms. Fari's run: **25/25 PASS**,
  213–365 ms. Con's pooled n=41 also includes windowed in-band reactions from his earlier warm-up sessions.
- Pooled via `scripts/poep_population_band.py --players Con,Fari,Khamari,Roy,Pookie --min-ms 120 --max-ms 450` (the N=5 fit; the original N=2 used `--players Con,Fari`).
- Raw capture files (`audits/poep_live_capture_*.json`) are **gitignored** (biometric-adjacent, public repo)
  and are **NOT** committed — only these derived latency statistics are.

## Honest ceiling (load-bearing)
- **N=5** (the `MIN_OPERATORS_FOR_POPULATION=2` gate is well cleared) but still a **small** sample of
  **fast-to-moderate** reactors (medians 254–295). The band widens/validates as more (esp. slower) people are
  sampled; it is the *current* measured band, not a frozen canonical constant.
- The **120 ms anticipation sub-floor is a conservative UNCITED prior**, not a measured floor.
- **The per-operator FRR in the Result table is IN-SAMPLE** (fraction of the *same* pooled reactions that
  defined the band falling outside it — ≈0 partly by construction). The **held-out** generalization tests
  (separate, real) are the 4 exercises in the Held-out section above; do not conflate the two.
- The pre-technique warm-up misses (470–694 ms LIVE-VERIFY FAILs) were **excluded by the [120,450] window** —
  they are "missed the buzz, reacted to the tail," not clean voluntary reactions; letting them define the
  band inflated the ceiling to 678 ms and the FAR to 0.24 (the untightened [120,800] pool).
- Candidate/advisory: emits a band, **gates nothing**.

## Field note (why the buzz was "dead" for an hour)
The actuator was fine the whole time. Two things: (1) **use `--mode pulse`, not rigid** — pulse *vibrates*
(felt at rest, like rumble); rigid resistance is only felt on a hard R2 pull and reads as "dead." (2) Keep
**light pressure on R2** so the pulse transmits through the trigger. A lightbar+rumble+trigger probe confirmed
the output path was healthy and isolated it to the mode. See `docs/poep-population-band-rig-runbook.md`.
