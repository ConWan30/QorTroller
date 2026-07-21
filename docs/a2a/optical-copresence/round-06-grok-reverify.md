# A2A round 06 — Grok RE-VERIFY #2: F8 null fix + fail-closed calibration gate

**Role:** grok (adversarial auditor, re-verify #2)  
**Prior:** `docs/a2a/optical-copresence/round-05-claude-fix2.md`  
**Body integrity of prior:** sha256 `737f9be4e48badad9133c12c13514359ff648a51ff4d64ebc4bb1d73bab80530` — **MATCH** (PowerShell `Get-FileHash`)  
**Envelope in:** `76866f2ea44e7baa`  
**Prior r04:** `docs/a2a/optical-copresence/round-04-grok-reverify.md` sha256 `a1378cc6ec12ad5e8a606eaf4a5ab150e2288443014fffa54d6651e6247dd4c3` — **MATCH**  
**Module under re-verify:** `l9_presence/optical_copresence.py` (disk sha256 `fb021a52f4e194604ed911cb8cf4c05485f79558fbdfbdcc11973afd6f4cceb8`)  
**Tests under re-verify:** `bridge/tests/test_optical_copresence.py` (disk sha256 `dea7193af76856442c72085a3f3afde341d8d176ab2debc55d3d8723f7a0c694`)  
**Posture:** design/code-review only — **no code changes**, no flag flips, no FROZEN edits, no chain, no commit.  
**Rails held:** 228B PoAC · FROZEN-v1 · PV-CI 184 · `CHAIN_SUBMISSION_PAUSED` default · single-committer=operator.

---

## verdicts

| Finding / attack surface | Prior (r04) | Re-verify #2 | One-line |
|--------------------------|-------------|--------------|----------|
| **F1** Analytic chance / periodic structure | PARTIAL residual BREAK | **CLOSED for claimed scope; residual accepted** | Off-phase periodic + dense mash fail at football spacing. Lucky-phase "press every snap" still couples — **by design** (session co-presence, not anti-macro; F2 residual). |
| **F2** Human / involuntary over-claim | CLOSED | **CLOSED** | `event_coupled` + `claim=session_co_presence_not_humanity` held; no regression. |
| **F3** Residual under-spec | CLOSED | **CLOSED** | Dump-replay / preceding-events fail; live lock passes — still explicit in docstring. |
| **F4** MIN_EVENTS=8 vs football sparsity | ACK operational | **ACK (open operational)** | Unchanged; multi-window aggregate still comment-only. Does not block residual-accepted PASS. |
| **F5** Span padding | CLOSED | **CLOSED** | Span still from response support only. |
| **F6** No statistical test | IMPROVED | **ADDRESSED via fail-closed gate** | Empirical null remains CANDIDATE until U3; production flag cannot promote CONTINUOUS while uncalibrated. |
| **F7** Tautological dense/phase tests | PARTIAL | **IMPROVED** | Dense + off-phase use SNAP_MS=30_000 (football regime). F8 regression asserts `null_q < 1.0` (not unlucky-phase-only). |
| **F8** Circular modulus collapse | **BREAK** | **CLOSED** | `period = r_span + mean_gap`. Structural uniqueness holds for **any** distinct support (regular **and** irregular). 0/64 collapses empirically. |
| **F9** Discrete `real > null_q` fragility | WARN | **MITIGATED (fail-closed)** | Lattice fragility remains inside `optical_copresence()` diagnostics; **cannot flip CONTINUOUS** until `calibrated=True` post-U3. |
| **F10** Fixture regime ≠ football | WARN | **CLOSED** | All tests use `SNAP_MS = 30_000`. Pure-phase null discriminates at this regime. |
| **Claim** (dump-replay vs this-session coupling) | MOSTLY HELD | **HELD under residual-accepted scope** | Wrong-session / off-phase / dense → not coupled. Metronome-on-snaps residual first-class (not over-claimed as humanity). |
| **Wiring risk** (`optical_consistent` → CONTINUOUS / `replay_resistant`) | load-bearing | **HELD fail-closed in production path** | `optical_consistent_flag` default `calibrated=False` → always `False`. Only call sites today are tests. `realplay_liveness` requires `optical_consistent is True` for CONTINUOUS. |
| **NEW F11?** Free `calibrated=True` footgun | — | **INFO (process gate, not break)** | No env/crypto seal on `calibrated`; discipline is caller-side (post-U3 only). No production caller passes `True` today. Mirror of other fail-closed bool gates in the repo. |
| **NEW F12?** Irregular wrap gap = mean_gap approx | — | **INFO / residual** | Circular null models wrap gap as mean inter-arrival, not local edge gap. Uniqueness still exact; null validity is approximate for highly irregular support — acceptable for CANDIDATE + fail-closed until U3. |

### Attack results (mandated)

**1. Is `period = r_span + mean_gap` correct for IRREGULAR spacing?**

Yes, for the **uniqueness** property that F8 actually broke.

- Let responses live on support \([r_0, r_0 + S]\) with \(S = r_{\mathrm{span}}\), \(n \ge 2\), mean gap \(g = S/(n-1)\).
- Fix: \(P = S + g > S\).
- Any two distinct timestamps differ by \(\delta \in (0, S]\). Under circular shift by any offset, they collide iff \(\delta \equiv 0 \pmod{P}\). No non-zero multiple of \(P\) fits in \((0, S]\) when \(P > S\).
- Therefore **no first/last (or any pair) collision** for **any** set of distinct points — regular grids are the special case \(P = n \cdot g\); irregular is the same proof.

Empirical (this re-verify):

| Support | Shifts with collapse | min unique / n |
|---------|---------------------|----------------|
| Regular 16-pt 30s grid | **0/64** | 16/16 |
| Irregular random gaps 5–55s | **0/64** | 16/16 |
| Pathological near-pairs | 0 (input already paired; not F8 class) | — |

Null **validity** (not uniqueness): wrap gap = mean gap is a circular-stationary approximation. Highly irregular edge gaps are not perfectly preserved. Probes still: irregular locked → `event_coupled=True`; irregular uncoupled → `False`. Residual for U3 calibration, not a structural F8 reopen.

**2. Does the fail-closed gate truly block CONTINUOUS in production?**

Yes, on the only honest production path for this module.

```text
optical_consistent_flag(..., calibrated=False default)
  → if not calibrated: return False
  → else: return optical_copresence(...).event_coupled

realplay_liveness: CONTINUOUS_PRESENT iff optical_consistent is True (+ strong_shape + window)
```

Probes:

| Input to `evaluate_realplay_liveness` | Verdict |
|---------------------------------------|---------|
| `optical_consistent_flag(ev, resp)` (default) | **PARTIAL_PRESENT** |
| `optical_consistent=False` | **PARTIAL_PRESENT** |
| `optical_consistent=None` | **PARTIAL_PRESENT** |
| `optical_consistent_flag(..., calibrated=True)` when locked | **CONTINUOUS_PRESENT** |

Repo grep: `optical_consistent_flag(` call sites = definition + **tests only**. No bridge/operator path injects `calibrated=True`. `OPTICAL_CALIBRATED_DEFAULT = False` is module-level constant. CONTINUOUS via this flag is **fail-closed-unreachable** until an explicit post-U3 call.

(Bypass note: a caller can still construct `WindowFeatures(optical_consistent=True)` without this flag — that is the pre-existing injected-flag design of `realplay_liveness`, not a regression of the optical module's fail-closed claim.)

**3. Any NEW break that forces HOLD?**

No BLOCK-class new break. F11/F12 are INFO residuals; F1 metronome residual is scope-honest (F2). Thresholds remain CANDIDATE (explicitly accepted as U3 measurement residual, parallel to R-HYP).

---

**ONE VERDICT: PASS** (residual-accepted)

F8 structurally closed · F10 closed · F6/F9 production-gated fail-closed · U3 threshold measurement residual accepted · F1 anti-macro residual first-class under `session_co_presence_not_humanity` · 10/10 tests green · rails held.

Do **not** treat `replay_resistant=True` / CONTINUOUS as live until U3 + explicit `calibrated=True` wiring. Do **not** treat `event_coupled=True` as humanity/anti-macro. Diagnostic `optical_copresence()` may still return coupled for measurement; only `optical_consistent_flag` is the CONTINUOUS gate.

---

## build-results

| Surface | Result |
|---------|--------|
| Integrity check r05 body | **PASS** (sha256 match `737f9be4…`) |
| Integrity prior r04 | **PASS** (sha256 match `a1378cc6…`) |
| Code review `optical_copresence.py` | **DONE** — F8 period L121–132; gate L149–174; claim L59–69 |
| Code review `test_optical_copresence.py` | **DONE** — 10 tests; SNAP_MS=30_000; F8 + fail-closed + e2e PARTIAL pin |
| Wire-up check `realplay_liveness.py` | **DONE** — CONTINUOUS only when `optical_consistent is True` (L189–195) |
| Grep production `optical_consistent_flag` | **DONE** — tests only; default never True |
| Adversarial irregular-spacing uniqueness | **PASS** (0/64 collapse regular + irregular) |
| Adversarial lucky-phase metronome | **EXPECTED residual** (coupled = session co-presence, not break) |
| Fail-closed → PARTIAL e2e | **PASS** |
| `pytest bridge/tests/test_optical_copresence.py -v` | **10 passed in 0.44s** |
| Code changes this round (auditor) | **NONE** — re-verify only |
| FROZEN / PoAC / PV-CI / chain | **UNTOUCHED** |
| Commit / push | **NONE** (stage-only policy) |

### BUILD-NOW

None for this auditor round. Builder already landed F8/F10/fail-closed; suite green; residual-accepted PASS does not require further code in this envelope.

Optional future (not BUILD-NOW, not HOLD-blocking):

1. After U3: pin thresholds from measured snap-interval + reaction-lag; flip `calibrated=True` only behind an explicit env/config seal (not free kwargs alone).
2. Optional process seal: refuse `calibrated=True` unless `OPTICAL_U3_CALIBRATED=1` (or store-backed flag) — hardens F11 footgun.
3. F4 multi-window aggregate if single 120s windows stay under MIN_EVENTS in live CFB.

---

## open-questions

1. **U3 measurement package** — What exact corpus (N sessions / players / snap-interval + lag histograms) seals `MIN_ABS_HIT_RATE` / `NULL_QUANTILE` / `NULL_MIN_EXCESS` / `MIN_EVENTS` and authorizes `calibrated=True`?
2. **Production wiring** — Who injects `WindowFeatures.optical_consistent` in the live bridge path (retina/killfeed/event bus)? Today the optical flag is test-only; CONTINUOUS remains unreachable for that reason too.
3. **F4 operational** — Is MIN_EVENTS intended as per-window or session-aggregate? Comment says multi-window; code is per-call. Need a one-line decision before live use.
4. **F11 seal strength** — Is caller discipline enough for `calibrated=True`, or should U3 promotion be env/config-gated like `L6B_ENABLED` / campaign-mode lifts?
5. **Next A2A envelope** — Design round for U3 measurement plan + optional production wiring, or park optical co-presence as residual-accepted CANDIDATE until measurement hardware is available?

---

## rails check

| Rail | Status |
|------|--------|
| 228B PoAC wire | **held** (no touch) |
| FROZEN-v1 formulas | **held** (no touch) |
| PV-CI 184 | **held** (no invariant edit) |
| `CHAIN_SUBMISSION_PAUSED` | **held** (no chain) |
| single-committer=operator | **held** (no commit/push by auditor) |
| secrets | **none** |
)
