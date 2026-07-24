---
name: protocol-invariants
description: The PV-CI invariant gate, FROZEN-v1 commitment families, the PATTERN-017 hash-chain discipline, Mythos drift variants, and the governance-seal boundary. Read before touching any commitment formula, adding a b"VAPI-..." domain tag, changing the invariant baseline, or editing a FROZEN surface.
---

# Protocol invariants and FROZEN surfaces

## The gate

`python scripts/vapi_invariant_gate.py` runs **first** in CI and fails closed.
Baseline is **184** invariants, pinned in `.github/INVARIANTS_ALLOWLIST.json`.
The gate and the allowlist are the single source of truth — if a doc says a
different number, the doc is stale.

Each invariant pins a code region by SHA-256 of the *matched lines*, not by
path. Moving content byte-identically into a new file does not break the pin;
changing the content does. Adding or editing an invariant means updating both
the gate logic and the allowlist digest **in the same commit**, or CI fails.

## Never do these

- Modify the **228-byte PoAC wire format**. The chain-link hash is
  `SHA-256(raw[0:164])` — the 164-byte body only, not the full 228.
- Change a **FROZEN-v1 formula**: byte order, domain tag, or hash algorithm.
  A change means a new version and a new genesis tag (e.g. WEC v1 → WEC v2),
  never an in-place edit.
- Inline a post-quantum signature into the PoAC record or on-chain payload.
  Arc 7's whole design is the decoupled sidecar: the 3,309-byte ML-DSA-65
  signature lives off-chain, only its 32-byte commitment crosses the boundary.
  `INV-ARC7-001` raises `HardForkDisallowedError` if the frame grows.

## Adding a new commitment family

Every `b"VAPI-..."` / `b"QORTROLLER-..."` domain-tag literal under
`bridge/vapi_bridge/` must be registered in `mythos_variants.py`, or the
**Mythos PR Gate** fails the PR:

- `_KNOWN_CAPABILITY_TAGS` — CANDIDATE families (no ceremony needed)
- `_PATTERN_017_FROZEN_TAGS` — governance-sealed FROZEN-v1 families

New work is CANDIDATE. Promotion to FROZEN is an operator ceremony, not an
agent decision.

**This is the single most-repeated mistake in this repo.** PRs #29/#41/#42/#43
each merged red for exactly this and needed a reconciliation commit afterward.
Register the tag in the same PR that introduces it, and sweep for *every* new
literal rather than the one you remembered.

## PATTERN-017 hash chains

Established by WEC (`watchdog_chain.py`) and GIC (`grind_chain.py`); shared
discipline, domain-specific fields:

- prev-hash chaining, tagged genesis, fixed-width big-endian integers
- `verify_*` fails closed — returns `False`, never raises. Make the except
  clause match what the call graph actually raises (`struct.error` and
  `AttributeError` are not `ValueError`/`TypeError` — that gap shipped once)
- pure functions, no internal clock read: **the caller owns time**, and owes a
  monotonicity guard (`INV-GIC-002`: `if ts_ns <= prev: ts_ns = prev + 1`)
  against backward NTP corrections

Field layouts differ per family by design. Divergences from precedent are fine
when stated; silent divergence is the problem.

## The governance-seal boundary

`scripts/vapi_invariant_gate.py --generate` is agent-runnable for a legitimate
refactor or bugfix. The `--confirm-governance` variant — an intentional
invariant change — stays **operator-fired**, even under an autonomous loop.

## Drift variants

Mythos runs 7 variants; the PR gate runs the two highest-leverage ones
(Frozen + Crypto). Others surface via `fleet_coherence_log`. Notably
`mythos_claude_md_curation` audits `CLAUDE.md` itself against
`target_chars=60_000` / `warn_chars=100_000` and flags stale NOTEs for archival.

## Related

- `chain-spend` skill — the spend/deploy ceremony
- `verification-first` skill — the standard invariant work is held to
- `.github/INVARIANTS_ALLOWLIST.json` — the 184 pinned entries
