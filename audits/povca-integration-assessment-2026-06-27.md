# PoVCA (cycle-42) — Integration Assessment & Correction Handoff

**To:** grok build · **From:** Claude (single-integrator pass) · **Date:** 2026-06-27
**Branch:** `feat/l9-consistency-adversarial-harness` · **Status:** corrected, all-green, **uncommitted** (operator decides commit)

## TL;DR
Your PoVCA scaffold had the right *shape* (compose-as-oracle, abstain-by-default, no FROZEN touch, the
field layout, the emulated-gate concept, PoSCA→PoVCA rename). But the **logic** shipped three defects that
the gates you ran (SDK + harness + PV-CI) could not see, plus a no-op and a coverage gap. I fixed all of them.
Nothing was committed before this. It is now green end-to-end and **honest** — the cycle-42 rails are enforced
in code, not just in comments.

## What I ran first (why your gates missed it)
Your "48 SDK tests + harness 83 + PV-CI 182" are all real and pass — but **none of them exercise the bridge
logic**: not the store insert, not the structure check, not the fuse posca branch. The first time the actual
co-capture insert ran (`test_nqpv_cocapture_store.py`, which you didn't run) it threw. Lesson for next time:
run `PYTHONPATH=bridge python -m pytest bridge/tests/test_nqpv_cocapture_store.py bridge/tests/test_novel_presence_fusion.py`
before declaring a store/fusion change done.

## Findings → fixes

### F1 · CRITICAL — `_check_structure_ok` failed OPEN (manufactured AUTHENTIC)
Original returned `len(input_events) > 0` (= True) whenever `l4_features` was absent — and even when L4 was
present and *anomalous* (`dist >= 7.009`) it fell through to the same `True`. So `structure_ok` was True for
macros, translators, and L4-flagged-anomalous input alike → `posca_verdict=AUTHENTIC` for non-human input.
That is the exact GCAP overclaim the cycle-42 note forbids, and the opposite of the function's own docstring.
**Fix (`posca_action_provenance.py`):** `structure_ok` is now **tri-state `Optional[bool]`** — `True` only when
L4 present AND `dist < L4_ANOMALY_THRESHOLD (7.009)`; `False` when L4 present AND `dist >= 7.009`; **`None`
(abstain)** when there is no authoring input or no usable L4 evidence. It NEVER returns True without evidence.

### F2 · HIGH — persistence was 100% broken (proven, broke 4 existing tests)
INSERT wrote 5 posca columns; `CREATE TABLE nqpv_cocapture_log` and `_NQPV_MIGRATIONS` had none → every
`insert_nqpv_cocapture` threw `no column named posca_verdict` on fresh AND existing DBs. `main.py` swallows it
best-effort, so it failed **silently** — cycle-33 co-capture persistence (live rows) was dead.
**Fix (`store/_core.py`):** added the 5 posca columns to the `CREATE TABLE` *and* 5 idempotent
`ALTER TABLE nqpv_cocapture_log ADD COLUMN posca_*` statements in `_NQPV_MIGRATIONS` (the loop swallows
duplicate-column, so fresh + the live 5.4 GB DB converge to the same schema).

### F3 · HIGH — commitment was dead code / fabricated
The real `compute_posca_commitment` was never called; `fuse()` emitted a fake `f"povca:{device}:{v}:{c}"`
string as `posca_commitment` (not recomputable). The real one also stringified a float `t` (non-deterministic).
**Fix:** `compute_posca_commitment` is now a deterministic byte encoding (`struct.pack`, domain tag
`QOR-POVCA-v1`, tri-state structure byte). It is **minted at action-detection** inside `detect_author_actions`
(when `device_id` + `poac_record_hash` are supplied) and carried on the action dict as `commitment`. `fuse()`
no longer fabricates — it takes a `posca_commitment` **pass-through** param. `dualshock_integration.py`,
`main.py`, and `operator_api/_app.py` wire the real commitment end-to-end (`""` when not computable = abstain).

### F4 · MEDIUM — "composes into the NQPV score" was a no-op
`contribs["posca"]` was set, but `_PROVISIONAL_WEIGHTS` has no `"posca"` key → `_w.get("posca",0)=0` →
posca contributed **zero** to `presence_score`. The claim was false.
**Fix (`novel_presence_fusion.py`):** posca is removed from `contribs` and is now an explicit **ADVISORY
field** (`posca_verdict`) that **does NOT move `presence_score`** — by design, until a measured RETINA-EXCL-2
study sets a calibrated weight under the anti-GCAP rail (fused TAR ≥ best single oracle). The verdict is
computed by one source of truth, `posca_verdict_from()`. Docstring + `notes` say so honestly.

### F5 · MEDIUM — zero coverage of the new logic → added 14 tests
`bridge/tests/test_posca_action_provenance.py` locks: tri-state structure (abstain w/o L4, False on anomalous,
never True w/o evidence), `posca_verdict_from` (emulated→UNVERIFIABLE, abstain→UNVERIFIABLE, AUTHENTIC,
ORPHAN_OR_WEAK), the emulated gate, commitment determinism + binding, detector binding via real
`assess_coherence`, **fuse posca is advisory-not-scored**, and the store roundtrip (locks F2).

### F6 · LOW — live discrete path is dormant (kept honest, not hidden)
`screen_events`/`input_events` aren't populated in the live continuous-controller-lobe path, so the hook
no-ops and posca abstains live. Correct-when-it-fires, honest meanwhile. **This is the real remaining
dependency** (see below), not a code defect.

## How PoVCA functions NOW (the behavioral contract)
- **Default-off, advisory.** No FROZEN-v1 / 228B PoAC / chain / IOTX. 0 invariants added (PV-CI still 182).
- **`structure_ok` tri-state** — `None` abstain is the default; AUTHENTIC is impossible without L4 evidence.
- **`posca_verdict`** (single source `posca_verdict_from`): `UNVERIFIABLE` (emulated device OR abstain),
  `AUTHENTIC` (structured + coupling ≥ 0.2 + real CCO device), `ORPHAN_OR_WEAK` (structured-but-weak or
  L4-anomalous).
- **Composes into NQPV as a FIELD on `FusedGamerPresenceProof`** — surfaced to the SDK + `/player/presence-proof`
  endpoint — but **does NOT influence `presence_score`** (anti-GCAP; gated on the measured study).
- **Commitment** is the real recomputable `QOR-POVCA-v1` hash, minted at detection, flowed through store →
  fuse → endpoint; `""` (abstain) when device/record/poac aren't available.
- **Persistence**: `nqpv_cocapture_log` carries the posca columns on fresh and existing DBs.
- **Emulated gate**: absent/FAIL/EMULATED/VIRTUAL CCO tier → `UNVERIFIABLE` (the translator cheat vector
  cannot author; only valid as a labeled red-team harness, never registered).

## Verification (all green)
| suite | result |
|---|---|
| `test_posca_action_provenance.py` (new) | 14 passed |
| `test_nqpv_cocapture_store.py` | 5 passed (was **4 failed** pre-fix) |
| `test_novel_presence_fusion.py` | 19 passed (no regression) |
| `test_nqpv_study` + `_corpus_loader` + `_offline_humanity` | 31 passed |
| SDK `test_vapi_sdk.py` | 48 passed |
| edited-module import smoke | OK |
| `scripts/vapi_invariant_gate.py` | PASS · 182 |
| VSD chain | untouched (43 links, head `8eed3160`) |

## Contracts to preserve going forward (please don't regress these)
1. `structure_ok` stays **tri-state**; never default `True` without L4 evidence.
2. posca stays **out of `_PROVISIONAL_WEIGHTS`** until a measured anti-GCAP study sets a weight.
3. Any new posca column → add to **BOTH** the `CREATE TABLE` and an idempotent `ALTER` migration.
4. Use **`posca_verdict_from`** as the single verdict source; don't re-implement the mapping.
5. Commitments via **`compute_posca_commitment`** (deterministic); never fabricate strings.

## Remaining work / next slices (yours to take)
1. **Populate `screen_events` + `input_events` live** — the dormant dependency. Gated on the WGC capture-rate
   fix (MPO-disable already got us 1.6→~7 fps; the ~7 fps ceiling is a capture-pipeline cost — downscale the
   frame *before* the full-res readback — measured separately this session).
2. **Confirm the L4-distance meta key.** I wired `l4_features` from best-effort
   `pitl_meta["l4_distance"] | ["pitl_l4_distance"]`. Verify which key actually carries the L4 Mahalanobis
   distance into the dualshock hook so structure becomes *real* (not always abstain) when the live path
   activates. (Harmless today since the path is dormant.)
3. **The measured study** (`oracle_panel` / nqpv study harness) consumes the posca rows and computes TAR/FAR
   with the anti-GCAP rail — only *after* that passes does a posca weight become defensible.

— End of handoff. The branch is green and uncommitted; commit/land is the operator's call.
