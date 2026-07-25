# A2A — RWM · round 12 · grok (sole agent continue)

**Channel:** terminal A2A bus · operator: “as the sole agent continue”  
**Prior:** R11 live_05 post (FROZEN_RING finding); NOV-3 shipped `073819da`

---

## What shipped this round

### 1. Mid-session FROZEN_RING alert (watcher)
`scripts/rwm_live_session_watch.py` now probes the last-20 panel hashes each progress tick.
After **≥20 crops**, if unique stays 1 → emits `frozen_ring_alert` so the operator can retarget source **before** finishing a useless session (live_05 lesson).

### 2. Shared diversity helper
`bridge/vapi_bridge/rwm_panel_diversity.py` — pure `panel_content_stats` / `panel_stats_for_dir`.
Used by post-session check + watcher (one definition of FROZEN_RING).

### 3. `RWM_BLOCK_PX` env override (optional, r08 follow-up)
`scripts/retina_capture_daemon.py`:
- default remains **32** (D7 placeholder)
- `RWM_BLOCK_PX` via process env or `bridge/.env` (same dotenv arm as flags)
- invalid / non-positive → fail-open default + log

### 4. Tests
`bridge/tests/test_rwm_panel_diversity.py` — frozen/diverse/sample_limit + block_px env cases.
Full RWM suite this pass: **28 passed**.

---

## Not done (still operator / hardware)

| Item | Why blocked |
|------|-------------|
| Diverse live capture | Needs live game + non-static panel ROI (live_05 UVC advanced, ROI frozen) |
| NOV-2 open | Ladder gate: NOV-3 dogfood enough; no scope doc yet |
| Live-rig palette calib | D7 deferred |

---

## How to use next session

```text
# optional mark size (default 32)
# bridge/.env: RWM_BLOCK_PX=32

python scripts/retina_capture_daemon.py start --label cfb_rwm_live_06 --uvc-index 2 --capture ...
python -u scripts/rwm_live_session_watch.py
# watcher will emit frozen_ring_alert if last-20 stay identical after 20 crops
python scripts/retina_capture_daemon.py stop --label cfb_rwm_live_06
```

---

## Rails

No PoAC/FROZEN/PV-CI/stop-path coupling change beyond env read for block_px. Archives still gitignored.

*Round-12 — sole agent continue 2026-07-25.*
