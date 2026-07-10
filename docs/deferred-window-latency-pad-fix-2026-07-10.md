# Deferred-Attestation Forward Window Latency Pad (Arc A)

**Status:** FIX DESIGN — audit PASS (Claude); **elevated build-gate G-VERIFY** folded below.  
**Goal:** Verifiable offline `authored>0` on saved RP archives (densecand_validate, M18) without replaying matches.  
**Rails:** forward-only pad · input-required preserved · pad=0 byte-identical · **pad persisted + re-applied in verify** · offline only · no PoAC/FROZEN/chain · PV-CI 182.

---

## 1. Claim / scope

**This fix recovers DEFERRED_AUTHORED classifications that fail only because under Remote Play the kill-row first appears after the narrow live R2 classify window ends — by optionally extending the window’s end by a bounded, empirically justified latency pad — without creating windows without input, without attributing kills that precede fire, and without changing K-floor, anti-tamper, or live capture.**

| In scope | Out of scope |
|----------|----------------|
| `l9_presence/kas_deferred.py` conjunction predicate | Live dense-candidate / OCR / session-anchor |
| `scripts/build_deferred_attestation.py` CLI param | Chain / PoAC / FROZEN |
| Offline re-runs on saved archives | “Fixing” 13 fps starvation |

---

## 2. Root cause (measured)

| Observation | Meaning |
|-------------|---------|
| densecand_validate deferred = `DEFERRED_OBSERVED_ONLY` | 1 AUTHORED + 7 OBSERVED + 36 unpromotable |
| 1+7 = 8 = live `inline_authored` | Recognition OK; conjunction demotes 7 real kills |
| Readability clean (80 reads / 0 false) | Not an OCR ceiling problem for this claim |
| Same shape as M18 deferred | Systemic RP fire→screen lag vs narrow R2 window |

**Mechanism:** `_classify_cluster` (`kas_deferred.py` ~L144–156) requires `_spans_overlap(cluster_span, window)`. Under RP, kill crops appear **after** R2 window end (FPS animation + stream delay), so overlap fails → `DEFERRED_OBSERVED` despite a real preceding fire.

Empirical fire→first-kill-row latencies (`audits/rp4-latency-recovery-2026-07-10.json`, nearest-preceding onset, Kill-1 excluded where noted):

| Session | Transport | n | median (s) | q1–q3 (s) | max (s) |
|---------|-----------|---|------------|-----------|---------|
| rp4_rp | Remote Play | 8 | **3.31** | 2.38–8.53 | 9.66 |
| M13 | HDMI direct | 18 | 4.68 | 2.97–6.98 | 9.03 |

(Assignment “~0.6–2.3s steady / tail ~4s” understates this file’s medians; **pad justification uses this JSON as the primary empirical source.**)

---

## 3. Exact predicate + pad math

### 3.1 Parameter

| Name | Type | Default | Meaning |
|------|------|---------|---------|
| `window_latency_pad_ms` | `float` ≥ 0 | **0** | Milliseconds added to each R2 window’s **end** for deferred conjunction only |

Propagate: `build_deferred_record(..., window_latency_pad_ms=0.0)` → `_classify_cluster(..., window_latency_pad_ms=...)`.  
CLI: `--window-latency-pad-ms` on `scripts/build_deferred_attestation.py` (default 0).

### 3.2 Predicate choice (D-DWP-2) — **first-appearance, forward-padded**

**When `window_latency_pad_ms <= 0` (byte-identical path):**

```text
# UNCHANGED from today:
window_hit iff exists window w:
  _spans_overlap(span[0], span[1], w[0], w[1])
```

**When `window_latency_pad_ms > 0` (RP recovery path):**

```text
pad = window_latency_pad_ms
# Kill first appearance must lie in [fire_window_start, fire_window_end + pad]
window_hit iff exists window w = [w0, w1] and span is not None:
  w0 <= span[0] <= (w1 + pad)
```

where `span = _cluster_span_ms(cluster)` = (min read ts_ms, max read ts_ms).

### 3.3 Why first-appearance (not padded span-overlap)

| Predicate | Causal story |
|-----------|----------------|
| **`span[0] ∈ [w0, w1+pad]`** | “The kill **first became visible** no earlier than the R2 window opened and no later than window-end + RP lag budget.” Kills that **precede** fire (span[0] < w0) never attribute even if the row lingers into the window. |
| Padded full overlap `overlap(span, [w0, w1+pad])` | A cluster that **started before** fire but remains on screen can still overlap the padded interval → weaker causality. |

First-appearance is **stricter and more directional** — preferred for anti-cheat authorship.

### 3.4 Forward-only

- Pad applies only to **w1** (end), never subtracts from **w0**.  
- No synthetic windows: if `windows` is empty, zero AUTHORED regardless of pad.

### 3.5 Pad value (D-DWP-1) — fixed conservative, empirically bounded

| Choice | Value | Justification |
|--------|-------|----------------|
| **Code default** | **0 ms** | Byte-identical; no silent RP bias on HDMI/direct archives |
| **Recommended RP operator value** | **4000 ms** | Slightly above rp4_rp median fire→kill (3.31 s); covers the common 1.4–~4 s band of the measured list without adopting the 10 s measurement cap or q3 (~8.5 s) which would over-attribute |
| **Not chosen: pure p90** | ~8–9 s from same file | Too loose for v0; would need separate adversarial FAR study |
| **Not chosen: 3000 ms only** | Below measured median | Likely leaves residual OBSERVED on this corpus |

### 3.6 Elevated build-gate **G-VERIFY** (audit → hard gate)

**Problem:** If AUTHORED was decided with `pad > 0` but `verify_deferred_record` re-runs conjunction at pad=0, padded clusters fail verification → result is **not verifiable** (defeats the arc’s purpose).

**Required:**

| Surface | Requirement |
|---------|-------------|
| **Record field** | `window_latency_pad_ms: float` on `DeferredAttestationRecord` / `to_dict()` — **always present** (0 when unused) |
| **Build** | `build_deferred_record(..., window_latency_pad_ms=pad)` stores the same value used for classification |
| **Verify** | `verify_deferred_record` reads `record.window_latency_pad_ms` (or dict key) and **re-applies the identical predicate** (legacy overlap if 0; first-appearance if >0) when recomputing cluster verdicts / recounting authored |
| **Notes** | May still note pad in `notes` for humans; **field is authoritative**, not notes-only |
| **T7** | Assert: build with pad=4000 → verify **passes**; mutate pad to 0 on a copy → verify **fails** or recount drops AUTHORED (detects pad/result mismatch) |

Without G-VERIFY, do not ship.

---

## 4. Five hard rails (audit checklist)

| # | Rail | Enforcement |
|---|------|-------------|
| **1** | **Forward-only** | Only `w1 + pad`; never `w0 - pad` |
| **2** | **Input-required** | Pad never creates windows; empty onsets → empty windows → 0 AUTHORED. **Test:** forged/idle no-onset session stays 0 authored at any pad including 4000 |
| **3** | **Bounded + empirical** | Recommended 4000 ms from `rp4-latency-recovery` median+; default 0; not unbounded |
| **4** | **Precise predicate** | pad>0 → first-appearance; pad=0 → legacy overlap (byte-identical) |
| **5** | **Default 0 / offline / no crypto surface** | No chain, FROZEN, PoAC, 228B; PV-CI 182 |
| **G-VERIFY** | **Pad on record + verify re-applies same pad/predicate** | Else padded AUTHORED is non-verifiable |

---

## 5. CODE-TRUTH

| Symbol | Location |
|--------|----------|
| `_spans_overlap` | `l9_presence/kas_deferred.py` ~L104–105 |
| `_cluster_span_ms` | same ~L108–113 |
| `_classify_cluster` | same ~L116–156 (conjunction ~L144–156) |
| `build_deferred_record` | same ~L159+ |
| `DEFAULT_K_FLOOR = 3`, `DEFAULT_MIN_KILLS` | module top / defaults |
| `DEFERRED_AUTHORED` / `DEFERRED_OBSERVED` | same |
| `verify_deferred_record` | same (must accept optional pad field or recompute with same pad) |
| Runner | `scripts/build_deferred_attestation.py` |
| Latency source | `audits/rp4-latency-recovery-2026-07-10.json` |
| Fixtures | `forged_*.jsonl` / `genuine_*.jsonl` (no-onset / idle guard tests) |
| Prior offline success | M14 deferred AUTHORED_SESSION (regression) |

**Implementation sketch (no new domain tag):**

```python
def _window_hit(span, windows, pad_ms: float):
    if not span or not windows:
        return None
    s0, s1 = span
    if pad_ms <= 0:
        for w0, w1 in windows:
            if _spans_overlap(s0, s1, float(w0), float(w1)):
                return [float(w0), float(w1)]
        return None
    pad = float(pad_ms)
    for w0, w1 in windows:
        w0f, w1f = float(w0), float(w1)
        if w0f <= s0 <= (w1f + pad):
            return [w0f, w1f]  # record unpadded window for audit; note pad separately
    return None
```

`window_hit_ms` on the cluster should still store the **original** R2 window bounds (not the padded end) so logs stay comparable; pad is session-level metadata.

---

## 6. Validation table (all offline)

| Case | Archive / fixture | Pad | Expected |
|------|-------------------|-----|----------|
| **V1** | densecand_validate | **4000** | OBSERVED→AUTHORED for the 7 lag-demoted kills; session toward `DEFERRED_AUTHORED_SESSION` if authored ≥ min_kills (expect ~8 authored ≈ inline_authored=8) |
| **V2** | M18 | **4000** | Climb off pure 0 / OBSERVED_ONLY if readable kills exist with lag structure |
| **V3** | M14 | **4000** | Regression: still AUTHORED_SESSION; authored count must not explode unboundedly (report delta; soft alert if authored >> prior×3 without note) |
| **V4** | forged / idle **no-onset** | **4000** | **0 AUTHORED** — rail 2 |
| **V5** | densecand_validate | **0** | Byte-identical to pre-fix deferred (1 AUTHORED / 7 OBSERVED class shape) |

Also re-run `verify_deferred_record` on each produced record.

---

## 7. Test plan (unit)

| ID | Assert |
|----|--------|
| T1 | pad=0: classifications identical to current fixture golden |
| T2 | pad>0: kill with span[0] just after w1 (within pad) → AUTHORED |
| T3 | pad>0: kill with span[0] < w0 → still OBSERVED (no backward attribution) |
| T4 | pad>0, windows=[] → 0 AUTHORED |
| T5 | forged no-onset composite/window set → 0 AUTHORED at pad=4000 |
| T6 | pad only extends end: unit on `_window_hit` math |
| T7 | **G-VERIFY:** build pad=4000 → `verify_deferred_record` OK; record field `window_latency_pad_ms==4000`; zeroing pad on a deep copy makes verify fail or authored count drop |
| T8 | pad field defaults to 0 on legacy-shaped dicts (fail-closed to byte-identical verify) |

---

## 8. Operator-decisions table

| ID | Decision | Default | Operator |
|----|----------|---------|----------|
| **D-DWP-1** | Recommended RP pad = **4000 ms** (empirical median+); code default **0** | Yes | ☐ accept ☐ amend |
| **D-DWP-2** | pad>0 uses **first-appearance** predicate; pad=0 keeps **legacy overlap** | Yes | ☐ accept ☐ amend |
| **D-DWP-3** | Param name `window_latency_pad_ms` / CLI `--window-latency-pad-ms` | Yes | ☐ accept ☐ amend |
| **D-DWP-4** | No automatic pad in production defaults; operator sets for RP offline runs | Yes | ☐ accept ☐ amend |
| **D-DWP-5** | Proceed Claude audit → build → offline validation table → stage | Hold for GO | ☐ GO ☐ hold |
| **D-DWP-6** | **G-VERIFY** mandatory: persist `window_latency_pad_ms` + verify re-applies | Yes | ☐ accept ☐ amend |

---

## 9. Honest limits

1. Does **not** fix live dense-candidate under 13 fps starvation.  
2. Does **not** prove field anti-cheat FAR; offline RP lag recovery only.  
3. 4000 ms will **not** recover the extreme q3/max (~8–9 s) latencies in the recovery JSON without a higher pad or second study.  
4. Pad is **transport-aware operator choice**, not a frozen protocol constant.  
5. Still `advisory=True` / developer_self on deferred records.

---

## 10. Success criterion (operator-facing)

A committed deferred record for **densecand_validate** with pad=4000 showing:

- `deferred_authored` significantly above the pad=0 baseline (target ~8 / matching inline)  
- `verify_deferred_record` OK  
- forged/idle still 0  
- **No new match required**

That is the verifiable, re-runnable authorship fix on saved data.

---

*End of deferred window latency pad design v0 — 2026-07-10.*
