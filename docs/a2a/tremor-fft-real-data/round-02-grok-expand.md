# A2A round 02 — Grok EXPAND: real tremor FFT on irregularly-sampled capture

**Role:** grok (forward expand / adversarial steer)  
**Prior:** `docs/a2a/tremor-fft-real-data/round-01-claude-open.md`  
**Body integrity of prior:** sha256 `f98c17ccb5fc3559b820b6c7cf5ed6937562c5a35a04facde73a908b1e4dc314` — **MATCH** (recomputed)  
**Envelope in:** `30529504a23ebc01`  
**Posture:** design only — **no code, no flag flips**, no FROZEN edits, no PoAC wire edits, no chain, no commit.  
**Rails held:** 228B PoAC · FROZEN-v1 · PV-CI 184 · `CHAIN_SUBMISSION_PAUSED` · single-committer=operator.

Capture under test: `~/.vapi/u3_captures/run3_cfb27_20260722` — **44079 HID rows**, **300.03 s**, keys include `accel_x/y/z` + `sensor_ts_ticks` (100% IMU/device-clock coverage).

---

## verdicts

| Item | Verdict | One-line |
|------|---------|----------|
| **Irregular-sampling diagnosis** | **PARTIALLY ACCEPT** | Serious for *naive whole-window* `fs=1/median(dt)`+rfft; **not** a full ban on any FFT from change-dedup data. |
| **Claude gap numbers (90–120 s)** | **REPRODUCED** | median 3.04 ms · mean 8.78 ms · p10 0.40 · p90 16.88 · max **1824** · accel_x std **0.0385 g** · 959 unique / 3409. |
| **E1 resample** | **PRIMARY STEER** | But **segment-first**: longest contiguous run with all gaps ≤ threshold → linear interp → rfft. Whole-window E1 alone is invalid. |
| **E2 Lomb–Scargle** | **DEFER** | Statistically nicer; new primitive; heavier verify; not needed if E1+gap-void is honest. |
| **E3 stick-velocity** | **REFUTE for G3** | Category error: G3 is *involuntary* continuity; stick spectrum is voluntary gameplay. Same sampling problem anyway. |
| **E4 fixed-interval recorder** | **ADOPT as follow-on** | Correct corpus hygiene; does **not** make run3 untouchable. |
| **Refute-all (never compute on run3)** | **REJECT** | Too strong — clean segments exist (best full-capture thr=50 ms: **9.0 s / 2413 samples**). |
| **Concrete gap void** | **50.0 ms** | Hard: do not interpolate across any gap > **50 ms**. Soft: if no clean segment ≥ **2.0 s** and ≥ **256** raw samples → return `(None, None)`. |
| **Compute tremor on run3?** | **YES, with honesty rails** | Not “full 30 s dump is valid”; yes on qualifying clean segments. |
| **"Defer, need recapture" as Done?** | **VALID OUTCOME, not default** | Valid *if* yield of qualifying segments across G1/G2/G5 windows is zero or peak never clears 8–12 Hz. Not the a priori Done. |
| **BUILD-NOW (this expand)** | **NONE** | Design-only per sealed mandate; Claude owns r02 build. |

---

## 1. Attack the irregular-sampling diagnosis

### What Claude got right

1. **Change-dedup ≠ uniform 1 kHz.** The tested path in `controller/tinyml_biometric_fusion.py` (~L495–559) builds `fs = 1/median(inter_frame_us)` then `np.fft.rfft` over a ring that was filled by continuous poll. U3 logs on CHANGE. Treating dedup rows as equal-Δt samples is a real spectral-model error (leakage / wrong frequency axis), not pedantry.

2. **Max gap 1824 ms is catastrophic if ignored.** At 10 Hz, period = 100 ms → a 1.82 s hole swallows ~18 tremor cycles. Linear interpolation invents a straight line where the hand was unobserved. That is not “mild smear.”

3. **Signal is real, not dead IMU.** Independent re-measure on the 90–120 s window matches Claude’s packet:

| Metric (90–120 s) | Claude r01 | Grok re-measure |
|-------------------|------------|-----------------|
| n rows | 3409 | **3409** |
| gap median / mean / p90 / max (ms) | 3.0 / 8.8 / 16.9 / 1824.1 | **3.04 / 8.78 / 16.88 / 1824.14** |
| accel_x std | 0.0385 g | **0.03853 g** |
| unique accel_x | 959 / 3409 | **959 / 3409** |

### What the framing overstates

1. **"Irregular ⇒ FFT invalid on any change-dedup capture" is false.**  
   Most *gaps* are short: p90 ≈ 17 ms ≪ 100 ms (10 Hz period). Median 3 ms implies dense bursts. The problem is **heavy-tailed gaps**, not uniform irregularity. Diagnosis should be: **FFT is valid on contiguous dense segments after gap control**; invalid on the raw concatenated series.

2. **Count vs time fraction (load-bearing).** On 90–120 s with thr=50 ms:

| | Value |
|--|------|
| gaps > 50 ms | **87 / 3408** (~2.6% of *gaps*) |
| **time** in gaps > 50 ms | **~39.8%** of the window |
| longest clean segment | **2.72 s / 505 samples** |

So: “almost all samples are fine” and “almost half the timeline is untrustworthy if you stitch across holes” are *both* true. Claude under-emphasized the **time fraction** and the need for **segmentation** (not only “void the whole window”).

3. **Nyquist is not the blocker.** Mean rate ≈ 114 Hz (3409/30 s); median rate ≈ 333 Hz. Both ≫ 2×12 Hz. The binding constraint is **gap-induced model violation**, not Nyquist.

4. **tinyml’s `fs=1/median(dt)` is already an approximation.** Live USB poll is mildly jittered; median-fs+rfft is the project’s accepted engineering path under *continuous* capture. The novelty here is not “FFT is hard,” it is “dedup creates multi-cycle voids continuous poll never had.”

### Corrected diagnosis (one sentence)

Change-dedup capture has **usable dense micro-bursts** for 8–12 Hz band estimation **if and only if** multi-cycle gaps are excluded (segment or void); a whole-window naive FFT on run3 is dishonest.

---

## 2. Steer E1 / E2 / E3 / E4 / refute-all

### Decision: **MERGE E1 + gap-void segment rail + E4 follow-on; refute E3-for-G3; defer E2; reject refute-all**

| Option | Verdict | Grounding |
|--------|---------|-----------|
| **E1 resample** | **YES — primary** | Standard DSP; reuses `np.fft.rfft` family already tested; `l9_presence/coupling.py::resample_uniform` already implements linear interp onto a grid (same primitive class). Target grid: **200 Hz** (Nyquist 100 Hz ≫ 12 Hz; lighter than 1 kHz; matches density of clean segments better than fabricating 1 kHz from ~100–300 Hz bursts). |
| **E1 whole-window** | **NO** | Max gap 1.8 s + ~40% time in >50 ms holes on the cited window → invented spectrum. |
| **E1 segment-first** | **YES — required amendment** | Longest contiguous run with all inter-sample gaps ≤ `GAP_VOID_MS`, then resample that run only. Empirically: full run3 thr=50 → best **9.03 s / 2413 samples**; window 120–150 s thr=50 → **6.17 s / 2007**; window 60–90 s thr=50 → **8.42 s / 1490**. Those clear a 2 s floor. Window 90–120 s thr=50 is *marginal* (2.72 s / 505) — may pass min-duration or return None honestly. |
| **E2 Lomb–Scargle** | **DEFER** | Right tool for irregular series in textbooks; wrong tool for *this* advisory G3 close-out: new math surface, no existing project tests, harder adversarial review, still needs a gap/quality story for multi-second holes (Lomb does not invent information in a 1.8 s void). Revisit only if E1+segment fails empirically with high clean-segment yield but nonsense peaks. |
| **E3 stick-velocity** | **REFUTE for Composite-B G3** | G3 is labeled *involuntary continuity* (`realplay_liveness.py` G3_continuity). Stick velocity FFT is the tinyml **primary gameplay** path for L4 features when stick is active — voluntary content. CFB27 has active stick (G2 already passes). Reporting stick spectral peak as “tremor” would let intentional stick oscillation mint G3. Accel magnitude (still-hold / residual grip) is the correct involuntary channel. E3 also **inherits the same irregular sampling problem** — it does not dodge the diagnosis. |
| **E4 fixed-interval log** | **YES — non-blocking follow-on** | Dual log: keep change-dedup for storage + emit fixed 5 ms (200 Hz) samples for spectral work. Unblocks future still-hold densification (dedup *undersamples quiet periods* where pure tremor lives). Does **not** make run3 non-computable. |
| **Refute-all** | **REJECT** | Contradicted by clean-segment lengths above + a quick E1 probe (below). Leaving the stub forever because “dedup bad” would be over-conservatism dressed as honesty. |

### Quick E1 probe (not a ship claim — existence proof)

Longest thr=50 ms clean segment inside 90–120 s: **2.72 s**, 505 raw → linear resample @ 200 Hz → 544 grid samples → zero-pad rfft n=1024:

| Quantity | Value | Note |
|----------|-------|------|
| Global spectral peak | **0.39 Hz** | Postural / residual gravity — expected for ‖a‖ after mean remove |
| Peak **inside 8–12 Hz** | **10.16 Hz** | In G3 band |
| Band power (8–12) / total | **0.0199** | ≫ `TREMOR_MIN_BAND_POWER=1e-6` |
| Peak in 1–15 Hz physio search | **6.06 Hz** | Outside 8–12; shows **search band choice is load-bearing** |

**Implement implication:** `tremor_peak_hz` for G3 must be the argmax **restricted to the physiological / G3 band** (prefer **8–12 Hz** to match `TREMOR_BAND_HZ`, or 1–15 then gate — but do **not** use unconstrained global argmax on accel magnitude, or G3 will almost always fail on low-frequency postural energy even when 8–12 content is real). Align with Phase 205 accel path spirit (band-limited peak search), not the stick path’s global peak.

This probe is **existence evidence that E1+segment can produce non-None in-band numbers on run3**, not proof every window reaches PARTIAL_PRESENT.

### Change-dedup still-hold bias (document, do not ignore)

When the pad is nearly still, CHANGE-logging **thins** the stream precisely where pure tremor is cleanest. Large gaps during still → segment void → `(None,None)`. That is honest for this capture mode. It is also why **E4 remains the right long-term fix** for tremor_resting / still-hold style probes — but active CFB27 windows often keep the stream denser (see 60–90 s / 120–150 s).

---

## 3. Concrete gap-length threshold (not “judgment”)

### Hard constants (pin in code comments as CANDIDATE, not FROZEN)

```text
GAP_VOID_MS          = 50.0    # never interpolate across a gap longer than this
MIN_CLEAN_SEG_MS     = 2000.0  # need ≥2.0 s of clean data (~16–24 cycles @ 8–12 Hz)
MIN_CLEAN_SEG_SAMPLES = 256     # raw samples in that segment (fail-closed floor)
RESAMPLE_HZ          = 200.0   # uniform grid after segment accept
TREMOR_SEARCH_HZ     = (8.0, 12.0)  # report peak inside this band for G3
# optional secondary: also compute 1–15 peak for diagnostics only
```

### Why **50 ms** (derivation)

| Anchor | Value | Relation to 50 ms |
|--------|-------|-------------------|
| Mid-band tremor period (10 Hz) | 100 ms | 50 ms = **½ period** — linear interp across ≥½ cycle can invent phase / suppress true peak |
| High-band period (12 Hz) | 83.3 ms | 50 ms ≈ **0.60 T** — slightly looser than ½·T₁₂; still voids multi-cycle holes |
| Low-band period (8 Hz) | 125 ms | 50 ms = **0.40 T** — conservative vs low band |
| run3 p90 gap | 16.9 ms | ≪ 50 → dense bulk **kept** |
| run3 max gap | 1824 ms | ≫ 50 → **voided** (not interpolated) |

**Rejected alternatives:**

| Candidate | Why not |
|-----------|---------|
| 16.9 ms (=p90) | Voids nearly every segment needlessly; p90 is a *density* descriptor, not a physics limit |
| 100 ms (=1 period @10 Hz) | Allows full-cycle interpolation; too permissive for claimed 8–12 Hz peak |
| 125 ms (=1 period @8 Hz) | Same class; on 90–120 s still leaves max=1824 void but admits 1-cycle fabrications |
| Void whole window if any gap > thr | Too blunt: 90–120 s has max=1824 but also a 2.7 s clean run; 120–150 s has 6+ s clean. Segment rail recovers them. |

### Soft void (window / call returns `(None, None)`)

After splitting on gaps > `GAP_VOID_MS`, take the **longest** remaining contiguous segment. Return `(None, None)` if:

1. `best_seg_duration_ms < MIN_CLEAN_SEG_MS`, **or**
2. `best_seg_n_samples < MIN_CLEAN_SEG_SAMPLES`, **or**
3. no accel keys / <2 timestamps, **or**
4. after resample, grid length < 128 (degenerate).

Do **not** invent peak=0.0 to “look computed” — existing stub contract is `(None, None)` → G3 fail-closed. Keep that.

### Optional diagnostic fields (runner/report only, not WindowFeatures required)

- `max_gap_ms`, `time_frac_gaps_gt_void`, `clean_seg_ms`, `clean_seg_n`, `resample_hz`  
Useful for the r02 eval report; keep out of FROZEN surfaces.

---

## 4. Is “defer, need recapture” a valid Done?

### Short answer

**Yes, as a *possible empirical outcome*. No, as the a priori Definition of Done for this loop.**

### Recommended Definition of Done (honest either way)

| Step | Pass criterion |
|------|----------------|
| D1 | `tremor_from_accel` implements E1+segment+gap-void; no whole-window naive FFT |
| D2 | Unit tests: absent accel → None; synthetic uniform 10 Hz sine → peak ∈ 8–12; synthetic with 200 ms hole → void or peak from clean side only (not peak pulled by interp across hole) |
| D3 | Re-run Composite-B on run3 windows that already pass G1/layer1/G2/G5 |
| D4a | **If** ≥1 such window gets non-None tremor with peak ∈ [8,12] and band_power ≥ 1e-6 → report PARTIAL_PRESENT possible; loop success = “G3 computed” |
| D4b | **If** all such windows return None (no clean segment) **or** peaks systematically outside band with high clean yield → **honest Done = G3 deferred pending E4 recapture** + document yield table |
| D5 | No claim of calibrated security; advisory / offline only; no poep/L6B/flag flips |

“Defer, need new data” is **valid Done under D4b**, not a way to skip D1–D3.

### When E4 becomes mandatory before claiming PARTIAL on realplay

- Clean-segment yield ≈ 0 on gameplay windows that pass G2, **or**
- Only still-hold captures are in scope and dedup systematically voids them, **or**
- Product wants continuous full-window tremor (not segment-local) as a stable feature.

None of those are proven pre-build; do not pre-commit to defer.

---

## 5. Ranked build order for Claude r02

| Rank | Item | Why |
|------|------|-----|
| **1** | Pure helpers in `realplay_feature_adapter.py` (or tiny sibling module): `inter_sample_gaps_ms`, `longest_clean_segment(rows, thr_ms)`, constants above | Testable without FFT; pins the rail |
| **2** | `tremor_from_accel`: filter window → clean segment → ‖a‖ → resample 200 Hz (`np.interp` or reuse coupling pattern **without** pulling coupling’s video deps into adapter if avoidable) → DC remove → rfft (zero-pad ≥1024 if short) → **band-limited** peak 8–12 Hz + band_power | Core ship |
| **3** | Unit tests (synthetic): no accel; uniform 10 Hz; gap >50 ms voids; short segment → None; band power floor behavior | Green CI |
| **4** | Wire only through existing `extract_window_features` (already calls stub) | No new flags |
| **5** | Offline eval: `scripts/realplay_liveness_eval.py` (or one-shot) on run3 windows 90–120 / 120–150 / 150–180; table of clean_seg_ms, peak_hz, band_power, G3 bit, verdict | Empirical Done fork D4a/D4b |
| **6** | Docstring on stub replacement: cite GAP_VOID_MS=50, segment rule, “not tinyml 1 kHz continuous” | Honesty |
| **7** | **E4 recorder dual-interval** (`u3_raw_capture.py`) | **Separate PR / follow-on** — do not block D1–D5 |
| **8** | E2 Lomb–Scargle | Only if D5 shows high clean yield + systematically garbage E1 peaks |

### Explicit non-goals (r02)

- No edits to `tinyml_biometric_fusion.py` live path / L4 production features  
- No `poep_enabled` / `L6B_ENABLED` / campaign flag flips  
- No FROZEN-v1 / 228B PoAC / PV-CI allowlist ceremony  
- No claim that PARTIAL_PRESENT = anti-replay (optical still required for CONTINUOUS)  
- No stick-velocity as G3 substitute (E3)

---

## build-results

| Deliverable | Status |
|-------------|--------|
| Expand design (this file) | **SHIPPED** |
| Independent gap re-measure on run3 | **DONE** (numbers in §1–§2) |
| Segment thr sweep + E1 existence probe | **DONE** (offline; not committed code) |
| Production `tremor_from_accel` implementation | **NOT THIS ROUND** (Claude r02 per ranked order) |
| Tests / flag flips / commit / push | **NONE** |

Probe script used for this expand (local, disposable): `scripts/_tmp_tremor_gap_probe.py` — **delete or leave untracked**; not part of the product surface.

---

## open-questions

1. **Band for peak report:** pin peak search to **[8, 12] Hz** (matches G3 gate exactly) vs tinyml accel’s **[1, 15] Hz** then gate? Recommend **[8, 12]** for G3-facing `tremor_peak_hz` to avoid 6 Hz postural peaks failing the gate after “successful” compute. Secondary diagnostic field optional.

2. **Multiple clean segments:** use longest only (recommended r02) vs power-weighted average of top-k peaks? Longest-only is simpler and harder to game.

3. **90–120 s marginal segment (2.72 s):** keep `MIN_CLEAN_SEG_MS=2000` (admits it) or raise to 4000 (rejects; forces reliance on denser windows like 120–150)? Recommend **2000** for first ship; report yield.

4. **E4 interval:** 5 ms (200 Hz) vs 1 ms (1000 Hz)? 200 Hz is enough for 12 Hz band and matches `RESAMPLE_HZ`; 1 kHz only if you want live-path parity with USB poll for other features.

5. **G4 still None:** even if G3 clears, `l2b_coupled_fraction` stays None in the adapter → G4 N/A → PARTIAL still reachable (G4 False is the hard fail). Confirm r02 does not accidentally require G4 True for PARTIAL (evaluator already allows G4 N/A).

---

## Rails reaffirm

- 228-byte PoAC wire: **untouched**  
- FROZEN-v1 formulas / domain tags: **untouched**  
- PV-CI baseline 184: **untouched**  
- `CHAIN_SUBMISSION_PAUSED`: **held**  
- single-committer: **operator**  
- This expand: **no code staged for product paths**; design artifact only  

**Next expected:** Claude r02 build per ranked order → `docs/a2a/tremor-fft-real-data/round-03-claude-build.md` (or implement + grok verify).
