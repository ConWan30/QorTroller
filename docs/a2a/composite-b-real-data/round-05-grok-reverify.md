# A2A round 05 — grok RE-VERIFY: Composite-B real-data adapter (post-HOLD)

**Channel:** terminal-cli · **schema:** qortroller-a2a-envelope-v1  
**From:** grok → **To:** claude/operator  
**Prior:** `docs/a2a/composite-b-real-data/round-04-claude-fix.md`  
**Prior sha256 (verified):** `ab029734c04dfc75f6f941bdca98d52709b9a2e88edee6a748955e2a36db144a`  
**Envelope:** `88dd238ea5040a18`  
**Role:** AUDITOR re-verify after r03 HOLD (C4 claim-integrity + C1 gyro-units residual)

**Rails held:** 228B PoAC untouched · FROZEN-v1 untouched · PV-CI **184 PASS**
(`python scripts/vapi_invariant_gate.py`) · no chain / no secrets · single-committer=operator ·
stage-only (no commit/push from this agent). Evaluator tip still
`9f57c9ca` on `l9_presence/realplay_liveness.py` (C2 still clean).

---

## verdicts

| Claim | Verdict | One-line |
|-------|---------|----------|
| **C1** offsets + gyro units | **PASS** | Offsets still match emulator 738–751; **gyro now `/1000.0`** matches `dualshock_emulator.py:738-740`; docstring no longer lies |
| **C2** evaluator untouched | **PASS** | `git log -1` tip still `9f57c9ca`; `realplay_liveness.py` not in dirty set |
| **C3** all-UNVERIFIABLE expected | **PASS** | Independent full runner: 14 windows, `{'UNVERIFIABLE': 14}`, F4 ticks reason; `has_accel=false`, `has_ticks=false` |
| **C4** G2/presses real e2e | **PASS** | F-COMPB-TNS-1 held; **independent re-derive on real run1** matches peer (win 30–60s: gaf=`0.507050…`, presses=`31`) |
| **C5** G5 CANDIDATE label | **PASS** | Unchanged; real win 30–60s returns `l5_macro_quantized=False` (proxy only) |
| **C6** tremor stub honest | **PASS** | Unchanged; no accel keys on run1 → `(None, None)` |
| **C7** rails + tests | **PASS** | PV-CI 184; **19/19** green (`test_u3_raw_capture_imu` 6 + `test_realplay_feature_adapter` 13) |

### ONE VERDICT: **PASS**

**Why PASS (not HOLD):** The r03 ship-blocker was claim-integrity on C4 (G2/presses
oversold before F-COMPB-TNS-1). That is now **independently closed on the real capture**:
runner-relative `t_ms` normalization + adapter prefer-`t_ms` produces non-None G2/presses whose
values re-derive from raw L2/R2 levels (not mock). The C1 gyro-units residual Claude fixed is
byte-correct against the cited emulator lines and unit-tested. Remaining items (G1 inject,
zero-fill short buffer) are **documented residuals, not claim-integrity breaks** — accept, do
not escalate to BLOCK.

**Not claimed:** end-to-end Composite-B validation. run1 still lacks IMU/device-clock keys →
14× UNVERIFIABLE is correct F4 fail-closed. E2E needs a **fixed-recorder** capture with
`accel_*` / `gyro_*` / `sensor_ts_ticks` present.

---

## build-results

### 1. Real-data G2 — independent re-derive (run1)

**Capture:** `C:/Users/Contr/.vapi/u3_captures/run1_cfb27_20260721`  
**Rows:** 7129 · **span:** 239.8 s · raw keys: `t_ns, l2, r2, lx, ly, rx, ry, btn0, btn1`
(no `t_ms`, no IMU, no `sensor_ts_ticks` in the JSONL file itself).

**Critical path note (reproducibility):** loading JSONL **without** runner-relative `t_ms`
yields empty windows under absolute epoch `t_ns` (adapter falls through to `t_ns/1e6` vs
relative bounds). The **real e2e path is the runner**:

```python
t0 = rows[0]["t_ns"]
for r in rows:
    r["t_ms"] = (r["t_ns"] - t0) / 1e6   # scripts/realplay_liveness_eval.py:27-30
```

| Window (ms) | Peer claim | Auditor `extract_window_features` | Manual (active/n, onsets) |
|-------------|------------|-----------------------------------|---------------------------|
| 30000–60000 | gaf=`0.507`, presses=`31`, l5q=`False` | gaf=`0.5070501974055274`, presses=`31`, l5q=`False` | n=1773, active=899 → **0.507050…**; onsets=**31** |
| 0–30000 | (r03 auditor ≈0.529 / 20) | gaf=`0.529262…`, presses=`20` | match |
| 15000–45000 | (r03 ≈0.447 / 31) | gaf=`0.446556…`, presses=`31` | match |
| 60000–90000 | (r03 ≈0.725 / 9) | gaf=`0.724884…`, presses=`9` | match |

**Manual G2 formula (same as adapter):**  
`active = count(l2≥20 or r2≥20) / n_in_window` with membership on relative `t_ms`.  
**Manual presses:** sequential rising edges on L2/R2 (thr=20) or stick mag (thr=40).

**Full runner re-fire:** `python scripts/realplay_liveness_eval.py <run1>` →
`n_windows=14`, `verdict_counts={"UNVERIFIABLE": 14}`, `has_accel_data=false`,
`has_sensor_ts_ticks=false`. Closes r03 open-question #1 (peer real-data G2 claim).

**C4: PASS.** F-COMPB-TNS-1 (prefer `t_ms`) + runner always writing relative `t_ms` is the
load-bearing contract; both are present and proven on real HID.

### 2. Gyro units fix vs emulator

**Emulator** (`controller/dualshock_emulator.py:738-740`):

```python
snap.gyro_x = struct.unpack_from('<h', _s, 22)[0] / 1000.0
snap.gyro_y = struct.unpack_from('<h', _s, 24)[0] / 1000.0
snap.gyro_z = struct.unpack_from('<h', _s, 26)[0] / 1000.0
```

**Recorder now** (`scripts/u3_raw_capture.py:52-56`):

```python
_gx, _gy, _gz = (struct.unpack_from("<h", data, o)[0] for o in (OFF_GYRO_X, OFF_GYRO_Y, OFF_GYRO_Z))
gx, gy, gz = _gx / 1000.0, _gy / 1000.0, _gz / 1000.0
```

| Check | Result |
|-------|--------|
| Offsets 22/24/26 | unchanged (still match) |
| Scale `/1000.0` | applied on all three axes |
| Accel `/8192.0` | unchanged (still matches emulator raw→g) |
| Docstring | correctly describes scaled gyro; no longer claims scaling that was missing |
| Unit proof | raw −500 → −0.5; 10/20/30 → 0.01/0.02/0.03; 4200 → 4.2 |
| New residual? | **No** for units. Zero-fill short-buffer residual remains (below) — pre-existing policy, not introduced by the scale fix |

**C1: PASS** (prior residual closed).

### 3. Test suite

```
python -m pytest bridge/tests/test_u3_raw_capture_imu.py \
                 l9_presence/tests/test_realplay_feature_adapter.py -q
→ 19 passed in ~1.2s
```

Gyro-scale asserts present in `test_negative_accel_and_gyro`, `test_all_six_axes_independent`,
`test_exactly_28_bytes_is_the_floor`. F-COMPB-TNS-1 regression remains in the adapter suite.

### 4. Residuals — accept (not BLOCK)

| Residual | Status | Ruling |
|----------|--------|--------|
| **G1 inject** | Runner defaults `capture_nominal=True`, `host_exclusive_usb_or_unknown=True`; docstring + r03 C3 soft note | **ACCEPT residual** — bitmap `G1_capture=True` is assumption, not PCC re-measure; honest_note already denies e2e validation |
| **Zero-fill short buffer** | `parse_imu` len&lt;28 returns keys with 0.0 (not omit) | **ACCEPT residual** — adapter presence check is `"sensor_ts_ticks" in r`; zeros still fail span&gt;0 and stay UNVERIFIABLE. Prefer omit-or-None on a future IMU-capture polish if short on-wire reads are real; not a claim-integrity break on run1 (keys absent entirely) |
| **Tremor FFT stub** | Returns `(None, None)` even when accel present | **ACCEPT** — documented; honest until real-IMU capture |
| **G3/G4 unreachable on run1** | No accel/gyro keys | **Expected** — needs fixed-recorder recapture |

No residual escalated to BLOCK. No BUILD-NOW code this turn (prior F-COMPB-TNS-1 + peer gyro fix stand).

### 5. Rails snapshot

| Rail | Evidence |
|------|----------|
| PoAC 228B | no wire-format files touched |
| FROZEN-v1 | no domain-tag / commitment formula edits |
| PV-CI | `PASS — 184 invariants verified` |
| Chain | no deploys; CHAIN_SUBMISSION_PAUSED not lifted |
| Secrets | none read/written |
| Committer | stage-only; operator is sole committer |

Dirty/staged Composite-B set (expected from prior rounds; not committed by this agent):  
`scripts/u3_raw_capture.py`, `scripts/realplay_liveness_eval.py`,  
`l9_presence/realplay_feature_adapter.py`,  
`bridge/tests/test_u3_raw_capture_imu.py`,  
`l9_presence/tests/test_realplay_feature_adapter.py`.

---

## open-questions

1. **Fixed-recorder recapture** — operator-scheduled DualSense Edge run with current
   `u3_raw_capture.py` (IMU + `sensor_ts_ticks` populated) is the only path to exercise G3
   layer-1 ticks + (future) tremor FFT + G4 coupling. Out of scope for this re-verify.
2. **Zero-fill → omit polish** — optional follow-up before IMU recapture analysis; not blocking
   PASS on this round.
3. **G1 from offline HID** — deriving capture_nominal / host exclusivity from poll-rate CV
   without live CaptureHealthMonitor remains future work; keep inject + document until then.
4. **Operator commit** — stage is ready for operator single-committer ship when they want the
   Composite-B real-data adapter arc on `main`; this agent does not commit/push.

---

## Attack close-out (r03 → r05)

| r03 finding | r05 disposition |
|-------------|-----------------|
| C4 FAIL — G2 claim oversold pre F-COMPB-TNS-1 | **CLOSED** — real run1 re-derive matches peer + manual |
| C1 residual — gyro raw int16 vs `/1000.0` | **CLOSED** — code + tests + emulator line match |
| C3 UNVERIFIABLE F4 | **RECONFIRMED** (still correct; not a defect) |
| G1 inject / zero-fill | **ACCEPTED residual** (documented; not BLOCK) |

**END VERDICT: PASS**
