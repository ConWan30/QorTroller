# A2A round 04 — Grok RE-VERIFY: optical co-presence F1/F2 fixes

**Role:** grok (adversarial auditor, re-verify)  
**Prior:** `docs/a2a/optical-copresence/round-03-claude-fix.md`  
**Body integrity of prior:** sha256 `a187741f08a883140d46d2b54aba95c1ea9ad5575477367fa5c957eade7a5f3e` — **MATCH** (PowerShell `Get-FileHash`)  
**Envelope in:** `b62b8c39e06d6f36`  
**Module under re-verify:** `l9_presence/optical_copresence.py` (disk sha256 `a5ec976e76d95f4878850f9c87b20aaaa25d4ad09cda9e6b7b01af971feeab63`)  
**Tests under re-verify:** `bridge/tests/test_optical_copresence.py` (disk sha256 `65b961a83405ed85d34ff3c90647cf2c26da3efd135aaf07c0fff827b37fee05`)  
**Posture:** design/code-review only — **no code changes**, no flag flips, no FROZEN edits, no chain, no commit.  
**Rails held:** 228B PoAC · FROZEN-v1 · PV-CI 184 · `CHAIN_SUBMISSION_PAUSED` default · single-committer=operator.

---

## verdicts

| Finding / attack surface | Prior | Re-verify | One-line |
|--------------------------|-------|-----------|----------|
| **F1** Analytic chance / periodic structure | BLOCK | **PARTIAL — residual BREAK** | Analytic uniform replaced; dense mash dies; **lucky-phase period-matched macros still FP**; regression fixture is unlucky-phase tautology. |
| **F2** Human / involuntary over-claim | BLOCK | **CLOSED** | `event_coupled` + `claim=session_co_presence_not_humanity`; involuntary/LIVE stripped; macro residual first-class. |
| **F3** Residual under-spec | WARN | **CLOSED** | Dump-replay fails (intended); live-optical+timed HID passes by design — stated in module docstring. |
| **F4** MIN_EVENTS=8 vs football sparsity | WARN | **ACK (open operational)** | Code comments multi-window aggregate; still U3-gated dead-rail risk on one 120s window. |
| **F5** Span padding vacates margin | WARN | **CLOSED (intent)** | Span from response support only; padding no longer shrinks an analytic chance term (chance term removed). |
| **F6** No statistical test | WARN | **IMPROVED, not closed** | Empirical null quantile is a real test; **implementation corrupts the null** (see F8). |
| **F7** Tautological dense test | INFO | **PARTIAL** | Dense now asserts `event_coupled is False`; **new periodic test is a different tautology** (phase outside window → hit_rate=0). |
| **F8 NEW** Circular modulus collapse | — | **BREAK** | `r_span = last−first` on regular grids → first/last collide under `% r_span` (n→n−1 unique); null demoted; props up 3s locked tests and residual FP. |
| **F9 NEW** Discrete `real > null_q` fragility | — | **WARN** | With hit rates on 1/n lattice, `null_q=(n−1)/n` and `real=1` always clears strict `>`; not a calibrated α-level test. |
| **F10 NEW** Fixture regime ≠ football | — | **WARN** | Tests use 3s event spacing; pure phase p≈0.10 for true lock (would fail α=0.05). Football ~30s pure phase p≈0.015 (OK). |
| **Claim (dump-replay vs this-session coupling)** | PARTIAL | **MOSTLY HELD** | Wrong-session dump / phase-offset similar-cadence → not coupled (probed). Residual non-causal metronome FP remains. |
| **Wiring risk** (`optical_consistent`→CONTINUOUS/`replay_resistant`) | load-bearing | **UNCHANGED** | Still upgrades composite; false `event_coupled` still not cosmetic. |

**ONE VERDICT: HOLD**

Do **not** treat F1 as closed or `replay_resistant=True` as load-bearing on this module until: (1) circular null is structurally correct, (2) lucky-phase periodic is regression-tested honestly, (3) test event spacing matches the operational football regime or thresholds are re-justified for 3s fixtures.

---

## build-results

| Surface | Result |
|---------|--------|
| Integrity check r03 body | **PASS** (sha256 match) |
| Integrity prior r02 | noted (not re-hashed this round; chain via envelope prior field) |
| Code review `optical_copresence.py` | **DONE** — full read; null loop L122–131; gate L133–137; claim L59–69 |
| Code review `test_optical_copresence.py` | **DONE** — 9 tests; periodic fixture audited |
| `pytest bridge/tests/test_optical_copresence.py -v` | **9 passed** in 0.30s |
| Empirical attack suite (this session, non-committed) | **DONE** — dense, period-ratio, same-cadence phase sweep, football 30s, wrap collision, pure-phase p-values, cross-session dump, busy-HID, double-in-window |
| Wire-up `realplay_liveness.py` | **DONE** — L186–195 unchanged: `optical_consistent is True` + strong_shape + window≥120s → `CONTINUOUS_PRESENT` + `replay_resistant=True` |
| Code changes / flag flips | **NONE** (re-verify mandate: code-review only) |
| BUILD-NOW implemented this round | **NONE** — HOLD; fix list is for builder (Claude), not auditor |
| Artifact written | `docs/a2a/optical-copresence/round-04-grok-reverify.md` |
| Stage/commit | **stage-only allowed; auditor does not commit** |

---

## 0. Integrity + method

1. Recomputed SHA-256 of sealed r03 body — matches envelope `body_sha256`.
2. Read fixed `optical_copresence.py` end-to-end (empirical null, `event_coupled`, claim language, F4/F5 comments).
3. Read `test_optical_copresence.py` (9 tests) and ran full file green.
4. Confirmed wiring still load-bearing in `realplay_liveness.py`.
5. Attacked the **empirical null itself** (mandate): period-ratio FP, same-cadence phase luck, circular wrap collision, pure-phase p-value comparison, response-span normalizer, cross-session dump.

Unverifiable future-hardware / live-optical capture claims tagged INFO/WARN, never PASS.

---

## 1. What the module does now (ground truth)

```text
aligned event  := ∃ response with ts ∈ [event_ts + 150, event_ts + 600] ms
hit_rate       := aligned / n_events
r_span         := responses[-1] - responses[0]          # response support only (F5)
null[k]        := hit_rate(events, circular_shift(responses, k/(N+1)*r_span)), k=1..64
null_q         := quantile(null, 0.95)
null_med       := quantile(null, 0.5)
event_coupled  := (n_events ≥ 8)
                 ∧ (hit_rate ≥ 0.35)
                 ∧ (hit_rate > null_q)
                 ∧ (hit_rate ≥ null_med + 0.15)
```

Cites: thresholds L36–42; `_hit_rate` L72–81; `_quantile` L84–89; span L116–120; null loop L122–131; gate L133–137; `to_dict` claim L69; adapter L146–154.

Fail-closed retained: too few events, no responses, degenerate `r_span≤0`. Good.

**Honest positive class (F2 — accepted):** session co-presence / event-coupling, including event-triggered macros. Not humanity, not anti-bot.

---

## 2. Disposition check (builder claims vs disk)

### F2 BLOCK → CLOSED ✓

- Field renamed `consistent` → `event_coupled`.
- Docstring + `to_dict()["claim"] == "session_co_presence_not_humanity"`.
- No "involuntary" / "LIVE player" in module surface.
- Macro/relay residual is explicit non-claim (L10–17).
- Tests: `test_flag_adapter_and_claim_language` pins claim string.

### F3 WARN → CLOSED ✓

- Dump of other session / preceding responses: not coupled (test + probe).
- Live-feed-timed HID: **passes by design** (probe `ET_MACRO` → `event_coupled=True`); documented, not sold as residual anti-bot.

### F4 WARN → ACK only (still open operationally)

- Comment L37–38 acknowledges multi-window aggregate.
- No code path implements session-aggregate yet. CONTINUOUS window may still starve at 8 snaps. U3 remains correct gate.

### F5 WARN → CLOSED (intent) ✓

- Analytic chance gone; no `window/span` term for an adversary to inflate.
- `r_span` from responses only (L116–118). Padding a far dummy response does not resurrect the old chance game (probe: periodic+pad still not coupled).
- **Caveat:** `r_span` is still the circular modulus — see F8 (different bug class than padding).

### F6 WARN → IMPROVED, not closed

- Quantile null is a real statistical object (better than `chance×2`).
- Corrupted by F8 + F9; not yet a defensible α-level test.

### F7 INFO → PARTIAL

- Dense test now asserts `event_coupled is False` ✓.
- Periodic regression (below) is a **new** tautology ✗.

### F1 BLOCK → PARTIAL / residual BREAK ✗

Builder replaced analytic chance with circular-shift null and added two regressions. That is real progress. It does **not** fully close F1:

| Probe | Result |
|-------|--------|
| Dense mash (200 ms) | `event_coupled=False` ✓ |
| Dump / responses precede events | False ✓ |
| Cross-session similar cadence (30s, +5s phase) | False ✓ |
| Event-locked (3s fixture / 30s football) | True ✓ under *current* null |
| Same-cadence periodic, **unlucky** phase (e.g. 50 ms) | False — **and hit_rate=0** (trivial) |
| Same-cadence periodic, **lucky** phase ∈ [150,600] on 3s grid | **True FP ~14% of phases (9/64)** |
| Mid periods (800–10000 ms) vs 30s events | residual FP **~6–8%** of phases |
| Same-period 30s macro vs 30s events | FP **~2%** ≈ geometric window/period |

**Regression fixture audit (load-bearing):**

```text
test_periodic_macro_not_flagged_by_empirical_null:
  events @ 0, 3000, 6000, ...
  macro  @ 50, 3050, 6050, ...     # phase=50 ∉ [150,600]
  → hit_rate = 0.0 → event_coupled=False for any non-broken gate
```

This does **not** exercise the attack F1 was about (periodic structure with **lucky phase**). Lucky phases 200–500 ms on the same fixture all return `event_coupled=True` under the current module. The test name overclaims.

---

## 3. Attack the empirical null (mandate)

### 3.1 Can a periodic macro still beat it?

**Yes, at non-trivial rates**, for two layers:

**Layer A — inherent phase coincidence (scope-honest residual).**  
If response period equals event period and phase lands in the 450 ms reaction band, the stream is *mathematically identical* to an event-locked grid. A phase-structure null **cannot** separate “causal reaction” from “period-matched luck.” Under F2’s claim (co-presence, not humanity) this is partly **in-class**: the HID stream is coupled to this session’s event *grid*. For football ~30s snaps, geometric luck ≈ 450/30000 ≈ 1.5% (probe ~2%). Sticky once aligned if both clocks are metronomic.

**Layer B — implementation artifact (not OK).**  
Mid-period macros (e.g. 1 s presses vs 30s snaps) show ~6–8% FP. Pure phase-shift nulls give p≈0.45 for those lucky phases (should **fail** α=0.05). Current circular null drops `null_q` to ~0.917 via wrap distortion, so `real=1 > null_q` passes. **That is a bug, not a philosophy.**

### 3.2 Is response-support span the right normalizer?

**As F5 anti-padding: yes.** Adversary cannot inflate span to crush a chance term that no longer exists.

**As circular-shift modulus: only if the period is the true process period.** Current code uses:

```text
r_span = responses[-1] - responses[0]   # = (n−1) × mean_ISI for a regular grid
shifted = r0 + ((r − r0 + off) % r_span)
```

For n regularly spaced responses with spacing P:

```text
r_span = (n−1)·P
(r_last − r0) % r_span = 0  → last collapses onto first after any shift
→ n unique timestamps become n−1
```

**Empirical proof (this session):** 12-point 30s grid → after shift, `len(set(shifted)) == 11` with a duplicated first sample. Null structure is not the observed structure.

**Consequence:**

- Null hit-rates are systematically demoted (3s locked: null mostly 0 or 0.917, never a clean full-grid 1.0 mass).
- `real=1 > null_q=0.917` becomes an easy bar — **props up both true locks and lucky periodic FPs**.
- Paradox: a *correct* pure-phase null at q=0.95 on the **3s test fixture** would set `null_q=1.0` often enough that **true event-lock would fail** (`real > 1` impossible). Pure-phase p-value for 3s lock ≈ **0.10** (fails α=0.05); for 30s football lock ≈ **0.015** (passes). The green tests are calibrated to a **buggy null + unrealistic event spacing**, not to a football-regime α-level test.

So: response-support span is the right *family* of normalizer, but **`(last−first)` is the wrong circular period** for grid-like response trains. Prefer `n/(n−1)·(last−first)` or mean ISI × n, and prefer **p = fraction(null ≥ real) < α** over discrete `real > q95` when hit rates live on a 1/n lattice (F9).

### 3.3 Other probes (sensitivity / edges)

| Probe | Outcome |
|-------|---------|
| Jittered locks (σ≤120 ms, 30s events) | Coupled 30/30 — good power in football regime |
| Busy HID (lock + mid-play presses, 30s) | Coupled — good (earlier 3s “lock+filler” fail was period-matched filler poison) |
| Double response both in window (3s) | **False negative** (`hit=1, null_q=1`) — WARN sensitivity |
| Every-other-event lock (3s) | Coupled at hit=0.5 — floor+excess can pass on half-rate |
| Window edges 150/600 | Count as hits; lag 149/601 miss — consistent |
| Degenerate single / zero-span multi | Fail-closed ✓ |

---

## 4. NEW findings

### F8 — BREAK — Circular modulus collapses regular response grids

**Site:** L118–129 (`r_span = responses[-1]-responses[0]` then `% r_span`).  
**Effect:** null is not a faithful phase ensemble of the observed structure; lowers `null_q`; residual FP + fixture green via artifact.  
**Required before PASS:** fix circular period; add unit assertion that regular grids retain n unique points after shift; re-run period-ratio FP table with target FP≈0 for mid periods under α=0.05.

### F9 — WARN — `real > null_q` on discrete hit-rate lattice

With n_events=12, rates ∈ {0, 1/12, …, 1}. If max corrupted-null is 11/12, any perfect real clears strict `>`. Prefer p-value or `real >= null_q + margin` with calibrated margin, and report `null_p` in `to_dict`.

### F10 — WARN — Test regime (3s) ≠ operational football (~25–40s)

3s spacing makes window fraction 15% of period — weak separability for pure phase tests. Either:

- move positive/negative fixtures to ~30s event spacing, **or**
- document that U3 calibration will retune `NULL_QUANTILE` / `NULL_MIN_EXCESS` / `MIN_EVENTS` for the real snap process,

and stop treating 3s greens as evidence the football claim is calibrated.

### F11 — INFO — Adapter name lag

`optical_consistent_flag` / `WindowFeatures.optical_consistent` still say “consistent” while semantics are `event_coupled`. Not a correctness break; rename is hygiene to prevent re-overclaim at call sites.

---

## 5. What closed cleanly (credit)

1. **F2 claim language** — best part of the fix; prevents the r02 “LIVE/involuntary” overclaim from re-entering via reason strings (`session-coupled (not human-proof)`).
2. **Dense mash** — empirical null kills density without the old analytic saturation story.
3. **Wrong-session dump** — still fail-closed; cross-session similar cadence with phase offset failed in probe.
4. **Explicit bot residual** — macros timed to live events are positive class; composite G3–G5 remain the human-shape layer (wiring still requires strong_shape for CONTINUOUS).
5. **Determinism** — systematic shifts, no RNG; good for auditability.

---

## 6. BUILD-NOW (for builder — not implemented this round)

Audit-only re-verify: **no code changes from grok.** When builder resumes:

1. **Fix circular period** so regular grids do not collapse under shift; prove with a unit test (`len(set(shifted)) == n` for synthetic grids).
2. **Replace or supplement** `real > null_q` with p-value `mean(null_i >= real) < α` (α CANDIDATE, U3), expose `null_p` in result/`to_dict`.
3. **Rewrite** `test_periodic_macro_not_flagged_by_empirical_null` to use **lucky** phase ∈ reaction window (and ideally mid periods 800–3000 ms vs sparse events); assert `event_coupled is False` **or** explicitly document period-matched lock as in-class and test only non-matched periods.
4. **Align fixtures** with football-like event spacing (~25–40s) for the load-bearing positive/negative pair, keep a short-spacing stress case if desired but don’t let it be the only green path.
5. Optional hygiene: rename adapter/`optical_consistent` → `event_coupled` through `realplay_liveness` with a compatibility alias.

Until 1–3 land, **HOLD**.

---

## open-questions

1. **Operator claim target:** Is optical co-presence allowed to accept period-matched coincidence (~1–2% sticky FP at football spacing) as “session co-presence,” or must FP≈0 against all non-causal metronomes? F2 text suggests the former; `replay_resistant` naming suggests the latter. **Needs one sentence of product scope.**
2. **U3 measurement:** What is the empirical distribution of snap intervals + human reaction lags in NCAA CFB capture logs? Thresholds (`MIN_ABS_HIT_RATE`, `NULL_QUANTILE`, `NULL_MIN_EXCESS`, `MIN_EVENTS`) remain CANDIDATE until then.
3. **Aggregation for F4:** Will `MIN_EVENTS=8` be satisfied by multi-window merge before CONTINUOUS tiering, or will CONTINUOUS stay rare in sparse football?
4. **Double-tap / dense-in-window humans:** Is the double-in-window false negative acceptable, or does the null need a response-thinning pre-step (one response per event window max)?
5. **Rename wave:** When should `optical_consistent` be renamed across realplay + frontend to match `event_coupled`?

---

## rails checklist

| Rail | Status |
|------|--------|
| 228B PoAC wire | **untouched** |
| FROZEN-v1 formulas | **untouched** |
| PV-CI 184 | **not run** (no invariant-surface edit; review-only) |
| `CHAIN_SUBMISSION_PAUSED` | **not flipped** |
| single-committer=operator | **held** (no commit/push) |
| Secrets | **none** |
| Flag flips (`poep_enabled` / `L6B_ENABLED` / etc.) | **none** |

---

**ONE VERDICT: HOLD**

F2/F3/F5 claim and density story are in good shape. F1 is **not** honestly closed: lucky-phase periodic residual FP + circular modulus collapse + tautological periodic regression. Next builder round should fix the null mechanics and re-open re-verify; do not wire this as load-bearing `replay_resistant` evidence until then.
