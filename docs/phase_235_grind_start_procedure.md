# Phase 235 — Grind Session 1 Start Procedure

**Version:** Phase 235-GAD (Bridge 2444 / SDK 527)  
**Target:** 100 consecutive_clean sessions with PCC + GAD + non-divergence gates  
**Result artifact:** GIC_100 — cryptographic chain hash anchored to IoTeX L1 (Phase 236)

Read every step before executing any. Do not skip steps. Do not improvise.

---

## Before You Sit Down

Hardware checklist (do these before touching the computer):

- [ ] DualSense Edge battery: **fully charged**
- [ ] PS5: **completely powered off** (not standby — hold PS button → Power Options → Turn Off PS5)
- [ ] USB-C cable: connected between DualSense Edge and laptop (**no hub, no USB switch**)
- [ ] PS5 Bluetooth pairing: **cleared** (on PS5: Settings → Bluetooth → DualSense Edge → Remove device; OR factory-reset the controller: hold CREATE + PS button 5 seconds until light bar flashes)

---

## Step 1 — Verify bridge/.env Configuration

Open `C:\Users\Contr\vapi-pebble-prototype\bridge\.env` and confirm **exactly**:

```
GRIND_SESSION_ID=grind_phase235_v1
GRIND_MODE=true
GRIND_TARGET=100
```

**Critical:** `GRIND_SESSION_ID` must be **identical** on every bridge restart during the grind.
A different ID creates a new genesis hash, resetting the chain. Use the value above verbatim.

If `ANTHROPIC_API_KEY` is not set, add it. The SessionAdjudicator will fall back to the rule
engine gracefully, but LLM adjudication provides richer evidence context.

---

## Step 2 — Confirm Environment is Clean

From the project root, run:

```bash
cd C:\Users\Contr\vapi-pebble-prototype
python scripts/grind_test_tools.py verify-empty grind_phase235_v1
```

Expected output: `PASS: ruling_validation_log is empty. Ready for real grind.`

If FAIL: investigate residual rows before proceeding. Do not start on dirty state.

---

## Step 3 — Start the Bridge

```bash
cd C:\Users\Contr\vapi-pebble-prototype
python -m bridge.vapi_bridge.main
```

Watch the startup log. Within the first 20 lines you must see:

```
============================
GRIND SESSION ID : grind_phase235_v1
GRIND MODE       : ACTIVE
GRIND TARGET     : 100
============================
```

If you don't see this block, check `bridge/.env` — the values aren't loading.

---

## Step 4 — Confirm PCC Warmup

Wait 30 seconds after bridge starts, then query:

```bash
curl -s -H "x-api-key: YOUR_KEY" http://localhost:8080/bridge/capture-health | python -m json.tool
```

Or open the dashboard (Step 5) and watch the GRIND INTEGRITY CHAIN panel.

**Required state before playing:**

| Field | Required value |
|-------|---------------|
| `capture_state` | `NOMINAL` |
| `host_state` | `EXCLUSIVE_USB` |
| `grind_ready` | `true` |
| `session_counting_paused` | `false` |
| `consecutive_clean_toward_target` | `0` |

If `grind_ready` is `false`: wait. The bridge needs 30 seconds of sustained NOMINAL + EXCLUSIVE_USB
to set the warmup flag. This typically takes 30–45 seconds from startup.

If `host_state` is `CONTESTED`: the PS5 is still claiming the controller. Confirm PS5 is fully off,
not just in standby. If the problem persists, use the controller's factory-reset (hold CREATE + PS 5 seconds).

---

## Step 5 — Open the Dashboard

```bash
cd C:\Users\Contr\vapi-pebble-prototype\frontend
npm run dev
```

Dashboard opens at: **http://localhost:5173** (default Vite port)

Navigate to: **Gamer view** (leftmost tab in the view selector)

You will see the **GRIND INTEGRITY CHAIN** panel showing:

- Progress bar: `consecutive_clean / grind_target` (starts at 0/100)
- PCC state: `NOMINAL` (green)
- HOST: `EXCLUSIVE_USB` (green)
- READY: `YES` (green)
- CHAIN: `0 links`
- GAMEPLAY: `NULL` (until first adjudication cycle fires)
- Session ID: `grind_phase235_v1`

---

## Step 6 — Verify Chain is Empty

```bash
curl -s -H "x-api-key: YOUR_KEY" http://localhost:8080/bridge/grind-chain-status | python -m json.tool
```

Expected:

```json
{
  "chain_length": 0,
  "chain_intact": true,
  "grind_session_id": "grind_phase235_v1"
}
```

If `chain_length > 0`: residual rows from a prior test exist. Investigate before continuing.

---

## Step 7 — Launch NCAA CFB 26

1. Launch NCAA CFB 26 on the laptop via whatever launcher you use
2. Start a **Play Now** game or **Online Franchise** game vs CPU — any competitive mode with real snaps
3. Do NOT start Dynasty recruiting screens, menus, or other non-gameplay activities

The GAD gate requires at least one L2/R2 trigger press per adjudication window
(~5-minute window). Normal competitive play with R2 snaps automatically satisfies this.

---

## Step 8 — Play and Monitor

Play normally. Watch the dashboard GRIND INTEGRITY CHAIN panel.

**After the first ~5 minutes of gameplay:**
- `consecutive_clean_toward_target` should advance to 1
- `GAMEPLAY` should show `ACTIVE_GAMEPLAY`
- `CHAIN` should show `1 links`

**What will pause counting:**
- `host_state` transitions to CONTESTED (PS5 waking up, trying to claim controller)
  → Disconnect PS5 power, wait for EXCLUSIVE_USB recovery
- `gameplay_context` shows MENU_DETECTED (no trigger presses in evidence window)
  → Return to active gameplay; menu sessions are cleanly excluded, no streak reset required
  → The streak only breaks if you haven't played recently enough for a full evidence window

**What will break the chain:**
- `chain_intact` turns false (GIC tamper detected on startup)
  → Call POST /operator/gic-reset with a reason, then restart bridge

---

## Step 9 — Complete the Grind (100 sessions)

When `consecutive_clean_toward_target` reaches 100:

1. **Run tournament preflight:**
   ```bash
   curl -s -X POST -H "x-api-key: YOUR_KEY" http://localhost:8080/agent/run-tournament-preflight | python -m json.tool
   ```
   Confirm `overall_pass: true`.

2. **Activate Stage 1 graduation:**
   ```bash
   curl -s -X POST -H "x-api-key: YOUR_KEY" \
     -H "Content-Type: application/json" \
     -d '{"agent_id": "ruling_enforcement_agent"}' \
     http://localhost:8080/agent/activate-graduation-stage | python -m json.tool
   ```

3. **Record GIC_100:**
   ```bash
   curl -s -H "x-api-key: YOUR_KEY" http://localhost:8080/bridge/grind-chain-status | python -m json.tool
   ```
   Copy `latest_gic_hash` — this is GIC_100, the Phase 236 Zenodo deposit headline artifact.

4. **Generate final snapshot:**
   ```bash
   python scripts/generate_grind_readiness_snapshot.py --bridge-url http://localhost:8080
   ```

---

## Emergency Procedures

### Controller unplugged mid-session
- Reconnect USB-C
- Wait 30s for `grind_ready` to return to `true`
- Bridge automatically resumes counting — the interrupted session does not count, but streak is NOT reset
- If startup log shows GIC CHAIN BROKEN: call POST /operator/gic-reset with reason

### Bridge crash mid-grind
- Restart bridge with same `bridge/.env` values
- Confirm startup shows same `GRIND_SESSION_ID`
- Confirm `chain_intact: true` via GET /bridge/grind-chain-status
- If chain is intact: resume normally — GIC chain survives restarts by design

### PS5 captures controller (host_state → CONTESTED)
- Turn PS5 fully off (not standby)
- Wait 45s for `host_state` to return to `EXCLUSIVE_USB`
- Any sessions during CONTESTED period have `grind_chain_hash=NULL` — they don't count, they don't break the chain

### `latest_gameplay_context` shows MENU_DETECTED unexpectedly
- This means the evidence window had zero trigger presses
- You were either in a timeout, half-time cut-scene, or extended play-call screen
- Return to active gameplay; next adjudication window that has any R2 snap will classify as ACTIVE_GAMEPLAY
- Streak breaks on MENU_DETECTED: you need a new ACTIVE_GAMEPLAY session to extend consecutive_clean again

---

## Dashboard Access Quick Reference

| Action | Command |
|--------|---------|
| Start bridge | `cd bridge && python -m vapi_bridge.main` (from project root: `python -m bridge.vapi_bridge.main`) |
| Start dashboard | `cd frontend && npm run dev` |
| Dashboard URL | http://localhost:5173 |
| Grind status panel | GamerView → GRIND INTEGRITY CHAIN (top of stats panel) |
| Raw endpoint | `curl http://localhost:8080/bridge/capture-health` |
| Chain status | `curl http://localhost:8080/bridge/grind-chain-status` |
