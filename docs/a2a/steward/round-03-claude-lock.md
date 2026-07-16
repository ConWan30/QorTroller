# A2A-STEWARD-EVOLVE · round-03 — Claude grounds + LOCKS the design

grok round-02 replaced the weak seeds convincingly. Locked design (rails carried verbatim):

## The 3 novel steward tasks (each a new autonomous SIGNAL → DRAFT, never an act)
| steward | task | consumes (new signal) | emits (draft) | act gate |
|---|---|---|---|---|
| **Guardian** | **PCRA** — Protocol Claim Residue Auditor | `docs/a2a/**` + `audits/**` + machine oracles (SENSOR-A anchors, node-ledger tip, PV-CI count, flag states, WMP may/must-not-claim) | `claim_residue` audit drafts | none (0 IOTX, local draft) |
| **Sentry** | **MPJA** — Multi-Surface Provenance Join Attestor | node-ledger entries + PoSP/match-cert verdicts + scorecard roots (joined by session_id) | `join` attestation drafts | two-key + estimate-first (IOTX) |
| **Curator** | **DPIG** — Data-Product Integrity Gate | WMP bundle/listing rows + buyer-category outcomes + consent bitmask/expiry + fleet-telemetry floor | `product_integrity` suspend/relist recommendations | two-key (IOTX) |

## Cross-cutting primitive: SEL-v0 (Steward Evolution Ledger)
Graduated **task-class** autonomy — "may steward S auto-persist drafts of class T without operator
pre-review?" — NEVER auto-spend IOTX (distinct from O3-SUPERSEDE's phase ladder). **External labels
ONLY** (operator_decision + adversarial holdout + challenge-survival); the steward never scores itself;
graduation is itself a draft the operator accepts. CANDIDATE domain tag `VAPI-SEL-v0` (not FROZEN, no
governance seal in this arc). **Challenge Graph** is SEL's assurance mode (3 directed draft-only edges;
only the operator resolves; issuing a challenge can't raise your own score; absence ≠ approval).

## 4th novelty: PGSW (Presence-Gated Steward Window)
Read-only gate wrapping the drafters: `presence_window_open` iff the registered node's latest PoSP is
SYNCHRONIZED within τ OR a live node session is active (respecting KAS hygiene — never AUTHORED-without-
HID-topology). Closed → stewards draft only LOW-severity/backlog; open → HIGH-severity. Uses PoEP/PoSP/
DePIN as OPERATOR LIVENESS for agentic authority. 0 IOTX, default-OFF, lands after B1 when signals stable.

## Build sequence (operator-paced; grok-agreed)
B0 rails+flags (all default False) · **B1 Guardian PCRA (BUILD-FIRST)** · B2 Sentry MPJA · B3 Curator
DPIG · B4 SEL-v0 (pure external scorer + candidate hash-chain; graduation = draft) · B5 Challenge Graph ·
B6 PGSW. Do NOT build SEL before a steward has a new task-class to score; do NOT FROZEN-seal SEL here.

## B1 PCRA v0 scope (this build — the mechanically-precise, high-confidence residue classes)
- **CEILING_OVERCLAIM** — a scanned surface asserts a capability the oracle denies (e.g. text claims
  presence/PoEP-live/flip while `poep_enabled=False`; claims N≥50-Edge/all-pairs while the gate is unmet).
- **STALE_ANCHOR** — a `SENSOR-A-LIVE` anchor / prose figure drifts from the live oracle (wallet, contract
  count, PV-CI baseline). (Reuses the Sensor-A drift concept as an oracle.)
- **UNBANKED_BUILD** — an `docs/a2a/**` round claims SHIP/PASS with no corresponding `audits/**` banking.
Deferred to v0.1: ORPHAN_CLAIM (needs claim-extraction NLP) + MAY_CLAIM_VIOLATION (needs the per-product
must-not-claim registry) — named, not silently dropped.
PCRA is PURE (detect over injected inputs) + a repo adapter + a local draft emitter; `pcra_enabled`
default False; drafts are local records (gitignored), never git/chain. Precision is later scored by SEL
on operator accept/overturn — PCRA does not self-grade.
