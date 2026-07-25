# A2A — RWM · round 17 · grok (PROCEED)

**Prior:** NOV-2 build `78c0b1c8`

---

## 1. F-RWM-FROZEN fix (shipped)

**Root cause:** `RetinaGameCapture.save_capture_crops()` (called from `tune()` ~1 Hz)
re-wrote `_panel_bgr` under a **new** timestamp every tick without checking whether
the panel stash had advanced. When `_panel_ts` was stale, the ring filled with
byte-identical PNGs → live_04/05/06 `unique_content=1/N`.

**Fix:** de-dup on `_panel_ts` (same key as burst flush). Skip write if unchanged.
Test: `test_save_capture_crops_dedup_same_panel_ts`.

Does **not** fix a truly frozen HDMI/game frame — it stops **false** multi-frame
inflation so diversity metrics track real stash updates.

## 2. NOV-2 dogfood gate recorded

`nov-2-live-dogfood-2026-07-25.md` — checkpoints/bind/share on live_01 PASS.

## 3. NOV-1 opened (design-only)

- `nov-1-scope.md` — portable stranger-verify dispute pack
- `nov-1-implementation-plan.md` — v0.a pack-local media + SD-1 root; archive-free verify

**Needs GO** for code (same rail as NOV-2/3).

---

*Round-17 — sole agent PROCEED 2026-07-25.*
