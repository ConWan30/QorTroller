# A2A-DEPIN-1 — the DePIN node program (3 synchronized legs, in sequence)

**Chartered 2026-07-13 (operator: "complete all three in sequence, synchronized via A2A").** One
program, three A2A loops run in dependency order and bound by a shared synchronization spine. Turns
QorTroller from a single-node proof tool into a **DePIN node**: it has an on-chain identity, its
output is verified by the network's own processing layer, and its contributions accumulate into a
verifiable, anchorable track record.

## The synchronization spine (why the legs compose, not collide)
A single **`node_id`** join-key threads through all three legs, alongside the existing `session_id`
(the §2.3 named-roots discipline already used by the trio planes / PoSP). `node_id` is derived
canonically from the node's birth (device_id + birth_receipt) — **no chain write to COMPUTE it**.
Every leg references it: leg-2 attestations carry it, leg-3 ledger entries key on it. One node, one
spine; sessions federate under `(node_id, session_id)`, never conflated.

## The three legs, in sequence (each its own A2A loop)
| # | leg | question it answers | desk-buildable? | chain step |
|---|---|---|---|---|
| **1** | **NODE-ID-1** | *who is the node?* — derive a canonical `node_id`, bind it to `birth_receipt`, thread it into the scorecard/receipt | YES (derive from device_id + birth; VMDR device already registered tx `0x68f6cf49`) | none new (registration already happened) |
| **2** | **W3BSTREAM-VERIFY-1** | *does the network's layer verify it?* — the wasm applet (`w3bstream/applet/`) verifies a session's proof root off-chain before it's anchorable (device→W3bstream→L1, the canonical IoTeX DePIN shape) | YES (wasm32 + ingestion test, no spend) | none |
| **3** | **NODE-LEDGER-1** | *what has the node contributed?* — hash-chained contribution ledger `(node_id, session_id, scorecard_root, posp_verdict, w3s_attested, ts)`, each entry anchorable to IoTeX | ledger + root + estimate tooling YES | anchor = estimate-first, **operator-fired**, triple-gated |

Sequence is dependency-forced: leg-3 entries reference the leg-1 `node_id` and the leg-2 attestation.

## Roles (ruling (a) symmetric, per leg)
grok and Claude alternate build/verify per leg (whoever builds, the other cross-verifies before
staging is accepted). grok designs the DePIN-legitimacy claims + red-teams over-claim; Claude grounds
`claim ⊆ reality` against the real primitives + builds. Operator = arbiter + sole committer; the only
actor who fires a chain write (leg-3 anchor) — always estimate-first, hard-capped.

## Rails (standing + program-specific)
`node_id` is DERIVED, not minted (no new on-chain identity spend in leg 1). No PoAC/FROZEN/chain/
secrets edits. `CHAIN_SUBMISSION_PAUSED=true` held; the only spend is the leg-3 anchor, operator-fired
+ triple-gated + estimate-first (reusing `anchor_posp_commitment.py` precedent). Every DePIN claim
tagged for what it proves vs asserts; the ledger never claims a contribution was anchored until the
operator fires the anchor and the tx confirms. Additive over the CLI. Single-committer.

## Stop criterion (program)
All three legs cross-verified + desk-green + the spine coherent (a scorecard names its `node_id`, the
applet verifies a session root, a ledger entry composes both). Then: the operator's next match is the
node's first fully-DePIN contribution, and the leg-3 anchor is a one operator-fired step away.

---
*DEPIN-1 program charter — 2026-07-13. Legs in `docs/a2a/depin/leg{1,2,3}/round-*.md`; envelopes on
the shared bus. Running leg 1 first.*
