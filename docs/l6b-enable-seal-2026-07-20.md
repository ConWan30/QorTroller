# L6B enable-seal — preparation + firing ceremony (operator-fired) · 2026-07-20

**Status: PREPARED, NOT FIRED. Blocked on a DB-reconciliation decision (F-L6B-SEAL-1 below).**
Claude prepares; the operator fires. `L6B_ENABLED` is an operator seal, never flipped autonomously.
Advisory work (the reaction band / `detect_session`) is unaffected either way — different code path.

## What flipping `L6B_ENABLED=true` does (be clear-eyed)
`L6B_ENABLED=false` is the shipped default. Flipping it true, on the LIVE bridge:
1. **Enables the L6B neuromuscular-reflex layer** in `dualshock_integration` — the auto-tick fire path
   (`_l6b_pre_buffer` → `_l6_driver` fire → `_l6b_post_buffer` → `_l6b_analyzer` → `_l6b_pending`).
2. **Adds the L6B reflex to the LIVE humanity-probability formula** (per the hard rule, the auto-tick + the
   humanity-formula contribution are STRICTLY `l6b_enabled`-gated — `poep_campaign_mode` never unlocks them).
3. **Unblocks the live-play ring campaign** (the ring requires `l6b_enabled=True` — see the arc spec).
It does NOT flip `poep_enabled` (stays False), does NOT gate tournaments, does NOT spend or touch chain.

## Gate verification (run 2026-07-20 — the honest state)
The gate is `l9_presence/poep_reflex_gate.is_usable_reflex` → `get_l6b_calibration_progress` (INDEPENDENT
usable reflexes on the certified Edge `581a836c…`), target N≥50. Checked live with `scripts/l6b_probe_status.py`:

| DB | Edge independent usable reflexes | gate_reached |
|---|---|---|
| `~/.vapi/bridge.db` (5.7 GB, where the 07-15→17 corpus lives) | **198** (221 valid / 1365 probes) | **TRUE** |
| `~/.vapi/presence_lean.db` (**the config `db_path` the LIVE bridge reads**) | **4** (85 probes) | **FALSE** |

**The N≥50 gate is genuinely MET — but only in `bridge.db`, NOT in the DB the running bridge reads.** The
lean-mode switch (`Config().db_path = presence_lean.db`) split the calibration corpus from the live config.

## F-L6B-SEAL-1 (BLOCKER) — corpus/live-DB divergence
Enabling `L6B_ENABLED` on the current config would run the L6B layer + humanity-formula contribution against
`presence_lean.db`'s **N=4** reflex corpus — **below the calibration gate the hard rule protects.** That is
exactly the failure the "never enable without N≥50 ON THE CERTIFIED DEVICE" rule exists to prevent. **The seal
CANNOT fire cleanly until this is reconciled.** Operator decision (pick one):
- **(a) Re-point the bridge config to `bridge.db`** (`db_path`), where the corpus + gate live. Simplest; but
  reverses the lean-mode DB choice (the lean DB exists to keep RP sessions light — see
  `[[project_remote_play_presence_lean_ondemand]]`).
- **(b) Migrate the `l6b_probe_log` reflex rows** for the Edge from `bridge.db` → `presence_lean.db` (the
  `scripts/backup_store.py` `.backup()` pattern / a scoped row-copy), so the live DB clears the gate. Keeps
  lean mode; needs a one-time migration + re-verify N≥50 on `presence_lean.db`.
- **(c) Confirm the live L6B should run on `bridge.db` for enablement** and lean mode is RP-capture-only.
NOTE: tonight's 6-person reaction captures used `--no-store` → they are NOT in either corpus (they live only
in the gitignored `poep_live_capture_*.json`). The L6B gate is met by the operator's own 198 reflexes; tonight's
reactions are the ADVISORY band, a separate thing.

## Firing ceremony (operator, AFTER F-L6B-SEAL-1 is resolved)
1. **Resolve F-L6B-SEAL-1** (a/b/c) and re-run: `python scripts/l6b_probe_status.py` → confirm
   `gate_reached: true` on the DB the bridge will actually read.
2. **Flip the flag.** Process-scoped (preferred, reversible on restart, matches the `CHAIN_SUBMISSION_PAUSED`
   discipline): set `L6B_ENABLED=1` in the bridge's environment for that run. OR a deliberate persistent
   `bridge/.env` edit if you want it durable — your call; Claude does not edit `bridge/.env`.
3. **Restart the bridge**; confirm the startup log + `GET /bridge/...` L6B-progress endpoint reports
   `gate_reached: true` and L6B active.
4. **Watch:** the humanity-formula now includes L6B; confirm it behaves (no spurious flips). Roll back by
   unsetting `L6B_ENABLED` + restart.

## Rails (unchanged)
`poep_enabled` STAYS False (earned separately — see `docs/poep-live-play-ring-arc-spec.md`). No FROZEN/PoAC
edit, no chain, no spend, no Solidity/firmware edit. PV-CI 184. The reaction band + `detect_session` are
advisory and unaffected. This document does not fire anything.
