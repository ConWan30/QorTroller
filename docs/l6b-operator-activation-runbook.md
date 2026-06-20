# L6B Operator Activation Runbook (CCO Phase B.3)

**Status:** Operator-facing — local activation only; CI/default remains `L6B_ENABLED=false`.  
**Parent:** `wiki/methodology/CCO_PHASE_B_DESIGN_v1.md` §8; attestation `audits/l6b-operator-attestation-2026-06-20.md`

---

## 1. Preconditions (all required)

| # | Gate | Verify |
|---|------|--------|
| 1 | Phase B on `main` | `git log -1 --oneline` includes L6B wiring merge |
| 2 | §5 attestation signed | `wiki/methodology/L6B_DESK_CALIBRATION_ANALYZER_v1.md` §5 all `[x]` |
| 3 | N≥50 corpus | `python scripts/l6b_probe_status.py` → gate reached |
| 4 | `poep_enabled=false` | `grep POEP bridge/.env` — must stay false for T0-only posture |

---

## 2. Local `.env` block (gitignored)

Copy from `docs/l6b-calibration-test-env.example` or use validated desk params:

```env
L6B_ENABLED=true
L6B_PROBE_INTERVAL_TICKS=60
L6B_PROBE_R2_FORCE=200
L6B_PROBE_MODE=rigid
L6B_PROBE_HOLD_MS=300
L6B_HUMAN_MAX_MS=350
```

**In-game sessions:** raise `L6B_PROBE_INTERVAL_TICKS` to 300–400; keep production `L6B_HUMAN_MAX_MS=280` unless operator GO for desk-only widening.

---

## 3. Activation steps

1. **Preflight hardware** (USB-only desk recommended first):
   ```powershell
   python scripts/l6_hardware_check.py
   ```
2. **Edit** `bridge/.env` with block above.
3. **Restart bridge:**
   ```powershell
   python -m bridge.vapi_bridge.main
   ```
4. **Verify session surface** (read-key):
   ```powershell
   curl -H "x-api-key: $env:OPERATOR_API_KEY" http://127.0.0.1:8000/player/session-status
   ```
   Expect `cco.l6b_enabled=true`, `cco.calibration.gate_reached=true`, oracle `presence_ceiling_candidate` for Edge-class profile.
5. **Desk operator-paced capture** (bridge **stopped** — avoids auto-probe contention):
   ```powershell
   python scripts/l6b_desk_reaction_session.py --player P1 --target 10
   ```
6. **Monitor corpus:**
   ```powershell
   python scripts/l6b_probe_status.py
   python scripts/l6b_probe_diagnostic_report.py
   ```

---

## 4. Unified grind + L6B (optional)

When bridge runs with `L6B_ENABLED=true` and NCAA gameplay:

```powershell
python scripts/unified_session_monitor.py --player P1 --game "NCAA Football 26"
```

GIC chain and L6B probes share the same bridge session; R2-quiet gate skips sprint windows.

---

## 5. Rollback

Set `L6B_ENABLED=false` in `bridge/.env` and restart bridge. No schema rollback required; `l6b_probe_log` rows are append-only audit.

---

## 6. Honesty rails (do not skip)

- `REFLEX_OBSERVED` is **telemetry only** — not tournament eligibility, not PoEP `PRESENT`.
- Do **not** set `L6B_ENABLED=true` in CI, default config, or shared deploy templates.
- Do **not** widen production `human_max` to 350 without separate operator GO (desk calibration posture only).
