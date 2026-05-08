# WHAT_IF Entry — Kill-Switch Incompleteness Re-Opened by web3.py 7.x rawTransaction Migration (2026-05-06)

**Source**: Empirical wallet-drain incident during Phase O1 D investigation;
audit of all 22 `send_raw_transaction` call sites in `bridge/vapi_bridge/chain.py`
**Phase**: 237.5.1 Path C+ kill-switch architecture fix (closure shipped commit `f1a7be31`)
**Validation**: CLOSED via @_gated_submission decorator + audit script + memory entry

---

## WIF-060 — A Code Migration Can Silently Re-Open A Sealed Wallet Drain

**Operator-observed symptom**: Bridge wallet `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692`
drained from 6.42 IOTX → 0.13 IOTX over ~3 hours during what was supposed to be
a kill-switch-protected session. `CHAIN_SUBMISSION_PAUSED=true` was set in
`bridge/.env`. The Phase 237.5 Path C+ kill-switch was supposedly active.
Yet ~6.27 IOTX disappeared.

**W1 — Failure mode (root-caused via 22-site audit)**:

The Phase 237.5 Path C+ kill-switch only gated the `_send_tx` chokepoint
(commit-1108-line check) plus 3 newer methods that explicitly inherited
the pattern (`anchor_corpus_snapshot`, `anchor_agent_commit`,
`anchor_pda_attestation`). **18 legacy methods bypass `_send_tx` entirely** —
they `build_transaction` + `sign_transaction` + `send_raw_transaction` inline
without ever reading `cfg.chain_submission_paused`.

For months, these 18 methods *appeared* gated because `signed.rawTransaction`
(web3.py 6.x attribute name) raised `AttributeError` on web3.py 7.x where it
was renamed to `raw_transaction`. The exceptions were caught in fire-and-forget
agent loops; no gas was spent. **The protection was accidental** — a happy
side-effect of an unmigrated API.

Commit `a0edaf03` migrated all 12 sites from `signed.rawTransaction` →
`signed.raw_transaction`. This was the correct web3.py 7.x fix. But it
inadvertently re-enabled 18 chain submission paths that had been silently
broken. Post-fix on bridge restart with `CHAIN_SUBMISSION_PAUSED=true`:
agent loops fired txs, IoTeX testnet's broken P256 precompile reverted them
with status=0, each tx consumed all allocated gas (~0.15 IOTX × 41 txs in
nonce window 185→226 = ~6.27 IOTX drained).

**Generalized lesson**: A protective invariant that depends on coverage at
N call sites can be silently re-broken by a code migration that touches
those sites. The kill-switch documentation said "operator can pause
on-chain transactions" — and was technically correct — but didn't say "only
the 4 of 22 sites that go through `_send_tx`."

**W2 — Closure (commit `f1a7be31`)**:

`@_gated_submission` decorator (functools.wraps) inserted at module top of
`chain.py`. Applied to all 18 leaking methods. Returns `""` sentinel when
paused (matches existing str-return convention; callers already treat empty
tx_hash as "not on chain"). Coverage went from 4/22 → **22/22**.

**Permanent rule** (memory file `feedback_kill_switch_coverage.md`):
- Every async method in chain.py that calls `send_raw_transaction` MUST
  carry `@_gated_submission`
- Audit regex script provided to verify coverage at any time
- Future migrations cannot silently re-open the drain without the audit
  surfacing the gap

**Operational impact**: Wallet 6.42 → 0.13 IOTX means G4 (Phase 239
gate_attestation anchor) is wallet-blocked until refill. Without WIF-060
closure, every future rawTransaction-style migration risks recurrence.

**Cross-references**:
- Commit `f1a7be31` — atomic 22/22 path fix
- Memory `feedback_kill_switch_coverage.md` — rule + audit script
- Memory `project_kill_switch_fix_2026_05_06.md` — incident snapshot
- Predecessor: WIF-059 (Phase 237.5 original drain finding; this WIF
  documents a corollary the original missed)
