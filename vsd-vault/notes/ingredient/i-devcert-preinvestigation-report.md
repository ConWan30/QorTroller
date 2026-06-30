---
type: ingredient
id: i-devcert-preinvestigation-report
title: Dev-Cert Pre-Investigation Report (Confirms 1-3) — verbatim
source: claude-code-investigation-2026-06-30
created: 2026-06-30T00:00:00Z
phase: VSD-LOOP
status: draft
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

External evidence note (provenance only — VSD-INV-6 forces a new ingredient id rather than a
silent edit if the source text drifts). Verbatim text of the READ-ONLY Dev-Cert Pre-Investigation
Report delivered by Claude Code on 2026-06-30. No paraphrase.

---

## Dev-Cert Pre-Investigation — Report

### Confirm 1 (F-CERT-001) — `developer_self` binding

**SHOWN:**
- `cert_scope` is set purely by the flag — a *regime label*, not a primitive binding:
  `novel_presence_fusion.py:281` -> `cert_scope = "developer_self" if developer_self_cert else "advisory"`.
  `population_certified=False` is hardcoded (`:307`).
- The proof object `FusedGamerPresenceProof` (`novel_presence_fusion.py:44-75`) folds these oracle
  fields: `cco_tier` (CCO), **`retina_verdict`** (PoCP/Retina screen-coupling, `:50`), **`poep_present`**
  (PoEP, `:51`), `l4_l5_l6_consistent`, `posca_*` (PoVCA). **There is no `kf_verdict` / authorship field
  anywhere on the proof.**
- `fuse()` builds `presence_score` from whichever oracles are present, omitting absent ones (`:233-242`);
  each abstains independently.
- The live USB co-capture (`cocapture_fields_from_pitl_meta`, `:102-138`) reads `poep_present` and
  `retina_coupled_verdict` from meta — both abstain unless populated (`:113-116`); **it never reads a
  kill-feed/authorship field.**
- **Recorded ground truth** — `audits/devcert-warzone-proof-1782523326.jsonl` (an actual
  `cert_scope="developer_self"` proof stream): `verdict=CONSISTENT_HUMAN_VERIFIED_HARDWARE`,
  `latest_poep_present=true`, `latest_cco=P-T3`, `latest_l4l5l6` true/false, **`window_retina_coupled: 0`**
  on every row. The screen-coupling PoCP contributed **zero**; the cert was driven by **PoEP + CCO + L4L5L6**.
- API emission (`operator_api/_app.py:1304-1326`) returns `poep_present`, `retina_verdict`, `cco_tier`,
  `l4_l5_l6_consistent`, `posca_verdict` — **no authorship field**.

**ANSWER:** **both (in schema), PoEP-in-practice, authorship = neither.** The `cert_scope` label binds no
primitive by itself; the proof *schema* folds both PoEP and PoCP as graceful-degrade oracles; but the
**live recorded cert is PoEP(+CCO+L4L5L6)-driven with screen-PoCP abstaining (`window_retina_coupled=0`)
and killfeed authorship entirely absent from the proof.** The design-review scope mismatch is
**confirmed**: the six levers (PoCP coupling + authorship) target primitives the live cert does **not** bind.
**GRADE: VERIFIED**

### Confirm 2 (F-CERT-002) — PoEP-liveness gate

**SHOWN:**
- Flag defaults: `poep_liveness_enabled` **False** (`config.py:2052-2054`); `developer_self_cert_enabled`
  **False** (`:2061`); `developer_self_cert_min_reflex_n` **30** (`:2064`). `L6_CHALLENGES_ENABLED`
  **not present in `bridge/.env`** -> effective = its default (documented False).
- **Current `.env` effective values** (read-only, `bridge/.env`): `DEVELOPER_SELF_CERT_ENABLED=true`
  (`:538`), `POEP_LIVENESS_ENABLED=true` (`:539`), `RETINA_GAME_CAPTURE_ENABLED=true` (`:548`).
  **The operator key is flipped on.**
- Two-key gate (`poep_activation.py:7-13, 31-51`): `poep_present_signal` returns `None` (abstain) unless
  **(a)** `poep_enabled` True **AND (b)** verdict != `calibration_incomplete` (data gate). It **cannot fire
  while the flag is off or N is short**.
- N gate (`l9_presence/poep_calibration.py`): L6B hard rule **N>=50** for the population model (`:9-10, 43-48`);
  a **developer-scoped `single_subject_reflex_model(min_n=30)`** exists (`:92-96` — "developer-scoped gate
  (30), not the population N>=50").
- The liveness verdict is **read from a file** written at enrollment (`read_session_poep_verdict`,
  `poep_activation.py:54-73`; loaded in `dualshock_integration.py:397-407`), i.e. a **session-level** verdict
  carried into every record — the recorded proof shows `window_poep_true=200` (the same session verdict
  repeated), not per-record live liveness.
- Recorded proof has `latest_poep_present=true` -> **both keys passed** (operator on + data gate satisfied).

**ANSWER:** **gate-honored.** The liveness field abstains unless both keys pass; it is currently *activated*
(flag on + enrollment verdict not `calibration_incomplete`), which is correct, not a bypass. The field is a
real PoEP liveness verdict (session-enrollment-scoped), not a weaker mislabel.
**GRADE: VERIFIED**

### Confirm 3 (F-CERT-004) — downstream consumers

**SHOWN:**
- `cert_scope`/`population_certified` consumers (13 files, non-test): `novel_presence_fusion.py` (sets),
  `operator_api/_app.py` (emits), `sdk/vapi_sdk.py` (`is_developer_self_certified`, `:182-184`),
  `scripts/record_devcert_session.py` + `scripts/poep_session_enroll.py` (recording), `audits/*.jsonl` (logs),
  `docs/*`, `d-developer-self-cert.md` (decision). **No marketplace / Curator / readiness / aggregate-trust
  consumer of `cert_scope` exists.**
- Honesty rails are hardcoded: `population_certified` **always False** (`novel_presence_fusion.py:307`,
  `operator_api/_app.py:1324`); `"certified": False` always on the endpoint (`:1326`, "never
  population/tournament-certified"); `"advisory": not _dev_self` (`:1325`).
- **`verifier_independence` — ABSENT** (grep: no files). Confirmed as expected.

**ANSWER:** **No laundering surface today.** Nothing weights `developer_self` into a score/listing/aggregate
as independent trust; the implicit independence rail is `population_certified=False` + `certified=False`
carried on every proof. **Latent risk:** that rail is *implicit* — there is no explicit `verifier_independence`
flag, so a *future* consumer that reads only `cert_scope`/`is_developer_self_certified()` without checking
`population_certified` could launder. No such consumer exists now.
**GRADE: VERIFIED**

### Synthesis (no decision — operator resolves D-CERT-1)

The source points toward **(b) keep `developer_self` = the working PoEP(+CCO+L4L5L6) cert; give the levers
(PoCP coupling + killfeed authorship) a separate new PoCP cert scope** — *or* **(a) with explicit versioning**
if folding into the existing scope. Reasoning: the proof schema already reserves a `retina_verdict` (PoCP)
slot, so (a) is mechanically possible, but the live cert **already emits recorded artifacts**
(`devcert-warzone-proof-*.jsonl`) as a PoEP-driven `CONSISTENT_HUMAN_VERIFIED_HARDWARE` with
`window_retina_coupled=0` — mutating that cert's meaning in place would change what an already-recorded scope
attests. **(c) two-primitive fold is NOT blocked** — Confirm 2 found the PoEP gate honored, not
bypassed/mislabeled.

**The single fact that most constrains the choice:** *the live dev-cert proof currently binds PoEP with the
screen-coupling PoCP contributing exactly zero (`window_retina_coupled=0`) and killfeed authorship entirely
absent from the proof schema* — i.e. the levers strengthen a primitive the recorded cert does not yet bind.

### Anomalies / drift surfaced (report only, not fixed)

1. **Load-bearing drift:** the entire capture/coupling/authorship line of work (Retina/PoCP) contributes
   **nothing** to the dev-cert that is actually being recorded (`window_retina_coupled=0` across the proof
   stream). The cert and the capture work are effectively decoupled today.
2. **`kf_verdict` (authorship) is absent from the proof schema** (`FusedGamerPresenceProof` has no field;
   `cocapture_fields_from_pitl_meta` doesn't read it). The state doc's "killfeed authorship" is wired into
   retina `status()` only, not into the cert.
3. **Orphaned config field:** `developer_self_cert_min_reflex_n` (config `:2064`, default 30) appears
   **unconsumed** — grep finds only its definition + comment. The effective developer N>=30 gate is a
   hardcoded default inside `single_subject_reflex_model(min_n=30)`, not driven by the config field.
4. **Two N thresholds coexist** (population N>=50 `_MIN_N` vs single-subject N>=30). Which one the live
   enrollment used is **not determinable from the proof artifact** alone (would require reading
   `scripts/poep_session_enroll.py`).
5. **Session-level vs per-record:** the cert's `poep_present=true` is a session-enrollment constant repeated
   per record (`window_poep_true=200`), not a continuous per-record liveness measurement — design-intended,
   but worth noting for "faithful rehearsal" framing.
6. **Implicit independence rail:** honesty against laundering rests on
   `population_certified=False`/`certified=False`, not an explicit `verifier_independence` field (Confirm 3
   latent risk).
7. **State-doc vs source:** the snapshot's "`developer_self` = PoEP liveness + developer profile" is
   **accurate in live practice** but **incomplete on schema** — the proof object is a multi-oracle fusion
   (PoEP + PoCP-retina + CCO + L4L5L6 + PoVCA). Source wins; flagged.
