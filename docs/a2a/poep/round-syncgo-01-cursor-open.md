# A2A SYNC-GO r01 — CURSOR OPEN (first GOs under ACTIVE_GAMEPLAY → path to SYNCHRONIZED_CONTROLLER)

**Micro-arc:** hardware fire is PROVEN (operator felt amp=80 manual `POST /operator/operator/poep/fire`).
Last live attach (`audits/poep_session_identity_attach_615bf5f54f94dac9.json`) returned
**`IDENTITY_ONLY`** with **`n_go_issued=0`**, **`gameplay_active_fraction=0.0`**,
**`activity_ok=false`** — challenges never issued because the activity gate was not ACTIVE_GAMEPLAY.
Charter ruling **(a)**: Cursor **BUILDS**; Grok **AUDITS / steers**; operator **only** commits.
**Spend ZERO; no flag flips (`L6B_ENABLED` / `poep_enabled` stay False); PV-CI 184; sealed l9
challenge/presence model stay honest (no forge GO).**

## Roles
| Role | Agent |
|------|--------|
| Builder | **Cursor** (this open → r02 build after grok forward) |
| Auditor / forward | **Grok** (this chat or round-*-grok-*.txt) |
| Commit | **Operator only** |

## Grounded state (do not re-litigate)
1. **F-RIG27-6** fire timeout 20s/25s — in tree (RP drain).
2. **F-RIG27-8** device-clock companion **committed** `c7ba84b7` — silicon still unproven on a
   successful attach path (`clock=device` not yet shown on attach GOs).
3. Manual fire **works**: `fired=true real_hardware=true`; operator **felt** R2 adaptive tug at amp 80.
4. Default gameplay amp is **60** (max **80**); hold ~15ms pulse — easy to miss if not holding R2.
5. Attach run 615bf5f5: **zero GOs** because `challenge_live` refused non-ACTIVE_GAMEPLAY
   (`refused_activity`) and/or never saw trigger activity (`live_trigger_active_fraction` was 0 at
   sample time). Identity lane OK (`identity_bound=true`).

## Goal (definition of done)
A **repeatable operator path** (runbook + any *minimal* code/UX needed) such that one Shell B
`--live` attach during real CFB 27 play yields:

- `n_go_issued >= 2` (real_hardware=True GOs), and  
- preferably `n_go_verify_pass >= 1` (device or t_mono in-band + peak — honest), and  
- controller_presence `verdict` is either **`SYNCHRONIZED_CONTROLLER`** **or** honest
  `IDENTITY_ONLY` with **non-zero** GO evidence (so the next gap is verify/clock, not “never fired”).

Plus a short **operator checklist** (activity green → fire → feel → react) in
`docs/poep-campaign-runbook.md` or a sibling `docs/a2a/poep/syncgo-operator-card.md`.

## Ceiling (will NOT claim)
- Does **not** flip `poep_enabled` / `L6B_ENABLED` / kill-switch.
- Does **not** weaken activity / PCC fail-closed to “always fire” (that would be a fabrication seam).
- Does **not** treat dry/injected fire as SYNCHRONIZED.
- Does **not** require a full AIT/corpus recal this arc.
- SYNCHRONIZED is a **session-liveness candidate**, not a product launch claim.

## Options for Cursor (grok will rank/kill in r02)
- **(a) Operator-path only:** runbook + preflight that blocks attach until
  `live_trigger_active_fraction > 0` and capture NOMINAL/EXCLUSIVE_USB; no code change.
- **(b) Attach CLI preflight:** `poep_session_identity_attach.py --live` polls capture-health,
  waits/retries for ACTIVE_GAMEPLAY (with timeout + clear stderr), then challenges; optional
  `--amplitude 80` flag (still clamped ≤80).
- **(c) Bridge activity signal quality:** ensure capture-health fields the attach fetcher uses
  actually carry trigger fraction during RP (if mismatch → fix mapping only).
- **(d) Out of scope unless (b)/(c) prove insufficient:** longer hold_ms / pulse feelability —
  only with explicit operator go (playability risk).

## Files likely in blast radius (if code)
- `scripts/poep_session_identity_attach.py`
- `l9_presence/poep_session_identity_run.py` / activity fetcher wiring (read-only first)
- `docs/poep-campaign-runbook.md` or new operator card
- Tests: fakes only for preflight wait / refuse-on-menu (no HID)

**Forbidden without new A2A:** sealed verify band forge; `classify_activity` always-ACTIVE;
dropping PCC gate; editing FROZEN PoAC / PV-CI pins casually.

## Sequencing
```
r01 this open (operator confirms scope)
  → r02 grok FORWARD (rank options, bars, seams)
  → Cursor BUILD + claims C1..Cn + auditor packet
  → r03 grok VERIFY (HOLD/PASS)
  → fix / re-verify
  → operator commit
  → rig: mid-drive attach → GOs felt → SYNCHRONIZED or next honest gap
```

## Operator: paste this into Cursor

```
You are the BUILDER in QorTroller A2A (charter ruling a). Grok is the independent auditor.
Read: docs/a2a/poep/round-syncgo-01-cursor-open.md
HOLD until operator confirms r01 scope, then wait for docs/a2a/poep/round-syncgo-02-grok-brainstorm.txt
(or operator paste of grok r02). Do NOT mark your own work PASS. Zero spend; no L6B_ENABLED /
poep_enabled flips; no weakening refused_activity into a free fire.
After build: numbered claims C1..Cn (file:line) + auditor packet for grok.
```

## Grok next (this chat)
On operator **GO** for r01 scope: write **r02 FORWARD** into
`docs/a2a/poep/round-syncgo-02-grok-brainstorm.txt` (option rank + r03 bars + seams).
