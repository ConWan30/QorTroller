# VAPI Pre-Grind Validation Report
**Date:** 2026-04-22  
**Phase context:** Phase 235-A/B complete — Grind Integrity Chain + PCC Attestation Slot  
**Purpose:** Validate ten operational categories before Phase 235 (100 consecutive_clean grind) begins

---

## Category 1 — Regression Fix Audit

**Status: VERIFIED, NO ACTION REQUIRED**

The PCC gate added in Phase 235-B caused 14 pre-existing tests to fail because those tests inserted `ruling_validation_log` rows without `pcc_state`/`pcc_host_state` (columns that didn't exist when those tests were written). All 14 were pre-PCC tests whose assertion semantics were preserved — not inverted — by the fix.

### Tests Updated (14 total)

| Test | What it verified | Fix applied |
|------|-----------------|-------------|
| `test_phase75::test_3` | `insert_validation_record` returns a positive row_id and `consecutive_clean >= 1` | Added `pcc_state="NOMINAL", pcc_host_state="EXCLUSIVE_USB"` to the single insert |
| `test_phase75::test_4` | 5 clean records → `consecutive_clean == 5` | Same fix to the 5-row loop |
| `test_phase75::test_5` | 2 clean, 1 divergent, 3 clean → `consecutive_clean == 3` (trailing clean) | `pcc_state/host` stamped on non-divergent rows only; divergent row left NULL (doesn't need it — divergence already breaks streak) |
| `test_phase78::test_3` | 10 clean rulings + rate=0.0 → `gate_passed=True` | Updated `_insert_val()` helper: `pcc_state="NOMINAL" if not divergence` |
| `test_phase88::test_2` | 5 CERTIFY sessions → `consecutive_clean=5, progress_pct=5.0` | Updated `_insert_ruling()` helper |
| `test_phase88::test_5` | Endpoint returns required fields including `consecutive_clean=3` | Same helper fix, propagates to endpoint test |
| `test_phase89::test_2` | 50 clean sessions → `gate_progress=17.5` component score | Updated `_insert_ruling()` helper |
| `test_phase100::test_4` | `progress_pct=50.0` with 50 clean sessions | Updated raw SQL INSERT in `_insert_clean_validation_records()` to include `pcc_state/host` columns |
| `test_phase100::test_5` | `current_blocking_step=4` when gate+cert+audit pass but `dry_run=True` | Same helper fix (uses 100 records) |
| `test_phase100::test_6` | `fully_activated=True` when all conditions met | Same helper fix |
| `test_phase103::test_2` | `seed_validation_records(110)` → `gate_passed=True` | Updated `ActivationSimulator.seed_validation_records()` in `activation_simulation.py` |
| `test_phase103::test_4` | `ActivationRunner.run(110)` → `vhp_minted=True, fully_activated=True` | Same (simulation uses same seed method) |
| `test_phase103::test_6` | `POST /agent/run-activation-simulation` returns 200 with `vhp_minted=True` | Same |
| `test_phase234::T234-8` | `consecutive_clean=3` (trailing non-divergent streak, with one divergent in middle) | Updated `_insert_validation()` closure: `pcc_state="NOMINAL" if not divergence` |

### Semantic Integrity Verification

None of the 14 tests had their assertion semantics inverted. Specifically:
- **None were testing that sessions WITHOUT PCC attestation should count.** All were written before Phase 235-B existed and were simply asserting pre-PCC streak behavior.
- The fix is additive: rows that should count now have PCC attestation; rows that should NOT count (divergent rows) were left unmodified or given NULL pcc_state (which correctly fail-closes).
- `test_phase75::test_5` and `test_phase234::T234-8` both involve mixed divergent/clean sequences. The divergent rows remain NULL pcc_state — this is intentional and correct, since divergence itself already breaks the streak before the PCC check runs.

No separate assertion-preserving test is required.

---

## Category 2 — LLM API Failure Modes

**Status: VERIFIED — 2 tests added (T235-GPC-1, T235-GPC-2)**

### Failure Mode Analysis

`SessionAdjudicator._llm_ruling()` wraps the entire Anthropic API call in `try/except Exception`. All failure modes fall through to `return self._rule_fallback(evidence)`.

| Mode | What happens | fallback_verdict produced? | ruling_validation_log written? | consecutive_clean advances? | GIC computed? | llm_verdict NULL? |
|------|-------------|---------------------------|-------------------------------|----------------------------|---------------|-------------------|
| a. No `ANTHROPIC_API_KEY` | `AsyncAnthropic()` raises `AuthenticationError` → caught → fallback | ✅ | ✅ | ✅ (if PCC healthy + no anomalies) | ✅ | ❌ (stores fallback result, not NULL) |
| b. Invalid API key | Same path — API returns auth error before response → caught → fallback | ✅ | ✅ | ✅ | ✅ | ❌ |
| c. Network unreachable | `ConnectionError` → caught → fallback | ✅ | ✅ | ✅ | ✅ | ❌ |
| d. Rate limit | `RateLimitError` → caught → fallback | ✅ | ✅ | ✅ | ✅ | ❌ |
| e. API error response | `APIError` or `json.JSONDecodeError` on response parse → caught → fallback | ✅ | ✅ | ✅ | ✅ | ❌ |
| f. Timeout (>30s) | `asyncio.TimeoutError` → caught → fallback | ✅ | ✅ | ✅ | ✅ | ❌ |

**Critical observation:** When LLM fails, the fallback verdict is stored in `agent_rulings.verdict`. The validator then independently computes `_rule_fallback(evidence)` and finds `llm_verdict == fallback_verdict` → `divergence=0` → `consecutive_clean` advances. **The GIC is computed by the validator from `fallback_verdict`, which is identical regardless of LLM availability.**

### GIC Chain Behavior Under LLM Failure

The GIC formula hashes `fallback_verdict` (output of `_rule_fallback()` — deterministic pure function). It does NOT hash `llm_verdict`. Therefore:
- LLM API outage during the grind → sessions still count
- Sessions still get GIC hashes
- Chain remains intact
- The GIC_100 artifact's cryptographic validity is independent of Anthropic API availability

### Tests Added

- **T235-GPC-1**: `test_1_llm_unavailable_fallback_executes_deterministically` — Mocks `anthropic.AsyncAnthropic()` to raise `ConnectionError`, confirms `_llm_ruling()` returns the same tuple as `_rule_fallback({})`.
- **T235-GPC-2**: `test_2_llm_fallback_ruling_produces_no_divergence_consecutive_clean_advances` — Inserts a ruling where `verdict="FLAG"` (as if LLM used fallback), validates it, confirms `divergence=0` and `consecutive_clean=1`.

Both tests pass (`4/4` in `test_phase235_grind_precheck.py`).

---

## Category 3 — Real-Hardware PCC State Transition Dry Run

**Status: PROCEDURE DOCUMENTED (hardware required for execution)**

This is a pre-grind mandatory manual test. Execute before the first real grind session.

### Procedure

**Prerequisites:** Bridge installed, `bridge/.env` has `GRIND_SESSION_ID=grind_test_20260422`, `GRIND_MODE=true`, `OPERATOR_API_KEY` set.

1. **Start bridge** with a TEST grind session ID:
   ```
   GRIND_SESSION_ID=grind_test_20260422 python bridge/main.py
   ```
   Confirm startup log shows: `GRIND SESSION ID : grind_test_20260422`

2. **USB-only connect** DualSense Edge. Verify:
   ```
   GET /bridge/capture-health
   ```
   Expected: `capture_state=NOMINAL, host_state=EXCLUSIVE_USB, grind_ready=false, sustained_duration_s < 30`

3. **Wait 30 seconds.** Verify:
   ```
   GET /bridge/capture-health
   ```
   Expected: `grind_ready=true, session_counting_paused=false`

4. **Play one NCAA CFB 26 session** (any duration). After session ends, verify a row exists:
   ```sql
   SELECT pcc_state, pcc_host_state, grind_chain_hash FROM ruling_validation_log ORDER BY id DESC LIMIT 1;
   ```
   Expected: `pcc_state=NOMINAL, pcc_host_state=EXCLUSIVE_USB, grind_chain_hash=<64-char hex>`

5. **Simulate PS5 contestation:** Power on PS5, press controller PS button to pair. While USB still connected, observe:
   ```
   GET /bridge/capture-health
   ```
   Expected: `host_state=CONTESTED, grind_ready=false, session_counting_paused=true`

6. **Play a partial session** during contested state. Verify the validation row has:
   ```sql
   SELECT pcc_state, pcc_host_state, grind_chain_hash FROM ruling_validation_log ORDER BY id DESC LIMIT 1;
   ```
   Expected: `pcc_state=NOMINAL OR DEGRADED, pcc_host_state=CONTESTED, grind_chain_hash=NULL`
   (CONTESTED host state = not PCC-eligible → no GIC stamp)

7. **Unplug USB.** Verify:
   ```
   GET /bridge/capture-health
   ```
   Expected: `capture_state=DISCONNECTED`

8. **Wait 10 seconds, replug USB.** Verify capture recovers to `NOMINAL + EXCLUSIVE_USB`. Wait 30s for `grind_ready=true`.

9. **Query chain status:**
   ```
   GET /bridge/grind-chain-status
   ```
   Expected: `chain_length=1` (only the clean step-4 session), `chain_intact=true`

10. **Teardown:** Delete test rows or use a test DB path:
    ```sql
    DELETE FROM ruling_validation_log WHERE pcc_state IS NOT NULL;
    DELETE FROM capture_health_log;
    ```
    Then restart bridge with the real `GRIND_SESSION_ID` to confirm clean state.

### Expected Observations
- Chain length never includes contested or NULL-pcc sessions
- `session_counting_paused` immediately reflects grind_ready changes
- DISCONNECTED state is logged in `capture_health_log`
- Recovery to grind_ready requires full 30s warmup (not partial credit)

---

## Category 4 — GRIND_SESSION_ID Persistence Across Restarts

**Status: ISSUE FOUND — RESOLVED (startup log added)**

### Finding
The bridge previously logged the GRIND_SESSION_ID only in GIC chain status messages, not prominently at startup. An operator restarting the bridge mid-grind could not verify which session they were continuing without querying the API.

### Resolution
Added prominent startup log block in `bridge/vapi_bridge/main.py`:
```
INFO  ============================================================
INFO  GRIND SESSION ID : grind_phase235_v1
INFO  GRIND MODE       : ACTIVE
WARN  GRIND_SESSION_ID not set in environment — auto-generated ID 'grind_20260422'.
      Set GRIND_SESSION_ID=grind_phase235_v1 in bridge/.env to persist the
      same grind session ID across bridge restarts.
INFO  ============================================================
```
The warning only fires when `grind_mode=True` AND `GRIND_SESSION_ID` env var is not set.

### Persistence Behavior (verified by code analysis)

1. Set `GRIND_SESSION_ID=grind_phase235_v1` in `bridge/.env`
2. Start bridge, write session rows — `grind_chain_hash` stamped with GIC using that ID
3. Stop bridge
4. Restart bridge with same env var → `get_prev_grind_chain_hash()` queries DB for `MAX(gic_ts_ns)` row → correct prev hash returned → chain continues
5. Restart bridge WITHOUT env var → auto-generates `grind_YYYYMMDD` → **different session ID** → `get_prev_grind_chain_hash()` returns `None` → genesis triggered → **chain restarts**

**Operator rule:** Set `GRIND_SESSION_ID` in `bridge/.env` before the first session and never change it. The bridge will chain across restarts as long as the ID matches.

---

## Category 5 — Chain-Break Recovery Procedure

**Status: ISSUE FOUND — RESOLVED (POST /operator/gic-reset implemented)**

### What causes `app._gic_chain_broken=True`

Set by `main.py` startup GIC integrity check when:
- `chain_length > 0` (at least one grind session exists)
- `chain_intact=False` (recomputed hash doesn't match stored hash for at least one row)

Root causes:
1. **Manual DB edits** during bridge operation (fallback_verdict, pcc_host_state, commitment_hash tampered)
2. **Bug in GIC computation** (e.g., formula argument order swapped)
3. **Partial write** — validator crashed mid-way through `update_grind_chain_hash()` leaving partial state

### Investigation Steps

When `app._gic_chain_broken=True`:
```
GET /bridge/grind-chain-status  →  chain_intact=False
```

1. Query the first broken link:
   ```sql
   SELECT id, grind_chain_hash, pcc_host_state, fallback_verdict, gic_ts_ns,
          created_at FROM ruling_validation_log
   WHERE grind_chain_hash IS NOT NULL ORDER BY created_at ASC;
   ```
2. Re-run `grind_chain.py` against the exported rows to find which row first diverges
3. Inspect `capture_health_log` for the affected time range
4. Check git history for any schema migration or formula changes

### Recovery Options

**Option A — Start new grind session (recommended if sessions < 30):**
- Set a new `GRIND_SESSION_ID` in `bridge/.env` (e.g., `grind_phase235_v2`)
- Restart bridge — new genesis, chain_length=0

**Option B — Repair existing chain (for sessions > 50, when tamper was isolated):**
- Fix the tampered row's source values in the DB (restore from backup)
- Call `POST /operator/gic-reset` to clear the flag
- Restart bridge — startup check recomputes and confirms chain_intact=True

### New Endpoint: POST /operator/gic-reset

```
POST /operator/gic-reset?api_key=<OPERATOR_API_KEY>&reason=<10+ chars>
```

- **Auth required:** Returns 503 if OPERATOR_API_KEY not configured; 403 on wrong key
- **reason field required:** Must be ≥ 10 characters (audit trail)
- **Effect:** Sets `app._gic_chain_broken = False`; logs reason as WARNING; writes `gic_chain_reset` agent event
- **Does NOT repair the chain** — only clears the startup flag. The operator must fix the underlying issue separately.

**Tests:** T235-GPC-3 (auth required), T235-GPC-4 (flag cleared + JSON returned) — both pass.

---

## Category 6 — Grind-Mode Auto-Resume Behavior

**Status: VERIFIED, NO ACTION REQUIRED — behavior documented**

### Warmup Timeline

When `grind_mode=True` and capture degrades, then recovers:

| Time | State |
|------|-------|
| t=0 | USB reconnected, `capture_state=NOMINAL, host_state=EXCLUSIVE_USB` |
| t=0 | `grind_ready=False`, `session_counting_paused=True` |
| t=30s | `sustained_duration_s >= pcc_stable_window_s (30)` → `grind_ready=True` |
| t=30s | `session_counting_paused=False` — counting resumes automatically |

The warmup is implemented in `CaptureHealthMonitor._is_grind_ready_locked()`:
```python
return (now - self._nominal_since) >= self._stable_s  # 30s default
```
`_nominal_since` resets whenever the state exits NOMINAL, so a partial recovery (NOMINAL for 20s, then CONTESTED for 1s) resets the 30s clock.

### Indicators

1. **`GET /bridge/capture-health`** — `sustained_duration_s` shows elapsed warmup time; `grind_ready` shows current state; `session_counting_paused` shows whether counting is active
2. **Bridge logs** — `update_sample()` logs state transitions at DEBUG level; `signal_disconnect()` logs DISCONNECTED at WARNING
3. **`GET /bridge/grind-chain-status`** — `chain_length` stays constant during warmup (no sessions counted)

### No Manual Warmup Advance

Warmup is strictly time-based. There is no operator command to skip it. This is intentional: the 30s window ensures the poll-rate CV stabilizer has processed enough samples to confidently classify `EXCLUSIVE_USB`. Forcing it early risks a CONTESTED misclassification.

### Dashboard Visibility

The capture health endpoint fields are surfaced in the frontend dashboard under the Capture Continuity section. The operator can monitor `sustained_duration_s` counting up toward 30s in real time.

---

## Category 7 — Timestamp Monotonicity

**Status: ISSUE FOUND — RESOLVED (monotonicity guard + precision fix)**

### Finding

The GIC timestamp was computed as `int(time.time() * 1e9)` which has two issues:
1. **Floating-point precision loss:** `time.time()` is a float64; converting to nanoseconds via multiplication loses the last ~3 digits of precision compared to the OS-native integer syscall
2. **NTP backward corrections:** If the system clock steps backward (NTP correction, manual adjustment), a new session's `ts_ns` could be ≤ the previous row's `ts_ns`, creating audit confusion

### Resolution

Two changes to `bridge/vapi_bridge/session_adjudicator_validator.py`:

1. **Precision fix:** `int(time.time() * 1e9)` → `time.time_ns()` (Python's OS-native nanosecond integer, no float conversion)

2. **Monotonicity guard:** Before stamping, query the previous maximum `gic_ts_ns` from the DB:
   ```python
   _ts_ns = time.time_ns()
   _prev_ts = self._store.get_prev_gic_ts_ns()
   if _ts_ns <= _prev_ts:
       _ts_ns = _prev_ts + 1
   ```
   New store method `get_prev_gic_ts_ns()` returns `MAX(gic_ts_ns)` across all GIC-stamped rows (0 if none).

### Design Decision

`time.monotonic_ns()` was rejected because it resets on process restart, making it unsuitable for a multi-day grind where the bridge may be restarted between sessions. `time.time_ns()` preserves wall-clock semantics while the monotonicity guard handles backward corrections.

**GIC formula is unchanged.** The byte representation of `ts_ns` in the hash (`struct.pack(">Q", ts_ns)`) remains identical — only the source of the integer changes (more precise + monotonically guaranteed).

**Updated invariant:** `gic_ts_ns` values in `ruling_validation_log` are strictly monotonically increasing within a grind session. A row's `gic_ts_ns` is ≥ the previous row's `gic_ts_ns + 1` nanosecond.

---

## Category 8 — Resource Footprint During Sustained Operation

**Status: PROCEDURE DOCUMENTED (8-hour soak test to run before grind)**

### Soak Test Procedure

Run the bridge for 8 hours with no controller connected (agent fleet operates, no HID input):

```bash
# Start bridge with grind_mode=False (no actual grind state changes)
python bridge/main.py &
BRIDGE_PID=$!

# Monitor memory every 30 minutes
while sleep 1800; do
    echo "$(date): $(ps -p $BRIDGE_PID -o rss=)kB RSS"
    curl -s "http://localhost:8080/agent/protocol-coherence-status?api_key=$OPERATOR_API_KEY" \
         | python -c "import sys,json; d=json.load(sys.stdin); print('anchors:', d.get('total_anchors',0))"
done
```

### What to Measure

| Metric | Concern | Green threshold | Red threshold |
|--------|---------|----------------|---------------|
| RSS memory | Unbounded agent state, ring buffers | < 200MB after 8h | > 400MB or linear growth |
| `agent_rulings` table size | Polling every 5 min × 38 agents | < 10k rows / 8h | Unbounded growth (missing cleanup) |
| HTTP API p95 response time | Event loop stalls | < 100ms | > 500ms |
| Log file size | Verbose debug logging | < 500MB / 8h | Unbounded (missing rotation) |
| SQLite WAL file size | Transaction batching | < 50MB | > 200MB (checkpoint not running) |

### Known Bounded Items

- `_fft_ring`, `_accel_mag_ring` in `BiometricFeatureExtractor`: fixed `maxlen=1024` deques
- `_pcc_history` in `CaptureHealthMonitor`: fixed `maxlen=60` ring buffer
- `_limiter` in operator_api: fixed sliding window (last 60 seconds)
- `frame_checkpoints`: bounded by `maxlen=60` in `_replay_ring`

### Action Required Before Grind

Run the 8-hour soak immediately before starting the grind. If any metric shows unbounded growth, identify the source and implement cleanup/rotation before starting. The grind may take multiple days — any memory leak that appears small in 8 hours becomes significant over 48 hours.

---

## Category 9 — L4 Staleness During Adjudication

**Status: VERIFIED, NO ACTION REQUIRED**

### Finding

The L4 Mahalanobis distance is computed in `dualshock_integration.py` against a 12-feature calibration baseline (thresholds: `anomaly=7.009`, `continuity=5.367`). The live feature space has 13 features (index 12 = `touchpad_spatial_entropy`, added in Phase 121).

**Phase 215 confirmed:** `touchpad_spatial_entropy` is structurally zero in all gameplay sessions (touchpad is not actively used during NCAA CFB 26 gameplay). A zero feature adds zero variance and does not shift the Mahalanobis distance. The 12-feature thresholds remain valid for 13-feature live sessions.

**Conclusion:** The L4 staleness (calib_dim=12, live_dim=13) does NOT produce false `0x30 BIOMETRIC_ANOMALY` codes during normal play.

### Advisory Code Impact on Grind (if 0x30 fires at all)

If 0x30 fires for any reason during the grind:
1. Evidence dict gains `advisory_codes: [0x30]`
2. `_rule_fallback(evidence)` returns `FLAG(0.5)` (advisory branch)
3. LLM also sees the advisory and returns `FLAG` (most likely outcome)
4. `llm_verdict == fallback_verdict == FLAG` → `divergence=0` → **streak continues**

The only divergence scenario for 0x30: LLM returns a different verdict (e.g., `CERTIFY` for an enrolled player while the advisory fires). This is possible for enrolled players. The safest approach: **don't start the grind as an enrolled player**. The grind sessions should use a non-enrolled device (enrollment requires 10 NOMINAL sessions separately tracked).

---

## Category 10 — Genesis Hash Timing

**Status: PROCEDURE DOCUMENTED**

The genesis GIC hash is permanent. Its `ts_ns` becomes part of the Phase 236 Zenodo deposit audit trail. It must reflect a deliberate, ready-to-grind moment.

### Pre-Grind Checklist (run in order)

**Day of grind — bridge startup sequence:**

```
[ ] 1. Set bridge/.env:
        GRIND_SESSION_ID=grind_phase235_v1
        GRIND_MODE=true
        OPERATOR_API_KEY=<key>
        (all other env vars as normal)

[ ] 2. Unpair controller from PS5:
        PS5 Settings → Accessories → Bluetooth Accessories → [controller] → Delete

[ ] 3. Connect DualSense Edge USB-C to PC only. No other USB hubs between.

[ ] 4. Start bridge:
        cd bridge && python main.py
        Verify startup log shows:
          GRIND SESSION ID : grind_phase235_v1
          GRIND MODE       : ACTIVE

[ ] 5. Verify initial chain state:
        GET /bridge/grind-chain-status
        Expected: chain_length=0, chain_intact=true

[ ] 6. Verify PCC state:
        GET /bridge/capture-health
        Expected: capture_state=NOMINAL, host_state=EXCLUSIVE_USB

[ ] 7. Wait for 30s warmup:
        GET /bridge/capture-health
        Expected: grind_ready=true, session_counting_paused=false
        Observe: sustained_duration_s >= 30

[ ] 8. Verify all 38 agents initialized (no startup errors in bridge log)

[ ] 9. Verify InsightSynthesizer Mode 6 initialization complete (log: "Mode 6" no errors)

[ ] 10. Run tournament preflight:
         POST /agent/run-tournament-preflight
         Expected: overall_pass=true (11/11 P0 conditions)

[ ] 11. Record pre-grind state:
         GET /bridge/grind-chain-status  →  note chain_length=0
         GET /bridge/capture-health  →  note timestamp
         These timestamps define the grind start boundary for the Zenodo deposit.

[ ] 12. Start NCAA CFB 26. Play the first session.

[ ] 13. After first session ends, verify genesis was written:
         GET /bridge/grind-chain-status
         Expected: chain_length=1, chain_intact=true
         Note: genesis_ts (this is the permanent genesis timestamp)
```

### Genesis Timing Notes

- The genesis `ts_ns` is set when the FIRST grind-eligible session is validated (not when the bridge starts)
- A "grind-eligible" session: `grind_mode=True AND pcc_state=NOMINAL AND pcc_host_state in (EXCLUSIVE_USB, UNKNOWN) AND divergence=0`
- If the first gameplay session produces a divergence (LLM disagrees with fallback), no genesis is written — the chain stays at `chain_length=0` and the next clean session becomes genesis
- This is correct behavior: genesis represents the first cryptographically clean moment

---

## Summary

| Category | Status | Evidence |
|----------|--------|----------|
| 1. Regression Fix Audit | VERIFIED | 14 tests updated; none inverted; all 2462+ pass |
| 2. LLM API Failure Modes | VERIFIED + 2 tests | T235-GPC-1/2 pass; LLM failure doesn't break chain |
| 3. Real-Hardware PCC Dry Run | PROCEDURE DOCUMENTED | See §Cat-3 |
| 4. GRIND_SESSION_ID Persistence | ISSUE FOUND → RESOLVED | Startup log added to main.py |
| 5. Chain-Break Recovery | ISSUE FOUND → RESOLVED | POST /operator/gic-reset implemented; T235-GPC-3/4 pass |
| 6. Auto-Resume Behavior | VERIFIED | 30s warmup, GET /bridge/capture-health indicator |
| 7. Timestamp Monotonicity | ISSUE FOUND → RESOLVED | `time.time_ns()` + guard; `get_prev_gic_ts_ns()` added |
| 8. Resource Footprint | PROCEDURE DOCUMENTED | 8-hour soak required before grind |
| 9. L4 Staleness | VERIFIED | calib_dim=12 vs live_dim=13 safe; 0x30 advisory doesn't break streak |
| 10. Genesis Hash Timing | PROCEDURE DOCUMENTED | 12-step pre-grind checklist |

**Net new tests:** 4 (T235-GPC-1/2/3/4) in `test_phase235_grind_precheck.py`  
**Bridge count:** 2430 + 4 = 2434 (delta-based)  
**Files changed:** `store.py`, `session_adjudicator_validator.py`, `main.py`, `operator_api.py`, `activation_simulation.py`, plus 7 test files (regression fixes)
