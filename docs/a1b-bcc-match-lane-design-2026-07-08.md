# A1-b — BCC Match-Lane Sub-Lane Design

**Status:** AUDITED + ACCEPTED (2026-07-08). v0 SHIPPED NONE-only — see AUDIT RESOLUTION below.  
**Decision already taken:** `D-A1b-1` — implementation deferred on a decisive kill-check (feature-space mismatch). This document is the design that kills the adapter path and freezes the honest path.  
**Audience:** next builder (implementation) + operator (accept / amend / reject).  
**Related:** `l9_presence/BCC_SCOPE.md`, `l9_presence/bcc.py`, `l9_presence/bcc_match.py`, `l9_presence/witness_agent.py`, `l9_presence/posp.py`, `l9_presence/kas_deferred.py`, `scripts/bcc_match_harvest.py`, `scripts/session_close_report.py`, `audits/rp-close-1-ledger-2026-07-07.md`.

---

## AUDIT RESOLUTION (2026-07-08, Claude — pre-implementation code audit)

grok authored this design; Claude audited it against the actual code before any implementation.
Every "Code truth" (§2) claim was verified against the repo. **Four of five cited surfaces are
byte-exact** (§2.1 BCC hash formula + lane codes + default-OFF `bcc.py:40-50,24-28,112`; §2.2
Witness gate `witness_agent.py:95,110,116`; §2.3 `_SEP_FEATURES` `biometric_features.py:113`;
§4 host `scripts/session_close_report.py` + `BCC_SCOPE.md` exist). One finding:

**F-A1b-AUDIT-1 — §2.4 L4 key list is inaccurate.** §2.4 attributes a 13-key ordered list to
`behavioral_archaeologist.FEATURE_KEYS`, but that constant is a **9-key list in a different
order** (ends `…stick_autocorr_lag5, press_timing_jitter_variance, touchpad_spatial_entropy`;
does **not** contain the design's `tremor_peak_hz / tremor_band_power /
accel_magnitude_spectral_entropy / touch_position_variance`). There is **no single bridge
constant** matching §2.4 — `continuity_prover.FEATURE_KEYS`=7, `pitl_prover.FEATURE_KEYS`
differ again. Pinning a 13-key vector now (§5.3 rule 1) would pin a **phantom** order.

**Resolution (operator GO 2026-07-08): ship v0 `feature_contract.name="NONE"` only.** The L4
attachment (§5.2 `feature_contract`, §5.3 rules) is **DEFERRED to `artifact-v1`**. This confines
the inaccuracy to the one section the design already made optional (§5.3 rule 3: NONE still
admits), and **strengthens corpus purity** — v0 rows are assertion-plane ONLY (PoSP / KAS /
coherence), zero controller-internal biometrics. `artifact-v1` re-adds L4 pinned against a real
`import FEATURE_KEYS`, and must first resolve *which* of the ≥3 divergent `FEATURE_KEYS` sources
is canonical (a question a design doc must not answer by guessing). **§2.4 and §5.2/§5.3's
`feature_contract` section are OUT OF SCOPE for v0 — do not implement them; see the inline
`[v0: NONE — F-A1b-AUDIT-1]` markers.**

**Minor notes baked into the v0 build (non-blocking):**
- **Candidate genesis tag flagged.** `QORTROLLER-BCC-MATCH-GENESIS-v0` is a *new* (candidate,
  unregistered) chain lane tag — within precedent (`bcc.py` docstring calls
  `QORTROLLER-BCC-GENESIS-v0` "a CANDIDATE chain tag, not a registered PATTERN-017 family"), NOT
  a FROZEN-v1 family, NOT a PV-CI invariant. Surfaced explicitly, not silent.
- **`.gitignore bcc_match/` is mandatory** (elevated from §8 step 6 "if not already covered"):
  even NONE-only rows carry `session_id` + archive dir paths (session-derived) — rail: raw
  session data never leaves the rig.
- **Per-match rows inherit a session-scoped PoSP.** PoSP is issued per `session_id`, not per
  match span; a per-match row (D-A1b-6) carries the session's SYNCHRONIZED verdict (G2,
  session-scope) with per-span coherence/authorship (G4/G5, span-scope). Documented in the module.
- **Coherence `max(1, eligible)` guard is dead-but-harmless** — authored ⊆ eligible ⇒
  fraction ≤ 1.0 always; the guard only bites at authored=0, which G5 already rejects. Kept
  defensive with a one-line comment.

**Rubric: 10/10 pass** (separate store not adapter · SYNCHRONIZED-only + coherence≥0.50 stricter
than lane A · fail-closed admission · M15/M16 excluded · writes only to `bcc_match/` · default-OFF
· provenance-linked · honest scope · no FROZEN-v1 / no PV-CI · reference-and-bind). **Rails
honored:** no 228B PoAC contact, no chain write / 0 IOTX, no FROZEN-v1 edit, single-committer
(implementation staged for operator commit).

---

## 0. One-sentence claim

**BCC Match is a sealed, gamer-local, provenance-chained corpus of match-bound multi-surface presence sessions — not a dump of L4 vectors into the L9 coupling lane, and not a silent promotion path into tournament biometrics.**

---

## 1. Why this exists (novelty that is QorTroller-shaped)

### 1.1 The project thesis (load-bearing)

QorTroller inverts anti-cheat: the player is sovereign; humanity is proven at **physical contact**; Remote Play / cloud is the flagship environment. The three-plane law governs every new surface:

```
  MEANING     (Lumen)        gamer-owned session intelligence
  ASSERTION   (QorTroller)   KAS + PoSP + OCR zero-false-read + coupling — protocol integrity
  OBSERVATION (retina/tier)  may SUGGEST, never ASSERT
```

BCC (existing) is the **depth lever**: a sealed accumulator that grows the developer's own reference pile without touching proven numbers (`mythos_corpus_drift = 0`). It is isolation as architecture, not as a comment.

### 1.2 The gap D-A1b-1 actually named

| Surface | Host | Unit of harvest | Feature space | Admission gate |
|---------|------|-----------------|---------------|----------------|
| **BCC Sub-lane A (live)** | Witness `process_session` | L9 `.npz` causal session | `_SEP_FEATURES` (3): `dominant_coupling`, `yaw_pitch_ratio`, `yaw_decoupled` | verdict=`PRESENT` ∧ biometric `reliable` |
| **BCC Sub-lane B (live)** | Witness menu lull | PoEP micro-sample | PoEP sample dict | `bcc_sublane_b_enabled` ∧ nominal |
| **Match flow (live, no BCC)** | Daemon stop + session_close + bridge NQPV | Match / U1 `session_id` | **13-dim L4** session biometrics + PoSP/KAS/archive surfaces | PoSP / KAS / deferred / hygiene — **not wired to BCC** |

Kill-check (ledger, 2026-07-08):

> L9 `_SEP_FEATURES` = 3-feature **coupling** space; the match flow emits the **13-feature L4** vector. DIFFERENT spaces: cross-harvesting would poison BCC corpus semantics. Honest path = a new sub-lane with its own feature contract + gate. No silent approximation.

ACT-1 KC-2 also corrected a wrong story: BCC's host is the **Witness lane**, not "every match harvests." Match-lane harvest is therefore **composition work at the match boundary**, not a flag flip on Witness.

### 1.3 Novelty — what competitors cannot casually copy

Most systems that grow a "gameplay corpus" do one of three dishonest things:

1. **Schema collapse** — pack whatever floats are handy into one vector store.  
2. **Gate collapse** — harvest everything that looks like a session.  
3. **Promotion collapse** — silently feed research piles into production models.

QorTroller's novelty for A1-b is the opposite stack:

| Principle | Match-lane instantiation |
|-----------|--------------------------|
| **Presence before identity** | Admission is PoSP/KAS assertion-plane gates, not L4 Mahalanobis distance |
| **Reference-and-bind** | Row integrity derives from PoSP / KAS / archive / (optional) perception root / beacon — **no new FROZEN-v1 family** |
| **Isolation as product** | Own store + own genesis candidate; never writes separation/AIT/L4 thresholds/PoEP models |
| **Honest types** | Payload is a **MatchPresenceArtifact**, not a 3-float pretending to be coupling |
| **Gamer sovereignty** | Local sealed lane (`bcc_match/`), consent-bound, promotion is a separate ceremony |
| **Fail-closed corpus hygiene** | M15-class (link flip / 0 authored) and M16-class (HYGIENE_FAIL) **never enter** as PRESENT-grade match assets |

The economic / protocol meaning: after M17, the scarce object is not "can we prove a session?" It is **"can we accumulate match-scoped, multi-surface certified sessions without lying about what the numbers mean?"** BCC Match is that institutional answer — the sealed feedstock for future population studies, VHR listing provenance, and gamer-owned match certificates — without poisoning L9 coupling depth or tournament L4/AIT state.

---

## 2. Code truth (what implementation must respect)

### 2.1 BCC mechanics (reuse the *pattern*, not the *schema*)

From `l9_presence/bcc.py`:

- Chain formula (candidate v0):  
  `BCC_N = SHA-256(prev(32) || feature_digest(32) || quality(1) || sub_lane(1) || ts_ns_be(8))`  
- `feature_digest = SHA-256(canonical JSON of payload)` — payload is opaque to the chain.  
- Harvester accepts **already-computed** payloads; it never extracts biometrics itself.  
- Default-OFF; promotion out of scope by design (`BCC_SCOPE.md`).

Sub-lane codes today: `A=0x01`, `B=0x02`. Match must **not** reuse these codes for a different feature contract without a typed payload **and** readers that hard-filter by type. Prefer a **separate store** (see §4).

### 2.2 Witness harvest gate (Sub-lane A — do not clone into match)

```text
_should_harvest_l9(verdict, reliable) := (verdict == "PRESENT") AND reliable
fvec := [bvec[k] for k in _SEP_FEATURES]   # exactly 3 floats
```

This gate is correct for **causal coupling**. It is the wrong gate for **match multi-surface presence**.

### 2.3 L9 feature contract (locked for lane A)

```python
# l9_presence/biometric_features.py
_SEP_FEATURES = ("dominant_coupling", "yaw_pitch_ratio", "yaw_decoupled")
# optional research: _SEP_FEATURES_RICH (+ pitch_coupling, pitch_decoupled)
```

### 2.4 Match / L4 feature contract (locked for tournament identity path — do not mix)

> **[v0: NONE — F-A1b-AUDIT-1]** The audit found this list does NOT match any real bridge
> constant: `behavioral_archaeologist.FEATURE_KEYS` is 9 keys in a different order;
> `continuity_prover`/`pitl_prover` differ again. **This block is OUT OF SCOPE for v0** —
> v0 ships `feature_contract.name="NONE"`. The list below is illustrative only and must be
> re-derived from a real `import FEATURE_KEYS` before any `artifact-v1` L4 attachment.

Canonical L4 keys (bridge / behavioral archaeologist, 13-dim live space):

```text
trigger_resistance_change_rate
trigger_onset_velocity_l2
trigger_onset_velocity_r2
micro_tremor_accel_variance
grip_asymmetry
stick_autocorr_lag1
stick_autocorr_lag5
tremor_peak_hz
tremor_band_power
accel_magnitude_spectral_entropy
touch_position_variance
press_timing_jitter_variance
touchpad_spatial_entropy          # index 12; often structural zero in pure gameplay
```

These are **controller-internal biometrics** (identity / anomaly). They are not causal render-loop coupling. Harvesting them into `record_l9([3 floats])` would be a category error even if you PCA'd 13→3.

### 2.5 Assertion-plane surfaces already available at match close

| Artifact | Module / path | What it certifies |
|----------|---------------|-------------------|
| U1 `session_id` | `l9_presence/session_identity.py` | Join key across KAS / NQPV / archive |
| KAS | daemon stop, `audits/kas_record_*` | Dual-lobe kill authorship (live) |
| Deferred KAS | `kas_deferred.py` | Post-hoc authorship from manifest crops |
| PoSP | `posp.py` | SYNCHRONIZED / PARTIAL_SURFACES / UNVERIFIABLE |
| Archive manifest | `retina_kf_archive/.../manifest.json` | Per-crop SHA-256s, session_id |
| Perception root | LUMEN-4a `roll_perception_root` | Named root (≠ kas_session_root) |
| Temporal beacon | PoSP A3-b field | Advisory recency reference |
| Match spans | `match_state.py` / LUMEN-2 | When a match began/ended |
| Session report | `scripts/session_close_report.py` | Composition host (read-only today) |
| NQPV rows | bridge `nqpv_cocapture_log` | Fusion evidence (+ optional L4/L5 flags) |
| L4 session rollups | bridge records / mean_json | 13-feature space (if captured) |

### 2.6 Machine-readable honesty (must travel with every match row)

From `advisory_presence_confidence.py` (C-4.2): `cert_scope="developer_self"`, `population_certified=False`, `advisory=True` on deferred/KAS-class records. BCC Match rows **must** carry the same class of fields so a future marketing path cannot re-label the pile as tournament-grade.

---

## 3. Rejected designs (with reasons)

| ID | Proposal | Why rejected |
|----|----------|--------------|
| **R1** | Adapter: map L4 13 → L9 3 (PCA / hand weights / first-3) | Poisons `_SEP_FEATURES` semantics; D-A1b-1 kill-check |
| **R2** | Same `bcc_chain.jsonl`, same `type: "l9"`, 13 floats in `features` | Readers assume 3-dim; silent shape break |
| **R3** | Harvest every daemon session with no PoSP gate | M15/M16-class pollution; destroys "self-cleaned corpus" property |
| **R4** | Auto-promote BCC Match into `separation_defensibility_log` / AIT | Violates BCC isolation + tournament honesty; needs separate promotion ceremony |
| **R5** | New FROZEN-v1 domain tag for match harvest | Violates reference-and-bind discipline; ceremony-gated only if ever needed |
| **R6** | Host inside Witness `process_session` | Wrong host (KC-2); Witness has no PoSP/archive/match_state |
| **R7** | Host on bridge hot path per-frame | Event-loop + privacy risk; match is a session-boundary object |
| **R8** | Treat PARTIAL_SURFACES as good enough for full admission | Soft gate; reintroduces pre-U1 ambiguity as first-class corpus |

---

## 4. Architecture decision — preferred shape

### D-A1b-2 — Separate sealed store (recommended)

| Field | Choice |
|-------|--------|
| Store root | `bcc_match/` (gitignored, parallel to `bcc_l9/`) |
| Chain file | `bcc_match/bcc_match_chain.jsonl` |
| Genesis tag (candidate) | `QORTROLLER-BCC-MATCH-GENESIS-v0` |
| Hash formula | **Byte-identical to BCC v0** (prev‖digest‖quality‖sub_lane‖ts_ns) so tooling pattern reuses; **different genesis** so chains cannot be concatenated by accident |
| Sub-lane codes (match-local) | `0x01` = MATCH_PRESENCE (full artifact), `0x02` reserved for future MATCH_REFLEX (not PoEP lane B) |
| Module | `l9_presence/bcc_match.py` (or `bcc_match/` package) — **does not import** tournament store writers |
| Harvester | Accepts pre-built `MatchPresenceArtifact` dict only; never computes L4 or PoSP itself |
| Config | `BCC_MATCH_ENABLED` default false; independent of `BCC_ENABLED` |

**Why not extend `bcc_l9` with sub_lane=0x03?** Feasible technically (digest is opaque), but analysis risk is real: any script that loads `bcc_chain.jsonl` and assumes `payload["features"]` is 3-dim will mis-train without failing loud. Separate directory makes the category error a path error (loud). Isolation over clever reuse.

### D-A1b-3 — Host = session-close composition (recommended)

Primary host: **`scripts/session_close_report.py` path** (or a sibling `scripts/bcc_match_harvest.py` called from the same post-stop ritual), with optional daemon-stop hook **fail-open** after PoSP issuance.

Rationale:

- All assertion surfaces already load there (PoSP, KAS, deferred, match spans, perception root).  
- Matches LUMEN-2 "system knows match begin/end."  
- Zero impact on HID / bridge event loop.  
- Operator can re-run offline on M14/M17 archives to backfill **only if gates pass** (historical honesty).

Witness remains owner of L9 lanes A/B only.

---

## 5. Feature contract — `MatchPresenceArtifact` (v0)

### 5.1 Design rule

The digestible payload is a **typed artifact**, not a bare float vector. Optional biometric sections are **named** and **never** aliased to `_SEP_FEATURES`.

Schema string (not a domain tag): `qortroller-bcc-match-artifact-v0`.

### 5.2 Required sections

```text
MatchPresenceArtifact v0
├── schema: "qortroller-bcc-match-artifact-v0"
├── type: "match_presence"                    # hard discriminator
├── session_id: hex                           # U1 join key
├── session_display: str
├── device_id: str | null
├── player: str                               # local label; not population id claim
├── span_ms: [start, end] | null
├── advisory: true                            # FROZEN default true in v0
├── cert_scope: "developer_self"              # FROZEN default in v0
├── population_certified: false               # FROZEN default false in v0
│
├── admission:                                # why this row was allowed in
│   ├── posp_verdict: "SYNCHRONIZED"          # only this admits in v0
│   ├── posp_commitment_refs: { kas?, fusion?, archive? }
│   ├── coherence_fraction: float             # authored / eligible_clusters
│   ├── coherence_numerator: int
│   ├── coherence_denominator: int
│   ├── authorship_tier: "LIVE" | "DEFERRED" | "BOTH"
│   └── quality_code: 0x01 NOMINAL | 0x10 DEGRADED (chain field)
│
├── assertion_refs:                           # REFERENCE-AND-BIND — integrity lives here
│   ├── kas_commitment: hex | null
│   ├── kas_verdict: str | null
│   ├── deferred_verdict: str | null
│   ├── deferred_authored: int | null
│   ├── posp_verdict: str
│   ├── kas_session_root: hex | null
│   ├── retina_perception_root: hex | null    # may be null honestly
│   ├── archive_manifest_dir: str | null
│   ├── archive_id_verified: bool
│   └── temporal_beacon: {block_number, block_hash, ...} | null
│
├── match_context:                            # LUMEN-2; structure, not kill evidence
│   ├── n_matches: int
│   ├── in_match_spans: [[t0,t1], ...]
│   └── transport: "USB" | "RP" | "UNKNOWN" | null
│
└── feature_contract:                         # v0: NONE-ONLY (F-A1b-AUDIT-1); L4 attach = artifact-v1
    ├── name: "L4_SESSION_V13" | "NONE"
    ├── dim: 13 | 0
    ├── keys: [ ... FEATURE_KEYS in canonical order ... ]
    ├── vector: [float × dim]                 # session aggregate (see §5.3)
    ├── aggregate: "session_mean" | "session_median" | "last_nominal"
    └── source: "bridge_records" | "nqpv" | "unavailable"
```

### 5.3 L4 attachment rules (when present)

1. **Canonical key order** must match bridge `FEATURE_KEYS` / live 13-dim space.  
2. Aggregate is **session-scoped** (one vector per admitted match/session row), never a raw frame dump into the chain.  
3. If L4 is unavailable (offline archive-only reprocess without DB): `feature_contract.name = "NONE"`, `dim = 0`, **still admit** if assertion gates pass — presence corpus grows without inventing biometrics.  
4. **Never** write L4 vectors into `bcc_l9` or label them `type: "l9"`.  
5. Structurally zero indices (e.g. touchpad entropy in pure gameplay) stay honest zeros; no imputation.

### 5.4 What is deliberately NOT in the artifact

- Raw HID frames / crop pixels / OCR full text (privacy + size; archive holds crops under manifest).  
- LLM adjudication text.  
- Separation ratio, AIT scores, tournament preflight bits.  
- Any field that would let a naive reader treat the row as a multi-player identity sample without reading `population_certified=false`.

---

## 6. Admission gate — fail-closed (v0)

### 6.1 Hard requirements (all must hold)

| # | Condition | Source | Fail behavior |
|---|-----------|--------|---------------|
| G1 | `session_id` non-empty | U1 | reject |
| G2 | PoSP `verdict == SYNCHRONIZED` | `posp.py` | reject (PARTIAL/UNVERIFIABLE out) |
| G3 | PoSP surface id checks clean (no mismatch notes that force UNVERIFIABLE) | PoSP notes / verifier | reject |
| G4 | Coherence fraction ≥ `BCC_MATCH_COHERENCE_FLOOR` | see §6.2 | reject |
| G5 | Authorship not empty: live AUTHORED_SESSION **or** deferred DEFERRED_AUTHORED_SESSION **or** both with authored ≥ 1 | KAS / deferred | reject |
| G6 | No inherited hygiene fail: KAS/deferred not HYGIENE_FAIL / UNVERIFIABLE | KAS / deferred | reject |
| G7 | `BCC_MATCH_ENABLED` true | env/config | no-op |
| G8 | Chain write only to `bcc_match/` | store | structural |

### 6.2 Coherence fraction (pin the definition)

**Definition (v0, pre-register — do not retune post-hoc on one match):**

```text
coherence_fraction =
  authored_clusters / max(1, eligible_kill_clusters)

where:
  authored_clusters =
    count of kill clusters with authored conjunction
    (live AUTHORED-equivalent OR DEFERRED_AUTHORED)

  eligible_kill_clusters =
    clusters that meet the K-floor size for the operative tier
    (DEFAULT_K_FLOOR = 3, same as kas_deferred / killfeed consistency)
    including OBSERVED-only clusters (visible kills without conjunction)

  OBSERVED-only clusters count in the denominator, not the numerator.
```

**Default floor (v0 recommendation):** `BCC_MATCH_COHERENCE_FLOOR = 0.50`

Rationale:

- M17-class (~17/18 ≈ 0.94) clearly admits.  
- M14-class live authorship starvation under RP may fail live-only but can pass on **deferred** tier if deferred authored fraction clears the floor — which is the honest RP path.  
- M15-class (0 authored, IMPLAUSIBLE) fails G5/G6.  
- Floor is **not** 1.0: human play includes unauthored-looking clusters under OCR thinning; 0.50 is a corpus-quality bar, not a tournament identity bar.

**Pre-registration rail:** if M17 deferred/live fractions are re-measured later, the floor does not move in the same PR that harvests them. Floor changes are a versioned design amend (`artifact-v1` or config version note).

### 6.3 Quality codes (chain field)

| Code | When |
|------|------|
| `0x01` NOMINAL | G1–G8 pass; L4 present or honestly NONE; perception root optional |
| `0x10` DEGRADED | Reserved: e.g. SYNCHRONIZED but beacon missing **and** operator opts into degraded harvest (v0 default: **do not write DEGRADED** — reject instead; avoids soft pile) |

v0 recommendation: **NOMINAL-only writes**. DEGRADED is specified for forward-compat but not used until a design amend.

### 6.4 Per-match vs whole-session rows

LUMEN-2 + `slice_scan_by_spans` already slice multi-match sessions.

| Mode | v0 default | Notes |
|------|------------|-------|
| **One row per IN_MATCH span** that independently passes gates | **Preferred** | Matches "match-lane" name; enables per-match data-economy assets |
| One row per daemon session | Allowed fallback | Use when match spans unavailable; set `match_context.n_matches` honestly |

If a session has 2 matches and only one passes coherence, **only the passing match is harvested**. No averaging across a fail.

---

## 7. Isolation contract (firewall)

Mirror `BCC_SCOPE.md`, specialized:

| Proven / parallel system | BCC Match obligation |
|--------------------------|----------------------|
| `bcc_l9/` / L9 `_SEP_FEATURES` studies | **never write**; never share chain file |
| `separation_defensibility_log`, AIT, all-pairs gate | **never write / never call** |
| L4 thresholds 7.009 / 5.367, threshold tracks | **never write** |
| PoEP calibration bands / device_signatures | **never write** |
| `behavioral_lattice` / GCAP | **never write** |
| GIC / WEC / CORPUS-SNAPSHOT / VAME | parallel only; Match is not a link in those chains |
| PoSP / KAS commitments | **reference only** (read commitments into artifact; do not re-mint) |
| Bridge consent registries | harvest is local; on-chain consent remains gamer-wallet only |
| PV-CI / FROZEN-v1 | no new invariant / family without ceremony |

**Promotion:** same as BCC — accumulate only. Promoting Match rows into any proven corpus is a **separate reviewed action** that re-runs analyses from scratch on an explicit export, never a live read of `bcc_match/` from tournament code paths.

---

## 8. Implementation sketch (for the session after acceptance — not now)

Ordered so each step is testable alone:

1. **`l9_presence/bcc_match.py`**  
   - Genesis, store, `compute_bcc_match_hash` (formula twin), `MatchHarvester.record(artifact) -> Optional[rec]`  
   - Status / verify / selftest CLI (mirror `bcc.py`)

2. **`build_match_presence_artifact(...)` pure function**  
   - Inputs: posp dict, kas dict, deferred dict | None, match spans, optional L4 vector, advisory fields  
   - Outputs: artifact dict **or** structured reject reason (never partial write)

3. **`passes_match_admission(artifact_inputs) -> (ok, reasons)`**  
   - Implements G1–G8; unit-tested against fixtures: M15 reject, M16 reject, M17 admit, PARTIAL reject

4. **Wire host**  
   - `scripts/bcc_match_harvest.py` + optional call from `session_close_report.py` after PoSP verify  
   - Fail-open: harvest errors never fail the session report

5. **Tests (minimum)**  
   - Chain integrity / monotonic ts  
   - Type discriminator required  
   - SYNCHRONIZED-only  
   - Coherence math (authored/eligible)  
   - L4 NONE still admits  
   - L4 present preserves key order + dim=13  
   - Never writes under `bcc_l9/`  
   - `population_certified` always false in v0  
   - Fixture: "adapter poison" regression — loading Match chain into L9 feature matrix must be impossible without an explicit export tool (path + type checks)

6. **Docs / ledger**  
   - Amend `BCC_SCOPE.md` with "third lane family lives in bcc_match/" pointer  
   - Ledger line: A1-b DESIGN ACCEPTED / IMPLEMENTED  
   - `.gitignore` `bcc_match/` if not already covered

7. **Config**  
   - `BCC_MATCH_ENABLED=false` default  
   - `BCC_MATCH_COHERENCE_FLOOR=0.50`  
   - `BCC_MATCH_OUT_DIR=bcc_match`

**Explicit non-goals for first code PR:** no bridge endpoint, no SDK class, no on-chain anchor, no auto-harvest from Witness, no PV-CI invariant, no FROZEN registration.

---

## 9. Novelty checklist (self-audit before acceptance)

| Question | v0 answer |
|----------|-----------|
| Does this mint a new trust primitive? | **No** — reference-and-bind to PoSP/KAS/archive |
| Does this improve multi-player separation by existing? | **No** — depth of developer_self match assets only |
| Does this make cheating unexpressible? | **Indirectly** — grows clean refuse-capable corpus; M15-class never enters |
| Does gamer own the data? | **Yes** — local sealed lane; promotion separate |
| Can marketing launder this? | **Harder** — `advisory` + `population_certified=false` + SYNCHRONIZED-only |
| Is the three-plane law honored? | **Yes** — observation roots optional; assertion gates mandatory; meaning not claimed |
| Is D-A1b-1 honored? | **Yes** — separate feature contract + store; no 13→3 map |

---

## 10. Operator decisions (accept / amend)

Please mark each:

| ID | Decision | Default in this doc | Operator (2026-07-08) |
|----|----------|---------------------|----------|
| **D-A1b-2** | Separate `bcc_match/` store vs sub_lane on `bcc_l9` | Separate store | ☑ accept (separate store) |
| **D-A1b-3** | Host = session-close composition vs daemon-only vs Witness | session-close (+ optional fail-open daemon) | ☑ accept — v0 ships the standalone runner `scripts/bcc_match_harvest.py`; session-close auto-hook deferred (minimize touch, reversible) |
| **D-A1b-4** | Coherence floor 0.50 | 0.50 pre-registered | ☑ accept (0.50) |
| **D-A1b-5** | NOMINAL-only writes in v0 (no DEGRADED harvest) | NOMINAL-only | ☑ accept (NOMINAL-only) |
| **D-A1b-6** | Per-match rows preferred vs session rows | Per-match preferred | ☑ accept (module is per-row agnostic; runner slices via `slice_scan_by_spans`) |
| **D-A1b-7** | L4 attachment optional (NONE still admits) | Optional | **☑ amend → v0 is NONE-ONLY** (F-A1b-AUDIT-1); L4 attach → `artifact-v1` |
| **D-A1b-8** | Proceed to implementation PR after accept | Hold for GO | ☑ **GO** — v0 built, staged for operator commit |

---

## 11. Acceptance tests (design-level — implementation must pin)

1. **Poison test:** A tool that tries to train on `bcc_match` rows as `_SEP_FEATURES` fails closed (type/dim check).  
2. **M15 test:** zero-authored / link-flip style inputs → `harvested=false`, chain length unchanged.  
3. **M16 test:** HYGIENE_FAIL → rejected.  
4. **M17-shaped test:** SYNCHRONIZED + high authored fraction → one (or per-match) NOMINAL row; `verify()` true.  
5. **Partial test:** PoSP PARTIAL_SURFACES → rejected.  
6. **Isolation test:** after harvest, no new rows in `separation_*` / AIT tables / `bcc_l9`.  
7. **Honesty test:** every stored row has `advisory=true` and `population_certified=false`.  
8. **Reference test:** artifact includes at least one of `kas_commitment` or deferred source commitment + posp verdict SYNCHRONIZED.

---

## 12. Relation to the rest of the board

| Item | Relation to A1-b |
|------|------------------|
| **RP-4** | Orthogonal. Latency calibration unlocks LUMEN-3; does not change Match feature contract. Do at rig first if available. |
| **ES seg-3** | Orthogonal (haptic disconfound). |
| **VHR submit** | Complementary: VHR proves a replay; BCC Match accumulates *which sessions* are clean feedstock. No dependency. |
| **RP-6** | Later: adversarial splice corpus should **not** auto-enter BCC Match (fail gates); may need a separate `adversarial/` lane if ever stored. |
| **A5 autonomy** | Unrelated; still two-key parked. |

---

## 13. Summary for the operator

A1-b is not "wire match → BCC." It is:

> **Create a second sealed family of gamer-local presence assets: match-bound, multi-surface, SYNCHRONIZED-only, coherence-gated, reference-and-bind, L4-optional under its own named contract — the corpus shape that matches QorTroller's purpose (sovereign, presence-first, honest) rather than a generic ML dump.**

D-A1b-1 already refused the cheap path. This design freezes the expensive-correct path.

**No code in this change.** Next step after operator marks §10: implement §8 in a single focused PR with the §11 tests.

---

*End of A1-b design v0 — 2026-07-08.*
