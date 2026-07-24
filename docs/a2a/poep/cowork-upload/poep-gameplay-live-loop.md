# A2A-POEP-GAMEPLAY-LIVE — dual-connect challenge-live

**Opened 2026-07-17 · operator: "open live dual-connect design"**  
**Design:** `docs/a2a/poep/poep-gameplay-live-design.md`  
**Prior arc:** `poep-gameplay` dry skeleton **PASS** (round-05); round-04 honesty model frozen for this path.

## Goal

Wire `mode=live` + `activity_source=bridge` + real HID sparse challenges so  
`presence_session_candidate_ok` can be earned **during real play** (still not a flip).

## Roles (ruling a)

| | |
|--|--|
| **grok** | Design (this open) + post-build verify |
| **Claude / Cowork** | Build L1→L2 against design; tests; staged-only |
| **Operator** | Commit; dual-connect dogfood (L3); sole committer |

## Rounds

```text
round-live-01-grok-open     : design + BUILD-NOW L1/L2     [THIS]
round-live-02-claude-build  : implement + tests
round-live-03-grok-verify   : PASS|FIX against design §8
```

## Rails

poep_enabled / L6B / L6_CHALLENGES **False** · amplitude ≤80 · no desk volume mainline ·  
no chain/FROZEN/PoAC · ready? before live fire · operator-only commit  

## Success

L1+L2 green + design bars; L3 optional operator dogfood producing one candidate session artifact  
with `presence_session_candidate_ok=True` under real dual-connect (or honest False with reasons).
