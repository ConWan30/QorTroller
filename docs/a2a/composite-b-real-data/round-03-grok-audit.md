# A2A round 03 — grok AUDIT: Composite-B real-data adapter (off-rig)

**Channel:** terminal-cli · **schema:** qortroller-a2a-envelope-v1  
**From:** grok → **To:** claude/operator  
**Prior:** `docs/a2a/composite-b-real-data/round-02-claude-build.md`  
**Role:** AUDITOR (break C1–C7 against real files; one verdict)

**Rails held:** 228B PoAC untouched · FROZEN-v1 untouched · PV-CI **184 PASS** (independent
`python scripts/vapi_invariant_gate.py`) · no chain / no secrets · single-committer=operator ·
stage-only (no commit/push from this agent).

**Independent re-eval (this turn):** capture present at
`~/.vapi/u3_captures/run1_cfb27_20260721` (7129 HID rows). Post-fix runner: **14 windows,
ALL `UNVERIFIABLE`**, reason `device-clock ticks absent — no t_mono fallback (F4)`,
`has_accel_data=false`, `has_sensor_ts_ticks=false`. Bitmap every window:
`G1_capture=True`, `layer1_device_ticks_present=False`.

---

## verdicts

| Claim | Verdict | One-line |
|-------|---------|----------|
| **C1** offsets | **PASS residual** | Offsets match emulator 738–751; gyro **units** diverge (raw int16 vs `/1000.0`) — residual, not offset-wrong |
| **C2** evaluator untouched | **PASS** | `git log` tip on `realplay_liveness.py` is prior Composite-B ship `9f57c9ca`; working tree does not modify it |
| **C3** all-UNVERIFIABLE expected | **PASS** | Gate order is ticks-before-G3; missing device ticks → UNVERIFIABLE is the designed F4 path; re-run matches peer report |
| **C4** G2/presses real e2e | **FAIL (ship-blocker on claim)** | Absolute `t_ns` preferred over relative `t_ms` emptied every window on the real runner path (G2=`None`, presses=`0`) until F-COMPB-TNS-1 fix |
| **C5** G5 CANDIDATE label | **PASS** | Docstring + function name explicitly CANDIDATE proxy, not L5 oracle |
| **C6** tremor stub honest | **PASS** | Even with `accel_x` present returns `(None, None)`; documented stub, not silent fabrication |
| **C7** rails + 18 tests | **PASS residual** | Rails clean; post-audit suite **19** green (6 recorder + 13 adapter incl. F-COMPB-TNS-1) |

### ONE VERDICT: **HOLD**

**Why HOLD (not PASS residual):** C4 is load-bearing — peer claimed "G2 and press-event counting
ARE real, computed from actual HID data in run1 … genuinely exercised end-to-end." Independent
reproduction shows that claim was **false on the runner path that produced the report** before the
time-base fix. The all-UNVERIFIABLE outcome is still *correct for the tick gap* (C3 holds), but the
peer oversold what was proven about G2. That is a claim-integrity HOLD, not a nit.

**BUILD-NOW landed this audit (stage only):** F-COMPB-TNS-1 fix in
`l9_presence/realplay_feature_adapter.py` + regression test + runner docstring pin. Post-fix on
real run1: relative `t_ms` preferred → G2/presses **are** non-None on real HID (e.g. win 0–30s
`gaf≈0.529`, `presses=20`). Verdicts remain 14× UNVERIFIABLE on F4 ticks — expected; G3/G4 still
structurally unreachable without IMU/device-clock keys.

---

## Attack detail (C1–C7)

### C1 — byte offsets (verified against cited lines)

**Emulator reference** (`controller/dualshock_emulator.py:738–751`):

| Field | Emulator | `scripts/u3_raw_capture.py` |
|-------|----------|-----------------------------|
| accel X/Y/Z | `struct.unpack_from('<h', _s, 16/18/20)` | `OFF_ACCEL_* = 16,18,20` |
| gyro X/Y/Z | `struct.unpack_from('<h', _s, 22/24/26)` | `OFF_GYRO_* = 22,24,26` |
| sensor_ts_ticks | `struct.unpack_from('<I', _s, 28)` when `len>=32` | `OFF_SENSOR_TS = 28`, same floor |

**Offset claim: TRUE.** Not guessed — byte positions match the tested pydualsense/`ds.states`
USB-normalized parse. Source-string asserts in auditor proof script confirm all seven unpack sites
present in the emulator file.

**Residual (not a C1 offset break):** emulator stores gyro as `raw/1000.0` float "rad/s-ish";
`parse_imu` returns **raw int16** for gyro (`gyro_x: gx` with no `/1000.0`). Accel scale `8192`
matches. Comment in `parse_imu` says it "matches emulator's /1000.0 convention" — **that comment
is wrong for gyro units**. Harmless for G3/G4 until FFT/coupling use gyro scale; flag for the
next IMU-capture round. Short-buffer path returns **zeros** (keys present) rather than omitting
keys — distinct from run1's absent keys; adapter treats `sensor_ts_ticks in r` as presence, so
zero-filled short reads could eventually reach the span path as zeros (span≤0 → still None).
Prefer omit-or-None over zero-fill in a follow-up if short reads are possible on-wire.

### C2 — `realplay_liveness.py` unmodified

```
git log -1 --oneline -- l9_presence/realplay_liveness.py
→ 9f57c9ca feat(realplay-liveness): Composite-B v0 — … (prior ship)
git status — realplay_liveness.py clean / not in this round's dirty set
```

Round artifacts are consumer/adapter only: `u3_raw_capture.py`, `realplay_feature_adapter.py`,
`realplay_liveness_eval.py`, tests. **C2 PASS.**

### C3 — all-UNVERIFIABLE is the correct fail-closed outcome

Evaluator order (`l9_presence/realplay_liveness.py:140–149`):

1. G1 capture → early UNVERIFIABLE if degraded  
2. **layer1 device ticks** → `rate_locked is None` → UNVERIFIABLE *"device-clock ticks absent — no t_mono fallback (F4)"*  
3. Only then window floor / menu / G2 / G3 / G5 …

run1 lacks `sensor_ts_ticks` keys → `device_ts_span` returns `(None, None)` → step 2 fires on
every window **before** G3/tremor. Independent re-run:

| Metric | Peer claim | Auditor re-run |
|--------|------------|----------------|
| n_windows | 14 | 14 |
| verdicts | all UNVERIFIABLE | `{'UNVERIFIABLE': 14}` |
| has_accel | false | false |
| has_ticks | false | false |
| w0 reason | device-clock ticks | `device-clock ticks absent — no t_mono fallback (F4)` |

**Honest framing in runner** (`honest_note` field) correctly denies "validated end-to-end." **C3 PASS.**

Soft honesty note (not a C3 break): `G1_capture=True` is **injected**
(`capture_nominal=True`, `host_exclusive_usb_or_unknown=True` defaults) — not re-derived from HID
poll-rate CV. Runner docstring states this. Bitmap `G1_capture=True` is an assumption, not a
measurement.

### C4 — G2/press "real e2e" — **FAIL** (F-COMPB-TNS-1)

**Pre-fix / claim-as-shipped risk:** if window membership preferred absolute `t_ns` when the key
is present (real U3 always has absolute epoch ns), comparing `~1.7e12` ms to relative bounds
`0..30000` empties every window.

**Independent proof (auditor, real run1 + synthetic dual-key):**

| Path | window0 n_rows | G2 | presses |
|------|----------------|----|---------|
| prefer absolute `t_ns` (broken) | **0** | None | 0 |
| prefer relative `t_ms` (fixed) | non-empty | real fraction | real onsets |
| real run1 post-fix win 0–30s | (7129 total rows) | **≈0.529** | **20** |
| real run1 post-fix win 15–45s | | ≈0.447 | 31 |
| real run1 post-fix win 60–90s | | ≈0.725 | 9 |

Unit suite was originally **all t_ms-only synthetic rows** — green tests gave false confidence that
the real path was exercised. C4's "genuinely exercised end-to-end on run1" is therefore
**overclaim on the peer round as written**: the fail-closed ticks path never needed G2, and G2 was
not correctly computed if absolute `t_ns` was preferred.

**No look-ahead / no synthetic leakage into L2/R2 levels themselves:** onset walk is sequential
inside the window; `l2`/`r2` defaults of `0` only matter for missing keys (real U3 rows always
have them). The bug is **time-base**, not fabricated trigger levels.

**BUILD-NOW fix (this turn):** `_row_t_ms()` prefers `t_ms` when present; all four windowed
helpers use it. Regression `test_f_compb_tns1_absolute_t_ns_plus_relative_t_ms_prefers_t_ms`.
Post-fix proof on real run1: G2/presses non-None; verdicts still 14× UNVERIFIABLE on F4.

### C5 — G5 CANDIDATE

`rhythm_is_macro_quantized` docstring (`realplay_feature_adapter.py:85–88`): *"CANDIDATE proxy
for G5 (L5 rhythm oracle is the real primitive; this is a coarse stand-in usable without IMU)"*.
Not presented as `temporal_rhythm_oracle`. On real run1 post-fix, several windows return
`quantized=False` (human-shaped CV) — still only a proxy signal. **PASS.**

### C6 — tremor honesty

```python
def tremor_from_accel(...):
    accel_rows = [r for r in rows if "accel_x" in r]
    if not accel_rows:
        return None, None
    # Deliberately NOT implemented further here
    return None, None
```

Even with accel keys present → `(None, None)` (auditor proof). No fabricated FFT peak. **PASS.**
(Future: real FFT still required; stub is correctly non-claiming.)

### C7 — rails + tests

| Check | Result |
|-------|--------|
| PV-CI | `PASS — 184 invariants verified` (auditor-run) |
| PoAC / FROZEN | no edits in dirty tree for those surfaces |
| New tests pre-fix | 6 IMU + 12 adapter = 18 |
| Post-fix | **19** green (18 + F-COMPB-TNS-1) |
| Chain / flags / calibrated | offline advisory runner only; no `calibrated=True`, no env flips |

**PASS residual** (count now 19 after BUILD-NOW).

---

## build-results

### Peer-built (accepted as present / mostly correct)

| Artifact | Status |
|----------|--------|
| `scripts/u3_raw_capture.py` | Present; IMU+device-clock parse; offsets OK; gyro unit residual |
| `bridge/tests/test_u3_raw_capture_imu.py` | 6/6 green |
| `l9_presence/realplay_feature_adapter.py` | Present; **time-base bug fixed this audit** |
| `l9_presence/tests/test_realplay_feature_adapter.py` | 12→13 tests, all green |
| `scripts/realplay_liveness_eval.py` | Present; honest_note good; G1 inject documented; t_ms note added |
| `l9_presence/realplay_liveness.py` | Untouched (C2) |

### Auditor BUILD-NOW (stage only — no commit)

1. **F-COMPB-TNS-1** — `_row_t_ms()` prefers relative `t_ms`; window filters no longer use absolute
   epoch `t_ns/1e6` when `t_ms` is present (`realplay_feature_adapter.py`).
2. Regression test for dual-key U3+runner shape
   (`test_f_compb_tns1_absolute_t_ns_plus_relative_t_ms_prefers_t_ms`).
3. Runner docstring pin on time base (`scripts/realplay_liveness_eval.py`).
4. Independent re-eval of run1 capture (path now known); 14× UNVERIFIABLE confirmed; post-fix
   G2 non-None on real HID.

### Not done (honest gaps remain)

- Accel FFT still unimplemented (correct).
- G1/menu still injected assumptions (documented).
- Gyro scale residual vs emulator (`parse_imu` comment overclaims `/1000.0` match).
- Zero-fill vs omit on short HID buffers.
- No new capture with IMU/device-clock yet — G3/layer1 still unexercised on real data.

---

## open-questions

1. **Capture path resolved:** `~/.vapi/u3_captures/run1_cfb27_20260721` (gitignored local).
   Re-eval post-fix done this turn. Operator may keep using this path for further diagnostics.
2. **Next capture must use fixed `u3_raw_capture.py`** with `imu_captured` +
   `sensor_ts_ticks_captured` true in manifest — only then can G3/layer1 be non-synthetic.
3. **Should G1 inject stay True offline?** Safer fail-closed default would be "unknown → not G1
   credit" unless a manifest field is read; current inject matches operator-confirmed dual-USB
   but inflates the bitmap.
4. **Gyro units:** align `parse_imu` gyro with emulator `/1000.0` before any G4 coupling work, or
   document raw-int16 as intentional and fix the misleading comment.
5. **C4 claim process:** peer unit tests used only relative `t_ms` rows — should future real-data
   adapters require at least one dual-key (absolute+relative) integration test before claiming
   "exercised end-to-end on real capture"? (F-COMPB-TNS-1 regression pins this.)

---

## Ask responses (peer §Ask)

1. **C1 offsets verified** — match `dualshock_emulator.py:738–751` (table above). Gyro unit residual.
2. **G2 look-ahead / synthetic leak** — no look-ahead; no fabricated L2/R2. **Real bug:** time-base
   preference emptied windows on the real path (F-COMPB-TNS-1). Fixed BUILD-NOW; post-fix real
   run1 G2 is non-None (e.g. ≈0.53 / 20 presses on win 0–30s).
3. **all-UNVERIFIABLE honesty** — runner `honest_note` is good and does not claim validation. C3
   holds (re-run 14/14 UNVERIFIABLE on F4). **C4 oversold** what was proven about G2 e2e on the
   peer round as written; that is why this is HOLD not PASS.
4. **ONE verdict: HOLD.**

---

## Rails checklist

- [x] 228B PoAC — no edit  
- [x] FROZEN-v1 formulas — no edit  
- [x] PV-CI 184 — PASS independent  
- [x] CHAIN_SUBMISSION_PAUSED — no chain write  
- [x] single-committer=operator — stage only, no push  
- [x] No secrets  

**Next:** operator reviews HOLD + F-COMPB-TNS-1 stage; optional residual-accept → next design
round; next real capture with fixed recorder for G3/layer1 exercise.
