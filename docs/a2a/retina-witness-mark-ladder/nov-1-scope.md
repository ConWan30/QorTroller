# NOV-1 — Portable stranger-verify dispute pack (scope)

**Status: BUILT (CANDIDATE)** (2026-07-25). Operator GO on plan granted.  
Implementation plan: `nov-1-implementation-plan.md`.  
**Shipped:** `rwm_stranger_pack.py` · `scripts/rwm_nov1_cli.py` · `test_rwm_nov1.py`.  
**Prior gate:** NOV-2 BUILT + dogfood. **Parent:** Path A RWM ladder (`README.md`).

---

## One-sentence claim (honest ceiling)

**NOV-1** lets a **stranger** (no operator machine, no full ring archive) verify a
dispute from a **portable pack**: commitment root + revealed marked-frame media +
membership proof — without needing every unrevealed leaf hash on disk, and without
claiming re-encode / YouTube-rip proof or Path B device signatures.

What it is **not**: live anti-cheat, FROZEN-v1 on day one, automatic on-chain spend,
or “this stream is unforgeable under lossy re-encode.”

---

## Why this layer exists

| Layer | What a steward can do today |
|-------|------------------------------|
| L0 | Re-verify full archive on operator disk |
| NOV-3 | Build escrow; verify needs archive **or** full `leaf_hashes` list in package |
| NOV-2 | SHARE postcard is **indicative only** (no membership proof without LOCAL) |
| **Gap** | Hand a third party a **small pack** that still **cryptographically** checks membership of revealed frames under a root |

NOV-3’s SD-1 shape already ships **all** leaf hashes in LOCAL packages (honest but
not portable/private). NOV-2 SHARE strips them (portable but not proof). **NOV-1**
closes the middle: **Merkle (or equivalent) selective disclosure** so SHARE-class
size can still prove “these reveals are in the committed set.”

---

## Surfaces to reuse

| Surface | Role |
|---------|------|
| NOV-3 leaf preimage + root discipline | Base commitment domain |
| NOV-2 SHARE redaction matrix | Privacy defaults for portable surface |
| NOV-2 session_bind | Optional tip summary inside pack |
| L0 marked/ originals | Reveal media bytes only for disputed frames |
| `sdk/wmp_disclosure.py` | Prior art for sorted-leaf / Merkle shapes (math reuse, not VDC force-fit) |

---

## Proposed artifact (CANDIDATE)

Working name: `qortroller-rwm-stranger-pack-v0`

```text
schema                  CANDIDATE
session_id
commitment_root         set root (Merkle or SD-1-compatible)
merkle_or_mode          "sorted_leaf_list_v0" | "merkle_v0"
set_size
revealed: [{
  frame_index, leaf_hash, frame_hash_hex,
  marked_media_b64_or_path,   # pack-local media
  merkle_proof?               # if merkle_v0
}]
optional session_bind summary (bind_ok / kind only)
reason / case_id
created_ts_ns
```

**Stranger verify:** recompute leaf from media + metadata; check membership under root
via full sorted list (v0.a, still large) **or** Merkle path (v0.b, portable).

**Shipped:** v0.a SD-1 + **v0.b / NOV-1.1 Merkle** (`merkle_inline_media_v0`) both live.

---

## Explicit non-goals

- No FROZEN/PV-CI pin without operator seal
- No automatic chain spend (optional later; kill-switch held)
- No Path B SE perceptual payload
- No stop-path coupling
- No claim that re-encoded streams match exact-pixel leaves

---

## Definition of Done (future build)

| Step | Criterion |
|------|-----------|
| D1 | Implementation plan GO |
| D2 | `build_stranger_pack` / `verify_stranger_pack` pure module |
| D3 | Verify **without** `archive_dir` when media inlined |
| D4 | Tests: happy, bit-flip media, missing leaf, SHARE still non-proof |
| D5 | CLI dogfood from live_01 escrow + archive |
| D6 | Docs honest ceiling |

---

## Parallel ops (not this layer)

`F-RWM-FROZEN` de-dup on `save_capture_crops` (panel_ts) ships separately so the
next live session does not inflate identical PNGs under new timestamps.

---

*Opened 2026-07-25 · sole agent PROCEED · design-only until plan GO for code.*
