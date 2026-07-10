# P0-A — Presence-Oracle Separation Study Design

**Status:** DESIGN ONLY (2026-07-09). Loop cycle 1 deliverable.  
**Rev:** negative-class / claim-scope sharpen (Claude corpus audit — derived negative, single-operator honesty).  
**Audience:** Claude (audit → harness) · operator (sessions + commits).  
**Rails:** `advisory=True` · `cert_scope=developer_self` · `population_certified=False` ·  
`verifier_independence=False` · offline analysis only · **zero capture-path touch** · no new  
FROZEN-v1 · PV-CI 182 unchanged.  
**Related:** `docs/qortroller-ai-loop-collab-2026-07-09.md` · `docs/session-handoff-for-grok-2026-07-09.md` ·  
`audits/rp-close-1-ledger-2026-07-07.md` · `l9_presence/README.md` (Stream A banked validation).

---

## 1. THE CLAIM (one sentence)

**This study establishes a pre-registered, offline, developer_self operating point for human-vs-modeled-automation separation on the L9 causal-presence oracle (input→rendered-camera coupling) — using a constructed negative class over the same human sessions — and does NOT establish human-vs-real-cheat-hardware detection, identity separation, multi-player population certification, or compromised-host resistance.**

Expanded (still one claim):

> On a declared positive class (live human aim sessions from one operator’s `sessions_l9` corpus) and a **derived** negative class (modeled automation: synthetic full camera-track injection via `synth_adversary`, with time-shuffle as the causality floor), the presence oracle’s scalar score separates the two classes by a gap that clears pre-registered floors.

**Claim-scoping word that must not be dropped:** **modeled** automation. There is no second real corpus of cheats on disk; the negative is constructed (§4). Over-reading as “field AC works against Cronus/XIM” is out of scope until P2.

---

## 2. Presence oracle in scope

### 2.1 Primary (single discriminator)

| Field | Choice |
|-------|--------|
| **Name** | **L9 Stream A — causal input→output coupling** |
| **Scalar** | `coupling_score` ∈ [0, 1] — max \|causal Pearson r\| of aim-stick response vs on-screen camera angular velocity over lag window |
| **Module** | `l9_presence.coupling.InputOutputCouplingOracle` → `extract_features().coupling_score` |
| **Session entry** | `l9_presence.session_recorder.analyze_session_data(SessionData)` → `coupling_score` |
| **Binary presence flag (runtime)** | `coupled := coupling_score >= COUPLING_THRESHOLD` with default `COUPLING_THRESHOLD = 0.20` (`coupling.py`) |
| **Causality honesty** | same session’s `negative_control()` = coupling with **time-shuffled** input; must collapse |

**Why this primary (tied to existing validation):**

From `l9_presence/README.md` Stream A (banked, 2026-05-21):

- Human coupling **0.29–0.45**
- Negative control (shuffle) **~0.02**
- Causal lag **25–83 ms** (low-latency); P4 showed high-latency streams still couple (up to ~0.955 at 400–500 ms; `LAG_MAX_MS` default 500)
- Full synthetic camera takeover → coupling **~0.05** across static/snap/track

This is the only presence surface with a **published human-vs-automation gap** already measured on this codebase. It matches the cloud/RP thesis: injected / upstream-synthesized camera motion fails the causal link.

### 2.2 Secondaries (report-only; do not drive the SEPARATED verdict)

| Secondary | Role | Why not primary for P0-A v0 |
|-----------|------|----------------------------|
| **`neg_control_margin`** = `coupling_score − negative_control` | Causality honesty gate on human sessions | Methodological control, not the automation class |
| **`decoupled_energy`** | Residual / partial-assist diagnostic | README: partial low-energy assist can hide under human residual; use for *diagnostics + injection sweep*, not primary OP |
| **NQPV fusion** | Match-path multi-surface presence | Different data surface (bridge `nqpv_cocapture_log`); C-4.2 marks CALIBRATED within developer_self; not the same scalar as L9 coupling; **Phase 2** once a join recipe is fixed |
| **PoEP / L6B** | Reflex / embodied challenge | C-4.2: `UNCALIBRATED`, `POEP_L6B_N=0`, flags default-OFF — **out of scope until N≥50 science** |
| **L9 Stream B** (`_SEP_FEATURES` LOO) | Identity-ish play-style fingerprint | Explicitly **not** the presence claim; EER-class / multi-player LOO is the identity yardstick we refused for P0-A |
| **PoSP / KAS / BCC Match** | Assertion-plane session quality | Admission / corpus hygiene for *which sessions count as match-grade*; not the human-vs-automation scalar |

### 2.3 PoCP relationship

`l9_presence/pocp.py` commits over `(coupling, lag_ms, negative_control, decoupled_energy, …)` with domain tag `QORTROLLER-L9-POCP-v0` (**candidate**, not FROZEN). The study scores the **underlying scalars**; it does **not** require minting new PoCP commitments or anchoring them.

---

## 3. Pre-registered metric

### 3.1 Unit of analysis

One **scored session** = one `SessionData` that returns a defined `coupling_score` from `analyze_session_data` (status ≠ `insufficient_aim_activity`).

Sessions with insufficient aim activity are **dropped from both class counts** and reported in a `skipped` bucket (not counted as automation).

### 3.2 Primary separation statistic (pre-registered)

```text
gap = median(C_human) − median(C_auto)

where C_* is the multiset of coupling_score values for scored sessions in that class.
```

**Decision rule (declared before results; do not retune in the same PR as first run):**

```text
SEPARATED  iff  ALL of:
  (M1)  n_human_scored  >= N_MIN_POS
  (M2)  n_auto_scored   >= N_MIN_NEG
  (M3)  median(C_human) >= TAU_HUMAN          # floor: real presence above runtime threshold
  (M4)  median(C_auto)  <= TAU_AUTO           # ceiling: automation below / near collapse
  (M5)  gap             >= GAP_MIN            # pre-registered separation magnitude
  (M6)  causality honesty on human class:
          median(negative_control_human) <= TAU_NC
          AND median(neg_control_margin_human) >= GAP_MIN
```

### 3.3 Pre-registered constants (v0)

| Symbol | Value | Rationale |
|--------|-------|-----------|
| `TAU_HUMAN` | **0.20** | = `COUPLING_THRESHOLD` default in `coupling.py` (env `L9_COUPLING_THRESHOLD`) — same floor the runtime oracle uses for `coupled` |
| `TAU_AUTO` | **0.10** | Below threshold with margin; banked full-injection ~0.05; shuffle ~0.02 |
| `GAP_MIN` | **0.15** | Conservative vs banked human−auto gap (~0.24–0.40 using 0.29–0.45 vs ~0.05); refuse to set from the first run’s data |
| `TAU_NC` | **0.10** | Shuffle must collapse; banked ~0.02 |
| `N_MIN_POS` | **8** | First honest OP floor (developer_self) |
| `N_MIN_NEG` | **24** | 8 human seeds × 3 injection modes (see §4) |

### 3.4 Diagnostic statistics (report; non-deciding)

| Statistic | Definition | Use |
|-----------|------------|-----|
| `separation_ratio` | `median(C_human) / max(median(C_auto), 1e-6)` | Human-readable; **not** the SEPARATED gate (ratio unstable near zero auto) |
| `mean` / `p25` / `p75` of each class | Robustness of median | Detect outlier-driven gap |
| Per-mode auto medians | static / snap / track separately | Mode-specific failure |
| Injection sweep at b ∈ {0, 0.25, 0.5, 0.75, 1.0} mode=`snap` | Reuse `synth_adversary.evaluate` pattern | Partial-assist honesty (README limit) |
| Optional AUC | ROC of coupling_score human vs auto | Only if both classes ≥ N_MIN; **not** required for SEPARATED |

### 3.5 Class definitions

| Class | Definition | Real or derived? |
|-------|------------|------------------|
| **Positive (human-live)** | `sessions_l9/*.npz` with real stick + real camera tracks; scored `coupling_score` defined | **Real captures** (developer_self) |
| **Negative (modeled automation)** | **Derived only** — §4.1 `synth_adversary` full camera injection on those same sessions | **Constructed** — no real-cheat corpus on disk |
| **Floor control (not a class)** | Per-positive `negative_control` time-shuffle (~0.02 banked floor) | **Derived method control** for M6; **not** members of C_auto |

**Corpus fact that forces this split (Claude audit 2026-07-09):** the ~59 `sessions_l9` files are **all** developer_self human sessions. They are the entire positive class. There is **no second real corpus** of automation sessions to score. Therefore the negative class **must** be constructed; calling it “real automation” would be a documentation lie.

---

## 4. Negative-class construction (load-bearing)

### 4.0 Principle — derived, not real

```text
POSITIVE  = real human sessions already on disk (sessions_l9)
NEGATIVE  = DERIVED from those sessions (no independent cheat recordings in v0)
FLOOR     = time-shuffle negative_control on each positive (causality honesty)
```

| Candidate in-repo | Role in v0 | Strength |
|-------------------|------------|----------|
| **`synth_adversary` full injection (static/snap/track)** | **PRIMARY negative class** → supplies `C_auto` for the gap | Strongest available offline model of decoupled camera |
| **Time-shuffle `negative_control()`** | **FLOOR control** → M6 only; banked ~0.02; honest lower bound on “uncaused” coupling | Methodological; not the auto class |
| **RP-replay / killcam / spectator** | Deferred (later) | Stronger *field* negative when labeled |
| **Real Cronus/XIM captures** | P2 board — **out of this study** | Required before any human-vs-real-cheat claim |

**Recommend (locked for Phase-1 harness):** primary = `synth_adversary` · floor = shuffle · RP-replay later · Cronus/XIM = P2.

### 4.1 Primary negative — paired synthetic full takeover (modeled automation)

**Method:** for each scored human session `s`, build three scripted sessions (do not write over the human `.npz`):

```text
s_static = synthesize(s, injection=1.0, mode="static", seed=SEED+i)
s_snap   = synthesize(s, injection=1.0, mode="snap",   seed=SEED+i)
s_track  = synthesize(s, injection=1.0, mode="track",  seed=SEED+i)
```

via `l9_presence.synth_adversary.synthesize` / `MODES = ("static", "snap", "track")`.  
`label` on the result is `"scripted"`; stick streams are byte-copied from the human; camera is replaced.

**What this models (honest):** *modeled* aimbot / upstream-synthesized **camera** motion while a human still holds the stick — the camera is **not** caused by the stick. Paired stick activity means the gap is not “bots don’t move the stick.”

**Why this is a strong negative for the *scoped* claim (human vs modeled automation):**

1. **Matches the oracle’s threat model** (`coupling.py`): high coupling for human; collapses for injected/upstream-synthesized motion.  
2. **Paired design** — same stick distribution; only camera track replaced → causal decoupling, not input poverty.  
3. **Already banked:** README Stream A: full takeover → coupling ~0.05 across three modes; `synth_adversary.evaluate` exists.  
4. **Three modes** — static / snap / track — avoid a single cartoon defining “automation.”  
5. **Only honest option given the corpus** — no real negative pile exists; constructing is correct, not a shortcut.  
6. **Deterministic + offline** — zero capture-path; harness-reproducible.

**Why this is still a model (ceiling — see §7):**

- Not a real Cronus/XIM/firmware aimbot session.  
- Not an input-masked cheat that forges stick to match camera (`synth_adversary.py` L19–23).  
- Partial injection (`b < 1`) can evade coupling (README); injection sweep is **diagnostic only**, not part of SEPARATED.

### 4.2 Floor control — time shuffle (not a member of C_auto)

For every human session, `analyze_session_data` returns `negative_control` via `InputOutputCouplingOracle.negative_control()` (`coupling.py`: shuffle predicted aim track, recompute max \|r\|). Banked floor **~0.02**.

**Role:**

- **Not** counted in `median(C_auto)` and **not** used to inflate the gap.  
- **Gate M6:** human class must show collapse — `median(NC) ≤ TAU_NC` and `median(neg_control_margin) ≥ GAP_MIN`. If not → `UNVERIFIABLE` / `CAUSALITY_FAIL` even if the synth gap looks large.  
- Documents the **honest lower bound** on uncoupled coupling under the same lag-search machinery (guards lag-search artifacts).

### 4.3 Explicitly deferred negatives (not v0)

| Construction | Status in v0 |
|--------------|--------------|
| Real RP-replay / killcam / spectator decoupled capture | Deferred — stronger field negative when labeled |
| Real Cronus/XIM capture pass | **P2** — required before any “real cheat hardware” claim |
| NQPV “uncoupled” fusion rows / `hw_nqpv_*.json` | Different surface; Phase-2 + adapter only |
| Identity Stream B LOO null | Wrong claim class |

---

## 5. N-plan

### 5.1 Phase 1 — first honest OP (offline, developer_self)

**Population honesty (pinned):**

| Fact | Implication for the OP |
|------|------------------------|
| Positive pool ≈ **59** `sessions_l9/*.npz` | Entire positive class is this pile (after label/score filters) |
| **1 operator** / `developer_self` | Single-human presence/liveness claim — **legitimate for a first presence OP** (presence ≠ multi-player identity) |
| No second human required for v0 SEPARATED | Multi-player expansion is growth, not a prerequisite for first OP |
| Negative count is **derived** | `n_auto = n_human_scored × 3` (modes); not independent sessions |

| Item | Plan |
|------|------|
| **Positive corpus** | **Only** `sessions_l9/*.npz` (Phase-1). Prefer `label=="human"` when present; report count excluded. Optional *diagnostic* add of cocapture L9 views is **off by default** for first OP (keep one primary pile). |
| **Negative corpus** | **Derived in-process** from each scored positive via §4.1 — never loaded from a cheat directory |
| **Floor control** | Shuffle NC on each positive (§4.2) |
| **Conditions** | One condition set; report backend mix if known (warning, not auto-fail) |
| **N_MIN for first honest OP** | `n_human_scored ≥ 8` and `n_auto_scored ≥ 24` (8×3 modes) — floors, not “use all 59” |
| **Capacity note** | Up to ~59 human scored possible offline without new captures; first OP may use a fixed subset or full pool — report `n_available` vs `n_scored` |
| **Seed** | `SEED=0` default; printed in report |
| **Player tags** | Report `player` histogram; v0 **allows n_players = 1** explicitly |

### 5.2 How BCC Match feeds the corpus

| Fact | Implication |
|------|-------------|
| BCC Match (`l9_presence/bcc_match.py`) stores **match-presence artifacts** (PoSP/KAS assertion-plane), default **NONE** L4 — **not** L9 coupling vectors | It is **not** a direct input to `coupling_score` |
| Admission G1–G8 requires PoSP SYNCHRONIZED + coherence ≥ 0.50 + authorship | Match-lane rows mark **which live matches were multi-surface certified** |
| Store path `bcc_match/` (gitignored; may be empty until harvest runs) | Optional feeder |

**v0 feeder role (honest, mechanical):**

1. **Phase 1 (this design):** primary positives = `sessions_l9` / optional `cocapture_l9` L9 views. BCC Match **not required**.  
2. **Phase 2 (after first OP):** if/when operator harvests BCC Match rows for RP matches M14/M17/…, those `session_id`s become a **whitelist** for “match-grade human” expansions — *only if* a corresponding L9/cocapture `.npz` (or rebuildable SessionData) exists for that session. No silent use of PoSP alone as a coupling score.  
3. BCC Match **never** supplies the automation class.

### 5.3 Growth path (not blocking first OP)

| Stage | N target | Notes |
|-------|----------|-------|
| First honest OP | ≥8 human scored / ≥24 auto | developer_self OK |
| Stability re-run | ≥15 human scored | Same constants; must not retune GAP_MIN |
| Multi-player presence | ≥3 players × ≥5 sessions | Still human-vs-modeled-auto, not identity LOO |
| Field-negative add-on | + real RP-replay / Cronus-XIM | New study version — required before any real-cheat claim |

---

## 6. Closed-enum study verdicts

```text
SEPARATED
  M1–M6 all true under pre-registered constants.

INSUFFICIENT_N
  Any of n_human_scored < N_MIN_POS or n_auto_scored < N_MIN_NEG
  (after skips). Metrics may be reported as diagnostic only.

INCONCLUSIVE
  N floors met, causality honesty (M6) held, but M3–M5 failed
  (human too weak, auto too strong, or gap < GAP_MIN).

UNVERIFIABLE
  No scorable human sessions; harness/IO failure; or M6 causality honesty
  failed (human negative_control does not collapse); or positive corpus
  empty after filters.

# Optional sub-label (may fold into UNVERIFIABLE in harness output):
CAUSALITY_FAIL
  Explicit alias when M6 fails — human coupling not causally validated.
```

**Rules:**

- Exactly one primary verdict per study run.  
- `INSUFFICIENT_N` beats `INCONCLUSIVE` (don’t call inconclusive without N).  
- Never emit `SEPARATED` if any constant was changed after seeing the run (version bump required: study schema `p0a-presence-op-v1` etc.).

---

## 7. Honest non-claims / limits

### 7.1 Ceiling forced by the negative class (primary)

| Claim people might over-read | Honest ceiling |
|------------------------------|----------------|
| “Separates humans from cheats” | Separates humans from **modeled** automation (`synth_adversary` full camera injection) |
| “Works against real hardware cheats” | **False until P2** Cronus/XIM (or equivalent) real corpus |
| “Population-validated anti-cheat OP” | **Single-operator developer_self** presence OP; `population_certified=False` |
| “Independent automation sessions” | Negatives are **derived from the same positive `.npz` files** — paired, not an independent field sample |

### 7.2 Full non-claims list

This study / harness / report **does not prove**:

1. **Human-vs-real-cheat-hardware** separation (Cronus/XIM/cloud-bot telemetry) — needs P2.  
2. **Identity** — who among N enrolled humans is playing (Stream B / AIT / L4 LOO).  
3. **Per-player FAR/FRR** as tournament operating points.  
4. **`population_certified=True`** — remains **False**; C-4.2 rails stay in force.  
5. **Multi-operator generalization** — positive class is one operator’s `sessions_l9` pile (~59).  
6. **Compromised-host resistance** — self-witnessed rig; EVENT-BIND/PORT-CERT limits unchanged.  
7. **Partial-assist detection** as the SEPARATED claim — injection sweep is diagnostic only.  
8. **Input-masked aimbots** that forge matching stick (`synth_adversary` non-goal).  
9. **RP-specific density/OCR authorship** (M14–M18) — orthogonal; coupling ≠ kill authorship.  
10. **PoEP/L6B readiness** — N=0.  
11. **Enforcement** — no `isFullyEligible` / hard BLOCK from this OP alone.  
12. **New FROZEN-v1 / PoAC edit** — none.  
13. **Capture-path changes** — harness is offline only.  
14. **NQPV / `hw_nqpv_*.json` as coupling inputs** — Phase-2 + adapter only.

### 7.3 What it *does* support (if SEPARATED)

> Under **developer_self / single-operator** scope, the L9 causal-presence scalar separates live human aim sessions from **modeled** full-camera-takeover sessions (constructed by `synth_adversary` on the same stick tracks) by a pre-registered gap, with time-shuffle causality intact — a first **human-vs-modeled-automation presence OP**. Suitable to cite in a narrow RP/cloud wedge thesis as *oracle viability evidence*, not as field AC certification.

---

## 8. Design-level acceptance tests (harness must pin)

| ID | Pin |
|----|-----|
| **T1** | Metric path is identical for both classes: both call `analyze_session_data` (or shared pure helper); no special-case scoring for `"scripted"`. |
| **T2** | No negative→positive leakage: synthesized sessions never enter the human multiset; human `.npz` files never rewritten on disk by the harness. |
| **T3** | Pre-registered constants are module-level (or frozen dict) and asserted in tests; SEPARATED path uses only those symbols. |
| **T4** | Fail-closed on insufficient N → verdict `INSUFFICIENT_N`, never `SEPARATED`. |
| **T5** | `insufficient_aim_activity` excluded from both class counts; counted in `skipped`. |
| **T6** | Causality fail (M6) → not `SEPARATED` (→ `UNVERIFIABLE` / `CAUSALITY_FAIL`). |
| **T7** | Paired construction: each auto session is `synthesize(human_i, injection=1.0, mode=m)`; n_auto = n_human_scored × 3 when all score. |
| **T8** | Report includes `cert_scope=developer_self`, `population_certified=False`, `advisory=True`, study schema id, seed, constant table. |
| **T9** | Zero imports of dualshock capture loops / daemon stamp paths for scoring (offline-only). |
| **T10** | Optional: golden fixture — tiny synthetic SessionData with known coupling behavior in unit tests (not live corpus). |

**Suggested harness layout (Claude builds; not this PR):**

- `l9_presence/presence_separation_study.py` (pure) + `scripts/run_p0a_presence_study.py` (CLI)  
- Output: `audits/p0a-presence-op-<date>.json` + `.md`  
- Tests: `l9_presence/tests/test_presence_separation_study.py`

---

## 9. Operator-decisions table

| ID | Decision | Default in this design | Operator |
|----|----------|------------------------|----------|
| **D-P0A-1** | Primary oracle = L9 Stream A `coupling_score` | Yes | ☐ accept ☐ amend |
| **D-P0A-2** | Negative = **derived** paired `synth_adversary` full injection × 3 modes; shuffle = floor only; not real-cheat corpus | Yes | ☐ accept ☐ amend |
| **D-P0A-3** | Decision metric = median gap with M1–M6 | Yes | ☐ accept ☐ amend |
| **D-P0A-4** | `GAP_MIN=0.15`, `TAU_HUMAN=0.20`, `TAU_AUTO=0.10`, `TAU_NC=0.10` | Yes | ☐ accept ☐ amend |
| **D-P0A-5** | First OP N floors: 8 human / 24 auto | Yes | ☐ accept ☐ amend |
| **D-P0A-6** | BCC Match Phase-2 feeder only (not required for first OP) | Yes | ☐ accept ☐ amend |
| **D-P0A-7** | NQPV / PoEP out of primary SEPARATED gate | Yes | ☐ accept ☐ amend |
| **D-P0A-8** | Proceed to Claude audit → harness build | Hold for GO | ☐ GO ☐ hold |

---

## 10. CODE-TRUTH

Claude: verify line-by-line. Paths relative to repo root `vapi-pebble-prototype/`.

### 10.1 Oracle math

| Symbol / API | Location | Notes |
|--------------|----------|-------|
| `COMMON_RATE_HZ` default 120 | `l9_presence/coupling.py` ~L53 | Resample grid |
| `LAG_MIN_MS` / `LAG_MAX_MS` (0 / 500) | `coupling.py` ~L56–64 | Causal lag window; P4 widened to 500 |
| `COUPLING_THRESHOLD` default **0.20** | `coupling.py` ~L73–74 | Runtime `coupled` floor; study `TAU_HUMAN` |
| `HUMAN_COUPLING_BASELINE` default 0.55 | `coupling.py` ~L76–78 | Normalization only; **PROVISIONAL** — study does **not** use this as the SEPARATED gate |
| `InputOutputCouplingOracle.extract_features` | `coupling.py` ~L280–322 | Returns `coupling_score`, `decoupled_energy`, `lag_ms`, `coupled` |
| `InputOutputCouplingOracle.negative_control` | `coupling.py` ~L325–332 | Time-shuffle control |
| `decoupled_energy_fraction` | `coupling.py` ~L133+ | Residual axis |
| `analyze_session_data` | `l9_presence/session_recorder.py` ~L165–186 | Returns `coupling_score`, `negative_control`, `neg_control_margin`, `coupled`, or `status=insufficient_aim_activity` |
| `analyze_session(path)` | `session_recorder.py` ~L189–191 | Load `.npz` + score |
| `load_session` / `SessionData` | `session_recorder.py` | Fields: `in_ts, in_sx, in_sy, mo_ts, mo_yaw, mo_pitch, label, in_fire?, player?` |

### 10.2 Negative-class generator

| API | Location | Notes |
|-----|----------|-------|
| `MODES = ("static", "snap", "track")` | `l9_presence/synth_adversary.py` ~L34 | |
| `injected_motion` | `synth_adversary.py` ~L37–57 | Camera-only |
| `synthesize(session, injection, mode, seed)` | `synth_adversary.py` ~L61–70 | Preserves stick; sets `label="scripted"` |
| `evaluate(paths, modes, seed)` | `synth_adversary.py` ~L85–117 | Existing mean-based sweep; harness may wrap or reimplement with **median** + pre-registered gates |
| Honest scope comment | `synth_adversary.py` L19–23 | Model of cheat, not real aimbot; not input-masked |

### 10.3 Stream B (out of primary gate — do not confuse)

| API | Location | Notes |
|-----|----------|-------|
| `_SEP_FEATURES` | `l9_presence/biometric_features.py` ~L113 | `dominant_coupling`, `yaw_pitch_ratio`, `yaw_decoupled` |
| `extract_feature_vector` | `biometric_features.py` ~L52–75 | Includes `reliable` vs `coupling_floor` default 0.2 |
| `between_player_separation` | `biometric_features.py` ~L119+ | **Identity** LOO — not P0-A SEPARATED |

### 10.4 PoCP / Witness (reference only)

| API | Location | Notes |
|-----|----------|-------|
| `compute_pocp_commitment` | `l9_presence/pocp.py` ~L40–56 | Domain `QORTROLLER-L9-POCP-v0`; candidate |
| Witness harvest L9 → BCC A | `l9_presence/witness_agent.py` `_maybe_harvest_bcc` | PRESENT + reliable → `bcc_l9/`; **different** from BCC Match |

### 10.5 BCC Match (feeder, Phase 2)

| API | Location | Notes |
|-----|----------|-------|
| Module | `l9_presence/bcc_match.py` | Separate store `bcc_match/`; genesis `QORTROLLER-BCC-MATCH-GENESIS-v0` candidate |
| Design | `docs/a1b-bcc-match-lane-design-2026-07-08.md` | G1–G8 admission |
| Does **not** emit `coupling_score` | — | Assertion-plane artifact |

### 10.6 Advisory rails (must appear on report)

| API | Location | Notes |
|-----|----------|-------|
| `build_advisory_presence_confidence_report` / constants | `l9_presence/advisory_presence_confidence.py` | `population_certified=False`, `cert_scope=developer_self`, AIT LOW, PoEP UNCALIBRATED N=0 |
| `nqpv_fusion` signal | same ~L126–130 | Secondary; developer_self CALIBRATED note |
| `poep_l6b` | same ~L131–136 | Out of scope |

### 10.7 Corpora paths (as of design-time kill-check 2026-07-09)

| Path | Observed | Role |
|------|----------|------|
| `sessions_l9/` | **exists**; **59** `.npz` | **Primary** human L9 sessions for Phase 1 |
| `cocapture_l9/` | **exists**; **32** files | Optional L9+L4 co-capture; extract L9 `SessionData` view if labeled human |
| `bcc_l9/` | exists; Witness coupling harvest lane | Not required for scoring; isolation from Match |
| `bcc_match/` | **may be absent** until harvest | Phase-2 session_id whitelist only |
| `sessions/human/` | exists — dirs include `terminal_cal_P*`, `phase_c_ait_*` | **Controller / AIT / terminal-cal corpus** — **not** the L9 optical-flow presence corpus; do **not** treat as drop-in for `coupling_score` without L9 stick+camera streams |
| `sessions/**/hw_nqpv_001.json` … `hw_nqpv_010.json` | **10 JSON files found** under `sessions/` (not a dir tree named nqpv) | NQPV **JSON** artifacts — **not** `SessionData` `.npz`; Phase-1 coupling harness must **not** hard-require them as L9 inputs. Phase-2 / NQPV secondary only after a verified schema map |
| Bridge `nqpv_cocapture_log` | SQLite on rig | Live NQPV fusion rows; PoSP refs these |
| `audits/kas_record_*`, `posp_record_*` | match assertion artifacts | Join keys for Phase-2 BCC Match feeder, not coupling scores |

**Kill-check note (2026-07-09, corrected):** Earlier shallow dir-walk missed `hw_nqpv_*.json` files. They **exist** (N=10) but are **JSON NQPV records**, not L9 `.npz` coupling sessions. Phase-1 primary remains `sessions_l9/*.npz`. Do not load `hw_nqpv_*.json` into `analyze_session_data` without an explicit adapter (out of v0 scope).

### 10.8 Banked validation citations (prose, not re-derived here)

| Claim | Source |
|-------|--------|
| Human coupling 0.29–0.45; NC ~0.02; lag 25–83 ms | `l9_presence/README.md` Stream A |
| Full synth takeover coupling ~0.05 | same |
| Partial assist can evade coupling/global residual | same + `engagement_locked_residual` in `session_recorder.py` |
| Stream B LOO generalizes but not tournament-grade identity | README Stream B — **out of P0-A claim** |
| RP M14–M17 authorship/PoSP | `audits/rp-close-1-ledger-2026-07-07.md` — orthogonal surface |

### 10.9 Constants the harness must not silently override

Do not change `COUPLING_THRESHOLD` / lag window mid-study without a **new study schema version**. Env overrides (`L9_COUPLING_THRESHOLD`, `L9_LAG_MAX_MS`, …) if present must be **read and recorded** in the report; decision constants `TAU_*` / `GAP_MIN` stay as in §3.3 unless operator amends §9.

---

## 11. Thin wedge thesis link (P0-B, non-blocking)

If this study returns `SEPARATED`, the wedge sentence becomes:

> For cloud/RP clients where kernel AC cannot instrument the host, QorTroller can cite a pre-registered developer_self **human-vs-modeled-automation** operating point on causal aim-coupling (plus the multi-surface match stack: PoSP / PORT-CERT / VHR) — **advisory**, not field-cheat certification, not identity-AC, not host-trustless.

If `INCONCLUSIVE` / `UNVERIFIABLE`, the wedge waits; do not market the banked README numbers as a fresh OP without the harness re-run.

---

## 12. Implementation sketch for Claude (after accept)

1. Audit this doc against CODE-TRUTH (especially `analyze_session_data` fields, `synthesize` label, corpus paths).  
2. Implement pure study module + CLI; pin T1–T10.  
3. Run on `sessions_l9/*.npz` offline; write `audits/p0a-presence-op-*.{json,md}`.  
4. Append one ledger line to `audits/rp-close-1-ledger-2026-07-07.md` (or continuation): study verdict + N + gap.  
5. No capture-path PR; no flag flips; no PV-CI churn.

---

*End of P0-A presence-oracle study design v0 — 2026-07-09. Awaiting Claude audit + operator §9.*
