# Golden Offline Authored Pack (P0 #2)

**The card-free "run this → authored>0" proof.** One command reproduces a verifiable Remote-Play
authorship figure from a fixed, known-good archive — **without playing another match**, no rig, no
chain, no IOTX, no FROZEN-v1 surface touched.

```bash
python scripts/golden_offline_authored.py
```

Exit `0` = PASS (≥1 golden reproduced `DEFERRED_AUTHORED_SESSION` + verifier OK) ·
`1` = FAIL (a present golden regressed — deferred logic broke) ·
`2` = no golden archive on disk (restore one; **never a silent pass**).

## Why this is the reliability path today

Live `authored>0` is still fragile under capture lag (the D1.1/F2 lag work targets that). The
**deferred-attestation** path (arc A / RP-2d) is the proof that works *now*: the session's archive
is manifest-committed live evidence, and attesting from it post-hoc is the same evidence read later
(identical trust boundary at `developer_self` scope). On both goldens the **live** KAS verdict is
`INSUFFICIENT_KILLS` (RP thinned the live crops to below the K=3 floor) yet the deferred path
recovers **authored=3** — that recovery *is* the card-free result.

| Golden archive | Live KAS | Deferred @ pad=4000 | Verifier |
|---|---|---|---|
| `densecand_validate_1783711025` | INSUFFICIENT_KILLS | **DEFERRED_AUTHORED_SESSION authored=3** | OK (40 checks) |
| `match14_rp_option_b_1783475385` | INSUFFICIENT_KILLS | **DEFERRED_AUTHORED_SESSION authored=3** | OK (23 checks) |

## Honest scope — do not soften

- **Bounded-lag only.** `authored>0` is guaranteed for archives whose RP fire→kill gap fits inside
  the **4000 ms** window-latency pad (arc A, forward first-appearance predicate). The pad is applied
  identically at build and re-derived by the verifier, so it is auditable, not a fudge factor.
- **M18 is intentionally excluded.** M18's >4 s lag is an **honest 0** — `pad=4000` recovered only
  3/8 of its kills. A looser pad would paper over the limit, not fix it; the >4 s tail needs a
  **deferred-FAR study**, not a bigger number. `test_golden_offline_pack::test_no_m18_honest_scope_rail`
  pins this — M18 can never be quietly promoted into the golden set.
- **`developer_self` scope.** This is a card-free authorship *demonstration*, not a
  population-certified or field-FAR claim, and not identity attestation.

## What is committed vs local

`retina_kf_archive/` is **gitignored** (biometric-capture policy) — the crop archives live on the
operator's disk, not in the repo. **Committed:** `scripts/golden_offline_authored.py` + this doc +
`l9_presence/tests/test_golden_offline_pack.py`. **Local (operator's reliability asset):** the two
golden archives + their `audits/rp_ocr_scan_*.json` / `audits/kas_record_*.json` inputs. If a golden
is evicted, the pack reports `MISSING` and names it; re-derive via `scripts/rp_ocr_precision_scan.py`
+ `scripts/build_deferred_attestation.py` on a retained archive, or capture a fresh bounded-lag RP
session.

## Acceptance checklist (bars — frozen)

**Status:** FORMAL (2026-07-10). Mechanics are built (`scripts/golden_offline_authored.py`);
this section is the authoritative pass/fail bar. P0 #2 is **closed** when this checklist is
enforced by the runner + tests and a clean `exit 0` is the only accepted green signal.

### A. Verdict bar (per golden)

| Check | PASS only if | FAIL if |
|-------|--------------|---------|
| **A1 Session verdict** | Deferred record `verdict == DEFERRED_AUTHORED_SESSION` | Any other verdict (`DEFERRED_OBSERVED_ONLY`, `UNVERIFIABLE`, live `AUTHORED_SESSION`, missing record) |
| **A2 Authored floor** | `deferred_authored >= 2` | `deferred_authored < 2` even if session verdict string is wrongfully set |
| **A3 Not live-conflated** | Record schema is deferred tier (`qortroller-kas-deferred-v0` or current deferred schema); live KAS may still be `INSUFFICIENT_KILLS` | Treating live KAS `AUTHORED_SESSION` as pack success |

**Rationale:** Session-level `DEFERRED_AUTHORED_SESSION` alone is insufficient without a numeric
floor (guards empty/degenerate records). Floor **≥ 2** matches `DEFAULT_MIN_KILLS` discipline
and both current goldens (authored=3).

### B. Verifier bar (per golden)

| Check | PASS only if | FAIL if |
|-------|--------------|---------|
| **B1 Crop re-hash** | `verify_deferred_record` (or pack-equivalent) **OK** — every referenced crop SHA matches the sealed manifest | `verify=FAIL` / anti-tamper / sha mismatch |
| **B2 Pad consistency** | Build used `window_latency_pad_ms` re-applied identically at verify (G-VERIFY) | Padded AUTHORED that fails when verify uses pad=0 |

**Hard rule:** **No PASS on verify=FAIL.** A green deferred verdict with a broken verifier is a
**FAIL**, not a soft warn.

### C. Presence / absence of goldens (pack-level exits)

| Situation | Exit | Meaning |
|-----------|------|---------|
| All present goldens meet A+B | **0** | PASS |
| Any **present** golden fails A or B (regression) | **1** | FAIL — deferred logic or inputs broke |
| Required golden archive **MISSING** on disk | **2** | Incomplete environment — restore archive; **never treat as PASS** |
| Mix of missing + present regression | **1** preferred if any present fails; else **2** if only missing | Do not hide regression behind missing |

**Hard rule:** Missing ≠ pass. Regression ≠ skip.

### D. Three-artifact join (per golden)

The pack asserts the U1 join key across:

| Artifact | Must hold |
|----------|-----------|
| **Archive `manifest.json`** | `session_id` present; crop count / shas consistent with deferred record |
| **KAS record** (`audits/kas_record_*`) | Same `session_id` (or explicit pre-U1 note if ever allowed — **not** for new goldens) |
| **Deferred record** | Same `session_id`; `source_kas_commitment` matches KAS commitment when present |

**FAIL** if any of: session_id missing, mismatch across the three, or deferred not bound to the
manifest’s sealed crops. This is the anti-splice rail for the pack, not optional metadata.

### E. Bounded-lag rail (set membership)

| Rule | Spec |
|------|------|
| **E1 Pad ceiling** | Goldens are validated at **`window_latency_pad_ms = 4000`** (arc A recommended RP value). Code default remains 0 for non-RP byte-identical paths. |
| **E2 Set pin** | Golden set is **bounded-lag only**. **M18-class is excluded** (honest 0 / partial recovery under 4 s pad). `test_no_m18_honest_scope_rail` (or successor) must stay green. |
| **E3 New golden admission** | Any **new** golden MUST document: (1) archive id, (2) **measured fire→kill lag** (method + median/p90 or max observed), (3) why it fits ≤ pad budget, (4) live KAS verdict + deferred authored count + verify OK. |
| **E4 Promotion ban** | Do not add a golden solely to “make exit 0” after a code change that fails existing goldens — fix logic or document a deliberate schema/version bump. |

### F. Reviewer-facing PASS line

A human or CI reviewer should accept **only** a line equivalent to:

```text
GOLDEN OFFLINE AUTHORED PACK: PASS
  goldens=N present=N missing=0
  each: verdict=DEFERRED_AUTHORED_SESSION authored>=2 verify=OK session_id=joined pad_ms=4000
  scope=developer_self bounded_lag=true m18_excluded=true
  exit=0
```

**Reject** any of:

```text
exit=0 with missing>0
exit=0 with verify=FAIL on any golden
exit=0 with verdict!=DEFERRED_AUTHORED_SESSION
exit=0 with authored<2
exit=0 with m18 in golden set
```

Exact runner stdout may vary in formatting; the **semantic fields above are mandatory**.

### G. Re-run cadence (when the pack must be green)

| Trigger | Required |
|---------|----------|
| **Before any external demo / pilot / organizer handoff** that cites card-free RP authorship | `python scripts/golden_offline_authored.py` → exit 0 |
| **Before merge** of changes touching `kas_deferred.py`, deferred verify, window pad, golden script, or golden set membership | exit 0 (CI or pre-commit operator run) |
| **After restoring or replacing a local golden archive** | exit 0 before claiming the pack is healthy |
| **Routine** | Recommended weekly if actively shipping authorship/lag work; otherwise on-demand at the triggers above |

Cadence is **process**, not a new FROZEN invariant — but shipping an external claim without a
recent exit 0 is an honesty violation of this checklist.

### H. Checklist summary (operator)

- [ ] **A1–A3** Session verdict = `DEFERRED_AUTHORED_SESSION` only; `authored >= 2`; not live-conflated  
- [ ] **B1–B2** Verifier OK (crop re-hash + pad re-apply); never PASS on verify=FAIL  
- [ ] **C** Present regression → exit 1; missing archive → exit 2; neither is pass  
- [ ] **D** `session_id` join: manifest + KAS + deferred  
- [ ] **E** Pad 4000; bounded-lag set; M18 excluded; new goldens state measured lag  
- [ ] **F** Reviewer PASS line semantics satisfied  
- [ ] **G** Re-run before external demo/pilot and before deferred-logic merges  

**P0 #2 closed** when: runner + tests enforce A–E, F is what reviewers look for, and G is the
operator habit for external claims.
