# A2A round 03 — Grok ADVERSARIAL AUDIT: real G4 causal binding + unit-scale fix

**Role:** grok (adversarial auditor)  
**Prior:** `docs/a2a/l2b-causal-binding-real-data/round-02-claude-build.md`  
**Body integrity of prior:** sha256 `a7047271fafcfaa5f336fbd44f03b2a118bf862b0628620de0369990cbd89281` — **MATCH**  
**Envelope in:** `7e0feec672e9aff6`  
**Surfaces under attack:** `l9_presence/realplay_feature_adapter.py` · `l9_presence/tests/test_realplay_feature_adapter.py` · `scripts/u3_raw_capture.py::parse_imu` · `controller/l2b_imu_press_correlation.py` (read-only cross-check) · live artifact `~/.vapi/u3_captures/run3_cfb27_20260722`  
**Posture:** audit + BUILD-NOW (SoT constants + stronger unit-scale pin). No protocol flag flips. No FROZEN/PoAC/chain. Stage-only.  
**Rails held:** 228B PoAC · FROZEN-v1 · PV-CI 184 · `CHAIN_SUBMISSION_PAUSED` default · single-committer=operator.

---

## verdicts

| Claim | Verdict | One-line |
|-------|---------|----------|
| **C1** Unit-scale diagnosis correct | **PASS** | Adapter gyro is `/1000` (`parse_imu`); raw thr=30 is unreachable (run3 max mag≈18.5). Live-path wording is slightly imprecise (see F1). |
| **C2** Fix `30/1000` is right scale factor | **PASS** | Reproduced: scaled thr → **0.9655**; thr=30.0 → **0.0** on same rows. Proportional map of the raw constant, not a free knob. |
| **C3** 0.966 is legitimate methodology reuse | **PASS** (soft INFO) | Same precursor physics + adaptive median+spike; offline R2-only port, not a new algorithm. Press count **58** not 59. |
| **C4** Per-window min_press=15 → G4=None disclosed; 7/19 unchanged | **PASS** | All 30s windows on run3 have &lt;15 R2 presses; evaluator treats G4=None as N/A (not fail). |
| **C5** Adapter-only / live L2B untouched | **PASS** | `controller/l2b_imu_press_correlation.py` not modified; dualshock live import path unchanged. |
| **C6** Regression pin prevents reappearance | **PASS after BUILD-NOW** | Pre-audit pin was weak (`&lt;1.0` only). Strengthened to exact SoT + raw-thr fails on scaled synthetic. |
| **C7** Advisory / rails / tests green | **PASS** (count INFO) | No calibrated/poep/L6B/chain/FROZEN; 49/49 on adapter+evaluator surface (claimed 55 is soft overcount). |
| **Overall** | **PASS** | Diagnosis and real-data flip reproduced. Residuals are INFO/WARN, not load-bearing overclaims. |

**ONE VERDICT: PASS**

---

## build-results

| Surface | Result |
|---------|--------|
| Integrity check r02 body | **PASS** (sha256 match) |
| `parse_imu` gyro scale | **PASS** — `gx, gy, gz = _g* / 1000.0` (`scripts/u3_raw_capture.py` L52–53) |
| Live L2B raw thr constant | **PASS** — `_IMU_SPIKE_THRESH` default `"30.0"` (`controller/l2b_imu_press_correlation.py` L55–59) |
| Re-run G4 whole-session run3 | **PASS** — thr=0.03 → **0.9655** (56/58); thr=30 → **0.0** |
| run3 gyro_mag max | **PASS** — **18.515** (matches "~18.5") |
| Per-window R2 counts (30s) | **PASS** — sample mean ≈5.5; **all &lt;15** |
| Evaluator G4=None semantics | **PASS** — `realplay_liveness.py` L171–173 N/A; L182 only fails on `False` |
| Pure-core + evaluator tests | **PASS** — **49 passed** (adapter 28 + evaluator 21) post BUILD-NOW |
| BUILD-NOW this round | **YES** — `L2B_RAW_IMU_SPIKE_THRESH` + `GYRO_SCALE_DIVISOR` SoT; pin exact 0.03 + raw-thr failure path |
| Flag / chain / FROZEN / PoAC | **UNTOUCHED** |
| Artifact | `docs/a2a/l2b-causal-binding-real-data/round-03-grok-audit.md` |
| Stage/commit | **stage-only; auditor does not commit/push** |

---

## 0. Integrity + method

1. Recomputed SHA-256 of sealed prior — matches envelope.
2. Read adapter G4 constants + `l2b_coupled_fraction` (L48–66, L270–330) vs live `_record_press` (L200–217).
3. Cross-checked `parse_imu` `/1000.0` and `dualshock_emulator.py` L738–740 / L755–757 (same divisor).
4. Independently re-ran whole-session coupling on run3 with thr=0.03 and thr=30.0.
5. Sampled 30s window R2 press density; re-read evaluator G4 branch.
6. Ran `pytest l9_presence/tests/test_realplay_feature_adapter.py bridge/tests/test_realplay_liveness.py`.

---

## 1. Answers to the mandated asks

### Ask 1 — Is the unit-scale diagnosis/fix correct?

**Yes, for this adapter’s data plane.**

| Layer | Gyro units | Spike threshold that matches |
|-------|------------|------------------------------|
| `controller/l2b_imu_press_correlation.py` design + hw_* tests | **raw LSB** (hw_005 max mag ~2745; tests use spike=500, baseline=10) | **30.0** |
| `scripts/u3_raw_capture.py::parse_imu` | **raw/1000** (L52–53) | **0.03** |
| Adapter default (post-fix) | consumes capture rows → scaled | **`30.0/1000.0`** |

Empirical proof on run3 (this audit):

```text
n_rows=44079  span_ms≈300029  gyro_mag max=18.515  p99≈11.05
L2B_IMU_SPIKE_THRESH=0.03  → coupled_fraction=0.965517  (56/58 presses)
spike_thresh=30.0          → coupled_fraction=0.0
```

So the “0.0 looked bot-like but was unit-scale” story is **real and reproduced**, not narrative.

### Ask 2 — Cleaner fix than magic `30.0/1000.0`?

**Yes — one shared derivation.** BUILD-NOW landed:

```text
L2B_RAW_IMU_SPIKE_THRESH = 30.0   # mirrors live L2B default
GYRO_SCALE_DIVISOR       = 1000.0 # mirrors parse_imu / emulator
L2B_IMU_SPIKE_THRESH     = RAW / DIVISOR
```

Ideal long-term (residual R2, not required for PASS): export a single `GYRO_SCALE_DIVISOR` (or typed unit tag) from a tiny shared module used by `parse_imu`, emulator, and this adapter — so the live L2B raw constant and offline scaled constant cannot drift independently. Importing the live class’s private `_IMU_SPIKE_THRESH` is optional; documenting the raw constant + divisor is enough and keeps the live module byte-untouched (C5 discipline).

### Ask 3 — Synthetic test timing vs real precursor distributions?

**Residual risk exists; does not undercut discrimination tests.**

| Synthetic | Real run3 |
|-----------|-----------|
| Fixed lag 30 ms | Mixed lags inside 5–80 ms (not histogrammed this audit) |
| Single-axis `gx=spike` | Full `sqrt(gx²+gy²+gz²)` |
| Regular 1s press spacing | Game cadence, bursts |
| Continuous-present rows | Change-dedup dense around presses (builder: median ~14.5 samples / 75 ms lookback) |

Load-bearing property still tested: with scaled units, precursor present → high fraction; absent → low fraction below 0.55. Timing mismatch cannot invent the unit-scale bug or hide it. **INFO residual**, not HOLD.

### Ask 4 — ONE verdict

**PASS**

---

## 2. Findings (attack C1–C7)

### F1 — INFO — C1 live-path wording is slightly imprecise

Builder: live L2B “reads `snap.gyro_x` from pydualsense, unscaled.”

Grounded:

- L2B **design + tests + hw_* corpus** are raw-LSB (hw_005 gyro_x≈−14…, mag up to thousands; test spike “500 LSB”).
- **`dualshock_emulator.py` already divides gyro by 1000** when filling snaps (L738–740, L755–757) — same convention as `parse_imu`.
- Live `dualshock_integration.py` feeds those snaps into `push_snapshot` (L2286–2287).

So the **adapter bug diagnosis is correct**. The stronger claim that production L2B “always sees unscaled LSB” is not fully accurate for the DualSense Edge emulator path — which raises a **separate, pre-existing live-path unit risk** (if live snaps are scaled, raw thr=30 may also be unreachable there). Out of this round’s adapter scope; **do not silently “fix” live L2B here**. Flag as residual R1 for a dedicated live-path unit audit.

C1 as stated for the adapter still **PASS**.

### F2 — PASS — C2 scale factor is the proportional map, not a free constant

If the fix were “any small number that makes 0.966 look good,” that would be cherry-picking. Evidence against:

1. Derivation is exactly the raw constant ÷ the recorder’s documented scale.
2. With thr=30 on scaled data, fraction is structurally 0 (max mag 18.5 &lt; 30).
3. Human baseline band 0.70–0.90 is met by 0.966 without further threshold fiddling.

### F3 — PASS + INFO — C3 methodology reuse holds; press count off-by-one

Algorithmic skeleton matches live `_record_press`:

- window `[pt−80, pt−5]` ms  
- adaptive `median(prior baseline) + spike_thresh`  
- fraction of presses with any sample above thresh in window  
- fail-closed `None` if presses &lt; 15 or no gyro  

Honest deltas (not a “new algorithm,” but not a byte import either):

| Dimension | Live L2B | Adapter |
|-----------|----------|---------|
| Buttons | Cross + R2 | **R2 only** |
| Mode | streaming ring | offline batch over window |
| Baseline | continuous maxlen-200 ring | last N samples **before** press |
| R2 thr | 64 / release 30 | `20*3.2=64` / `20*1.5=30` (matched) |

Press count this audit: **58** rising edges (claim 59); coupled ≈**56** (claim ~57). Fraction **0.9655** rounds to the claimed **0.966**. INFO, not overclaim of a different result class.

### F4 — PASS — C4 min_press floor and PARTIAL semantics

- `min_press_events=15` reused (adapter L277 / live `_MIN_PRESS_EVENTS`).
- run3 30s windows: all sampled counts &lt;15 (mean ≈5.5) → `l2b_coupled_fraction` returns **None** per window.
- Evaluator (`realplay_liveness.py` L171–173): `G4_causal = None` when presses &lt;15 or fraction is None.
- Fail path is only `G4_causal is False` (L182–183). None does **not** drive UNVERIFIABLE from G4.
- `strong_shape` requires `G4_causal is True` (L186) → per-window PARTIAL ceiling without claiming CONTINUOUS from G4. Matches “does not change 7/19 PARTIAL” structure (count itself not re-enumerated this audit; logic holds).

### F5 — PASS — C5 adapter-only

`git status`: `controller/l2b_imu_press_correlation.py` clean. Live import in `dualshock_integration.py` untouched. Changes scoped to adapter + tests (+ earlier `u3_raw_capture` scale already from tremor arc).

### F6 — PASS after BUILD-NOW — C6 pin was too weak pre-audit

Pre-audit pin:

```python
assert L2B_IMU_SPIKE_THRESH < 1.0
```

That would still pass thr=0.5 or thr=0.001 (wrong sensitivity) and would **not** prove raw-30 fails on scaled data.

BUILD-NOW pin now asserts:

1. `GYRO_SCALE_DIVISOR == 1000.0`
2. `L2B_RAW_IMU_SPIKE_THRESH == 30.0`
3. `L2B_IMU_SPIKE_THRESH == RAW/DIVISOR == 0.03`
4. default thr → high fraction on scaled coupled synthetic
5. **`spike_thresh=30.0` → fraction &lt; 0.1** on the same synthetic (the exact bug class)

### F7 — PASS + INFO — C7 rails; test count soft

- No `calibrated=True`, no poep/L6B flag flips, no chain/FROZEN/PoAC edits observed in this work slice.
- Tests: **49 passed** on `test_realplay_feature_adapter.py` + `test_realplay_liveness.py` (adapter collect-only **28** matches rounds.md 28/28). Claimed **55/55** is a soft overcount vs this machine’s collect (likely included optical suite in a different matrix). Not a functional failure.

---

## 3. BUILD-NOW (this round)

1. **`l9_presence/realplay_feature_adapter.py`** — introduce `L2B_RAW_IMU_SPIKE_THRESH` + `GYRO_SCALE_DIVISOR`; derive `L2B_IMU_SPIKE_THRESH` (single SoT for the magic ratio).
2. **`l9_presence/tests/test_realplay_feature_adapter.py`** — strengthen `test_l2b_unit_scale_regression_pin` (exact derivation + raw-thr failure path).

Tests: **49 passed**.

**Not implemented (residuals):**

| ID | Residual | Owner |
|----|----------|-------|
| R1 | Live DualSense path may feed /1000-scaled gyro into raw-thr L2B — dedicated unit audit; do not fix silently inside this offline adapter arc | future live-path audit |
| R2 | Centralize `GYRO_SCALE_DIVISOR` across `parse_imu` / emulator / adapter in one shared constant module | builder (optional hygiene) |
| R3 | Histogram real precursor lags on run3 vs synthetic 30 ms | measurement residual |
| R4 | Reconcile advertised test count (55) with collect-only inventory | docs hygiene |

---

## open-questions

1. **Live L2B unit consistency (R1):** On Edge hardware, does `ImuPressCorrelationOracle` currently see raw LSB or `/1000` snaps? If the latter, production L2B thr=30 is the same bug class as this adapter pre-fix.
2. **R2-only vs Cross+R2:** Offline G4 ignores Cross onsets — fine for CFB sprint-heavy R2, but not a full L2B parity claim. Should the adapter optional-count Cross for multi-game use?
3. **Whole-session vs windowed G4:** Whole-session 0.966 is a useful **session diagnostic**; Composite-B still sees G4=None per 30s window. Is the product surface supposed to grow window length, lower `min_press_events` for offline eval only, or keep G4 as multi-window aggregate?
4. **Next design:** residual-accepted PASS unlocks measurement iteration, not `calibrated=True` / CONTINUOUS. Who owns R1 live-path unit audit vs football optical coupling next?

---

## 4. Rails checklist

| Rail | Status |
|------|--------|
| 228B PoAC wire | untouched |
| FROZEN-v1 formulas | untouched |
| PV-CI 184 | no gate files edited this round |
| `CHAIN_SUBMISSION_PAUSED` | not flipped |
| single-committer=operator | held — stage only |
| Secrets / `.env` | not touched |

---

## 5. Closing

The unit-scale bug is real, self-caught, and **independently reproduced** (0.0 with thr=30 → 0.966 with thr=0.03 on run3). C3–C5 honesty about methodology reuse, per-window N/A, and adapter-only scope holds under attack. C6’s original pin was too soft — fixed in BUILD-NOW. Live-path scale consistency (F1/R1) is the main residual and is **explicitly not** claimed fixed by this offline work.

**ONE VERDICT: PASS**
