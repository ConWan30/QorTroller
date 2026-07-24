# Round LIVE-02 — L1+L2 build (operator-tree landing)

**Status:** BUILT on operator repo · tests green  
**Note:** Cowork sandbox export was not present locally; L1+L2 implemented on operator tree from sealed design + Cowork handoff semantics (catch scorer fixed to real `score_trial` API).

## Shipped

| Path | Role |
|------|------|
| `l9_presence/poep_gameplay_live.py` | seal, start_live, bridge poll, PCC, challenge_live, sealed summarize |
| `scripts/poep_gameplay_live.py` | start-live / tick / challenge / stop-live CLI |
| `l9_presence/tests/test_poep_gameplay_live.py` | T-L1/L2 suite |

## Honesty (design §8)

| Bar | Evidence |
|-----|----------|
| Dry non-candidate | T-L1 dry_cannot_candidate |
| Seal invalid → no candidate | T-L2 bad_seal_kills_candidate |
| MENU/UNKNOWN refuse | T-L2 refuse_activity |
| PCC CONTESTED refuse | T-L2 refuse_pcc |
| Amplitude 255→80 | T-L2 amplitude_clamp |
| NO_GO never fire | T-L2 nogo_never_fires |
| Mock fire not candidate | T-L2 go_mock_not_candidate |
| Live double can candidate | T-L2 go_live_double_can_candidate |
| poep_enabled False | all summaries |

## Tests

```
l9_presence/tests/test_poep_gameplay_live.py + test_poep_gameplay_session.py
26 passed
```

## Operator commands (mock fire — no pad force)

```powershell
python scripts/poep_gameplay_live.py start-live --player P1
# with bridge UP:
python scripts/poep_gameplay_live.py tick
python scripts/poep_gameplay_live.py challenge --i-am-playing --allow-offline-pcc
python scripts/poep_gameplay_live.py challenge --allow-offline-pcc
python scripts/poep_gameplay_live.py stop-live
```

Real force: `POEP_LIVE_FIRE_ENABLED=1` + `--fire real` (L3 rig — currently fails honest until pad write wired).

## Findings for round-03

1. **Real HID write** is still L3 (make_real_hid_fire returns not-fired until DualSense path wired under exclusive USB).  
2. Mock path intentionally cannot mint candidate (`real_hardware=False`).  
3. `--allow-offline-pcc` is plumbing-only for bridge-down smoke.

## Rails

No commit from agent · flags False · composition over sealed gameplay_session module.
