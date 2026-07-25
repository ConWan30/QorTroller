# A2A — RWM · round 13 · grok (sole agent continue)

**Channel:** terminal A2A bus · operator: “as the sole agent continue”  
**Prior:** R12 frozen_ring_alert + RWM_BLOCK_PX (`41e53ae9`)

---

## What shipped this round

### 1. NOV-2 scope OPEN (design-only)
`docs/a2a/retina-witness-mark-ladder/nov-2-scope.md`

| Artifact (proposed) | Role |
|---------------------|------|
| Session bind v0 | Verified PoAC-segment / GIC tip (replaces free-text-only `external_ref`) |
| Multi-checkpoint locator | N mark windows; L0 N=1 stays valid |
| Dispute share postcard | LOCAL full vs SHARE-redacted (receipt dual-surface pattern) |

**Not built.** Needs implementation plan + operator GO (same rail as NOV-3).

Ladder README + RWM `scope.md` status lines updated.

### 2. Live watcher honesty (ops, not FROZEN)
`scripts/rwm_live_session_watch.py`:

- **`eye_check_prompt`** — once, on first panel crop: absolute path + “open this PNG now”
- **`--diversity-alert-at`** default **10** (was hard-coded 20) — earlier freeze signal
- **`--sample-limit`**, **`--interval-s`** CLI knobs
- still never kills the watch loop on diversity errors

### 3. Tests
`test_watcher_argparse_defaults` + `test_watcher_newest_panel` in
`bridge/tests/test_rwm_panel_diversity.py`.

### 4. Bus hygiene
R12 mailbox envelope + ledger staged with this commit if still uncommitted.

---

## Not done (operator / hardware)

| Item | Why blocked |
|------|-------------|
| Diverse live capture `live_06` | Needs live game + non-static panel ROI |
| NOV-2 implementation plan / code | Scope only; needs GO |
| NOV-1 | Gated on NOV-2 live-verify |
| Live-rig palette calib | D7 deferred |

---

## How to use next session

```text
python scripts/retina_capture_daemon.py start --label cfb_rwm_live_06 --uvc-index 2 --capture ...
python -u scripts/rwm_live_session_watch.py --diversity-alert-at 10
# → eye_check_prompt with path: OPEN the PNG, confirm gameplay
# → frozen_ring_alert if last-N stay identical after ≥10 crops
python scripts/retina_capture_daemon.py stop --label cfb_rwm_live_06
```

---

## Rails

No PoAC / FROZEN / PV-CI / stop-path change. NOV-2 is docs only. Archives still gitignored.
Escrow dogfood JSON stays local (device_id + leaf hashes; not committed).

*Round-13 — sole agent continue 2026-07-25.*
