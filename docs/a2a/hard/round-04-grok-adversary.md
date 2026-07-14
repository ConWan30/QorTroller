# A2A-HARD-1 · Round 04 — grok VERIFY (ruling a) + RE-ATTACK

**2026-07-13 · grok → claude.** Adversary + verifier seat. Round-03 body integrity
`sha256=92909632090e5a861cba5fb67f2338dd4f777847ea41d59665687689cd907088` **MATCH**. Prior
`round-02-grok-adversary.md` sha=`e68b1e224d4a08db2530a02e4468df6627ac89e85d2ea7b63a4f6682dd759686`
**MATCH**. I re-grounded every R03 patch claim against source + re-ran the claimed desk surface.
I did **not** patch production code (builder seat remains Claude's).

---

## verdicts

### Ruling (a): **ACCEPT-WITH-RESERVATIONS**

A1–A4 patches are real, staged, and desk-green. The R02 **CRITICAL** false-authorship surfaces
(H1-A2 substring poison + H1-A3 offset-fraction death→kill) are **CLOSED** under exact token
equality. Residual medium attacks remain (fade-before-gap recall, falsy-ts de-dup hole + TOCTOU,
OCR-fold confusable collision). Stop criterion (**two consecutive clean rounds with zero new
breaks**) is **not** met this round.

| Claim (Claude R03) | Repo reality (grok re-check) | Tag |
|---|---|---|
| `is_own_killer_token` exact equality after `canon` | Present `killfeed_authorship.py:40-48`; `canon(killer)==own_canon` | **BUILD-NOW OK** |
| `push_killfeed_line` tokenized; killer=leftmost; death=neutral | Present L97-117; A2 poison + A3 death desk-repro green | **BUILD-NOW OK** |
| `classify_rows` uses `is_own_killer_token` | Present `killfeed_raw_reader.py:91` | **BUILD-NOW OK** |
| True positive preserved (`QorTrola30 Efram1` → own_kills=1) | Re-run `test_oracle_real_own_kill_still_authors` PASS | **BUILD-NOW OK** |
| Poison closed (`QorTro1a300` → own_kills=0 / OTHER_ROW) | Re-run A2 oracle + classify tests PASS | **BUILD-NOW OK** |
| Death closed (`Efram1 QorTrola30` → own_kills=0 / OWN_DEATH) | Re-run A3 tests PASS | **BUILD-NOW OK** |
| `kf_watch_step` → `(fire, advance)`; gap-blocked high-diff does not advance | Present `qortroller_retina_capture.py:356-369`; watcher uses it L1046-1048 | **BUILD-NOW OK** |
| Gap-then-static sequence fires at gap open | `test_watch_step_gap_then_static_sequence_eventually_fires` PASS | **BUILD-NOW OK** |
| A4 per-stash de-dup `ts == _kf_last_read_ts` | Present L1136-1138 shared path | **BUILD-NOW OK** (with residual hole — see H1-A7) |
| A5 GATED:strict-sink-seal, not patched | Sink still append-only jsonl L1166-1184; no crop-hash binding | **GATED:strict-sink-seal** (ACK) |
| `test_kf_fresh_trigger.py` 17/17 | **17/17 PASS** (re-run 1.53 s) | **BUILD-NOW OK** |
| Daemon + CLI green (Claude claimed 103) | fresh 17 + daemon 35 + CLI 43 = **95/95 PASS** (re-run); authorship+raw_reader **20/20** separate | **BUILD-NOW OK** (count base 95 verified; 103 may include extra suites not re-scoped) |
| PV-CI 183 | `python scripts/vapi_invariant_gate.py` → **PASS — 183** | **BUILD-NOW OK** |
| `py_compile` clean | re-run OK on capture + authorship + raw_reader | **BUILD-NOW OK** |
| Staged (git add) | Index has `A test_kf_fresh_trigger.py` + `M` capture/authorship/raw_reader/qortroller pack | **BUILD-NOW OK** (R01 CLAIM-MISMATCH corrected) |
| No PoAC / FROZEN / secrets | Diff surface remains retina + killfeed + pack pin + tests + A2A docs | **BUILD-NOW OK** |
| `killer_max_frac` dead in push path, kept on `__init__` | Confirmed unused in `push_killfeed_line`; still on `__init__` L83-87 | **BUILD-NOW OK** (cleanup deferred) |
| observer-only pins `RETINA_KF_FRESH_TRIGGER=true` | `scripts/qortroller.py` PACKS L62 | **BUILD-NOW OK** |

**Rails audit:** token equality is the zero-false-read-safe direction for A2/A3. The watcher + de-dup
do not introduce a new authorship verdict path. Residual false-authorship risk is only the
pre-existing OCR-fold collision class (H1-A8), not the substring/offset class.

**Staging discipline for operator:** A1–A4 code is **staged** and desk-green for the closed
attacks. Residual H1-A6/A7 are optional builder polish before dogfood; they do not re-open the
CRITICAL A2/A3 false-authorship class. Operator remains sole committer — do not commit from agent.

### What I did **not** build this round
Adversary seat: no production patches. No FROZEN / PoAC / chain / secrets. No commit / push.
Optional BUILD-NOW from the generic envelope does not apply — HARD-1 flipped roles: Claude builds,
grok attacks + verifies.

---

## attacks

Re-attack of the **patched** chain
`card → _kf_bgr → [qt-kf-fresh] → rapidocr → rows → killer-slot/canon → oracle → sink → v3 → PoSP`.
≥3 concrete residual / new-surface attacks. Desk-reproducible; no fabricated live evidence.

### H1-A6 · fade-before-gap starve (LANDS — residual A1 recall hole; MEDIUM)

| Field | Value |
|---|---|
| **surface** | `kf_watch_step` + baseline advance rule |
| **attack** | Kill appears during the 1.2 s refractory (high diff, `advance=False`). Before the gap opens, the row fades / scrolls off so `diff ≤ threshold`. Step returns `(fire=False, advance=True)` → baseline absorbs the empty post-fade frame. When the gap later opens, static empty vs new baseline → `diff≈0` → **never OCR'd**. |
| **desk proof** | `kf_watch_step(20,800,500)` → (F,F); `(20,1000,500)` → (F,F); `(0,1100,500)` → (F,T) **advance without fire**; `(0,1750,500)` → (F,T) still no fire. |
| **vs R03 claim** | R03 closes continuous high-diff until gap open (regression test). It does **not** cover high-diff entirely inside the gap then settle. |
| **severity** | MEDIUM residual recall — needs kill lifetime after appear **shorter than remaining gap**. Claude's ~5 s feed-lifetime argument bounds how often this bites; still a pure-function miss vs "every screen change eventually OCR'd." |
| **patch direction** | Latch a `pending_fire` (or sticky high-water) while gap-blocked; fire once when gap opens even if current frame is now static **or** OCR the frozen stash buffer from first high-diff frame. |

### H1-A7 · falsy-ts de-dup bypass + TOCTOU double-OCR (LANDS — residual A4; MEDIUM multiplicity)

| Field | Value |
|---|---|
| **surface** | `_rapidocr_read_and_feed` L1136-1138 |
| **attack (a) falsy ts** | Guard is `if ts and ts == _kf_last_read_ts`. When `ts` is `0.0` or `None`, the check is skipped → every call OCRs. Tune path uses `getattr(_kf_ts) or 0.0` (L1162) — if `_kf_ts` is ever missing/zero, dual drivers + repeated ticks multi-count. |
| **desk proof (a)** | Mirror of production: `ts=0.0` twice → OCR,OCR (calls=2); `ts=1.0` twice → OCR,DEDUP (calls=1). |
| **attack (b) race** | No lock around check-then-set. Fresh thread + tune tick can both observe `_kf_last_read_ts != ts` before either writes → double OCR of the same stash into oracle + sink. |
| **desk proof (b)** | Two concurrent threads with sleep yield window → `n=2` double-OCR on identical `ts`. |
| **severity** | MEDIUM multiplicity (bound_kills / own_kills / sink lines inflate) — **not** false authorship of another player. A2/A3 stay closed. |
| **patch direction** | De-dup on `ts is not None` with explicit `is not None` (not truthiness); atomic claim via lock or `compare-and-swap` on last-read ts; optional content hash of crop as secondary key. |

### H1-A8 · OCR-fold confusable-collision (LANDS — residual exact-equality; MEDIUM false-authorship class)

| Field | Value |
|---|---|
| **surface** | `canon` + `is_own_killer_token` |
| **attack** | Exact equality is on **folded** form. Distinct glyph strings that only differ by OCR confusables map to the same own handle and **author**. Example: own=`QorTrola30` → `q0rtr01a30`; killer token `Q0rTr0Ia30` (different spelling) → `is_own_killer_token` **True** → with R2 in lag → **AUTHORED_PRESENT**. |
| **desk proof** | `is_own_killer_token("Q0rTr0Ia30", canon("QorTrola30")) is True`. |
| **honest framing** | This is the intentional recall side of the OCR fold (same as `QorTroIa3O` matching you). It is **not** the R02 A2 substring bug (`QorTro1a300` correctly rejects). Collision false-authorship requires a *different real player* whose handle folds identically — rare for long unique handles, real for short/confusable handles. |
| **severity** | MEDIUM residual class; not CRITICAL under current operator handle. |
| **patch direction** | GATED:handle-collision-policy — document allowed fold; optional strict mode without fold for tournament; deny-list of known confusable near-handles. **Do not** re-open substring match. |

### H1-A5 · sink provenance ceiling (still GATED — not a F-T66B-1 code break)

| Field | Value |
|---|---|
| **surface** | `killfeed_events.jsonl` append path |
| **status** | Unchanged. Observational log; no per-event crop-SHA-256 / session_id seal. Receipt already labels observer-only. |
| **tag** | **GATED:strict-sink-seal** (ACK Claude; later HARD round) |

### Closed attacks (do not re-open)

| ID | Status |
|---|---|
| H1-A1 gap-consumed continuous high-diff | **CLOSED** by `kf_watch_step` (gap-blocked does not advance) |
| H1-A2 substring poison killer | **CLOSED** by exact `is_own_killer_token` |
| H1-A3 short-killer death → own kill | **CLOSED** by leftmost-token killer rule |
| H1-A4 dual-driver same-ts double-feed (happy path) | **CLOSED** for non-falsy equal ts; residual H1-A7 only |

---

## build-results

| Item | Result |
|---|---|
| Adversary production patches | **none** (role-correct) |
| Re-verify tests | `test_kf_fresh_trigger.py` **17/17 PASS** |
| Daemon regression | `test_qortroller_retina_capture.py` **35/35** (bundled in 52 with fresh) |
| CLI | `test_qortroller_cli.py` **43/43 PASS** |
| Core HARD surface | **95/95** (17+35+43) |
| Authorship + raw_reader blast radius | **20/20 PASS** |
| PV-CI | **PASS — 183** |
| py_compile | **OK** |
| Stage / commit | **no agent stage/commit** — Claude's index already holds A1–A4; operator sole committer |

---

## open-questions

1. **H1-A6 latch:** prefer sticky `pending_fire` (OCR current stash when gap opens even if now static) vs freeze-frame buffer of first high-diff crop? Freeze is more accurate for short-lived rows; sticky is simpler.
2. **H1-A7 priority:** is multiplicity inflation worth a lock before dogfood, or is happy-path same-ts de-dup enough for observer-only?
3. **H1-A8:** operator handle uniqueness — any known confusable near-handle in the live lobby corpus? If none, treat as documented residual, not builder-blocking.
4. **Stop criterion:** this round is **not** clean (3 residual LANDS, all MEDIUM). Next builder (R05) can either (a) patch A6+A7 then I re-verify for first clean, or (b) operator accepts MEDIUM residuals as non-blocking for dogfood and marks clean-for-scope = CRITICAL-closed only — **operator call**.
5. **A5 quickstart sentence:** still not written (Claude deferred). Side-deliverable; not a HARD-1 code gate.

---

*Round-04 — re-verified + re-attacked 2026-07-13. A2/A3 CRITICAL CLOSED · A1 primary CLOSED · residual A6/A7/A8 MEDIUM · PV-CI 183 · 17/17 HARD · 95 core. No agent commit.*
