# WMP-5 Outcome Annotation — Scope Ruling (Decision-First)

**Status:** DECISION-FIRST DESIGN (2026-07-11). **No build until operator rules §1.**  
**Source vision:** `docs/depin-interop-vision-2026-07-11.md` novel idea **A** (commit `c6067a41`).  
**Banked WMP v1:** `docs/world-model-provenance.md` · `bridge/vapi_bridge/wmp/bundle_assembler.py` · `sdk/wmp_verify.py`.  
**Rails:** 228B PoAC untouched · no new FROZEN family without ceremony · post-φ only · PV-CI 182 · TGE frozen · gamer consent · observation floor remains sacred for **pixels / framebuffer / biometrics**.

---

## 0. Why this document exists

WMP v1 is **action-channel-only**. Every bundle emits FROZEN `scope_disclosure`:

| Field (v1) | FROZEN value |
|------------|--------------|
| `scope_channel` | `ACTION_ONLY` |
| `scope_observation_channel` | `ABSENT_BY_DESIGN_DATA_FLOOR` |
| `scope_fidelity` | `MACRO_INTENT_POST_PHI_NOT_BIOMECHANICAL` |
| `is_full_pomdp_tuple` | `False` |

Since the 2026-06-05 blueprint, the July arc built **cryptographically bound discrete outcome events** (KAS kill-authorship, EVENT-BIND, LUMEN-2b match boundaries, capture-card path toward clean 60fps). Interop vision proposes WMP-5: attach sparse outcome labels to action-provenance bundles for planner demos.

**Before any design of roots or verifier check #6, the protocol must rule whether those labels violate the observation-channel prohibition.**

---

## 1. The scope ruling (operator must decide)

### 1.1 Question

> Are **discrete outcome labels** (killfeed events, match start/end spans) **inside** or **outside** the WMP observation-channel prohibition?

### 1.2 Argument — PROHIBITION side (labels OUT / WMP-5 blocked)

1. **Derivation:** Killfeed and scoreboard events are extracted from **screen pixels** (OCR / vision). The observation channel is defined as “what the human saw.” Pixel-derived labels are downstream of the forbidden channel.  
2. **Slippery slope:** Once screen-derived data exports, consumers will ask for more frames, patches, or “just the HUD crop” — pressure against `ABSENT_BY_DESIGN_DATA_FLOOR`.  
3. **Honesty of v1 freeze:** `ACTION_ONLY` was a hard product promise. Extending without ceremony looks like bait-and-switch to corpus buyers.  
4. **Trust boundary:** Capture host sees the framebuffer; exporting labels still depends on that host’s vision stack (not publisher event API). Self-witnessed outcome is not independent observation.  
5. **Consent surface:** Gamers who granted “action export” may not have granted “event timeline from my screen.”

**Conclusion (prohibition side):** Keep observation ABSENT; KAS stays in the anti-cheat / session-cert stack; **do not** put event roots in WMP bundles.

### 1.3 Argument — PERMITTED side (labels IN under a new disclosed channel)

1. **Macro-public:** Kill times, match boundaries, and “who got the kill” (as public HUD events) appear in **every esports VOD and replay**. They are not biomechanical micro-signal and not raw pixels.  
2. **Already exported elsewhere:** KAS deferred records and PoSP-class artifacts already serialize authorship verdicts and event structure for session integrity — the novelty is **WMP packaging**, not the existence of labels.  
3. **Planner value without observation:** Li’s taxonomy scarcity is action demos; sparse reward-like labels `(t_k, event_type)` improve demonstration utility **without** shipping RGB. That is closer to “annotated action” than “observation channel.”  
4. **Separable data floor:** Observation prohibition targets **pixels, full state, liveness features**. Discrete enums (`KILL`, `MATCH_START`, `MATCH_END`) + timestamps + **commitment references** can be scrubbed of crops and L4.  
5. **Disclosure, not silent widen:** A new FROZEN-ish disclosure string makes the contract machine-checkable: consumers see exactly what channel they got.

**Conclusion (permitted side):** Allow **sparse discrete event labels** as a **third channel class**, never as observation, never as biometrics, never as reward-model quality claim.

### 1.4 Formal distinguishing test (load-bearing)

A candidate export field is **PERMITTED as outcome_channel** iff **all** hold:

| # | Test | Fail → |
|---|------|--------|
| **T1 Semantic** | Field is a **finite public event vocabulary** (enum / small struct): e.g. kill, death, match_start, match_end — not image, not embedding, not HUD crop bytes | REJECT (observation-shaped) |
| **T2 No pixels** | Bundle bytes contain **zero** image/crop/frame payloads; only **hashes / roots / indices** that re-derive against sealed archives **outside** the WMP export (reference-and-bind) | REJECT |
| **T3 No liveness / biometric** | Field is not L4/L5/L6/tremor/force-curve/raw HID; post-φ action matrix remains the only continuous control trace | REJECT (moat leak) |
| **T4 Macro-public analog** | A reasonable esports spectator could assert the same event from a public broadcast **without** special sensors | If no → treat as private observation; REJECT for WMP-5 |
| **T5 Consent-separable** | Export requires world-model consent **and** an explicit outcome-annotation grant (or documented super-set); cannot ride silent on action-only consent | REJECT |
| **T6 Non-conflation** | `scope_disclosure` must **not** set `observation_channel` to present; outcome is a **separate** key | REJECT if observation flipped to PRESENT |

**Pass all six →** eligible for WMP-5 outcome channel.  
**Fail any →** stays out of WMP (may still exist in KAS/session stack).

### 1.5 Proposed `scope_disclosure` extension (only if PERMITTED)

Keep v1 keys **byte-stable for pure action bundles**. For outcome-annotated bundles:

```text
scope_channel:                 ACTION_ONLY                    # unchanged — continuous control still action
scope_observation_channel:     ABSENT_BY_DESIGN_DATA_FLOOR    # NEVER flipped by WMP-5
scope_outcome_channel:         DISCRETE_EVENT_LABELS_MACRO_PUBLIC   # NEW
scope_outcome_fidelity:        SPARSE_PUBLIC_LABELS_NO_PIXELS       # NEW
scope_fidelity:                MACRO_INTENT_POST_PHI_NOT_BIOMECHANICAL  # unchanged
is_full_pomdp_tuple:           false                          # still false — no observation
is_reward_model_grade:         false                          # explicit non-claim
outcome_events_binding:        REFERENCE_AND_BIND_KAS         # roots only
```

**Consumer sees exactly:**

- Action: yes (post-φ)  
- Observation (pixels/state): **absent by design**  
- Outcome: **sparse macro-public discrete labels**, commitment-bound, not a full reward model  

Verifier **SCOPE HONESTY** (check #5) extends: if `scope_outcome_channel` present, values must match the FROZEN allowlist; if absent, bundle is pure v1 action-only (backward compatible).

### 1.6 Operator decision (gate)

| Option | Meaning |
|--------|---------|
| **R-WMP5-OUT** | Outcome labels **OUT** — WMP stays action-only; KAS remains non-WMP |
| **R-WMP5-IN** | Outcome labels **IN** under §1.4 test + §1.5 disclosure — unlock §2–3 design only |
| **R-WMP5-HOLD** | Park until capture card + publisher event API reduce pixel-derivation critique |

**Default recommendation (design, not operator):** **R-WMP5-IN** is *coherent* if and only if disclosure never pretends observation is present and T1–T6 are enforced in assembler + verifier. If operator wants zero screen-derived anything in export forever → **R-WMP5-OUT**.

```text
Operator ruling:  ☐ OUT   ☐ IN   ☑ HOLD          (R-WMP5-HOLD)
Date / initials:  2026-07-11 / operator (session ruling; Claude audit PASS both docs)
Rationale: park until the capture card's clean event channel is proven live (and/or a
publisher event API reduces the pixel-derivation critique). No urgency penalty — the
build was gated regardless. Re-open = operator re-rules IN against the same T1–T6 test.
```

**Stop here if not IN.** Sections 2–3 are design **contingent** on R-WMP5-IN.

---

## 2. Contingent design — WMP-5 bundle shape (only if IN)

### 2.1 Architecture principle

**REFERENCE-AND-BIND** (same family as PoSP / PORT-CERT):

- WMP bundle **references** KAS commitment(s), optional events_root, match span ids  
- WMP bundle **never copies** kill crops, OCR bitmaps, or raw vision tensors  
- Integrity of labels derives from existing KAS/deferred verify + archive seals, not a new FROZEN-v1 tag (unless operator later ceremonies one)

```text
ProvenanceBundle (WMP-5 annotated)
  ├── action matrix (post-φ) + VHR + PoSR + consent     [v1]
  ├── scope_disclosure (+ outcome keys)                 [§1.5]
  ├── outcome_refs:                                     [NEW]
  │     kas_commitment: 0x…        # reference only
  │     events_root: 0x…             # if present; parallel named root — never conflate with action root
  │     match_spans: [{start_ts, end_ts, span_id, beacon_ref?}]
  │     binding: REFERENCE_AND_BIND_KAS
  └── device_did?: did:io:…          # optional; ioID ceremony bars
```

### 2.2 Never-conflate rails

| Rail | Rule |
|------|------|
| **Action root ≠ events root** | Separate fields; no XOR into one “session root” that hides which failed |
| **Observation stays ABSENT** | Assembler hard-rejects any observation payload key |
| **Crops** | Forbidden in bundle JSON; consumer who needs re-verify uses offline KAS/archive tools, not WMP corpus |
| **228B PoAC** | Untouched; only referenced if already in v1 pattern |
| **W3bstream** | `EvmLogPayload.events_root` already exists — validation extension is a **separate** interop move (#3), not automatic WMP-5 |

### 2.3 Verifier check #6 — `events_root` re-derivation

Extend `sdk/wmp_verify.py` / `verify_action_provenance.py` **only after IN ruling**:

```text
6. OUTCOME BINDING (WMP-5 only; skip if scope_outcome_channel absent)
   - scope_outcome_channel == DISCRETE_EVENT_LABELS_MACRO_PUBLIC
   - observation_channel still ABSENT_BY_DESIGN_DATA_FLOOR
   - recompute events_root from referenced public event list OR
     verify against injected kas_verify(commitment) callable
   - FAIL if kas_commitment present but verify fails
   - FAIL if any image/crop field appears in bundle
```

v1 five-check path remains for pure action bundles (no check #6).

### 2.4 Attachment sources (allowed inputs to the public event list)

| Source | Allowed in WMP-5? | Note |
|--------|-------------------|------|
| KAS / deferred authored event list (timestamps + type enum) | **Yes** (primary) | Must pass T1–T6 |
| LUMEN-2b match boundaries | **Yes** | Span labels only |
| EVENT-BIND record_hash links | **Yes as refs** | No host-compromise claim |
| Raw retina crops / composite frames | **No** | Observation |
| L4 distances / biometric snapshots | **No** | Moat / floor |

---

## 3. Contingent explicit non-claims (only if IN)

Publish with every WMP-5 corpus:

1. **Not a reward model** — sparse labels ≠ dense reward, ≠ value function, ≠ RL-ready shaped reward. `is_reward_model_grade=false`.  
2. **Not observation** — no pixels, no full POMDP tuple.  
3. **Not field-FAR / identity** — no claim about who the human is or cheat catch rates.  
4. **Sparse only** — not every frame annotated; kill/match-class events only.  
5. **`developer_self` / pilot grade** until population + multi-title policy says otherwise.  
6. **Screen-derived labels remain host-trusting** — same capture trust boundary as KAS; not publisher-signed events until API exists.  
7. **No new FROZEN-v1 family** in first ship — reference-and-bind only; domain-tag ceremony only if later required.  
8. **Consent** — world-model (+ outcome) grant by gamer; bridge does not grant.

---

## 4. Relationship to other lanes

| Lane | Relation |
|------|----------|
| **WMP v1 action** | Unchanged; WMP-5 is additive disclosure + optional refs |
| **KAS / PoSP / PORT-CERT** | Upstream integrity; WMP references, does not re-prove host |
| **Capture card (OA-RP-1)** | Improves **reliability** of labels; does **not** by itself change scope law — ruling is logical, card is engineering |
| **ioID** | Optional `device_did` join; see `docs/ioid-ceremony-review-bars-2026-07-11.md` |
| **Marketplace listing** | Only after consent + scope honesty; no silent outcome upgrade of old listings |

---

## 5. Operator decision table (full)

| ID | Decision | Default | Operator |
|----|----------|---------|----------|
| **D-WMP5-1** | Scope ruling OUT / IN / HOLD (§1.6) | **HOLD** until explicit | ☑ **HOLD 2026-07-11** (re-open after live card-clean event channel; T1–T6 test stands) |
| **D-WMP5-2** | If IN: adopt T1–T6 + §1.5 disclosure strings | Yes | ☐ accept ☐ amend |
| **D-WMP5-3** | If IN: reference-and-bind only; no crops in bundle | Yes | ☐ accept ☐ amend |
| **D-WMP5-4** | If IN: verifier #6; v1 5-check path preserved | Yes | ☐ accept ☐ amend |
| **D-WMP5-5** | If IN: non-claims §3 mandatory on export | Yes | ☐ accept ☐ amend |
| **D-WMP5-6** | Build code (assembler + verify) | **Blocked until IN** | ☐ GO ☐ hold |

---

## 6. CODE-TRUTH index

| Topic | Path |
|-------|------|
| FROZEN scope strings | `bridge/vapi_bridge/wmp/bundle_assembler.py` `_SCOPE_*` |
| Consumer checks 1–5 | `sdk/wmp_verify.py`, `scripts/verify_action_provenance.py` |
| WMP lane doc | `docs/world-model-provenance.md` |
| KAS / deferred | `l9_presence/kas_deferred.py`, golden offline pack |
| Interop vision A | `docs/depin-interop-vision-2026-07-11.md` §4.A |
| Data floor | `ReplayPreProcessor.FORBIDDEN_COLUMNS` / INV-VHR-004 |

---

*WMP-5 outcome-annotation scope ruling v0 — 2026-07-11. Decision-first; no build without D-WMP5-1 = IN.*
