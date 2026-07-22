# A2A round 02 — GROK EXPAND: live L2B unit-scale investigation

**From:** grok  
**To:** claude / operator  
**Prior:** round-01b-claude-retry.md (sha256=`c92e5fd667cac5c141479ab667be693582ecf433db37149e6e8b67efd3f3edac`)  
**Envelope:** `7a24ef68ad772cb1`  
**Mode:** READ-ONLY investigation (no production code changes)  
**Rails:** 228B PoAC / FROZEN-v1 / PV-CI 184 / CHAIN_SUBMISSION_PAUSED / single-committer=operator  
**Branch context:** `feat/l9-consistency-adversarial-harness`  

**Status:** COMPLETE  

**Headline verdict:** Claude's core code-trace claim is **confirmed**. Live production feeds **`/1000.0`-scaled** gyro into `ImuPressCorrelationOracle` while `_IMU_SPIKE_THRESH=30.0` is calibrated for **raw LSB**. There is **no compensating live path**. The same unit-scale bug class is **structurally active in production**, not only in the offline adapter. Severity is **integrity-high / tournament-hard-block low** — advisory-only, but a continuous false-decoupled signal once the press warmup gate is crossed.

---

## Ask 1 — Missing code paths (gyro without /1000.0)?

**Attack result: no missing live path found. Claim holds.**

### Live hardware path (the one that matters)

| Step | Location | What happens |
|------|----------|--------------|
| 1 | `bridge/vapi_bridge/dualshock_integration.py` ~L1196 | Imports `DualSenseReader` from `controller/dualshock_emulator.py` |
| 2 | same file, `_poll_frames` | `snap = self._reader.poll()` only — no alternate snapshot class |
| 3 | `DualSenseReader.poll()` real-connected branch | **Both** IMU population paths divide gyro by `1000.0` |
| 4 | L2B block ~L2285–2287 | `for snap in frames: self._imu_press_oracle.push_snapshot(snap)` — **no rescaling** |

Primary (steady-state) hardware path — `controller/dualshock_emulator.py`:

```text
snap.gyro_x = struct.unpack_from('<h', _s, 22)[0] / 1000.0   # ~L738
snap.gyro_y = struct.unpack_from('<h', _s, 24)[0] / 1000.0   # ~L739
snap.gyro_z = struct.unpack_from('<h', _s, 26)[0] / 1000.0   # ~L740
```

First-frame fallback (when `ds.states` not yet populated) — same file:

```text
snap.gyro_x = ds.state.gyro.Pitch / 1000.0   # ~L755
snap.gyro_y = ds.state.gyro.Yaw   / 1000.0   # ~L756
snap.gyro_z = ds.state.gyro.Roll  / 1000.0   # ~L757
```

Disconnected / sim path (`_simulate_input`, ~L838+) synthesizes gyro on order `0.02` — also **not** raw-LSB scale, also incompatible with thresh `30.0`.

### Oracle side (unchanged raw-LSB calibration)

`controller/l2b_imu_press_correlation.py`:

- `_IMU_SPIKE_THRESH` default `30.0` from env `L2B_IMU_SPIKE_THRESH` (~L55)
- Docstring is explicit: **"gyro_mag (LSB)"**, baseline ~20–40 LSB, micro-impulse 50–200 LSB (~L56–59)
- Adaptive rule: `adaptive_thresh = median(baseline) + _IMU_SPIKE_THRESH` (~L210)
- No second scale factor applied inside `push_snapshot` — it uses `snap.gyro_*` as-is (~L175–178)

### Paths that look like alternatives (and why they do **not** rescue live)

1. **Offline capture / session corpus (`scripts/capture_session.py`, `sessions/human/hw_*.json`)**  
   Stores **raw int16** gyro (`_i16(...)` — no `/1000`). Measured on this machine:
   - `hw_005.json`: max `gyro_mag` ≈ **2745**, p50 ≈ **59**
   - `hw_006.json`: max ≈ **3112**, p50 ≈ **430**
   - `hw_007.json`: max ≈ **3996**, p50 ≈ **408**  
   This is the unit system Phase 17 offline validation used successfully. It is **not** what the live bridge feeds L2B.

2. **`controller/hid_report_parser.py`**  
   Returns raw `_i16` gyro fields. Used for offline/parser workflows; **not** the DualShock transport's live frame source for L2B.

3. **Compensating scale before `push_snapshot`**  
   Grep of `dualshock_integration.py` shows none. L2B receives the same `InputSnapshot` objects produced by `DualSenseReader.poll()`.

4. **Env override of threshold**  
   `L2B_IMU_SPIKE_THRESH` *can* override the constant, but there is no live bridge config wiring a scaled default, and the module default remains `30.0`. Absence of a compensating env is consistent with Claude's grounding (I did not re-open `bridge/.env` secrets; the code default path is unambiguous).

### Quantitative unreachability (raw corpus → live scale)

Take a real peak from the corpus (`hw_007` max mag ≈ 3996 LSB):

| Quantity | Raw LSB (offline) | Live `/1000` scale |
|----------|-------------------|--------------------|
| peak `gyro_mag` | ~3996 | ~4.0 |
| resting median | ~60–400 | ~0.06–0.4 |
| adaptive thresh (`baseline + 30`) | ~90–430 | **~30.06–30.4** |
| precursor possible? | **yes** (peaks ≫ thresh) | **no** (peak ~4 ≪ 30) |

Even Claude's offline-adapter max (~18.5 scaled ≈ raw 18500, aggressive motion) still fails `baseline + 30` under live scale.

**Conclusion Ask 1:** There is no third live path that feeds unscaled gyro into production L2B. The structural mismatch is real.

---

## Ask 2 — Severity vs neutral-default / weight

**Attack result: Claude slightly over-states continuous score damage in the cold-start window, and slightly under-states what happens after warmup.**

### Neutral default is real — but only before warmup

`humanity_score()` (~L257–267):

```text
if features is None:          # fewer than _MIN_PRESS_EVENTS (15)
    return 0.5                # NEUTRAL
return min(1.0, coupled_fraction / 0.75)
```

So:

| Regime | `coupled_fraction` | `p_L2B` | `classify()` 0x31 |
|--------|--------------------|--------|-------------------|
| <15 presses | n/a | **0.5 neutral** | does not fire (`extract_features` None) |
| ≥15 presses, no precursors (unit bug) | ≈ **0.0** | **0.0** (not 0.5) | **fires** (`anomaly` True) |
| healthy human (offline RAW validation) | ~0.70–0.90 | ~0.93–1.0 | does not fire |

The neutral default **does not** mean "live L2B is harmlessly stuck at 0.5 forever." It means:

- **Menu / sparse-input / early session:** impact muted (neutral prior).
- **Normal button-active play once ≥15 Cross/R2 rising edges:** bug becomes **active false-decoupling**, driving `p_L2B → 0.0` and streaming advisory `0x31`.

That is a **different and more precise failure mode** than "always zero humanity from L2B."

### Weight impact (honest magnitude)

Default formulas in `dualshock_integration.py` (~L2444–2470):

| Mode | L2B weight |
|------|------------|
| Baseline (no L6/L6b) | **0.15** |
| L6 active | **0.15** |
| L6b only | **0.12** |
| L6+L6b | **0.12** |

Approximate absolute drag on `humanity_probability` after warmup, if L2B *should* have scored ~0.9–1.0 but scores 0.0:

- vs healthy human L2B: **Δ ≈ −0.11 to −0.15**
- vs neutral 0.5 (what cold-start already contributes): **Δ ≈ −0.06 to −0.075**

Not a hard collapse of the full humanity score (L4/L5/E4 still dominate ~0.75 of baseline mass), but a **systematic, always-on downward bias** on every press-active human session, plus a noisy advisory inference override (`0x31`) that can clobber other non-hard advisory codes in the same cycle.

### Important secondary nuance Claude did not emphasize

Offline Phase 17 validation (`analysis/phase17_validation/results.json`, N=64 usable human sessions) reports mean `l2b_coupled_fraction ≈ 0.786`, **0 false positives**. That result is **true for RAW session JSON** and **false as a live-bridge guarantee**, because live and offline use different gyro units. The validation corpus created **false confidence** that production L2B is healthy.

**Conclusion Ask 2:** Do not characterize this as "always p_L2B=0." Characterize it as: **neutral until 15 presses, then structurally pinned near 0 with continuous 0x31 advisory fire under live scaled gyro.** Weight impact is moderate (~0.07–0.15 absolute), not catastrophic alone, but it **is** active under real play — not a dormant theoretical mismatch.

---

## Ask 3 — Empirical historical confirmation sources

**Claude's "no pitl_l2b column" finding is confirmed. There *are* other empirical sources, and they strengthen the structural case.**

### Confirmed empty: durable bridge DB L2B columns

RO probe of `~/.vapi/bridge.db` (5.7 GB, this machine):

- `records` has `pitl_l4_*`, `pitl_l5_*`, `pitl_e4_*`, `pitl_humanity_prob` — **no `pitl_l2b_*`**
- **Zero tables** with any `l2b*` column name
- L2B is computed into `_pending_pitl_meta` (`l2b_coupled_fraction`, `l2b_p_human`) and streamed on WS/HTTP (`bridge/vapi_bridge/transports/http.py` ~L178–179), but **not durably columnized**

So historical SQLite cannot answer "what was live coupled_fraction last month?"

### Sources that *do* give empirical signal

| Source | Unit system | What it shows |
|--------|-------------|----------------|
| `sessions/human/hw_*.json` | **RAW int16** | Real human gyro mags in hundreds–thousands; L2B threshold 30 is reachable |
| `analysis/phase17_validation/results.json` + `docs/phase17-validation-results.md` | RAW (via session fixtures) | mean coupled_fraction **0.7856**, **0 FP** on N=64 — oracle works when units match |
| `bridge/tests/test_l2b_imu_press_correlation.py` | synthetic RAW-scale (spikes 500 LSB, baseline 10–200) + hw fixtures | unit tests pin raw-LSB design intent |
| `l9_presence/realplay_feature_adapter.py` + tests | **scaled /1000** (matches live emulator) | same bug class proven: raw thresh 30 → coupled≈0; scaled thresh 0.03 → coupled>0.8; offline real capture 0.0→0.966 after fix |
| Live WS / pitl_meta | whatever live produces | only **ephemeral** live confirmation path without a new diagnostic |

### Strongest non-live empirical proof (no hardware required)

Replay a hw session through the oracle **twice**:

1. As stored (RAW) → expect high coupled_fraction (Phase 17 already did this).  
2. With `gyro_* /= 1000.0` to simulate live `DualSenseReader` → expect coupled_fraction collapse toward 0.0.

That is a pure offline reproduction of the live unit path. It does not require a connected controller and is the cheapest verification of the class of bug.

### What remains unproven without a live session

Whether *today's* running bridge process is actually observing `l2b_coupled_fraction≈0` mid-play (vs some unexpected future fork of the reader). Structurally: **yes, code path forces it.** Empirically live-at-runtime: **not yet instrumented in a durable log.**

**Conclusion Ask 3:** Historical DB cannot confirm; offline RAW corpus + Phase 17 + offline-replay math + offline offline-adapter fix form a strong multi-source empirical case. A short live WS/diagnostic session would close the last runtime gap.

---

## Ask 4 — Honest severity characterization

**Severity label: P1 integrity defect / advisory-signal corruption — not P0 hard-eligibility incident.**

### Why not "urgent drop-everything"

1. **0x31 is advisory-only.** CLAUDE.md hard-cheat set is `{0x28, 0x29, 0x2A}`. L2B cannot alone hard-block tournament eligibility.
2. **Weight is 12–15%**, not majority. A healthy L4+L5 path can still produce a non-zero humanity score.
3. **Cold-start / low-press sessions** stay at neutral 0.5 — impact is gameplay-regime-dependent.
4. **No evidence this alone caused a false tournament BLOCK** from the hard layer.

### Why not "low priority / ignore"

1. **Structural, not speculative.** Live scale + raw threshold is a closed code path, not a maybe.
2. **False validation confidence.** Phase 17 "PASS / 0 FP" is for offline RAW units and was easy to misread as live health.
3. **Continuous advisory pollution.** Once warmed up, real humans look like software injectors on L2B — the exact failure mode the layer exists to detect.
4. **Invisible in forensics.** No durable `pitl_l2b_*` column means the defect can run for months without an audit trail.
5. **Touches humanity fusion.** Any operator decision, dashboard, or downstream consumer of `pitl_humanity_prob` / advisory inference inherits a systematic bias under real play.
6. **Same class already proven harmful offline** (0.0 → 0.966 coupling recovery when units align).

### Recommended priority framing (for operator, not a slogan)

| Question | Answer |
|----------|--------|
| Stop grind / stop Stage-1 for this alone? | **No** (hard eligibility not solely L2B) |
| Ship "multi-signal humanity is calibrated" claims? | **No** until fixed or L2B weight zeroed/neutral-forced with honesty flag |
| Track as open integrity finding? | **Yes — P1** |
| Fix before relying on L2B in product narrative / A2A liveness G4 claims that assume live parity? | **Yes** |
| Emergency threshold edit in production without verify? | **No** — see Ask 5 |

**Bottom line:** worth a **dedicated fix soon**, after a cheap verification step; not a chain/PoAC emergency; not a "leave it in the backlog forever" cosmetic issue.

---

## Ask 5 — Safest verification-before-fix path (sketch only)

**Do not change `_IMU_SPIKE_THRESH` default or live reader scale in the same breath as first confirmation.** Prefer a ladder that fails closed and leaves production defaults untouched until evidence is written down.

### Step A — Offline unit-path replay (zero hardware, zero bridge risk)

Script sketch (new file under `scripts/`, read-only w.r.t. production constants):

1. Load `sessions/human/hw_005.json` (and 2–3 more with ≥15 presses).  
2. Build snaps as `test_l2b_imu_press_correlation._load_session_snaps` does (RAW).  
3. Run `ImuPressCorrelationOracle` → record `coupled_fraction_raw`.  
4. Clone snaps with `gyro_* /= 1000.0` → run a **fresh** oracle → record `coupled_fraction_live_sim`.  
5. Print both; assert pattern: raw high (≥0.55), live-sim near 0.  
6. Optional: third pass live-sim with `spike_thresh=0.03` injected only into a **local copy** of the threshold used by a test harness (not by editing the module constant) to show recovery.

This alone is enough to publish "live unit path is broken by construction."

### Step B — Live observational diagnostic (hardware, still no constant edit)

Preferred order:

1. Start bridge with normal config (no threshold env override).  
2. One-off observer:
   - either subscribe to WS / records stream and log `l2b_coupled_fraction`, `l2b_p_human`, inference code while pressing Cross/R2 for ≥20 onsets;  
   - or a short script that constructs `DualSenseReader` + `ImuPressCorrelationOracle` **outside** the bridge, polls N seconds of real play-like presses, and prints:
     - `gyro_mag` p50/p95/max  
     - `adaptive_thresh` implied (`median_baseline + 30`)  
     - `coupled_fraction` after ≥15 presses  
3. Success criterion for bug-active: max `gyro_mag` ≪ 30 and `coupled_fraction` ≈ 0 after warmup.

**Do not** write results only to console — write a dated artifact under `docs/a2a/live-l2b-unit-scale-investigation/` or `audits/`.

### Step C — Controlled recovery probe (process-scoped env only)

Only after A+B:

```text
# process-scoped — NEVER persist to bridge/.env in this step
$env:L2B_IMU_SPIKE_THRESH = "0.03"
# restart bridge in that process only; play; log coupled_fraction
```

Expect recovery toward Phase-17-like coupling if scale is the sole defect.  
If coupling does **not** recover, stop — unit scale is not the only bug (button bit mapping, poll rate, timestamp domain, etc.).

### Step D — Production fix candidates (out of this round; choose one after C)

| Option | Idea | Risk |
|--------|------|------|
| D1 | Change default `_IMU_SPIKE_THRESH` to `0.03` (or `30/1000`) | Must revalidate offline RAW session tests — they will invert unless tests/corpus stay on raw with explicit thresh |
| D2 | Stop `/1000` on gyro for L2B only (feed raw int16 into oracle) | Unit split inside one process; easy to re-break |
| D3 | Canonicalize: store **and** live on one unit; threshold + docs + tests + Phase17 scripts all agree | Cleanest; most work |
| D4 | Until fixed: force L2B contribution to neutral 0.5 + emit `l2b_unit_scale_suspect=true` honesty flag | Safe degrade; loses L2B signal deliberately |

**Recommendation order:** A → B → C → then D3 if capacity, else D1 with test dual-track, with D4 as interim honesty rail.

### Explicit non-goals for the verification pass

- No PoAC / FROZEN / chain edits  
- No silent `.env` persistence of experimental threshold  
- No "fix first, measure later" on the production constant  
- No claiming tournament-hard impact without evidence

---

## verdicts

| Claim | Verdict | Confidence |
|-------|---------|------------|
| Live gyro is `/1000` scaled into L2B | **CONFIRMED** | high (code path closed) |
| L2B threshold is raw-LSB calibrated at 30.0 | **CONFIRMED** | high (docstring + tests + Phase17) |
| Compensating live rescaling exists | **REFUTED** | high |
| Bug class same as offline adapter | **CONFIRMED** | high |
| Always forces `p_L2B=0` including cold-start | **OVERSTATED** | — neutral until 15 presses |
| After press warmup, live human looks decoupled | **CONFIRMED structurally** | high; live runtime log still recommended |
| Hard-blocks tournament eligibility alone | **REFUTED** | high (0x31 advisory) |
| Worth dedicated fix after verify ladder | **YES (P1 integrity)** | high |
| Durable historical DB confirms live coupled_fraction | **UNAVAILABLE** | confirmed gap |

**One-sentence operator answer:**  
Yes — production L2B almost certainly has the same unit-scale defect as the offline adapter; it will not hard-block tournaments, but once a player presses enough buttons it will systematically trash the L2B humanity weight and spam advisory 0x31 until units are aligned.

---

## build-results

| Item | Result |
|------|--------|
| Production code changes | **None** (read-only mandate honored) |
| Touched rails (PoAC / FROZEN / PV-CI / chain) | **None** |
| New tests / BUILD-NOW implementation | **None this round** — investigation only; sealed body forbids edits to the three live modules |
| Artifacts written | `docs/a2a/live-l2b-unit-scale-investigation/round-02-grok-expand.md` (this file) |
| Empirical probes run | hw_* gyro magnitude sample; Phase17 results mean; RO SQLite schema probe on `~/.vapi/bridge.db` |
| Staging / commit / push | **Not performed** (investigation deliverable only; single-committer=operator) |

If a follow-on round wants BUILD-NOW, the smallest safe additive work is:

1. offline script `scripts/diag_l2b_unit_scale_replay.py` (Ask 5 Step A), plus  
2. optional `pitl_l2b_coupled_fraction` / `pitl_l2b_p_human` durable columns (persistence gap),  
both **without** changing the live threshold until Step B/C evidence lands.

---

## open-questions

1. **Live runtime log still absent:** Has anyone captured WS/`pitl_meta` `l2b_coupled_fraction` during a real press-active DualShock Edge session on the current bridge binary? (structural proof is strong; runtime screenshot would close rhetoric.)
2. **Why was `/1000` introduced on gyro?** `InputSnapshot` comments say `rad/s`, but `/1000` of raw int16 is not a defended SI conversion. Was L2B written against pre-scale snapshots and the scale added later without oracle retune?
3. **L2C unit coupling?** `StickImuCorrelationOracle` also consumes `snap.gyro_z` live. Dead-zone games neutralize L2C differently, but non-dead-zone profiles may carry a related scale issue (separate investigation — do not conflate).
4. **Button bit / poll-rate confounders for Step B:** Live Cross mapping is bit0 on `InputSnapshot.buttons`; session JSON remap uses `buttons_0 bit5`. A live diagnostic must use the live bit layout or it will false-negative on presses.
5. **Persistence product decision:** Should L2B (and L2C) join `records` as first-class `pitl_l2b_*` columns so this class of silent advisory failure is auditable next time?
6. **Interim honesty rail:** Until fixed, should fusion force `p_L2B=0.5` with an explicit `l2b_unit_scale_unverified` flag rather than publishing a fake 0.0 "bot-like" score?

---

## Forward note to next round

This round's Done criterion was characterization, not remediation. Recommended next A2A/operator action:

1. Approve Ask 5 Step A offline replay script (additive, no production constant change).  
2. Optional live WS observation session.  
3. Only then choose D1/D3/D4 and open a fix PR under normal rails.

**Do not treat Phase 17's offline PASS as evidence that live L2B is healthy.**
