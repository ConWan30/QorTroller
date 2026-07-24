# L6B enable-seal — preparation + firing ceremony (operator-fired) · 2026-07-20

**Status: PREPARED + UNBLOCKED — F-L6B-SEAL-1 RESOLVED 2026-07-20. READY FOR OPERATOR FIRE (not yet fired).**
Claude prepared + reconciled the DB; the operator fires the flag. `L6B_ENABLED` is an operator seal, never
flipped autonomously. Advisory work (the reaction band / `detect_session`) is unaffected — different code path.

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
| `~/.vapi/presence_lean.db` (**the config `db_path` the LIVE bridge reads**) | **4 → 202** (post-migration) | **FALSE → TRUE** |

**The N≥50 gate is now MET on the live DB** after F-L6B-SEAL-1 was resolved (below).

## F-L6B-SEAL-1 (RESOLVED 2026-07-20) — corpus/live-DB divergence, option (b) migrate
Original blocker: enabling `L6B_ENABLED` would have run the L6B layer + humanity-formula contribution against
`presence_lean.db`'s **N=4** reflex corpus — below the calibration gate the hard rule protects. **Resolved via
option (b):** `scripts/l6b_migrate_reflex_rows.py --execute` copied the Edge's 1365 `l6b_probe_log` rows from
`bridge.db` → `presence_lean.db` (idempotent dedup, `id` PK not copied, dst **backed up** to
`presence_lean.db.pre-l6b-migrate.*.bak` first). Result: live DB **independent 4 → 202, `gate_reached: True`**
(confirmed by `scripts/l6b_probe_status.py`, the same reporter the bridge uses). Lean mode preserved. Rollback:
restore the `.bak`. NOTE: tonight's 6-person reaction captures used `--no-store` → NOT in the corpus; the gate
is met by the operator's own reflexes (the ADVISORY reaction band is a separate thing).

## Firing ceremony (operator — F-L6B-SEAL-1 now resolved, ready to fire)
1. **(DONE)** F-L6B-SEAL-1 resolved; `python scripts/l6b_probe_status.py` reports `gate_reached: true` (N=202)
   on `presence_lean.db`, the DB the bridge reads.
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
