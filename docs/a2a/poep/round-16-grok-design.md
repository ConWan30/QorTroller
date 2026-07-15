# A2A-POEP-P3P4 Round 16 — Grok Design: RBM-v1 (or Honest Limit)

**Role:** model designer + adversary  
**Prior result:** RBM-v0 (latency + peak boolean) **FAILED** the adversarial gate  
**Gate scores (RBM-v0):** A-CONST FAR **0.76** · A-REPLAY FAR **0.90** · A-RAND FAR **0.43** · A-JITTER FAR **0.61**  
**Corpus (Claude-grounded):** registered Edge · **N=68 usable reflexes** · features from `diagnostic_json` only  
**Rails (non-negotiable):** `poep_enabled=False` · no L6B flip · honest both ways · no phantom waveform · no claim that offline scoring equals live presence

---

## 0. What RBM-v0 actually proved (and what it did not)

RBM-v0 asked: *given stored `(latency, peak_boolean)`, can a simple offline scorer reject constant / random / jittered / replayed macros?*

**Answer: no.** The FARs are not “slightly soft thresholds.” They are **structural collapse**:

| Adversary | FAR | Interpretation |
|-----------|-----|----------------|
| A-CONST | 0.76 | Pre-scheduled fixed-latency macro lives deep inside the human latency band |
| A-REPLAY | 0.90 | Replaying a past human `(latency, peak)` is nearly free |
| A-RAND | 0.43 | Uniform/random draws in physiological band still pass often |
| A-JITTER | 0.61 | Small jitter around a human mean is not a separatrix |

RBM-v0 did **not** prove “presence is impossible.” It proved:

> **Offline scoring of `(latency, peak)` does not earn presence.** It earns, at best, a weak filter against *naive* macros that land outside the human latency band — and even that bar is low.

The design question for Round 16 is not “add features until FAR looks good.” It is:

> **Do the *available stored scalars* create a hard attack cost against a shape-aware adversary who also fakes those scalars — or is the presence claim load-bearing on the *live* nonce-challenge protocol?**

---

## 1. Available feature inventory (grounded; no invention)

Claude-grounded scalars from `diagnostic_json` on the registered Edge (68 usable):

| Feature | Empirical structure | Presence-relevant? | Spoof cost |
|---------|---------------------|--------------------|------------|
| `precursor_gap_ms` | p10=0.08 · med=8.85 · p90=93.75; **30/68 near-0 (step-like), 38 structured**; operator own reflexes ~**44% step-like** | Weak / mixed | **Low** — emit 0 or ~9 ms |
| `reflex_gap_ms` | p10=44 · med=130 · p90=246 | Band filter only | **Low** — sample from [44, 246] |
| `pre_accel_mean` | 66–191 (pre-stimulus grip baseline) | Session-static, not challenge-bound | **Low** — hold a fixed grip baseline |
| `crossing_index` / `precursor_index` | Sample indices | Ordering bookkeeping | **Trivial** — pick indices consistent with gaps |
| `peak` (boolean / magnitude if present) | Peak present/absent | Binary gate | **Low** — always fire a peak |
| Full accel waveform | **NOT STORED** | Would raise shape cost | **N/A offline** |
| Nonce binding | **NOT in stored rows** | Live CR protocol | **Orthogonal to offline scoring** |

**Critical honesty constraint:** only derived **scalars** are stored. A shape-aware macro does **not** need to synthesize a biomechanically honest IMU trajectory offline; it only needs to match the **scalar projection** the scorer sees.

---

## 2. Question 1 — Can RBM-v1 (scalars + latency + peak) honestly defeat a shape-aware macro that fakes the scalars?

### 2.1 Short answer

**No.** Not as a *presence* claim. Not against an adversary that targets the *same feature map* the model uses.

RBM-v1 can at most:

- slightly lower FAR against *naive* macros that ignore new scalars, and  
- re-label some edge cases (e.g. reject pure zero-latency + zero-precursor + unnatural peak combos).

It **cannot** honestly claim defeat of a shape-aware scalar-matching macro, because:

1. **Feature map is shared.** Anything in the scoring vector is in the adversary’s target vector.  
2. **Human distribution has a large step-like mass (~44% of operator reflexes).** “Step-like on `precursor_gap_ms`” is *not* a bot signature; it is a common human mode on this instrumented surface. A detector that hard-rejects step-like precursors will attack the operator’s own real reflexes (FRR inflation).  
3. **No waveform → no residual shape energy.** Without stored accel traces, there is no residual the model can score that the macro did not also emit as scalars.  
4. **`pre_accel_mean` is not challenge-bound.** It is a slow grip baseline; a macro can sample once per session and hold it.  
5. **Index features are algebraically dependent** on gaps at fixed sampling rate — they do not add independent biomechanical evidence.

### 2.2 RBM-v1 candidate (for completeness — then kill it)

If one *must* write a v1 offline scorer for research (not product presence):

**Feature vector `x` (stored-only):**
```
x = [
  reflex_gap_ms,          # latency
  peak_flag,              # 0/1
  precursor_gap_ms,       # shape proxy (weak)
  pre_accel_mean,         # grip baseline
  # optional derived:
  log1p(precursor_gap_ms),
  is_step := 1[precursor_gap_ms < τ_step],  # τ_step ~ 1–2 ms
]
```

**Model class (honest ceiling):** density / one-class on human `x`, or logistic on (human vs *naive* synthetic).  
**What it may claim:** “rejects macros that ignore precursor/grip structure.”  
**What it may NOT claim:** “presence,” “anti-macro,” “anti-replay,” “embodied human.”

**Why the mixture kills hard separation:**

- Real human mass ≈ **0.44 step + 0.56 structured** on precursor.  
- A discriminator that treats “step” as adversarial will misclassify ~44% of real operator reflexes (or must soften until the step class is accepted — which is exactly what a step-faking macro wants).  
- The structured class is still a low-dimensional cloud; sampling from the empirical joint of `(reflex_gap_ms, precursor_gap_ms, pre_accel_mean, peak)` is a textbook generative attack.

### 2.3 Adversary design: **A-SCALAR** (shape-aware macro that fakes the scalars)

**Goal:** maximize FAR against any offline RBM-v1 defined on the stored scalar set.

**A-SCALAR-0 — Empirical joint sampler (strong default):**
1. Fit a non-parametric joint on the 68 human rows:  
   e.g. Gaussian KDE or discrete bootstrap over  
   `(reflex_gap_ms, peak_flag, precursor_gap_ms, pre_accel_mean)`.
2. For each attack trial, sample one vector from that joint (or multinomial bootstrap of real rows + small noise).
3. Emit HID/IMU *any* way you like as long as the *pipeline’s scalar extractor* yields those values.

**Expected outcome:** FAR → **≈ human acceptance rate** of RBM-v1 (often ≥ 0.8–0.95 if the model is calibrated for usable FRR). This is **A-REPLAY generalized from latency-only to full stored feature vectors.**

**A-SCALAR-1 — Two-mode precursor matcher (exploits the 44% step mass):**
1. With p = 0.44: set `precursor_gap_ms ≈ 0` (step mode).  
2. With p = 0.56: sample precursor from structured human conditional (med≈8.85, p90≈93.75).  
3. Independently sample `reflex_gap_ms` from human latency (med 130, band 44–246).  
4. Hold `pre_accel_mean` fixed in [66, 191] per “session.”  
5. Always set peak present.

**Expected outcome:** matches the *operator’s own mixture*; any model that accepts the operator must accept A-SCALAR-1 at high rate.

**A-SCALAR-2 — Conditional replay (strongest offline):**
1. Store a bank of real past `(latency, peak, precursor, pre_accel_mean)` from the same device.  
2. On each challenge *offline scoring pass*, pick a bank row (optionally nearest-neighbor in a dummy context).  
3. No live coupling required.

**Expected outcome:** FAR ≈ A-REPLAY (0.90 class) or worse — **full-feature replay**.

**A-SCALAR-3 — Optimizer against a white-box RBM-v1:**
If RBM-v1 scores `s(x)` publicly (or is reverse-engineered):
1. Maximize `s(x)` subject to box constraints from human ranges.  
2. Project onto the human convex hull of the 68 points.  

**Expected outcome:** near-perfect FAR against that specific scorer; classic Goodhart on a 4–6 dim feature map.

### 2.4 Verdict on Q1

| Claim | Honest status |
|-------|----------------|
| RBM-v1 beats *naive* macros that only fake latency | **Plausible, modest, not presence** |
| RBM-v1 beats A-SCALAR / full-feature replay | **No** |
| “Shape features earn presence offline” | **False** given 44% step-like real mass + no waveform |
| Smallest offline win | Research metric only: ΔFAR vs A-CONST when A-CONST ignores precursor/grip |

**Design decision:** Do **not** ship RBM-v1 as a presence model. If implemented at all, label it:

> `RBM-v1-OFFLINE-FILTER` — **non-presence**, research/debug scorer, adversary-expected FAR high under A-SCALAR.

---

## 3. Question 2 — What is the REAL defense against A-CONST / A-RAND / A-JITTER / A-REPLAY?

### 3.1 Attack class → real defense

| Adversary | Failure mode of offline features | Real defense |
|-----------|----------------------------------|--------------|
| **A-CONST** | Fixed delay lands in human band | **Unpredictable challenge onset** (nonce-scheduled); macro cannot pre-arm a single constant without missing or early-firing relative to unknown t₀ |
| **A-RAND** | Random draws hit physiological band | Same: response must be **causally post-challenge** with binding; random pre-fire fails timing gates; random post-hoc fabrication fails **nonce binding** |
| **A-JITTER** | Jittered schedule still precomputable | Same as CONST if schedule is independent of live nonce; jitter does not create information about secret onset |
| **A-REPLAY** | Old human scalars are still human-shaped | **Fresh nonce** → old response does not bind; commitment must include `nonce ∥ device_id ∥ response_features ∥ ts` (PoEP-style); replay of stored rows fails verification |

**Core thesis (honest):**

> The separatrix for these adversaries is **not feature richness of stored reflexes**.  
> It is **live challenge unpredictability + cryptographic binding of the response to that challenge**.

Offline scoring of historical `(latency, peak[, scalars])` is a **different problem**: population physiology / quality control / FRR calibration. It is **not** session presence.

Nonce-binding is correctly described in the grounded brief as:

- **Live protocol** (daemon fires nonce-scheduled challenge, captures response)  
- **Not** a column in the stored offline feature table  
- Therefore **orthogonal** to RBM-v0/v1 offline FAR tables

### 3.2 What offline scoring *can* still do (narrow, honest)

Offline scoring can:

1. **Calibrate human bands** (latency quantiles, usable-reflex filters B1/B2).  
2. **Reject impossible rows** (latency < sensory-motor floor, peak absent when IMU-corroboration required).  
3. **Measure corpus health** (step vs structured precursor rates, per-device FRR).  
4. **Provide weak prior** for *advisory* UI — never a tournament gate alone.

It cannot:

- Prove the response was elicited by *this* challenge.  
- Prevent replay of past human-shaped scalars.  
- Prevent generative sampling from the human joint of stored features.

### 3.3 Is RBM-v1 offline-scoring the wrong tool for presence?

**Yes — for presence.**  

RBM-v1 is the wrong *primary* tool if the goal is to “earn presence” against A-CONST/A-REPLAY/A-RAND/A-JITTER. Those attacks are defeated by **protocol**, not by **richer offline features on a spoofable projection**.

RBM-v1 may remain a **secondary offline filter** inside a live pipeline (e.g. drop clearly non-physiological responses before commitment), but:

> Presence claim = **LIVE nonce-challenge (+ binding)**, optionally strengthened by waveform retention.  
> Offline model claim = **corpus / quality**, not presence.

---

## 4. Question 3 — Honest verdict: earnable presence with current stored set + offline model?

### 4.1 Verdict (single sentence)

**Presence is NOT earnable from the current stored scalar set via an offline model; it structurally REQUIRES the live nonce-challenge protocol, and full-waveform capture is the next *honest* offline-strengthening increment — still secondary to live binding.**

### 4.2 What current data can claim

| Surface | Claim allowed | Claim forbidden |
|---------|---------------|-----------------|
| Offline RBM-v0/v1 on stored scalars | “Weak physiological band / quality filter”; research FAR vs *naive* macros | “Proof of presence”; “anti-replay”; “anti-macro under A-SCALAR” |
| Live nonce CR (daemon) | “Session-bound challenge-response attempt”; path toward PoEP candidate | “Tournament-grade presence” until N≥50 **usable Edge** reflexes + binding verification + adversarial live suite |
| Full waveform + offline shape model | Higher cost vs crude macros; research separability | Presence without live nonce binding (waveform replay still exists) |

### 4.3 Smallest honest buildable increment toward a REAL presence proof

**Name:** **P-LIVE-0** — *Nonce-Bound Reflex Capture + Verify* (not “RBM-v1”)

**Minimal scope (buildable, rails-safe):**

1. **Keep** `poep_enabled=False`, `L6B_ENABLED=false` — no product flip.  
2. **Instrument** the existing live challenge path (daemon already nonce-schedules):  
   - On challenge: record `nonce`, `t_challenge_ns`, policy_ref, device_id.  
   - On response: record `t_response_ns`, extracted scalars, **and** (if feasible) a **bounded raw accel window** around the event (e.g. ±150 ms @ poll rate) hashed + stored as optional evidence blob.  
3. **Commitment (candidate, not FROZEN promotion this round):**  
   `SHA-256(b"QORTROLLER-POEP-v0-CANDIDATE" || device_id || nonce || response_feature_digest || ts_ns)`  
   — matches existing PoEP candidate spirit; **do not** claim FROZEN-v1.  
4. **Verify path (offline auditor, not a ML “presence model”):**  
   - `response_ts > challenge_ts`  
   - `latency ∈ human band` (from Edge usable corpus)  
   - `nonce` unique / not previously answered  
   - commitment recomputes  
   - optional: peak/IMU-corroboration flags from existing usable-reflex gate  
5. **Adversarial suite for P-LIVE-0 (live, not offline FAR on stored rows):**  
   - A-CONST-LIVE: fixed delay from wall clock (no challenge listen) → must fail onset coupling  
   - A-REPLAY-LIVE: resubmit old response + old nonce → must fail fresh nonce  
   - A-REPLAY-BIND: old response features + **new** nonce without new capture → must fail if features not re-derived from live capture  
   - A-RAND-LIVE / A-JITTER-LIVE: pre-scheduled fire trains → fail if onset unknown  

**What P-LIVE-0 CAN claim (if suite passes):**
- “This device produced a response that is **time-ordered after** and **bound to** a fresh challenge nonce, with physiological-band latency.”  
- i.e. a **session-bound liveness attempt** / candidate presence *proof package*, not identity, not anti-all-cheats.

**What P-LIVE-0 CANNOT claim:**
- Inter-player identity or enrollment.  
- Defeat of a **closed-loop** macro that *listens* for the challenge and synthesizes a biomechanical response in-band (that needs harder physical channels / waveform + multi-feature + device-auth, still not offline RBM).  
- Tournament gate eligibility.  
- That offline RBM-v1 is now “presence.”

**Optional second increment (still not product flip):** **P-WAVE-0** — persist full accel window under evidence hash so *future* shape models have a non-spoofable-by-scalars residual. Even then, **replay of the waveform under a new nonce fails only if binding + live capture are enforced**; waveform alone does not stop capture-time synthesis.

### 4.4 Explicit non-goals this round

- Do **not** retune RBM-v0 thresholds to “look green.”  
- Do **not** promote RBM-v1 as the presence solution.  
- Do **not** set `poep_enabled=True` or `L6B_ENABLED=true`.  
- Do **not** claim N≥50 Edge usable human-reflex gate is met (grounded: usable Edge campaign still the rig gate; desk DualSense ≠ registered Edge).  
- Do **not** treat precursor step-like mass as bot evidence.

---

## 5. RBM-v1 design decision matrix

| Option | Description | Ship? | Why |
|--------|-------------|-------|-----|
| **RBM-v1-ML** (richer offline classifier) | Add precursor + pre_accel_mean + indices to latency+peak | **No as presence** | A-SCALAR / joint bootstrap defeats it; 44% step mass blocks hard precursor rules |
| **RBM-v1-FILTER** | Same features as soft QC before commit | **Yes, optional, labeled non-presence** | Cheap sanity checks only |
| **P-LIVE-0** | Live nonce bind + verify + adversarial live suite | **Yes — primary path** | Attacks A-CONST/RAND/JITTER/REPLAY at the correct layer |
| **P-WAVE-0** | Store hashed accel window | **Yes — secondary** | Raises offline shape cost later; still requires live bind |
| **Honest limit statement** | Offline presence is structurally out of reach | **Required in docs/tests** | Prevents Goodhart on FAR tables |

---

## 6. Recommended round-16 artifact text (operator-facing)

**HONEST LIMIT (RBM track):**  
RBM-v0 failed because latency+peak live inside a cheap macro’s range. RBM-v1 cannot rescue presence: stored scalars are a low-dimensional, partially step-like, fully spoofable projection; a shape-aware macro that matches the joint of those scalars (A-SCALAR / full-feature replay) inherits human-like scores. **Presence is not an offline classification problem on the current feature store.**

**REAL DEFENSE:**  
Unpredictable nonce-scheduled challenge onset + cryptographic binding of the live response to that nonce. That is the correct counter to A-CONST, A-RAND, A-JITTER, and A-REPLAY. Feature richness without live binding is the wrong tool.

**SMALLEST HONEST INCREMENT:**  
**P-LIVE-0** — verify-time-ordered, nonce-unique, band-checked, commitment-recomputable live reflex packages; optional **P-WAVE-0** waveform evidence hash. Claims: session-bound liveness candidate only. Non-claims: identity, tournament gate, closed-loop macro immunity, offline presence.

**Rails:** `poep_enabled=False` · no L6B flip · honest both ways.

---

## 7. Adversarial acceptance criteria (so the next round cannot self-deceive)

A future PR may claim “presence progress” **only if** all hold:

1. **Live suite** includes A-CONST-LIVE, A-REPLAY-LIVE, A-REPLAY-BIND, A-RAND-LIVE, A-JITTER-LIVE with **protocol-level** fail (not offline FAR on stored rows alone).  
2. Any offline scorer is labeled `non_presence_filter=true` in API/docs.  
3. A-SCALAR (joint bootstrap of stored features) is reported; if FAR stays high, that is **expected and not a gate fail for P-LIVE-0**.  
4. No FRR win is purchased by rejecting step-like precursors without measuring operator step rate (~44%).  
5. No enablement of product flags without separate operator GO + Edge N≥50 usable gate.

---

## 8. Final answers (compressed)

1. **RBM-v1 vs shape-aware scalar-faking macro:** **Cannot honestly defeat it.** Features too weak / shared / step-contaminated. Adversary = **A-SCALAR** (empirical joint bootstrap + two-mode precursor + conditional full-feature replay + white-box score max).  
2. **Real defense vs A-CONST/A-RAND/A-JITTER/A-REPLAY:** **Live nonce-bound challenge-response timing and binding**, not offline feature richness. RBM-v1 offline is the wrong primary tool for presence.  
3. **Earnable with current stored set + offline model?** **No.** Presence **structurally requires** the live nonce-challenge protocol; full-waveform is a useful secondary evidence increment. **Smallest honest build:** **P-LIVE-0** (nonce-bound capture+verify + live adversarial suite), optional **P-WAVE-0**. Claims liveness-binding candidate only; not tournament presence, not identity, not anti-closed-loop-macro.

---

**Round 16 designer+adversary seal:** RBM-v1 is declined as a presence model. The RBM offline track is closed for presence claims; the open path is protocol (P-LIVE-0), not denser scalars on a spoofable store.

*End of round-16-grok-design.md*
