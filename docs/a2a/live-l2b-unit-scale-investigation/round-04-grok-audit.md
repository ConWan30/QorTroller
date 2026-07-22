# A2A round 04 — GROK AUDIT: Step C controlled recovery probe (scope)

**Role:** grok (adversarial auditor)  
**Prior:** `docs/a2a/live-l2b-unit-scale-investigation/round-03-claude-open.md`  
**Body integrity of prior:** sha256 `edc297f66eaa8aa468ea3f1531ce656bd1a66a3d4091b510a47cb3ac0cc7491f` — **MATCH** (envelope `ca53b55559a872f0`)  
**Prior expand:** `round-02-grok-expand.md` · Steps A/B results on disk  
**Mode:** SCOPING only — no code, no bridge start, no `.env` edit, no production fix  
**Rails:** 228B PoAC · FROZEN-v1 · PV-CI 184 · `CHAIN_SUBMISSION_PAUSED` · single-committer=operator  
**Bus:** claimed via `deliver --handoff` / `claim --for grok` (Claude-safe path)

---

## verdicts

| ID | Verdict | One-line |
|----|---------|----------|
| **C1** Process-scoped env override is safe / import-time thresh | **PASS** (with named mods) | `load_dotenv` default does not clobber OS env; L2B thr is module-level at first import; **no agent path rewrites `L2B_IMU_SPIKE_THRESH` or `bridge/.env`**. |
| **C2** Zero-code `/ws/records` observation | **PASS** (with named mods) | Fields present unauthenticated; **port is 8080 not 8000 on this machine**; client needs **60s keep-alive pings**. |
| **C3** Procedure | **APPROVE WITH MODIFICATIONS** | Safe if preflight flags + port + no-watchdog + ≥20 presses after non-null. |
| **C4** Risk / flag posture | **PASS** after live `.env` check this audit | `GRIND_MODE=false`, `CHAIN_SUBMISSION_PAUSED=true`, L6B/campaign off; note `IOSWARM_ENABLED=true` (emulator) + `STAGED_GRADUATION_ENABLED=true` (API-gated). |
| **Overall Step C** | **(b) approve with named modifications** | Ready for **operator-fired** live run only after preflight checklist below. Does **not** authorize execution itself. |

---

## build-results

| Check | Result |
|-------|--------|
| Prior body sha256 | **MATCH** |
| `config.py` load_dotenv | `load_dotenv(_env_path)` — **no `override=True`** → OS env wins |
| L2B thr read site | `controller/l2b_imu_press_correlation.py` L55 — **import-time** `getenv` |
| Grep write to `.env` / L2B persist | **none** in bridge Python |
| Calib agent / min() path | L4-only (no L2B thr rewrite found) |
| `/ws/records` | `ws.accept()` unauth; streams `l2b_coupled_fraction` / `l2b_p_human` (http.py L178–179, L238–253) |
| Live `bridge/.env` safety keys (values only, no secrets) | see §Ask 3 |
| Code / bridge start this round | **NONE** |
| Artifact | this file |

---

## 1. Attack C1–C4

### C1 — PASS (named caveats)

**What holds**

1. **dotenv does not clobber a pre-set OS env** when `override` is omitted (python-dotenv default `override=False`). `bridge/vapi_bridge/config.py` L17–23:

   ```text
   load_dotenv(_env_path, encoding="utf-8")   # no override=True
   ```

2. **L2B threshold is frozen at first import** of `l2b_imu_press_correlation`:

   ```text
   _IMU_SPIKE_THRESH = float(os.getenv("L2B_IMU_SPIKE_THRESH", "30.0"))  # L55
   ```

   Live oracle is constructed later (`dualshock_integration.py` ~L1454–1455) **after** config import, still in the same process. Setting the var in the **launching shell before** `python -m bridge.vapi_bridge.main` is the correct order.

3. **No bridge code path writes `L2B_IMU_SPIKE_THRESH` or mutates `bridge/.env`** for this key (repo grep). CalibrationIntelligenceAgent `min()` discipline is **L4 per-player thresholds**, not L2B spike thresh — C1’s separation claim holds.

4. **Current `bridge/.env` does not set `L2B_IMU_SPIKE_THRESH`** → code default 30.0 unless the shell overrides. Process-scoped `0.03` will not fight a file value.

**Caveats (do not ignore)**

| Caveat | Why it matters |
|--------|----------------|
| **Import-time freeze** | Changing the env *after* the module is imported does nothing. Mid-session “re-export” is useless — must restart the process. |
| **Watchdog restart** | `scripts/bridge_watchdog.py` spawns via `Popen` inheriting **parent** env. A watchdog **without** `L2B_IMU_SPIKE_THRESH=0.03` that restarts a Step C bridge will silently return to thr=30. **Do not run Step C under an unscoped watchdog.** Manual `python -m bridge.vapi_bridge.main` only. |
| **Second shell** | Observation terminal must **not** start a second bridge. Env override is only on the bridge process. |

**No leak into later sessions** if the override is only process-scoped and never written to disk. Confirmed no L2B auto-persistence agent path.

---

### C2 — PASS (named mods)

**What holds**

- `_record_to_ws_msg` already emits `l2b_coupled_fraction` and `l2b_p_human` (http.py L178–179).
- `/ws/records` accepts with **no API key** (L238–241). Subscribe-only clients are added to `_ws_clients` and receive broadcasts; disconnect removes them. No auth, no DB write from the WS handler itself.
- Dualshock path populates those fields in `pitl_meta` (~L2533–2534) when the oracle has features.

**Attacks / corrections**

| Issue | Severity | Fix for procedure |
|-------|----------|-------------------|
| **Wrong default port** | **HIGH (procedure bug)** | This machine’s `HTTP_PORT=8080` (from `bridge/.env`), **not** 8000. WS URL must be `ws://127.0.0.1:8080/ws/records` unless preflight shows otherwise. |
| **60s receive timeout** | MEDIUM | Handler waits for client text; silent client is **closed after 60s** (L247–249). Observer **must send keep-alive pings** (any text) at &lt;60s interval or logging will stop mid-session. |
| **Null until ≥15 presses** | INFO | `extract_features()` / coupled_fraction are None until `_MIN_PRESS_EVENTS=15`. Early WS rows with `null` are expected — not a failed recovery. |
| **No dedicated REST status for L2B** | INFO | No operator endpoint surfaces live L2B fraction (grep empty). `/ws/records` is the correct zero-edit tap. Optional: log lines at INFO when oracle classifies — not required if WS works. |
| **Unauth WS is a standing surface** | INFO (pre-existing) | Fine for localhost diagnostic; do not treat as a new hole opened by Step C. |

**Side effects of connecting:** register in `_ws_clients` only; broadcast fan-out cost is tiny. Does not start HID, agents, or chain. **Does not** trip operator rate limits (those are HTTP). Safe as read-only observation.

---

### C3 — APPROVE WITH MODIFICATIONS

Base procedure is sound. **Required modifications before operator run:**

1. **Preflight checklist (operator, ~2 min)** — print-only, no secrets:
   - `GRIND_MODE` is false / unset-as-false  
   - `CHAIN_SUBMISSION_PAUSED=true`  
   - `L6B_ENABLED` / `L6_CHALLENGES_ENABLED` / `POEP_CAMPAIGN_MODE` / `POEP_LIVE_FIRE_ENABLED` not true  
   - Note `HTTP_PORT` (this box: **8080**)  
   - Note `IOSWARM_ENABLED` (this box: **true** — emulator OK if chain paused)  
   - Confirm **no** `bridge_watchdog` will own restarts  
   - Confirm **no** second process holds the Edge HID (bridge exclusive)

2. **Bridge start (terminal 1 only):**
   ```powershell
   $env:L2B_IMU_SPIKE_THRESH = "0.03"
   # optional belt: explicit pause even if .env already true
   $env:CHAIN_SUBMISSION_PAUSED = "true"
   $env:GRIND_MODE = "false"
   python -m bridge.vapi_bridge.main
   ```
   Confirm startup log: Layer 2B oracle initialised; port matches preflight.

3. **Observer (terminal 2):** subscribe to **`ws://127.0.0.1:{HTTP_PORT}/ws/records`**, ping every ~20–30s, log timestamped non-null `l2b_coupled_fraction` / `l2b_p_human` / `inference_name`.

4. **Stimulus:** USB Edge, human Cross/R2, **≥20–25 rising edges after** the first non-null fraction (warmup to 15, then 5–10 more for a stable reading). Desk presses OK (Step B style); game not required.

5. **Stop:** Ctrl-C bridge process; leave the shell or `Remove-Item Env:L2B_IMU_SPIKE_THRESH` so a later manual start does not inherit thr by accident in that shell.

6. **Compare** to Step B baseline (`coupled_fraction=0.0`, thr=30, 25 presses).

---

### C4 — PASS after this audit’s `.env` read

Claude correctly refused to assume flag posture. This audit read **names+values of non-secret safety flags only**:

| Key | Live value (this machine) | Step C implication |
|-----|---------------------------|--------------------|
| `GRIND_MODE` | **false** | Good — no grind counting |
| `CHAIN_SUBMISSION_PAUSED` | **true** | Good — no chain spend |
| `L6B_ENABLED` | **false** | Good — no auto L6b fire |
| `L6_CHALLENGES_ENABLED` | not set (false default) | Good |
| `POEP_CAMPAIGN_MODE` | not set | Good |
| `POEP_LIVE_FIRE_ENABLED` | not set | Good |
| `GSR_ENABLED` | false | Good |
| `IOSWARM_ENABLED` | **true** | Emulator paths may log; **not** a spend path if chain paused — accept, do not “fix” by editing `.env` |
| `STAGED_GRADUATION_ENABLED` | **true** | Only matters if someone POSTs graduation activate — **do not call that API** during Step C |
| `HTTP_PORT` | **8080** | WS URL must use this |
| `L2B_IMU_SPIKE_THRESH` | not set | Process override will apply cleanly |

**Residual risks of “full bridge” (honest, non-blocking if checklist held):**

- SQLite writes to `~/.vapi/bridge.db` (records, agent tables) — expected, short session  
- Background agents/poll loops may run — fail-open, no chain with pause held  
- Frontend if open will also connect WS — harmless noise  

Not a grind, not a ceremony, not a deploy.

---

## 2. Answers to Asks 1–5

### Ask 1 — Can anything override/persist thr=0.03?

**No silent override into `bridge/.env` found.** Paths checked:

- dotenv load: non-override  
- L2B module: import-time only  
- Calibration / threshold agents: L4 min() only  
- No `set_key` / `.env` writers for L2B  

**Can be lost mid-session only via process restart without the env** (watchdog, second start). Named modification: no watchdog; one process; env set before launch.

### Ask 2 — Is `/ws/records` safe? Better tap?

**Safe for localhost short diagnostic** if keep-alive pings are sent. Connecting does not mutate protocol flags or chain state.

**Simpler alternatives?** No zero-edit REST for L2B. Operator endpoints require API key and don’t surface live L2B fraction. Stick with WS; correct the port.

### Ask 3 — What to check/neutralize before start?

**Must verify (this box already good except notes):**

| Action | Process-scoped preferred? |
|--------|---------------------------|
| Confirm `CHAIN_SUBMISSION_PAUSED=true` | Yes — re-export in launch shell for belt |
| Confirm `GRIND_MODE=false` | Yes |
| Confirm L6B / campaign / live-fire off | Yes (already off) |
| **Do not** flip `IOSWARM_ENABLED` in `.env` for this probe | Leave file alone; chain pause is the spend gate |
| **Do not** call graduation / mint / commit-activation APIs | Operator discipline |
| No watchdog | Procedural |
| HTTP port noted | Procedural |

Do **not** edit `bridge/.env` on disk for Step C — that would violate the investigation’s “process-scoped only” discipline and risk persistence.

### Ask 4 — Success / failure numeric bar

Use **dual gates** (bridge integration can be slightly noisier than offline Step A = 1.0 recovery):

| Outcome | Criteria (after ≥20 press events total, ≥5 samples with non-null fraction) |
|---------|-----------------------------------------------------------------------------|
| **RECOVERY CONFIRMED** | Latest (or median of last 5 non-null) `l2b_coupled_fraction` **≥ 0.55** (clears live `_COUPLED_FRACTION` / anomaly floor) **and** `l2b_p_human` **> 0.5** **and** no sustained stream of `IMU_BUTTON_DECOUPLED` / 0x31 after warmup |
| **PARTIAL / inconclusive** | 0.15 ≤ fraction &lt; 0.55 — scale is directionally right but not sole/full fix; capture logs, do **not** ship D1 yet |
| **RECOVERY FAILED** | Fraction stays **&lt; 0.15** (or remains null after 30+ genuine presses) **or** 0x31 still fires once press floor is met |

Rationale: Step A offline recovery hit **1.0** at thr=0.03 — that is the **upper** reference, not the pass bar. Live path has event-loop batching of snaps into the oracle; requiring ≥0.55 matches the product anomaly threshold and Step B’s inverse (0.0 at thr=30). Requiring ≥0.79 (Phase-17 human mean) is **aspirational**, not fail-closed for “scale is the bug.”

### Ask 5 — If recovery fails, fastest next isolation

Ordered **minimum new work**:

| Step | Isolates | How |
|------|----------|-----|
| **C-fail-1** | Under-correction vs wrong thr | Re-run same bridge session with thr=`0.01` then thr=`0.05` process-scoped only; if still ~0, not a fine-tune issue |
| **C-fail-2** | Integration vs oracle | Re-run **Step B script** with `L2B_IMU_SPIKE_THRESH=0.03` in that process (patch or env before import) on same desk presses — if standalone recovers but bridge doesn’t → integration confound |
| **C-fail-3** | Button / Cross bit remap | Log press_count from oracle `extract_features` vs raw Cross/R2 rising edges on WS/inference path; compare to Step B’s button remap |
| **C-fail-4** | Timing / batching | Confirm oracle receives gyro samples in the 5–80 ms pre-edge window under bridge poll batching (instrument temporary **script-side** only if operator allows a later build round — not this scope) |
| **C-fail-5** | Structural new | Only after 1–4 fail: open a new investigation (not auto-D1) |

Do **not** jump to D1 production thr change if C fails — that would mask an integration bug.

---

## 3. Definition-of-done outcome

**(b) Approve Step C with named modifications** (not as-is).

**Operator may execute** only after accepting:

1. Preflight table in §C3  
2. Port **8080** (or live HTTP_PORT)  
3. Keep-alive WS client  
4. No watchdog  
5. Process-scoped thr + belt `CHAIN_SUBMISSION_PAUSED` / `GRIND_MODE`  
6. Dual-gate success bar §Ask 4  

**This round does not authorize execution.** Operator finger still required for the live run.

---

## open-questions

1. Should Step C’s WS logger be a tiny **additive** script under `scripts/` in a later build round (still zero production edits), or is a one-off operator snippet enough?
2. After RECOVERY CONFIRMED, which production path does the operator prefer for D-phase: **D1** default thr rescale, **D3** end-to-end unit canon, or **D4** honesty-neutral until D3?
3. With `IOSWARM_ENABLED=true`, is there any desire to process-scope `IOSWARM_ENABLED=false` for maximum quiet — or is chain-pause sufficient (auditor recommendation: **pause is enough**)?

---

## Ceiling / rails

- No code changes, no bridge start by auditor  
- No `bridge/.env` edit  
- No FROZEN / PoAC / chain  
- Stage-only when/if follow-on scripts land  

**ONE VERDICT: APPROVE WITH MODIFICATIONS — Step C safe to operator-fire after checklist.**
