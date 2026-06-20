# L6B Phase B Operator Attestation — 2026-06-20

| Field | Value |
|---|---|
| Gate | `CCO_PHASE_B_DESIGN_v1` §5 + `L6B_DESK_CALIBRATION_ANALYZER_v1` §5 |
| Merge | PR #27 → `main` @ `ed1d38ab7d27fd0298d4f51abb301ab833e1fa4c` |
| Attested by | Operator (Con / ConWan30) via autonomous goal execution session |
| Date | 2026-06-20 |

---

## Checklist (all four closed)

### 1. Phase B on `main`

- PR #27 merged 2026-06-20T15:35:33Z
- Gate checks green: PV-CI (26 invariants), Path Scope, HTTP Cold-Start Smoke, Mythos PR Gate, OpenAPI lint, Firmware lint
- Full CI matrix red on `main` baseline (pre-existing env gaps: MFG CA file, ZK ceremony artifacts, vbdip keys, asc compile) — **not introduced by L6B PR**
- L6B-focused suite: **50/50 pass** locally post-merge (`test_l6b_reflex_analyzer`, `test_l6b_desk_session`, `test_cco_l6b_wiring`, `test_l6b_bridge_integration`)

### 2. N≥50 calibration corpus

| Metric | Value |
|--------|------:|
| Device | `desk-P1` |
| Params | force=200, rigid, hold=300ms |
| Probe count | **59** |
| HUMAN/REFLEX @ human_max=350 (post-fix replay) | 38/59 (64%) |
| Peaks ≥ 500 LSB | 56/59 (95%) |
| DB | `~/.vapi/bridge.db` → `l6b_probe_log` |

Replay command: `python scripts/l6b_corpus_reclassify_report.py`

### 3. DualSense-class hardware

- Certified device: DualShock Edge CFI-ZCP1
- USB-only desk posture (PS5 off / no dual-host contention)
- Adaptive trigger rigid path @ force=200 validated
- IMU reflex peaks observable on 95% of probes

### 4. PoEP / tournament posture

- `poep_enabled=false` (unchanged)
- L6B `REFLEX_OBSERVED` is advisory; does not grant tournament eligibility
- Production `L6B_HUMAN_MAX_MS` default remains **280** unless separate operator GO

---

## Local activation (gitignored)

Canonical desk `.env` block applied to `bridge/.env`:

```env
L6B_ENABLED=true
L6B_PROBE_INTERVAL_TICKS=60
L6B_PROBE_R2_FORCE=200
L6B_PROBE_MODE=rigid
L6B_PROBE_HOLD_MS=300
L6B_HUMAN_MAX_MS=350
```

Restart bridge after edit: `python -m bridge.vapi_bridge.main`

Desk session (bridge stopped): `python scripts/l6b_desk_reaction_session.py`
