# A2A-DEPIN-1 · LEG 3 (NODE-LEDGER-1) · Round 03 — Claude cross-verifies R02: ACCEPTED · PROGRAM COMPLETE

**2026-07-13 · Claude → grok + operator.** grok's R02 built the contribution ledger + anchor CLI
(re-fired once — the first single-turn returned only an intent line, a tooling hiccup; the re-fire
delivered). Ruling (a) independent verification. This closes DEPIN-1.

## Independent verification (leg 3)
- **`node_contribution_ledger.py`** + `qortroller ledger` (append/list, chain-verify on read) +
  `qortroller anchor` (estimate-first). **`test_depin1_node_ledger.py` 63-suite green** · CLI 43/43
  · **PV-CI 183** · `py_compile` clean.
- **Tamper-evident chain (GIC/WEC-style):** genesis deterministic (T1); 3-entry chain intact (T3);
  a mutated entry → `entry_hash` mismatch flagged on read (T4). `QORTROLLER-NODE-LEDGER-v0` candidate
  tag, not a FROZEN family (PV-CI 183 unchanged).
- **Anchor honesty — the load-bearing rails, test-pinned + smoked:**
  - `anchor --session X` DEFAULT = estimate-only **DRY-RUN**; `--execute` requires the triple-gate
    (`CHAIN_SUBMISSION_PAUSED=false` + `--confirm` + hard cost cap) — no autonomous spend.
  - `mark_anchored` **refuses an empty tx** (T8) — the ledger cannot record an anchor it doesn't have;
    `anchored` stays **false** until a real tx hash + block confirm.
  - missing-entry anchor **aborts** (smoked: `no ledger entry for session=…`), never fabricates.
- **w3s_attested provenance** carried honestly from leg 2 (mechanical verify = format/presence, not
  network-validated truth).

**Verdict: ACCEPTED.**

## DEPIN-1 — PROGRAM COMPLETE (desk)
| leg | question | state | commit |
|---|---|---|---|
| 1 · NODE-ID-1 | who is the node? | ✅ node_id spine (derived, no spend) | `b8c706ed` |
| 2 · W3BSTREAM-VERIFY-1 | does the network's layer verify it? | ✅ wasm applet verifies node/session root | `dd3b4224` |
| 3 · NODE-LEDGER-1 | what has it contributed? | ✅ hash-chained ledger, anchorable | (this leg) |

The three legs compose: a session → scorecard root → a hash-chained ledger entry keyed on the
`node_id` spine, carrying the leg-2 attestation, **anchorable to IoTeX in one operator-fired,
estimate-first step**. QorTroller is now a DePIN node with identity + network-layer verification +
a verifiable contribution ledger — every claim tagged for what it proves vs asserts, nothing anchored
until a real tx confirms.

**The only remaining step is yours:** play a match → `qortroller stop` → `qortroller score
--kills-scored N` → `qortroller ledger --append-scorecard <card>` → `qortroller anchor --session <id>
--execute` (when you choose to spend). The next match is the node's first fully-DePIN contribution.

---
*Leg-3 round-03 — verification only. 63-suite + CLI green · PV-CI 183. DEPIN-1 desk-complete.*
