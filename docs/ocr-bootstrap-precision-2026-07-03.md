# OCR bootstrap precision + B2 premise — G1'/G0 findings (2026-07-03)

Fusion Arc Increment 1, read-only gates. **G1'** characterizes the precision of the tight-row OCR bootstrap
that replaces the marginal static-template bootstrap (feed_v1 scored this session's kills max **0.566** vs the
0.55 catch-floor → the producer failed live 0/23). **G0** checks whether the R2∧B2 dense-classify premise can
be shown from existing data. Both are read-only; no wiring, no live match (the 23-kill finding stands). PV-CI
182 unchanged; l2_ads `enabled=False`; no FROZEN-v1/PoAC/pinned/vault touch.

---

## G1' — OCR bootstrap precision (dual-instrument)

Viability was already settled (tight-row OCR reads `Qortrola30` on 12–13/25 live kill rows, rendering-
independent — full-panel OCR is mojibake). The gate question is **precision**, and it must not self-grade, so
two INDEPENDENT instruments label every crop in the dense archive (`retina_kf_crops/`, N=611):

- **Instrument A — `ocr_row_v1`** (`l9_presence/killfeed_ocr_bootstrap.tight_row_ocr`): locate a killer-slot
  row via a LOOSE feed_v1 template match (score ≥ 0.40, *below* B's 0.66 verdict floor), then READ the literal
  handle glyphs from a tight handle-centred crop (upscale ×4 + Otsu + `pytesseract` psm-7, both polarities) and
  accept only a STRICT full 10-glyph canon match (`q0rtr01a30`). Verdict by **reading**.
- **Instrument B — `template_ensemble_v1`** (`killfeed_cv.killer_slot_best` / `classify_panel`): max-over-
  anchors killer-slot score against {feed_v1, roster_v1, the R4 session-anchor library} at the frozen 0.66
  floor; refined to OWN_DEATH / OTHER_ROW / UNRESOLVED. Verdict by **scoring** template correlation.

**Independence is at the verdict MECHANISM, not location.** A clean OCR read needs a tight crop centred on the
handle, which needs its (x,y); the template-free edge-density locator misframes the glyphs ("Qortaa30" — strict
canon fails), so A borrows feed_v1 *only to locate*. A then resolves rows in the 0.40–0.66 band that B's floor
rejects — that disagreement is the independence payoff (A reads what B's score misses). The one correlated
blind spot is the deep tail (feed_v1 < 0.40: A can't even locate) — annotated, not hidden. Tooling:
`scripts/killfeed_audit_lane.py` (the shared engine `killfeed_ocr_bootstrap` is dual-consumer: this lane +
the live bootstrap, so offline and live cannot drift).

Full pass: **611 crops**, ~2.0 s/crop. Raw labels + disagreement/contact sheets in
`audits/killfeed_audit_lane_2026_07_03.{report.md,taxonomy.jsonl,contact_sheet.md}`.

### Zero-false-read bar (the hard gate) — **PASS after adjudication**

- Instrument A OWN_KILL reads: **35**.
- Candidate false reads (A=OWN_KILL contradicted by B seeing the handle in a non-killer slot): **3** — the
  bar did NOT hold *mechanically*, so all 3 were adjudicated by eye against the crops:

  | crop | A read (killer-slot) | B label | verdict |
  |------|----------------------|---------|---------|
  | `panel_1783086326328232800` | `Qortrola30` @ xf 0.16 | OTHER_ROW (killer score 0.629) | **A correct** — crop shows THREE feed rows with Qortrola30 as killer (→Whatcheese/Steawr_vex/Runner_sss); B matched the persistent "2 Qortrola30" roster at y=0.92 while its killer score fell just under 0.66 |
  | `panel_1783085400551178000` | `Qortrola30` @ xf 0.20 | OTHER_ROW (killer score 0.534) | **A correct** — own-handle in the killer slot; B matched the bottom roster entry (xf 0.92) |
  | `panel_1783086241933226900` | `Qortrola30` @ xf 0.16 | OWN_DEATH (killer score 0.519) | **A correct** — clean full-handle read in the killer slot; B's global-best at xf 0.55 is a coexisting death row or a sub-floor artifact (killer score 0.519, deep sub-floor) — either way NOT an A false read |

- **0 confirmed A false reads.** A full 10-glyph strict canon match (`q0rtr01a30`) cannot be hallucinated from
  non-handle glyphs; every "conflict" is B's killer-slot score falling sub-floor (0.53/0.52/0.63) and B's
  refine bucketing the roster/victim — i.e. **A read own-kills B's 0.66 floor missed** (the independence
  payoff, not a precision failure). The zero-false-read bar holds; no threshold tightening needed.

### Per-instrument taxonomy + UNRESOLVED drift alarm

- A `ocr_row_v1` (killer-slot READER): `{UNRESOLVED: 576, OWN_KILL: 35}`.
- B `template_ensemble_v1` (SCORER): `{UNRESOLVED: 338, OWN_KILL: 57, OTHER_ROW: 185, OWN_DEATH: 31}`.
- UNRESOLVED rate — A **94.3%** / B **55.3%**. High is EXPECTED (most of the 611 dense crops are non-kill
  background/menu); this is the pre-registered **drift-alarm baseline** — a future rendering/UI change spikes
  it *before* recall silently collapses (the two-match anchor mystery converted to a same-session alarm).

### Disagreement report + Instrument B coverage annotation

- Disagreements (OWN_KILL-relevant only; benign A-abstain-on-death/roster excluded): `B_KILL_A_MISS: 25`,
  `CONFLICT_A_KILL_B_ROSTER: 2`, `CONFLICT_A_KILL_B_DEATH: 1`.
- **B coverage: INCLUDES R4.** B's 57 OWN_KILLs by winning anchor: R4 `session_anchor_20260703…` **25** +
  `…replay2…` **28** (= 53 R4-carried) + static feed_v1 **2** + roster_v1 **2**. Because the R4 anchors were
  cut *from this session's rendering*, B is strong here — so A-B agreement corroborates independence over the
  R4-covered subset, and the 25 `B_KILL_A_MISS` are A's **recall gap**, not a B error. There is no
  `A_KILL_B_GAP` on this archive (B had coverage); the 3 A-only kills are `CONFLICT`s where B's score was
  sub-floor despite coverage.

### A's role: rendering-independent COLD START (not steady-state recall)

The load-bearing reframe: on an archive where B already holds R4 anchors cut from the session, **B's recall
(57) exceeds A's (35)** — but B needs those anchors to *exist first*, and cutting them requires catching the
first kill, which is precisely the bootstrap A owns. **A needs no per-session anchor** (it read 35 own-kills
rendering-independently), so A is the cold-start first-catch; once A's first catch seeds an R4 anchor, B's
higher-recall template ensemble takes over. A's modest recall is fine for that role — the bootstrap needs ONE
frame of ONE early kill, and a kill row persists ~5 s ≈ many dense frames, so per-frame recall compounds:
crop-level detection ratio ≈ 35/60 union-with-B ≈ **0.58**, giving first-catch-by-kill-`n` = `1 − (1−0.58)^n`
→ **~82% by kill 2, ~93% by kill 3** even before counting multi-frame persistence per kill.

---

## G0 — R2∧B2 dense-classify premise: **NEEDS-CAPTURE** (coarse-positive)

The framework invariant is R2 ∧ B2 — B2 (hitmarker redness) schedules a killfeed classification ONLY inside a
live R2 window; B2 alone never triggers (the structural anti-splice). The premise the dense-classify multiplier
leans on is that B2 reliably flashes, coupled to R2, at kill moments. **That premise cannot be shown from
existing data**, on two axes:

1. **Raw per-frame B2 at kill moments is NOT persisted.** `center_roi_redness` is computed per WGC frame and
   pushed into `TriggerHudCouplingOracle` as an in-memory ring buffer (`_roi_ts`/`_roi_v` deques, `maxlen`
   bounded); `push_roi` appends to memory only. Grep confirms **zero** per-frame B2/red writes to disk. The
   only B2 surface persisted is the RGC diag's *windowed aggregate* (`th2_coupling`/`th2_lag_ms`/`th2_coupled`
   from `extract_features()`), not per-kill B2.

2. **The coarse windowed signal is positive but not per-kill proof.** The 3 match daemon logs carry the
   periodic `th2_coupling` aggregate:

   | match log        | th2 samples | non-null | `th2_coupled=True` | median | max   |
   |------------------|-------------|----------|--------------------|--------|-------|
   | match_authored   | 42          | 93%      | 5                  | 0.127  | 0.386 |
   | match_feedv1     | 61          | 87%      | 26                 | 0.190  | 0.512 |
   | match_sessionanchor | 195      | 78%      | 55                 | 0.121  | 0.585 |

   B2↔R2 coupling is real at match granularity — the kill-heavy matches (feedv1, sessionanchor) fire far more
   `coupled_true` events (26, 55) than the death-only authored match (5), and coupling reaches 0.39–0.59. This
   is **encouraging** for the premise, but it is a windowed coupling score, not a per-kill B2 reliability
   measurement — it can't distinguish "B2 flashed at every kill" from "B2 coupled over a subset." So the strict
   conjunction premise is **needs-capture**, with a coarse-positive lean.

---

## HOLDS

**HOLD 1 (G1') — bar HELD, operator confirm.** Zero-false-read bar: 3 candidates, all 3 adjudicated A-correct
(B distracted by roster/sub-floor) → **0 confirmed false reads**, no threshold change. B has R4 coverage on
this archive so A-B agreement corroborates independence; A's value is the rendering-independent cold-start
first-catch (35 own-kills, no per-session anchor) plus the 3 kills B's floor missed. Confirm the adjudication
(the 3 conflict crops are in the contact sheet) before any wiring.

**HOLD 2 (G0) — a real fork (needs-capture, coarse-positive lean):**
- **(a) instrumented-capture-first (premise-proof):** one brief RP session with off-hot-path per-frame B2
  scalar logging at kill moments → R2∧B2 proceeds premise-shown (the conjunction's first leg proven this
  increment).
- **(b) dense-tail-now (premise-free, fastest to G3):** in-window dense-tail classify (tighter cadence inside
  the R2 window) now; let B2 earn its way in later. Neither compromises the R2∧B2 invariant.
  Operator lean per plan: dense-tail-now for speed, instrumented-capture-first for premise-proof.
