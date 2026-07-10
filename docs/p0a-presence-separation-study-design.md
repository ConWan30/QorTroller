# P0-A — Presence-Oracle Separation Study Design

**Status:** DESIGN — active schema **`p0a-presence-op-v2`** (aim-activity inclusion amendment).  
**Rev history:**  
- v0/v1 design + harness + raw-pool OP → **INCONCLUSIVE** (permanent honest record, commit `22bb867d`).  
- **v2 amendment:** positive-class aim-activity inclusion gate; decision constants frozen.  
- **v2 run:** **SEPARATED** (`audits/p0a-presence-op-v2-2026-07-09.*`) — median human 0.374, auto 0.067, gap 0.307.  
- **v2.1 doc rev (this):** CODE-TRUTH — `sessions_l9` is a **3-player developer corpus** (not N=1 human); §7 P1 heterogeneity limit; min-per-player policy for future schemas.  
**Audience:** Claude (audit → harness) · operator (sessions + commits).  
**Rails:** `advisory=True` · `cert_scope=developer_self` · `population_certified=False` ·  
`verifier_independence=False` · offline analysis only · **zero capture-path touch** · no new  
FROZEN-v1 · PV-CI 182 unchanged.  
**Related:** `audits/p0a-presence-op-2026-07-09.json` (v1) · `audits/p0a-tail-characterization-2026-07-09.md` ·  
`l9_presence/README.md` · `l9_presence/presence_separation_study.py`.

---

## 1. THE CLAIM (one sentence)

### v2 claim (active)

**This study establishes a pre-registered, offline, developer_self operating point for human-vs-modeled-automation separation on the L9 causal-presence oracle, restricted to aim-active sessions from a small multi-player developer corpus — using a constructed negative class over those same sessions — and does NOT establish uniform-across-players separation, population certification, identity FAR/FRR, human-vs-real-cheat-hardware detection, or compromised-host resistance.**

Expanded:

> On a declared positive class (**aim-active** live sessions from the **3-player** `sessions_l9` developer corpus, after the §5.1 inclusion gate) and a **derived** negative class (modeled automation: `synth_adversary` full camera-track injection, with time-shuffle as the causality floor), the **pooled** presence-oracle `coupling_score` separates the two classes by a gap that clears **frozen** pre-registered floors (M1–M6). Per-player medians may differ substantially (§7.1 F-P0A-V2-1).

**Words that must not be dropped:** **modeled** automation · **aim-active** sessions · **pooled** (not uniform-per-player) · **developer corpus** (not population-certified).

### v1 claim (historical — do not re-run as the headline OP)

v1 scoped positives to all scorable human sessions (oracle abstain only). That run returned **INCONCLUSIVE** and remains the permanent raw-pool record. v2 is a **narrower population**, not a retune of TAU_*/GAP_MIN.

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
  (M1)  n_human_included >= N_MIN_POS   # v2: after aim gate; v1: all scored
  (M2)  n_auto_scored    >= N_MIN_NEG
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
| **Positive (human, aim-active)** — **v2** | `sessions_l9/*.npz` with real stick + real camera; `coupling_score` defined; **and** `aim_activity_std ≥ AIM_ACTIVITY_MIN` (§5.1) | **Real captures**, activity-selected |
| **Positive (human, raw pool)** — **v1 only** | Same without aim gate — historical INCONCLUSIVE record | Real, unselected |
| **Negative (modeled automation)** | **Derived only** — §4.1 `synth_adversary` on **included** positives only | **Constructed** |
| **Floor control (not a class)** | Per-positive `negative_control` time-shuffle | M6 only; not in `C_auto` |

**Filter order (v2 harness):** (1) load `sessions_l9` → (2) score / drop `insufficient_aim_activity` → (3) **aim-activity inclusion gate** → (4) build synth negatives **only** from included positives → (5) apply frozen M1–M6.

**Corpus fact:** ~59 `sessions_l9` files are developer_self human sessions; negative must be constructed (§4).

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

### 5.0 Schema versions

| Schema | Positive inclusion | Decision constants | Status |
|--------|-------------------|--------------------|--------|
| `p0a-presence-op-v1` | Scorable only (oracle abstain) | TAU_*/GAP_MIN/M1–M6 | **CLOSED — INCONCLUSIVE** (permanent) |
| `p0a-presence-op-v2` | Scorable **+ aim-activity gate** (§5.1) | **Identical** frozen constants | **ACTIVE** — re-run after this amendment |

v2 is an **inclusion-criterion** amendment only. It does **not** change TAU_HUMAN, TAU_AUTO, GAP_MIN, TAU_NC, N_MIN_*, or the M1–M6 rule text.

### 5.1 Positive-class plan + aim-activity inclusion gate (v2 substantive change)

#### 5.1.1 Population honesty (CODE-TRUTH corrected v2.1)

| Fact | Implication |
|------|-------------|
| Positive pool ≈ **59** `sessions_l9/*.npz` | Developer L9 coupling corpus |
| **Player tags (empirical, v2 histogram):** P1≈32, P2≈8, P3≈12, +~7 untagged | **3-player developer corpus** — **not** single-human / N=1 operator-as-sole-subject. Stronger than “one person only,” still **not** population-certified |
| `cert_scope=developer_self` | Means *not external population-certified* — does **not** mean “only one labeled player exists in the pile” |
| v1: 44 scored, 22 with coupling &lt; 0.20 | Tail: mostly **low-aim** (`audits/p0a-tail-characterization-2026-07-09.md`) |
| v2 SEPARATED is **pooled** | Carried by higher-coupling players; P1 remains low even when aim-active (F-P0A-V2-1) |
| Negative count is **derived** | `n_auto = n_human_included × 3` |

#### 5.1.2 Gate metric (pre-registered)

```text
aim_activity_std(session) =
    max( std(in_sx − median(in_sx)),
         std(in_sy − median(in_sy)) )

# Same median-centering and max-axis form as the oracle activity check in
# InputOutputCouplingOracle.extract_features (coupling.py):
#   if max(sx.std(), sy.std()) < MIN_STICK_STD * 255.0: return None
```

| Symbol | Definition |
|--------|------------|
| `ORACLE_ABSTAIN_STD` | `MIN_STICK_STD * 255.0` — default **2.55** LSB (scale-tolerant; stick streams are 8-bit-class) |
| `AIM_ACTIVITY_MULT` | **4** (dimensionless, pre-registered) |
| `AIM_ACTIVITY_MIN` | `AIM_ACTIVITY_MULT * ORACLE_ABSTAIN_STD` = **10.2** LSB (at default `MIN_STICK_STD=0.01`) |

**Inclusion (v2 positive):**

```text
include_positive  iff
    coupling_score is defined
    AND  aim_activity_std >= AIM_ACTIVITY_MIN
```

Sessions that score but fail the aim gate → bucket `excluded_low_aim` (reported; not in `C_human`; no synth pairs built from them).

#### 5.1.3 Why this threshold is principled (not outcome-tuned)

**Principle first:** Stream A’s claim is *input→camera causal coupling while the player is aiming*. The oracle already refuses to define coupling when stick activity is below `ORACLE_ABSTAIN_STD` (“player not aiming” — `coupling.py` activity gate). That floor only guarantees **minimal** stick variance so Pearson r is defined. It does **not** guarantee that aim is a material activity of the session (idle fidget, rare flicks, walk-heavy captures can clear 2.55 LSB std and still be aim-poor).

**“Aim-active” definition (methodology):** a session in which right-stick variance is large enough that aim is a **primary activity**, not incidental noise above the abstain floor.

**Threshold derivation (from oracle constants + noise physics only):**

1. `ORACLE_ABSTAIN_STD = MIN_STICK_STD * 255` is the **definition of “not aiming / undefined”** already in production code.  
2. DualSense idle ADC noise is ~**2.5 LSB** std (`DEFAULT_STICK_NOISE_FLOOR` in `killfeed_inline.py`) — same order as the abstain floor.  
3. Sessions with `aim_activity_std` only 1–2× abstain sit in the **noise-adjacent / incidental-aim** band: scorable, but not “aim is the point of the capture.”  
4. Require **`AIM_ACTIVITY_MULT = 4`** so session stick std is **≥ 4× the oracle abstain floor** (variance ≥ **16×** the abstain variance scale). That is a fixed multiple of an existing protocol constant — not a percentile of the coupling distribution, not “clear TAU_HUMAN,” not the v1 high-group p25 (34.2), and not the v1 low-group median stick-std (12.6).

**What we deliberately refuse as the gate:**

| Tempting threshold | Why rejected |
|--------------------|--------------|
| Split on `coupling_score ≥ 0.20` | That **is** TAU_HUMAN — circular with the decision rule |
| High-group stick-std p25 (34.2) | Defined from the coupling split (outcome-adjacent) |
| Low-group median stick-std (12.6) | Defined from the coupling split |
| “Exclude until median human ≥ 0.20” | Outcome-tuned by construction |

**Post-registration report (Claude runs after gate is coded):** where the corpus falls (`n_included`, `n_excluded_low_aim`, aim_activity quantiles). That report **does not** authorize moving `AIM_ACTIVITY_MIN`.

#### 5.1.4 Player confound + heterogeneity (report; v2 does not hard-balance)

v1 tail was **P1-dominated** among low-aim sessions. v2 aim gate + histogram surfaced a second fact:

| Finding | Detail |
|---------|--------|
| **F-P0A-V2-1** | Even among **aim-active** included sessions, **P1 median coupling ≈ 0.09** vs **P2 ≈ 0.59** / **P3 ≈ 0.38**. Pooled SEPARATED is **carried by P2/P3**; P1 is a systematic low-coupling outlier (capture style / protocol / genuine low coupling — cause TBD, not re-labeled as bot). |

| Requirement | **v2 rule (this SEPARATED run)** | **Going forward** |
|-------------|-------------------------------|-------------------|
| Per-player histogram | **Mandatory:** n_scored / n_included / n_excluded_low_aim, median aim, median coupling per player | keep |
| Per-player aim × coupling | **Mandatory** | keep |
| Min n per player for SEPARATED | **Not required** — would change the decision rule; v2 SEPARATED stands | see below |
| Skew warning | ≥80% of included from one player → `player_skew_warning` | keep |
| Per-player floor vs TAU_HUMAN | **Not a SEPARATED veto in v2** | report `players_below_tau_human` list |

**Policy — min per-player n (design decision, frozen for v2):**

| Option | Choice |
|--------|--------|
| **v2 / current SEPARATED** | **No** min-per-player-n requirement. Pooled M1–M6 only. F-P0A-V2-1 is a **§7 limit**, not a silent fail. |
| **v3 candidate (optional stronger claim)** | Schema `p0a-presence-op-v3` *if operator wants* a **uniform-across-labeled-players** claim: e.g. each labeled player with `n_included ≥ 5` must have `median(C_player) ≥ TAU_HUMAN`, else verdict stays SEPARATED only if a new enum branch `SEPARATED_POOLED_ONLY` is used — **not implemented until operator GO**. Do **not** retrofit v2. |

Rationale: requiring min-n + per-player TAU now would (a) move goalposts after a clean pre-registered SEPARATED, (b) mix identity-style balance into a presence OP. Honest path = document heterogeneity, keep pooled SEPARATED, promote uniformity only under a new schema.

#### 5.1.5 Phase-1 corpus + N floors (unchanged floors, applied post-gate)

| Item | Plan |
|------|------|
| **Positive corpus** | **Only** `sessions_l9/*.npz` → score → **aim gate** → included set |
| **Negative corpus** | Derived via §4.1 from **included** positives only |
| **Floor control** | Shuffle NC on each **included** positive |
| **N_MIN_POS / N_MIN_NEG** | Still **8** / **24** — counted on the **included** set (M1–M2 unchanged) |
| **Decision constants** | **Frozen:** TAU_HUMAN=0.20, TAU_AUTO=0.10, GAP_MIN=0.15, TAU_NC=0.10 |
| **Seed** | `SEED=0` |
| **Schema id in report** | `p0a-presence-op-v2` |

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
  Any of n_human_included < N_MIN_POS or n_auto_scored < N_MIN_NEG
  (after oracle skips + aim-gate exclusions). Diagnostics OK.

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
- Never emit `SEPARATED` if any decision constant (TAU_*/GAP_MIN) or the aim gate was changed after seeing that run’s metrics — version bump required (`p0a-presence-op-v3`+).  
- v1 raw-pool **INCONCLUSIVE** is never overwritten by a v2 SEPARATED; both records coexist.

---

## 7. Honest non-claims / limits

### 7.1 Ceilings (negative class + aim selection + player heterogeneity)

| Claim people might over-read | Honest ceiling |
|------------------------------|----------------|
| “Separates humans from cheats” | Separates **aim-active** humans from **modeled** automation (**pooled**) |
| “Works on all human sessions” | **False for v2** — low-aim excluded; v1 raw pool INCONCLUSIVE |
| “Works equally for every labeled player” | **False** — **F-P0A-V2-1:** P1 aim-active median coupling ~0.09 vs P2 ~0.59 / P3 ~0.38; SEPARATED is **not** uniform-across-players |
| “N=1 single-operator only” | **CODE-TRUTH correction:** `sessions_l9` is a **3-player developer corpus** (P1/P2/P3 + untagged) — stronger than N=1, still not population-certified |
| “Works against real hardware cheats” | **False until P2** Cronus/XIM corpus |
| “Population-validated anti-cheat OP” | `developer_self` / `population_certified=False` |
| “Independent automation sessions” | Negatives derived from included positives only |
| “We filtered until it passed” | Aim gate = 4× oracle abstain, pre-registered before re-run |

### 7.2 Full non-claims list

This study / harness / report **does not prove**:

1. **Human-vs-real-cheat-hardware** separation — needs P2.  
2. **Separation on the unselected raw human pool** — that is v1 (INCONCLUSIVE).  
3. **Identity** / per-player FAR/FRR / `population_certified=True`.  
4. **Multi-operator generalization** or balanced multi-player presence.  
5. **Compromised-host resistance**.  
6. **Partial-assist** detection as the SEPARATED claim.  
7. **Input-masked aimbots**.  
8. **RP authorship / OCR** properties.  
9. **PoEP/L6B** readiness.  
10. **Enforcement** into tournament hard path.  
11. **FROZEN-v1 / PoAC / capture-path** changes.  
12. **NQPV JSON as coupling inputs**.  
13. That low coupling on low-aim sessions is “bot-like” — v1 tail says it is mostly **absence of aim signal**.

### 7.3 What it *does* support (v2 SEPARATED — actual run)

> On the **3-player developer** `sessions_l9` corpus, after a pre-registered **aim-activity** gate, the **pooled** L9 causal-presence scalar separates aim-active human sessions from **modeled** full-camera-takeover sessions (gap 0.307, median human 0.374, auto 0.067, M1–M6) — a **human-vs-modeled-automation OP on aim-active sessions**. P2/P3 carry the human side; **P1 remains low-coupling even when aim-active** (F-P0A-V2-1). Not field AC; not identity; not uniform-per-player; not population-certified.

---

## 8. Design-level acceptance tests (harness must pin)

| ID | Pin |
|----|-----|
| **T1** | Metric path is identical for both classes: both call `analyze_session_data` (or shared pure helper); no special-case scoring for `"scripted"`. |
| **T2** | No negative→positive leakage: synthesized sessions never enter the human multiset; human `.npz` files never rewritten on disk by the harness. |
| **T3** | Pre-registered constants are module-level (or frozen dict) and asserted in tests; SEPARATED path uses only those symbols. |
| **T4** | Fail-closed on insufficient N → verdict `INSUFFICIENT_N`, never `SEPARATED`. |
| **T5** | Oracle `insufficient_aim_activity` → `skipped`; aim-gate fails → `excluded_low_aim` (distinct buckets). |
| **T6** | Causality fail (M6) → not `SEPARATED`. |
| **T7** | Synth pairs only from **included** humans; n_auto = n_human_included × 3 when all score. |
| **T8** | Report: schema `p0a-presence-op-v2`, AIM_ACTIVITY_* constants, seed, frozen TAU_*/GAP_MIN, per-player histogram. |
| **T9** | Offline-only (no capture-path imports for scoring). |
| **T10** | Golden fixture optional. |
| **T11** | `aim_activity_std` uses median-centered max axis std; `AIM_ACTIVITY_MIN == 4 * MIN_STICK_STD * 255` at default env (assert in test). |
| **T12** | Decision constants byte-identical to v1 module values (regression: changing TAU_* fails test). |

**Suggested harness layout (Claude builds; not this PR):**

- `l9_presence/presence_separation_study.py` (pure) + `scripts/run_p0a_presence_study.py` (CLI)  
- Output: `audits/p0a-presence-op-<date>.json` + `.md`  
- Tests: `l9_presence/tests/test_presence_separation_study.py`

---

## 9. Operator-decisions table

| ID | Decision | Default in this design | Operator |
|----|----------|------------------------|----------|
| **D-P0A-1** | Primary oracle = L9 Stream A `coupling_score` | Yes | ☐ accept ☐ amend |
| **D-P0A-2** | Negative = **derived** paired `synth_adversary` full injection × 3 modes; shuffle = floor only | Yes | ☐ accept ☐ amend |
| **D-P0A-3** | Decision metric = median gap with M1–M6 | Yes | ☐ accept ☐ amend |
| **D-P0A-4** | `GAP_MIN=0.15`, `TAU_HUMAN=0.20`, `TAU_AUTO=0.10`, `TAU_NC=0.10` | **Frozen across v1→v2** | ☐ accept ☐ amend |
| **D-P0A-5** | N floors: 8 human included / 24 auto | Yes | ☐ accept ☐ amend |
| **D-P0A-6** | BCC Match Phase-2 feeder only | Yes | ☐ accept ☐ amend |
| **D-P0A-7** | NQPV / PoEP out of SEPARATED gate | Yes | ☐ accept ☐ amend |
| **D-P0A-8** | v1 harness build (done) | — | closed |
| **D-P0A-9** | **v2 aim gate:** `aim_activity_std ≥ 4 × MIN_STICK_STD × 255` (default **10.2** LSB); claim = human-vs-modeled-automation **on aim-active sessions**; schema `p0a-presence-op-v2` | Yes | ☐ accept ☐ amend |
| **D-P0A-10** | Per-player histogram mandatory; ≥80% one player → `player_skew_warning` only (no hard balance) | Yes | ☐ accept ☐ amend |
| **D-P0A-11** | v2 harness + re-run OP | Done — **SEPARATED** | closed |
| **D-P0A-12** | CODE-TRUTH: 3-player developer corpus (not N=1); F-P0A-V2-1 P1 heterogeneity in §7; **no** min-per-player-n for v2 SEPARATED; optional v3 for uniform claim | Yes | ☐ accept ☐ amend |
| **D-P0A-13** | Commit package: v2 harness + SEPARATED artifact + design rev + ledger line | Operator GO | ☐ commit ☐ hold |

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
| `sessions_l9/` | **exists**; **59** `.npz`; **3 labeled players** (P1≈32, P2≈8, P3≈12, +untagged) | **Primary** L9 coupling corpus — multi-player **developer** pile, not single-subject |
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

| Class | Symbols | v1→v2 |
|-------|---------|-------|
| Decision (frozen) | TAU_HUMAN, TAU_AUTO, GAP_MIN, TAU_NC, N_MIN_* , M1–M6 | **Unchanged** |
| Inclusion (v2 only) | AIM_ACTIVITY_MULT=4, AIM_ACTIVITY_MIN=4×MIN_STICK_STD×255 | **New filter** |
| Oracle env | `L9_MIN_STICK_STD`, `L9_COUPLING_THRESHOLD`, lag window | Record if overridden; do not retune TAU_* to match |

Schema string in report: **`p0a-presence-op-v2`**. Changing AIM_ACTIVITY_MULT after a SEPARATED run requires **v3**, not a quiet constant edit.

---

## 11. Thin wedge thesis link (P0-B, non-blocking)

If **v2** returns `SEPARATED`, the wedge sentence becomes:

> For cloud/RP clients where kernel AC cannot instrument the host, QorTroller can cite a pre-registered developer_self **human-vs-modeled-automation** OP on causal aim-coupling **for aim-active sessions** (plus PoSP / PORT-CERT / VHR) — **advisory**, not raw-pool certification (v1 INCONCLUSIVE), not field-cheat certification, not identity-AC.

v1 INCONCLUSIVE remains citable as the honest unselected baseline.

---

## 12. Implementation sketch for Claude (after accept)

1. Audit this doc against CODE-TRUTH (especially `analyze_session_data` fields, `synthesize` label, corpus paths).  
2. Implement pure study module + CLI; pin T1–T10.  
3. Run on `sessions_l9/*.npz` offline; write `audits/p0a-presence-op-*.{json,md}`.  
4. Append one ledger line to `audits/rp-close-1-ledger-2026-07-07.md` (or continuation): study verdict + N + gap.  
5. No capture-path PR; no flag flips; no PV-CI churn.

---

*End of P0-A presence-oracle study design v0 — 2026-07-09. Awaiting Claude audit + operator §9.*
