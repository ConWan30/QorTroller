```markdown
# A2A-POEP-P3P4 · Round 14 · Grok Adversary + Presence-Readiness

**Role:** Grok — ADVERSARY + presence-readiness designer  
**Loop:** A2A-POEP-P3P4  
**Surface under test:** RBM-v0 boolean operating point on `(latency_ms, peak_lsb)`  
**Claim at stake:** `poep_enabled=True` ⇒ CLAIM PRESENCE (a live human physically on the certified Edge *now*)  
**Date posture:** design-only; no flip; operator two-key only  

---

## 0. Framing (non-negotiable)

RBM-v0 ships a **boolean** decision on two features:

| Feature | Band / threshold (RBM-v0) |
|--------|---------------------------|
| `latency_ms` | ∈ **[80, 300]** |
| `peak_lsb` | ≥ **1000** |

**Empirical base (honest, non-adversarial):**

| Cohort | N | Role |
|--------|---|------|
| Operator real reflexes | 52 | positive class |
| NO_RESPONSE nulls | 22 | negative class (absence / no voluntary response) |

| Metric | Value | Caveat |
|--------|-------|--------|
| Full-fit TPR | 0.904 | fit on same 52; not held-out adversary |
| Full-fit FAR | 0.000 | FAR vs **no-response only** |
| Nested-LOO flip-rate | 1/52 | STABLE on operator positives |

**Critical gap this round closes in design (not yet in data):**

> RBM-v0 has **never faced an adversary**. It has only faced *no response*.  
> A presence proof must defeat **presence-FAKING**, not mere silence.

**Rails (binding):**

1. **No autonomous flip** of `poep_enabled` — design + synthetic eval only this round.  
2. **Operator two-key** fires any enablement (process intent env + explicit confirm; chain kill-switch discipline preserved).  
3. **Honest outcomes both ways** — PASS warrants a *candidate* readiness claim for operator review; FAIL blocks flip and routes remediation (diagnostic features / Stage-A / hold).  
4. Synthetic nulls are **attack-class labeled** and **never mixed into the 52-reflex human corpus** as unlabeled “human.”  

---

## 1. Adversarial NULL attack classes (≥4)

Each class is a **presence-faking** strategy: produce a (latency, peak) pair that lands inside RBM-v0’s accept band so the boolean says PRESENT when no live human reflex occurred on the certified Edge.

### A-CONST · Constant-latency macro

| Field | Spec |
|-------|------|
| **id** | `A-CONST` |
| **attack** | Fixed-delay macro / cronus-style script: on challenge onset, wait **exactly** `L₀` ms, then inject a synthetic force/IMU peak of magnitude `P₀`. |
| **how it fakes (latency, peak)** | Latency is **deterministic** (clock-scheduled, not neuromuscular). Peak is a **step or short pulse** with amplitude programmed ≥1000 LSB (or scaled to pass). Output: `(L₀, P₀)` with `L₀ ∈ [80,300]`, `P₀ ≥ 1000` — **always** in-band if parameters chosen once. |
| **why realistic** | Lowest skill bar. Competitive pads, reWASD, Cronus Zen / Titan-class translators, and game macros already support fixed delay + synthetic HID/force-shaped events. No model of the operator needed — only knowledge of the published band (or one brute-force calibration pass against a local RBM oracle). |

**Threat signature (diagnostic, not used by RBM-v0 today):** zero inter-trial latency variance; peak amplitude discrete/quantized; no trial-to-trial coupling to grip posture or tremor.

---

### A-REPLAY · Replayed real-reflex trace

| Field | Spec |
|-------|------|
| **id** | `A-REPLAY` |
| **attack** | Capture one or more **accepted** real (latency, peak) outcomes from a prior live session (or from leaked / co-located capture), store as a library, and on each challenge **replay** a stored pair (or full time-series that yields the same extracted features). |
| **how it fakes (latency, peak)** | The pair is **literally sampled from the human positive distribution** that RBM-v0 was fit to. Feature-space collision is near-perfect by construction: every replay lands in the same (latency, peak) region as a real accept. RBM-v0 has **no session nonce binding** at the feature layer — replay is invisible to the 2-feature boolean. |
| **why realistic** | Same-device / same-rig capture is available to the attacker (compromised host, dual-connection laptop, shared tournament station, or prior enrollment session). Extracted features are low-dimensional; full IMU/trigger waveforms are even more damning if stored. This is the **strongest** attack against a latency+peak-only gate. |

**Threat signature:** exact or near-exact reuse of historical `(latency, peak)`; optional mild resampling still stays in-band; commitment-level defense requires **nonce-bound challenge + waveform / device-auth binding**, not band thresholds alone.

---

### A-RAND · Random-in-band

| Field | Spec |
|-------|------|
| **id** | `A-RAND` |
| **attack** | On challenge, sample latency ~ Uniform(80, 300) and peak ~ Uniform(1000, P_max) (or truncated log-normal with mass above 1000), emit synthetic response with those targets. |
| **how it fakes (latency, peak)** | **Any** draw is in the accept region by construction. FAR against this class, under pure band logic, is **1.0** unless additional structure (shape, multi-axis, device-auth) is required. RBM-v0’s boolean *is* “in band?” — random-in-band is the adversarial dual of that definition. |
| **why realistic** | One-line bot after the band is known or reverse-engineered. No need to match human biomechanics. Useful as the **null hypothesis of pure threshold gaming**. |

**Threat signature:** latency histogram flat on [80,300]; peak uncorrelated with latency; no physiological joint structure (human LOO-stable cloud is not uniform box-filling).

---

### A-JITTER · Timing-jittered bot

| Field | Spec |
|-------|------|
| **id** | `A-JITTER` |
| **attack** | Bot/macro with base delay `μ` ∈ [80,300] plus **injected timing noise** (Gaussian, truncated Gaussian, or mixture) and optional peak jitter so the scatterplot **mimics human trial variance** while remaining fully synthetic. |
| **how it fakes (latency, peak)** | Mean latency sits mid-band; noise keeps nearly all trials inside [80,300]; peak mean ≥1000 with σ small enough that P(peak≥1000)≈1. Nested-LOO “human-like” spread can be matched without any live neuromuscular plant. Defeats naive “variance = human” heuristics that might be bolted onto RBM-v0 later if not carefully specified. |
| **why realistic** | Next step after A-CONST once anti-cheat literature or a local oracle rejects zero-variance macros. Scriptable on host; common in aim/input bots that already randomize delay to evade simple detectors. |

**Threat signature:** may match 1st/2nd moments of human latency; fails on **higher-order / cross-modal** structure (IMU gravity posture, trigger force-curve shape, nonce-locked device-auth slope) that RBM-v0 does **not** use.

---

### A-HYBRID · Stale-band + peak inject (recommended 5th class)

| Field | Spec |
|-------|------|
| **id** | `A-HYBRID` |
| **attack** | Combine **partial replay** of latency with **independent peak injection** (or vice versa): e.g. latency from a real historical trial, peak from a fixed amp, *or* latency from jittered bot + peak cloned from max historical peak. |
| **how it fakes (latency, peak)** | Breaks independence assumptions: the **joint** (latency, peak) need not match the human covariance; only the **axis-wise** band constraints matter for RBM-v0. Still fully in-band. |
| **why realistic** | Attacker with incomplete capture (latency logged, waveform not) or rate-limited HID injection that cannot reproduce full peak dynamics still clears a 2-axis gate. |

**Threat signature:** wrong latency–peak correlation; peak capped at discrete levels; useful stress test for any future ellipse / Mahalanobis refinement of RBM.

---

## 2. Synthetic null generator (Claude builds — pure Python, stdlib only)

**Module target (suggested):** `l9_presence/adversarial_nulls_rbm_v0.py`  
**Constraint:** stdlib only (`random`, `math`, `statistics`, `json`, `dataclasses`, `hashlib` for seed provenance). **No numpy.**  
**Output row schema:**

```text
{
  "attack_id": "A-CONST" | "A-REPLAY" | "A-RAND" | "A-JITTER" | "A-HYBRID",
  "latency_ms": float,
  "peak_lsb": float,
  "seed": int,
  "trial_index": int,
  "meta": { ... attack-specific ... }
}
```

**Global RNG:** `random.Random(master_seed)` with documented `master_seed` (default `0xP0EP14` → `0x504F45503134` or integer `0xP0EP14` folded to `int`).  
**Provenance:** optional `batch_id = sha256(f"{master_seed}|{attack_id}|{n}".encode()).hexdigest()[:16]` for audit.

### 2.1 Per-class parameters + counts

| attack_id | N samples | Generator parameters | Sampling rule |
|-----------|-----------|----------------------|---------------|
| **A-CONST** | **200** | `L0_ms ∈ {100, 150, 200, 250}` (50 trials each); `P0_lsb ∈ {1000, 1500, 2500, 5000}` cycled or fixed `P0=2000` for half | `latency = L0`; `peak = P0` exactly. Sub-split: 100× pure fixed `(150, 2000)`; 100× grid over L0×P0. |
| **A-REPLAY** | **200** | **Library:** the 52 operator accepted (or all RBM-pass) real pairs `(ℓ_i, p_i)`; if only raw table available, use those 52 as bootstrap library | With replacement: `i ~ Uniform{0..51}`; emit `(ℓ_i, p_i)`. Sub-split: 100× pure replay; 100× replay + **ε** with `ε_lat ~ U(-2,2)` ms, `ε_pk ~ U(-20,20)` LSB, then **re-clamp** to still satisfy band if out (or drop/redraw — prefer redraw to keep pure in-band FAR estimate). |
| **A-RAND** | **300** | `lat ~ U(80, 300)`; `peak ~ U(1000, 8000)` (cap documents “unlimited amp bot”) | Independent uniforms. Optional 100-trial tail: `peak ~ U(1000, 1200)` (barely-above-threshold). |
| **A-JITTER** | **300** | Base: `μ_lat = 160`, `σ_lat = 35`; `μ_pk = 2200`, `σ_pk = 400`. Truncate: redraw until `lat ∈ [80,300]` and `peak ≥ 1000` (rejection sampling; max 50 tries then hard-clamp peak to 1000+) | Gaussian via Box–Muller from stdlib `random`. Document rejection rate. Alt mixture 20%: second mode `μ_lat=220`, `σ_lat=25` to mimic bimodal fatigue. |
| **A-HYBRID** | **200** | Latency: 50% A-JITTER draw, 50% A-REPLAY latency only; Peak: 50% fixed 3000, 50% A-RAND peak | Independent axis mix. |

**Total synthetic adversarial nulls:** **1200** (200+200+300+300+200).  

**Control cohort (required for honest report):** re-emit the **22 NO_RESPONSE** nulls as `A-NORESP` (N=22) — not adversarial, but regression baseline so FAR vs silence remains 0.000 under the same scorer.

### 2.2 API Claude must implement

```text
generate_attack_batch(attack_id: str, n: int, rng: random.Random, **params) -> list[dict]
generate_all(master_seed: int = ..., counts: dict | None = None) -> list[dict]
score_against_rbm_v0(rows: list[dict]) -> dict
  # returns per-attack: n, n_accept, far = n_accept/n, tpr_unaffected note
write_jsonl(path, rows)  # optional
```

**RBM-v0 boolean (frozen for this eval — mirror production):**

```text
accept(latency_ms, peak_lsb) := (80.0 <= latency_ms <= 300.0) and (peak_lsb >= 1000.0)
```

**Eval rule:**  
`adversarial_FAR(attack) = #{accept} / N_attack`.  
Do **not** average attacks into one FAR without also reporting **per-class** FAR (min / max / mean). Presence readiness is **fail-closed on the worst class** (see §3).

### 2.3 Forbidden generator behaviors

- No labeling synthetic rows as `HUMAN` / `REFLEX_OBSERVED`.  
- No silent merge into `poep_reflex` training sets.  
- No “adaptive” attacker that queries the live boolean in a loop **inside** the generator for A-CONST/A-RAND (unnecessary — band is open). Optional **oracle adaptive** mode deferred as `A-ORACLE` future class (not required for round-14).  

---

## 3. PRESENCE-READINESS BAR

### 3.1 Ceiling definition

For **honest warrant** to even *propose* `poep_enabled=True` to the operator (still two-key; still not autonomous):

| Attack class | Adversarial-FAR ceiling | Rationale |
|--------------|-------------------------|-----------|
| **A-CONST** | **FAR ≤ 0.05** | Constant macros must not clear as “presence” more than 5% of trials without additional signals. |
| **A-REPLAY** | **FAR ≤ 0.05** | Hardest class; if 2-feature model cannot bind nonce/session, **expect FAIL** — ceiling is aspirational for *this* feature set. |
| **A-RAND** | **FAR ≤ 0.05** | Pure band gaming must not be free. Under pure RBM-v0 definition, **expect FAR ≈ 1.0** → structural FAIL. |
| **A-JITTER** | **FAR ≤ 0.10** | Slightly looser: human-mimic variance is harder; still must not be open season. |
| **A-HYBRID** | **FAR ≤ 0.10** | Joint-structure abuse. |
| **A-NORESP** (regression) | **FAR = 0.000** | Must not regress vs 22 silence nulls. |
| **Aggregate rule** | **max_class FAR ≤ ceiling(class)** AND **no class omitted** | Worst-class fail-closed. Mean FAR is reporting-only, not the gate. |

**TPR floor (must not trade away):** operator nested-LOO TPR / flip stability must remain **≥ 0.85 TPR-equivalent** and **flip-rate ≤ 2/52** if any remediation tightens the band (document tradeoff; do not silently sacrifice the 0.904/1-flip story).

### 3.2 Decision matrix

| Outcome | Meaning | Action |
|---------|---------|--------|
| **PASS all ceilings** | RBM-v0 boolean is **adversarially non-trivial** on this synthetic suite | Candidate for operator two-key review; still require Edge-device corpus / rig gate per hard rules; **no auto flip**. |
| **FAIL any class** | RBM-v0 alone **cannot** honestly underwrite CLAIM PRESENCE against presence-faking | **HOLD** `poep_enabled=False`. Publish per-class FAR table. Route remediation below. |
| **FAIL A-RAND or A-CONST only** | Threshold definition is gamed; model is a **band check**, not a detector | Do not flip. Need features beyond open bands. |
| **FAIL A-REPLAY (even if others pass)** | Feature vector is **not challenge-bound** | Do not flip for tournament-grade presence; require deferred diagnostics / PoEP full stack. |

### 3.3 What a 2-feature (latency, peak) model **can** defend

- **Silence / NO_RESPONSE** (already shown FAR 0.000 on N=22).  
- **Out-of-band bots** (latency <80 or >300; peak <1000) — trivial rejects.  
- **Crude mistimed macros** that miss the band.  
- **Partial honest residual:** separating “no press” from “something in human band” for **advisory UX**, not cryptographic presence.

### 3.4 What a 2-feature model **cannot** defend (structural)

| Attack | Why 2 features lose |
|--------|---------------------|
| **A-RAND** | Accept region *is* the attack support. |
| **A-CONST** (in-band) | No variance / waveform / device-auth term in the boolean. |
| **A-REPLAY** | No nonce, no session_id, no raw-trace commitment in RBM-v0. |
| **A-JITTER** | Moments of (latency, peak) are forgeable without a plant model. |

**Implication:** if synthetic eval shows FAR ≫ ceiling on A-RAND / A-REPLAY (expected), the honest conclusion is **not** “tune thresholds harder until PASS.” Shrinking the band may destroy TPR on the 52 real reflexes and still leave A-REPLAY / mid-band A-CONST intact.

### 3.5 Remediation if FAIL (ordered)

1. **HOLD flip** — `poep_enabled` remains **False**; document round-14 adversarial FAR table as evidence.  
2. **Do not** retrain RBM-v0 on synthetic adversaries as if they were a balanced “bot class” without a **challenge-bound** label story — that invents a security claim the sensors don’t support.  
3. **Promote deferred diagnostic features** (already anticipated in PoEP / L6B / CCO arcs), minimum set for a *presence-relevant* upgrade path:  
   - **Nonce-bound challenge** (challenge_id in commitment preimage — PoEP design intent).  
   - **Waveform / multi-sample shape** (not single peak scalar): rise-time, multi-axis IMU, force-curve if Edge adaptive path.  
   - **Device-auth channel** (ON/OFF force-slope / CCO path) — presence *of certified hardware*, not only of a number pair.  
   - **Session binding** (`session_id` / PoSP join) so A-REPLAY across sessions fails closed.  
4. **Stage-A measurement** (Sensor Stack v2.1 discipline): adversarial separability is an **empirical unknown** — same posture as EU #1 / #4. Synthetic FAR is a **lower bound on attacker power**, not a substitute for multi-player live adversarial campaigns on the **registered Edge**.  
5. **Corpus honesty:** certified Edge usable reflex N≥50 gate remains **UNMET** if Edge N=0 — even a perfect RBM on desk DualSense does not authorize Edge presence claims.  
6. If product needs a weaker claim before full stack: ship **advisory** “in-band response detected” UI **without** `poep_enabled=True` / without CLAIM PRESENCE language.

---

## 4. Honest one-line

> **`poep_enabled=True` would MEAN:** the protocol is authorized to assert a **challenge-bound, device-attested, adversarial-resistant presence decision** that a live human is physically on the **certified Edge now**; **it MUST NOT mean** “latency∈[80,300] and peak≥1000 on a 2-feature band that only beat silence,” nor “desk-DualSense reflex model generalized to Edge,” nor “operator one-click without two-key,” nor “immunity to macro / replay / random-in-band fakes.”

---

## 5. Round-14 handoff (for Claude + operator)

| Deliverable | Owner | Acceptance |
|-------------|-------|------------|
| Implement §2 generator + JSONL/fixture of 1200 (+22) rows | Claude | stdlib-only; seeded; per-class counts match |
| Score RBM-v0 boolean per class | Claude | table: attack_id, N, accepts, FAR |
| Compare to §3.1 ceilings | Claude + Grok verify | PASS/FAIL per class + worst-class rule |
| Flip recommendation | **Neither agent alone** | Only operator two-key after PASS **and** Edge corpus gate; else HOLD |
| Artifact name | — | results → e.g. `audits/poep-rbm-v0-adversarial-far-round14.md` |

**Expected prior (adversary’s honest forecast):**  
A-RAND FAR ≈ **1.0**, A-CONST FAR ≈ **1.0**, A-REPLAY FAR ≈ **1.0**, A-JITTER FAR ≈ **1.0** under pure RBM-v0 — i.e. **systemic FAIL** of presence-readiness for CLAIM PRESENCE. That failure is **valuable**: it prevents a dishonest flip and forces Stage-A / diagnostic / nonce-bound path.

**Grok stance:** Prefer a documented FAIL that keeps `poep_enabled=False` over a cosmetic PASS that renames a band-check as presence.

---

## 6. Rails recapitulation

- [ ] No autonomous `poep_enabled` flip this round  
- [ ] Operator two-key is the only enable path later  
- [ ] Honest PASS and FAIL both publishable  
- [ ] Synthetic adversaries never laundered into human corpus  
- [ ] Silence FAR regression must stay 0.000  
- [ ] Edge certification / L6B usable-N gate remains separate and binding  

**END · round-14-grok-adversary.md**
```
