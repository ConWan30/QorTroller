# A2A-POEP-CATCH — catch trials + adversary re-run

**Opened 2026-07-17 · build path on FLIP-A ladder items 6 + software gate.**

## Scope
- Catch trials: GO / NO_GO (4:1), no force on NO_GO
- Adversary re-run: TellWatcher + always-fire catch + band-only honesty + human FA sim
- `poep_enabled` stays **False**

## Live capture
```powershell
python scripts/poep_live_capture.py --player P1 --count 10 --catch --force 255 --mode pulse --db "C:/Users/Contr/.vapi/bridge.db"
```

## Software re-run (no hardware)
```powershell
python -m l9_presence.poep_adversary_rerun --out audits/poep-adversary-rerun-DATE.md
```

## Bars
| Metric | Bar |
|--------|-----|
| Tell removal | stdout FAR≥0.90, continuous_poll FAR≤0.15 |
| Always-fire on NO_GO | catch ≥0.90 |
| Human FA on NO_GO (live) | ≤0.05 |
| Band-only macro | FAR≈1 (expected — not anti-bot) |

## Still not a flip
Live multi-day catch FA, operator claim language, two-key fire.
