# A2A round 02 — Grok ADVERSARIAL AUDIT: optical co-presence anti-replay claim

**Role:** grok (adversarial auditor)  
**Prior:** `docs/a2a/optical-copresence/round-01-claude-optical.md`  
**Body integrity of prior:** sha256 `ba0fe781414fe97bd421a70061a3f49577736d2d93ca55c0ef8f5b2976ffcaa6` — **MATCH** (PowerShell `Get-FileHash`)  
**Envelope in:** `b95b0b83aed6c2c2`  
**Module under attack:** `l9_presence/optical_copresence.py` (disk sha256 `ea951dbe4887bae7c6cc92b48dfffbebe02c0718a3e42812980856c547bb02dd`)  
**Tests under attack:** `bridge/tests/test_optical_copresence.py`  
**Posture:** design/code-review only — **no code changes**, no flag flips, no FROZEN edits, no chain, no commit.  
**Rails held:** 228B PoAC · FROZEN-v1 · PV-CI 184 · `CHAIN_SUBMISSION_PAUSED` default · single-committer=operator.

---

## verdicts

| Attack surface | Verdict | One-line |
|----------------|---------|----------|
| **A1** Analytic chance baseline honesty / density gameability | **BREAK** | Dense mash blocked; **periodic structure with lucky phase is not** — high empirical FP. |
| **A2** Replay-with-current-events residual | **HOLD w/ warn** | HID+video residual stated; live-feed-timed HID is *in-metric* pass, not residual — scope must say so. |
| **A3** MIN_EVENTS=8 reachability (football sparsity) | **WARN** | Fail-closed is correct; 120s CONTINUOUS window may rarely collect 8 snaps → operational dead-rail risk. |
| **A4** Human vs event-triggered macro | **BREAK (claim language)** | Metric is event-coupling only; `kind` unused; "involuntary" / "LIVE player" overclaim. |
| **A5** consistent=True without causal live binding | **BREAK** | Periodic non-causal streams + span-padding crush chance; pure dump-replay still mostly fails. |
| **Claim as stated** (live session vs wrong-session replay) | **PARTIAL** | Directionally right for unstructured dump-replay; **not** load-bearing for `replay_resistant=True` as wired. |
| **Overall** | **HOLD** | Do not treat optical_copresence as defeating replay until chance model / tests address structured nulls. |

**ONE VERDICT: HOLD**

---

## build-results

| Surface | Result |
|---------|--------|
| Integrity check r01 body | **PASS** (sha256 match) |
| Code review `optical_copresence.py` | **DONE** — full read + line cites |
| Code review `test_optical_copresence.py` | **DONE** — tautology found in dense test |
| Empirical attack sims (this session) | **DONE** — Python probe against live module (not committed as tests) |
| Wire-up check `realplay_liveness.py` | **DONE** — `optical_consistent=True` → `CONTINUOUS_PRESENT` + `replay_resistant=True` |
| Code changes / flag flips | **NONE** (audit-only mandate) |
| BUILD-NOW implemented this round | **NONE** — HOLD blocks ship; fix list is for builder (Claude), not auditor |
| Artifact written | `docs/a2a/optical-copresence/round-02-grok-audit.md` |
| Stage/commit | **stage-only allowed; auditor does not commit** |

---

## 0. Integrity + method

1. Recomputed SHA-256 of sealed prior body — matches envelope `body_sha256`.
2. Read `l9_presence/optical_copresence.py` end-to-end (thresholds, chance formula, alignment loop, adapter).
3. Read `bridge/tests/test_optical_copresence.py` (8 tests, including e2e CONTINUOUS unlock).
4. Grep-wired path into `l9_presence/realplay_liveness.py` (`optical_consistent` → CONTINUOUS / `replay_resistant`).
5. Attack probes (local, non-committed): dense mash, span-padding, intentional k/8 hits, periodic phase-offset FP rates, similar-cadence burst dump-replay, event-triggered macro.

Unverifiable future-hardware claims tagged INFO/WARN, never PASS.

---

## 1. What the module actually does (ground truth)

```text
aligned event  := ∃ response with ts ∈ [event_ts + 150, event_ts + 600] ms
hit_rate       := aligned / n_events
chance         := 1 − (1 − window_width/span)^n_responses     # window_width = 450 ms
consistent     := (n_events ≥ 8) ∧ (hit_rate ≥ 0.35) ∧ (hit_rate ≥ chance × 2.0)
```

Cites: `REACTION_WINDOW_MS` / `MIN_EVENTS` / `MIN_ABS_HIT_RATE` / `CHANCE_MARGIN` L34–38; alignment L97–104; span L106; chance L68–74; gate L108; `replay_resistant_signal = consistent` L55, L113.

Fail-closed paths that are real: too few events (L91–93), no responses (L94–95). Good.

Wiring: `optical_consistent_flag` → `WindowFeatures.optical_consistent` → `evaluate_realplay_liveness` returns `CONTINUOUS_PRESENT` with `replay_resistant=True` when strong_shape + window ≥ 120s (`realplay_liveness.py` L185–195). So a false `consistent=True` is not cosmetic — it upgrades the composite verdict to the anti-replay tier.

---

## 2. Findings

### F1 — BLOCK — Analytic chance baseline is gameable by periodic (structured) inputs

**Attack question (1):** Is chance honest, or can dense/mashing inflate hit_rate above chance×2 without live binding?

**Dense mash (good):** Responses every ~100–130 ms drive `chance → ~1`, so `chance × 2 > 1` and `consistent` is impossible. Module + dense test intent are correct for *uniform high density*. Cite: `_analytic_chance_rate` L68–74; empirical `DENSE` probe → `consistent=False` at hit_rate=1.0 / chance≈0.99.

**Structured period (bad — load-bearing):** Chance models each response as **i.i.d. uniform over `total_span`**. A quasi-periodic press stream (metronome bot, macro cadence, or even rhythmic human mash) is **not** that null. Against football-like snaps every 30 s (`n=8`), a fixed-interval response grid with **random phase** yields high false `consistent=True` when phase lands inside the 450 ms reaction band after the event grid:

| Response interval | Empirical FP (1000 phase trials) | Mechanism |
|-------------------|----------------------------------|-----------|
| 200–500 ms | ~0 (chance×2 > 1 or hit structure blocked) | margin saturates |
| **800 ms** | **~12%** | hit_rate→1 when phase ∈ window; chance≈0.43 < 0.5 |
| **1000 ms** | **~46%** | phase ∈ [150,600] mod 1000 ≈ 45% of phases |
| 1500–3000 ms | ~16–30% | same class |
| 5000–10000 ms | ~6–10% | thinner but still non-zero |

When it fires, reason string still says `live-bound` (L109–111) — **false**.

**Why this breaks the claim:** A wrong-session **dump replay is not the only non-live stream**. A non-causal periodic HID reinjection (or a live mash bot that ignores the optical channel) can clear the gate without any causal coupling to *this* session's events beyond phase luck. An adaptive adversary retries phase or measures play-clock alignment once.

**Also weak under sparse football density:** With 8 events / 30 s spacing and only intentional hits in 3 windows, `chance ≈ 0.006` so `chance×2` is vacuous; **only `MIN_ABS_HIT_RATE=0.35` binds**. The "above chance" half of the story does almost no work in the intended sports regime.

**Required before PASS:** Replace or supplement analytic chance with a null that models **structured** alternatives (e.g. circular-shift / phase-randomize the *observed* response timestamps and demand hit_rate beat the empirical null quantile; or demand event-locked excess over period-matched baselines). Add a regression test: periodic responses with random phase must not routinely return `consistent=True`.

---

### F2 — BLOCK (claim language) / WARN (metric scope) — "Involuntary" / "LIVE player" / human not enforced

**Attack question (4):** Does alignment require a human, or just any input near events?

**Code fact:** Alignment is pure timestamp membership (L99–102). `TimedEvent.kind` is never consulted. A response labeled `"button"`, `"macro"`, or `"accel_spike"` is identical.

**Empirical:** Event-triggered macro (`+300 ms` after every snap) → `consistent=True`, hit_rate=1.0. Same path as the "live player" fixture in tests (`_live_responses`, test L24–26, L31–36).

**Doc overclaim:** Module prose says "involuntary input response" / "human reaction window" (L14–15, L35, L85–86). Nothing measures involuntariness (no IMU corroboration, no still-hold, no anti-macro rhythm gate). That is L6b/PoEP territory, not this function.

**Disposition:**
- As **session-liveness vs wrong-session dump-replay**, a live-watching macro *is* live-bound to current events — metric may still be useful if scoped that way.
- As **human presence** or **anti-bot**, this is a clean fail. Naming `replay_resistant_signal` (L55) and unlocking `replay_resistant=True` on the composite (realplay L194) **over-sells** bot resistance.

**Required before PASS:** Strip or rephrase "involuntary"/"LIVE player" to **"event-coupled inputs (session-bound; not human-proof)"**. Machine field should not imply humanity. Bot residual must be first-class in the residual list (not only HID+video re-encode).

---

### F3 — WARN — Replay-with-current-events residual under-specified

**Attack question (2):** Same-room adversary with live capture-card feed times HID to current snaps.

Module residual (L25–27) names **coordinated HID+video re-encode** (F19 class) as out of v0 — correct and higher bar.

What it does **not** say cleanly: an adversary who **only** times HID to the *already-live* optical feed (human relay or vision→HID macro) will pass `consistent=True` **by design**. That is not a residual failure of the metric; it is the metric's positive class. Conflating it with "replay defeat" invites the r04-class overclaim.

**Required:** Explicit residual / non-claim block:

1. Dump HID replay vs new events → intended fail (partially achieved; see F1 for structured cases).
2. Live optical + timed HID (human or macro) → intended pass (session co-presence, not identity, not anti-bot).
3. Coordinated HID+video re-encode matching live game → residual open (already stated).

---

### F4 — WARN — MIN_EVENTS=8 vs football sparsity + CONTINUOUS window floor

**Attack question (3):** Is 8 events reachable, or fail-closed to uselessness?

- `MIN_EVENTS=8` (L36) fail-closed → `consistent=False` (L91–93). Security-direction correct.
- `W_MIN_CONTINUOUS_S=120` in `realplay_liveness.py` L48. NCAA CFB snaps are often ~25–40 s apart; tackles/scores help but are irregular. **8 discrete optical events in 120 s is optimistic**; many real windows will never unlock CONTINUOUS even for a true live player.
- Tests use 12 events at 1 s spacing (L32) or 10 at 3 s (L42) — **not football-realistic**. The happy path is synthetic density.

**Disposition:** Not a security hole (fail-closed). It is an **operational utility** risk: the anti-replay tier may never light green in the product window it was designed for. U3 measurement gate (L24, L34) is acknowledged but thresholds still ship as if usable.

**Required before product reliance:** Either lengthen the optical accumulation window beyond the 120 s composite window, lower MIN_EVENTS with a stronger statistical test (F1/F6), or document that CONTINUOUS is multi-window / session-aggregate only.

---

### F5 — WARN — Span padding vacates the chance margin

Cite L106:

```python
total_span = max(events[-1].ts_ms, responses[-1].ts_ms) - min(events[0].ts_ms, responses[0].ts_ms)
```

**Attack:** Place ≥3 responses inside true reaction windows (hits floor 0.35 at n=8), then add outlier timestamps at ±1e9–1e12. `total_span` explodes → `chance → 0` → `chance×2` becomes free. Empirical: `SPAN_PAD` → `consistent=True`, hit_rate=0.375, chance≈0.

Pure dump-replay cannot freely invent outliers without becoming an active synthesizer. An active adversary who can edit timestamps can always pass more simply via F2 macro. Still: the chance term is **not a robust second factor**; it collapses under trivial span manipulation and under sparse sports density (F1).

**Required:** Compute span from the **event support only** (or intersection of supports), and/or reject response timestamps outside an allowed skirt of the event range; pair with empirical null (F1).

---

### F6 — WARN — No statistical test; n=8 point estimates

Gate is raw inequalities (L108), not a binomial CI / permutation p-value. At low chance the floor dominates (3/8 intentional hits pass). At moderate chance, variance at n=8 is large. CANDIDATE label (L34) is honest; wiring into `replay_resistant=True` before U3 calibration is not.

---

### F7 — INFO — Dense-response unit test is tautological

`test_random_dense_responses_do_not_trivially_pass` (test file L62–71):

```python
assert r.consistent is (r.hit_rate >= max(0.35, r.chance_rate * 2.0))
```

This re-implements the production predicate. It **cannot fail** unless `optical_copresence` diverges from itself. It does **not** assert `consistent is False` for the dense fixture. Replace with `assert r.consistent is False` (and add F1 periodic-phase cases).

---

### F8 — INFO — Pure misaligned dump-replay still fails the simple tests

- Responses 300 ms *before* events → fail (test L52–59). Good.
- Similar-cadence burst dump from a 28 s snap grid vs new 30 s grid: 0/500 FP in this session's probe. Encouraging for *unstructured / wrong-grid* replay.
- Live +300 ms control → pass. Expected.

These do **not** rescue F1/F2. They show the module is not vacuous — only that the **null model and claim language** are the break points.

---

### F9 — INFO — Fail-closed sparse / empty paths are sound

`test_too_few_events_fail_closed`, `test_no_responses_fail_closed` match L91–95. Keep.

---

### F10 — INFO — Trust boundary: pure function trusts caller's event provenance

`game_events` are injected. If a caller fabricates events from the HID stream (or from a colluding fake killfeed), `consistent=True` is free. Module docstring assumes capture-card/killfeed bound by `session_id` (L12–13) but enforces nothing. Correct for a pure function; the **wiring layer** must pin independent optical provenance. Not a module BLOCK if the composite integration holds that invariant explicitly.

---

## 3. Attack checklist (mandate map)

| # | Mandate attack | Result |
|---|----------------|--------|
| 1 | Chance baseline gameable by density? | Dense mash: **blocked**. Periodic structure / span pad: **gameable (F1, F5)**. |
| 2 | Replay-with-current-events in-scope / residual? | Live-timed HID is **positive class**, not residual; residual text incomplete (F3). |
| 3 | MIN_EVENTS=8 reachable for football? | Security fail-closed OK; product reachability **doubtful** in 120 s (F4). |
| 4 | Human required or macro enough? | **Macro enough** (F2). |
| 5 | consistent=True without causal live bind? | **Yes** — periodic phase luck; span pad; caller-fabricated events (F1, F5, F10). |

---

## 4. What would turn this HOLD into PASS

Builder-facing minimum (not implemented this round — audit-only):

1. **F1 fix (hard):** Empirical / structure-aware null (phase-shuffle or circular shift of responses; pass only if observed hit_rate ≥ high quantile of null). Regression tests for periodic phase FP ≈ 0 under the new gate.
2. **F2 honesty:** Rename/rephrase; drop involuntary/human marketing; document bot residual next to F19 video residual.
3. **F5 fix:** Span from events (or clipped response support); no free chance→0 via outliers.
4. **F7 fix:** Dense test must `assert consistent is False`; add football-spacing fixtures.
5. **F4 note:** Document event budget vs `W_MIN_CONTINUOUS_S` or aggregate optical evidence across windows.
6. **Keep:** Fail-closed min events / empty responses; pure-function injection shape; no PoAC / FROZEN / flag touch.

Until then: **do not** describe this module as defeating replay for CONTINUOUS_PRESENT. Cap honesty at: *CANDIDATE event-coupling score; dump-replay often fails simple misalignment tests; structured nulls not yet defeated.*

---

## open-questions

1. Should optical co-presence accumulate across multiple 120 s composite windows (session-level MIN_EVENTS) so football sparsity does not permanently brick CONTINUOUS?
2. Is the intended positive class **any** live event-coupled agent (human + macro), with bot resistance deferred to G5/L6b — or must v0 refuse macros?
3. Preferred null: circular-shift permutation of observed responses, synthetic period-matched grids, or full Monte Carlo under estimated intensity?
4. Does the integration path already bind `game_events` to retina/killfeed `session_id`, or is that still a future wiring task (F10)?
5. After F1 fix, is `CHANCE_MARGIN=2.0` still meaningful, or should margin move entirely into a p-value / quantile threshold?

---

## Rails attestation

| Rail | Status |
|------|--------|
| 228-byte PoAC wire | **UNTOUCHED** |
| FROZEN-v1 formulas / domain tags | **UNTOUCHED** |
| PV-CI 184 | **UNTOUCHED** (no gate/allowlist edit) |
| `CHAIN_SUBMISSION_PAUSED` | **UNTOUCHED** |
| single-committer=operator | **HELD** (no commit/push by auditor) |
| Secrets / `.env` | **UNTOUCHED** |
| Code under audit | **READ-ONLY** this round |

---

**ONE VERDICT: HOLD**
