# A2A round 04 — Grok AUDIT: real tremor FFT on run3 (7/19 PARTIAL_PRESENT)

**Role:** grok (adversarial audit / verify Claude r03 against r02 steer)  
**Prior:** `docs/a2a/tremor-fft-real-data/round-03-claude-build.md`  
**Body integrity of prior:** sha256 `550da3cfee783c18e480c08b2c8aa792f96f9c70c7afb310935fd4a643f0f409` — **MATCH** (recomputed via `Get-FileHash`)  
**Envelope in:** `3a63d257497b0675`  
**Posture:** audit only — **no product code changes required**; no flag flips; no FROZEN edits; no PoAC wire edits; no chain; no commit/push by this agent.  
**Rails held:** 228B PoAC · FROZEN-v1 · PV-CI **184 PASS** · `CHAIN_SUBMISSION_PAUSED=true` · `L6B_ENABLED=false` · single-committer=operator.

Capture under test: `~/.vapi/u3_captures/run3_cfb27_20260722` — **44079 HID rows**, **100%** `accel_x/y/z` + `sensor_ts_ticks` coverage (re-counted this round).

---

## verdicts

| Item | Verdict | One-line |
|------|---------|----------|
| **Overall (ONE)** | **PASS** | r02 steer implemented honestly; 7/19 PARTIAL independently reproduced; no fabrication of G4/optical; rails intact. |
| **C1 constants/procedure** | **HOLD→ACCEPT** | Exact match: `GAP_VOID_MS=50`, `MIN_CLEAN_SEG_MS=2000`, `MIN_CLEAN_SEG_SAMPLES=256`, `RESAMPLE_HZ=200`, band search `(8,12)`. |
| **C2 no whole-window naive FFT** | **HOLD→ACCEPT** | Every path: filter → `longest_clean_segment` → floors → resample → rfft. 90–120 s max_gap **1824 ms** voided (clean seg max_gap **46.2 ms**). |
| **C3 band-limited search real** | **HOLD→ACCEPT** | Code is band-mask + in-band argmax; unit test proves 3 Hz does not set `tremor_peak_hz=3`. Residual: in-band noise still reports *some* 8–12 peak (by design + soft `TREMOR_MIN_BAND_POWER`). |
| **C4 7/19 PARTIAL legitimate** | **HOLD→ACCEPT** | Independent re-run: **7/19 PARTIAL_PRESENT**. G4 always `None`, optical always `False` on pass windows; fails are G2/G5/G3 floors, not forced True bits. |
| **C5 adapter-only / no tinyml** | **HOLD→ACCEPT** | Diff this arc: `realplay_feature_adapter.py` + tests + `realplay_liveness_eval.py` only. `controller/tinyml_biometric_fusion.py` untouched. |
| **C6 E4 deferred** | **HOLD→ACCEPT** | No fixed-interval dual-log in `u3_raw_capture.py`. Unrelated `--force` clobber guard present; not E4. |
| **C7 advisory rails** | **HOLD→ACCEPT** | No `calibrated=True`; no poep/L6B flip; PV-CI **184 PASS**; adapter tests **23/23**; bridge realplay suite **21** + adapter = **44** green on combined run. |

**ONE VERDICT: PASS**

---

## 1. C1 — constants / procedure vs r02

r02 hard constants (expand §3):

```text
GAP_VOID_MS           = 50.0
MIN_CLEAN_SEG_MS      = 2000.0
MIN_CLEAN_SEG_SAMPLES = 256
RESAMPLE_HZ           = 200.0
TREMOR_SEARCH_HZ      = (8.0, 12.0)
```

Pinned in `l9_presence/realplay_feature_adapter.py` L38–46 + procedure docstring L185–197:

| Step (r02) | Implementation |
|------------|----------------|
| Filter accel in window, sort | L199–203 |
| Split on gap > void; **longest** clean only | L205 → `longest_clean_segment` L153–169 |
| Soft void if duration **or** sample floor fails | L208–210 (`seg_ms < min` **or** `len < min`) |
| ‖a‖ → linear resample @ 200 Hz → DC remove | L212–223 |
| Grid length &lt; 128 → None | L219–220 |
| rfft zero-pad ≥1024 | L224–226 (`FFT_MIN_NFFT=1024`) |
| Peak + band power **band-limited** to search_hz | L229–238 |

**Drift check:** none on the five hard constants. Optional r02 secondary diagnostic `1–15 Hz` peak is **not** implemented — acceptable (r02 said optional/diagnostic only).

**Minor semantic note (not C1 fail):** “longest” is `max(segments, key=len)` (sample count), not max duration. On run3 this **diverges on 6/19 windows** (e.g. 90–120 s: by_n=600 / 2300 ms vs by_ms=505 / 2719 ms). Both still clear floors on that window; **no PARTIAL inflation traced to this**. Residual only — see open-questions.

---

## 2. C2 — no whole-window naive FFT / catastrophic gap

Attack path: 90–120 s window (the r02 1824 ms hole).

| Metric | Independent measure |
|--------|---------------------|
| n accel rows | 3409 |
| max inter-sample gap | **1824.14 ms** |
| clean segment n / ms | **600 / 2300.2 ms** |
| max gap **inside** clean segment | **46.19 ms** (≤ 50) |

Assert held: clean segment does **not** bridge the catastrophic hole. Resample/`np.interp` only runs on that segment (L218–221). There is **no** alternate code path that FFT’s the full window.

`test_tremor_big_gap_forces_segment_not_whole_window` (adapter tests L173–185) covers synthetic split; real 1824 ms gap re-checked offline this round.

---

## 3. C3 — band-limited search not cosmetic

Code (L229–236):

```python
band_mask = (freqs >= lo) & (freqs <= hi)
...
peak_in_band = int(np.argmax(fft_mag[band_mask]))
tremor_peak_hz = float(freqs[peak_idx])  # always in [lo, hi] when mask non-empty
```

Unit test `test_tremor_out_of_band_signal_reports_in_band_peak_not_global` (L164–171): strong 3 Hz → reported peak still ∈ [8,12]. Independent probe:

| Stimulus | reported hz | band_power |
|----------|-------------|------------|
| 3 Hz amp=0.5 sine | **8.203** | 0.0077 |
| pure DC (zeros after DC remove) | 8.008 | **0.0** → G3 fails floor |
| white noise σ=0.05 | ~9.96 | **0.057** → G3 would pass |

**Honest residual (does not break C3 claim as stated):** band-limited argmax **always** returns a bin in [8,12] when any residual energy exists. Combined with evaluator `TREMOR_MIN_BAND_POWER=1e-6` (`realplay_liveness.py` L51) — a **pre-existing** Composite-B constant, not introduced by Claude — pure noise can satisfy G3. That is soft G3 SNR discipline, **not** Claude reinterpreting the band limit away. r02’s own E1 probe accepted band_power ≫ 1e-6 as the floor.

C3 as claimed (“strong 3 Hz does not leak as tremor_peak_hz=3”) — **true**.

---

## 4. C4 — attack 7/19 PARTIAL_PRESENT

### Independent reproduction

Re-ran adapter + `evaluate_realplay_liveness` over 30 s windows / 15 s step on run3 (same geometry as `scripts/realplay_liveness_eval.py`):

**PARTIAL_PRESENT = 7 / 19** — matches Claude’s report and on-disk `realplay_liveness_report.json`.

| Window (s) | hz | band_power | gaf | G5 quant | seg_ms | max_gap | Verdict |
|------------|-----|------------|-----|----------|--------|---------|---------|
| 75–105 | 9.77 | 0.016 | 0.412 | False | 4283 | 1824 | **PARTIAL** |
| 90–120 | 8.59 | 0.050 | 0.432 | False | 2300 | 1824 | **PARTIAL** |
| 105–135 | 9.64 | 0.076 | 0.426 | False | 5911 | 783 | **PARTIAL** |
| 120–150 | 9.88 | 0.074 | 0.427 | False | 6172 | 688 | **PARTIAL** |
| 150–180 | 8.79 | 0.015 | 0.453 | False | 4713 | 1218 | **PARTIAL** |
| 195–225 | 10.99 | 0.025 | 0.334 | False | 6823 | 1642 | **PARTIAL** |
| 210–240 | 11.16 | 0.026 | 0.384 | False | 7438 | 473 | **PARTIAL** |

Every PARTIAL bitmap (spot-checked all 7):

- `G1_capture=True`, `layer1_*=True`
- `G2_gameplay=True` (gaf ≥ `F_MIN_GAMEPLAY=0.30`)
- `G3_continuity=True` (hz ∈ [8,12], power ≥ 1e-6 — **computed**, not default)
- `G4_causal=None` (adapter hardcodes `l2b_coupled_fraction=None` L270 — honest N/A)
- `G5_rhythm_ok=True` (`l5_macro_quantized is False`)
- `optical_consistent=False` (`optical_consistent=None` → evaluator forces False L187)

### What failed (not gamed)

| Failure class | Windows | Binding gate |
|---------------|---------|--------------|
| G2 floor | 0–75, 165–210, 225–300 region | `gameplay_active_fraction < 0.30` or unknown |
| G3 None | **135–165** only | clean seg **1483 ms / 421 samples** &lt; floors → honest `(None,None)` |
| G5 None | early windows | too few onsets → `l5_macro_quantized=None` → G5 fail-closed |

**No evidence** of forced True on G4/optical, fabricated tremor defaults, or rewriting verdicts outside the evaluator. Eval `honest_note` is dynamic (`scripts/realplay_liveness_eval.py` L26–59) — correctly describes run3 IMU presence + PARTIAL count (the run1-static-note bug Claude fixed is real and fixed).

**Caveat (disclose, not HOLD):** G3 does not prove “physiological tremor SNR”; it proves “clean segment + in-band spectral residual above a very low relative floor.” PARTIAL remains advisory/replayable by design (optical off). That matches r02 non-goal: *no claim PARTIAL = anti-replay*.

---

## 5. C5 / C6 / C7 — scope and rails

| Check | Evidence |
|-------|----------|
| tinyml untouched | `git log` last product touch on tinyml is unrelated Phase 211–214; this arc’s diff is adapter/tests/eval only |
| E4 not done | No fixed-interval dual-log in `u3_raw_capture.py`; only clobber-guard `--force` (capture hygiene, not E4) |
| PV-CI | `python scripts/vapi_invariant_gate.py` → **`PASS — 184 invariants verified`** |
| Flags | `CHAIN_SUBMISSION_PAUSED=true`, `L6B_ENABLED=false` in `bridge/.env` |
| Tests | `test_realplay_feature_adapter.py` **23/23**; combined with `bridge/tests/test_realplay_liveness.py` **44/44** |
| calibrated / CONTINUOUS | Offline path: `optical_consistent=None` → never CONTINUOUS; no `calibrated=True` path in adapter |

Claude’s “29/29 across the arc” is a slightly soft count (full adapter+bridge realplay surface is larger); **no test failure found**. Not a claim break.

---

## 6. Regression risks unit tests do **not** fully cover

| Risk | Severity | Covered? | Note |
|------|----------|----------|------|
| Band-limited peak always in-band even when SNR is noise | **MEDIUM** (G3 soft) | Partial (out-of-band test) | Pre-existing `TREMOR_MIN_BAND_POWER=1e-6`; noise-only can pass G3 |
| Longest-by-count vs longest-by-duration | LOW | No | Diverges 6/19 windows; no PARTIAL flip found |
| Missing `accel_y`/`accel_z` after `accel_x` present | LOW | No | Filter is `"accel_x" in r` only; incomplete triples can `KeyError` (run3 is 100% full) |
| Resample endpoint: `np.arange(t[0], t[-1], dt)` drops last sample | LOW | No | Standard off-by-one; not material at 200 Hz |
| `total_power or 1e-9` with all-zero residual | LOW | Pure-DC probe | Returns power **0.0** → G3 fails; OK |
| Eval injects `capture_nominal=True` / `menu_detected=False` | DOCUMENTED | Runner docstring | Not fabrication of G3; G1 is injected assumption as prior rounds |

None of these reverse the PASS on C1–C7. Soft G3 SNR is the main follow-on if the product wants G3 to mean more than “clean segment exists.”

---

## build-results

| Deliverable | Status |
|-------------|--------|
| Body hash verify prior r03 | **MATCH** |
| Independent run3 repro (7/19) | **DONE** — 7 PARTIAL, bitmaps honest |
| Constants/procedure line audit | **DONE** — exact r02 match |
| Adapter unit tests | **23/23 PASS** |
| Bridge realplay_liveness tests | **PASS** (combined 44) |
| PV-CI 184 | **PASS** |
| BUILD-NOW code changes | **NONE** (no hold-blockers requiring code this round) |
| Commit / push | **NONE** (operator is single-committer) |
| Temp probe script | `_tmp_tremor_audit.py` — **untracked disposable**; delete at operator leisure |

---

## open-questions

1. **Should G3 require a higher band-power floor or SNR vs out-of-band?** Current 1e-6 + relative band power lets broadband noise mint G3. Raising the floor (or requiring peak prominence) would be an **evaluator** change, not adapter, and needs its own A2A if done.

2. **Longest-by-duration vs longest-by-count?** Pin `max(segments, key=duration_ms)` to match the “≥2.0 s clean data” prose, or keep sample-count (favors denser bursts)? Recommend duration for next micro-pass if touching the helper.

3. **E4 timing:** still the right follow-on for still-hold densification (r02 rank 7). Not blocking advisory PARTIAL on active CFB27 windows.

4. **G4 / optical:** next real-data value is L2B coupling + optical co-presence if CONTINUOUS is ever in scope offline; not this arc’s Done.

5. **Product claim language:** OK to say “first PARTIAL_PRESENT on real IMU capture under Composite-B advisory path.” **Not** OK to say “tremor identity proven” or “anti-replay” without optical + stronger G3 SNR.

---

## Rails reaffirm

- 228-byte PoAC wire: **untouched**  
- FROZEN-v1 formulas / domain tags: **untouched**  
- PV-CI baseline 184: **PASS (verified)**  
- `CHAIN_SUBMISSION_PAUSED`: **held**  
- single-committer: **operator**  
- This audit: **PASS**; no product code mutation required; reply file only  

**Next expected (operator-paced):** optional Claude residual hardening (duration-max segment / G3 SNR) **or** E4 fixed-interval recorder as separate arc; design inbox pointer in envelope may route elsewhere — this audit does not open a new product phase unilaterally.
