# NOV-2 — Cross-primitive session bind + multi-checkpoint locator (scope)

**Status: SCOPE OPEN + PLAN DRAFTED (design-only)** (2026-07-25).  
Implementation plan: `nov-2-implementation-plan.md` — **operator GO required before code**.  
**Prior gate:** NOV-3 BUILT (CANDIDATE) + dogfood escrow against `cfb_rwm_live_01` / live_05 / live_06.  
**Parent:** Path A RWM ladder (`README.md`).  
**Not yet opened:** NOV-1.

---

## One-sentence claim (honest ceiling)

**NOV-2** upgrades an L0 RWM session from “locator breadcrumb + leaf set” to a
**verified cross-primitive bind**: the escrow / chain tip can cite a real,
re-checkable PoAC-segment or GIC tip (when present), and the mark stream can
carry **more than one checkpoint** so a long session is addressable at multiple
chain positions — without claiming re-encode proof or Path B device signatures.

What it is **not**: live anti-cheat, optical CONTINUOUS, on-chain auto-anchor,
or “this YouTube rip proves the pristine archive.”

---

## Why this layer exists

L0 + NOV-3 already give:

1. Per-frame leaf inventory + selective dispute escrow (membership in a committed set)
2. Single checkpoint mark (`checkpoint_index=0` only in L0 ship)
3. Free-text `external_ref` on escrow — **not verified**

Disputes and tournament stewards next need:

| Gap | Why it hurts |
|-----|----------------|
| Free-text `external_ref` | Anyone can type a fake PoAC/GIC id; package still verifies as escrow |
| Single checkpoint | Long matches only pin one chain position in the visual mark stream |
| No dual-surface share pack | NOV-3 reveals hashes/paths; no SHARE-redacted postcard for non-steward handoff |

NOV-2 closes those **without** inventing a new FROZEN-v1 family on day one.

---

## Surfaces to reuse (do not rebuild)

| Surface | Role in NOV-2 |
|---------|----------------|
| L0 `rwm_manifest_chain.json` | Session identity + leaf inventory |
| NOV-3 escrow schema v0 | Extend with *optional* verified bind fields; keep v0 packages readable |
| PoAC 228B wire / chain link | **Read-only** tip reference if a session export exists — never mutate wire format |
| GIC / grind chain tip | Optional bind when grind session co-runs; fail-open if absent |
| `qortroller receipt` dual-surface pattern | Model for LOCAL full vs SHARE-redacted dispute postcard |
| Locator encode/decode | Multi-checkpoint = multiple symbol windows, same palette/composite path |

---

## Proposed NOV-2 artifacts (CANDIDATE — not frozen)

### A. Verified external bind (replaces free-text-only)

Working name: `qortroller-rwm-session-bind-v0`

```text
schema                  CANDIDATE string
session_id              from L0
l0_chain_tip_hex        from L0 (must match re-verify)
bind_kind               none | poac_segment | gic_tip | dual
bind_ref_hex            tip / segment id (hex)
bind_proof              how to re-check (path, algorithm id, or empty if local-only)
bind_ok                 bool — set only after verify_bind() succeeds
```

**Fail-closed for bind_ok:** if the cited tip cannot be re-checked from local
artifacts, `bind_ok=false` and stewards must treat the package as L0/NOV-3 only.

**Fail-open for L0:** missing PoAC/GIC never breaks stop-path or L0 harvest.

### B. Multi-checkpoint locator

```text
checkpoint_index        int >= 0
checkpoint_ts_ns        issuance time for that mark window
chain_head_at_cp        32B tip bound into mark commitment (same L0 formula)
n_checkpoints           inventory length
```

L0 remains valid with `n_checkpoints=1`. NOV-2 decode accepts N windows and
reports which checkpoint matched.

### C. Dispute share postcard (optional, offline)

Reuse dual-surface discipline (LOCAL full package vs SHARE-redacted):

- SHARE: schema, session_id, commitment_root, revealed_indices, bind_ok summary — **no** device_id if policy says so, **no** full leaf list if size/privacy requires
- LOCAL: full NOV-3 package + bind proof paths

Never auto-upload. Consent banner stays.

---

## Explicit non-goals (this layer)

- No FROZEN-v1 / PV-CI pin in the first ship
- No automatic chain spend / on-chain escrow registry
- No Path B SE-signed perceptual payload (still banked on hardware gate)
- No re-encode / YouTube-rip verification claim
- No `poep_enabled` / L6B / kill-switch flips
- No coupling that can fail `cmd_stop`

---

## Definition of Done (future *build* round — not this scope open)

| Step | Criterion |
|------|-----------|
| D1 | Implementation plan reviewed (operator GO) |
| D2 | `verify_bind()` pure helper: happy + wrong tip + missing artifact |
| D3 | Multi-checkpoint encode/decode unit tests (N=1 backward-compat + N≥2) |
| D4 | Escrow v0 packages still verify; optional bind fields additive |
| D5 | Offline CLI dogfood on a real multi-minute archive |
| D6 | Docs: honest ceiling; SHARE matrix explicit |
| D7 | No PoAC wire / FROZEN domain-tag mutation |

“Scope open” ≠ “code authorized.”

---

## Relationship to live ops (parallel, not blocking)

Diverse live capture (`cfb_rwm_live_06+` with non-frozen panel ROI) remains the
**evidence** gate for trusting L0 under real play. NOV-2 design does not wait
on that capture, but any multi-checkpoint live-verify will need a long enough
session with content diversity (watcher `frozen_ring_alert` + eye-check).

---

## Open questions for the operator (plan inputs)

1. **Bind priority** — PoAC segment only, GIC only, or dual-optional?
2. **Checkpoint cadence** — wall-clock (e.g. every 60s) vs every N frames vs operator mark?
3. **SHARE redaction** — strip `device_id_hex` by default?
4. **Escrow schema** — additive fields on v0 vs new `…-escrow-v1` string?

---

*Opened 2026-07-25 · sole agent (grok) · design-only.*
