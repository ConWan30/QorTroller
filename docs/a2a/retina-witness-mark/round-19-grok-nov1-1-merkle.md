# A2A — RWM · round 19 · grok (PROCEED → NOV-1.1 Merkle)

**Prior:** NOV-1 `ed8145b3`

---

## What shipped

| Item | Detail |
|------|--------|
| Mode | `merkle_inline_media_v0` |
| Domain tags | `VAPI-RWM-MERKLE-LEAF/NODE-v0` · `VAPI-RWM-STRANGER-MERKLE-v0` |
| Pack | merkle_root + inclusion_proof per reveal; **no** full `leaf_hashes` |
| CLI | `--mode merkle_inline_media_v0` |
| Tests | +3 merkle (8 total NOV-1 suite) |
| Dogfood | live_01 set_size=1076 · 3 reveals · VERIFY OK archive-free |

## Honest ceiling

Still membership under committed set + pack-local media. Not re-encode proof. Sibling hashes leak on proof path (standard Merkle).

## Ladder remainder (optional)

| Item | Notes |
|------|-------|
| live_07 | operator play — validate F-RWM-FROZEN de-dup + diversity |
| NOV-2.1 | multi-checkpoint **re-encode** at stop (touches RWM issue path) |
| Hold | Path A offline surface complete for CANDIDATE desk tools |

*Round-19 — sole agent PROCEED 2026-07-25.*
