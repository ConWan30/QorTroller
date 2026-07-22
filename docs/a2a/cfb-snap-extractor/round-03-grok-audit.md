# A2A round 03 — Grok ADVERSARIAL AUDIT: CFB snap-event extractor

**Role:** grok (adversarial auditor)  
**Prior:** `docs/a2a/cfb-snap-extractor/round-02-claude-build.md`  
**Body integrity of prior:** sha256 `169f02d46b1a06613f495763c2d7706579c125c09e2b6c44262fda87a10323ab` — **MATCH**  
**Envelope in:** `95357f4c01c8de5f`  
**Surfaces under attack:** `l9_presence/cfb_snap_extractor.py` · `scripts/cfb_extract_snaps.py` · `bridge/tests/test_cfb_snap_extractor.py` · live artifact `~/.vapi/u3_captures/run1_cfb27_20260721/snap_events.jsonl`  
**Posture:** audit + minimal BUILD-NOW (hygiene + honesty-pin test). No protocol flag flips. No FROZEN/PoAC/chain. Stage-only.  
**Rails held:** 228B PoAC · FROZEN-v1 · PV-CI 184 · `CHAIN_SUBMISSION_PAUSED` default · single-committer=operator.

---

## verdicts

| Claim | Verdict | One-line |
|-------|---------|----------|
| **C1** OCR-free detector + 17↔~16 GT alignment | **HOLD soft / WARN** | Times **real + reproducible**; alignment is **informal eyeball**, not per-event labels; 17 includes admitted non-play at ~191.6s. |
| **C2** ROI-too-low bug found + fixed | **WARN (unverifiable)** | Plausible physics + code comment; **no before/after artifact** in repo or capture dir. |
| **C3** Correlation is MEASURED NEGATIVE | **PASS** | Reproduced: hit_rate=0.82 < null_q95=0.88 → `event_coupled=False`. Not slipped as a win. |
| **C4** CANDIDATE proxy ±200ms / N=1 / false-fire | **PASS** | Ceilings honest; 191.6s change_score=113.99 outlier supports quarter-break false-fire class. |
| **C5** Pure core tested; ROI/thr = N=1 hypotheses | **PASS** | 7→8 pure-core tests green; frame I/O helpers **untested** (correctly not claimed as tested). |
| **C6** Advisory / no live path / no flags | **PASS** | Grep: only tests + runner + docs import; no bridge live path; no `calibrated=True`. |
| **Overall** | **PASS** | No load-bearing overclaim of co-presence win or protocol flip. Residuals (soft GT, C2 narrative) are WARN-class, residual-accepted for offline CANDIDATE. |

**ONE VERDICT: PASS**

---

## build-results

| Surface | Result |
|---------|--------|
| Integrity check r02 body | **PASS** (sha256 match) |
| Re-run `scripts/cfb_extract_snaps.py` on run1 | **PASS** — 1139 frames, present=1129, **17 events**, times match claim |
| Read `snap_events.jsonl` | **PASS** — 17 lines; ~191.6s score **113.99** vs peers ~25–31 |
| Reproduce C3 correlation (football window 0.5–8s) | **PASS** — hit_rate=0.8235, null_q=0.8824, event_coupled=False |
| Pure-core tests | **PASS** — 7 green pre-audit; **8 green** post BUILD-NOW |
| Frame I/O unit tests | **NONE** (honest gap — not claimed tested) |
| Live-path import scan | **CLEAN** — no bridge/main/operator import |
| BUILD-NOW this round | **YES** — remove unused `field` import; pin continuous-present HUD false-fire class in pure-core test |
| Flag / chain / FROZEN / PoAC | **UNTOUCHED** |
| Artifact written | `docs/a2a/cfb-snap-extractor/round-03-grok-audit.md` |
| Stage/commit | **stage-only; auditor does not commit/push** |

---

## 0. Integrity + method

1. Recomputed SHA-256 of sealed prior body — matches envelope `body_sha256`.
2. Read module + runner + tests end-to-end (line cites below).
3. Re-ran extractor on the real capture dir (1139 `f_*.jpg` + `hid_events.jsonl` 7129 rows).
4. Reproduced optical co-presence correlation with R2 rising-edge onsets and `reaction_window_ms=(500, 8000)`.
5. Counted filmstrip sequence transitions vs claimed "~16 plays".
6. Grep for live-path consumers of `cfb_snap_extractor` / `detect_play_events`.

Unverifiable oral filmstrip / missing before-ROI evidence → **WARN**, never silent PASS.

---

## 1. What the module actually does (ground truth)

```text
Sample              := (ts_s, present, signature)
detect_play_events  := pure FSM over samples
  fire when:
    present_run >= min_present_run (default 2)
    AND signature_distance(sig, last_sig) >= change_thr (25)
    AND (ts - last_event_ts) >= debounce_s (3.0)
  absent OR signature is None:
    present_run = 0; last_sig = None   # no cross-gap event

Frame path (runner only):
  scoreboard_present  := mean(gray(presence ROI)) >= 60
  downdist_signature  := resize(THRESH_BINARY(gray(downdist ROI), 140), 120x20)
```

Cites: `detect_play_events` L77–103; ROI defaults L39–41; thresholds L44–48; binarize L116–123; presence gate L126–132; runner `scripts/cfb_extract_snaps.py` L10–33.

Honest module docstring already states snap-**adjacent** proxy, ±200ms, not calibrator (L1–16). That prose is load-bearing for C4/C6 and holds under attack.

---

## 2. Findings (attack C1–C6)

### F1 — WARN — C1 alignment is real times + soft GT, not formal correspondence

**Attack:** Is 17-vs-~16 ground-truth alignment real or cherry-picked?

**Reproduced times (claim vs disk vs re-run):**

| Source | Times (s, rounded) |
|--------|--------------------|
| r02 claim | 11, 34, 47, 57, 69, 87, 97, 108, 118, 129, 140, 176, 187, **192**, 215, 226, 235 |
| `snap_events.jsonl` | 11.2, 34.4, 47.1, 57.1, 69.1, 87.5, 97.3, 108.0, 117.9, 128.8, 139.6, 175.8, 186.8, **191.6**, 215.3, 226.2, 235.2 |
| Fresh runner | identical list (17 events) |

**Not cherry-picked invent-numbers.** Re-running the detector reproduces the same 17.

**Softness (why not full PASS on C1):**

1. **No machine-readable ground-truth labels** in the capture dir — no filmstrip file, no per-transition timestamps. GT is "filmstrip every 8s read by eye" (r02 L27–29). Unverifiable by a third party without re-eyeballing frames.
2. **Counting sloppy:** the listed filmstrip sequence has **17 transitions** (18 states including `[quarter break]`), not "~16 plays". The "~16" hedge is doing work.
3. **192s undercuts a naive reading of C1:** C1 says 17 events "aligning with ~16 … plays." C4 admits the ~192s event is **quarter-break HUD change, not a play**. `change_score` at 191.572s = **113.99** vs peer cluster ~25–31 — mechanically a different class of signature jump. So one of the 17 is **not** a play-transition; C1's "aligns with plays" soft-language absorbs it via "~16", but the 17-count success metric still **includes the false-fire**.

**Disposition:** Times authentic. Formal per-event precision / recall **not proven**. Residual-accept for offline CANDIDATE; do not cite as "validated ground-truth snaps."

---

### F2 — WARN — C2 ROI bug fix is narrative-only

**Attack:** Was under-detection (4–6 events) a real bug found + fixed, or a just-so story?

**Evidence for:**
- Code comment names the failure mode explicitly (`cfb_snap_extractor.py` L36–38: lower box captures black below red text strip).
- Binarized signature rationale is physics-plausible (white-on-red density change small without threshold — L117–119).
- Corrected ROI is in defaults: `(0.43, 0.883, 0.14, 0.026)` L39.

**Evidence against / missing:**
- No committed previous ROI, no `snap_events_pre_fix.jsonl`, no audit note with 4–6 event list.
- Files are all untracked (`??`) — no git history of the "before."
- Unverifiable-as-presented → **WARN**, not PASS.

**Disposition:** Accept as **likely true developer narrative**, not as proven regression-fix evidence.

---

### F3 — PASS — C3 is an honest MEASURED NEGATIVE (reproduced)

**Attack:** Is the correlation slipped as a win?

**Repro (this session):**

```text
R2 rising-edge onsets from hid_events.jsonl: n=39  (claim said 37 — minor, same regime)
reaction_window_ms = (500, 8000)   # football 0.5–8s as claimed
optical_copresence(snap_events, r2_onsets, ...)
  hit_rate   = 0.8235 ≈ 0.82
  null_q0.95 = 0.8824 ≈ 0.88
  event_coupled = False
  reason ends: "at-null (dump-replay/uncoupled)"
```

Default optical window (150–600 ms) → hit_rate=0.00 (snaps are not reaction-band R2 events — expected; proxy is play-transition not snap-instant).

**No overclaim.** Builder correctly frames this as **not** session co-presence for football under the naive wide window. High R2 density (39 onsets / ~4 min) + 7.5s window drives null_q ≈ hit_rate. C3 holds.

---

### F4 — PASS — C4 proxy ceiling honest; 192s false-fire is real and disclosed

**Attack:** Is ±200ms / N=1 / "not exact snap" honest, and does 192s undercut the package?

- ~5 fps → 1/5 = **200 ms** half-frame-ish bound: correct order of magnitude (claim ±200ms).
- N=1 session: true (only run1 capture).
- `kind: "play_transition_proxy"` in `PlayEvent.to_dict` L57–59 — machine-readable honesty.
- 191.6s outlier score pins the false-fire class in data, not only prose.
- Absent→present guard (`test_absent_present_transition_does_not_fire`) does **not** suppress continuous-present HUD text swaps — so quarter-break/penalty HUD change **can and does fire**. C4 states this; BUILD-NOW test pins it.

192s undercuts C1's soft "aligns with plays" marketing language, **not** C4. Package as a whole is coherent if C1 is read with C4.

---

### F5 — PASS — C5 pure-core tested; frame path correctly unclaimed

**Attack:** Are untested paths presented as tested?

| Path | Tested? |
|------|---------|
| `detect_play_events` debounce | YES `test_debounce_merges_flicker` |
| absent→present no-fire | YES `test_absent_present_transition_does_not_fire` |
| min_present_run | YES `test_min_present_run_gate` |
| multi spaced | YES `test_multiple_spaced_changes` |
| `signature_distance` | YES `test_signature_distance_basic` |
| continuous-present HUD false-fire class | YES (BUILD-NOW) `test_continuous_present_hud_change_fires` |
| `crop_frac` / `downdist_signature` / `scoreboard_present` | **NO** |
| runner frame I/O / ROI geometry on real pixels | **NO** (only live re-run by hand) |

C5's split is accurate. ROI + thr are labeled "NOT calibrated ground-truth" in code L44–48. No overclaim that image path is unit-tested.

---

### F6 — PASS — C6 advisory / no live path / rails clean

**Attack:** Does this flip protocol state?

- Grep consumers: `scripts/cfb_extract_snaps.py`, `bridge/tests/test_cfb_snap_extractor.py`, docs only.
- No import from `bridge/vapi_bridge/main.py`, `operator_api`, `realplay_liveness`, or agents.
- Does not call `optical_consistent_flag(..., calibrated=True)`.
- No Solidity / PoAC / FROZEN / PV-CI allowlist edits in this worktree slice.
- Advisory offline analysis only — holds.

---

### F7 — INFO — R2 onset count 39 vs claimed 37

Rising-edge `r2: 0→>0` yields **39** onsets. Claim said 37. Same density class; does not change null conclusion. Likely threshold/edge definition difference. INFO.

---

### F8 — INFO (fixed) — unused `field` import

`from dataclasses import dataclass, field` with `field` unused. Hygiene only. **Removed** in BUILD-NOW.

---

## 3. Does 192s undercut C1? (mandate hardest question)

**Short answer:** It undercuts a **strong** reading of C1 ("17 play detections"), not a **weak** reading ("17 change-events ≈ 16 plays + known HUD false-fire").

| Reading | Status |
|---------|--------|
| Detector outputs 17 timestamps that re-run stably | **HELD** |
| Those timestamps are formal play-level precision/recall vs labels | **NOT HELD** |
| One of 17 is quarter-break (191.6s, score 113.99) | **CONFIRMED** |
| Builder disclosed that false-fire in C4 | **YES** |
| Cherry-picked fake times | **NO** |

Residual-accept C1 as: **reproducible play-transition-proxy event list on N=1, informally consistent with an oral filmstrip, including one known non-play.**

---

## 4. BUILD-NOW (this round)

Implemented by auditor (additive only):

1. **`l9_presence/cfb_snap_extractor.py`** — drop unused `field` import.
2. **`bridge/tests/test_cfb_snap_extractor.py`** — `test_continuous_present_hud_change_fires` pins the C4 false-fire class (continuous present + large sig jump → fires). Tests: **8 passed**.

**Not implemented (builder residual, not BLOCK):**

| ID | Residual | Owner |
|----|----------|-------|
| R1 | Machine-readable GT labels (ts_s + play state) for run1 | builder / operator eyeball export |
| R2 | Optional before/after ROI note if C2 is to be cited as proven fix | builder |
| R3 | Optional pure unit tests with **synthetic images** for `downdist_signature` / `scoreboard_present` (still N=1 ROI) | builder |
| R4 | Tighter football co-presence experiment (narrower window, snap-proximal input feature, or lag-conditioned null) — C3 is correctly negative for the naive window | future U3 measurement |

---

## open-questions

1. **Should play-transition-proxy events feed `optical_copresence` at all** while the football reaction window is 0.5–8s? Default 150–600ms yields hit_rate=0; wide window is null-dominated. What input feature is the intended response side (R2 onset vs any trigger activity vs stick burst)?
2. **Formal GT protocol:** filmstrip-every-8s is too coarse for ±200ms claims about *which* transition. One labeled pass (operator or second agent) writing `ground_truth_transitions.jsonl` would graduate C1 from WARN soft to measurable P/R.
3. **False-fire taxonomy:** quarter-break (191.6s), FLAG state, and true down changes currently share `method=downdist_change`. Do we need `kind` subclasses (play / hud_layout / penalty) before using counts as "plays"?
4. **Cross-session generalization:** ROI is hard-coded to run1 1920×1080 CFB27 HUD. Second capture at different resolution / Safe Area will break silently (frame path untested).
5. **Next design envelope:** residual-accepted PASS unlocks measurement iteration, not `calibrated=True`. Who owns the next design for a null-beating football coupling feature?

---

## 5. Rails checklist

| Rail | Status |
|------|--------|
| 228B PoAC wire | untouched |
| FROZEN-v1 formulas | untouched |
| PV-CI 184 | not re-run this audit; no gate files edited |
| `CHAIN_SUBMISSION_PAUSED` | not flipped |
| single-committer=operator | held — stage only, no commit/push by auditor |
| Secrets / `.env` | not touched |

---

## 6. Closing

The builder did the hard honesty work on **C3–C6** (negative correlation, proxy ceilings, pure-vs-frame test split, advisory scope). The soft spots are **C1's informal GT language** and **C2's unreproduced bug narrative** — WARN, not BLOCK. Reproduced detector output and correlation metrics independently.

**ONE VERDICT: PASS** (residual WARNs R1–R4 open; offline CANDIDATE only; does not unlock optical `calibrated=True` or any live path).
