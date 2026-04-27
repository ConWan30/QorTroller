# WHAT_IF Entry — IoTeX Chain Drain During P256 Precompile Failure (2026-04-26)

**Source**: Phase 237.5 Path C+ session diagnosis; Explore agent investigation;
operator-observed wallet drop from ~18.5 IOTX to 0.5525 IOTX in one session
**Phase**: 237.5 Path C+ correction (kill-switch shipped same commit)
**Validation**: PENDING_AUTORESEARCH (this entry seeds the corpus with a
real protocol-side risk surfaced by the inaugural-anchor diagnosis path)

---

## WIF-059 — Broken Precompile + Retry-Blind Agents = Silent Wallet Drain

**Operator-observed symptom**: Bridge wallet
`0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692` lost ~17.95 IOTX over a single
3-4 hour session against IoTeX testnet, with no operator-initiated chain
transactions accounting for the loss. Phase 237.5 inaugural anchor attempts
(~6-8 calls × ~0.16 IOTX each = ~1.3 IOTX) explained only a small fraction.
The remaining ~16+ IOTX was burned by background bridge agents that the
operator didn't realize were active.

**W1 — Failure mode (verified by code citation + Explore agent)**:

When IoTeX testnet's P256 precompile is unavailable (current state per
bridge startup log: "Batch dead-lettered: IoTeX testnet P256 precompile
unavailable (0xf46a06ea)"), every agent that fires `chain.*` transactions
without checking dry_run / dead-letter state causes failed-but-gas-consuming
on-chain attempts. Two retry-blind paths produce sustained drain:

1. **Primary culprit**: `bridge/vapi_bridge/dualshock_integration.py:2324-2335`
   fires 3 fire-and-forget chain calls (`submit_pitl_proof`,
   `ensure_ioid_registered`, `ioid_increment_session`) per PITL proof
   during `_session_loop()`. Inspection confirms:
   - No `agent_dry_run_mode` guard (compare with vhp_renewal_agent.py:70
     which DOES check it)
   - No P256 precompile error handling
   - Fire-and-forget via `asyncio.create_task(...)` — failures don't
     propagate back; tasks die silently after consuming gas
   - Triggered every ~100ms during session warmup → 30-100 attempts/minute
2. **Secondary culprit**: `bridge/vapi_bridge/batcher.py:471-527` retry
   loop re-queues failed submissions. The `_p256_unavailable=True` flag
   set at `:311` only gates LOGGING (line 313: "DEBUG thereafter"), NOT
   actual retry attempts. Each retry executes a fresh `_send_tx` call.

**Implication**: This is a **protocol-side economic risk** specific to
testnet operations where infrastructure (precompiles, RPC) may be
unreliable. A bridge running unattended overnight against a broken
precompile can drain a wallet entirely without surfacing any visible
error to the operator. The bridge log emits the dead-letter message ONCE
and goes silent. Cost-vs-detection asymmetry is severe.

**Mitigation shipped (Path C+ kill-switch)**:

Global `chain_submission_paused: bool` config field (env var
`CHAIN_SUBMISSION_PAUSED`, default `False`). When `True`:
- `chain.py:_send_tx` short-circuits with `RuntimeError` (gates batcher
  path + most modern-pattern chain.* methods)
- `chain.anchor_corpus_snapshot` returns `(None, False)` early
- `dualshock_integration.py:2324-2335` skips the 3 task creates entirely

`bridge/.env` set to `CHAIN_SUBMISSION_PAUSED=true` immediately. Bridge
can run during the wallet funding gap with zero on-chain activity. Read-
only paths (eth_call, view functions) unaffected — on-chain queries for
diagnostic purposes still work.

**Status**: MITIGATED via `chain_submission_paused`. Kill-switch is
operator-controlled per-restart via env var; default `False` for
forward-compat with existing tournament deployments.

**W2 — Opportunity (novel)**: **Chain-Submission Pause as Protocol
Invariant for Testnet Operations**.

Mechanism: codify `chain_submission_paused` as a first-class protocol
invariant (alongside FROZEN-v1 cryptographic primitives in PATTERN-017),
specifically for the testnet-vs-mainnet operational distinction:

- On testnet (where infrastructure breakage is a known recurring class of
  problem), `chain_submission_paused=true` is the **default** during any
  observed precompile failure or RPC instability. The bridge auto-detects
  P256 precompile errors and flips the flag, posts an `agent_event`
  notifying the operator, and continues serving local PoAC + GIC chain
  operations with zero on-chain submission attempts.
- On mainnet (where precompile availability is a hard requirement), the
  flag is hardcoded `false` and any P256 failure triggers an immediate
  HARD_HALT alert — distinguishing testnet drain (silent, recoverable)
  from mainnet outage (loud, requires intervention).

This is a generalizable pattern: **distinguish the network's reliability
model from the protocol's expected behavior, and let the protocol
gracefully degrade when infrastructure conflicts with assumptions**.

**Phase candidate**: Phase 237.5.1 (post-funding) — auto-detect P256
failure and auto-set `chain_submission_paused=true` at runtime; surface
the flag state in `/health` endpoint; add Hardhat test for the auto-detect
behavior; add a tx-attempt rate-limiter as defense-in-depth.

**Exclusive because**: VAPI is the first DePIN gaming protocol whose
operator runtime is observable enough to surface this precise failure
mode (hundreds of failed retry attempts visible in bridge log + DB) AND
whose kill-switch primitive sits at the right architectural layer
(`_send_tx` chokepoint at `chain.py:1062`) to gate uniformly.

**Status**: OPEN — kill-switch shipped manually-activated; auto-detect
mechanism deferred to Phase 237.5.1 candidate. Funding gap of "several
days" creates a natural window for shipping the auto-detect refinement
before the next mainnet-class operation.

**Why this seeds the autoresearch wiki loop usefully**:

The autoresearch cycle's `format_cycle_prompt()` (Phase 238 wiring,
`vapi_autoresearch.py`) embeds active FSCA contradiction findings. WIF-059
documents a problem class FSCA cannot directly detect — silent economic
drain via background agent loops on a broken-but-not-failing chain. The
detection signal lives in the wallet balance over time, NOT in the
agent's own success/failure state. Autoresearch cycles that reference
WIF-059 can identify other instances of this pattern in future:
"high-frequency operation × silent retry × external infrastructure
unreliability = silent resource drain."

Sister WIF reference:
- WIF-058 (PS5_COMPAT_MODE dormant) is the same architectural shape:
  fix exists in code, gated by operator-only config knob, with no
  automated detection path. Path C+'s kill-switch follows the same
  default-False, env-var-gated pattern.

---

## Code citations

- Drain culprit: `bridge/vapi_bridge/dualshock_integration.py:2324-2335`
- Retry-blind path: `bridge/vapi_bridge/batcher.py:471-527`
- P256 dead-letter (logging only): `bridge/vapi_bridge/batcher.py:307,311,313`
- Kill-switch: `bridge/vapi_bridge/config.py:chain_submission_paused`
- Kill-switch chokepoint: `bridge/vapi_bridge/chain.py:_send_tx` early-return
- Kill-switch caller-site: `bridge/vapi_bridge/dualshock_integration.py:2324`
  with `_chain_paused` guard
- Phase 237.5 ship: commit `f9c6ec11`
- Phase 237.5 Path C+ correction: this commit (TBD)
