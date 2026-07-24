---
name: chain-spend
description: Read BEFORE any action that could spend IOTX, deploy a contract, or write to IoTeX — including "just estimate gas", running a deploy script, or flipping CHAIN_SUBMISSION_PAUSED. Covers the triple-gate ceremony, the estimate-first rule, and why chain writes are operator-fired.
---

# Chain writes and spending

Real money on a real chain. Testnet IOTX is refilled by hand from a faucet, and
the bridge wallet is the same key that deployed 72 live contracts — a mistake
here is not recoverable by re-running.

**The rule that matters most: agents do not fire chain writes. The operator does.**
Not "agents ask first, then fire" — the operator types the command. Every on-chain
transaction in this repo's history was operator-fired, down to the human finger,
including ones an agent had fully prepared and verified.

## Before you touch anything chain-shaped

`CHAIN_SUBMISSION_PAUSED=true` lives in `bridge/.env` and is the kill switch.

- Never edit it in the file. Lift it **process-scoped** for one command
  (`CHAIN_SUBMISSION_PAUSED=false python ...`) so it re-arms on the next restart.
- It gates every `send_raw_transaction` path via `@_gated_submission`. A pre-fix
  leak once drained 6.27 IOTX because one path wasn't decorated — if you add a
  new send path, it needs the decorator.

## Estimate first, always

`estimate_gas` before every send, and treat a revert during estimation as the
answer — not something to retry with more gas. This single habit turned several
wrong-model ceremony attempts into **zero-spend** learning during the ioID arc:
each wrong assumption reverted at estimation and cost nothing.

Static-gas wrappers are a known trap. `record_adjudication` and
`record_gate_attestation_on_chain` shipped with hardcoded gas (80k/100k) and
reverted out-of-gas on IoTeX (status 101), wasting ~0.36 IOTX. Use
`estimate_gas * 1.25`, the pattern `anchor_corpus_snapshot` already follows.

## The triple gate

Deploy and spend scripts require three independent things, by design:

1. an **intent env var** (e.g. `MFG_REGISTER_CONFIRM=1`, `VAPI_TBR_DEPLOY_CONFIRM=1`)
2. an explicit **`--execute` / `--confirm` CLI flag**
3. a **hard cap** on spend, checked against a live balance read

Plus a deployer identity check (must equal the bridge wallet) and a 2x balance
guard. If you are writing a new spend path, reproduce all of it. The gates are
not ceremony for its own sake — they are what makes an agent-prepared,
operator-fired transaction safe to hand over.

## Reporting spend honestly

Read the balance live (`eth_getBalance` on `babel-api.testnet.iotex.io`, needs a
`User-Agent` header or it 403s). Never echo a balance from a previous note or
summary — the wallet line in `CLAUDE.md` drifted stale for weeks that way, which
is why the `SENSOR-A-LIVE:WALLET` anchor now exists to catch it mechanically.

Report measured cost, not estimated cost, and say which transaction it came from.

## Two-key surfaces

Some agents (Sentry, Curator) are at `O3_ACTING` authority but executor-disabled
on purpose: their actions spend real IOTX. Making them autonomous is deliberately
a **two-key decision** — flip the per-agent flag *and* lift the kill switch. Do
not do one and treat it as done. Guardian is the only autonomous agent by design,
and only because its authority is local/off-chain at 0.0 IOTX budget.

## Related

- `docs/posr-keeper-runbook.md` — operational cost math for a live keeper
- `protocol-invariants` skill — FROZEN-v1 surfaces and the governance seal boundary
- `contracts/deployed-addresses.json` — the live address book (72 keys, some superseded)
