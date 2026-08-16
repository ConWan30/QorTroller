# DualSense Edge Bluetooth observer — Phase 1 runbook

**Status:** research / CANDIDATE  
**Topology (Phase 0 proven):**

| Link | Role |
|------|------|
| Edge **USB → PS5** | Gameplay (PS5 Bluetooth off recommended) |
| Edge **Bluetooth → Windows** | This observer (HID report stream) |

**Not** the default grind topology (USB → PC + BT → PS5).  
**Not** USB ~1000 Hz PCC/grind physics. Measured BT stream is often ~500–600 Hz.

## Rules

- READ-only observer — **no L6 / haptic write** in Phase 1  
- **Zero IOTX** / no chain  
- Do not claim humanity / tournament-grade from BT reports alone  
- Eye-check still applies to any optical/retina path you run in parallel  

## Quick probe

```powershell
cd C:\Users\Contr\vapi-pebble-prototype
python scripts/bt_phase0_hid_probe.py
python scripts/bt_phase0_hid_probe.py --sample 5
```

Expect `RESULT: REPORTS_OK` while mashing buttons (desktop or in-game).

## Capture session (JSONL)

```powershell
python scripts/bt_edge_observe.py --smoke 5
python scripts/bt_edge_observe.py --duration 60 --out logs/bt_edge_obs_play.jsonl
```

JSONL events: `session_start`, `device_open`, `sample`, `session_end`.  
Domain tag in meta: `QORTROLLER-BT-EDGE-OBSERVER-v0` (not a FROZEN commitment family).

## Pairing order (if Windows loses the pad)

1. PS5: Bluetooth off / forget Edge  
2. Unplug USB from PS5  
3. Edge pairing mode (Create + PS, fast blink) → pair to Windows  
4. Confirm probe `ENUM_OK` / `REPORTS_OK`  
5. Plug USB back into PS5 for gameplay; re-check reports in-game  

## If probe is silent (0 reports)

Earlier Phase 0 saw **~560 Hz** and decodable R2/sticks when the stream was live.
Windows can also drive the **mouse** from the pad (touchpad / accessibility).
If the observer opens but is silent:

1. Move sticks / press face buttons **during** the sample window  
2. Quit **Steam**, DS4Windows, Xbox Game Bar overlays that exclusive-open HID  
3. Toggle BT off/on or re-pair the Edge  
4. Unplug/replug USB on PS5 after PC BT is solid  
5. Re-run: `python scripts/bt_edge_observe.py --smoke 5`

Mouse moving on the desktop is still evidence the OS sees the pad even when
our process temporarily gets 0 raw reports (exclusive reader contention).

## Next (not Phase 1)

- Bridge transport adapter selecting BT vs USB  
- PCC `EXCLUSIVE_BT` readiness for research sessions  
- Couple JSONL windows to retina session_id (local only)  
- Any write/L6 path needs exclusive-ownership proof first  
