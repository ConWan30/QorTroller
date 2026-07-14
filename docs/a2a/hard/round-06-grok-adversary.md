# A2A-HARD-1 · Round 06 — grok VERIFY (ruling a) + RE-ATTACK

**2026-07-13 · grok → claude / operator.** Adversary + verifier seat. Round-05 body integrity
`sha256=058518606147f0b14ccbeb18fc4d19899bcda8d701f7fe56b276999317c2843d` **MATCH**. Prior
`round-04-grok-adversary.md` sha=`8ed6f9f8e96e61530d67fc58a30d578c4dfcd193b30c726d8c7555f1470945ae`
**MATCH**. I re-grounded every R05 A6/A7 claim against source, desk-reproduced the closed sequences,
and re-attacked the latch / lock residual surface Claude invited. I did **not** patch production
code (builder seat remains Claude's). **No BUILD-NOW items this round.**

---

## verdicts

### Ruling (a): **ACCEPT — first clean round (zero new code breaks)**

A6 and A7 patches are real, staged, and desk-green. The R04 MEDIUM residuals that were **code**
(H1-A6 fade-before-gap, H1-A7 falsy-ts + TOCTOU) are **CLOSED**. Re-attack found **no new LAND
requiring a builder patch**. Remaining items are policy / gated / intentional design bounds —
not reopenings of A1–A7 or false-authorship.

| Claim (Claude R05) | Repo reality (grok re-check) | Tag |
|---|---|---|
| `kf_watch_step` → `(action, advance, latch)` 3-state | Present `qortroller_retina_capture.py:359-384`; gap-open + pending → `fire_pending`; fade holds without advance | **BUILD-NOW OK** |
| Fade sequence fires frozen crop | Desk: `(20,800,500,F)→latch`; `(0,1100,500,T)→hold`; `(0,1750,500,T)→fire_pending` | **BUILD-NOW OK** |
| Continuous high-diff still fires | Desk + `test_watch_step_gap_then_static_sequence_eventually_fires` PASS | **BUILD-NOW OK** |
| Watcher holds `pending_bgr/pending_ts`, OCRs frozen crop | Present L1048-1070; latch assigns then fire uses pending (order correct) | **BUILD-NOW OK** |
| Stash assignment is new object (not in-place mutate of prior pending) | `_kf_bgr = _u8_from_scale(...)` L591; ROI partial-width → `ascontiguousarray` **copies** (desk: mutate source leaves pending mean intact) | **BUILD-NOW OK** (see residual note H1-A9b) |
| De-dup `ts is not None` (not truthiness) | Present L1161; desk `ts=0.0` twice → OCR,DEDUP | **BUILD-NOW OK** |
| `_kf_read_lock` atomic claim in `__init__` | Present L133-135 + L1158-1163; 8-thread race → OCR count **1** | **BUILD-NOW OK** |
| Tune path `or 0.0` + watcher `ts is None` skip | Tune L1187; watcher L1057 — production never multi-OCR via bare `None` | **BUILD-NOW OK** |
| A8 not patched → operator policy | Confirmed: fold equality still authors confusable near-handle | **GATED:handle-collision-policy** (ACK) |
| A5 not patched | Sink still append-only jsonl; no crop-hash seal | **GATED:strict-sink-seal** (ACK) |
| HARD suite 19 | **19/19 PASS** (1.58 s) | **BUILD-NOW OK** |
| Daemon + CLI | `test_qortroller_retina_capture` + `test_qortroller_cli` **78/78** (35+43) | **BUILD-NOW OK** |
| Authorship + raw_reader blast radius | **20/20 PASS** (token rule untouched) | **BUILD-NOW OK** |
| Core desk surface | **19+78 = 97** (Claude's "105" not re-scoped; measured 97 + 20 authorship = 117 with blast radius) | **BUILD-NOW OK** (count honesty) |
| PV-CI 183 | `python scripts/vapi_invariant_gate.py` → **PASS — 183** | **BUILD-NOW OK** |
| `py_compile` clean | OK on capture + authorship + raw_reader | **BUILD-NOW OK** |
| Staged (git index) | Index holds A1–A7 code + HARD tests + hard A2A docs; R04 was untracked → staged this round with R06 | **BUILD-NOW OK** |
| No PoAC / FROZEN / secrets | Diff surface remains retina + killfeed + pack pin + tests + A2A docs | **BUILD-NOW OK** |
| A2/A3 still CLOSED | Poison + death + true-positive tests still green under R03 token rule | **BUILD-NOW OK** |

**Rails audit:** A6 latch is the correct recall direction for fade-inside-refractory. A7 claim-before-OCR
under a microsecond lock is the correct multiplicity direction for dual drivers. Neither path
touches authorship tokens or invents a second verdict surface. Residual false-authorship risk
remains only the pre-existing OCR-fold class (A8), not substring/offset.

---

## re-attack (mandated probes + residual notes)

### H1-A6 · fade-before-gap — **CLOSED** (re-verify)

| Field | Value |
|---|---|
| **desk proof** | Pure stepper sequence above; regression `test_watch_step_fade_before_gap_still_fires_pending` PASS |
| **watcher wiring** | `pending_bgr is not None` feeds `has_pending`; fire calls `_rapidocr_read_and_feed(pending_bgr, pending_ts)` then clears |
| **vs R04 attack** | R04's `(0,1100)` advance-without-fire is gone: advance stays False while pending |

### H1-A7 · falsy-ts + TOCTOU — **CLOSED** (re-verify)

| Field | Value |
|---|---|
| **desk proof (a)** | `ts=0.0` twice → `['OCR','DEDUP']` under production guard shape |
| **desk proof (b)** | 8 concurrent threads same ts → OCR count **1** |
| **ts=None probe** | Guard skips equality when `ts is None` (would re-OCR if called). **Production paths do not call that way**: watcher continues on `ts is None`; tune uses `or 0.0`. Closed for live dual-driver surface |

### H1-A8 · OCR-fold confusable — still **GATED:handle-collision-policy**

Unchanged. Not a code break. Operator chooses (i) accept residual / (ii) deny-list / (iii) no-fold tournament mode. Substring match stays OFF.

### H1-A5 · sink provenance — still **GATED:strict-sink-seal**

Unchanged. Later HARD round + quickstart line. Not a F-T66B-1 code gate.

### H1-A9 · single-slot latch capacity (re-attack; **DOCUMENTED design bound — not BUILD-NOW**)

| Field | Value |
|---|---|
| **surface** | `kf_watch_step` latch only when `not has_pending` + watcher single `pending_bgr` |
| **attack** | Kill1 latches in refractory; kill2 appears (high-diff) while `has_pending=True` → `latch=False` (second crop never frozen). Gap open fires kill1 only; baseline advances to current; if kill2 is now static vs that baseline → **miss kill2** until a later change. |
| **desk proof** | `kf_watch_step(20,1000,500,True)[2] is False` — cannot re-latch while pending |
| **severity** | MEDIUM residual **recall under multi-kill within one min-gap** — not false authorship; not a reopen of A6's single-fade case |
| **honest framing** | Min-gap single-flight already caps OCR rate at ~1/1.2s. Latch trades "OCR whatever is on screen at fire" for "OCR the first change before fade." Multi-kill inside one refractory is a capacity bound of that design, not a missing `if`. Queue/depth-N latch is optional polish if live dogfood shows multi-kill clusters dominating misses. |
| **tag** | **DOCUMENTED:single-slot-latch-bound** — not BUILD-NOW; does **not** block clean-for-code-breaks |

### H1-A9b · latch reference durability (re-attack; **DOCUMENTED residual — not LAND**)

| Field | Value |
|---|---|
| **surface** | `pending_bgr, pending_ts = bgr, ts` (no `.copy()`) |
| **probe** | Partial-width ROI (live KF shape): `_u8_from_scale` → real copy; mutate source buffer → pending intact. Full-row C-contiguous slice: can alias and corrupt after source rewrite. |
| **live path** | KF ROI is partial-width → non-contiguous → copy in practice. Freeze holds for the production crop geometry. |
| **tag** | **DOCUMENTED:latch-ref-no-explicit-copy** — optional hardening `pending_bgr = bgr.copy()`; not BUILD-NOW under current ROI |

### Closed attacks (do not re-open)

| ID | Status |
|---|---|
| H1-A1 gap-consumed continuous high-diff | **CLOSED** (latch holds until fire) |
| H1-A2 substring poison killer | **CLOSED** (exact token equality) |
| H1-A3 short-killer death → own kill | **CLOSED** (leftmost killer) |
| H1-A4 dual-driver same-ts double-feed | **CLOSED** (incl. falsy `0.0` + lock) |
| H1-A6 fade-before-gap starve | **CLOSED** (pending crop latch) |
| H1-A7 falsy-ts + TOCTOU | **CLOSED** (`is not None` + `_kf_read_lock`) |

---

## build-results

| Item | Result |
|---|---|
| Adversary production patches | **none** (role-correct; no BUILD-NOW set) |
| Re-verify HARD | `test_kf_fresh_trigger.py` **19/19 PASS** |
| Daemon + CLI | **78/78 PASS** |
| Authorship + raw_reader | **20/20 PASS** |
| Core HARD surface (fresh+daemon+CLI) | **97/97** |
| PV-CI | **PASS — 183** |
| py_compile | **OK** |
| Stage | **round-04** (was untracked) + **round-06** staged for operator; no code re-stage needed (Claude's A6/A7 already in index) |
| Commit / push | **none** — operator sole committer |

---

## open-questions

1. **Stop criterion (operator call, still open):** R06 is the **first clean round for new code breaks** under ruling (a). One more clean re-verify (R07 adversary, no new LAND) **or** operator **(b)** clean-for-scope closes HARD-1 subject-#2. Claude recommended **(b)**; I **concur** — CRITICAL false-authorship (A2/A3) and both cheap code residuals (A6/A7) are closed; remaining A8/A5/A9 are policy, gated seal, or single-flight design bound. Live dogfood is the real recall oracle.

2. **H1-A9 depth-N latch:** only worth a builder ticket if live multi-kill clusters inside 1.2s dominate missed own_kills. Default: leave single-slot.

3. **H1-A9b `.copy()`:** one-line hardening if ROI geometry ever becomes full-row contiguous; optional.

4. **A8 policy pick:** (i) accept for `QorTrola30`-class handles / (ii) deny-list / (iii) tournament no-fold — operator only.

5. **A5:** still deferred later HARD round + quickstart sentence.

6. **Count honesty:** measured core surface **97** (19+78), not Claude's "105"; authorship blast **+20**. No functional mismatch — labeling only.

---

## stop-criterion status

| Bar | Status |
|---|---|
| CRITICAL false-authorship (A2/A3) | **CLOSED** |
| Code residuals A6/A7 | **CLOSED** (this re-verify) |
| New LAND / BUILD-NOW this round | **none** |
| First clean round (code breaks) | **YES — R06** |
| Two consecutive clean / operator (b) | **pending operator** |
| A8 / A5 / A9 | policy / gated / design-bound — non-blocking for clean-for-code |

---
*Round-06 — re-verified + re-attacked 2026-07-13. 19 HARD · 78 daemon+CLI · 20 authorship · PV-CI 183.
No production patch. First clean code-break round. Operator sole committer.*
