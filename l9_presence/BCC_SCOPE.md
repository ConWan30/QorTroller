# Behavioral Capture Chain (BCC) — Scope

**Status:** SCOPE / design-only. A **sealed, dormant-but-active developer reference lane**
that grows the behavioral corpus from casual gameplay (Witness-harvested, GIC-style) **without
touching any proven system or number.** It is an accumulator, not an input to any verdict.

## The defining property: ISOLATION (load-bearing)
BCC is **read-only with respect to every proven system.** It accumulates into its **own sealed
lane** (`bcc_l9/` + its own chain) and **never** writes to, calls, or mutates the separation/
identity/PoEP machinery. If BCC ever changed a proven number, it would be a bug, not a feature.
Promoting BCC data *into* a proven corpus is **explicitly out of scope** (see below).

## Mythos real-time alignment audit (2026-05-22)
- **mythos_corpus_drift = 0** → separation/GIC/AIT corpus state is clean. **BCC's contract is to
  keep it 0** — it must never perturb separation_ratio (1.261), AIT, GIC, or TGE-blocker state.
- **mythos_frozen_drift = 1 / mythos_crypto_drift = 1** → the two pre-existing operator-gated
  items (INV-016, VAPI-O3-SUPERSEDE-v1). Guardrails: BCC adds no pinned invariant / commitment
  family except via ceremony; `QORTROLLER-BCC-*` stays a candidate tag (not registered).

## What it is
A passive, provenance-chained accumulator the Witness Agent fills while you play casually —
the GIC pattern applied to behavioral capture: per-capture, quality-gated, hash-chained, in its
own lane. It deepens the *developer's own* model and grows a tamper-evident reference pile that
*could later* be promoted, by a separate explicit action, into the proven pipelines.

## Two sub-lanes
- **Sub-lane A — passive (active gameplay):** harvest L9 render-loop feature vectors per session
  from normal aim-input + screen optical flow. Zero interaction. The truly-passive growth path.
- **Sub-lane B — opportunistic (GAD `MENU_DETECTED` windows only):** optionally fire a PoEP
  micro-challenge during a detected lull → harvest a reflex/force sample. PoEP is inherently
  active, so this is semi-passive and **separately opt-in** (off even when sub-lane A is on).

## Isolation contract (what BCC must NEVER touch)
| Proven system / number | BCC obligation |
|---|---|
| `separation_defensibility_log`, `separation_ratio_snapshots`, separation ratio **1.261**, all-pairs gate | **never write / never call**; BCC computes no separation |
| Multi-player separation + identity (LOO, EER **29.2%**) | **out of scope** — BCC is single-developer depth, adds no players |
| L4 thresholds (**7.009 / 5.367**), `l4_threshold_tracks`, calibration | **never write** |
| PoEP calibration model — band **[209.6, 355.0]**, device_signatures, `poep_verify` | **never write**; BCC does not feed PoEP verdicts |
| `behavioral_lattice` / GCAP numbers | **never write** |
| Corpora `cocapture_l9/`, `sessions_l9/`, `poep_l9/` | **never write** — BCC writes only to `bcc_l9/` |
| GIC / WEC / CORPUS-SNAPSHOT chains | untouched — BCC is a **parallel** chain, not a link in any of them |

## Chain (own lane, candidate-frozen)
`BCC_N = SHA-256(b"QORTROLLER-BCC-GENESIS-v0" / prev(32) || feature_digest(32) || quality_code(1)
|| sub_lane(1) || ts_ns_be(8))`. Own genesis tag, own store, own monotonic chain — tamper-
evident reference provenance, so the pile is provably real gated gameplay, not fabrication.
Candidate v0 (not a registered PATTERN-017 family; registration would be a separate ceremony).

## Activation posture — dormant but active when necessary
- `bcc_enabled=False` **default** → fully dormant, zero behavior, zero overhead.
- Developer flips it on to accumulate; flips off to sleep. Sub-lane B is a second, independent flag.
- PCC/GAD-gated like GIC: only NOMINAL + EXCLUSIVE_USB captures chain; menu-window detection for sub-lane B.
- Consent-bound, gamer-owned (the dev's own data), local-only (`bcc_l9/` gitignored).

## Promotion is OUT OF SCOPE (the firewall)
BCC **only accumulates.** Nothing reads BCC into a proven pipeline automatically. Promoting BCC
captures into `cocapture_l9`/PoEP/lattice corpora would be a **separate, explicit, reviewed
action** that **re-runs the proven analyses from scratch** on the enlarged corpus — never a
silent mutation of an existing number. That firewall is what lets BCC lie dormant and grow
safely without ever putting the proven results at risk.

## Honest constraints
- **Depth, not breadth.** BCC grows the developer's own session count + the population reflex
  band; it does **not** add players, so it does **not** move the multi-person separation/lattice
  ceiling. That lever still needs more people.
- **PoEP is only semi-passive** (sub-lane B is a micro-interaction at menus, not invisible).
- **Capture overhead** — sub-lane A needs screen capture running during play (mss/WGC).
- **No number changes, ever** — by construction; verified by keeping `mythos_corpus_drift = 0`.

## What this is NOT
Not a separation/identity system. Not a PoEP verdict input. Not a modifier of any proven number.
Not auto-promoted. Not a registered primitive. A dormant, isolated, provenance-chained developer
reference that turns casual play into a safe, growing pile — and nothing more until you say so.
