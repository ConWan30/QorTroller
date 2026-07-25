# A2A — RWM · round 15 · grok (NOV-2 implementation plan)

**Channel:** operator “commit and push, then proceed with next task if its NOV-2”  
**Prior:** live_06 post `23097401` · NOV-2 scope `9a8f670a`

---

## Commit hygiene first

| Item | Action |
|------|--------|
| live_06 post docs | already on `main` (`23097401`) |
| Escrow JSON / `*.jsonl` | **left uncommitted** (local dogfood; may carry device_id + leaf set) |
| joypad-os dirty | ignored (submodule noise) |

Nothing else shippable was pending for “commit and push.”

---

## NOV-2 next task delivered

**D1 implementation plan** (design-only):

`docs/a2a/retina-witness-mark-ladder/nov-2-implementation-plan.md`

### Locked decisions (Q1–Q4)

| Q | Lock |
|---|------|
| Bind | dual-optional PoAC + GIC; `bind_ok` only when tips re-check |
| Checkpoints | v0 **inventory** over frame indices (default quintile); L0 stop still paints cp=0 |
| SHARE | strip `device_id_hex` + full leaf lists by default |
| Schema | additive optional `session_bind` on escrow v0 + three new CANDIDATE schemas |

### Explicit non-code until GO

No modules, no stop-path, no FROZEN/PoAC mutation. Reply **GO NOV-2 plan** to authorize build (D2–D7).

---

*Round-15 — sole agent 2026-07-25.*
