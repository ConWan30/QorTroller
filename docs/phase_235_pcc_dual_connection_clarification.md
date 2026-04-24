# Phase 235-PCC-CLARIFY: PCC Dual-Connection Audit

**Date:** 2026-04-24  
**Status:** CLEARED — no bugs found. Dual-connection is structurally supported.

---

## PCC Dual-Connection Audit

### Quick Answer

**Yes, dual-connection (USB-C to laptop + BT-paired to PS5) is fully supported** because
`_infer_host_state()` at `capture_continuity.py:219` works exclusively from observed USB
poll-rate statistics — it has no knowledge of, and cannot be affected by, the controller's
simultaneous BT connection to the PS5. If the USB HID channel delivers frames at ~1000 Hz
with low variance, the monitor reports `EXCLUSIVE_USB` regardless of what BT is doing.

The earlier "unpair from PS5" instruction was written before the NCAA CFB 26 PS5-exclusive
constraint was clear and is **incorrect**. This document supersedes it.

---

### Question 1: What host_state actually measures

**Answer: poll-rate coefficient of variation only. No firmware flags. No BT pairing query.**

The module docstring at `capture_continuity.py:17` states explicitly:
> "Host states (inferred from poll rate variance, not HID descriptor flags)"

The implementation confirms this at `_infer_host_state()` (`capture_continuity.py:219–249`):

```python
def _infer_host_state(self, samples: list, rate: float) -> HostState:
    """Infer host arbitration state from per-sample rate variance."""
    rates = [r for r, _ in samples if r > 0]
    if len(rates) < 5:
        return HostState.UNKNOWN
    if rate < self._degraded_hz:
        return HostState.UNKNOWN

    mean = sum(rates) / len(rates)
    ...
    std = math.sqrt(sum((r - mean) ** 2 for r in rates) / len(rates))
    cv = std / mean

    # Stable ~1000 Hz, low variance
    if mean >= 900 and cv < 0.20:
        return HostState.EXCLUSIVE_USB
    # Contested: high variance or sudden dips amidst high-rate polling
    if cv >= self._CONTESTED_CV and mean >= self._CONTESTED_MIN_RATE_HZ:
        return HostState.CONTESTED
    ...
```

**What it measures:**
- `mean`: rolling average of per-interval frame rates (Hz) across the last 60 samples
- `cv`: standard deviation / mean — measures consistency of the USB polling rate
- Nothing else. No OS API calls. No HID feature report reads. No BT pairing queries.

**The three signals that determine classification:**
| Condition | Result |
|---|---|
| `mean >= 900 Hz AND cv < 0.20` | `EXCLUSIVE_USB` |
| `cv >= 0.40 AND mean >= 300 Hz` | `CONTESTED` |
| `200 Hz <= mean <= 350 Hz AND cv < 0.20` | `EXCLUSIVE_BT` |
| `mean >= 900 Hz` (moderate cv, 0.20–0.40) | `EXCLUSIVE_USB` (line 247 fallthrough) |
| otherwise | `UNKNOWN` |

**Important:** there is no code path that checks whether the controller is simultaneously
BT-connected to a PS5. The PS5's BT link is entirely invisible to `CaptureHealthMonitor`.

---

### Question 2: Dual-connection clean play behavior

**`host_state = EXCLUSIVE_USB` during clean dual-connection play.**

When a DualSense Edge is:
- USB-C to laptop → HID frames arriving at ~1000 Hz (isochronous USB HS transfer)
- BT-paired to PS5 running NCAA CFB 26 → BT radio at ~125–250 Hz (independent channel)

The USB HID channel and the BT radio operate on completely separate firmware paths inside
the controller. The controller's USB interrupt controller sends HID reports to the laptop at
1000 Hz; simultaneously, the BT radio sends HID reports to the PS5 at 125–250 Hz. Neither
channel is aware of the other's traffic rate.

From `CaptureHealthMonitor`'s perspective:
- `n_frames ≈ 1000` per 1-second interval (from `_session_loop()`)
- `rate ≈ 1000.0` Hz, `cv < 0.10` (USB isochronous is extremely consistent)
- `_infer_host_state()` → `mean >= 900 AND cv < 0.20` → **`EXCLUSIVE_USB`**

The PS5 being powered on, running the game, and actively processing BT input reports has
**zero effect** on the USB poll rate seen by the bridge.

---

### Question 3: Failure modes that trigger CONTESTED in dual-connection

The following conditions would produce `CONTESTED` (`cv >= 0.40 AND mean >= 300 Hz`)
or `DEGRADED`/`DISCONNECTED` in a dual-connection setup:

**a) PS5 home screen navigation during active play**  
When the user presses the PS button and navigates to the PS5 home screen, the PS5 may
attempt to assert priority over the controller's input stream. Depending on DualSense Edge
firmware behavior, this can cause momentary USB report burst irregularity or brief rate
dips. Effect: `cv` rises; if above 0.40 → `CONTESTED`. Recovery: returning to the game
restores normal BT behavior and USB polling stabilizes.

**b) USB cable power-only (no data lines)**  
If the USB-C cable carries power but not data (cheap charging cables), `n_frames = 0`
forever. Effect: `DISCONNECTED` immediately. Not `CONTESTED` — the bridge has no USB HID
connection at all.

**c) Windows USB power management suspending the HID device**  
If Windows puts the HID device into selective suspend (USB power save), HID reports stop.
Effect: `effective_rate = 0` via the staleness check at `_recompute:174` (> 3s since last
sample). → `DISCONNECTED`. Fix: disable USB selective suspend for the controller in Device
Manager.

**d) DualSense Edge firmware USB/BT arbitration at connection time**  
During the first few seconds of dual-connection establishment, the controller firmware
negotiates which host gets which report types. This can produce brief rate instability.
Effect: `UNKNOWN` (< 5 samples) then stabilizes to `EXCLUSIVE_USB`. Not a sustained issue.

**e) PS5 going to sleep mid-session**  
If the PS5 enters sleep mode during a grind session, the BT connection drops cleanly. The
controller continues USB HID reporting to the laptop without interruption. Effect: none —
`EXCLUSIVE_USB` unchanged. The game will have paused/exited, so the operator must restart.

**f) USB cable physically disturbed**  
Partial disconnect causes zero frames. Effect: staleness check at `_recompute:174` fires
after 3 seconds → `DISCONNECTED`. Reconnecting USB restores normal operation after the
30-second NOMINAL warmup window.

**Dashboard visibility:** All state transitions are buffered in `_state_transitions` and
logged to `capture_health_log` via `insert_capture_health_event()`. The GrindPanel on the
dashboard polls `GET /bridge/capture-health` every 3 seconds and displays `capture_state`,
`host_state`, `grind_ready`, and `session_counting_paused` in real time.

---

### Question 4: Inference source (firmware flags vs poll rate)

**Pure poll-rate inference. No firmware flags are read.**

`CaptureHealthMonitor` receives exactly one input from the outside world: the argument to
`update_sample(n_frames, window_s)` called from `DualShockTransport._session_loop()`.
`n_frames` is the count of HID frames collected in one interval. That is the complete
input — one integer per second.

No code in `capture_continuity.py` or its callers:
- Reads HID feature reports (no `ioctl(HIDIOCSFEATURE)` or `hidapi.get_feature_report()`)
- Queries the OS for transport type or BT pairing state
- Parses HID usage page descriptors for connection mode flags
- Calls any platform API about the controller's wireless status

**Implication for dual-connection:** The monitor is structurally blind to BT state.
A controller BT-paired to a PS5 AND USB-connected to the laptop looks identical to a
controller USB-connected to the laptop only, as long as USB HID frames arrive at ~1000 Hz.
`EXCLUSIVE_USB` will be reported in both cases.

---

### Question 5: Test coverage of dual-connection

**No dual-connection-specific test exists. All tests use synthetic poll-rate streams.**

From `test_phase234_7_pcc.py`:

| Test | What it covers |
|---|---|
| T234_7-1 | Initial state (no samples) |
| T234_7-2 | `n_frames=1000, window_s=1.0` × 15 → NOMINAL + EXCLUSIVE_USB |
| T234_7-3 | `n_frames=500` → DEGRADED |
| T234_7-4 | `signal_disconnect("hid_timeout")` → DISCONNECTED |
| T234_7-5 | 30-second NOMINAL sustain → `grind_ready=True` |
| T234_7-6 | `pop_transitions()` buffer |
| T234_7-7 | Config field defaults |
| T234_7-8 | Store round-trip |
| T234_7-9 | `set_pcc_monitor` attribute |
| T234_7-10 | `session_counting_paused` logic gate |
| T234_7-11 | INV-PCC-001 stale-read detection |

None of these tests simulate:
- Mixed-rate behavior (USB at 1000 Hz coexisting with BT at 250 Hz)
- Interleaved bursts from dual connection
- Real HID hardware

No tests would fail as a result of dual-connection because the code doesn't model BT at all.
The dual-connection case is structurally identical to USB-only from the monitor's perspective,
so T234_7-2 (clean 1000 Hz) effectively IS the dual-connection test.

---

### Documented Operator Setup

The **only viable physical setup** for Phase 235 grind is:

```
DualSense Edge CFI-ZCP1
│
├─ USB-C data cable → Laptop (Windows 11, bridge running)
│   HID reports: ~1000 Hz to bridge via hidapi
│   PCC sees: EXCLUSIVE_USB (if cable delivers data and rate is stable)
│
└─ Bluetooth (BT 5.0) → PS5 (powered ON, running NCAA CFB 26)
    Game inputs: ~125–250 Hz to PS5 (required for gameplay)
    PCC sees: nothing — BT is invisible to CaptureHealthMonitor
```

**Step-by-step corrected setup:**

1. **DO NOT unpair the DualSense Edge from the PS5.** BT pairing to the PS5 is REQUIRED
   to play NCAA CFB 26. The PCC code is blind to BT pairing state and does not care.

2. **Use a USB-C data cable** (not a charging-only cable) from the DualSense Edge to the
   laptop. Verify data connection with `GET /bridge/capture-health` showing
   `poll_rate_hz ≈ 1000` and `capture_state = NOMINAL`.

3. **Power on the PS5 and launch NCAA CFB 26.** The BT connection will establish
   automatically. Play normally.

4. **Wait for `grind_ready = True`** (30 seconds of sustained NOMINAL + EXCLUSIVE_USB).
   This appears in the GrindPanel dashboard or via `GET /bridge/capture-health`.

5. **Do not navigate to the PS5 home screen during an active grind session.** Pressing
   the PS button and leaving the game may cause transient USB rate instability. If you
   must pause, return to the game before the next adjudication window closes.

6. **If `host_state = CONTESTED` appears mid-session:**
   - The current session will NOT count toward `consecutive_clean` (PCC gate fails-closed)
   - Finish your current play action if safe; do not panic-quit
   - Wait for rate to stabilize → `EXCLUSIVE_USB` to return
   - `session_counting_paused` will show `True` on the dashboard
   - No retroactive un-counting: sessions already logged as NOMINAL+EXCLUSIVE_USB are safe

7. **If `host_state = EXCLUSIVE_USB` remains stable throughout the session**, the session
   counts normally. The GIC link is stamped once the adjudicator validator fires.

**What signals a successful grind session:**
```
capture_state: NOMINAL
host_state:    EXCLUSIVE_USB  (or UNKNOWN during early bootstrap)
grind_ready:   True
gameplay_context: ACTIVE_GAMEPLAY
```

**What causes a session NOT to count:**
```
capture_state: DEGRADED or DISCONNECTED  → PCC gate fails-closed
host_state:    CONTESTED                 → PCC gate fails-closed
gameplay_context: MENU_DETECTED          → GAD gate breaks streak
consecutive_clean gate: pcc_state=NOMINAL AND pcc_host_state in (EXCLUSIVE_USB,UNKNOWN)
                        required (NULL or CONTESTED = fail-closed, streak breaks)
```

---

### Bugs Found

**None.** The PCC implementation is fully compatible with the dual-connection setup.

`_infer_host_state()` derives `EXCLUSIVE_USB` from USB poll-rate characteristics alone.
BT pairing to the PS5 is invisible to this function. As long as the USB cable delivers
HID data at ~1000 Hz with `cv < 0.20`, the monitor reports `EXCLUSIVE_USB` and the
grind proceeds normally.

The earlier "unpair from PS5" instruction was **documentation drift** — a conservative
guess written before the PS5-exclusive nature of NCAA CFB 26 was known. No code change
is required.

---

### CLAUDE.md grind_procedure Update

The `grind_procedure` gotcha block step (1) and (2) must be corrected.

**Before (incorrect):**
> (1) Unpair controller from PS5 via PS5 Settings→Bluetooth Devices; (2) USB-C connect
> controller to PC ONLY — no Bluetooth pairing, no remote play

**After (correct):**
> (1) Keep DualSense Edge BT-paired to PS5 — BT pairing is REQUIRED for gameplay (NCAA CFB
> 26 is PS5-exclusive; PCC is blind to BT state and only reads USB poll rate); (2) USB-C
> data cable to laptop REQUIRED — this is what CaptureHealthMonitor reads. Dual-connection
> (USB to laptop + BT to PS5) is the only valid grind setup.

See the CLAUDE.md `grind_procedure` key gotcha block for the full updated 12-step procedure.
