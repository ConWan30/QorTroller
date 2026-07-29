# Dual-connect continuum live run — 2026-07-25

**Operator:** ready · dual-connect · bridge started with process-scoped `POEP_LIVE_FIRE_ENABLED=1`  
**Archive:** `cfb_rwm_live_10_1784953588` (Edge `581a836c…`, U1 `a33d240b…`)  
**Bridge:** main-repo process, `/health` OK · capture-health `NOMINAL` / `EXCLUSIVE_USB` · poll ~1.6 kHz  
**L6B:** true in `bridge/.env` · fire endpoint: `POST /operator/operator/poep/fire` (doubled prefix)

## Result (honest)

| Surface | Outcome |
|---------|---------|
| Optical L0 re-verify | **PASS** |
| ioID ceremony bind | **PASS** (token 498) |
| Dual-connect bridge fires | **PASS** — `fired=true` + `real_hardware=true` on multiple probes |
| Preflight ACTIVE_GAMEPLAY | **PASS** (frac 0.10→0.50, window_n≥19) |
| GO verify (`verify_live_response`) | **FAIL** — `n_go_issued=2`, `n_go_verify_pass=0` |
| `presence_session_candidate_ok` | **False** |
| Continuum verdict | **`OPTICAL_IDENTITY`** (not SYNCHRONIZED) |

## Why not SYNCHRONIZED

Sealed gameplay summary requires `dry_plumbing_ok` (GO verify floor) **and** live hardware.  
Live path had:

- `effective_live=True`, `live_hardware=True`, `activity_source=bridge`, `activity_ok=True`
- `go_ok=False` because measured reflexes did not pass reaction-band + IMU floor

Probe sample (5 fires, amp 60–80):

| amp | latency_ms | peak_lsb | band 80–450 | peak ≥1000 |
|-----|------------|----------|-------------|------------|
| 60 | −1 | 412 | no | no |
| 80 | 846 | 1072 | no | **yes** |
| 80 | 5424 | 788 | no | no |
| 80 | −1 | 237 | no | no |
| 70 | 5760 | 673 | no | no |

**PASS_ANY band∧peak: False.**  
Composition and dual-connect ring are live; the **reflex measurement / band gate** is the remaining bar to play-attested SYNCHRONIZED.

## Artifacts

- `audits/poep_live_summary_LIVE10_bridge_diag.json` — sealed summary (candidate false)
- `audits/rwm_continuum_LIVE10_bridge_diag.json` — continuum **OPTICAL_IDENTITY**
- This note

## Non-claims

- Did **not** flip `poep_enabled` / invent candidate
- Did **not** claim play-attested SYNCHRONIZED
- Sim-live SYNCHRONIZED dogfood remains mechanism-only (prior artifact)

## Next (operator)

1. Desk-still or known-good reflex conditions (clean IMU peak in-band) while dual-connect ring fires  
2. Or extend campaign/analyzer if dual-connect gameplay systematically yields out-of-band latency  
3. Re-run:  
   `POEP_LIVE_FIRE_ENABLED=1 python scripts/rwm_continuum_dual_connect_live.py --archive … --require-candidate`
