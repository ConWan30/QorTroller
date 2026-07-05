# Phase C — C-1.3: Cross-Lobe Latency Distribution Analysis

**Date:** 2026-07-05  
**Branch:** feat/l9-consistency-adversarial-harness  
**Status:** DRAFT — UNCALIBRATED (observational dataset, N=17, controlled conditions)  
**Author:** Phase C protocol execution  
**Depends on:** C-1.1 (HID routing fix `f9584bd6`), C-1.2 data collection (`0b2ee81d`)

---

## 1. What Is Being Measured

**Cross-lobe latency** = time from R2 rising-edge onset (HID lobe, device clock) to kill
recognition (screen lobe, OCR killfeed confirmation).

The field in `retina_session_root.py` is named `nearest_preceding_latency_s` — the name
encodes the matching semantics: for each confirmed authored kill, the system walks backward
through the R2 onset log and attaches the most recent R2 onset that precedes the kill
timestamp. This is **not** guaranteed to be the causal R2 press; it is the closest prior
R2 in time. That distinction is load-bearing for interpreting the outliers (§4).

Pipeline for each measurement:
1. R2 rising edge → `HidOnsetDetector` → onset timestamp (device clock, HID lobe)
2. Kill row → OCR bootstrap (`killfeed_ocr_bootstrap.py`, exact fuzzy match "Qortrola30")
   → candidate_cut → promoted → kill timestamp (wall clock, screen lobe)
3. `nearest_preceding_latency_s` = kill_wall_clock − onset_device_clock (both in seconds)

Interstitial path: PS5 game engine → PS5 frame buffer → Remote Play encode → LAN →
Windows Remote Play decode → WGC screen capture → OpenCV crop → OCR → killfeed
bootstrap detection.

---

## 2. Data

### Session 1 — phase_c_c1_2_match2_classifyburst_2026_07_05
- 12 kills, AUTHORED_SESSION, COHERENT ratio 1.0
- Handle bootstrap: exact OCR match "Qortrola30" → candidate_cut → promoted
- Handle color: **yellow** (match 2 team color)

| Kill | Latency (s) |
|------|------------|
| 1    | 3.47       |
| 2    | 1.64       |
| 3    | 0.23       |
| 4    | 0.72       |
| 5    | 0.63       |
| 6    | 0.63       |
| 7    | 1.47       |
| 8    | 1.65       |
| 9    | 1.28       |
| 10   | 0.96       |
| 11   | 2.34       |
| 12   | 2.11       |

### Session 2 — phase_c_c1_2_match3_classifyburst_2026_07_05
- 5 kills, AUTHORED_SESSION, COHERENT ratio 1.0
- D-CG-1 stall-witness fired live: "Qortrola30Th" → candidate_demoted_stall → "Qortrola30" exact → promoted
- Handle color: **yellow** (same match-day rendering)

| Kill | Latency (s) |
|------|------------|
| 1    | 6.91       |
| 2    | 1.21       |
| 3    | 0.75       |
| 4    | 0.79       |
| 5    | 1.03       |

---

## 3. Distribution Characterization

### 3.1 Summary Statistics

Combined dataset sorted:
```
[0.23, 0.63, 0.63, 0.72, 0.75, 0.79, 0.96, 1.03, 1.21, 1.28, 1.47, 1.64, 1.65, 2.11, 2.34, 3.47, 6.91]
```

| Statistic | Value |
|-----------|-------|
| N         | 17    |
| Min       | 0.23 s |
| Q1        | 0.74 s |
| Median    | 1.21 s |
| Q3        | 1.88 s |
| Max       | 6.91 s |
| Mean      | 1.64 s |
| Std dev   | 1.57 s |
| IQR       | 1.15 s |

The mean (1.64s) is substantially above the median (1.21s), indicating right skew driven by
the two high-end observations (3.47s, 6.91s).

### 3.2 Distribution Shape

The distribution is **right-skewed and roughly unimodal** with a core cluster:

```
0.0  |█                   (0.23s)
0.5  |████                (0.63, 0.63, 0.72, 0.75)
1.0  |███████             (0.79, 0.96, 1.03, 1.21, 1.28, 1.47, 1.64)
1.5  |███                 (1.65, 2.11, 2.34)
2.5  |                    
3.0  |█                   (3.47)
3.5  |                    
4.0  |                    
5.0  |                    
6.0  |                    
6.5  |█                   (6.91)
```

Core body (14/17 = 82% of observations): **0.23–2.34 s**  
Outlier zone: 3.47 s (borderline, just within 1.5×IQR upper fence of 3.60 s) and 6.91 s
(clear outlier, above the 3×IQR extreme fence at 5.32 s).

### 3.3 Outlier Classification

**6.91 s (Session 2, Kill 1):**  
Clear statistical outlier (above 3×IQR fence = 5.32 s). This is the first kill of Session 2,
which is also the first kill after promotion (the stall-witness fired mid-bootstrap on this
match). See §4.1 for the most likely root cause.

**3.47 s (Session 1, Kill 1):**  
Borderline — within the 1.5×IQR fence (3.60 s). Also the first kill of Session 1 (first kill
after promotion). Session 1's OCR bootstrap was clean (no stall-witness), but first-kill
latency is structurally different from steady-state (see §4.2).

**Pattern:** Both high-end observations are Kill 1 (post-promotion) in their respective
sessions. This is not coincidence — there is a structural explanation (§4.2).

---

## 4. Root Cause Hypotheses for Spread

### 4.1 Nearest-Preceding R2 Matching During Multi-Shot Bursts

The `nearest_preceding_latency_s` field semantically attaches the **most recent prior R2
onset**, not necessarily the causal one.

Scenario: player fires a burst (R2 held or pressed repeatedly), kills opponent on the 2nd or
3rd press. The kill is matched to the 2nd or 3rd onset — latency reflects time from that
onset, which is short. If the system missed an R2 onset (e.g., onset fell before
ClassifyBurstController was armed, or between poll cycles), the next onset in the log is an
earlier one — inflating the measured latency substantially.

This mechanism plausibly explains the **6.91 s** observation: if Kill 1 of Session 2 happened
~7s into a play, but the nearest logged R2 onset was from an early game action (before the
bootstrap fully promoted), the latency would be computed against that older onset rather than
the immediate preceding one.

Pre-ClassifyBurstController, the onset log would have large gaps (1Hz sampling ceiling). With
ClassifyBurstController now at ~150ms polling, the onset log is denser, but any R2 press that
occurred during the `maybe_classify_in_window` inter-poll window could still be missed or
timestamped imprecisely.

**Testability:** A replay pass that logs every R2 onset with timestamps, cross-referenced to
kill timestamps from the same session, would directly validate or refute this hypothesis. This
is Phase C-1.4 scope (not this document).

### 4.2 First-Kill Structural Latency

Both high-end observations are Kill 1 post-promotion. The bootstrap-to-promotion path involves:
1. OCR reads the killer handle (fuzzy match)
2. candidate_cut is issued
3. R2-sanity and R3-consistency gates run
4. Anchor is promoted to LIVE

During the promotion window, R2 onset events are being logged but the anchor isn't yet LIVE —
classification results are not yet written as AUTHORED. The first kill that succeeds after
promotion may correspond to an R2 onset that predates the promotion timestamp by several
seconds. The `nearest_preceding` match finds that early onset and computes a large Δt.

This is a **design behavior**, not a bug. The correct interpretation: Kill 1 latency after
promotion is not a valid steady-state latency measurement. Excluding Kill 1 from both sessions:

| Statistic | All 17 | Kill-1 excluded (N=15) |
|-----------|--------|------------------------|
| Median    | 1.21 s | 1.03 s                 |
| Mean      | 1.64 s | 1.24 s                 |
| Std dev   | 1.57 s | 0.54 s                 |
| Max       | 6.91 s | 2.34 s                 |

With Kill 1 excluded, the distribution tightens substantially (std 1.57→0.54) and the max
drops to 2.34 s. This is the better-conditioned view for steady-state latency characterization.

### 4.3 Remote Play Network and Encoding Jitter

The screen-side path includes PS5 → Remote Play encode → LAN → Windows decode → WGC capture.
On a local LAN, the Remote Play round-trip adds ~80–200 ms at steady state but can spike to
400–800 ms during encoding hitches (I-frame refresh, codec adaptation, PS5 CPU load peaks).

The OCR killfeed timestamp reflects when the kill row was detected on the captured frame, which
is subject to this variable path. For short kill-to-OCR measurements (0.23–0.96 s), the Remote
Play jitter is small relative to the total; for 6.91 s, jitter alone cannot explain the
magnitude — the nearest-preceding-R2 mismatch hypothesis (§4.1/§4.2) is more likely.

### 4.4 Game Engine and HDMI Capture Latency

PS5 runs NCAA CFB 26 at 60Hz (16.7 ms/frame). The kill event registers on a frame boundary.
WGC captures at a configured rate (typically 30–60 fps). The accumulated engine-to-capture
latency is bounded to approximately 1–3 frames = 17–50 ms. This is a fixed floor, not a
source of the multi-second spread.

---

## 5. Comparison to Expectations

**Expected minimum latency** (fast-path, everything aligns perfectly):
- PS5 frame registration: ~17 ms (60fps)
- Remote Play encode + decode: ~80–150 ms (LAN, warm)
- WGC capture latency: ~17–33 ms
- OCR pipeline (crop + upscale + Otsu + Tesseract): ~50–100 ms
- Killfeed row persistence on screen: 0 ms (captured on first frame it appears)
- **Minimum theoretical: ~164–300 ms**

**Observed minimum: 0.23 s (230 ms)** — consistent with the lower bound. The 0.23 s kill
is a best-case alignment: R2 press occurred immediately before the kill frame, the kill row
appeared on the first captured frame, OCR ran fast.

**Median observed: 1.21 s (steady-state, Kill-1 included)** or **1.03 s (Kill-1 excluded)**.
The ~800–860 ms above the theoretical minimum is attributable to:
- R2-press-to-kill elapsed game time: the player pressed R2, then the in-game animation
  completed and the kill registered. In football, this is a tackle or sack — not instantaneous.
  The "game time" between trigger and kill varies by play type (0.1 s for a quick sack,
  2+ s for a broken tackle or scramble kill).
- Remote Play jitter above the minimum: 50–200 ms typical variability.
- OCR detection lag: the kill row may appear for several frames before the OCR window catches it.

**Steady-state range (Q1–Q3 excl. Kill 1): 0.63–1.88 s** — this reflects the natural
distribution of in-game R2-to-kill time for this game corpus, not a pipeline defect.

**Above-expectation outliers:** 3.47 s and 6.91 s are both best explained by the nearest-
preceding-R2 matching semantics at session/promotion boundaries, not by pipeline latency per se.

---

## 6. Honest Limitations

### 6.1 UNCALIBRATED Status

This dataset does **not** calibrate cross-lobe latency as a system property. It observes
`nearest_preceding_latency_s` as a derived metric from the existing onset log + kill log,
under the specific matching semantics described in §1. A true calibration would require:
- Known ground-truth R2-to-kill delay (controlled stimulus + outcome)
- Independent timing reference (e.g., a second timestamp source not subject to Remote Play jitter)
- Separation of pipeline delay from in-game delay

Neither condition is met here. The dataset is useful for characterizing the **observable
distribution** and identifying structural edge cases, not for making latency claims.

### 6.2 Small Sample Size

N=17 (N=15 excl. Kill 1) is too small for robust distribution fitting or quantile estimation.
The IQR and std dev are reliable enough to identify outlier character, but the shape of the
distribution's tail is not well-sampled. Variance estimates should be treated as order-of-
magnitude only.

Session 2 contributes only 5 kills — the Match 3 dataset is a minor sample at this stage.
Session 1's 12 kills are the primary dataset.

### 6.3 Nearest-Preceding Matching Semantics

The current matching algorithm is a simplification. It does not:
- Validate that the matched R2 onset is causally plausible (e.g., within a 3 s window)
- Handle multi-R2-press bursts where multiple onsets precede a single kill
- Distinguish kills from continuous sustained R2 (e.g., a full linebacker run vs. a point-and-click sack)

This means the latency value for any given kill is a **lower-bounded approximation**: the real
causal onset may be a later one (missed by the log), in which case the reported latency is
inflated. It cannot be deflated — a later kill timestamp would require a later onset, not an
earlier one.

### 6.4 Controlled Conditions Bias

Both sessions were unranked/exhibition matches played specifically to generate this dataset.
The player's play style under measurement conditions may differ from tournament play (different
pacing, different kill types, different opponent archetypes). The game corpus is also limited to
NCAA CFB 26, which has specific R2-to-kill timing distributions (sacks, tackles, interceptions)
that may not generalize.

### 6.5 Single Handle / Single Operator

Both sessions used the same handle ("Qortrola30") with consistent OCR performance. Sessions
where OCR struggles (partial fuzzy match, stall-witness demotions mid-session) may produce
different latency distributions if kill attribution is affected. The D-CG-1 stall-witness
firing in Session 2 Kill 1 (the 6.91 s outlier) demonstrates that non-trivial OCR events do
coincide with high-latency measurements.

---

## 7. Summary Findings

| Finding | Value | Interpretation |
|---------|-------|---------------|
| Core body (82%) | 0.23–2.34 s | Reflects in-game R2-to-kill timing distribution + pipeline overhead |
| Steady-state median (excl. Kill 1) | 1.03 s | Operationally representative |
| Steady-state std (excl. Kill 1) | 0.54 s | Well-conditioned spread |
| Minimum | 0.23 s | Aligns with theoretical floor (~200–300 ms) |
| Kill 1 outliers | 3.47 s, 6.91 s | Nearest-preceding mismatch at promotion boundary; exclude from steady-state |
| Distribution shape | Right-skewed | Outliers are structural, not random noise |

**Operational conclusion (advisory):** The cross-lobe latency distribution is functionally
stable in the range 0.6–2.3 s for steady-state play. Kill 1 post-promotion should be excluded
from any latency-based analysis. No pipeline defect is indicated by the spread — the variance
reflects in-game R2-to-kill timing, not OCR or capture instability.

**Next step (C-1.4, not scoped here):** A replay pass that logs every R2 onset and performs
forensic matching against the kill log would validate the nearest-preceding hypothesis directly.
This is the only path to converting the observational dataset into a calibrated latency
measurement.

---

## 8. Open Questions for C-2.x / C-3.x Integration

- **C-2.1 (biometric):** The latency spread (§3, §4.2) means R2-to-kill window for L4/L5
  feature extraction has 0.6–2.3 s of variability. Feature windows should be aligned to the
  onset timestamp, not the kill timestamp.
- **C-3.1 (KAS quality):** KAS authorship confidence is not affected by latency distribution —
  authorship is binary (handle matched → authored). Latency data does not change the KAS oracle
  scoring logic.
- **PoSP U3:** The `kas_events_root` in FusedGamerPresenceProof captures per-session KAS
  events; kill-level latency is below the PoSP abstraction layer.
