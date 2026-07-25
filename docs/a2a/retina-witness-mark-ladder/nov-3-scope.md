# NOV-3 — Ledger-native dispute escrow (scope)

**Status: SCOPE OPEN** (2026-07-24) — design-only until operator GO on an implementation plan.  
**Prior gate:** L0 live-verify PASS — `l0-live-verify-2026-07-24.md`.  
**Parent:** Path A RWM ladder (`README.md`).  
**Not yet opened:** NOV-2, NOV-1.

---

## One-sentence claim (honest ceiling)

**NOV-3** lets a gamer (or operator steward) put an L0 RWM session’s frame-hash leaves into a **selective-disclosure escrow**: commit to the full set of leaves, reveal only the frames needed for a dispute, and keep the rest committed-but-hidden — without inventing a new FROZEN-v1 family on day one.

What it is **not**: live anti-cheat, optical CONTINUOUS proof, device-signed Path B marks, or “this stream is unforgeable under re-encode.”

---

## Why this layer exists

L0 already produces:

1. **Pristine originals** (tier-1 `manifest.json` hashes — forensic baseline)
2. **Marked sidecar** (`marked/`) + **session chain** (`rwm_manifest_chain.json`) — additive proof layer
3. **Per-frame addressable leaves** (`frame_index`, `frame_hash_hex`) — L0 plan explicitly shaped these for SD-1

Disputes need a *subset* of frames (e.g. “these 12 seconds”) without shipping the whole ring or claiming more than L0 can prove. That is selective disclosure over leaves, not a new hash algorithm.

From L0 implementation plan (NOV-3 forward-compat note):

> entries are individually addressable (frame_index-keyed) … matching `sdk/wmp_disclosure.py`’s “sorted leaf hashes” shape, so NOV-3 can wire SD-1’s `build_disclosure` / `verify_disclosure` directly over manifest entries later without a manifest redesign.

---

## Surfaces to reuse (do not rebuild)

| Surface | Role in NOV-3 |
|---------|----------------|
| `rwm_manifest_chain.json` frames[] | Leaf inventory + hashes (already on disk) |
| `sdk/wmp_disclosure.py` | `build_disclosure` / `verify_disclosure` — set commitment + reveal subset |
| `sdk/wmp_derived.py` | Claim hashing if L0 leaves are wrapped as VDC-shaped claims |
| `marked/` + originals | Reveal packages point at paths; never overwrite originals |
| L0 chain verify | Any escrow package that fails L0 re-verify is dead on arrival |

**Sizing expectation (from scope.md reviewer note):** new surface may reduce to **wiring** SD-1 over L0 leaves + a small escrow record schema — not a greenfield reveal protocol.

---

## Proposed NOV-3 artifact (CANDIDATE — not frozen)

Working name: `qortroller-rwm-dispute-escrow-v0` (schema string TBD in implementation plan).

Minimum fields (draft — subject to plan review):

```text
schema                  CANDIDATE string
session_id              from L0 chain
device_id_hex           from L0 chain (never fabricated)
l0_chain_tip_hex        binding to L0 session chain head
leaf_set                sorted frame_hash_hex (or SD-1 leaf_hashes)
commitment_root         SD-1 style root over leaves + inventory
revealed_frame_indices  subset authorized for this dispute
revealed_paths          marked/ and/or original relative paths
reason / case_id        human audit text (min length; not secrets)
created_ts_ns           issuance time (session-monotonic ok if stated)
```

**Fail-closed:** if L0 `verify_session_chain` fails on the cited session, escrow issuance returns None / error — never invent leaves.

**Fail-open vs stop path:** NOV-3 must **never** break `cmd_stop` or L0 harvest. Escrow is offline or opt-in post-stop.

---

## Explicit non-goals (this layer)

- No FROZEN-v1 promotion in the first ship
- No automatic on-chain anchor (optional later; kill-switch held)
- No multi-checkpoint locator index (still L0 `checkpoint_index=0`; multi-cp is ladder-later)
- No Path B device-signed mark payload
- No claim that re-encoded YouTube rips verify against exact-pixel L0 hashes (Path A boundary — pristine archive only)
- No continuum with PoEP / L6B flag flips

---

## Definition of Done (for a future NOV-3 *build* round — not this scope open)

| Step | Criterion |
|------|-----------|
| D1 | Implementation plan reviewed (operator GO) — this scope is not that plan |
| D2 | Pure helper: L0 frame rows → SD-1-compatible claims / leaves |
| D3 | `build_escrow` + `verify_escrow` unit tests (happy + bit-flip leaf + wrong session) |
| D4 | Offline CLI or script against a real L0 archive (gitignored path; no crop commit) |
| D5 | Docs: honest ceiling + non-goals restated at ship |
| D6 | No PoAC / FROZEN / PV-CI ceremony unless operator explicitly seals a new pin |

“Scope open” ≠ “code authorized.” Code needs the same GO discipline L0 used.

---

## Open questions (for the implementation plan, not blocked on this file)

1. **Leaf identity:** raw `frame_hash_hex` as SD-1 leaves vs wrap each frame as a VDC claim with `derivation_id=f"rwm_frame_{i}"`?
2. **Reveal package size:** ship marked PNGs only, originals only, or hash-only + out-of-band path for media?
3. **Who can open an escrow?** gamer wallet only vs operator dual-key for tournament steward disputes?
4. **Binding to PoAC / GIC:** optional cross-link field now, or strict L0-only until NOV-2?
5. **Retention / erasure:** BP-007 / consent categories for dispute media — cite consent ledger before any public share path.

---

## Rails reaffirm

228B PoAC · FROZEN-v1 · PV-CI 184 · no secrets in git · capture archives gitignored · `CHAIN_SUBMISSION_PAUSED` · single-committer=operator · CANDIDATE schemas only until ceremony

---

*Opened 2026-07-24 after L0 live-verify on `cfb_rwm_live_01`. Implementation plan is the next authorized deliverable — not code.*
